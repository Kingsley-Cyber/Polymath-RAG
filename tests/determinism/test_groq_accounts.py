"""DOCUMENT-SEMANTIC-INDEX-V1 slice S7 — Groq per-account shared-budget accounting.

Pins that an account's TWO model lanes (compound + compound-mini) aggregate into ONE
shared budget for the router (GROQ-ROUTING-POLICY-V1 §2 correction), that the live
`AdaptiveLimiter.capacity_snapshot()` reports the fields the aggregation needs, and
that the assembled AccountState list drives `groq_router.choose` to the least-loaded
account. Pure — no network, no model.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import groq_accounts as GA  # noqa: E402
from polymath_shared.document_profile import groq_router as GR  # noqa: E402
from polymath_shared.llm_extraction.limiter import AdaptiveLimiter, ProviderLimit  # noqa: E402


def _snap(day_count=0, rolling_rpm=0, tpm_used=0, in_flight=0, locked_until=0.0, breaker_open=False,
          remaining_rpd=1000):
    return {"day_count": day_count, "rolling_rpm": rolling_rpm, "tpm_used": tpm_used,
            "in_flight": in_flight, "locked_until": locked_until, "breaker_open": breaker_open,
            "remaining_rpd": remaining_rpd}


def test_two_model_lanes_share_one_account_budget():
    # account K1 has a compound lane (100 used) + a mini lane (50 used); shared quota 250.
    lane_snapshots = {
        "k1_compound": _snap(day_count=100, rolling_rpm=2, tpm_used=3000, in_flight=1),
        "k1_mini": _snap(day_count=50, rolling_rpm=1, tpm_used=1000, in_flight=0, locked_until=5.0),
    }
    account_of = {"k1_compound": "K1", "k1_mini": "K1"}
    states = GA.account_states(lane_snapshots, account_of, {"K1": 250})
    assert len(states) == 1
    s = states[0]
    assert s.account == "K1"
    assert s.remaining_rpd == 100          # 250 - (100 + 50) SHARED, not per-lane
    assert s.rolling_rpm == 3 and s.tpm_used == 4000 and s.in_flight == 1
    assert s.locked_until == 5.0           # max across lanes
    assert s.breaker_open is False


def test_breaker_and_lock_aggregate_and_accounts_sort():
    lane_snapshots = {
        "k2_compound": _snap(day_count=10, breaker_open=True),
        "k1_compound": _snap(day_count=5),
    }
    account_of = {"k2_compound": "K2", "k1_compound": "K1"}
    states = GA.account_states(lane_snapshots, account_of, {"K1": 250, "K2": 250})
    assert [s.account for s in states] == ["K1", "K2"]     # deterministic sort
    assert states[1].breaker_open is True                  # any lane broken -> account broken


def test_unmapped_lane_skipped():
    states = GA.account_states({"x": _snap(day_count=1)}, {}, {})
    assert states == []


def test_live_capacity_snapshot_reports_the_fields():
    lim = AdaptiveLimiter("k1_compound", ProviderLimit(kind="rate", rpm=30, tpm=70000, rpd=250,
                                                       max=6, min=1, conc_cap=6))
    snap = lim.capacity_snapshot()
    assert set(snap) >= {"remaining_rpd", "rolling_rpm", "tpm_used", "in_flight", "locked_until",
                         "breaker_open", "day_count", "rpd_budget"}
    assert snap["remaining_rpd"] == 250 and snap["day_count"] == 0 and snap["breaker_open"] is False
    assert snap["rolling_rpm"] == 0 and snap["in_flight"] == 0    # fresh lane


def test_snapshot_from_registry_and_router_picks_least_loaded():
    reg = {"k1_compound": AdaptiveLimiter("k1_compound", ProviderLimit(kind="rate", rpm=30, tpm=70000, rpd=250, max=6, min=1)),
           "k2_compound": AdaptiveLimiter("k2_compound", ProviderLimit(kind="rate", rpm=30, tpm=70000, rpd=250, max=6, min=1))}
    # k1 has spent 200 of its day; k2 is fresh -> the router must pick k2.
    reg["k1_compound"]._day_count = 200
    states = GA.snapshot_from_registry(reg, ["k1_compound", "k2_compound"],
                                       {"k1_compound": "K1", "k2_compound": "K2"}, {"K1": 250, "K2": 250})
    decision = GR.choose("GLOBAL_DOCUMENT_PROFILE", states, now=0.0, est_total_tokens=4000.0)
    assert decision.routed and decision.account == "K2" and decision.model == "groq/compound"
