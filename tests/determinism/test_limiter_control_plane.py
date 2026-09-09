"""GROQ-MAP-CONTROL-PLANE-REPAIR-V1 regressions.

The limiter/client control plane must be an OBSERVABLE conservation chain:

* a refusal is REASONED and dispatches zero HTTP (never charges provider quota);
* a successful 2xx carries the provider's rate-limit headers to the limiter, so
  provider-RPD truth is observable on success (not only on 429);
* DAILY `*-requests` headers drive a distinct provider-RPD representation and
  NEVER the per-minute `_rpm` bucket (the Target-A category error);
* provider-declared daily exhaustion refuses admission conservatively without
  charging the local safety cap.
"""
from __future__ import annotations

import time

import polymath_shared.llm_extraction.limiter as lim
from polymath_shared.llm_extraction.limiter import (
    BREAKER_WINDOW,
    FAMILY_FAILURE_THRESHOLD,
    REFUSE_BREAKER,
    REFUSE_FAMILY_GATE,
    REFUSE_PROVIDER_RPD,
    REFUSE_RETRY_AFTER,
    REFUSE_RPD,
    AdaptiveLimiter,
    LimiterDecision,
    ProviderLimit,
    _FamilyGate,
    parse_reset_seconds,
)
from polymath_shared.llm_extraction.client import LLMExtractionClient


def _lane(**over):
    spec = dict(kind="rate", init=2, min=1, max=6, rpm=30, tpm=10000,
                conc_cap=4, adaptive=True, use_headers=True)
    spec.update(over)
    return AdaptiveLimiter("cp", ProviderLimit(**spec))


# --- Target A: daily request headers never touch the per-minute RPM bucket ---
def test_requests_header_does_not_touch_rpm_but_sets_provider_rpd():
    lane = _lane(rpm=30)
    before = lane._rpm.capacity
    lane._sync_headers({
        "x-ratelimit-limit-requests": "1000",       # DAILY budget
        "x-ratelimit-remaining-requests": "7",
        "x-ratelimit-reset-requests": "2m30s",
    })
    assert lane._rpm.capacity == before             # RPM bucket UNTOUCHED
    snap = lane.capacity_snapshot()
    assert snap["provider_rpd_limit"] == 1000.0     # observed as provider RPD
    assert snap["provider_rpd_remaining"] == 7.0


def test_token_headers_still_drive_tpm():
    lane = _lane(tpm=10000)
    lane._sync_headers({"x-ratelimit-remaining-tokens": "40"})
    assert lane._tpm.tokens <= 40.0                 # token remaining still honored


# --- provider-RPD gate: reasoned refusal, zero local charge, conservative ----
def test_provider_rpd_exhausted_refuses_with_reason_and_no_local_charge():
    lane = _lane(rpd=230)
    lane._sync_headers({"x-ratelimit-remaining-requests": "0",
                        "x-ratelimit-reset-requests": "300"})   # epoch open
    before_day = lane.state()["day_count"]
    d = lane.admit(block=False)
    assert isinstance(d, LimiterDecision)
    assert d.admitted is False and d.reason == REFUSE_PROVIDER_RPD
    assert lane.state()["day_count"] == before_day  # local safety cap NOT charged
    assert lane._sem.held == 0                       # nothing held


def test_provider_rpd_reset_epoch_allows_again():
    lane = _lane(rpd=230)
    lane._sync_headers({"x-ratelimit-remaining-requests": "0",
                        "x-ratelimit-reset-requests": "0"})     # already elapsed
    time.sleep(0.01)
    assert lane.admit(block=False).admitted is True             # stale zero, allow
    lane.release()


def test_provider_rpd_remaining_is_conservative_within_epoch():
    lane = _lane()
    lane._sync_headers({"x-ratelimit-limit-requests": "250",
                        "x-ratelimit-remaining-requests": "40",
                        "x-ratelimit-reset-requests": "600"})
    lane._sync_headers({"x-ratelimit-remaining-requests": "90"})  # provider "rose"
    assert lane.state()["provider_rpd_remaining"] == 40.0         # min kept


# --- reasoned refusals: each names its gate and leaks nothing (0 HTTP) --------
def test_local_rpd_refusal_reason():
    lane = _lane(rpd=1)
    assert lane.admit(block=False).admitted
    lane.release()
    d = lane.admit(block=False)
    assert d.admitted is False and d.reason == REFUSE_RPD
    assert lane._sem.held == 0


def test_retry_after_refusal_reason_nonblocking():
    lane = _lane()
    lane._not_before = time.monotonic() + 10.0
    d = lane.admit(block=False)
    assert d.admitted is False and d.reason == REFUSE_RETRY_AFTER
    assert d.retry_after and d.retry_after > 0


def test_breaker_refusal_reason():
    lane = _lane(adaptive=False)
    for _ in range(BREAKER_WINDOW):
        lane.record_failure()
    d = lane.admit(block=False)
    assert d.admitted is False and d.reason == REFUSE_BREAKER
    assert lane._sem.held == 0


def test_family_gate_refusal_reason_isolated_to_family():
    gate = _FamilyGate()
    lim.FAMILY_GATE = gate
    try:
        a = _lane(family="grp_a")
        b = _lane(family="grp_a")
        other = _lane(family="grp_b")
        for _ in range(FAMILY_FAILURE_THRESHOLD):
            a.record_failure()
        assert b.admit(block=False).reason == REFUSE_FAMILY_GATE   # sibling damped
        assert other.admit(block=False).admitted is True           # other family ok
        other.release()
    finally:
        lim.FAMILY_GATE = _FamilyGate()


def test_parse_reset_seconds_forms():
    assert parse_reset_seconds("60") == 60.0
    assert parse_reset_seconds("60.5") == 60.5
    assert abs(parse_reset_seconds("2m30s") - 150.0) < 1e-9
    assert abs(parse_reset_seconds("1h2m3s") - 3723.0) < 1e-9
    assert parse_reset_seconds(None) is None
    assert parse_reset_seconds("garbage") is None


# --- client complete_one: 2xx feeds provider headers; refusal dispatches 0 ----
def _client(key):
    return LLMExtractionClient("cloud", url="http://x",
                               model="groq/compound-mini", limiter_key=key,
                               api_key="k", max_attempts=1)


def test_complete_one_success_feeds_provider_headers_to_limiter(monkeypatch):
    c = _client("cp_success")
    lane = c._lane_limiter()

    def fake_chat(user, mt, system_prompt=None):
        return "MAP|P1|sig|h", 10, 5, {
            "x-ratelimit-limit-requests": "250",
            "x-ratelimit-remaining-requests": "123",
            "x-ratelimit-reset-requests": "300"}

    monkeypatch.setattr(c, "_chat", fake_chat)
    raw, err = c.complete_one("u", system_prompt="s", max_tokens=100)
    assert err is None and raw.startswith("MAP|")
    assert c._last_http_dispatched is True
    assert lane.state()["provider_rpd_remaining"] == 123.0   # observed on 2xx


def test_complete_one_refused_dispatches_nothing_and_names_reason(monkeypatch):
    c = _client("cp_refused")
    lane = c._lane_limiter()
    monkeypatch.setattr(
        lane, "admit",
        lambda est_tokens=0.0, block=True: LimiterDecision(False, REFUSE_FAMILY_GATE))
    called = {"chat": False}

    def boom(*a, **k):
        called["chat"] = True
        raise AssertionError("_chat must not run on a refusal")

    monkeypatch.setattr(c, "_chat", boom)
    raw, err = c.complete_one("u", system_prompt="s", max_tokens=100)
    assert raw == "" and err == "LIMITER_REFUSED"    # bare string (back-compat)
    assert c._last_refusal_reason == REFUSE_FAMILY_GATE
    assert c._last_http_dispatched is False
    assert called["chat"] is False                    # zero HTTP dispatched
