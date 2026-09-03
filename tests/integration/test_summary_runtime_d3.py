"""SUMMARY RUNTIME D3: document-summary worker against the live store."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "summary-d3-test"


def _seed_parent(conn, sid, text, ents, cpts):
    conn.execute(
        """INSERT INTO parent_summaries (summary_id, parent_id, corpus_id,
           artifact_hash, contract_version, created_by_worker, source_ids,
           entities, concepts, summary)
           VALUES (%s,%s,%s,%s,'admission-harbor-v2','w','{}',%s,%s,%s)""",
        (sid, "par_" + sid, CORPUS, "hash_" + sid, ents, cpts, text))


def _reset_corpus_tables():
    import psycopg

    with psycopg.connect(DSN) as c:
        for t in ("summary_artifacts", "document_summaries",
                  "parent_summaries", "corpus_summaries",
                  "summary_jobs"):
            c.execute("DELETE FROM " + t + " WHERE corpus_id=%s",
                      (CORPUS,))


def test_d3_lifecycle_lineage_and_idempotency():
    from polymath_shared.summary_runtime import run_document_summary_ticket
    ticket = "tkt_" + uuid.uuid4().hex
    ih = "in_" + uuid.uuid4().hex
    with psycopg.connect(DSN) as conn:
        p1, p2 = "ps_" + uuid.uuid4().hex[:8], "ps_" + uuid.uuid4().hex[:8]
        _seed_parent(conn, p1, "Transformer uses self-attention.",
                     ["Transformer"], ["self-attention"])
        _seed_parent(conn, p2, "BERT was trained on BooksCorpus.",
                     ["BERT", "BooksCorpus"], ["pretraining"])
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'DOCUMENT_SUMMARY',%s,%s,'admission-harbor-v2')""",
            (ticket, CORPUS, ih))

        r = run_document_summary_ticket(
            conn, ticket_id=ticket, corpus_id=CORPUS,
            document_id="doc_9", input_hash=ih,
            contract_version="admission-harbor-v2", worker_id="d3w",
            parent_summary_ids=[p1, p2], title="Attention 101",
            accepted_predicates=["uses", "trained_on"], event_count=1)
        assert r["status"] == "COMPLETE", r

        row = conn.execute(
            "SELECT major_entities, major_concepts, methods, summary "
            "FROM document_summaries WHERE document_id='doc_9'").fetchone()
        assert set(row[0]) >= {"Transformer", "BERT"}
        assert set(row[1]) >= {"self-attention", "pretraining"}
        assert set(row[2]) == {"uses", "trained_on"}
        assert "Attention 101 —" in row[3]

        state = conn.execute("SELECT state FROM summary_jobs "
                             "WHERE ticket_id=%s",
                             (ticket,)).fetchone()[0]
        assert state == "COMPLETE"

        # idempotency leg on a retried ticket
        # idempotency leg: a RETRIED ticket is the same content-addressed
        # ticket re-armed by the controller (P23 SUMMARY-IDEMPOTENCY-V1:
        # (stage, input_hash) is unique, so no second job row exists)
        conn.execute("UPDATE summary_jobs SET state='RETRY_WAIT' "
                     "WHERE ticket_id=%s", (ticket,))
        r2 = run_document_summary_ticket(
            conn, ticket_id=ticket, corpus_id=CORPUS,
            document_id="doc_9", input_hash=ih,
            contract_version="admission-harbor-v2", worker_id="d3w",
            parent_summary_ids=[p1, p2])
        assert r2["status"] == "EXISTING"
        n = conn.execute("SELECT count(*) FROM document_summaries "
                         "WHERE document_id='doc_9'").fetchone()[0]
        assert n == 1


def test_d3_fails_closed_on_missing_parent():
    from polymath_shared.summary_runtime import run_document_summary_ticket
    ticket = "tkt_" + uuid.uuid4().hex
    ih = "in_" + uuid.uuid4().hex
    with psycopg.connect(DSN) as conn:
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'DOCUMENT_SUMMARY',%s,%s,'admission-harbor-v2')""",
            (ticket, CORPUS, ih))
        r = run_document_summary_ticket(
            conn, ticket_id=ticket, corpus_id=CORPUS,
            document_id="doc_x", input_hash=ih,
            contract_version="admission-harbor-v2", worker_id="d3w",
            parent_summary_ids=["does_not_exist"])
        assert r["status"] == "FAILED" and "missing parent" in r["reason"]
        state = conn.execute("SELECT state FROM summary_jobs "
                             "WHERE ticket_id=%s",
                             (ticket,)).fetchone()[0]
        assert state == "FAILED"


def _cleanup():
    with psycopg.connect(DSN) as c:
        c.execute("DELETE FROM summary_artifacts WHERE "
                  "corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM document_summaries WHERE "
                  "corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM parent_summaries WHERE corpus_id=%s",
                  (CORPUS,))
        c.execute("DELETE FROM summary_jobs WHERE corpus_id=%s", (CORPUS,))
        c.commit()


@pytest.fixture(autouse=True)
def _isolated_corpus():
    _reset_corpus_tables()
    yield
