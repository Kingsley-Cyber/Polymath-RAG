"""P11 profile-yield receipt — the killer metric (PROFILE-YIELD-RECEIPT-V1).

Proves: profile_expansion_evidence_yield counts a PROFILE subquery ONLY when a FINAL selected
evidence item names it (scout nominations are never yield); distinguishes "expansion occurred"
(a PROFILE subquery ran) from "expansion produced evidence" (it surfaced surviving source
evidence); a non-selected item does not count; the per-origin breakdown is correct; and
librarian_receipt composes q0 → scout → plan(+P6 provenance) → evidence → resolution → yield.
Pure — no I/O, no LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from pytest import approx  # noqa: E402
from polymath_shared.chat_plan import ChatPlan, CompiledQuery  # noqa: E402
from polymath_shared.profile_yield import (  # noqa: E402
    evidence_provenance, evidence_yield_by_origin, librarian_receipt,
    profile_expansion_evidence_yield, selected_evidence_query_ids,
)


def _q(qid, origin="USER", type="MECHANISM"):
    return CompiledQuery(id=qid, type=("PRIMARY" if qid == "q0" else type), query=f"text {qid}",
                         origin=origin)


def _plan(queries, q0="what does the corpus say about X"):
    return ChatPlan(
        contract="chat-intent-plan-v1", original_request=q0, resolved_request="resolved " + q0,
        task_type="GROUNDED_QA", evidence_policy="corpus_grounded", retrieval_required=True,
        retrieval_goal=None, queries=queries, semantic_queries=[], exact_terms=[], entities=[],
        must_answer=[], user_constraints=[], response_type="answer", antecedent=None,
        graph_useful=False)


def _ev(cid, qids, *, selected=True, doc="d1"):
    return {"candidate_id": cid, "doc_id": doc, "source_query_ids": qids, "selected": selected,
            "rerank_score": 0.5}


# --- killer metric -----------------------------------------------------------------------

def test_profile_yield_counts_only_profile_subqueries_with_final_evidence():
    subs = [_q("q0", "USER"), _q("q1", "PROFILE"), _q("q2", "PROFILE"), _q("q3", "GRAPH")]
    # q1 surfaced selected evidence; q2 did not; q0/q3 irrelevant to the profile metric
    evidence = [_ev("c1", ["q0", "q1"]), _ev("c2", ["q3"])]
    y = profile_expansion_evidence_yield(subs, evidence)
    assert y["profile_subqueries"] == 2 and y["profile_subqueries_with_evidence"] == 1
    assert y["profile_expansion_evidence_yield"] == approx(0.5)
    assert y["expansion_occurred"] is True and y["expansion_yielded_evidence"] is True
    assert y["yielded_query_ids"] == ["q1"]


def test_expansion_occurred_but_no_evidence():
    subs = [_q("q0", "USER"), _q("q1", "PROFILE")]
    evidence = [_ev("c1", ["q0"])]                       # only q0 (direct) produced evidence
    y = profile_expansion_evidence_yield(subs, evidence)
    assert y["expansion_occurred"] is True and y["expansion_yielded_evidence"] is False
    assert y["profile_expansion_evidence_yield"] == approx(0.0)


def test_no_profile_expansion_at_all():
    subs = [_q("q0", "USER"), _q("q1", "USER")]
    y = profile_expansion_evidence_yield(subs, [_ev("c1", ["q1"])])
    assert y["expansion_occurred"] is False and y["profile_expansion_evidence_yield"] == approx(0.0)


def test_unselected_evidence_does_not_count():
    subs = [_q("q0", "USER"), _q("q1", "PROFILE")]
    evidence = [_ev("c1", ["q1"], selected=False)]       # retrieved but reranked away → not final
    y = profile_expansion_evidence_yield(subs, evidence)
    assert y["profile_subqueries_with_evidence"] == 0 and y["expansion_yielded_evidence"] is False


def test_scout_nomination_is_not_evidence():
    # a scouted PROFILE subquery with an inspired_by link but NO final child evidence yields 0.
    q1 = CompiledQuery(id="q1", type="ENTITY", query="scouted aspect",
                       inspired_by_profile=("docZ",), origin="PROFILE")
    subs = [_q("q0", "USER"), q1]
    y = profile_expansion_evidence_yield(subs, [_ev("c1", ["q0"])])
    assert y["expansion_yielded_evidence"] is False       # the nomination itself never counts


# --- helpers -----------------------------------------------------------------------------

def test_selected_evidence_query_ids_union():
    ids = selected_evidence_query_ids([_ev("c1", ["q0", "q1"]), _ev("c2", ["q1", "q2"], selected=False),
                                       _ev("c3", ["q3"])])
    assert ids == {"q0", "q1", "q3"}                     # c2 excluded (not selected)


def test_by_origin_breakdown():
    subs = [_q("q0", "USER"), _q("q1", "PROFILE"), _q("q2", "EVIDENCE_GAP")]
    evidence = [_ev("c1", ["q0"]), _ev("c2", ["q2"])]
    by = evidence_yield_by_origin(subs, evidence)
    assert by["USER"] == {"subqueries": 1, "with_evidence": 1}
    assert by["PROFILE"] == {"subqueries": 1, "with_evidence": 0}
    assert by["EVIDENCE_GAP"] == {"subqueries": 1, "with_evidence": 1}


def test_evidence_provenance_normalizes_single_id():
    rows = evidence_provenance([{"candidate_id": "c1", "doc_id": "d1", "source_query_id": "q1"}])
    assert rows[0]["source_query_ids"] == ["q1"] and rows[0]["selected"] is True


# --- full receipt ------------------------------------------------------------------------

def test_librarian_receipt_composes_all_stages():
    subs = [_q("q0", "USER"), _q("q1", "PROFILE")]
    plan = _plan(subs)
    evidence = [_ev("c1", ["q0"]), _ev("c2", ["q1"])]
    rec = librarian_receipt(
        plan, evidence, scout={"nominations": 3}, mode="HYBRID", lanes=["dense", "lexical"],
        resolution={"contract": "resolution-state-v1", "hop_2_fired": False, "reason": "stop:no_material_gap"})
    assert rec["contract"] == "librarian-receipt-v1"
    assert rec["q0"] == "what does the corpus say about X" and rec["mode"] == "HYBRID"
    assert rec["lanes"] == ["dense", "lexical"] and rec["scout"] == {"nominations": 3}
    assert rec["plan"]["task_type"] == "GROUNDED_QA"                 # P6 provenance rides in plan
    assert rec["resolution"]["hop_2_fired"] is False
    assert len(rec["evidence"]) == 2 and rec["evidence"][1]["source_query_ids"] == ["q1"]
    assert rec["yield"]["profile_subqueries_with_evidence"] == 1     # q1 produced evidence
    assert rec["yield_by_origin"]["PROFILE"]["with_evidence"] == 1
