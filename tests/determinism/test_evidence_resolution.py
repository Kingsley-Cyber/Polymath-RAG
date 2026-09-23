"""P10 evidence-driven resolution — bounded round contract (EVIDENCE-RESOLUTION-V1).

Proves: deterministic lexical gap detection (SUPPORTED/PARTIAL/UNSUPPORTED + explicit CONFLICTING);
importance is position-weighted; a resolution round fires ONLY for an important unresolved gap and
emits a single targeted CompiledQuery (role=resolution, origin=EVIDENCE_GAP, derived_from=claim, target=need); the
most important / most severe gap is chosen deterministically; the loop is BOUNDED (no round past
max_rounds → no runaway); q0 is immutable across rounds; advance_state folds evidence back and
retires a SUPPORTED claim; the receipt is observable. Pure — no I/O, no LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from pytest import approx  # noqa: E402
from polymath_shared.chat_plan import ORIGIN_TYPES, ROLE_TYPES  # noqa: E402
from polymath_shared.evidence_resolution import (  # noqa: E402
    EVIDENCE_STATES, MAX_RESOLUTION_ROUNDS, ClaimState, ResolutionDecision, RetrievalState,
    advance_state, assess_claims, plan_resolution_round, resolution_receipt,
)


# --- claim assessment (deterministic lexical gap detection) ------------------------------

def test_assess_claims_states_by_coverage():
    must = ["shutter angle motion blur", "color grading workflow", "sound design ambience"]
    evidence = [
        "the shutter angle controls motion blur in the exposure",   # fully covers claim_0
        "a basic grading step for color",                            # partial for claim_1
    ]
    claims = assess_claims(must, evidence)
    by_id = {c.claim_id: c for c in claims}
    assert by_id["claim_0"].evidence_state == "SUPPORTED"
    assert by_id["claim_1"].evidence_state in ("PARTIAL", "SUPPORTED")
    assert by_id["claim_2"].evidence_state == "UNSUPPORTED"          # nothing about sound/ambience
    # importance decreases with position; gap claims carry a next_information_need
    assert by_id["claim_0"].importance > by_id["claim_2"].importance
    assert by_id["claim_2"].next_information_need == "sound design ambience"
    assert by_id["claim_0"].next_information_need is None            # supported → no need


def test_assess_claims_conflict_flag():
    claims = assess_claims(["topic one", "topic two"], ["topic one covered here"],
                           conflict_ids=("claim_1",))
    assert {c.claim_id: c.evidence_state for c in claims}["claim_1"] == "CONFLICTING"


def test_claimstate_normalizes():
    c = ClaimState(claim_id="x", importance=9.0, evidence_state="BOGUS")
    assert c.importance == 1.0 and c.evidence_state == "UNSUPPORTED"
    assert ClaimState("y", -1, "PARTIAL").importance == 0.0


# --- resolution decision (bounded, gap-driven) -------------------------------------------

def _state(claims, *, round=1, q="original q0 question"):
    return RetrievalState(original_query=q, round=round, unresolved_needs=tuple(claims))


def test_no_gap_stops():
    st = _state([ClaimState("claim_0", 1.0, "SUPPORTED")])
    d = plan_resolution_round(st)
    assert d.should_resolve is False and d.reason == "stop:no_material_gap"


def test_low_importance_gap_stops():
    st = _state([ClaimState("claim_0", 0.2, "UNSUPPORTED", "need x")])
    d = plan_resolution_round(st, importance_floor=0.5)
    assert d.should_resolve is False and d.reason == "stop:no_material_gap"


def test_gap_fires_targeted_resolution_query():
    st = _state([ClaimState("claim_0", 0.9, "UNSUPPORTED", "sound design ambience")])
    d = plan_resolution_round(st)
    assert d.should_resolve is True and d.reason == "gap:claim_0:UNSUPPORTED"
    q = d.query
    assert q is not None and q.role == "resolution" and q.role in ROLE_TYPES
    assert q.origin == "EVIDENCE_GAP" and q.origin in ORIGIN_TYPES
    assert q.derived_from == "claim_0" and q.query == "sound design ambience"   # E7: the claim is the reference
    assert q.target == "sound design ambience"                                  # and the need is the target


def test_picks_most_important_then_most_severe():
    st = _state([
        ClaimState("claim_0", 0.7, "PARTIAL", "a"),
        ClaimState("claim_1", 0.9, "PARTIAL", "b"),      # higher importance → chosen
        ClaimState("claim_2", 0.9, "UNSUPPORTED", "c"),  # equal importance, more severe → chosen over claim_1
    ])
    d = plan_resolution_round(st)
    assert d.claim.claim_id == "claim_2"   # importance 0.9 and UNSUPPORTED (severity beats claim_1 PARTIAL)


def test_max_rounds_stops_runaway():
    st = _state([ClaimState("claim_0", 1.0, "UNSUPPORTED", "x")], round=MAX_RESOLUTION_ROUNDS)
    d = plan_resolution_round(st)
    assert d.should_resolve is False and d.reason.startswith("stop:max_rounds")


# --- advance + bounded loop --------------------------------------------------------------

def test_advance_retires_supported_claim_and_preserves_q0():
    st = _state([ClaimState("claim_0", 0.9, "UNSUPPORTED", "sound design")], q="Q0")
    d = plan_resolution_round(st)
    st2 = advance_state(st, d, new_evidence=["e1", "e2"], new_docs=["docA"], resolved_state="SUPPORTED")
    assert st2.original_query == "Q0"                         # q0 immutable
    assert st2.round == 2 and "claim_0" in st2.answered_claims
    assert not any(c.claim_id == "claim_0" for c in st2.unresolved_needs)
    assert st2.evidence_chunks == ("e1", "e2") and st2.discovered_docs == ("docA",)
    assert st2.retrieval_history[-1]["claim"] == "claim_0" and st2.retrieval_history[-1]["added_evidence"] == 2


def test_loop_is_bounded_to_one_resolution_round():
    # a still-unsupported claim after round 1 must NOT trigger an unbounded second resolution.
    st = _state([ClaimState("claim_0", 1.0, "UNSUPPORTED", "x")])
    fired = 0
    while True:
        d = plan_resolution_round(st)
        if not d.should_resolve:
            break
        fired += 1
        st = advance_state(st, d, new_evidence=["e"], resolved_state="PARTIAL")  # still a gap
        assert fired <= MAX_RESOLUTION_ROUNDS   # never runs away
    assert fired == MAX_RESOLUTION_ROUNDS - 1   # round 1 initial + exactly one resolution


# --- receipt -----------------------------------------------------------------------------

def test_resolution_receipt_shape():
    st = _state([ClaimState("claim_0", 0.9, "UNSUPPORTED", "need")])
    d = plan_resolution_round(st)
    rec = resolution_receipt(st, d)
    assert rec["contract"] == "resolution-state-v1" and rec["hop_2_fired"] is True
    assert rec["reason"] == "gap:claim_0:UNSUPPORTED" and rec["resolution_query"] == "need"
    assert rec["resolution_claim"] == "claim_0"
    assert rec["unresolved"] and rec["unresolved"][0]["evidence_state"] == "UNSUPPORTED"


def test_receipt_stop_when_supported():
    st = _state([ClaimState("claim_0", 0.9, "SUPPORTED")])
    rec = resolution_receipt(st, plan_resolution_round(st))
    assert rec["hop_2_fired"] is False and rec["unresolved"] == [] and rec["resolution_query"] is None


def test_evidence_states_vocabulary():
    assert EVIDENCE_STATES == ("UNSUPPORTED", "PARTIAL", "CONFLICTING", "SUPPORTED")
    assert MAX_RESOLUTION_ROUNDS >= 2 and approx(1.0) == 1.0
