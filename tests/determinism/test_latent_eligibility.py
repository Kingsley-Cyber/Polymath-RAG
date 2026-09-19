"""WLK2C C4 — latent evidence eligibility (pure state machine). Pins the safety-critical contract:
q0 primary (DIRECT wins regardless of bridge); BOTH links must hold (valid bridge AND local relevance);
and — the load-bearing test — a locally EXCELLENT chunk on an INVALID bridge is INELIGIBLE (strong
origin↔chunk never compensates for weak q0↔bridge). Thresholds default to the existing floor; DIVERGENT
uses the C2 role hint to pick a (config-driven) stricter local bar. C4 emits states only; C5 seats.
"""
from __future__ import annotations

import json

from polymath_shared.latent_eligibility import (
    COMPLEMENTARY_ELIGIBLE,
    DIRECT_ELIGIBLE,
    DIVERGENT_ELIGIBLE,
    INELIGIBLE,
    bridge_validity,
    evaluate_candidate,
    latent_eligibility,
)

# logits (floor 0.5 on the sigmoid ⟺ logit ≥ 0): + = clears, − = sub-floor
STRONG, WEAK = 2.0, -2.0


def test_direct_wins_regardless_of_bridge():
    e = latent_eligibility(q0_chunk_score=STRONG, bridge_id="b1", bridge_q0_score=WEAK, origin_chunk_score=WEAK)
    assert e.state == DIRECT_ELIGIBLE and e.direct is True   # q0 primary — an invalid bridge is irrelevant here


def test_complementary_when_both_links_hold():
    e = latent_eligibility(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=STRONG,
                           origin_chunk_score=STRONG, proposed_role="COMPLEMENTARY")
    assert e.state == COMPLEMENTARY_ELIGIBLE and e.bridge_valid and e.local_relevant


def test_ANTIHIJACK_excellent_local_cannot_rescue_invalid_bridge():
    # q0-subfloor chunk, INVALID bridge (q0↔bridge low), but the chunk is a PERFECT match to the bridge.
    # It must be INELIGIBLE — strong local relevance never compensates for an invalid bridge.
    e = latent_eligibility(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=-5.0, origin_chunk_score=6.0)
    assert e.state == INELIGIBLE and e.bridge_valid is False and e.reason == "bridge_invalid_semantic"


def test_local_subfloor_rejected_even_with_valid_bridge():
    e = latent_eligibility(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=STRONG, origin_chunk_score=WEAK)
    assert e.state == INELIGIBLE and e.bridge_valid is True and e.reason == "local_subfloor"


def test_divergent_eligible_on_role_hint():
    e = latent_eligibility(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=STRONG,
                           origin_chunk_score=STRONG, proposed_role="DIVERGENT")
    assert e.state == DIVERGENT_ELIGIBLE


def test_divergent_uses_stricter_local_floor():
    # origin score clears the normal floor (0.5) but NOT the stricter divergent floor (0.9).
    kw = dict(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=STRONG, origin_chunk_score=1.0)
    assert latent_eligibility(proposed_role="COMPLEMENTARY", **kw).state == COMPLEMENTARY_ELIGIBLE
    assert latent_eligibility(proposed_role="DIVERGENT", divergent_local_floor=0.9, **kw).state == INELIGIBLE


def test_pure_q0_subfloor_no_bridge():
    e = latent_eligibility(q0_chunk_score=WEAK)
    assert e.state == INELIGIBLE and e.reason == "q0_subfloor_no_bridge" and e.bridge_id is None


def test_bridge_valid_floor_configurable():
    # a marginally-valid bridge (logit 0.3, sig ~0.57) passes the default floor but fails a stricter bar.
    kw = dict(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=0.3, origin_chunk_score=STRONG)
    assert latent_eligibility(**kw).state == COMPLEMENTARY_ELIGIBLE
    assert latent_eligibility(bridge_valid_floor=0.7, **kw).state == INELIGIBLE


def test_floor_boundary_is_logit_zero():
    assert latent_eligibility(q0_chunk_score=0.0).state == DIRECT_ELIGIBLE       # sig 0.5 == floor → clears
    assert latent_eligibility(q0_chunk_score=-0.01).state == INELIGIBLE          # just below


def test_neither_link_compensates_matrix():
    # only (valid bridge AND local relevant) yields eligibility; every other pairing is INELIGIBLE.
    for bq0, oc, expect_eligible in [(STRONG, STRONG, True), (STRONG, WEAK, False),
                                     (WEAK, STRONG, False), (WEAK, WEAK, False)]:
        e = latent_eligibility(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=bq0, origin_chunk_score=oc)
        assert (e.state == COMPLEMENTARY_ELIGIBLE) is expect_eligible


def test_bridge_validity_helper_and_scores_recorded():
    assert bridge_validity(1.0) is True and bridge_validity(-1.0) is False
    e = latent_eligibility(q0_chunk_score=WEAK, bridge_id="b1", bridge_q0_score=STRONG, origin_chunk_score=STRONG)
    assert e.scores == {"q0_chunk": WEAK, "origin_chunk": STRONG, "bridge_q0": STRONG}
    json.dumps(e.to_dict())     # JSON-native for the receipt / C6 calibration


# ---- C4 many-to-one: evaluate ALL lineage paths, never collapse ----

def test_evaluate_candidate_keeps_all_paths_and_picks_best():
    ce = evaluate_candidate(chunk_id="X", q0_chunk_score=WEAK, bridge_paths=[
        {"bridge_id": "A", "proposed_role": "COMPLEMENTARY", "bridge_q0_score": STRONG, "origin_chunk_score": STRONG},
        {"bridge_id": "B", "proposed_role": "COMPLEMENTARY", "bridge_q0_score": -5.0, "origin_chunk_score": 6.0},  # invalid bridge
        {"bridge_id": "C", "proposed_role": "DIVERGENT", "bridge_q0_score": STRONG, "origin_chunk_score": STRONG},
    ])
    assert len(ce.lineage_results) == 3                        # NONE collapsed
    states = {r.bridge_id: r.state for r in ce.lineage_results}
    assert states == {"A": COMPLEMENTARY_ELIGIBLE, "B": INELIGIBLE, "C": DIVERGENT_ELIGIBLE}
    assert ce.role == COMPLEMENTARY_ELIGIBLE and ce.best().bridge_id == "A"   # best admissible path wins


def test_evaluate_candidate_direct_wins_but_keeps_paths():
    ce = evaluate_candidate(chunk_id="X", q0_chunk_score=STRONG, bridge_paths=[
        {"bridge_id": "A", "bridge_q0_score": WEAK, "origin_chunk_score": WEAK}])
    assert ce.direct_eligible and ce.role == DIRECT_ELIGIBLE
    assert len(ce.lineage_results) == 1                        # path retained (q0 primary short-circuits scoring)


def test_evaluate_candidate_no_paths_subfloor_is_ineligible():
    ce = evaluate_candidate(chunk_id="X", q0_chunk_score=WEAK, bridge_paths=[])
    assert not ce.direct_eligible and ce.role == INELIGIBLE and ce.best().reason == "no_lineage_paths"
    json.dumps(ce.to_dict())


def test_evaluate_candidate_best_breaks_ties_by_local_relevance():
    ce = evaluate_candidate(chunk_id="X", q0_chunk_score=WEAK, bridge_paths=[
        {"bridge_id": "A", "bridge_q0_score": STRONG, "origin_chunk_score": 1.0},
        {"bridge_id": "D", "bridge_q0_score": STRONG, "origin_chunk_score": 4.0}])   # both COMPLEMENTARY
    assert ce.best().bridge_id == "D"                          # higher origin↔chunk wins the tie
