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

        # SUMMARY-IDEMPOTENCY-V1 (P23): a second ticket for the SAME
        # logical work is refused by the database, not merely
        # discouraged. This block previously did the opposite — it
        # inserted a second ticket and commented that "a retried attempt
        # arrives on its OWN ticket", which is exactly how 21,315
        # tickets accumulated for 3,025 distinct input_hash values.
        import psycopg.errors as _pgerr

        # A SAVEPOINT, not a rollback: the whole test runs in one
        # transaction, so rolling back would also undo the completed
        # run we are about to assert on.
        with conn.transaction(force_rollback=True):
            try:
                conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
                    corpus_id, input_hash, contract_version)
                    VALUES (%s,'PARENT_SUMMARY','summary-d1-test',%s,
                    'admission-harbor-v2')""", (ticket + "_b", input_hash))
            except _pgerr.UniqueViolation:
                refused = True
            else:
                refused = False
        assert refused, (
            "a second ticket for the same (stage, input_hash) was "
            "accepted — the control plane can re-execute settled work")

        # a retry is an ATTEMPT on the existing job, never a new job
        conn.execute("""INSERT INTO summary_jobs (ticket_id, stage,
            corpus_id, input_hash, contract_version)
            VALUES (%s,'PARENT_SUMMARY','summary-d1-test',%s,
            'admission-harbor-v2')
            ON CONFLICT (stage, input_hash) DO UPDATE
               SET attempts = summary_jobs.attempts + 1""",
            (ticket + "_b", input_hash))
        jobs, attempts = conn.execute(
            "SELECT count(*), max(attempts) FROM summary_jobs "
            "WHERE stage='PARENT_SUMMARY' AND input_hash=%s",
            (input_hash,)).fetchone()
        assert jobs == 1, f"{jobs} jobs exist for one logical unit of work"
        assert attempts >= 1, "the retry was not recorded as an attempt"

        # Re-running settled work is a no-op. The status is now
        # SKIPPED_NOT_CLAIMABLE rather than EXISTING, because a second
        # ticket can no longer be created to carry the retry — the
        # settled job itself is simply not claimable again. Both mean
        # "no duplicate work"; what matters is the row counts below.
        r2 = _run_ticket(conn, ticket, input_hash)
        assert r2["status"] in ("EXISTING", "SKIPPED_NOT_CLAIMABLE"), r2
        n_after = conn.execute("SELECT count(*) FROM parent_summaries "
                               "WHERE corpus_id='summary-d1-test'"
                               ).fetchone()[0]
        assert n_after == 1
        live = conn.execute("SELECT count(*) FROM parent_summaries "
                            "WHERE corpus_id='summary-d1-test' "
                            "AND superseded_at IS NULL").fetchone()[0]
        assert live == 1, "more than one authoritative summary for a parent"
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
