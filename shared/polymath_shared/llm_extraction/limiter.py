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
import os
import re
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
    # FLEET-V3: requests-per-DAY budget (provider daily quota, e.g.
    # gemini free tier) — acquire refuses once spent, the ladder
    # routes around; resets at UTC midnight. None = unlimited.
    rpd: int | None = None
    # FLEET-V3: provider FAMILY for the shared circuit — four healthy
    # keys on one throttled project 429 together; per-lane AIMD can't
    # see that. Lanes of one family share a damp signal.
    family: str | None = None

    @classmethod
    def from_config(cls, base: ProviderLimit, cfg: dict | None) -> ProviderLimit:
        """Overlay a config mapping on a code-level seed. Unknown keys are
        ignored (a typo in limiter.yaml must not crash the first
        extraction call)."""
        known = {f.name for f in fields(cls)}
        merged = {**base.__dict__,
                  **{k: v for k, v in (cfg or {}).items() if k in known}}
        return cls(**merged)


def _utc_iso() -> str:
    """RPD-DURABILITY-V1 (D-4): UTC wall-clock stamp for the durable row. The day
    bucket itself is already UTC (`time.gmtime`), so the two agree by construction."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


# --- control-plane observability (GROQ-MAP-CONTROL-PLANE-REPAIR-V1) ----------
# A single boolean `acquire()` collapsed every admission gate into one opaque
# "refused". `admit()` returns a LimiterDecision naming WHICH gate refused, so
# the caller can distinguish a family-circuit cooldown from a breaker, a local
# daily cap, or a provider-declared exhaustion — none of which dispatch HTTP.
REFUSE_RETRY_AFTER = "RETRY_AFTER"
REFUSE_FAMILY_GATE = "FAMILY_GATE"
REFUSE_BREAKER = "BREAKER"
REFUSE_CONCURRENCY = "CONCURRENCY"
REFUSE_RPM = "RPM"
REFUSE_TPM = "TPM"
REFUSE_RPD = "RPD"                 # local daily safety cap spent
REFUSE_PROVIDER_RPD = "PROVIDER_RPD"  # provider header says the day is spent


@dataclass(frozen=True)
class LimiterDecision:
    """The outcome of one admission attempt. `admitted=False` ALWAYS means no
    HTTP request is dispatched and no provider quota is consumed."""
    admitted: bool
    reason: str | None = None          # None iff admitted; else a REFUSE_* class
    retry_after: float | None = None


_DURATION_RE = re.compile(
    r"^(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?$")


def parse_reset_seconds(value) -> float | None:
    """Seconds until a rate-limit reset. Accepts plain seconds ("60", "60.5")
    and Groq's duration form ("2m59.56s", "1h2m3s"). None when unparseable."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        pass
    m = _DURATION_RE.match(str(value).strip())
    if not m or not any(m.groups()):
        return None
    h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600.0 + mi * 60.0 + s


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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

    def adopt_capacity(self, new_cap: float) -> bool:
        """FLEET-V3 header-declared ceiling adoption: grow-only — the
        provider's own declared limit raises the configured seed. The
        caller clamps against the safety multiple."""
        with self._lock:
            if new_cap > self.capacity:
                self.capacity = float(new_cap)
                return True
        return False

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


#: FLEET-V3 family circuit tuning
FAMILY_FAILURE_THRESHOLD = 8      # correlated failures ...
FAMILY_WINDOW_S = 30.0            # ... inside this window ...
FAMILY_COOLDOWN_S = 45.0          # ... open the family this long
FAMILY_REFRESH_S = 10.0           # cross-process re-read cadence
CEILING_ADOPT_MAX_MULTIPLE = 4    # never adopt past seed x this


class _FamilyGate:
    """Shared per-family damp signal (FLEET-V3): correlated failures
    across a provider family open a family-wide cooldown, persisted
    through the controller store so every worker process sees it.
    Deliberately NOT a scheduler — a boolean gate with a cooldown,
    fail-open on any store trouble."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}
        self._open_until: dict[str, float] = {}
        self._last_read: dict[str, float] = {}

    def note_failure(self, family: str, store) -> None:
        now = _now()
        with self._lock:
            window = [ts for ts in self._failures.get(family, [])
                      if now - ts <= FAMILY_WINDOW_S]
            window.append(now)
            self._failures[family] = window
            if (len(window) >= FAMILY_FAILURE_THRESHOLD
                    and self._open_until.get(family, 0.0) < now):
                self._open_until[family] = now + FAMILY_COOLDOWN_S
                self._failures[family] = []
                if store is not None:
                    try:
                        store.save(f"family:{family}", {
                            "open_for_s": FAMILY_COOLDOWN_S,
                            "opened_wall": time.time()})
                    except Exception:
                        pass

    def allowed(self, family: str, store) -> bool:
        now = _now()
        with self._lock:
            if self._open_until.get(family, 0.0) > now:
                return False
            if (store is not None
                    and now - self._last_read.get(family, 0.0)
                    > FAMILY_REFRESH_S):
                self._last_read[family] = now
                try:
                    state = store.load(f"family:{family}") or {}
                    opened = float(state.get("opened_wall") or 0.0)
                    open_for = float(state.get("open_for_s") or 0.0)
                    remaining = opened + open_for - time.time()
                    if remaining > 0:
                        self._open_until[family] = now + remaining
                        return False
                except Exception:
                    pass
        return True


FAMILY_GATE = _FamilyGate()


def _registry_store():
    """The registry's attached controller store (None before attach) —
    resolved lazily so the family gate works from any process that
    attached persistence, and fails open everywhere else."""
    try:
        return REGISTRY._store
    except Exception:
        return None


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
        # FLEET-V3: daily budget + header-adopted ceilings
        self._day = time.strftime("%Y-%m-%d", time.gmtime())
        self._day_count = 0
        self._adopted_rpm: float | None = None
        self._adopted_tpm: float | None = None
        # PROVIDER-RPD OBSERVATION (distinct from the local `_day_count` safety
        # cap): the provider's OWN declared daily request budget, read from
        # x-ratelimit-*-requests. Never fed into the per-minute _rpm bucket.
        self._provider_rpd_limit: float | None = None
        self._provider_rpd_remaining: float | None = None
        self._provider_rpd_reset_at: float | None = None   # monotonic epoch end
        # RPD-DURABILITY-V1 (D-4): the day counter must survive a restart, not only
        # an AIMD move. `_emit_change()` fires when the controller CHANGES SHAPE, so a
        # lane that runs steadily at concurrency 1 and never adapts (exactly the pMAP
        # lanes) persisted nothing — `day_count` lived in memory and died with the
        # worker. These track a coalesced persist of the counter itself.
        self._last_dispatch_at: str | None = None
        self._last_rpd_persist_mono: float = 0.0
        self._rpd_dirty: bool = False

    # -- durable state -----------------------------------------------------

    def state(self) -> dict:
        with self._lock:
            return {"effective": self._effective, "streak": self._streak,
                    "floor": self._floor, "ceiling": self._ceil,
                    "increases": self._increases, "decreases": self._decreases,
                    "day": self._day, "day_count": self._day_count,
                    # RPD-DURABILITY-V1 (D-4): when this lane last DISPATCHED, so a
                    # restart can reconcile "day/window + dispatch count + last update"
                    # from durable truth. The lane is the row key and its account/
                    # function come from the LANE REGISTRY join (never duplicated here,
                    # and never a secret).
                    "last_dispatch_at": self._last_dispatch_at,
                    "adopted_rpm": self._adopted_rpm,
                    "adopted_tpm": self._adopted_tpm,
                    # provider truth (observed from headers; not restored — it is
                    # re-observed live each epoch so a stale value never binds)
                    "provider_rpd_limit": self._provider_rpd_limit,
                    "provider_rpd_remaining": self._provider_rpd_remaining}

    def capacity_snapshot(self, *, now: float | None = None) -> dict:
        """Read-only capacity view for the SELECTION layer (GROQ-ROUTING-POLICY-V1 /
        groq_router.choose). The limiter remains the ENFORCEMENT authority — this only
        REPORTS remaining headroom so the router can prefer the least-loaded account.
        No second scheduler. Uses the monotonic clock (matching `_not_before`)."""
        now = _now() if now is None else now
        with self._lock:
            today = time.strftime("%Y-%m-%d", time.gmtime())
            day_count = self._day_count if self._day == today else 0
            remaining_rpd = (self.spec.rpd - day_count) if self.spec.rpd else 1_000_000_000
            rpm_cap = self._adopted_rpm or (self.spec.rpm or 0)
            tpm_cap = self._adopted_tpm or (self.spec.tpm or 0)
            rpm_tokens = self._rpm.tokens if self._rpm else 0.0
            tpm_tokens = self._tpm.tokens if self._tpm else 0.0
            not_before = self._not_before
            in_flight = self._sem.held
        return {
            "remaining_rpd": max(0, remaining_rpd),
            "rolling_rpm": max(0, int(round(rpm_cap - rpm_tokens))) if rpm_cap else 0,
            "tpm_used": max(0, int(round(tpm_cap - tpm_tokens))) if tpm_cap else 0,
            "in_flight": in_flight,
            "locked_until": not_before,
            "breaker_open": self._breaker.is_open,
            "day_count": day_count,
            "rpd_budget": self.spec.rpd,
            # provider-declared daily-request truth (None until first observed)
            "provider_rpd_limit": self._provider_rpd_limit,
            "provider_rpd_remaining": self._provider_rpd_remaining,
        }

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
            today = time.strftime("%Y-%m-%d", time.gmtime())
            if state.get("day") == today:
                self._day, self._day_count = today, int(
                    state.get("day_count", 0) or 0)
                # RPD-DURABILITY-V1 (D-4): the next dispatch continues from durable
                # truth. A row from a PREVIOUS day is deliberately not restored — the
                # daily budget resets, and carrying it over would refuse live capacity.
                lda = state.get("last_dispatch_at")
                self._last_dispatch_at = str(lda) if lda else None
            for attr, bucket in (("adopted_rpm", self._rpm),
                                 ("adopted_tpm", self._tpm)):
                val = state.get(attr)
                if val and bucket is not None:
                    bucket.adopt_capacity(float(val))
                    setattr(self, "_" + attr, float(val))
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
        """Backward-compatible boolean admission. Returns True iff admitted;
        a False return never leaves anything held. Callers that need the
        REASON for a refusal use `admit()` (GROQ-MAP-CONTROL-PLANE-REPAIR-V1)."""
        return self.admit(est_tokens=est_tokens, block=block).admitted

    def admit(self, est_tokens: float = 0.0, block: bool = True) -> LimiterDecision:
        """Take the concurrency slot + rate tokens, returning a reasoned
        LimiterDecision. `admitted=False` ALWAYS means zero HTTP dispatch and
        zero provider consumption; every refusal releases whatever it briefly
        held. The gate order (retry-after → family → breaker → concurrency →
        rpm/tpm → provider-rpd → local-rpd) is unchanged; only the outcome is
        now named."""
        if not self._honor_retry_after(block):
            with self._lock:
                ra = max(0.0, self._not_before - _now())
            return LimiterDecision(False, REFUSE_RETRY_AFTER, retry_after=ra)
        if self.spec.family and not FAMILY_GATE.allowed(
                self.spec.family, _registry_store()):
            return LimiterDecision(False, REFUSE_FAMILY_GATE)  # correlated storm
        if not self._breaker.allow():
            # BREAKER-WAIT (measured 2026-08-30): failing fast here turned
            # one OOM storm into a dead ticket — every stage retry hit the
            # still-open breaker within seconds and burned its attempt.
            # A BLOCKING caller waits for the cooldown and takes the
            # half-open probe itself; only a non-blocking caller (or a
            # breaker that stays open past BREAKER_WAIT_MAX_S) is refused.
            if not block or not self._wait_for_breaker():
                return LimiterDecision(False, REFUSE_BREAKER)
        if block:
            self._sem.acquire()
        elif not self._sem.try_acquire():
            self._breaker.release_probe()
            return LimiterDecision(False, REFUSE_CONCURRENCY)
        if self.spec.kind == "rate":
            reason: str | None = None
            if self._rpm is not None and not self._rpm.acquire(1.0, block):
                reason = REFUSE_RPM
            elif (self._tpm is not None and est_tokens > 0
                    and not self._tpm.acquire(est_tokens, block)):
                if self._rpm is not None:
                    self._rpm.refund(1.0)         # no call will be made
                reason = REFUSE_TPM
            # PROVIDER-declared daily exhaustion (from headers) refuses BEFORE
            # the local cap is charged — a provider-spent day must not consume a
            # local admission slot, and must never dispatch.
            if reason is None:
                with self._lock:
                    prov_spent = self._provider_rpd_exhausted_locked()
                if prov_spent:
                    reason = REFUSE_PROVIDER_RPD
                    self._refund_rate(est_tokens)
            if reason is None and self.spec.rpd:
                with self._lock:
                    today = time.strftime("%Y-%m-%d", time.gmtime())
                    if today != self._day:
                        self._day, self._day_count = today, 0
                    if self._day_count >= self.spec.rpd:
                        reason = REFUSE_RPD      # local daily safety cap spent
                    else:
                        self._day_count += 1
                        # RPD-DURABILITY-V1 (D-4): admission is the dispatch moment.
                        self._last_dispatch_at = _utc_iso()
                        self._rpd_dirty = True
                if reason == REFUSE_RPD:
                    self._refund_rate(est_tokens)
            if reason is not None:
                self._sem.release()
                self._breaker.release_probe()
                return LimiterDecision(False, reason)
        # RPD-DURABILITY-V1 (D-4): persist the day counter OUTSIDE the lock, on the
        # admitted path only (a refusal consumes no provider request, so it moves no
        # counter). Coalesced — see _persist_rpd_if_due.
        self._persist_rpd_if_due()
        return LimiterDecision(True)

    #: RPD-DURABILITY-V1 (D-4) coalescing window. A write per dispatch would put a
    #: Postgres round trip in the admission path of every extraction call; a window
    #: keeps the store's "writes are rare" contract while bounding what an abrupt
    #: kill can lose to at most this many seconds of dispatches on ONE lane. The
    #: durable row is therefore a LOWER BOUND on today's dispatches, never an
    #: over-count — which is the safe direction for a budget.
    RPD_PERSIST_MIN_INTERVAL_S: float = 1.0

    def _persist_rpd_if_due(self, *, force: bool = False) -> None:
        cb = self._on_change
        if cb is None:
            return
        with self._lock:
            if not self._rpd_dirty:
                return
            now = _now()
            if not force and (now - self._last_rpd_persist_mono) < self.RPD_PERSIST_MIN_INTERVAL_S:
                return
            self._last_rpd_persist_mono = now
            self._rpd_dirty = False
        try:
            cb(self.state())          # outside the lock: does I/O
        except Exception:             # noqa: BLE001 — accounting must never block a call
            log.debug("rpd persist failed for %s; continuing in-memory", self.name)

    def flush_rpd(self) -> None:
        """Force the coalesced counter out (shutdown / end of a bounded run)."""
        self._persist_rpd_if_due(force=True)

    def _refund_rate(self, est_tokens: float) -> None:
        """Hand back the rpm/tpm tokens taken for a call that will not be made."""
        if self._rpm is not None:
            self._rpm.refund(1.0)
        if self._tpm is not None and est_tokens > 0:
            self._tpm.refund(est_tokens)

    def _observe_provider_rpd_locked(self, limit, remaining, reset_secs) -> None:
        """Reconcile the provider's declared daily-request budget conservatively.
        Within one reset epoch the provider's `remaining` must not rise (we take
        the min); a proven epoch boundary — the reset deadline elapsed, or the
        declared limit changed — adopts the fresh value. Caller holds the lock."""
        now = _now()
        epoch_expired = (self._provider_rpd_reset_at is not None
                         and now >= self._provider_rpd_reset_at)
        new_epoch = (self._provider_rpd_remaining is None or epoch_expired
                     or (limit is not None and limit != self._provider_rpd_limit))
        if limit is not None:
            self._provider_rpd_limit = limit
        if remaining is not None:
            self._provider_rpd_remaining = (
                remaining if new_epoch
                else min(self._provider_rpd_remaining, remaining))
        if reset_secs is not None:
            self._provider_rpd_reset_at = now + reset_secs

    def _provider_rpd_exhausted_locked(self) -> bool:
        """True only when the provider itself reports zero daily requests left
        AND the current reset epoch has NOT elapsed (a stale zero past its reset
        is treated as a probable reset, not a block). Caller holds the lock."""
        if self._provider_rpd_remaining is None:
            return False
        if (self._provider_rpd_reset_at is not None
                and _now() >= self._provider_rpd_reset_at):
            return False
        return self._provider_rpd_remaining <= 0

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
        if self.spec.family:
            FAMILY_GATE.note_failure(self.spec.family, _registry_store())
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
        # GROQ-MAP-CONTROL-PLANE-REPAIR-V1: `*-requests` headers are a DAILY
        # (RPD) budget on Groq — they MUST NOT touch the per-MINUTE `_rpm`
        # bucket (the old code fed x-ratelimit-*-requests into _rpm, a
        # per-day/per-minute category error). Only `*-tokens` are per-minute
        # (TPM) and correctly drive `_tpm`; `*-requests` drive the distinct
        # provider-RPD observation below.
        #
        # FLEET-V3 CEILING ADOPTION (owner 2026-09-01), now TOKENS-only: when
        # the provider declares a token limit above our seed, adopt theirs,
        # clamped to seed x CEILING_ADOPT_MAX_MULTIPLE. Grow-only.
        if (self._tpm is not None and self.spec.tpm is not None
                and "x-ratelimit-limit-tokens" in headers):
            declared = _to_float(headers["x-ratelimit-limit-tokens"])
            if declared is not None:
                cap = min(declared, self.spec.tpm * CEILING_ADOPT_MAX_MULTIPLE)
                if self._tpm.adopt_capacity(cap):
                    self._adopted_tpm = cap
                    log.info(
                        "%s adopted provider-declared x-ratelimit-limit-tokens:"
                        " %s (seed %s)", self.name, int(cap), self.spec.tpm)
        for key, bucket in (("x-ratelimit-remaining-tokens", self._tpm),
                            ("anthropic-ratelimit-tokens-remaining", self._tpm)):
            if bucket is not None and key in headers:
                val = _to_float(headers[key])
                if val is not None:
                    bucket.sync_remaining(val)
        # PROVIDER-RPD OBSERVATION (distinct from the local `_day_count` safety
        # cap): record the provider's own declared daily-request budget so RPD
        # truth is observable on EVERY response (success and 429), and gate
        # admission when the provider says the day is spent. Never inflates or
        # shrinks the per-minute bucket.
        lim_v = _to_float(headers.get("x-ratelimit-limit-requests"))
        rem_v = _to_float(headers.get("x-ratelimit-remaining-requests"))
        reset_v = parse_reset_seconds(headers.get("x-ratelimit-reset-requests"))
        if lim_v is not None or rem_v is not None or reset_v is not None:
            with self._lock:
                self._observe_provider_rpd_locked(lim_v, rem_v, reset_v)

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

    def ensure_store(self) -> None:
        """RPD-DURABILITY-V1 (D-4): make durability a property of the REGISTRY, not of
        one caller.

        Before this, the only attach site was `workers.llm_provider.
        _ensure_controller_store()`. The extract worker goes through that module, so its
        Gemini/NVIDIA lanes persisted. The pMAP stage worker uses the SHARED
        `LLMExtractionClient` directly and never imports `workers.llm_provider`, so in
        that process no store was ever attached, `_on_change` stayed None, and every
        pMAP dispatch was accounted only in memory — measured 2026-09-10: zero
        `llm_controller_state` rows for `map_groq2..6` despite thousands of dispatches.

        Attaching here means every consumer of the one registry (extract, pMAP,
        doc_profile, chat compiler) gets the same durable accounting with no per-caller
        wiring to forget. Idempotent, and fail-soft exactly like the store itself: no
        DSN or no table means one warning and in-memory operation, never a blocked call.
        """
        if self._store is not None:
            return
        dsn = os.environ.get("POLYMATH_PG_DSN", "").strip()
        if not dsn:
            return
        try:
            from polymath_shared.llm_extraction.state_store import PostgresControllerStore
            self.attach_store(PostgresControllerStore(dsn))
        except Exception:  # noqa: BLE001 — accounting must never block extraction
            log.debug("controller store unavailable; continuing in-memory")

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
        self.ensure_store()          # RPD-DURABILITY-V1 (D-4): durable by default
        k = (provider, key or "default")
        with self._lock:
            if k not in self._lanes:
                lim = AdaptiveLimiter(f"{provider}[{k[1]}]", spec)
                self._bind(lim, lim.name)
                self._lanes[k] = lim
            return self._lanes[k]

    def get_lane(self, provider: str, key: str) -> AdaptiveLimiter | None:
        """Read-only lookup of an EXISTING lane (None if never created). For the
        SELECTION layer (groq_router) to read live capacity without creating a lane."""
        with self._lock:
            return self._lanes.get((provider, key or "default"))

    def budget(self, key: str, *, seed: int, floor: int, ceiling: int,
               step: int) -> AdaptiveBudget:
        self.ensure_store()          # RPD-DURABILITY-V1 (D-4)
        with self._lock:
            if key not in self._budgets:
                budget = AdaptiveBudget(key, seed=seed, floor=floor,
                                        ceiling=ceiling, step=step)
                self._bind(budget, key)
                self._budgets[key] = budget
            return self._budgets[key]


REGISTRY = LimiterRegistry()
