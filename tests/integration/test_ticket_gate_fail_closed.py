"""TICKET-GATE-FAIL-CLOSED-V1 — an outbox event with no ticket row is not
claimable; a READY ticket is. DB-backed, rolled back."""
from __future__ import annotations

import json
import pathlib
import sys

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.execution import worker_identity  # noqa: E402
from polymath_shared.worker_runtime import claim_ticket_events  # noqa: E402


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def test_event_without_ticket_is_not_claimable(conn) -> None:
    corpus, run = "gate-test-corpus", "run_gate_test_0001"
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, 'gate-test') ON CONFLICT DO NOTHING",
                 (corpus, corpus))
    conn.execute("INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', '{}')",
                 (run, corpus))
    conn.execute("""INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
                    VALUES (%s, 'profile_document.v1', %s, %s)""",
                 (run, json.dumps({"run_id": run}), "gate-test-key-1"))
    identity = worker_identity("profile_document")
    assert claim_ticket_events(conn, identity, ["profile_document.v1"], 10) == []

    conn.execute("""INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status)
                    VALUES ('tkt_gate_test', %s, %s, 'profile_document', 'profile_document.v1', 'pending')""",
                 (run, corpus))
    assert claim_ticket_events(conn, identity, ["profile_document.v1"], 10) == []

    conn.execute("UPDATE stage_tickets SET status='ready' WHERE ticket_id='tkt_gate_test'")
    claimed = claim_ticket_events(conn, identity, ["profile_document.v1"], 10)
    assert [e["run_id"] for e in claimed] == [run]
