"""R3b grounded answer generation invariants (no stores).

The validator is the trust boundary: structured claims referencing
bundle item ids are validated deterministically before any prose
renders. No factual assertion survives unless supported by one or more
bundle items. Conflicts are represented, never arbitrated. Epistemic
scope survives. Empty/insufficient evidence abstains explicitly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.answer_synthesis import (  # noqa: E402
    ABSTENTION_MESSAGE,
    CONFLICT_NOTE,
    bundle_item_id,
    grounded_answer,
    synthesize_claims,
    validate_claims,
)
from polymath_shared.evidence_assembly import assemble_evidence_bundle  # noqa: E402

QUERY = "who founded AcmeCorp"

FACTS = {
    "fact_f1": {
        "fact_id": "fact_f1", "predicate": "founded",
        "subject_id": "ent_alice", "object_id": "ent_acme",
        "qualifiers": {}, "decision": "ACCEPT",
        "rule_id": "founded-rule", "rule_version": "1.0.1",
        "provenance": {"roleset": "establish.01", "trigger_surface": "founded",
                       "semlink_resolved": True, "resource_contract_id": "03a513ec",
                       "compiled_lexical_sha256": "5c58adbd", "orientation": "active",
                       "weak": False},
    },
    "fact_f2": {
        "fact_id": "fact_f2", "predicate": "founded",
        "subject_id": "ent_bob", "object_id": "ent_acme",
        "qualifiers": {}, "decision": "ACCEPT",
        "rule_id": "founded-rule", "rule_version": "1.0.1",
        "provenance": {"roleset": "establish.01", "trigger_surface": "founded",
                       "semlink_resolved": True, "resource_contract_id": "03a513ec",
                       "compiled_lexical_sha256": "5c58adbd", "orientation": "active",
                       "weak": False},
    },
    "fact_scoped": {
        "fact_id": "fact_scoped", "predicate": "developed",
        "subject_id": "ent_alice", "object_id": "ent_gamma",
        "qualifiers": {"attributed": True, "attribution_source": "the report",
                       "certainty": "speculative"},
        "decision": "QUALIFY",
        "rule_id": "developed-rule", "rule_version": "1.0.1",
        "provenance": {"roleset": "develop.01", "trigger_surface": "developed",
                       "semlink_resolved": True, "resource_contract_id": "03a513ec",
                       "compiled_lexical_sha256": "5c58adbd", "orientation": "active",
                       "weak": False, "scope": {"conditional": True}},
    },
}

EVIDENCE = {
    "fact_f1": [{"evidence_id": "ev_f1", "fact_id": "fact_f1", "doc_id": "doc_a",
                 "chunk_id": "chunk_a1", "span_offsets": {}, "rule_id": "founded-rule",
                 "extractor_version": "1.0", "rule_version": "1.0.1"}],
    "fact_f2": [{"evidence_id": "ev_f2", "fact_id": "fact_f2", "doc_id": "doc_b",
                 "chunk_id": "chunk_b1", "span_offsets": {}, "rule_id": "founded-rule",
                 "extractor_version": "1.0", "rule_version": "1.0.1"}],
    "fact_scoped": [{"evidence_id": "ev_sc", "fact_id": "fact_scoped", "doc_id": "doc_c",
                     "chunk_id": "chunk_c1", "span_offsets": {}, "rule_id": "developed-rule",
                     "extractor_version": "1.0", "rule_version": "1.0.1"}],
}

ENTITIES = {
    "ent_alice": {"entity_id": "ent_alice", "core_type": "PERSON",
                  "normalized_surface": "AliceSmith"},
    "ent_bob": {"entity_id": "ent_bob", "core_type": "PERSON",
                "normalized_surface": "BobJones"},
    "ent_acme": {"entity_id": "ent_acme", "core_type": "ORGANIZATION",
                 "normalized_surface": "AcmeCorp"},
    "ent_gamma": {"entity_id": "ent_gamma", "core_type": "ORGANIZATION",
                  "normalized_surface": "GammaTech"},
}

DOCUMENTS = {
    "doc_a": {"doc_id": "doc_a", "corpus_id": "corpus_x", "source_name": "a.txt"},
    "doc_b": {"doc_id": "doc_b", "corpus_id": "corpus_x", "source_name": "b.txt"},
    "doc_c": {"doc_id": "doc_c", "corpus_id": "corpus_x", "source_name": "c.txt"},
}

CHUNKS = {
    "chunk_a1": {"chunk_id": "chunk_a1", "doc_id": "doc_a",
                 "text": "AliceSmith founded AcmeCorp.", "char_start": 0, "char_end": 27},
    "chunk_b1": {"chunk_id": "chunk_b1", "doc_id": "doc_b",
                 "text": "BobJones founded AcmeCorp.", "char_start": 0, "char_end": 25},
    "chunk_c1": {"chunk_id": "chunk_c1", "doc_id": "doc_c",
                 "text": "The report says AliceSmith developed GammaTech.",
                 "char_start": 0, "char_end": 47},
    "chunk_ctx": {"chunk_id": "chunk_ctx", "doc_id": "doc_c",
                  "text": "context chunk with no facts", "char_start": 48,
                  "char_end": 74},
}


def _graph_fact(fact_id: str) -> dict:
    fact = FACTS[fact_id]
    return {"fact_id": fact_id, "predicate": fact["predicate"],
            "subject": ENTITIES[fact["subject_id"]]["normalized_surface"],
            "object": ENTITIES[fact["object_id"]]["normalized_surface"]}


def _bundle(graph_facts=None, child_evidence=None) -> dict:
    return assemble_evidence_bundle(
        QUERY,
        graph_facts if graph_facts is not None else [_graph_fact("fact_f1")],
        child_evidence or [],
        resolve_fact=lambda fid: FACTS.get(fid),
        resolve_evidence=lambda fid: EVIDENCE.get(fid, []),
        resolve_entity=lambda eid: ENTITIES.get(eid),
        resolve_document=lambda did: DOCUMENTS.get(did),
        resolve_chunk=lambda cid: CHUNKS.get(cid),
    )


def test_direct_answer_is_grounded_and_cited() -> None:
    resp = grounded_answer(_bundle(), QUERY)
    assert resp["answer"] == "AliceSmith founded AcmeCorp [1]"
    assert resp["meta"]["abstained"] is False
    assert resp["meta"]["supported_claim_count"] == 1
    claims = [c for c in resp["claims"] if c["status"] == "supported"]
    assert len(claims) == 1
    assert claims[0]["text"] == "AliceSmith founded AcmeCorp"
    assert len(claims[0]["support"]) == 1
    assert resp["citations"] == [{
        "citation_id": 1,
        "bundle_item_ids": claims[0]["support"],
        "source_document_ids": ["doc_a"],
        "locators": ["chunk:chunk_a1@0:27"],
    }]


def test_multi_source_answer_cites_each_source() -> None:
    bundle = _bundle(graph_facts=[_graph_fact("fact_f1"), _graph_fact("fact_scoped")])
    resp = grounded_answer(bundle, QUERY)
    assert resp["meta"]["supported_claim_count"] == 2
    assert "AliceSmith founded AcmeCorp [1]" in resp["answer"]
    assert "According to the report, " in resp["answer"]
    docs = {d for c in resp["citations"] for d in c["source_document_ids"]}
    assert docs == {"doc_a", "doc_c"}
    assert resp["citations"][0]["locators"] == ["chunk:chunk_a1@0:27"]


def test_conflict_represented_never_arbitrated() -> None:
    bundle = _bundle(graph_facts=[_graph_fact("fact_f1"), _graph_fact("fact_f2")])
    resp = grounded_answer(bundle, QUERY)
    assert resp["meta"]["supported_claim_count"] == 2
    assert "AliceSmith founded AcmeCorp" in resp["answer"]
    assert "BobJones founded AcmeCorp" in resp["answer"]
    assert resp["answer"].endswith(CONFLICT_NOTE)
    conflicting = [c for c in resp["claims"] if c.get("conflicts_with")]
    assert len(conflicting) == 2
    assert conflicting[0]["conflicts_with"] == conflicting[1]["support"]


def test_scoped_claim_keeps_epistemic_qualification() -> None:
    resp = grounded_answer(_bundle(graph_facts=[_graph_fact("fact_scoped")]), QUERY)
    assert resp["answer"].startswith(
        "Under the stated condition, It is possible that According to the report, "
        "AliceSmith developed GammaTech [1]"
    )
    claim = resp["claims"][0]
    ep = claim["epistemics"]
    assert ep["conditional"] is True
    assert ep["certainty"] == "speculative"
    assert ep["attributed"] is True
    assert ep["attribution_source"] == "the report"


def test_evidence_only_input_abstains() -> None:
    bundle = _bundle(graph_facts=[], child_evidence=[{
        "chunk_id": "chunk_ctx", "doc_id": "doc_c", "parent_id": "",
        "text": "context chunk with no facts", "contract_ids": ["lexical-v1"],
    }])
    resp = grounded_answer(bundle, QUERY)
    assert resp["answer"] == ABSTENTION_MESSAGE
    assert resp["meta"]["abstained"] is True
    assert resp["citations"] == []
    assert all(c["status"] != "supported" for c in resp["claims"])


def test_unsupported_generated_claim_is_rejected() -> None:
    bundle = _bundle()
    fake = {"text": "AliceSmith founded AcmeCorp in 2019",
            "support": [bundle_item_id(bundle["evidence_bundle"][0])]}
    resp = grounded_answer(bundle, QUERY, synthesize=lambda b: [fake])
    assert "2019" not in resp["answer"]
    assert resp["meta"]["supported_claim_count"] == 0
    assert resp["meta"]["unsupported_claim_count"] == 1
    assert resp["claims"][0]["status"] == "unsupported"
    assert resp["answer"] == ABSTENTION_MESSAGE


def test_fake_citation_is_rejected() -> None:
    bundle = _bundle()
    fake = {"text": "AliceSmith founded AcmeCorp", "support": ["bitem_deadbeef"]}
    resp = grounded_answer(bundle, QUERY, synthesize=lambda b: [fake])
    assert resp["meta"]["supported_claim_count"] == 0
    assert resp["claims"][0]["status"] == "unsupported"
    assert resp["answer"] == ABSTENTION_MESSAGE


def test_claim_backed_only_by_evidence_items_is_rejected() -> None:
    bundle = _bundle(graph_facts=[], child_evidence=[{
        "chunk_id": "chunk_ctx", "doc_id": "doc_c", "parent_id": "",
        "text": "context chunk with no facts", "contract_ids": ["lexical-v1"],
    }])
    ev_item_id = bundle_item_id(bundle["evidence_bundle"][0])
    fake = {"text": "context chunk with no facts", "support": [ev_item_id]}
    resp = grounded_answer(bundle, QUERY, synthesize=lambda b: [fake])
    assert resp["claims"][0]["status"] == "unsupported"
    assert resp["answer"] == ABSTENTION_MESSAGE


def test_malformed_model_output_fails_closed() -> None:
    bundle = _bundle()
    resp = grounded_answer(bundle, QUERY, synthesize=lambda b: [
        None, "not a dict", {"text": None, "support": None},
        {"text": "   ", "support": ["x"]}, {"text": 42, "support": []},
    ])
    assert resp["meta"]["supported_claim_count"] == 0
    assert resp["answer"] == ABSTENTION_MESSAGE
    assert resp["meta"]["abstained"] is True


def test_identical_synthetic_output_is_byte_identical() -> None:
    bundle = _bundle(graph_facts=[_graph_fact("fact_f1"), _graph_fact("fact_scoped")])
    fake_proposer = lambda b: [
        {"text": "AliceSmith founded AcmeCorp",
         "support": [bundle_item_id(i) for i in b["evidence_bundle"]
                     if i.get("fact_id") == "fact_f1"]},
        {"text": "AliceSmith developed GammaTech",
         "support": [bundle_item_id(i) for i in b["evidence_bundle"]
                     if i.get("fact_id") == "fact_scoped"]},
    ]
    a = grounded_answer(bundle, QUERY, synthesize=fake_proposer)
    b = grounded_answer(bundle, QUERY, synthesize=fake_proposer)
    assert a == b


def test_citation_order_follows_bundle_order_deterministically() -> None:
    bundle = _bundle(graph_facts=[_graph_fact("fact_scoped"), _graph_fact("fact_f1")])
    a = grounded_answer(bundle, QUERY)
    b = grounded_answer(bundle, QUERY)
    assert a == b
    first_claim = [c for c in a["claims"] if c["status"] == "supported"][0]
    assert first_claim["text"] == "AliceSmith founded AcmeCorp"  # bundle order: f1 < scoped
    assert a["citations"][0]["citation_id"] == 1


def test_default_proposer_emits_one_claim_per_claim_item() -> None:
    bundle = _bundle(graph_facts=[_graph_fact("fact_f1"), _graph_fact("fact_f2")])
    proposed = synthesize_claims(bundle)
    assert len(proposed) == 2
    assert all(p["support"] for p in proposed)


def test_validate_claims_maps_every_support_to_real_bundle_item() -> None:
    bundle = _bundle()
    proposed = synthesize_claims(bundle)
    validation = validate_claims(proposed, bundle)
    supported = validation["supported"]
    assert supported
    item_ids = {bundle_item_id(i) for i in bundle["evidence_bundle"]}
    for claim in supported:
        assert all(s in item_ids for s in claim["support"])
