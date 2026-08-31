"""R3a EvidenceBundle assembly invariants (no stores).

Every candidate claim must be traceable to fact/entity IDs, source
document, exact evidence span, provenance, epistemics, scope, and
retrieval lane. Missing provenance or unresolvable references fail
loudly. Duplicates collapse; conflicts coexist; ordering is
deterministic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.evidence_assembly import (  # noqa: E402
    MissingProvenanceError,
    UnresolvedChunkError,
    UnresolvedEntityError,
    UnresolvedEvidenceError,
    UnresolvedFactError,
    assemble_evidence_bundle,
)

QUERY = "who founded Acme and what did the evaluator verify"

FACTS = {
    "fact_f1": {
        "fact_id": "fact_f1", "predicate": "founded",
        "subject_id": "ent_alice", "object_id": "ent_acme",
        "qualifiers": {}, "decision": "ACCEPT",
        "rule_id": "founded-rule", "rule_version": "1.0.1",
        "provenance": {
            "roleset": "establish.01", "trigger_lemma": "found",
            "trigger_surface": "founded", "semlink_resolved": True,
            "resource_contract_id": "03a513ec", "orientation": "active",
            "weak": False,
            "compiled_lexical_sha256": "5c58adbd",
        },
    },
    "fact_f2": {
        "fact_id": "fact_f2", "predicate": "causes",
        "subject_id": "ent_evaluator", "object_id": "ent_verification",
        "qualifiers": {"attributed": True, "attribution_source": "the report"},
        "decision": "QUALIFY",
        "rule_id": "causes-rule", "rule_version": "1.0.1",
        "provenance": {
            "roleset": "cause.01", "trigger_lemma": "verifies",
            "trigger_surface": "verifies", "semlink_resolved": True,
            "resource_contract_id": "03a513ec", "orientation": "active",
            "weak": True, "scope": {"conditional": True, "speculative": True},
            "compiled_lexical_sha256": "5c58adbd",
        },
    },
    "fact_conflict": {
        "fact_id": "fact_conflict", "predicate": "founded",
        "subject_id": "ent_bob", "object_id": "ent_acme",
        "qualifiers": {}, "decision": "ACCEPT",
        "rule_id": "founded-rule", "rule_version": "1.0.1",
        "provenance": {
            "roleset": "establish.01", "trigger_lemma": "found",
            "trigger_surface": "founded", "semlink_resolved": False,
            "resource_contract_id": "03a513ec", "orientation": "active",
            "weak": False, "compiled_lexical_sha256": "5c58adbd",
        },
    },
    "fact_no_provenance": {
        "fact_id": "fact_no_provenance", "predicate": "uses",
        "subject_id": "ent_alice", "object_id": "ent_acme",
        "qualifiers": {}, "decision": "ACCEPT",
        "rule_id": "uses-rule", "rule_version": "1.0.1",
        "provenance": {},
    },
}

EVIDENCE = {
    "fact_f1": [
        {"evidence_id": "ev_f1a", "fact_id": "fact_f1", "doc_id": "doc_a",
         "chunk_id": "chunk_a1", "span_offsets": {"chunk_char_start": 0},
         "rule_id": "founded-rule", "extractor_version": "1.0",
         "rule_version": "1.0.1"},
    ],
    "fact_f2": [
        {"evidence_id": "ev_f2a", "fact_id": "fact_f2", "doc_id": "doc_b",
         "chunk_id": "chunk_b1", "span_offsets": {"chunk_char_start": 10},
         "rule_id": "causes-rule", "extractor_version": "1.0",
         "rule_version": "1.0.1"},
    ],
    "fact_conflict": [
        {"evidence_id": "ev_c1", "fact_id": "fact_conflict", "doc_id": "doc_a",
         "chunk_id": "chunk_a2", "span_offsets": {"chunk_char_start": 5},
         "rule_id": "founded-rule", "extractor_version": "1.0",
         "rule_version": "1.0.1"},
    ],
    "fact_no_provenance": [
        {"evidence_id": "ev_np1", "fact_id": "fact_no_provenance",
         "doc_id": "doc_a", "chunk_id": "chunk_a1",
         "span_offsets": {}, "rule_id": "uses-rule",
         "extractor_version": "1.0", "rule_version": "1.0.1"},
    ],
}

ENTITIES = {
    "ent_alice": {"entity_id": "ent_alice", "core_type": "PERSON",
                  "normalized_surface": "Alice"},
    "ent_bob": {"entity_id": "ent_bob", "core_type": "PERSON",
                "normalized_surface": "Bob"},
    "ent_acme": {"entity_id": "ent_acme", "core_type": "ORGANIZATION",
                 "normalized_surface": "Acme"},
    "ent_evaluator": {"entity_id": "ent_evaluator", "core_type": "SYSTEM",
                      "normalized_surface": "the evaluator"},
    "ent_verification": {"entity_id": "ent_verification", "core_type": "PROCESS",
                         "normalized_surface": "verification"},
}

DOCUMENTS = {
    "doc_a": {"doc_id": "doc_a", "corpus_id": "corpus_x",
              "source_name": "a.txt"},
    "doc_b": {"doc_id": "doc_b", "corpus_id": "corpus_x",
              "source_name": "b.txt"},
}

CHUNKS = {
    "chunk_a1": {"chunk_id": "chunk_a1", "doc_id": "doc_a",
                 "text": "Alice founded Acme in 2010.", "char_start": 0, "char_end": 27},
    "chunk_a2": {"chunk_id": "chunk_a2", "doc_id": "doc_a",
                 "text": "Bob actually founded Acme.", "char_start": 28, "char_end": 52},
    "chunk_b1": {"chunk_id": "chunk_b1", "doc_id": "doc_b",
                 "text": "The evaluator verifies output; the report says so.",
                 "char_start": 0, "char_end": 52},
    "chunk_c1": {"chunk_id": "chunk_c1", "doc_id": "doc_b",
                 "text": "generator evaluator loop verification",
                 "char_start": 53, "char_end": 91},
}


def _graph_fact(fact_id: str) -> dict:
    fact = FACTS[fact_id]
    return {
        "fact_id": fact_id, "predicate": fact["predicate"],
        "subject": ENTITIES[fact["subject_id"]]["normalized_surface"],
        "object": ENTITIES[fact["object_id"]]["normalized_surface"],
    }


def _assemble(graph_facts=None, child_evidence=None):
    return assemble_evidence_bundle(
        QUERY,
        graph_facts if graph_facts is not None else [_graph_fact("fact_f1")],
        child_evidence if child_evidence is not None else [],
        resolve_fact=lambda fid: FACTS.get(fid),
        resolve_evidence=lambda fid: EVIDENCE.get(fid, []),
        resolve_entity=lambda eid: ENTITIES.get(eid),
        resolve_document=lambda did: DOCUMENTS.get(did),
        resolve_chunk=lambda cid: CHUNKS.get(cid),
    )


def test_direct_fact_assembles_fully_traceable_claim() -> None:
    bundle = _assemble()
    assert bundle["query"] == QUERY
    assert bundle["meta"]["claim_count"] == 1
    item = bundle["evidence_bundle"][0]
    assert item["kind"] == "claim"
    assert item["claim_candidate"] == "Alice founded Acme"
    assert item["fact_id"] == "fact_f1"
    assert item["knowledge_id"] == "fact_f1"
    assert item["entity_ids"] == {"subject_id": "ent_alice", "object_id": "ent_acme"}
    assert item["predicate"] == "founded"
    assert item["source_document_id"] == "doc_a"
    assert item["source_span"]["text"] == "Alice founded Acme in 2010."
    assert item["source_span"]["locator"] == "chunk:chunk_a1@0:27"
    assert item["source_span"]["chunk_id"] == "chunk_a1"
    assert item["source_span"]["offsets_source"] == "chunk"
    assert item["provenance"]["rule_id"] == "founded-rule"
    assert item["provenance"]["evidence_id"] == "ev_f1a"
    assert item["provenance"]["roleset"] == "establish.01"
    assert item["provenance"]["resource_contract_id"] == "03a513ec"
    assert item["epistemics"]["decision"] == "ACCEPT"
    assert item["applicability"]["corpus_id"] == "corpus_x"
    assert item["retrieval"] == {"lanes": ["graph"], "score": None}


def test_relation_fact_with_scope_keeps_scope() -> None:
    bundle = _assemble(graph_facts=[_graph_fact("fact_f2")])
    item = bundle["evidence_bundle"][0]
    assert item["claim_candidate"] == "the evaluator causes verification"
    assert item["epistemics"]["decision"] == "QUALIFY"
    assert item["epistemics"]["attributed"] is True
    assert item["epistemics"]["attribution_source"] == "the report"
    conditions = item["applicability"]["conditions"]
    assert "conditional" in conditions
    assert "attributed:the report" in conditions


def test_conflicting_evidence_coexists() -> None:
    bundle = _assemble(graph_facts=[
        _graph_fact("fact_f1"), _graph_fact("fact_conflict"),
    ])
    claims = [i for i in bundle["evidence_bundle"] if i["kind"] == "claim"]
    assert len(claims) == 2
    assert {c["fact_id"] for c in claims} == {"fact_f1", "fact_conflict"}
    assert "Alice founded Acme" in {c["claim_candidate"] for c in claims}
    assert "Bob founded Acme" in {c["claim_candidate"] for c in claims}


def test_missing_provenance_fails_loudly() -> None:
    with pytest.raises(MissingProvenanceError):
        _assemble(graph_facts=[_graph_fact("fact_no_provenance")])


def test_unresolved_fact_fails() -> None:
    with pytest.raises(UnresolvedFactError):
        _assemble(graph_facts=[{
            "fact_id": "fact_ghost", "predicate": "uses",
            "subject": "x", "object": "y",
        }])


def test_claim_without_evidence_fails() -> None:
    FACTS["fact_orphan"] = {
        "fact_id": "fact_orphan", "predicate": "uses",
        "subject_id": "ent_alice", "object_id": "ent_acme",
        "qualifiers": {}, "decision": "ACCEPT",
        "rule_id": "uses-rule", "rule_version": "1.0.1",
        "provenance": {"roleset": "use.01", "resource_contract_id": "03a513ec",
                       "compiled_lexical_sha256": "5c58adbd"},
    }
    try:
        with pytest.raises(UnresolvedEvidenceError):
            _assemble(graph_facts=[_graph_fact("fact_orphan")])
    finally:
        del FACTS["fact_orphan"]


def test_unresolved_entity_fails() -> None:
    with pytest.raises(UnresolvedEntityError):
        assemble_evidence_bundle(
            QUERY,
            [_graph_fact("fact_f1")],
            [],
            resolve_fact=lambda fid: {**FACTS["fact_f1"],
                                      "subject_id": "ent_ghost"},
            resolve_evidence=lambda fid: EVIDENCE.get(fid, []),
            resolve_entity=lambda eid: ENTITIES.get(eid),
            resolve_document=lambda did: DOCUMENTS.get(did),
            resolve_chunk=lambda cid: CHUNKS.get(cid),
        )


def test_unresolved_chunk_fails() -> None:
    with pytest.raises(UnresolvedChunkError):
        assemble_evidence_bundle(
            QUERY,
            [_graph_fact("fact_f1")],
            [],
            resolve_fact=lambda fid: FACTS.get(fid),
            resolve_evidence=lambda fid: [
                {**EVIDENCE["fact_f1"][0], "chunk_id": "chunk_ghost"},
            ],
            resolve_entity=lambda eid: ENTITIES.get(eid),
            resolve_document=lambda did: DOCUMENTS.get(did),
            resolve_chunk=lambda cid: CHUNKS.get(cid),
        )


def test_duplicate_facts_collapse_deterministically() -> None:
    dup = [_graph_fact("fact_f1"), _graph_fact("fact_f1")]
    bundle = _assemble(graph_facts=dup)
    claims = [i for i in bundle["evidence_bundle"] if i["kind"] == "claim"]
    assert len(claims) == 1


def test_evidence_only_items_resolve_and_make_no_claims() -> None:
    bundle = _assemble(
        graph_facts=[],
        child_evidence=[
            {"chunk_id": "chunk_c1", "doc_id": "doc_b", "parent_id": "p_b",
             "text": "generator evaluator loop verification",
             "contract_ids": ["lexical-v1", "dense-v1"]},
            {"chunk_id": "chunk_c1", "doc_id": "doc_b", "parent_id": "p_b",
             "text": "generator evaluator loop verification",
             "contract_ids": ["lexical-v1"]},  # duplicate chunk collapses
        ],
    )
    assert bundle["meta"]["evidence_count"] == 1
    item = bundle["evidence_bundle"][0]
    assert item["kind"] == "evidence"
    assert item["claim_candidate"] is None
    assert item["fact_id"] is None
    assert item["knowledge_id"] == "chunk_c1"
    assert item["source_document_id"] == "doc_b"
    assert item["source_span"]["locator"] == "chunk:chunk_c1@53:91"
    assert item["retrieval"]["lanes"] == ["dense", "lexical"]
    assert item["epistemics"]["decision"] == "evidence"


def test_bundle_ordering_is_deterministic_for_identical_inputs() -> None:
    graph = [_graph_fact("fact_conflict"), _graph_fact("fact_f1")]
    child = [
        {"chunk_id": "chunk_c1", "doc_id": "doc_b", "parent_id": "p_b",
         "text": "generator evaluator loop verification",
         "contract_ids": ["lexical-v1"]},
    ]
    a = json.dumps(_assemble(graph_facts=graph, child_evidence=child), sort_keys=True)
    b = json.dumps(_assemble(graph_facts=list(reversed(graph)),
                             child_evidence=child), sort_keys=True)
    assert a == b
    kinds = [i["kind"] for i in _assemble(graph_facts=graph, child_evidence=child)["evidence_bundle"]]
    assert kinds == ["claim", "claim", "evidence"]
    ids = [i["knowledge_id"] for i in _assemble(graph_facts=graph, child_evidence=child)["evidence_bundle"]]
    assert ids == ["fact_conflict", "fact_f1", "chunk_c1"]


def test_presentation_fields_are_additive_and_null_safe() -> None:
    """UI-V3 §3.1: every item carries presentation {title, heading_path,
    human_locator}; NULL heading_path (legacy rows) degrades to
    source-name-only, empty strings, never a raise."""
    # legacy chunk (no heading_path key at all)
    bundle = _assemble(child_evidence=[
        {"chunk_id": "chunk_a1", "doc_id": "doc_a", "contract_ids": []}])
    items = bundle["evidence_bundle"]
    assert all("presentation" in i for i in items)
    child = next(i for i in items if i["text_kind"] == "child_chunk")
    assert child["presentation"] == {
        "title": "", "heading_path": "", "human_locator": "a.txt"}

    # chunk WITH a heading path -> title is the leaf, locator composes
    CHUNKS["chunk_hp"] = {
        "chunk_id": "chunk_hp", "doc_id": "doc_a",
        "text": "Zoned text.", "char_start": 100, "char_end": 111,
        "heading_path": ["Chapter 1", "Cloud Models"]}
    try:
        bundle2 = _assemble(child_evidence=[
            {"chunk_id": "chunk_hp", "doc_id": "doc_a", "contract_ids": []}])
        child2 = next(i for i in bundle2["evidence_bundle"]
                      if i["text_kind"] == "child_chunk")
        assert child2["presentation"]["title"] == "Cloud Models"
        assert child2["presentation"]["heading_path"] == \
            "Chapter 1 \u203a Cloud Models"
        assert child2["presentation"]["human_locator"] == \
            "a.txt \u203a Cloud Models"
    finally:
        del CHUNKS["chunk_hp"]

    # document summaries: title IS the source name
    bundle3 = _assemble(child_evidence=[])
    # (claim items present; verify doc-summary path via a summary row)
    from polymath_shared.evidence_assembly import assemble_evidence_bundle
    b4 = assemble_evidence_bundle(
        QUERY, [], [],
        resolve_fact=lambda f: None, resolve_evidence=lambda f: [],
        resolve_entity=lambda e: None,
        resolve_document=lambda did: DOCUMENTS.get(did),
        resolve_chunk=lambda cid: CHUNKS.get(cid),
        document_summaries=[{"doc_id": "doc_a", "summary": "About A."}])
    ds = b4["evidence_bundle"][0]
    assert ds["presentation"]["human_locator"] == "a.txt"
    assert ds["presentation"]["title"] == "a.txt"
