"""CONTROL-TICK-SIDE-STAGE-GUARD-V1 — a PENDING ticket for a stage outside STAGE_DAG
(doc_parent_map, parent_enrichment: minted READY by their own triggers, never chain-advanced)
must never kill the control tick. Measured 2026-09-11 23:53 → 09-13: `_try_advance_one` did
`DAG_ORDER.index(stage)` on such a ticket → ValueError → every tick failed (10,191 times), no
corpus advanced, the supervisor restarted control every 180 s. Real Postgres, rolled back."""
from __future__ import annotations

import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "control", ROOT / "shared"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import control.tickets as T  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


class _NoDb:
    """A connection that proves the guard returns BEFORE any query."""
    def execute(self, *a, **k):  # pragma: no cover - reached only on regression
        raise AssertionError("side-stage guard must not touch the database")


def test_side_stages_are_outside_the_dag_by_design():
    for stage in ("doc_parent_map", "parent_enrichment"):
        assert stage not in T.DAG_ORDER and stage not in T._STAGE_SPEC
        assert stage in T.NON_BLOCKING_STAGES


def test_try_advance_one_skips_a_side_stage_without_raising_or_querying():
    for stage in ("doc_parent_map", "parent_enrichment", "never_a_stage"):
        assert T._try_advance_one(_NoDb(), "tkt_probe", "run_probe", stage) is False
    # a DAG stage still goes to the database (the guard is the ONLY difference)
    with pytest.raises(AssertionError):
        T._try_advance_one(_NoDb(), "tkt_probe", "run_probe", "extract")


@pytest.fixture()
def conn():
    """Real Postgres. `_eligible_all_stages` COMMITS when its keyset wraps, so a rollback cannot
    undo this test's rows — every probe row is deleted explicitly (by its unique prefix) instead."""
    try:
        c = psycopg.connect(DSN, autocommit=False, connect_timeout=3)
    except Exception as exc:  # pragma: no cover - environment gate
        pytest.skip(f"postgres unavailable: {exc}")
    probes: list[str] = []
    c.probes = probes  # type: ignore[attr-defined]
    try:
        yield c
    finally:
        c.rollback()
        for corpus in probes:
            c.execute("DELETE FROM outbox_events WHERE run_id IN (SELECT run_id FROM runs WHERE corpus_id=%s)", (corpus,))
            c.execute("DELETE FROM stage_tickets WHERE corpus_id=%s", (corpus,))
            c.execute("DELETE FROM scheduler_cursors WHERE corpus_id=%s", (corpus,))
            c.execute("DELETE FROM runs WHERE corpus_id=%s", (corpus,))
            c.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
        c.commit()
        c.close()


def test_advance_survives_a_pending_side_stage_ticket(conn):
    """The exact production shape: a corpus whose only pending ticket is a doc_parent_map ticket
    (the forensic-hold pause). Advancement completes, the ticket stays pending (never emitted),
    nothing raises."""
    corpus = "probe-ssg-" + uuid.uuid4().hex[:8]
    conn.probes.append(corpus)
    rid = "run_probe_" + uuid.uuid4().hex[:16]
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'p','probe')", (corpus, corpus))
    conn.execute("INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s,%s,'reconciling','{}'::jsonb)", (rid, corpus))
    tid = "tkt_probe_" + uuid.uuid4().hex[:16]
    conn.execute("""INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status)
                    VALUES (%s,%s,%s,'doc_parent_map','doc_parent_map.v1','pending')""", (tid, rid, corpus))
    advanced = T._advance_pending_corpus(conn, corpus, {"qdrant": set(), "neo4j": set()})
    assert advanced == 0
    row = conn.execute("SELECT status FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone()
    assert row[0] == "pending"                                   # skipped, not advanced, not archived
    assert conn.execute("SELECT COUNT(*) FROM outbox_events WHERE run_id=%s", (rid,)).fetchone()[0] == 0
