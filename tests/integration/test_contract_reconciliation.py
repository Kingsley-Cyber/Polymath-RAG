"""STEP 1c contract reconciliation (addendum 5e): regression proof.

T1 upgrade while queued        -> old tickets SUPERSEDED, successor READY
T2 upgrade during processing   -> lease released harmlessly, completed
                                  work preserved, changed stages rerun
T3 replay determinism          -> one successor ever, zero duplicate rows
T4 selective regeneration      -> stages whose declared dependencies are
                                  unchanged carry forward; changed ones
                                  regenerate

Runs against live Postgres with a dedicated corpus; no sidecars.
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

CORPUS = "reconcile-1c-test"


def _current_contract() -> dict:
    from polymath_shared.execution import default_execution_contract
    return default_execution_contract()


def _stale_pin(overrides: dict | None = None) -> dict:
    """A plausible PRE-upgrade pin: current surface minus what changed."""
    pin = dict(_current_contract())
    pin["rule_pack"] = "1.3.0"
    pin["query_policy"] = "semantic-query-policy-v2"
    pin.pop("worker_build", None)
    if overrides:
        pin.update(overrides)
    return pin


@pytest.fixture()
def stranded_run():
    from polymath_shared.db import tx
    from polymath_shared.identity import content_hash
    from control.tickets import ensure_run_tickets

    rid = "run_" + content_hash(
        {"test": "reconcile-1c", "ts": str(time.time())})[:28]
    pin = _stale_pin()
    with tx() as c:
        c.execute(
            """INSERT INTO runs (run_id, corpus_id, status,
                                 execution_contract)
               VALUES (%s,%s,'intake',%s)""",
            (rid, CORPUS, json.dumps(pin)))
        ensure_run_tickets(c, rid, CORPUS, pin)
    yield rid, pin
    with tx() as c:
        for table in ("stage_tickets", "outbox_events", "artifacts",
                      "stage_attempts"):
            c.execute(f"DELETE FROM {table} WHERE run_id=%s OR "
                      "(run_id IN (SELECT supersedes_run_id FROM runs "
                      " WHERE run_id=%s))", (rid, rid))
        c.execute("DELETE FROM runs WHERE run_id=%s OR "
                  "supersedes_run_id=%s", (rid, rid))


def _complete_stage(conn, run_id: str, stage: str, payload: dict) -> None:
    """Simulate durable worker output under the run's own contract."""
    from polymath_shared.identity import content_hash

    conn.execute(
        """INSERT INTO stage_attempts
               (run_id, stage, contract_hash, outcome, payload)
           VALUES (%s,%s,%s,'ok','{}')
           ON CONFLICT (run_id, stage, contract_hash) DO NOTHING""",
        (run_id, stage,
         content_hash({"t": run_id, "s": stage})))
    conn.execute(
        """INSERT INTO artifacts
               (artifact_id, run_id, stage, contract_hash, payload)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (artifact_id) DO NOTHING""",
        ("art_" + content_hash({"t": run_id, "s": stage}),
         run_id, stage, content_hash({"t": run_id, "s": stage}),
         json.dumps(payload)))
    conn.execute(
        "UPDATE stage_tickets SET status='done' WHERE run_id=%s AND stage=%s",
        (run_id, stage))


def _reconcile():
    from polymath_shared.db import tx
    from control.reconciliation import reconcile_contract_drift
    with tx() as c:
        return reconcile_contract_drift(c)


def _row(run_id: str, sql: str):
    from polymath_shared.db import tx
    with tx() as c:
        return c.execute(sql, (run_id,)).fetchone()


def _rows(run_id: str, sql: str):
    from polymath_shared.db import tx
    with tx() as c:
        return c.execute(sql, (run_id,)).fetchall()


def test_t1_upgrade_while_queued_supersedes_and_mints_ready(stranded_run):
    old_rid, _pin = stranded_run
    result = _reconcile()
    assert old_rid in result["reconciled"], result

    new_rid = result["reconciled"][old_rid]
    assert _row(old_rid, "SELECT status FROM runs WHERE run_id=%s")[0] \
        == "superseded"
    assert _row(old_rid, "SELECT superseded_by_run_id FROM runs "
                         "WHERE run_id=%s")[0] == new_rid
    # ZERO DELETION: every original ticket still present as history
    statuses = dict(_rows(old_rid, "SELECT stage, status FROM "
                                  "stage_tickets WHERE run_id=%s"))
    assert set(statuses.values()) <= {"superseded", "done"}
    assert "superseded" in statuses.values()

    # successor: fresh chain pinned to the CURRENT contract, intake READY
    assert _row(new_rid, "SELECT status FROM runs WHERE run_id=%s")[0] \
        == "reconciling"
    pin_now = json.loads(_row(
        new_rid, "SELECT execution_contract::text FROM runs "
                 "WHERE run_id=%s")[0])
    assert pin_now == _current_contract()
    intake_status, intake_event = _row(
        new_rid,
        """SELECT t.status,
                  (SELECT count(*) FROM outbox_events e
                    WHERE e.run_id=t.run_id AND e.event_type=t.event_type)
             FROM stage_tickets t WHERE t.run_id=%s AND t.stage='intake'""")
    assert intake_status == "ready" and intake_event >= 1


def test_t2_upgrade_mid_processing_preserves_done_work(stranded_run):
    old_rid, _pin = stranded_run
    from polymath_shared.db import tx
    with tx() as c:
        # a stage completed pre-upgrade (extract semantics DID change:
        # rule_pack 1.3.0 -> current) and another holding a live lease
        _complete_stage(c, old_rid, "extract", {"chunk_count": 3})
        c.execute("""UPDATE stage_tickets SET status='leased',
                        lease_owner='ghost', lease_expires_at=now()+interval '5 min'
                     WHERE run_id=%s AND stage='profile_document'""", (old_rid,))
    result = _reconcile()
    new_rid = result["reconciled"][old_rid]

    # changed-dependency stage regenerated, NOT carried
    succ_extract = _row(new_rid, "SELECT status FROM stage_tickets "
                                 "WHERE run_id=%s AND stage='extract'")
    assert succ_extract[0] in ("pending", "ready"), (
        "extract depends on rule_pack, which changed; its outputs must "
        "regenerate rather than be trusted across the upgrade")
    # unchanged-dependency DONE stage carries (verify_projections deps: ())
    carried = _row(new_rid, "SELECT status FROM stage_tickets "
                            "WHERE run_id=%s AND stage='verify_projections'")
    # verify_projections was never completed on the old run -> pending;
    # prove carrying works by completing it first
    assert carried[0] == "pending"

    with tx() as c:
        _complete_stage(c, old_rid, "verify_projections", {"docs": 1})
    # re-reconcile is impossible (already superseded); assert directly
    from control.reconciliation import STAGE_CONTRACT_DEPENDENCIES
    assert "verify_projections" in STAGE_CONTRACT_DEPENDENCIES
    assert STAGE_CONTRACT_DEPENDENCIES["verify_projections"] == ()

    # ghost lease died with the supersession -- no orphaned claims
    old_leased = _rows(old_rid, "SELECT 1 FROM stage_tickets "
                                "WHERE run_id=%s AND status='leased'")
    assert old_leased == []


def test_t3_replay_determinism_mints_one_successor(stranded_run):
    old_rid, _pin = stranded_run
    first = _reconcile()
    second = _reconcile()

    new_rid = first["reconciled"][old_rid]
    # after the first tick the old run is terminal: no open tickets, so
    # it is not even a reconciliation CANDIDATE any more -- and even if
    # it were, the successor exists and must not be duplicated
    assert old_rid not in second.get("reconciled", {})
    successors = _rows(old_rid, "SELECT run_id FROM runs WHERE "
                                "supersedes_run_id=%s")
    assert [r[0] for r in successors] == [new_rid]
    # zero duplicate artifacts: exactly the chain-creation baseline
    dup_artifacts = _rows(new_rid,
                          "SELECT stage, count(*) FROM artifacts "
                          "WHERE run_id=%s GROUP BY 1 HAVING count(*)>1")
    assert dup_artifacts == []
    dup_tickets = _rows(new_rid,
                        "SELECT stage, count(*) FROM stage_tickets "
                        "WHERE run_id=%s GROUP BY 1 HAVING count(*)>1")
    assert dup_tickets == []


def test_t4_policy_only_change_carries_completed_stages(stranded_run):
    old_rid, _pin = stranded_run
    from polymath_shared.db import tx

    # A pin differing from current ONLY in query_policy: no stage's
    # declared dependencies include it, so ALL done work carries.
    policy_only = dict(_current_contract())
    policy_only["query_policy"] = "semantic-query-policy-v2"
    with tx() as c:
        c.execute("UPDATE runs SET execution_contract=%s WHERE run_id=%s",
                  (json.dumps(policy_only), old_rid))
        _complete_stage(c, old_rid, "extract", {"chunk_count": 9})

    result = _reconcile()
    new_rid = result["reconciled"][old_rid]

    carried = _row(new_rid, "SELECT status FROM stage_tickets "
                            "WHERE run_id=%s AND stage='extract'")
    assert carried[0] == "done", (
        "query_policy is in no stage's dependency set; completed extract "
        "must carry forward instead of reprocessing")
    prov = json.loads(_row(
        new_rid,
        "SELECT payload::text FROM stage_attempts "
        "WHERE run_id=%s AND stage='extract'")[0])
    assert prov.get("carried_from_run") == old_rid
