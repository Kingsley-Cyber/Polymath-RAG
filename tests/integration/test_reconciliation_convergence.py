"""RECONCILIATION-CONVERGENCE-E2E (roadmap A1) — DB-backed, rolled back.

The acceptance the 2026-08-31 outage demanded: a completed run pinned to
a STALE contract, holding open work, must — through reconcile → carry →
census → promotion — reach query_ready on a SUCCESSOR run with NO manual
re-pin, NO ticket surgery. The manual restoration that night (parked
successors, re-pinned originals, restored tickets) is exactly what this
test makes impossible to need again.

Also regression-pins the census-killer: a DAG-less owner-triggered
ticket (parent_enrichment) in ready state must not break advancement.
"""
from __future__ import annotations

import json
import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.execution import default_execution_contract  # noqa: E402
from control.census import STAGE_CHAIN, compute_census  # noqa: E402
from control.reconciliation import reconcile_contract_drift  # noqa: E402
from control.scheduler import apply_promotions  # noqa: E402
from control.tickets import advance_tickets  # noqa: E402


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _mk_completed_run(conn, tag: str, pin: dict) -> tuple[str, str]:
    """A run whose whole STAGE_CHAIN succeeded under `pin`, currently
    'reconciling' with ONE re-armed (open) ticket — the exact live shape
    after a latent re-projection on an old run."""
    corpus = f"reconv-{tag}"
    run = f"run_reconv_{tag}"
    conn.execute(
        "INSERT INTO corpora (corpus_id, name, config_hash) "
        "VALUES (%s,%s,'reconv') ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata, "
        "execution_contract) VALUES (%s,%s,'reconciling','{}',%s)",
        (run, corpus, json.dumps(pin, sort_keys=True)))
    for i, stage in enumerate(STAGE_CHAIN):
        conn.execute(
            "INSERT INTO stage_attempts (run_id, stage, contract_hash, "
            "started_at, completed_at, outcome, payload) "
            "VALUES (%s,%s,%s,now(),now(),'ok','{}')",
            (run, stage, f"h_{tag}_{stage}"))
        conn.execute(
            "INSERT INTO artifacts (artifact_id, run_id, stage, "
            "contract_hash, payload) VALUES (%s,%s,%s,%s,%s)",
            (f"art_rc_{tag}_{stage}", run, stage, f"h_{tag}_{stage}",
             json.dumps({"carried_test": tag})))
        conn.execute(
            "INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, "
            "stage, event_type, status) VALUES (%s,%s,%s,%s,%s,%s)",
            (f"tkt_rc_{tag}_{i}", run, corpus, stage,
             {"intake": "intake.v1", "extract": "chunked.v1",
              "profile_document": "profile_document.v1",
              "project_qdrant": "project_qdrant.v1",
              "project_neo4j": "project_neo4j.v1",
              "canonicalize": "canonicalize.v1",
              "project_canonical": "project_canonical.v1",
              "verify_projections": "verify.v1"}[stage],
             # the re-armed open ticket that makes the run "stranded"
             "ready" if stage == "project_qdrant" else "done"))
    conn.execute(
        "INSERT INTO outbox_events (run_id, event_type, payload, "
        "idempotency_key) VALUES (%s,'intake.v1',%s,%s)",
        (run, json.dumps({"run_id": run, "corpus_id": corpus,
                          "content_ref": "spool://reconv"}),
         f"reconv-intake-{tag}"))
    return corpus, run


def test_contract_drift_converges_without_manual_repin(conn) -> None:
    tag = uuid.uuid4().hex[:8]
    current = default_execution_contract()
    # a pin differing ONLY in a key no stage depends on: everything
    # carries, nothing regenerates — pure lineage mechanics under test
    old_pin = dict(current)
    old_pin["query_policy"] = "reconv-test-old-policy"
    corpus, old_run = _mk_completed_run(conn, tag, old_pin)

    # census-killer regression: a DAG-less owner ticket sits ready with
    # its event delivered — advancement must survive it
    conn.execute(
        "INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, "
        "event_type, status) VALUES (%s,%s,%s,'parent_enrichment',"
        "'parent_enrichment.v1','ready')",
        (f"tkt_rc_enr_{tag}", old_run, corpus))

    out = reconcile_contract_drift(conn)
    assert old_run in out["reconciled"], out
    successor = out["reconciled"][old_run]

    # old run retired, successor pinned to the CURRENT contract
    row = conn.execute(
        "SELECT status, superseded_by_run_id FROM runs WHERE run_id=%s",
        (old_run,)).fetchone()
    assert row == ("superseded", successor)
    pin = conn.execute(
        "SELECT execution_contract::text FROM runs WHERE run_id=%s",
        (successor,)).fetchone()[0]
    assert json.loads(pin) == current          # no manual re-pin needed

    # carried: every TRULY-DONE chain stage carries with its own
    # attempt + artifact rows (per-run reads must keep working). The
    # stage whose ticket was OPEN on the old run (project_qdrant — the
    # live latent re-arm shape) is OWED WORK: it must NOT carry, and
    # must re-execute on the successor instead (receipt-incremental).
    for stage in STAGE_CHAIN:
        t = conn.execute(
            "SELECT status FROM stage_tickets WHERE run_id=%s AND stage=%s",
            (successor, stage)).fetchone()
        if stage == "project_qdrant":
            assert t and t[0] != "done", f"owed stage carried! {t}"
            continue
        assert t and t[0] == "done", f"{stage} ticket {t}"
        a = conn.execute(
            "SELECT outcome FROM stage_attempts WHERE run_id=%s AND stage=%s",
            (successor, stage)).fetchone()
        assert a and a[0] == "ok", f"{stage} attempt missing"
        art = conn.execute(
            "SELECT 1 FROM artifacts WHERE run_id=%s AND stage=%s",
            (successor, stage)).fetchone()
        assert art, f"{stage} artifact not carried"

    # the census-killer: advancement runs clean with the DAG-less ticket
    advance_tickets(conn)

    # the WORKER completes the owed stage (as the fleet would — the
    # census re-drives it; receipts make it incremental):
    conn.execute(
        "UPDATE stage_tickets SET status='done', updated_at=now() "
        "WHERE run_id=%s AND stage='project_qdrant'", (successor,))
    conn.execute(
        "INSERT INTO stage_attempts (run_id, stage, contract_hash, "
        "started_at, completed_at, outcome, payload) "
        "VALUES (%s,'project_qdrant',%s,now(),now(),'ok','{}')",
        (successor, f"h2_{tag}_pq"))

    # census sees a complete successor chain and promotes it
    census = compute_census(conn)
    my_gaps = [g for g in census.gaps if g.corpus_id == corpus]
    assert successor in census.promote, (
        f"not promoted; gaps={[(g.stage, g.reason) for g in my_gaps]}")
    apply_promotions(conn, census)
    status = conn.execute(
        "SELECT status FROM runs WHERE run_id=%s", (successor,)).fetchone()[0]
    assert status == "query_ready"


def test_occupied_successor_pointer_skips_instead_of_killing_tick(conn) -> None:
    """TICK-SURVIVAL regression (2026-08-31 control-plane wedge): a
    PARKED successor husk (status superseded, superseded_by NULL) from
    a past restoration occupies the one-successor pointer. The mint
    hits runs_one_successor_idx — that must be a per-run SKIP, never a
    tick-killing exception (the live wedge rolled back every control
    tick; census and ticketing died with it)."""
    tag = uuid.uuid4().hex[:8]
    current = default_execution_contract()
    old_pin = dict(current)
    old_pin["query_policy"] = "husk-test-old-policy"
    corpus, old_run = _mk_completed_run(conn, tag, old_pin)

    # the husk: occupies supersedes_run_id=old_run, itself dead
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata, "
        "execution_contract, supersedes_run_id) "
        "VALUES (%s,%s,'superseded','{}',%s,%s)",
        (f"run_husk_{tag}", corpus, json.dumps(old_pin, sort_keys=True),
         old_run))

    out = reconcile_contract_drift(conn)      # must not raise
    assert out["skipped"].get(old_run) == "successor_pointer_occupied"
    assert old_run not in out["reconciled"]

    # a later tick still reconciles OTHER stranded runs fine
    corpus2, other_run = _mk_completed_run(conn, tag + "b", old_pin)
    out2 = reconcile_contract_drift(conn)
    assert other_run in out2["reconciled"]
    assert out2["skipped"].get(old_run) == "successor_pointer_occupied"

    # the owner detach (what reingest_corpus.py does) unblocks it
    conn.execute(
        "UPDATE runs SET supersedes_run_id=NULL "
        "WHERE supersedes_run_id=%s AND status='superseded' "
        "AND superseded_by_run_id IS NULL", (old_run,))
    out3 = reconcile_contract_drift(conn)
    assert old_run in out3["reconciled"]


def test_successor_gets_fresh_failure_budget(conn) -> None:
    """FRESH-BUDGET invariant (owner 2026-09-01): NEW execution
    contract → NEW failure budget; OLD attempts → immutable audit
    history. A run whose stage burned its whole strike budget under a
    failure class the new contract fixed must NOT arrive at the
    successor pre-poisoned. Holds structurally today (per-run ticket
    ids mint fresh rows) — this pin keeps a refactor from ever
    carrying attempt counters across the lineage."""
    tag = uuid.uuid4().hex[:8]
    current = default_execution_contract()
    old_pin = dict(current)
    old_pin["rule_pack"] = "budget-test-old-rules"   # extract regenerates
    corpus, old_run = _mk_completed_run(conn, tag, old_pin)
    # the old run's extract ticket: strike budget EXHAUSTED
    conn.execute(
        "UPDATE stage_tickets SET status='failed', attempt=3 "
        "WHERE run_id=%s AND stage='extract'", (old_run,))

    out = reconcile_contract_drift(conn)
    successor = out["reconciled"][old_run]

    st, att = conn.execute(
        "SELECT status, attempt FROM stage_tickets "
        "WHERE run_id=%s AND stage='extract'", (successor,)).fetchone()
    assert st != "failed" and att == 0        # fresh budget
    # the audit history survives untouched on the OLD run
    old_att = conn.execute(
        "SELECT attempt FROM stage_tickets WHERE run_id=%s "
        "AND stage='extract'", (old_run,)).fetchone()[0]
    assert old_att == 3


def test_stale_stage_regenerates_instead_of_carrying(conn) -> None:
    tag = uuid.uuid4().hex[:8]
    current = default_execution_contract()
    old_pin = dict(current)
    old_pin["rule_pack"] = "reconv-old-rules"   # extract-family goes stale
    corpus, old_run = _mk_completed_run(conn, tag, old_pin)

    out = reconcile_contract_drift(conn)
    successor = out["reconciled"][old_run]

    # extract must NOT carry (dependency changed); intake must carry
    ex = conn.execute(
        "SELECT status FROM stage_tickets WHERE run_id=%s AND stage='extract'",
        (successor,)).fetchone()
    assert ex is None or ex[0] != "done"
    it = conn.execute(
        "SELECT status FROM stage_tickets WHERE run_id=%s AND stage='intake'",
        (successor,)).fetchone()
    assert it and it[0] == "done"
    # and the census does NOT promote a regenerating successor
    census = compute_census(conn)
    assert successor not in census.promote
