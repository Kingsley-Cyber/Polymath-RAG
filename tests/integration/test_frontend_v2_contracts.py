"""F11 — integration contracts the V2 frontend depends on.

Runs against a LIVE orchestrator (the frontend is a renderer; if these shapes drift the
UI lies). Gated behind POLYMATH_INTEGRATION=1 like the rest of tests/integration.

Every assertion here is a shape the UI reads, and each one is tied to the plan rule it
protects, so a failure says WHICH promise broke rather than just "a key is missing".
"""
from __future__ import annotations

import os

import pytest
import urllib.request
import json

BASE = os.environ.get("POLYMATH_BASE_URL", "http://127.0.0.1:7200")
COVERED = "rag-canary"      # VNEXT_COMPLETE — the green path
INCOMPLETE = "cinema"       # the honesty fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="live backend required; set POLYMATH_INTEGRATION=1")


def _get(path: str, timeout: int = 60):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.load(r)


def _post(path: str, body: dict, timeout: int = 300):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(body).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ── the readiness triad (plan §7) ────────────────────────────────────────────

def test_the_three_readiness_concepts_are_separately_served() -> None:
    sr = _get(f"/semantic_readiness?corpus_id={COVERED}")
    assert sr["contract"] == "semantic-readiness-v1"
    assert sr["verdict"] in ("SEMANTIC_COMPLETE", "SEMANTIC_INCOMPLETE")
    assert sr["vnext"]["verdict"] in ("VNEXT_COMPLETE", "VNEXT_INCOMPLETE")
    for k in ("eligible", "mapped", "excluded", "unresolved"):
        assert k in sr["vnext"]["parents"]
    cp = _get(f"/control_plane?corpus_id={COVERED}")
    for k in ("documents", "semantic_ready", "processing", "blocked"):
        assert k in cp["summary"]


def test_the_legacy_query_ready_boolean_is_not_a_readiness_signal() -> None:
    """The reason the UI refuses that field: it can read true on an incomplete corpus."""
    corpora = {c["corpus_id"]: c for c in _get("/corpora")["corpora"]}
    if INCOMPLETE not in corpora:
        pytest.skip("cinema not present")
    sr = _get(f"/semantic_readiness?corpus_id={INCOMPLETE}")
    if sr["vnext"]["verdict"] == "VNEXT_COMPLETE":
        pytest.skip("cinema is now complete — the fixture no longer demonstrates the gap")
    assert corpora[INCOMPLETE]["query_ready"] is True
    assert sr["vnext"]["verdict"] == "VNEXT_INCOMPLETE"


def test_per_document_readiness_carries_its_own_blockers() -> None:
    s = _get(f"/documents/summary?corpus_id={COVERED}")["summaries"]
    assert s, "covered corpus has no documents"
    one = next(iter(s.values()))
    for k in ("vnext_ready", "map_eligible", "map_active", "map_excluded",
              "map_unresolved", "profile_present", "profile_vnext",
              "graph_entities", "graph_relations", "parents", "children"):
        assert k in one


# ── the query trace: FIRED != SURVIVED != USED (plan §3) ─────────────────────

def test_the_retrieval_receipt_can_distinguish_fired_from_survived() -> None:
    out = _post("/retrieve", {"query": "what is the ZQX fact",
                              "corpus_id": COVERED, "mode": "HYBRID"})
    assert out["meta"]["plan_version"] == "chat-retrieval-v2", \
        "the final core must serve /retrieve (register 11.191)"
    trace = out["trace"]
    assert "lane_sizes" in trace, "no per-lane sizes => the UI cannot show FIRED"
    assert "funnel_lanes" in trace, "no union counts => the UI cannot show ENTERED UNION"
    assert isinstance(out["evidence"], list)


# ── GRAPH-BROWSE-V1 (F9) ─────────────────────────────────────────────────────

def test_graph_entity_search_is_corpus_scoped_and_ided() -> None:
    d = _get(f"/graph/entities?corpus_id={COVERED}&q=&limit=5")
    assert d["contract"] == "graph-browse-v1"
    for e in d["entities"]:
        for k in ("normalized_surface", "surface", "mentions", "documents", "entity_id"):
            assert k in e


def test_graph_relationships_are_source_attested_or_withheld() -> None:
    ents = _get(f"/graph/entities?corpus_id={COVERED}&q=&limit=10")["entities"]
    withid = [e for e in ents if e["entity_id"]]
    if not withid:
        pytest.skip("no entity resolved to a graph id in this corpus")
    d = _get(f"/graph/entity/{withid[0]['entity_id']}/relationships"
             f"?corpus_id={COVERED}&limit=10")
    assert "dropped_unattested" in d, "the UI must be able to show what was withheld"
    for r in d["relationships"]:
        assert r["sources"], "a relationship with no source must never be served"
        assert r["source_count"] >= 1
        for s in r["sources"]:
            assert s["doc_id"] and s["chunk_id"]


# ── COMPARE-REVIEW-V1 (F6, F7) ───────────────────────────────────────────────

def test_compare_runs_every_arm_and_returns_per_arm_accounting() -> None:
    d = _post("/compare", {"message": "what is the ZQX fact", "corpus_id": COVERED,
                           "modes": ["HYBRID", "GRAPH"]})
    assert d["contract"] == "compare-retrieval-v1"
    assert [a["mode"] for a in d["arms"]] == ["HYBRID", "GRAPH"]
    for arm in d["arms"]:
        assert arm["ok"], arm.get("error")
        r = arm["retrieval"]
        for k in ("evidence_count", "selected_documents", "union_size", "lane_sizes", "documents"):
            assert k in r
        assert isinstance(r["rows"], list)


def test_compare_refuses_a_non_public_mode() -> None:
    """VECTOR is a backend primitive, never a product mode (plan §2)."""
    try:
        _post("/compare", {"message": "x", "corpus_id": COVERED, "modes": ["VECTOR"]})
    except urllib.error.HTTPError as exc:      # noqa: F821
        assert exc.code == 422
    else:
        pytest.fail("VECTOR must not be comparable")


def test_review_refuses_an_empty_answer() -> None:
    try:
        _post("/review", {"question": "q", "answer": "   ", "citations": [],
                          "evidence": [], "retrieval_meta": {}})
    except urllib.error.HTTPError as exc:      # noqa: F821
        assert exc.code == 422
    else:
        pytest.fail("an empty answer must not be reviewable")
