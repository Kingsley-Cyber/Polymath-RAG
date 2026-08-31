"""Phase D engine proofs: the latent lane deepens through ORIGINAL
children, reserved seats survive the cut, latent text never becomes a
candidate, and latent_enabled=False leaves the engine output identical
to a run with no latent machinery supplied at all (§0b)."""
from __future__ import annotations

from dataclasses import replace

from polymath_shared.hybrid import HYBRID_DEFAULT_PLAN, hybrid_retrieve
from polymath_shared.latent.rescue import (
    ARRIVAL_LATENT_RESCUE,
    latent_rescue_parents,
)

CORPUS = "corpus_t"


def _mk_search(latent_rows_by_kind, children_by_parent):
    def search(_collection, _qvec, filters):
        kind = filters.get("representation_kind")
        if kind in ("latent_abstraction", "latent_transfer"):
            return latent_rows_by_kind.get(kind, [])
        if kind == "routing_child" and filters.get("parent_id"):
            return children_by_parent.get(filters["parent_id"], [])
        if kind == "routing_document_summary":
            return [{"score": 0.9, "payload": {
                "summary_id": "sum_d1", "doc_id": "d1",
                "corpus_id": CORPUS, "text": "doc one summary",
                "source_name": "one.md"}}]
        if kind == "routing_section_summary":
            return [{"score": 0.8, "payload": {
                "summary_id": "sum_s1", "doc_id": "d1", "parent_id": "p_s1",
                "corpus_id": CORPUS, "text": "section one",
                "source_name": "one.md"}}]
        if kind == "routing_child" and filters.get("parent_id") is None:
            return []
        return []
    return search


def _child_row(cid, pid, doc="d1", score=0.5):
    return {"score": score, "payload": {
        "chunk_id": cid, "doc_id": doc, "parent_id": pid,
        "corpus_id": CORPUS, "text": f"text of {cid}",
        "source_name": "one.md"}}


LATENT_ROWS = {
    "latent_abstraction": [{"score": 0.95, "payload": {
        "parent_id": "p_latent", "doc_id": "d1",
        "source_name": "one.md"}}],
}
CHILDREN = {
    "p_latent": [_child_row("c_latent_1", "p_latent"),
                 _child_row("c_latent_2", "p_latent")],
    "p_s1": [_child_row("c_s1", "p_s1", score=0.7)],
}


def _run(plan, with_latent):
    search = _mk_search(LATENT_ROWS, CHILDREN)

    def latent_rescue(qvec, skip):
        return latent_rescue_parents(
            qvec, corpus_id=CORPUS, plan=plan,
            routing_search=search, skip_parent_ids=skip)

    return hybrid_retrieve(
        "test query",
        plan=replace(plan, corpus_ids=(CORPUS,)),
        embed_query=lambda q: [0.1] * 4,
        routing_search=search,
        lexical_search=lambda q, k: [],
        rerank_children=None,
        latent_rescue=latent_rescue if with_latent else None,
    )


def test_latent_lane_admits_original_children_only():
    plan = replace(HYBRID_DEFAULT_PLAN, latent_enabled=True,
                   rerank_enabled=False)
    result = _run(plan, with_latent=True)
    latent_items = [c for c in result.final_evidence
                    if c.get("arrival") == ARRIVAL_LATENT_RESCUE]
    assert latent_items, "latent children missing from evidence"
    assert {c["chunk_id"] for c in latent_items} <= {
        "c_latent_1", "c_latent_2"}
    # latent surfaces themselves never appear as candidates
    assert all(not str(c.get("chunk_id", "")).startswith("penr_")
               for c in result.final_evidence)
    trace = result.trace["latent"]
    assert trace["enabled"] and trace["parents"][0]["parent_id"] == "p_latent"
    # LATENT-DIAGNOSTICS-V1: survival attribution present and truthful
    assert trace["parents_nominated"] == 1
    assert trace["parents_survived"] == 1
    assert trace["children_admitted"] == len(latent_items)
    assert trace["kinds"] == {"abstraction": 1}


def test_disabled_flag_is_byte_identical_to_no_machinery():
    plan = replace(HYBRID_DEFAULT_PLAN, rerank_enabled=False)
    a = _run(plan, with_latent=False)
    b = _run(replace(plan, latent_enabled=False), with_latent=True)
    assert a.final_evidence == b.final_evidence
    assert a.selected_sections == b.selected_sections
    assert b.trace["latent"] == {"enabled": False}
