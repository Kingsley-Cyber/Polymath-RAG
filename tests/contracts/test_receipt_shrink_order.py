"""RECEIPT-SHRINK-ORDER: a receipt over 64 KB loses its diagnostic bulk first and its forensic core — the plan (facets), the legend,
the used evidence — last. Live 2026-09-27: a WILDCARD turn kept 32 KB of chunk ids and lost all three."""
from __future__ import annotations

import json

from polymath_shared.query_receipts import META_MAX_CHARS, _meta_json


def _big_meta() -> dict:
    ids = [f"chunk_{i:064x}" for i in range(400)]
    return {
        "mode": "WILDCARD",
        "chat_plan": {"facets": [{"id": "f1", "name": "one part", "query_ids": ["q0"]}, {"id": "f2", "name": "another", "query_ids": ["q1"]}],
                      "queries": [{"id": "q0", "query": "a"}, {"id": "q1", "query": "b"}]},
        "legend": [{"tag": f"S{i}", "chunk_id": ids[i], "breadcrumb": "Book > ch"} for i in range(12)],
        "used_evidence": ids[:14],
        "funnel": {"version": "retrieval-funnel-v1", "counts": {"union": 400}, "lane_counts": {"dense": 50},
                   "lanes": {lane: ids for lane in ("dualread", "hierarchical", "seealso_fanout", "global_dense_child", "global_sparse_child", "latent_rescue")},
                   "stages": {st: ids for st in ("union", "retrieved", "pre_rerank", "post_rerank", "selected", "cited")},
                   "arrivals": {i: ["dense", "sparse"] for i in ids[:200]}},
        "wildcard": {"mapped_pass": {"kept": 6, "built": 6}, "baseline_chunks": ids, "latent_candidates": [{"chunk_id": i, "hop1": 0.5} for i in ids],
                     "returned": ids, "candidate_parents": ids[:100]},
        "retrieval_trace": {"aspects": {f"q{i}": {"union": 20, "ids": ids[:60]} for i in range(12)}},
        "latent_selection": {"graded": [{"chunk_id": i, "score": 1.0} for i in ids]},
        "composition": {"doc_counts": {"doc_a": 8, "doc_b": 7}, "doc_share_top": 0.4},
        "synthesis": {"facets": [{"id": "f1", "confidence": "strong"}], "uncited": 2, "sentences": 20},
        "gap_check": {"claims": [{"text": "x", "found": 3}]},
    }


def test_the_forensic_core_survives_and_the_bulk_goes_first():
    meta = _big_meta()
    assert len(json.dumps(meta, default=str)) > META_MAX_CHARS
    out = json.loads(_meta_json(meta))
    assert len(json.dumps(out)) <= META_MAX_CHARS
    assert out["chat_plan"]["facets"] == meta["chat_plan"]["facets"]                  # the plan's facets, intact
    assert out["legend"] == meta["legend"] and out["used_evidence"] == meta["used_evidence"]
    assert out["composition"] == meta["composition"] and out["synthesis"] == meta["synthesis"] and out["gap_check"] == meta["gap_check"]
    assert out["wildcard"]["mapped_pass"] == {"kept": 6, "built": 6}                   # the small facts inside a shrunk block stay
    held = out["wildcard"]["baseline_chunks"][-1]
    assert held.get("truncated") and held.get("held") == 400 and len(out["wildcard"]["baseline_chunks"]) == 9
    assert len(json.dumps(out["funnel"])) <= 8_000 + 400 and out["funnel"]["counts"] == {"union": 400}


def test_a_small_receipt_is_untouched_byte_for_byte():
    meta = {"mode": "HYBRID", "chat_plan": {"facets": []}, "legend": [], "used_evidence": ["chunk_a"]}
    assert _meta_json(meta) == json.dumps(meta, default=str)


def test_when_even_the_core_is_too_big_the_row_still_holds_valid_json():
    meta = {"chat_plan": {"blob": "x" * (META_MAX_CHARS * 2)}, "legend": [], "used_evidence": []}
    out = json.loads(_meta_json(meta))                                          # valid JSON, the oversized core marked, never sliced
    assert out["chat_plan"] == {"truncated": True} and len(json.dumps(out)) <= META_MAX_CHARS


def test_a_dropped_funnel_keeps_its_counts():
    """The funnel goes first, but only its id lists: its counts survive whatever else must be cut (test_chat_funnel)."""
    meta = {"funnel": {"version": "retrieval-funnel-v1", "counts": {"cited": 1, "union": 9}, "lane_counts": {"dense": 3},
                       "stages": {"union": ["c" * 60] * 50}},
            "legend": [{"tag": f"S{i}", "locator": "chunk:" + "x" * 80} for i in range(3000)], "mode": "HYBRID"}
    out = json.loads(_meta_json(meta))
    assert out["mode"] == "HYBRID" and out["funnel"]["counts"] == {"cited": 1, "union": 9}
    assert out["funnel"]["lane_counts"] == {"dense": 3} and "stages" not in out["funnel"]
