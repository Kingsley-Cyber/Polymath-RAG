"""Adaptive per-(provider, key) rate limiting for the extraction fleet.

Design (owner directive, 2026-08-29): providers differ in the KIND of
limit, not just the number —

* local (MLX/Ollama): the bottleneck is CONCURRENCY (GPU/VRAM). A dynamic
  semaphore, seeded low.
* cloud: the bottleneck is RATE (RPM + TPM). Token buckets gate calls
  before they leave, with a concurrency cap only as a safety ceiling.

Both kinds ADAPT (AIMD, TCP-style): +1 on every K consecutive clean
successes, ×0.5 on 429/503/timeout, honoring Retry-After. Cloud buckets
sync from standard rate-limit response headers when present, so the
limiter throttles BEFORE the 429 instead of reacting to it. A per-lane
circuit breaker (closed → open on error spike → half-open probe) keeps a
down provider from being hammered.

No third-party dependencies: ~200 lines, threading-based (the extraction
fleet uses sync httpx + ThreadPoolExecutor). Static config values are
seeds and ceilings only; `adaptive` moves the effective limit inside
[min, max] at runtime.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# AIMD constants (TCP-flavored)
SUCCESS_STREAK_FOR_INCREASE = 4      # +1 slot per K clean successes
DECREASE_FACTOR = 0.5                # ×0.5 on throttle/timeout
BREAKER_ERROR_RATE = 0.5             # open when >50% of window failed
BREAKER_WINDOW = 10                  # ... across the last N outcomes
BREAKER_COOLDOWN_S = 30.0            # open → half-open after this long



@dataclass
class ProviderLimit:
    """Static seed + ceilings for one provider kind (config-loaded)."""
    kind: str                    # "concurrency" | "rate"
    init: int = 2
    min: int = 1
    max: int = 6
    rpm: int | None = None       # rate kind: calls per minute
    tpm: int | None = None       # rate kind: tokens per minute
    conc_cap: int | None = None  # rate kind: safety concurrency ceiling
    adaptive: bool = True
    use_headers: bool = False


def _now() -> float:
    return time.monotonic()


class _TokenBucket:
    """Refilling bucket (tokens, per-minute window)."""

    def __init__(self, capacity: int) -> None:
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.rate = capacity / 60.0     # refill per second
        self.ts = _now()
        self._lock = threading.Lock()

    def acquire(self, n: float, block: bool = True) -> bool:
        with self._lock:
            while True:
                now = _now()
                self.tokens = min(self.capacity,
                                  self.tokens + (now - self.ts) * self.rate)
                self.ts = now
                if self.tokens >= n:
                    self.tokens -= n
                    return True
                if not block:
                    return False
                need = (n - self.tokens) / self.rate
                time.sleep(min(need, 1.0))

    def sync_remaining(self, remaining: float) -> None:
        """Header sync: trust the provider's own budget report."""
        with self._lock:
            self.tokens = min(self.tokens, max(0.0, remaining))


class _DynamicSemaphore:
    """Counting semaphore whose ceiling moves with AIMD."""

    def __init__(self, limit: int) -> None:
        self._cond = threading.Condition()
        self._limit = limit
        self._held = 0

    @property
    def limit(self) -> int:
        with self._cond:
            return self._limit

    def set_limit(self, limit: int) -> None:
        with self._cond:
            self._limit = limit
            self._cond.notify_all()

    def acquire(self) -> None:
        with self._cond:
            while self._held >= self._limit:
                self._cond.wait(timeout=0.5)
            self._held += 1

    def release(self) -> None:
        with self._cond:
            self._held = max(0, self._held - 1)
            self._cond.notify_all()


@dataclass
class _Breaker:
    window: int = BREAKER_WINDOW
    error_rate: float = BREAKER_ERROR_RATE
    cooldown_s: float = BREAKER_COOLDOWN_S
    outcomes: list = field(default_factory=list)   # 1 ok / 0 fail
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if _now() - self.opened_at >= self.cooldown_s:
            self.opened_at = None       # half-open: one probe allowed
            self.outcomes.clear()
            return True
        return False

    def record(self, ok: bool) -> None:
        self.outcomes.append(1 if ok else 0)
        if len(self.outcomes) > self.window:
            self.outcomes.pop(0)
        recent = self.outcomes[-self.window:]
        if (len(recent) >= self.window
                and sum(recent) / len(recent) < self.error_rate):
            self.opened_at = _now()


class AdaptiveLimiter:
    """One lane's adaptive limiter. Keyed per (provider, api_key) by the
    registry so multi-key pools scale linearly."""

    def __init__(self, name: str, spec: ProviderLimit) -> None:
        self.name = name
        self.spec = spec
        if spec.kind == "rate":
            ceil = spec.conc_cap or spec.max
            seed = spec.init or ceil          # AIMD seeds LOW and climbs
        else:
            seed, ceil = spec.init, spec.max
        ceil = max(ceil, spec.min)
        seed = max(spec.min, min(seed, ceil))
        self._floor = spec.min
        self._ceil = ceil
        self._sem = _DynamicSemaphore(seed)
        self._rpm = _TokenBucket(spec.rpm) if spec.kind == "rate" and spec.rpm else None
        self._tpm = _TokenBucket(spec.tpm) if spec.kind == "rate" and spec.tpm else None
        self._breaker = _Breaker()
        self._streak = 0
        self._effective = seed
        self._lock = threading.Lock()

    # -- acquisition -------------------------------------------------------

    def acquire(self, est_tokens: float = 0.0, block: bool = True) -> bool:
        """Take the concurrency slot + rate tokens. Returns False when
        non-blocking and the lane is saturated or the breaker is open."""
        if not self._breaker.allow():
            return False
        if not block and self._sem._held >= self._sem.limit:
            return False
        self._sem.acquire()
        if self.spec.kind == "rate":
            refused = False
            if self._rpm is not None and not self._rpm.acquire(1.0, block):
                refused = True
            elif (self._tpm is not None and est_tokens > 0
                    and not self._tpm.acquire(est_tokens, block)):
                refused = True
            if refused:
                self.release()
                return False
        return True

    def release(self) -> None:
        self._sem.release()

    # -- feedback (AIMD + breaker + header sync) ---------------------------

    def record_success(self, headers: dict | None = None) -> None:
        with self._lock:
            self._breaker.record(True)
            self._streak += 1
            if (self.spec.adaptive
                    and self._streak >= SUCCESS_STREAK_FOR_INCREASE
                    and self._effective < self._ceil):
                self._effective += 1
                self._streak = 0
                self._sem.set_limit(self._effective)
        self._sync_headers(headers)

    def record_failure(self, retry_after: float | None = None,
                       headers: dict | None = None) -> None:
        with self._lock:
            self._breaker.record(False)
            self._streak = 0
            if self.spec.adaptive:
                self._effective = max(self._floor,
                                      int(self._effective * DECREASE_FACTOR))
                self._sem.set_limit(self._effective)
        self._sync_headers(headers)

    def _sync_headers(self, headers: dict | None) -> None:
        if not headers or not self.spec.use_headers:
            return
        for key, bucket in (("x-ratelimit-remaining-requests", self._rpm),
                            ("x-ratelimit-remaining-tokens", self._tpm),
                            ("anthropic-ratelimit-tokens-remaining", self._tpm)):
            if bucket is not None and key in (headers or {}):
                try:
                    bucket.sync_remaining(float(headers[key]))
                except (TypeError, ValueError):
                    pass

    @property
    def effective(self) -> int:
        return self._effective

    @property
    def breaker_open(self) -> bool:
        return self._breaker.opened_at is not None


class LimiterRegistry:
    """(provider, api_key) → AdaptiveLimiter. Different keys of the same
    provider each get their own lane — quotas scale linearly."""

    def __init__(self) -> None:
        self._lanes: dict[tuple[str, str], AdaptiveLimiter] = {}
        self._lock = threading.Lock()

    def lane(self, provider: str, key: str, spec: ProviderLimit) -> AdaptiveLimiter:
        k = (provider, key or "default")
        with self._lock:
            if k not in self._lanes:
                self._lanes[k] = AdaptiveLimiter(f"{provider}[{k[1]}]", spec)
            return self._lanes[k]


REGISTRY = LimiterRegistry()
