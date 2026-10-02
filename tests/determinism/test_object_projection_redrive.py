"""OBJECT-PROJECTION-REDRIVE-V1 (measured live 2026-10-02, cinema): knowledge objects compiled AFTER a run's promotion
(compile_objects runs after verify and never blocks it) were never indexed — the census only re-checks runs that are not
yet query_ready — so cinema read SEMANTIC_INCOMPLETE with 119 procedures + 10 concepts and no work left to index them.
The control phase reopens ONE done project_qdrant ticket of such a corpus, unless a re-drive is in flight, the corpus's
projection ran within the cooldown, or the object's document is gone (the projector cannot index it). Real Postgres."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "control", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _pg_reachable() -> bool:
    import psycopg

    try:
        psycopg.connect(DSN, connect_timeout=3).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_reachable(), reason="postgres unavailable (make db-up)")

CORPUS = "objredrive_v1"
RUN, OTHER, DOC = "run_objredrive_1", "run_objredrive_2", "doc_objredrive_1"


@pytest.fixture()
def conn():
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as c:
        _cleanup(c)
        c.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, 'r', 'c')", (CORPUS,))
        for rid in (RUN, OTHER):
            c.execute("INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'query_ready')", (rid, CORPUS))
        c.execute("INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash) "
                  "VALUES (%s, %s, 'o.md', 'text/markdown', 10, 'hash-objredrive')", (DOC, CORPUS))
        c.execute("""INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status, updated_at)
                     VALUES ('tkt_objredrive_q', %s, %s, 'project_qdrant', 'project_qdrant.v1', 'done',
                             now() - interval '1 hour')""", (RUN, CORPUS))
        c.execute("INSERT INTO procedure_artifacts (procedure_id, document_id, corpus_id, title) "
                  "VALUES ('proc_objredrive_1', %s, %s, 'how to')", (DOC, CORPUS))
        try:
            yield c
        finally:
            _cleanup(c)


def _cleanup(c) -> None:
    c.execute("DELETE FROM projection_receipts WHERE entity_id LIKE 'proc_objredrive_%%'")
    c.execute("DELETE FROM procedure_artifacts WHERE corpus_id = %s", (CORPUS,))
    c.execute("DELETE FROM concept_artifacts WHERE corpus_id = %s", (CORPUS,))
    for rid in (RUN, OTHER):
        c.execute("DELETE FROM outbox_events WHERE run_id = %s", (rid,))
        c.execute("DELETE FROM stage_tickets WHERE run_id = %s", (rid,))
        c.execute("DELETE FROM runs WHERE run_id = %s", (rid,))
    c.execute("DELETE FROM documents WHERE doc_id = %s", (DOC,))
    c.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))


def _status(c) -> str:
    return c.execute("SELECT status FROM stage_tickets WHERE ticket_id = 'tkt_objredrive_q'").fetchone()[0]


def test_an_unindexed_object_of_a_promoted_corpus_reopens_one_projection(conn):
    from control.scheduler import redrive_unprojected_objects

    assert redrive_unprojected_objects(conn) >= 1
    assert _status(conn) == "ready"                                   # was: done forever (nothing re-checked it)
    ev = conn.execute("SELECT delivered_at FROM outbox_events WHERE run_id = %s AND event_type = 'project_qdrant.v1'",
                      (RUN,)).fetchall()
    assert ev and all(d is None for (d,) in ev)                        # the claim event is armed
    conn.execute("UPDATE stage_tickets SET status = 'done', updated_at = now() - interval '1 hour' "
                 "WHERE ticket_id = 'tkt_objredrive_q'")
    redrive_unprojected_objects(conn)                                  # idempotent: one event row, re-armed
    assert conn.execute("SELECT count(*) FROM outbox_events WHERE run_id = %s", (RUN,)).fetchone()[0] == 1


def test_nothing_is_reopened_when_indexed_in_flight_cooling_down_or_orphaned(conn):
    from control.scheduler import redrive_unprojected_objects

    conn.execute("""INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash, active)
                    VALUES ('qdrant', 'routing_procedure', 'proc_objredrive_1', 'h', TRUE)""")
    redrive_unprojected_objects(conn)
    assert _status(conn) == "done"                                     # indexed: nothing to do
    conn.execute("UPDATE projection_receipts SET active = FALSE WHERE entity_id = 'proc_objredrive_1'")

    conn.execute("""INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status)
                    VALUES ('tkt_objredrive_live', %s, %s, 'project_qdrant', 'project_qdrant.v1', 'ready')""",
                 (OTHER, CORPUS))
    redrive_unprojected_objects(conn)
    assert _status(conn) == "done"                                     # a re-drive is already in flight
    conn.execute("DELETE FROM stage_tickets WHERE ticket_id = 'tkt_objredrive_live'")

    conn.execute("UPDATE stage_tickets SET updated_at = now() - interval '2 minutes' WHERE ticket_id = 'tkt_objredrive_q'")
    redrive_unprojected_objects(conn)
    assert _status(conn) == "done"                                     # the projection ran within the cooldown
    conn.execute("UPDATE stage_tickets SET updated_at = now() - interval '1 hour' WHERE ticket_id = 'tkt_objredrive_q'")

    conn.execute("UPDATE procedure_artifacts SET document_id = 'doc_objredrive_gone' WHERE corpus_id = %s", (CORPUS,))
    redrive_unprojected_objects(conn)
    assert _status(conn) == "done"                                     # its document is gone: the projector cannot index it
