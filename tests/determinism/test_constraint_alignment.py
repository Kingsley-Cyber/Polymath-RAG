"""CONSTRAINT-AWARE-RETRIEVAL-V1 (CA3) — post-rerank portfolio partition.

Proves the deterministic reorder: HARD leads with constraint-satisfying evidence (semantic order
preserved within each portfolio), SOFT is a bounded promotion (never a demotion, never below rank 2),
EXPLORATORY is anchor-only identity, and no-constraint / unresolved / source-absent is identity.
No score is added or tuned; items are only reordered. Pure shared/ — executed path is this worktree.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.query_constraints import (  # noqa: E402
    Constraint, align_by_constraint, align_evidence_for_constraints)


def _ev(*docs):
    """Rerank-ordered evidence: each arg 'doc#chunk' -> {doc_id, chunk_id} (list order = rerank order)."""
    out = []
    for i, spec in enumerate(docs):
        doc = spec.split("#")[0]
        out.append({"doc_id": doc, "chunk_id": f"{spec}:{i}"})
    return out


def _docs(ev):
    seen, order = set(), []
    for e in ev:
        if e["doc_id"] not in seen:
            seen.add(e["doc_id"]); order.append(e["doc_id"])
    return order


# --- HARD: constraint-satisfying evidence leads, order preserved within portfolios -----------
def test_hard_source_leads():
    ev = _ev("rabiger", "murch", "edhooks")            # reranker put rabiger #1, murch #2
    out = align_by_constraint(ev, {"murch"}, "HARD")
    assert _docs(out) == ["murch", "rabiger", "edhooks"]   # source doc now #1


def test_hard_preserves_order_within_each_portfolio():
    ev = _ev("rabiger", "murch#a", "edhooks", "murch#b")
    out = align_by_constraint(ev, {"murch"}, "HARD")
    assert [e["chunk_id"] for e in out] == [
        "murch#a:1", "murch#b:3", "rabiger:0", "edhooks:2"]   # murch chunks lead in their order; others after in theirs


def test_hard_no_source_evidence_is_identity():
    ev = _ev("rabiger", "edhooks")
    assert align_by_constraint(ev, {"murch"}, "HARD") == ev


# --- SOFT: bounded promotion (never a demotion, never below rank 2) --------------------------
def test_soft_lifts_source_to_rank_two():
    ev = _ev("rabiger", "edhooks", "murch")            # source buried at rank 3
    out = align_by_constraint(ev, {"murch"}, "SOFT")
    assert _docs(out) == ["rabiger", "murch", "edhooks"]   # top result kept #1; source lifted to #2


def test_soft_does_not_demote_already_top_source():
    ev = _ev("murch", "rabiger", "edhooks")            # source already #1
    assert align_by_constraint(ev, {"murch"}, "SOFT") == ev   # unchanged (no demotion)


def test_soft_source_at_rank_two_unchanged():
    ev = _ev("rabiger", "murch", "edhooks")
    assert align_by_constraint(ev, {"murch"}, "SOFT") == ev


# --- EXPLORATORY: anchor only (identity) -----------------------------------------------------
def test_exploratory_is_identity():
    ev = _ev("rabiger", "edhooks", "murch")
    assert align_by_constraint(ev, {"murch"}, "EXPLORATORY") == ev


# --- degenerate inputs are identity ----------------------------------------------------------
def test_no_targets_identity():
    ev = _ev("rabiger", "murch")
    assert align_by_constraint(ev, set(), "HARD") == ev


def test_unknown_strength_identity():
    ev = _ev("rabiger", "murch")
    assert align_by_constraint(ev, {"murch"}, "BOGUS") == ev


def test_never_adds_or_drops_items():
    ev = _ev("a", "b", "murch", "c", "murch#2")
    for strength in ("HARD", "SOFT", "EXPLORATORY"):
        out = align_by_constraint(ev, {"murch"}, strength)
        assert sorted(e["chunk_id"] for e in out) == sorted(e["chunk_id"] for e in ev)


# --- align_evidence_for_constraints: governing tier + resolved-only ---------------------------
def test_only_resolved_constraints_act():
    ev = _ev("rabiger", "murch")
    unresolved = Constraint(kind="SOURCE", value="Murch", strength="HARD")   # resolved_targets == []
    assert align_evidence_for_constraints(ev, [unresolved]) == ev            # identity


def test_hard_governs_over_soft():
    ev = _ev("rabiger", "edhooks", "murch")
    hard = Constraint(kind="SOURCE", value="Murch", strength="HARD", resolved_targets=["murch"])
    soft = Constraint(kind="SOURCE", value="Block", strength="SOFT", resolved_targets=["edhooks"])
    out = align_evidence_for_constraints(ev, [soft, hard])
    assert _docs(out)[0] == "murch"                     # HARD tier governs -> source leads


def test_resolved_hard_leads_end_to_end():
    ev = _ev("rabiger", "murch", "edhooks")
    c = Constraint(kind="SOURCE", value="Walter Murch", strength="HARD", resolved_targets=["murch"])
    assert _docs(align_evidence_for_constraints(ev, [c])) == ["murch", "rabiger", "edhooks"]
