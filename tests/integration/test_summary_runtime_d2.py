"""SUMMARY RUNTIME D2: parent-summary worker against the live store.

Covers: claim, idempotency gate (same input -> EXISTING), COMPLETE
transition, artifact + summary rows durable.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
WORKER = "d2-test-worker"


def _run_ticket(conn, ticket_id, input_hash):
    from polymath_shared.summary_runtime import run_parent_summary_ticket
    return run_parent_summary_ticket(
        conn, ticket_id=ticket_id, corpus_id="summary-d1-test",
        parent_id="par_001", input_hash=input_hash,
        contract_version="admission-harbor-v2", worker_id=WORKER,
        parent_text="The encoder uses self-attention layers.",
        children=[{"id": "ch_1",
                   "text": "The encoder uses self-attention layers."}],
        facts=[{"predicate": "uses", "subject_surface": "encoder",
                "object_surface": "self-attention"}],
        entities=[{"surface": "encoder", "core_type": "Component"}],
        source_ids=["ch_1"])


def test_lifecycle_and_idempotency():
    ticket = "tkt_" + uuid.uuid4().hex
    input_hash = "in_" + uuid.uuid4().hex
    with psycopg.connect(DSN) as conn:
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'PARENT_SUMMARY','summary-d1-test',%s,
            'admission-harbor-v2')""", (ticket, input_hash))
        r1 = _run_ticket(conn, ticket, input_hash)
        assert r1["status"] == "COMPLETE", r1
        state = conn.execute("SELECT state FROM summary_jobs "
                             "WHERE ticket_id=%s", (ticket,)).fetchone()[0]
        assert state == "COMPLETE"
        n_rows = conn.execute("SELECT count(*) FROM parent_summaries "
                              "WHERE corpus_id='summary-d1-test'"
                              ).fetchone()[0]
        assert n_rows == 1

        # same input again -> EXISTING, no duplicate artifact
        # (a retried attempt arrives on its OWN ticket)
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'PARENT_SUMMARY','summary-d1-test',%s,
            'admission-harbor-v2')""", (ticket + "_b", input_hash))
        r2 = _run_ticket(conn, ticket + "_b", input_hash)
        assert r2["status"] == "EXISTING"
        n_after = conn.execute("SELECT count(*) FROM parent_summaries "
                               "WHERE corpus_id='summary-d1-test'"
                               ).fetchone()[0]
        assert n_after == 1
        arts = conn.execute("SELECT count(*) FROM summary_artifacts "
                            "WHERE corpus_id='summary-d1-test'"
                            ).fetchone()[0]
        assert arts == 1

        # cleanup test rows
        for tbl in ("summary_artifacts", "parent_summaries"):
            conn.execute(f"DELETE FROM {tbl} WHERE "
                         "corpus_id='summary-d1-test'")
        conn.execute("DELETE FROM summary_jobs WHERE "
                     "corpus_id='summary-d1-test'")
        conn.commit()
