"""Adaptive per-(provider, key) rate limiting for the extraction fleet.

Design (owner directive, 2026-08-29): providers differ in the KIND of
limit, not just the number —

* local (MLX/Ollama): the bottleneck is CONCURRENCY (GPU/VRAM). A dynamic
  semaphore, seeded low.
* cloud: the bottleneck is RATE (RPM + TPM). Token buckets gate calls
  before they leave, with a concurrency cap only as a safety ceiling.

Both kinds ADAPT (AIMD, TCP-style): +1 on every K consecutive clean
successes, ×0.5 on 429/503/timeout, honoring Retry-After (the lane holds
every acquire until the provider's not-before instant). Cloud buckets
sync from standard rate-limit response headers when present, so the
limiter throttles BEFORE the 429 instead of reacting to it. A per-lane
circuit breaker (closed → open on error spike → half-open: exactly ONE
probe → closed on success / re-open on failure) keeps a down provider
from being hammered.

Concurrency contract (audit 2026-08-29): no lock is ever held while
sleeping; a non-blocking acquire never waits; a refused acquire never
leaks a slot, a bucket token, or the breaker's probe.

No third-party dependencies: threading-based (the extraction fleet uses
sync httpx + ThreadPoolExecutor). Static config values are seeds and
ceilings only; `adaptive` moves the effective limit inside [min, max] at
runtime.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import Protocol

log = logging.getLogger("polymath.llm_limiter")

# AIMD constants (TCP-flavored)
SUCCESS_STREAK_FOR_INCREASE = 4      # +1 slot per K clean successes
DECREASE_FACTOR = 0.5                # ×0.5 on throttle/timeout
BREAKER_ERROR_RATE = 0.5             # open when >50% of window failed
BREAKER_WINDOW = 10                  # ... across the last N outcomes
BREAKER_COOLDOWN_S = 30.0            # open → half-open after this long
RETRY_AFTER_MAX_S = 60.0             # never honor a Retry-After beyond this
BREAKER_WAIT_MAX_S = 75.0            # blocking acquire waits this long for a half-open probe
BUDGET_STREAK_FOR_INCREASE = 4       # batch budget: +step per K clean batches


class ControllerStore(Protocol):
    """Durable state for a controller (see state_store.PostgresControllerStore)."""

    def load(self, key: str) -> dict | None: ...

    def save(self, key: str, state: dict) -> None: ...


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

    @classmethod
    def from_config(cls, base: ProviderLimit, cfg: dict | None) -> ProviderLimit:
        """Overlay a config mapping on a code-level seed. Unknown keys are
        ignored (a typo in limiter.yaml must not crash the first
        extraction call)."""
        known = {f.name for f in fields(cls)}
        merged = {**base.__dict__,
                  **{k: v for k, v in (cfg or {}).items() if k in known}}
        return cls(**merged)


def _now() -> float:
    return time.monotonic()


def parse_retry_after(value) -> float | None:
    """Seconds from a Retry-After header value; None when absent or in the
    HTTP-date form (which the fleet does not honor)."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, seconds)


class _TokenBucket:
    """Refilling bucket (tokens, per-minute window)."""

    def __init__(self, capacity: int) -> None:
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.rate = capacity / 60.0     # refill per second
        self.ts = _now()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = _now()
        self.tokens = min(self.capacity,
                          self.tokens + (now - self.ts) * self.rate)
        self.ts = now

    def acquire(self, n: float, block: bool = True) -> bool:
        # A request larger than the whole bucket could never be satisfied
        # (tokens are capped at capacity): clamp so a blocking acquire waits
        # for a FULL bucket instead of forever.
        n = min(float(n), self.capacity)
        while True:
            with self._lock:
                self._refill_locked()
                if self.tokens >= n:
                    self.tokens -= n
                    return True
                if not block:
                    return False
                need = (n - self.tokens) / self.rate
            # sleep OUTSIDE the lock: header sync and other acquirers must
            # never convoy behind a sleeper
            time.sleep(min(max(need, 0.0), 1.0))

    def refund(self, n: float) -> None:
        """Hand back tokens taken for a call that was never made."""
        with self._lock:
            self.tokens = min(self.capacity, self.tokens + float(n))

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

    @property
    def held(self) -> int:
        with self._cond:
            return self._held

    def set_limit(self, limit: int) -> None:
        with self._cond:
            self._limit = limit
            self._cond.notify_all()

    def acquire(self) -> None:
        with self._cond:
            while self._held >= self._limit:
                self._cond.wait(timeout=0.5)
            self._held += 1

    def try_acquire(self) -> bool:
        """Non-blocking: check-and-increment under the SAME lock (no
        TOCTOU window between the check and the take)."""
        with self._cond:
            if self._held >= self._limit:
                return False
            self._held += 1
            return True

    def release(self) -> None:
        with self._cond:
            self._held = max(0, self._held - 1)
            self._cond.notify_all()


@dataclass
class _Breaker:
    """closed → open (error spike) → half-open (ONE probe after cooldown)
    → closed on probe success / open again on probe failure.

    Calls admitted before the breaker opened may still complete while it
    is half-open; their outcome is treated as the probe's — a documented
    approximation that errs toward staying open."""
    window: int = BREAKER_WINDOW
    error_rate: float = BREAKER_ERROR_RATE
    cooldown_s: float = BREAKER_COOLDOWN_S
    outcomes: list = field(default_factory=list)   # 1 ok / 0 fail
    opened_at: float | None = None
    half_open: bool = False
    probe_in_flight: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock,
                                 repr=False, compare=False)

    def allow(self) -> bool:
        with self.lock:
            if self.opened_at is None:
                return True
            if self.probe_in_flight:
                return False
            if _now() - self.opened_at >= self.cooldown_s:
                self.half_open = True
                self.probe_in_flight = True     # exactly one probe
                return True
            return False

    def release_probe(self) -> None:
        """The admitted probe never reached the provider (rate refusal or
        non-blocking saturation): hand the probe slot back."""
        with self.lock:
            if self.half_open:
                self.probe_in_flight = False

    def record(self, ok: bool) -> None:
        with self.lock:
            if self.half_open:
                self.half_open = False
                self.probe_in_flight = False
                if ok:
                    self.opened_at = None
                    self.outcomes.clear()
                else:
                    self.opened_at = _now()     # re-open immediately
                return
            self.outcomes.append(1 if ok else 0)
            if len(self.outcomes) > self.window:
                self.outcomes.pop(0)
            if self.opened_at is not None:
                return                          # already open: stragglers do not extend the cooldown
            if (len(self.outcomes) >= self.window
                    and sum(self.outcomes) / len(self.outcomes) < self.error_rate):
                self.opened_at = _now()

    @property
    def is_open(self) -> bool:
        with self.lock:
            return self.opened_at is not None


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
        self._not_before = 0.0            # Retry-After horizon (monotonic)
        self._lock = threading.Lock()
        self._increases = 0
        self._decreases = 0
        self._last_logged_decreases = 0
        self._on_change: Callable[[dict], None] | None = None

    # -- durable state -----------------------------------------------------

    def state(self) -> dict:
        with self._lock:
            return {"effective": self._effective, "streak": self._streak,
                    "floor": self._floor, "ceiling": self._ceil,
                    "increases": self._increases, "decreases": self._decreases}

    def restore(self, state: dict | None) -> bool:
        """Adopt a persisted effective limit (clamped into [floor, ceil]).
        The persisted value is what the controller had FOUND before the
        process died; the yaml seed is only for a lane with no history."""
        if not state or "effective" not in state:
            return False
        try:
            value = int(state["effective"])
        except (TypeError, ValueError):
            return False
        with self._lock:
            self._effective = max(self._floor, min(value, self._ceil))
            self._streak = 0
            self._increases = int(state.get("increases", 0) or 0)
            self._decreases = int(state.get("decreases", 0) or 0)
            self._sem.set_limit(self._effective)
        return True

    def _emit_change(self) -> None:
        state = self.state()
        # Operators must SEE the controller move without opening artifacts:
        # a halving is a warning (provider pushed back), a climb is info.
        (log.warning if state["decreases"] > self._last_logged_decreases else log.info)(
            "llm limiter %s effective=%s floor=%s ceiling=%s (+%s/-%s)",
            self.name, state["effective"], state["floor"], state["ceiling"],
            state["increases"], state["decreases"])
        self._last_logged_decreases = state["decreases"]
        cb = self._on_change
        if cb is not None:
            cb(state)                 # outside self._lock: may do I/O

    # -- acquisition -------------------------------------------------------

    def _honor_retry_after(self, block: bool) -> bool:
        with self._lock:
            delay = self._not_before - _now()
        if delay <= 0:
            return True
        if not block:
            return False
        time.sleep(min(delay, RETRY_AFTER_MAX_S))
        return True

    def _wait_for_breaker(self) -> bool:
        deadline = _now() + BREAKER_WAIT_MAX_S
        while _now() < deadline:
            time.sleep(min(1.0, max(0.05, self._breaker.cooldown_s / 10)))
            if self._breaker.allow():
                return True
        return False

    def acquire(self, est_tokens: float = 0.0, block: bool = True) -> bool:
        """Take the concurrency slot + rate tokens. Returns False when
        non-blocking and the lane is saturated, when the breaker is open,
        or (non-blocking) inside a Retry-After hold. A False return never
        leaves anything held."""
        if not self._honor_retry_after(block):
            return False
        if not self._breaker.allow():
            # BREAKER-WAIT (measured 2026-08-30): failing fast here turned
            # one OOM storm into a dead ticket — every stage retry hit the
            # still-open breaker within seconds and burned its attempt.
            # A BLOCKING caller waits for the cooldown and takes the
            # half-open probe itself; only a non-blocking caller (or a
            # breaker that stays open past BREAKER_WAIT_MAX_S) is refused.
            if not block or not self._wait_for_breaker():
                return False
        if block:
            self._sem.acquire()
        elif not self._sem.try_acquire():
            self._breaker.release_probe()
            return False
        if self.spec.kind == "rate":
            refused = False
            if self._rpm is not None and not self._rpm.acquire(1.0, block):
                refused = True
            elif (self._tpm is not None and est_tokens > 0
                    and not self._tpm.acquire(est_tokens, block)):
                if self._rpm is not None:
                    self._rpm.refund(1.0)         # no call will be made
                refused = True
            if refused:
                self._sem.release()
                self._breaker.release_probe()
                return False
        return True

    def release(self) -> None:
        self._sem.release()

    # -- feedback (AIMD + breaker + header sync) ---------------------------

    def record_success(self, headers: dict | None = None) -> None:
        changed = False
        with self._lock:
            self._breaker.record(True)
            self._streak += 1
            if (self.spec.adaptive
                    and self._streak >= SUCCESS_STREAK_FOR_INCREASE
                    and self._effective < self._ceil):
                self._effective += 1
                self._streak = 0
                self._increases += 1
                self._sem.set_limit(self._effective)
                changed = True
        self._sync_headers(headers)
        if changed:
            self._emit_change()

    def record_failure(self, retry_after: float | str | None = None,
                       headers: dict | None = None) -> None:
        changed = False
        with self._lock:
            self._breaker.record(False)
            self._streak = 0
            if self.spec.adaptive:
                new = max(self._floor, int(self._effective * DECREASE_FACTOR))
                changed = new != self._effective
                self._effective = new
                self._decreases += 1
                self._sem.set_limit(self._effective)
            seconds = parse_retry_after(retry_after)
            if seconds is not None:
                self._not_before = max(
                    self._not_before, _now() + min(seconds, RETRY_AFTER_MAX_S))
        self._sync_headers(headers)
        if changed:
            self._emit_change()

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
        return self._breaker.is_open

    @property
    def not_before(self) -> float:
        with self._lock:
            return self._not_before


class AdaptiveBudget:
    """AIMD over a scalar budget — the LOCAL lane's real throughput knob.

    Local batched calls run one at a time (the server serializes decodes),
    so "concurrency" there is the number of tokens per batched call. The
    budget climbs +step per K clean batches toward the ceiling and halves
    on a GPU-OOM, exactly like the concurrency limiter — and persists the
    same way, so the fleet keeps the batch size it found."""

    def __init__(self, name: str, *, seed: int, floor: int, ceiling: int,
                 step: int) -> None:
        self.name = name
        self._floor = max(1, int(floor))
        self._ceil = max(self._floor, int(ceiling))
        self._step = max(1, int(step))
        self._effective = max(self._floor, min(int(seed), self._ceil))
        self._streak = 0
        self._increases = 0
        self._ooms = 0
        self._last_logged_ooms = 0
        self._lock = threading.Lock()
        self._on_change: Callable[[dict], None] | None = None

    @property
    def effective(self) -> int:
        with self._lock:
            return self._effective

    @property
    def ceiling(self) -> int:
        return self._ceil

    def record_success(self) -> None:
        changed = False
        with self._lock:
            self._streak += 1
            if self._streak >= BUDGET_STREAK_FOR_INCREASE and self._effective < self._ceil:
                self._effective = min(self._ceil, self._effective + self._step)
                self._streak = 0
                self._increases += 1
                changed = True
        if changed:
            self._emit_change()

    def record_oom(self) -> None:
        with self._lock:
            self._effective = max(self._floor, int(self._effective * DECREASE_FACTOR))
            self._streak = 0
            self._ooms += 1
        self._emit_change()

    def state(self) -> dict:
        with self._lock:
            return {"effective": self._effective, "streak": self._streak,
                    "floor": self._floor, "ceiling": self._ceil, "step": self._step,
                    "increases": self._increases, "ooms": self._ooms}

    def restore(self, state: dict | None) -> bool:
        if not state or "effective" not in state:
            return False
        try:
            value = int(state["effective"])
        except (TypeError, ValueError):
            return False
        with self._lock:
            self._effective = max(self._floor, min(value, self._ceil))
            self._streak = 0
            self._increases = int(state.get("increases", 0) or 0)
            self._ooms = int(state.get("ooms", 0) or 0)
        return True

    def _emit_change(self) -> None:
        state = self.state()
        (log.warning if state["ooms"] > self._last_logged_ooms else log.info)(
            "llm batch budget %s effective=%s floor=%s ceiling=%s (+%s/oom %s)",
            self.name, state["effective"], state["floor"], state["ceiling"],
            state["increases"], state["ooms"])
        self._last_logged_ooms = state["ooms"]
        cb = self._on_change
        if cb is not None:
            cb(state)


class LimiterRegistry:
    """(provider, api_key) → AdaptiveLimiter. Different keys of the same
    provider each get their own lane — quotas scale linearly. With a
    ControllerStore attached, every lane/budget restores its persisted
    effective value on creation and writes it back on every change."""

    def __init__(self) -> None:
        self._lanes: dict[tuple[str, str], AdaptiveLimiter] = {}
        self._budgets: dict[str, AdaptiveBudget] = {}
        self._store: ControllerStore | None = None
        self._lock = threading.Lock()

    @property
    def store_attached(self) -> bool:
        return self._store is not None

    def attach_store(self, store: ControllerStore) -> None:
        """Attach durable state; lanes created earlier are restored now."""
        with self._lock:
            self._store = store
            for lim in self._lanes.values():
                self._bind(lim, lim.name)
            for key, budget in self._budgets.items():
                self._bind(budget, key)

    def _bind(self, controller, key: str) -> None:
        store = self._store
        if store is None:
            return
        controller.restore(store.load(key))
        controller._on_change = lambda state, _k=key: store.save(_k, state)

    def lane(self, provider: str, key: str, spec: ProviderLimit) -> AdaptiveLimiter:
        k = (provider, key or "default")
        with self._lock:
            if k not in self._lanes:
                lim = AdaptiveLimiter(f"{provider}[{k[1]}]", spec)
                self._bind(lim, lim.name)
                self._lanes[k] = lim
            return self._lanes[k]

    def budget(self, key: str, *, seed: int, floor: int, ceiling: int,
               step: int) -> AdaptiveBudget:
        with self._lock:
            if key not in self._budgets:
                budget = AdaptiveBudget(key, seed=seed, floor=floor,
                                        ceiling=ceiling, step=step)
                self._bind(budget, key)
                self._budgets[key] = budget
            return self._budgets[key]


REGISTRY = LimiterRegistry()
