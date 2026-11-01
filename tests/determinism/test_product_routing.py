"""product-library-routing-v1: a product turn with several libraries in scope is routed to the best one before retrieval — one
embedding, ONE query over the document profile collection (filtered to the caller's libraries, document points only), reciprocal
ranks aggregated per library; no profile → the library with the most query-ready documents; nothing countable → the first by id.
A fake Qdrant client and embedder (never a store for real). Pure: shared/ only."""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.product_search import routing as R  # noqa: E402
from polymath_shared.product_search.intent import detect  # noqa: E402
from polymath_shared.product_search.service import ProductTurn  # noqa: E402

MSG = "Find me products I could dropship for pet owners in the US"


class FakeQdrant:
    """query_points → the fused profile ranking it was given; records every call and closes."""

    def __init__(self, ranking=(), error: Exception | None = None):
        self.ranking, self.error, self.calls, self.closed = list(ranking), error, [], False

    def query_points(self, collection, **kw):
        self.calls.append({"collection": collection, **kw})
        if self.error is not None:
            raise self.error
        return SimpleNamespace(points=[SimpleNamespace(payload={"corpus_id": c, "doc_id": d}, score=1.0) for c, d in self.ranking])

    def close(self):
        self.closed = True


def embed(texts):
    return [[0.1, 0.2, 0.3] for _ in texts]


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(R.__file__).resolve().is_relative_to(ROOT), R.__file__


def test_a_single_library_skips_routing():
    q = FakeQdrant()
    got = R.route_library(MSG, ["cinema"], embed=embed, client=q, collection="c")
    assert got["method"] == "single" and got["chosen"] == "cinema" and got["runner_up"] is None and q.calls == []


def test_one_profile_query_filtered_to_the_callers_libraries_picks_the_best_and_records_the_runner_up():
    q = FakeQdrant([("commerce-v1", "d1"), ("commerce-v1", "d2"), ("cinema", "d3"), ("commerce-v1", "d4"), ("cinema", "d5")])
    got = R.route_library(MSG, ["cinema", "commerce-v1", "psych"], embed=embed, client=q, collection="polymath_document_profiles_x")
    assert got["method"] == "profile_rrf" and got["chosen"] == "commerce-v1" and got["runner_up"] == "cinema"
    assert got["scores"] == {"commerce-v1": round(1 / 61 + 1 / 62 + 1 / 64, 6), "cinema": round(1 / 63 + 1 / 65, 6), "psych": 0.0}
    assert got["documents_read"] == 5 and got["candidates"] == ["cinema", "commerce-v1", "psych"]
    assert len(q.calls) == 1 and q.calls[0]["collection"] == "polymath_document_profiles_x"     # ONE query
    call = q.calls[0]
    assert call["with_payload"] == ["doc_id", "corpus_id"] and call["limit"] == R.TOP_DOCS
    flt = call["prefetch"][0].filter
    assert flt.must[0].key == "corpus_id" and list(flt.must[0].match.any) == ["cinema", "commerce-v1", "psych"]
    assert flt.must_not[0].key == "scope" and flt.must_not[0].match.value == "section"           # document points only
    assert {p.using for p in call["prefetch"]} == {"identity", "theme", "questions", "searches", "title"}
    assert not q.closed                                                                           # a caller's client stays open


def test_each_document_counts_once_and_a_library_scores_its_best_three():
    ranking = [("a", "x1"), ("a", "x1"), ("b", "y1"), ("a", "x2"), ("a", "x3"), ("a", "x4"), ("a", "x5"), ("b", "y2")]
    scores, read = R.aggregate([SimpleNamespace(payload={"corpus_id": c, "doc_id": d}) for c, d in ranking], ["a", "b"])
    assert read == 7
    assert scores == {"a": round(1 / 61 + 1 / 63 + 1 / 64, 6), "b": round(1 / 62 + 1 / 67, 6)}
    assert R.aggregate([{"payload": {"corpus_id": "z", "doc_id": "q"}}], ["a"]) == ({}, 0)      # outside the scope: ignored


def test_no_profile_falls_back_to_the_library_with_the_most_query_ready_documents():
    counts = {"cinema": {"documents": 77, "query_ready_runs": 3}, "commerce-v1": {"documents": 120, "query_ready_runs": 0},
              "psych": {"documents": 40, "query_ready_runs": 1}}
    got = R.route_library(MSG, ["cinema", "commerce-v1", "psych"], embed=embed, client=FakeQdrant([]), collection="c",
                          counts=lambda cands: counts)
    assert got["method"] == "most_query_ready_documents" and got["chosen"] == "cinema" and got["runner_up"] == "psych"
    assert got["scores"] == {"cinema": 77, "psych": 40, "commerce-v1": 0}                         # no query-ready run: none ready
    assert got["counts"]["commerce-v1"] == {"documents": 120, "query_ready_runs": 0}
    assert any("no document profile" in n for n in got["notes"])


def test_a_failed_profile_query_is_receipted_and_falls_back():
    got = R.route_library(MSG, ["b", "a"], embed=embed, client=FakeQdrant(error=RuntimeError("qdrant down")), collection="c",
                          counts=lambda cands: {"a": {"documents": 1, "query_ready_runs": 1}})
    assert got["method"] == "most_query_ready_documents" and got["chosen"] == "a"
    assert any("the profile query failed (RuntimeError: qdrant down)" in n for n in got["notes"])


def test_nothing_countable_takes_the_first_library_by_id():
    def boom(cands):
        raise RuntimeError("db down")
    got = R.route_library(MSG, ["zeta", "alpha", "mid"], embed=None, counts=boom)
    assert got["method"] == "first_candidate" and got["chosen"] == "alpha" and got["runner_up"] == "mid"
    assert any("no embedder" in n for n in got["notes"]) and any("readiness count failed" in n for n in got["notes"])


def test_an_owned_client_comes_from_the_factory_and_is_closed():
    q = FakeQdrant([("b", "d1")])
    got = R.route_library(MSG, ["a", "b"], embed=embed, client_factory=lambda: (q, "coll"))
    assert got["chosen"] == "b" and q.closed and q.calls[0]["collection"] == "coll"


def test_the_product_turn_keeps_the_chosen_library_and_receipts_the_routing():
    t = ProductTurn(detect(MSG), message=MSG, corpus_ids=["cinema", "commerce-v1"], search=lambda **kw: {"status": "EMPTY"})
    chosen = t.route(["cinema", "commerce-v1"], embed=embed, client=FakeQdrant([("commerce-v1", "d1")]), collection="c")
    assert chosen == "commerce-v1" and t.corpus_ids == ["commerce-v1"]
    block, steps = t.finish_evidence()
    assert block["corpus_ids"] == ["commerce-v1"] and block["next"]["full_research"]["input"]["corpus_ids"] == ["commerce-v1"]
    routing = block["receipts"]["routing"]
    assert routing["chosen"] == "commerce-v1" and routing["runner_up"] == "cinema" and routing["method"] == "profile_rrf"
    assert set(routing) >= {"candidates", "chosen", "runner_up", "scores", "method"}
    assert t.receipt()["routing"] == {"method": "profile_rrf", "candidates": 2}


def test_a_routing_crash_never_fails_the_turn(monkeypatch):
    def crash(*a, **k):
        raise ValueError("bad")
    monkeypatch.setattr(R, "route_library", crash)
    t = ProductTurn(detect(MSG), message=MSG, corpus_ids=["b", "a"])
    assert t.route(["b", "a"], embed=embed) == "a" and t.routing["method"] == "first_candidate"
    assert t.routing["notes"] == ["routing failed (ValueError)"]
