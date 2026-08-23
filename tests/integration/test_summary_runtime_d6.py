"""SUMMARY RUNTIME D6: hardening — determinism, drift, contamination."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.corpus_mapping import build_corpus_map  # noqa: E402
from polymath_shared.parent_summary import build_parent_summary  # noqa: E402
from polymath_shared.summary_layer import validate_envelope  # noqa: E402
from polymath_shared.summary_workers import (  # noqa: E402
    build_document_summary,
)
from polymath_shared.vocabulary_mapping import (  # noqa: E402
    admit_family,
    build_concept_families,
)

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


def _parent(payload_summary):
    return {"payload": {"parent_id": "par_1", "entities": ["BERT"],
                        "concepts": ["pretraining"],
                        "summary": payload_summary}}


def _doc(parents):
    return build_document_summary(document_id="d1", title="T",
                                  parent_summaries=parents)


def test_rebuild_determinism_same_inputs_same_hashes():
    a = build_parent_summary(
        parent_id="p", parent_text="The encoder uses self-attention.",
        children=[{"id": "c1",
                   "text": "The encoder uses self-attention."}],
        facts=[{"predicate": "uses", "subject_surface": "encoder",
                "object_surface": "self-attention"}],
        entities=[{"surface": "encoder", "core_type": "Component"}])
    b = build_parent_summary(
        parent_id="p", parent_text="The encoder uses self-attention.",
        children=[{"id": "c1",
                   "text": "The encoder uses self-attention."}],
        facts=[{"predicate": "uses", "subject_surface": "encoder",
                "object_surface": "self-attention"}],
        entities=[{"surface": "encoder", "core_type": "Component"}])
    assert a["output_hash"] == b["output_hash"]

    rows = [{"summary_id": "s1", "major_entities": ["BERT"],
             "major_concepts": ["pretraining"], "methods":
             ["trained_on"]}]
    m1 = build_corpus_map(corpus_id="c", document_summaries=rows)
    m2 = build_corpus_map(corpus_id="c", document_summaries=list(rows))
    from polymath_shared.identity import content_hash
    assert content_hash(m1) == content_hash(m2)


def test_drift_invalidates_only_dependent_summaries():
    d_a1 = _doc([_parent("version one")])
    d_a2 = _doc([_parent("version two")])
    d_b1 = _doc([_parent("unrelated sibling")])
    d_b2 = _doc([_parent("unrelated sibling")])
    assert d_a1["output_hash"] != d_a2["output_hash"], \
        "changed parent must invalidate its dependent document summary"
    assert d_b1["output_hash"] == d_b2["output_hash"], \
        "unrelated documents must not invalidate"


def test_vocabulary_contamination_two_corpora_two_families():
    ai = build_concept_families(
        corpus_id="ai_v1",
        parent_summaries=[{"payload": {"parent_id": "p1",
                                       "concepts": ["model"]}}],
        document_summaries=[], accepted_concepts=[])
    cyber = build_concept_families(
        corpus_id="cyber_v1",
        parent_summaries=[{"payload": {"parent_id": "p1",
                                       "concepts": ["model"]}}],
        document_summaries=[], accepted_concepts=[])
    assert len(ai["families"]) == 1 and len(cyber["families"]) == 1
    ok_ai, _ = admit_family(ai["families"][0], corpus_id="ai_v1")
    ok_cy, _ = admit_family(cyber["families"][0], corpus_id="cyber_v1")
    assert ok_ai and ok_cy
    cross, reason = admit_family(ai["families"][0], corpus_id="cyber_v1")
    assert not cross and reason == "R1_corpus_isolation"
    # no global vocabulary pollution: separate canonical spaces
    assert (ai["families"][0]["corpus_id"]
            != cyber["families"][0]["corpus_id"])


def test_failure_lifecycle_bounded_then_dead_letter():
    import psycopg

    from polymath_shared.summary_runtime import (
        MAX_ATTEMPTS, backoff_seconds, fail_ticket)
    assert MAX_ATTEMPTS == 5
    assert backoff_seconds(1) == 8 and backoff_seconds(2) == 16
    assert backoff_seconds(10) == 600

    ticket = "tkt_" + uuid.uuid4().hex
    with psycopg.connect(DSN) as conn:
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'PARENT_SUMMARY','summary-d6-test',%s,'v')""",
            (ticket, "in_" + uuid.uuid4().hex))
        states = []
        for attempt in range(MAX_ATTEMPTS):
            states.append(fail_ticket(conn, ticket, attempt))
        final = conn.execute("SELECT state, attempts FROM summary_jobs "
                             "WHERE ticket_id=%s",
                             (ticket,)).fetchone()
        conn.execute("DELETE FROM summary_jobs WHERE ticket_id=%s",
                     (ticket,))
        conn.commit()
    assert states[:4] == ["RETRY_WAIT"] * 4
    assert final[0] == "FAILED_PERMANENT" and final[1] == 5
