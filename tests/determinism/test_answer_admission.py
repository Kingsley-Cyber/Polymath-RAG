"""ANSWER-ADMISSION-V1: NO ANSWER > UNSUPPORTED ANSWER.

Regression for the 2026-08-26 SMART verification P0: a nonce query
with zero exact support returned ten cited passages and
abstained=false — evidence RETRIEVAL was treated as evidence
SUFFICIENCY.

Two deterministic gates (existing term conventions, no similarity
thresholds):
  gate 1  a TEXT passage supports a claim only if it shares >=1 query
          content term (dense-similarity noise never supports);
  gate 2  the union of ALL supporting surfaces must contain EVERY
          query content term, or the verdict is insufficient_evidence
          and the system abstains.

The seven required cases: (1) direct supported fact, (4) paraphrase
with real support, (5) relationship question with graph support,
(6) nonce with no support, (7) neighboring-topic without the answer.
Cases (2) supported procedure and (3) supported concept go through
/ask stored-object scoring, which requires term overlap by
construction (score > 0), and are qualified live in the transcript
scenario. QUERY_BACKEND_FAILED stays a typed HTTP 502 upstream of
synthesis (rerank_unavailable / graph backend tests).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.answer_synthesis import (  # noqa: E402
    ABSTENTION_MESSAGE,
    grounded_answer,
)
from polymath_shared.evidence_assembly import assemble_evidence_bundle  # noqa: E402

FACT = {
    "fact_id": "fact_adm_1", "predicate": "founded",
    "subject_id": "ent_adm_alice", "object_id": "ent_adm_acme",
    "qualifiers": {}, "decision": "ACCEPT",
    "rule_id": "founded-rule", "rule_version": "1.0.1",
    "provenance": {"roleset": "establish.01", "trigger_surface": "founded",
                   "semlink_resolved": True, "resource_contract_id": "x",
                   "compiled_lexical_sha256": "y", "orientation": "active",
                   "weak": False},
}
ENTITIES = {
    "ent_adm_alice": {"entity_id": "ent_adm_alice", "core_type": "PERSON",
                      "normalized_surface": "AliceSmith"},
    "ent_adm_acme": {"entity_id": "ent_adm_acme",
                     "core_type": "ORGANIZATION",
                     "normalized_surface": "AcmeCorp"},
}
EVIDENCE = {"fact_adm_1": [{
    "evidence_id": "ev_adm_1", "fact_id": "fact_adm_1", "doc_id": "doc_adm",
    "chunk_id": "chunk_adm_1", "span_offsets": {}, "rule_id": "founded-rule",
    "extractor_version": "1.0", "rule_version": "1.0.1"}]}
DOCUMENT = {"doc_id": "doc_adm", "corpus_id": "corpus_adm",
            "source_name": "adm.txt"}
CHUNKS = {
    "chunk_adm_1": {
        "chunk_id": "chunk_adm_1", "doc_id": "doc_adm",
        "text": "AliceSmith founded AcmeCorp.", "char_start": 0,
        "char_end": 27},
    "chunk_adm_para": {
        "chunk_id": "chunk_adm_para", "doc_id": "doc_adm",
        "text": ("Getting the company off the ground, AliceSmith founded "
                 "AcmeCorp in 2010 after leaving her research lab."),
        "char_start": 28, "char_end": 130},
    "chunk_adm_related": {
        "chunk_id": "chunk_adm_related", "doc_id": "doc_adm",
        "text": ("AliceSmith later wrote essays about leadership and "
                 "long walks in the mountains."),
        "char_start": 131, "char_end": 210},
}


def _bundle(query: str, graph_facts=None, child_chunk_ids=()):
    return assemble_evidence_bundle(
        query,
        graph_facts or [],
        [{"chunk_id": cid, "doc_id": "doc_adm", "parent_id": ""}
         for cid in child_chunk_ids],
        resolve_fact=lambda fid: FACT if fid == "fact_adm_1" else None,
        resolve_evidence=lambda fid: EVIDENCE.get(fid, []),
        resolve_entity=lambda eid: ENTITIES.get(eid),
        resolve_document=lambda did: DOCUMENT if did == "doc_adm" else None,
        resolve_chunk=lambda cid: CHUNKS.get(cid),
    )


GRAPH_FACT = {"fact_id": "fact_adm_1", "predicate": "founded",
              "subject": "AliceSmith", "object": "AcmeCorp"}


def test_case1_direct_supported_fact_answers():
    resp = grounded_answer(_bundle("who founded AcmeCorp",
                                   graph_facts=[GRAPH_FACT]),
                           "who founded AcmeCorp")
    assert resp["meta"]["verdict"] == "supported"
    assert resp["meta"]["abstained"] is False
    assert "AliceSmith founded AcmeCorp" in resp["answer"]


def test_case4_paraphrase_with_real_support_answers():
    query = "when did AliceSmith found AcmeCorp"
    resp = grounded_answer(
        _bundle(query, child_chunk_ids=["chunk_adm_para"]), query)
    assert resp["meta"]["verdict"] == "supported"
    assert resp["meta"]["abstained"] is False
    assert resp["citations"]


def test_case5_relationship_question_with_graph_support_answers():
    query = "which company did AliceSmith found"
    # coverage union: fact surfaces cover alicesmith + found(ed); the
    # paraphrase passage covers 'company'.
    resp = grounded_answer(
        _bundle(query, graph_facts=[GRAPH_FACT],
                child_chunk_ids=["chunk_adm_para"]), query)
    assert resp["meta"]["verdict"] == "supported"
    assert any(c.get("lane") == "graph"
               for c in resp["claims"] if c["status"] == "supported")


def test_case6_nonce_query_abstains():
    query = "what is glorbofex used for"
    resp = grounded_answer(
        _bundle(query, child_chunk_ids=["chunk_adm_1", "chunk_adm_para",
                                        "chunk_adm_related"]), query)
    assert resp["meta"]["verdict"] == "insufficient_evidence"
    assert resp["meta"]["abstained"] is True
    assert resp["answer"] == ABSTENTION_MESSAGE
    assert resp["meta"]["supported_claim_count"] == 0
    assert resp["citations"] == []


def test_case6b_partial_term_overlap_still_abstains():
    """The sharpened nonce: passages DO share a common term ('used'
    class) with the query, so gate 1 alone would answer — gate 2's
    full-coverage rule is what abstains, and the withheld claims stay
    visible in the ledger under an honest status."""
    query = "what did AliceSmith name the glorbofex"
    resp = grounded_answer(
        _bundle(query, child_chunk_ids=["chunk_adm_para"]), query)
    assert resp["meta"]["verdict"] == "insufficient_evidence"
    assert resp["meta"]["abstained"] is True
    assert "glorbofex" in resp["meta"]["uncovered_query_terms"]
    assert any(c["status"] == "withheld_insufficient_coverage"
               for c in resp["claims"])


def test_case7_neighboring_topic_abstains():
    """Corpus contains related information about the entity but not
    the asked-for answer."""
    query = "how much does AliceSmith charge for workshops"
    resp = grounded_answer(
        _bundle(query, child_chunk_ids=["chunk_adm_related"]), query)
    assert resp["meta"]["verdict"] == "insufficient_evidence"
    assert resp["meta"]["abstained"] is True
    assert set(resp["meta"]["uncovered_query_terms"]) >= {"charge", "workshops"}


def test_zero_overlap_passage_never_supports():
    """gate 1: a passage sharing no content term with the query is
    dense-retrieval noise; it is unsupported, not merely withheld."""
    query = "explain quantum entanglement decoherence"
    resp = grounded_answer(
        _bundle(query, child_chunk_ids=["chunk_adm_related"]), query)
    assert resp["meta"]["abstained"] is True
    assert all(c["status"] == "unsupported" for c in resp["claims"])
