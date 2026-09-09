"""AdaptiveLimiter — AIMD, token buckets, breaker, per-key registry.

Owner directive 2026-08-29: providers differ in the KIND of limit —
concurrency for local, rate (RPM/TPM) for cloud — and the limiter must
adapt within [min, max] rather than trust static numbers.
"""
from __future__ import annotations

import sys
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.llm_extraction.limiter import (  # noqa: E402
    AdaptiveLimiter,
    LimiterRegistry,
    ProviderLimit,
)


def test_concurrency_aimd_increase() -> None:
    lim = AdaptiveLimiter("local", ProviderLimit(
        kind="concurrency", init=2, min=1, max=4))
    assert lim.effective == 2
    for _ in range(4):
        lim.record_success()
    assert lim.effective == 3            # additive increase (K=4)
    for _ in range(4):
        lim.record_success()
    assert lim.effective == 4
    for _ in range(16):
        lim.record_success()
    assert lim.effective == 4            # ceiling respected


def test_concurrency_aimd_decrease_on_throttle() -> None:
    lim = AdaptiveLimiter("local", ProviderLimit(
        kind="concurrency", init=4, min=1, max=4))
    lim.record_failure()
    assert lim.effective == 2            # x0.5
    lim.record_failure()
    assert lim.effective == 1            # floor respected


def test_rate_bucket_refuses_when_drained() -> None:
    lim = AdaptiveLimiter("cloud", ProviderLimit(
        kind="rate", rpm=3, tpm=None, conc_cap=8, min=2, max=8,
        adaptive=False))
    assert lim.acquire(est_tokens=0, block=False)
    lim.release()
    assert lim.acquire(est_tokens=0, block=False)
    lim.release()
    assert lim.acquire(est_tokens=0, block=False)
    lim.release()
    # bucket drained: non-blocking acquire refused, slot NOT leaked
    assert not lim.acquire(est_tokens=0, block=False)
    assert lim._sem._held == 0


def test_rate_tpm_gate_estimates_before_send() -> None:
    lim = AdaptiveLimiter("cloud", ProviderLimit(
        kind="rate", rpm=100, tpm=1000, conc_cap=8, min=2, max=8,
        adaptive=False))
    assert lim.acquire(est_tokens=900, block=True)
    lim.release()
    # remaining budget ~100 tokens: a 500-token call must be refused
    assert not lim.acquire(est_tokens=500, block=False)
    lim.release()


def test_rate_conc_cap_is_the_safety_ceiling() -> None:
    lim = AdaptiveLimiter("cloud", ProviderLimit(
        kind="rate", rpm=1000, tpm=None, conc_cap=2, min=2, max=8,
        adaptive=False))
    lim._sem.set_limit(2)
    # non-blocking acquires never wait and never leak: exactly conc_cap
    # succeed while held (no background threads — a blocked non-daemon
    # thread would keep the interpreter alive and hang the test run)
    got = [lim.acquire(est_tokens=0, block=False) for _ in range(6)]
    assert got == [True, True, False, False, False, False]
    assert lim._sem.held == 2
    for _ in range(2):
        lim.release()
    assert lim._sem.held == 0
    # a blocking acquire proceeds once a slot is free
    done = []

    def grab():
        done.append(lim.acquire(est_tokens=0, block=True))
        lim.release()

    t = threading.Thread(target=grab, daemon=True)
    t.start()
    t.join(timeout=2)
    assert done == [True]


def test_header_sync_throttles_before_429() -> None:
    lim = AdaptiveLimiter("cloud", ProviderLimit(
        kind="rate", rpm=100, tpm=1000, conc_cap=8, min=2, max=8,
        adaptive=False, use_headers=True))
    lim.record_success(headers={"x-ratelimit-remaining-tokens": "50"})
    assert not lim.acquire(est_tokens=200, block=False)   # budget honored
    lim.release()


def test_breaker_opens_and_half_opens() -> None:
    lim = AdaptiveLimiter("cloud", ProviderLimit(
        kind="rate", rpm=1000, conc_cap=8, min=2, max=8, adaptive=False))
    for _ in range(10):
        lim.record_failure()
    assert lim.breaker_open
    assert not lim.acquire(est_tokens=0, block=False)     # refused, no I/O
    lim._breaker.cooldown_s = 0.0                          # force half-open
    import time
    time.sleep(0.01)
    assert lim.acquire(est_tokens=0, block=True)
    lim.release()


def test_registry_keys_by_provider_and_key() -> None:
    reg = LimiterRegistry()
    a = reg.lane("llm_cloud", "keyA", ProviderLimit(kind="rate", rpm=10))
    b = reg.lane("llm_cloud", "keyB", ProviderLimit(kind="rate", rpm=10))
    a2 = reg.lane("llm_cloud", "keyA", ProviderLimit(kind="rate", rpm=10))
    assert a is not b and a is a2


def test_siliconflow_lanes_are_independent_concurrency() -> None:
    """SILICONFLOW-EXTRACTION-LANES-V1: the three siliconflow lanes load from
    limiter.yaml as INDEPENDENT pure-concurrency limiters (measured 2026-09-08:
    the provider exposes no rate headers and rate-limits nothing up to the
    heavy-latency edge, so a rate bucket would be a fiction). Guards against a
    limiter.yaml edit silently turning them into rate lanes, correlating them
    under a shared family, or moving the measured ceiling."""
    from polymath_shared.llm_extraction.client import _lane_limit
    for name in ("siliconflow1", "siliconflow2", "siliconflow3"):
        spec = _lane_limit("cloud", provider=name)
        assert spec.kind == "concurrency", f"{name} must be concurrency, not rate"
        assert spec.family is None, f"{name} must be independent (no family cooldown)"
        assert (spec.init, spec.min, spec.max) == (12, 2, 24), \
            f"{name} measured seed/ceiling drifted: {(spec.init, spec.min, spec.max)}"
        lim = AdaptiveLimiter(name, spec)
        assert lim._rpm is None and lim._tpm is None, \
            f"{name} concurrency lane must build NO rate/token buckets"
        st = lim.state()
        assert st["effective"] == 12 and st["ceiling"] == 24 and st["floor"] == 2
