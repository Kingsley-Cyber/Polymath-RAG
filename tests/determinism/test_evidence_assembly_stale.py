"""STALE-PROJECTION-TOLERANCE-V1 — the assembler skips text-lane hits whose
document/chunk no longer resolves when a sink is supplied, records them,
and still raises (unchanged contract) when it is not; graph-lane facts
never become tolerant."""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.evidence_assembly import (  # noqa: E402
    UnresolvedDocumentError,
    assemble_evidence_bundle,
    stale_projection_degradation,
)

LIVE = "doc_live"
GHOST = "doc_ghost"


def _resolve_document(doc_id):
    return {"doc_id": doc_id, "corpus_id": "c", "source_name": "live.md"} if doc_id == LIVE else None


def _resolve_chunk(chunk_id):
    return {"chunk_id": chunk_id, "doc_id": LIVE, "parent_id": "p1", "text": "live text"} \
        if chunk_id.startswith("live") else None


def _assemble(**kw):
    return assemble_evidence_bundle(
        "q", [], [{"chunk_id": "live-c1", "doc_id": LIVE, "parent_id": "p1", "contract_ids": []},
                  {"chunk_id": "ghost-c9", "doc_id": GHOST, "parent_id": "p9", "contract_ids": []}],
        resolve_fact=lambda fid: None, resolve_evidence=lambda fid: [],
        resolve_entity=lambda eid: None, resolve_document=_resolve_document,
        resolve_chunk=_resolve_chunk,
        document_summaries=[{"doc_id": LIVE, "summary": "live doc"},
                            {"doc_id": GHOST, "summary": "ghost doc"}],
        section_summaries=[{"chunk_id": "live-p1", "doc_id": LIVE, "summary": "live section"},
                           {"chunk_id": "ghost-p9", "doc_id": GHOST, "summary": "ghost section"}],
        **kw)


def test_strict_default_still_raises() -> None:
    with pytest.raises(UnresolvedDocumentError):
        _assemble()


def test_sink_skips_and_records_stale_text_hits() -> None:
    stale: list[dict] = []
    bundle = _assemble(unresolved=stale)
    ids = {(i.get("source_document_id"), i.get("text_kind")) for i in bundle["evidence_bundle"]}
    assert all(d == LIVE for d, _ in ids)
    assert len(bundle["evidence_bundle"]) == 3          # live doc summary, section, child
    assert sorted(e["kind"] for e in stale) == ["child_chunk", "document_summary", "section_summary"]
    assert all(e.get("doc_id") == GHOST or e["kind"] == "child_chunk" for e in stale)
    deg = stale_projection_degradation(stale)
    assert deg and deg[0]["component"] == "projection" and GHOST in deg[0]["doc_ids"]
    assert stale_projection_degradation([]) == []


def test_graph_lane_never_tolerant() -> None:
    from polymath_shared.evidence_assembly import UnresolvedChunkError
    stale: list[dict] = []
    with pytest.raises((UnresolvedDocumentError, UnresolvedChunkError)):
        assemble_evidence_bundle(
            "q", [{"fact_id": "f1", "predicate": "uses", "subject": "a", "object": "b"}], [],
            resolve_fact=lambda fid: {"fact_id": "f1", "predicate": "uses", "subject_id": "e1",
                                      "object_id": "e2", "qualifiers": {}, "decision": "ACCEPT",
                                      "rule_id": "uses-rule", "rule_version": "1.0.1",
                                      "provenance": {"extractor": "test", "run_id": "r1"}},
            resolve_evidence=lambda fid: [{"evidence_id": "ev1", "chunk_id": "ghost-c9", "doc_id": GHOST}],
            resolve_entity=lambda eid: {"entity_id": eid, "core_type": "Concept", "normalized_surface": eid},
            resolve_document=_resolve_document, resolve_chunk=_resolve_chunk,
            unresolved=stale)


def test_graph_fact_no_supporting_evidence_fails_open(pytestconfig=None) -> None:
    # GRAPH-FAIL-OPEN-V1 (§19): a graph fact with NO supporting evidence chunk cannot be
    # source-attested, so with a sink it is DROPPED (recorded), not raised — the normal answer
    # path survives on the remaining source-backed evidence. Strict default (no sink) still raises.
    from polymath_shared.evidence_assembly import UnresolvedEvidenceError
    fact = [{"fact_id": "f1", "predicate": "uses", "subject": "a", "object": "b"}]
    kw = dict(resolve_fact=lambda fid: {"fact_id": "f1", "predicate": "uses", "subject_id": "e1",
                                        "object_id": "e2", "qualifiers": {}, "decision": "ACCEPT",
                                        "rule_id": "uses-rule", "rule_version": "1.0.1",
                                        "provenance": {"extractor": "test", "run_id": "r1"}},
              resolve_evidence=lambda fid: [],          # NO supporting evidence
              resolve_entity=lambda eid: {"entity_id": eid, "core_type": "Concept", "normalized_surface": eid},
              resolve_document=_resolve_document, resolve_chunk=_resolve_chunk)
    # strict default: raises
    with pytest.raises(UnresolvedEvidenceError):
        assemble_evidence_bundle("q", fact, [], **kw)
    # with a sink: fails open — the fact is dropped + recorded, no raise, the turn survives
    stale: list[dict] = []
    bundle = assemble_evidence_bundle("q", fact, [
        {"chunk_id": "live-c1", "doc_id": LIVE, "parent_id": "p1", "contract_ids": []}],
        unresolved=stale, **kw)
    assert any(e.get("kind") == "graph_fact" and e.get("fact_id") == "f1" for e in stale)
    assert bundle["evidence_bundle"]                     # the child evidence still assembles
