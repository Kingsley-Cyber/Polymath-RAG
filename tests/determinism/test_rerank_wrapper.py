"""G3 rerank wrapper invariants (no stores).

The reranker reorders the FUSED candidates only: it never adds or
removes candidates (recall cannot drop), attaches rerank provenance
(model identity + revision + version) to every reordered candidate,
and leaves rank-based fusion upstream untouched. Degradation is loud.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.rerank import (  # noqa: E402
    RERANK_VERSION,
    RerankUnavailable,
    apply_rerank,
    rerank_enabled,
    rerank_fused,
)


class FakeClient:
    def __init__(self, scorer) -> None:
        self._scorer = scorer

    def rerank(self, query, documents, top_k=None):
        scores = [self._scorer(query, d) for d in documents]
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return {
            "scores": scores,
            "order": order,
            "model_id": "fake-model",
            "model_revision": "fake-rev",
        }

    def close(self) -> None:
        pass


def _scorer(query, doc):
    return float(len(set(query.split()) & set(doc.split())))


def test_rerank_reorders_without_changing_candidate_set() -> None:
    docs = [
        {"doc_id": "a", "semantic_summary": "baking bread and cakes"},
        {"doc_id": "b", "semantic_summary": "vector retrieval and ranking"},
    ]
    rd, rc = rerank_fused("vector retrieval", docs, [], client=FakeClient(_scorer))
    assert [d["doc_id"] for d in rd] == ["b", "a"]
    assert {d["doc_id"] for d in rd} == {"a", "b"}  # no drop, no add


def test_rerank_attaches_provenance() -> None:
    docs = [{"doc_id": "a", "semantic_summary": "vector retrieval"}]
    rd, _ = rerank_fused("vector retrieval", docs, [], client=FakeClient(_scorer))
    assert rd[0]["rerank_score"] == 2.0
    assert rd[0]["rerank_model_id"] == "fake-model"
    assert rd[0]["rerank_model_revision"] == "fake-rev"
    assert rd[0]["rerank_version"] == RERANK_VERSION


def test_children_reranked_too() -> None:
    children = [
        {"chunk_id": "c1", "text": "sourdough fermentation"},
        {"chunk_id": "c2", "text": "vector retrieval systems"},
    ]
    _, rc = rerank_fused("vector retrieval", [], children, client=FakeClient(_scorer))
    assert [c["chunk_id"] for c in rc] == ["c2", "c1"]
    assert rc[0]["rerank_version"] == RERANK_VERSION


def test_disabled_candidate_returns_inputs_untouched(monkeypatch) -> None:
    monkeypatch.setattr("polymath_shared.rerank.rerank_enabled", lambda: False)
    docs = [{"doc_id": "a", "semantic_summary": "x"}]
    rd, rc = apply_rerank("q", docs, [])
    assert rd is docs and rc == []


def test_unavailable_reranker_is_loud(monkeypatch) -> None:
    monkeypatch.setattr("polymath_shared.rerank.rerank_enabled", lambda: True)

    def boom():
        raise RuntimeError("connection refused")

    with pytest.raises(RerankUnavailable):
        apply_rerank("q", [{"doc_id": "a", "semantic_summary": "x"}], [],
                     client_factory=boom)
