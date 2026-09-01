"""DIVERGENT-RETRIEVAL-V1 exit gate: the frontier excludes the
obvious neighborhood, two-hop validation grounds every bridge, the
novelty damp punishes ordinary similarity, bounds hold hard, and
every stage fails open to an empty lane."""
from __future__ import annotations

from polymath_shared.divergent import (
    DIVERGENT_DEFAULT_PLAN,
    DivergentPlan,
    divergent_retrieve,
)


def _latent_rows(rows_by_kind):
    def search(kind, _qvec, top_k):
        return (rows_by_kind.get(kind) or [])[:top_k]
    return search


def _lat(parent, score, kind_text, doc="d_far", name="far.md"):
    return {"score": score, "payload": {
        "parent_id": parent, "doc_id": doc, "source_name": name,
        "text": kind_text}}


def _kid(cid, text):
    return {"score": 0.5, "payload": {"chunk_id": cid, "text": text,
                                      "source_name": "far.md"}}


BASELINE = {"doc_ids": {"d_near"}, "parent_ids": {"p_near"},
            "chunk_ids": {"c_near_1"}}


def _run(latent, children, rerank=None, baseline=BASELINE,
         plan=DIVERGENT_DEFAULT_PLAN):
    return divergent_retrieve(
        "how can I make an animated punch feel heavier",
        embed_query=lambda q: [0.1] * 4,
        latent_search=_latent_rows(latent),
        children_of=lambda pid: children.get(pid, []),
        baseline=baseline, rerank_pairs=rerank, plan=plan)


def test_obvious_neighborhood_is_excluded():
    latent = {"latent_abstraction": [
        _lat("p_near", 0.99, "principle near", doc="d_near"),
        _lat("p_far", 0.8, "variation in force changes perceived "
                           "intensity")]}
    children = {"p_far": [_kid("c_far", "strong weight gives movement "
                               "a forceful powerful quality")]}
    out = _run(latent, children)
    ids = [b["parent_id"] for b in out["wildcard"]]
    assert ids == ["p_far"]
    assert out["diagnostics"]["excluded_obvious"] == 1


def test_two_hop_support_floor_kills_ungrounded_bridges():
    latent = {"latent_abstraction": [
        _lat("p_a", 0.9, "abstract principle alpha"),
        _lat("p_b", 0.85, "abstract principle beta")]}
    children = {"p_a": [_kid("c_a", "totally unrelated source text")],
                "p_b": [_kid("c_b", "source that supports beta")]}

    def rerank(anchor, texts):
        return [0.9 if "beta" in anchor and "beta" in t else 0.02
                for t in texts]

    out = _run(latent, children, rerank=rerank)
    ids = [b["parent_id"] for b in out["wildcard"]]
    assert ids == ["p_b"]                       # interesting but
    assert out["diagnostics"]["support_filtered"] == 1  # unsupported dies
    assert out["wildcard"][0]["scores"]["source_support"] == 0.9


def test_novelty_damps_obvious_children():
    latent = {"latent_abstraction": [
        _lat("p_novel", 0.7, "principle one"),
        _lat("p_obvious", 0.9, "principle two")]}
    children = {
        "p_novel": [_kid("c_new", "weight quality modulates perceived "
                                  "force in expressive movement")],
        # lexically the query itself -> "useful but obvious" damp
        "p_obvious": [_kid("c_dup", "make an animated punch feel "
                                    "heavier with animated punch")],
    }
    out = _run(latent, children)
    first = out["wildcard"][0]
    assert first["parent_id"] == "p_novel"      # 0.7*0.7*1.0 > 0.9*0.9*0.4
    assert out["wildcard"][1]["scores"]["novelty"] == \
        DIVERGENT_DEFAULT_PLAN.borderline_novelty


def test_hard_bounds_and_channels_merge():
    latent = {
        "latent_abstraction": [_lat(f"p{i}", 0.9 - i * 0.01,
                                    f"principle {i}") for i in range(10)],
        "latent_transfer": [_lat("p0", 0.95, "transfer text zero")],
    }
    children = {f"p{i}": [_kid(f"c{i}", f"support text {i} mechanism")]
                for i in range(10)}
    out = _run(latent, children)
    assert len(out["wildcard"]) == DIVERGENT_DEFAULT_PLAN.max_bridges
    top = out["wildcard"][0]
    assert top["parent_id"] == "p0"
    assert set(top["channels"]) == {"abstraction", "transfer"}
    assert top["why_it_may_transfer"] == "transfer text zero"


def test_everything_fails_open_to_empty_lane():
    def broken(*_a, **_k):
        raise RuntimeError("store down")
    out = divergent_retrieve(
        "q", embed_query=lambda q: [0.0],
        latent_search=broken, children_of=broken,
        baseline=None, rerank_pairs=None)
    assert out["wildcard"] == []
    assert out["diagnostics"]["returned"] == 0


def test_no_reranker_fails_open_without_support_scores():
    latent = {"latent_abstraction": [_lat("p_a", 0.8, "principle")]}
    children = {"p_a": [_kid("c_a", "some grounded source text")]}
    out = _run(latent, children, rerank=None)
    assert len(out["wildcard"]) == 1
    assert out["wildcard"][0]["scores"]["source_support"] is None


def test_deterministic():
    latent = {"latent_abstraction": [
        _lat(f"p{i}", 0.8, f"principle {i}") for i in range(6)]}
    children = {f"p{i}": [_kid(f"c{i}", f"support {i}")]
                for i in range(6)}
    assert _run(latent, children) == _run(latent, children)


def test_bounds_configurable():
    latent = {"latent_abstraction": [
        _lat(f"p{i}", 0.9, f"principle {i}") for i in range(5)]}
    children = {f"p{i}": [_kid(f"c{i}", f"support {i}")]
                for i in range(5)}
    out = _run(latent, children,
               plan=DivergentPlan(max_bridges=1))
    assert len(out["wildcard"]) == 1
