"""CONTROL-PLANE-V2 integration: ticket machinery over live Postgres.

Proves the four targets end-to-end at the machinery level: explicit
handoff (event exists only after verified predecessor), compatibility
leasing (incompatible worker refused), generation barrier, snapshot
acquire/validate/abort-on-drift. Uses a fake stage processor and a
dedicated corpus; no sidecars needed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="set POLYMATH_INTEGRATION=1 with live stores",
)

CORPUS = "cp2-ticket-test"


@pytest.fixture()
def run_env():
    from polymath_shared.db import tx
    from polymath_shared.identity import content_hash
    from control.tickets import ensure_run_tickets

    run_id = "run_" + content_hash({"test": "cp2", "ts": str(time.time())})[:28]
    with tx() as c:
        c.execute(
            "INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'intake') "
            "ON CONFLICT DO NOTHING", (run_id, CORPUS))
        contract = {"worker_build": "cptest", "query_policy": "semantic-query-policy-v1",}
        ensure_run_tickets(c, run_id, CORPUS, contract)
    yield run_id, contract
    with tx() as c:
        c.execute("DELETE FROM stage_tickets WHERE corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM outbox_events WHERE run_id=%s", (run_id,))
        c.execute("DELETE FROM artifacts WHERE run_id=%s", (run_id,))
        c.execute("DELETE FROM stage_attempts WHERE run_id=%s", (run_id,))
        c.execute("DELETE FROM runs WHERE run_id=%s", (run_id,))
        c.execute("DELETE FROM corpus_snapshots WHERE corpus_id=%s", (CORPUS,))


def _complete_stage(conn, run_id, stage, artifacts: dict):
    """Simulate a worker's durable output: attempt ok + merged artifact."""
    conn.execute(
        """
        INSERT INTO stage_attempts (run_id, stage, contract_hash, outcome, completed_at)
        VALUES (%s, %s, 'cp2-test', 'ok', now())
        ON CONFLICT (run_id, stage, contract_hash) DO UPDATE
        SET outcome = 'ok', completed_at = now()
        """,
        (run_id, stage))
    conn.execute(
        """
        INSERT INTO artifacts (artifact_id, run_id, stage, contract_hash, payload)
        VALUES (%s, %s, %s, 'cp2-test', %s)
        ON CONFLICT (run_id, stage, contract_hash) DO UPDATE
        SET payload = artifacts.payload || EXCLUDED.payload
        """,
        (f"art_{run_id[:16]}_{stage}", run_id, stage, json.dumps(artifacts)))


def test_ticket_chain_explicit_handoff_and_barrier(run_env):
    from polymath_shared.db import tx
    from polymath_shared.worker_runtime import claim_ticket_events, complete_ticket
    from control.tickets import advance_tickets, generation_barrier

    run_id, contract = run_env
    identity = {"worker_id": "w-cp2-1", "worker_type": "intake",
                "contracts": {"build_sha": "cptest",
                              "query_policy": "semantic-query-policy-v1"}}

    # intake ticket born ready: its event is claimable immediately
    with tx() as c:
        events = claim_ticket_events(c, identity, ["intake.v1"], 4)
    assert any(e["run_id"] == run_id for e in events)
    with tx() as c:
        _complete_stage(c, run_id, "intake", {})
        complete_ticket(c, next(e["ticket_id"] for e in events if e["run_id"] == run_id))

    # extract ticket NOT ready until intake verified + advanced
    with tx() as c:
        events = claim_ticket_events(c, identity, ["chunked.v1"], 4)
    assert not any(e["run_id"] == run_id for e in events)

    with tx() as c:
        advance_tickets(c)
    with tx() as c:
        events = claim_ticket_events(c, identity, ["chunked.v1"], 4)
    assert any(e["run_id"] == run_id for e in events), "advance must emit the verified handoff"

    # barrier: open tickets block promotion
    with tx() as c:
        verdict = generation_barrier(c, CORPUS)
    assert verdict["open_tickets"] > 0 and not verdict["passed"]

    # finish the whole chain
    with tx() as c:
        for e in events:
            if e["run_id"] == run_id:
                complete_ticket(c, e["ticket_id"])
                _complete_stage(c, run_id, "extract", {"manifest": {}})
        for stage, arts in [
            ("profile_document", {"documents_profiled": 1}),
            ("project_qdrant", {"chunk_count": 0}),
            ("project_neo4j", {"facts": []}),
            ("canonicalize", {"canonical_entities": []}),
            ("project_canonical", {"memberships": []}),
            ("verify_projections", {"docs": []}),
        ]:
            advance_tickets(c)
            evs = claim_ticket_events(c, identity, [_event_of(stage)], 4)
            mine = [e for e in evs if e["run_id"] == run_id]
            assert mine, f"{stage} ticket must become ready+claimable after advance"
            for e in mine:
                _complete_stage(c, run_id, stage, arts)
                complete_ticket(c, e["ticket_id"])

    with tx() as c:
        verdict = generation_barrier(c, CORPUS)
    assert verdict["passed"], verdict


def test_incompatible_worker_is_refused_the_lease(run_env):
    from polymath_shared.db import tx
    from polymath_shared.worker_runtime import claim_ticket_events

    run_id, _contract = run_env
    stale = {"worker_id": "w-cp2-stale", "worker_type": "intake",
             "contracts": {"build_sha": "OLD", "query_policy": "semantic-query-policy-v1",}}
    with tx() as c:
        events = claim_ticket_events(c, stale, ["intake.v1"], 4)
    assert not any(e["run_id"] == run_id for e in events), \
        "worker with wrong build must NOT lease the run's work"

    with tx() as c:
        row = c.execute(
            "SELECT status FROM stage_tickets WHERE run_id=%s AND stage='intake'",
            (run_id,)).fetchone()
    assert row[0] == "ready"  # ticket untouched by the refused lease


def test_snapshot_barrier_aborts_on_drift(run_env):
    from polymath_shared.db import tx
    from control.snapshots import acquire_snapshot, corpus_state_hash, validate_snapshot

    run_id, _contract = run_env
    with tx() as c:
        c.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (run_id,))
        from control.tickets import ensure_run_tickets
        # mark every ticket done so the barrier passes
        c.execute("UPDATE stage_tickets SET status='done' WHERE run_id=%s", (run_id,))
        snapshot_id = acquire_snapshot(c, CORPUS)
    with tx() as c:
        validate_snapshot(c, snapshot_id)  # stable -> OK

    # drift: touch authoritative state
    with tx() as c:
        c.execute("UPDATE runs SET status='reconciling' WHERE run_id=%s", (run_id,))
    with pytest.raises(RuntimeError, match="ABORT"):
        with tx() as c:
            validate_snapshot(c, snapshot_id)
    with tx() as c:
        row = c.execute("SELECT valid FROM corpus_snapshots WHERE snapshot_id=%s",
                        (snapshot_id,)).fetchone()
    assert row[0] is False


def _event_of(stage: str) -> str:
    from control.tickets import _STAGE_SPEC
    return _STAGE_SPEC[stage][0]
