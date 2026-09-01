"""EXTRACTION-FLEET-V3 limiter gate: header-declared ceiling adoption
(grow-only, clamped, persisted), the RPD daily budget (refuses when
spent, rolls at UTC midnight, restores same-day), and the provider-
family circuit (correlated failures damp the whole family; cooldown
closes it again; fail-open without a store)."""
from __future__ import annotations

import time

import polymath_shared.llm_extraction.limiter as lim
from polymath_shared.llm_extraction.limiter import (
    CEILING_ADOPT_MAX_MULTIPLE,
    FAMILY_COOLDOWN_S,
    FAMILY_FAILURE_THRESHOLD,
    AdaptiveLimiter,
    ProviderLimit,
    _FamilyGate,
)


def _lane(**over):
    spec = dict(kind="rate", init=2, min=1, max=6, rpm=30, tpm=10000,
                conc_cap=4, adaptive=True, use_headers=True)
    spec.update(over)
    return AdaptiveLimiter("t", ProviderLimit(**spec))


def test_ceiling_adoption_grows_and_clamps():
    lane = _lane(rpm=30)
    lane._sync_headers({"x-ratelimit-limit-requests": "60"})
    assert lane._rpm.capacity == 60.0            # provider said more
    lane._sync_headers({"x-ratelimit-limit-requests": "10"})
    assert lane._rpm.capacity == 60.0            # grow-only
    lane._sync_headers({"x-ratelimit-limit-requests": "100000"})
    assert lane._rpm.capacity == 30 * CEILING_ADOPT_MAX_MULTIPLE
    assert lane.state()["adopted_rpm"] == 30 * CEILING_ADOPT_MAX_MULTIPLE


def test_adopted_ceiling_survives_restore():
    lane = _lane()
    lane._sync_headers({"x-ratelimit-limit-requests": "90"})
    saved = lane.state()
    fresh = _lane()
    assert fresh.restore(saved)
    assert fresh._rpm.capacity == 90.0


def test_rpd_budget_refuses_when_spent_and_restores():
    lane = _lane(rpd=3)
    for _ in range(3):
        assert lane.acquire(block=False)
        lane.release()
    assert not lane.acquire(block=False)         # daily budget spent
    saved = lane.state()
    fresh = _lane(rpd=3)
    fresh.restore(saved)
    assert not fresh.acquire(block=False)        # same-day count carried


def test_rpd_rolls_over_at_midnight():
    lane = _lane(rpd=1)
    assert lane.acquire(block=False)
    lane.release()
    assert not lane.acquire(block=False)
    lane._day = "1999-01-01"                     # force rollover
    assert lane.acquire(block=False)
    lane.release()


def test_family_gate_opens_on_correlated_failures_and_cools():
    gate = _FamilyGate()
    assert gate.allowed("fam", None)
    for _ in range(FAMILY_FAILURE_THRESHOLD):
        gate.note_failure("fam", None)
    assert not gate.allowed("fam", None)         # circuit open
    assert gate.allowed("other", None)           # other families untouched
    gate._open_until["fam"] = 0.0                # cooldown elapsed
    assert gate.allowed("fam", None)


def test_family_gate_blocks_acquire_across_lanes():
    gate = _FamilyGate()
    lim.FAMILY_GATE = gate
    try:
        a = _lane(family="gem")
        b = _lane(family="gem")
        for _ in range(FAMILY_FAILURE_THRESHOLD):
            a.record_failure()                   # one lane's storm...
        assert not b.acquire(block=False)        # ...damps its sibling
    finally:
        lim.FAMILY_GATE = _FamilyGate()


def test_413_style_paths_untouched_without_family():
    lane = _lane(family=None)
    lane.record_failure()
    assert lane.acquire(block=False)             # no family = no gate
    lane.release()
