"""STALL-TRACER-V1: every unit older than the threshold gets exactly one
deterministic diagnosis; fresh units are never traced; an episode is
persisted once and resolved the tick it clears. Real Postgres, rolled
back — the probe rows never commit."""
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

import psycopg
import pytest

from control.stall_tracer import (Stall, _live_sibling_runs, collect_stalls,
                                  diagnose_leased, diagnose_pending, diagnose_ready,
                                  persist_traces)

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "census-probe"


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        c.execute(
            """INSERT INTO corpora (corpus_id, name, config_hash, purpose)
               VALUES (%s, %s, 'probe', 'probe') ON CONFLICT (corpus_id) DO NOTHING""",
            (CORPUS, CORPUS))
        yield c
        c.rollback()


def _run(conn, status="reconciling", age_s=600):
    run_id = "run_probe_" + uuid.uuid4().hex[:16]
    conn.execute(
        """INSERT INTO runs (run_id, corpus_id, status, metadata, updated_at)
           VALUES (%s, %s, %s, '{"source_name": "probe.md"}'::jsonb,
                   now() - make_interval(secs => %s))""",
        (run_id, CORPUS, status, age_s))
    return run_id


def _ticket(conn, run_id, stage, status, age_s=600, **cols):
    tid = "tkt_probe_" + uuid.uuid4().hex[:16]
    extra_cols = "".join(f", {k}" for k in cols)
    extra_vals = "".join(", %s" for _ in cols)
    conn.execute(
        f"""INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type,
                                       status, updated_at{extra_cols})
            VALUES (%s, %s, %s, %s, %s, %s, now() - make_interval(secs => %s){extra_vals})""",
        (tid, run_id, CORPUS, stage, f"{stage}.v1", status, age_s, *cols.values()))
    return tid


def _by_id(stalls, unit_id):
    hits = [s for s in stalls if s.unit_id == unit_id]
    assert len(hits) == 1, f"expected exactly one trace for {unit_id}, got {len(hits)}"
    return hits[0]


def test_fresh_units_are_never_traced(conn):
    run_id = _run(conn, age_s=10)
    tid = _ticket(conn, run_id, "extract", "ready", age_s=10)
    ids = {s.unit_id for s in collect_stalls(conn, threshold_s=180)}
    assert tid not in ids and run_id not in ids


def test_ready_without_claim_event_and_without_live_slot(conn):
    run_id = _run(conn)
    tid = _ticket(conn, run_id, "extract", "ready")
    s = _by_id(collect_stalls(conn, threshold_s=180), tid)
    assert s.diagnosis == "READY_NO_CLAIM_EVENT"
    assert s.detail["lane"] == "extract"
    # with a pending claim event the slot view decides
    conn.execute(
        """INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
           VALUES (%s, 'extract.v1', %s::jsonb, %s)""",
        (run_id, '{"ticket_id": "%s"}' % tid, "idem_probe_" + uuid.uuid4().hex[:12]))
    # V1.3: the live fleet may have every extract worker busy (P6 was running
    # when this was written) — give the lane one idle worker so the probe
    # ticket is judged claimable rather than queued behind saturation
    conn.execute(
        """INSERT INTO worker_registrations (worker_id, worker_type, pid, host)
           VALUES ('w-idle-probe', 'extract', 6161, 'probe')
           ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()""")
    dead = collect_stalls(conn, threshold_s=180,
                          slots_alive={"extract": False, "profile": False, "extract2": False})
    assert _by_id(dead, tid).diagnosis == "READY_NO_LIVE_SLOT"
    alive = collect_stalls(conn, threshold_s=180, slots_alive={"extract": True})
    assert _by_id(alive, tid).diagnosis == "READY_UNCLAIMED"


def test_leased_owner_gone_vs_expired_vs_long_running(conn):
    run_id = _run(conn)
    # owner never registered, lease still in the future -> gone
    t_gone = _ticket(conn, run_id, "extract", "leased", lease_owner="w-ghost",
                     lease_expires_at=None)
    conn.execute("UPDATE stage_tickets SET lease_expires_at = now() + interval '10 min' "
                 "WHERE ticket_id = %s", (t_gone,))
    # lease already expired -> the sweep should have released it
    t_exp = _ticket(conn, run_id, "project_qdrant", "leased", lease_owner="w-ghost2")
    conn.execute("UPDATE stage_tickets SET lease_expires_at = now() - interval '1 min' "
                 "WHERE ticket_id = %s", (t_exp,))
    # live, heartbeating owner -> long running
    conn.execute(
        """INSERT INTO worker_registrations (worker_id, worker_type, pid, host)
           VALUES ('w-live-probe', 'extract', 4242, 'probe')
           ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()""")
    t_long = _ticket(conn, run_id, "project_neo4j", "leased", lease_owner="w-live-probe")
    conn.execute("UPDATE stage_tickets SET lease_expires_at = now() + interval '10 min' "
                 "WHERE ticket_id = %s", (t_long,))
    stalls = collect_stalls(conn, threshold_s=180)
    assert _by_id(stalls, t_gone).diagnosis == "LEASED_OWNER_GONE"
    assert _by_id(stalls, t_exp).diagnosis == "LEASED_EXPIRED_NOT_RELEASED"
    long = _by_id(stalls, t_long)
    assert long.diagnosis == "LEASED_LONG_RUNNING"
    assert long.detail["worker_pid"] == 4242


def test_pending_names_the_predecessor_it_waits_on(conn):
    run_id = _run(conn)
    _ticket(conn, run_id, "intake", "done")
    t_extract = _ticket(conn, run_id, "extract", "ready")
    t_pending = _ticket(conn, run_id, "profile_document", "pending")
    s = _by_id(collect_stalls(conn, threshold_s=180), t_pending)
    assert s.diagnosis == "PENDING_ON_PREDECESSOR"
    assert s.detail["predecessor"] == "extract"
    assert s.detail["predecessor_ticket_status"] == "ready"
    assert t_extract  # the extract ticket is traced on its own


def test_pending_behind_live_work_is_not_a_stall(conn):
    """STALL-TRACER-V1.1: a pending ticket whose predecessor is LEASED by a
    heartbeating worker is waiting on live work; the same ticket behind a
    predecessor whose holder is gone IS traced."""
    run_id = _run(conn)
    _ticket(conn, run_id, "intake", "done")
    conn.execute(
        """INSERT INTO worker_registrations (worker_id, worker_type, pid, host)
           VALUES ('w-live-pred', 'extract', 4343, 'probe')
           ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()""")
    t_extract = _ticket(conn, run_id, "extract", "leased", lease_owner="w-live-pred")
    conn.execute("UPDATE stage_tickets SET lease_expires_at = now() + interval '10 min' "
                 "WHERE ticket_id = %s", (t_extract,))
    t_pending = _ticket(conn, run_id, "profile_document", "pending")
    ids = {s.unit_id for s in collect_stalls(conn, threshold_s=180)}
    assert t_pending not in ids, "queued behind live work must not be traced"
    # the holder dies -> the dependent is traced again
    conn.execute("UPDATE worker_registrations SET heartbeat_at = now() - interval '10 min' "
                 "WHERE worker_id = 'w-live-pred'")
    s = _by_id(collect_stalls(conn, threshold_s=180), t_pending)
    assert s.diagnosis == "PENDING_ON_PREDECESSOR" and s.detail["predecessor_ticket_status"] == "leased"


def test_runs_without_open_work(conn):
    r_nochain = _run(conn, status="intake")
    r_degraded = _run(conn, status="degraded")
    _ticket(conn, r_degraded, "intake", "done")
    r_progress = _run(conn, status="reconciling")
    _ticket(conn, r_progress, "extract", "ready")   # open work: explained by the ticket
    stalls = collect_stalls(conn, threshold_s=180)
    assert _by_id(stalls, r_nochain).diagnosis == "RUN_NO_TICKET_CHAIN"
    assert _by_id(stalls, r_degraded).diagnosis == "RUN_DEGRADED_AWAITING_DECISION"
    assert r_progress not in {s.unit_id for s in stalls}


def test_summary_job_inflight_is_traced(conn):
    run_id = _run(conn)
    tid = _ticket(conn, run_id, "parent_summary", "leased", lease_owner="w-x")
    job = f"{tid}:abc"
    conn.execute(
        """INSERT INTO summary_jobs (ticket_id, stage, corpus_id, input_hash,
                                     contract_version, state, created_at)
           VALUES (%s, 'PARENT_SUMMARY', %s, %s, 'v1', 'READY',
                   now() - interval '10 min')""",
        (job, CORPUS, "h_" + uuid.uuid4().hex[:8]))
    s = _by_id(collect_stalls(conn, threshold_s=180), job)
    assert s.diagnosis == "SUMMARY_JOB_INFLIGHT_STALLED"
    assert s.detail["ticket_status"] == "leased"


def test_episode_persists_once_and_resolves_when_cleared(conn):
    run_id = _run(conn)
    tid = _ticket(conn, run_id, "extract", "ready")
    first = collect_stalls(conn, threshold_s=180)
    new = persist_traces(conn, [s for s in first if s.unit_id == tid])
    assert [s.unit_id for s in new] == [tid]
    again = persist_traces(conn, [s for s in first if s.unit_id == tid])
    assert again == []                       # same episode, no new row
    open_rows = conn.execute(
        "SELECT count(*) FROM stall_traces WHERE unit_id = %s AND resolved_at IS NULL",
        (tid,)).fetchone()[0]
    assert open_rows == 1
    persist_traces(conn, [])                 # the unit moved: nothing stalled
    resolved = conn.execute(
        "SELECT resolved_at IS NOT NULL FROM stall_traces WHERE unit_id = %s",
        (tid,)).fetchone()[0]
    assert resolved is True


def test_pure_diagnoses_are_deterministic():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    row = {"stage": "extract", "attempt": 0, "live_workers": 3, "claim_event_pending": True}
    assert diagnose_ready(row, None)[0] == "READY_UNCLAIMED"
    assert diagnose_ready(dict(row, claim_event_pending=False), None)[0] == "READY_NO_CLAIM_EVENT"
    leased = {"heartbeat_at": now - timedelta(seconds=5), "lease_expires_at": now + timedelta(minutes=5),
              "lease_owner": "w", "pid": 1, "worker_status": "healthy"}
    assert diagnose_leased(leased, now)[0] == "LEASED_LONG_RUNNING"
    assert diagnose_leased(dict(leased, heartbeat_at=None), now)[0] == "LEASED_OWNER_GONE"
    assert diagnose_leased(dict(leased, lease_expires_at=now - timedelta(seconds=1)), now)[0] \
        == "LEASED_EXPIRED_NOT_RELEASED"
    assert Stall("ticket", "t1", now, 200, "X").key == "ticket:t1"


def test_corpus_barrier_behind_live_sibling_run_is_not_a_stall(conn, monkeypatch):
    """STALL-TRACER-V1.2: corpus_summary/vocabulary wait for EVERY document
    of the corpus to be projected (the receipt predicate is corpus-scoped).
    While a sibling run is converging with live work the barrier ticket is
    waiting, not stuck; once the sibling goes quiet it IS traced and names
    the sibling. Measured 2026-09-03 on the incrementality probe."""
    import control.tickets as tk
    monkeypatch.setattr(tk, "_stage_attempt_ok", lambda *a, **k: True)
    monkeypatch.setattr(tk, "_artifacts_present", lambda *a, **k: True)
    monkeypatch.setattr(tk, "_receipts_present", lambda *a, **k: False)
    run_a = _run(conn, status="query_ready")
    t_barrier = _ticket(conn, run_a, "corpus_summary", "pending")
    row = {"run_id": run_a, "corpus_id": CORPUS, "stage": "corpus_summary", "ticket_id": t_barrier}
    # sibling run B with a ticket that changed state 30 s ago -> live work
    run_b = _run(conn, age_s=30)
    t_b = _ticket(conn, run_b, "extract", "ready", age_s=30)
    assert _live_sibling_runs(conn, row, 180) == [run_b]
    assert diagnose_pending(conn, row, {}, threshold_s=180) is None
    # sibling goes quiet (no state change for 10 min, nothing leased) -> traced, naming it
    conn.execute("UPDATE stage_tickets SET updated_at = now() - interval '10 min' WHERE ticket_id = %s", (t_b,))
    assert _live_sibling_runs(conn, row, 180) == []
    diag, detail = diagnose_pending(conn, row, {}, threshold_s=180)
    assert diag == "PENDING_ADVANCE_BLOCKED" and detail["missing"] == "receipts"
    assert detail["sibling_runs_open"] == [run_b]
    # a quiet sibling whose ticket is LEASED by a heartbeating worker is live again
    conn.execute(
        """INSERT INTO worker_registrations (worker_id, worker_type, pid, host)
           VALUES ('w-live-sib', 'extract', 4444, 'probe')
           ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()""")
    conn.execute("UPDATE stage_tickets SET status = 'leased', lease_owner = 'w-live-sib' WHERE ticket_id = %s", (t_b,))
    assert _live_sibling_runs(conn, row, 180) == [run_b]
    assert diagnose_pending(conn, row, {}, threshold_s=180) is None


def test_ready_queued_behind_a_saturated_lane_is_not_a_stall(conn):
    """STALL-TRACER-V1.3: every live worker of the ticket's type holds a lease
    -> the READY ticket is queued behind live work. Owner-triggered stages
    mint per-RUN claim events (no ticket_id in the payload) — those count."""
    run_a = _run(conn); run_b = _run(conn)
    conn.execute(
        """INSERT INTO worker_registrations (worker_id, worker_type, pid, host)
           VALUES ('w-busy-1', 'extract-probe', 5151, 'probe')
           ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()""")
    _ticket(conn, run_a, "intake", "done"); _ticket(conn, run_b, "intake", "done")
    t_busy = _ticket(conn, run_a, "extract", "leased", lease_owner="w-busy-1")
    # the probe holder is the stage's most recent lease -> capacity is judged by ITS worker type,
    # so live-fleet registrations (and their post-restart ghosts) cannot skew the probe
    conn.execute("UPDATE stage_tickets SET lease_expires_at = now() + interval '10 min', updated_at = now() "
                 "WHERE ticket_id = %s", (t_busy,))
    t_queued = _ticket(conn, run_b, "extract", "ready")
    conn.execute(
        """INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
           VALUES (%s, 'extract.v1', %s::jsonb, %s)""",
        (run_b, '{"run_id": "%s"}' % run_b, "idem_probe_" + uuid.uuid4().hex[:12]))   # per-RUN event, no ticket_id
    ids = {s.unit_id for s in collect_stalls(conn, threshold_s=180)}
    assert t_queued not in ids, "queued behind the only (busy) extract worker must not be traced"
    # the worker frees up (lease released) -> the ready ticket IS traced again
    conn.execute("UPDATE stage_tickets SET status='done', lease_owner=NULL WHERE ticket_id = %s", (t_busy,))
    s = _by_id(collect_stalls(conn, threshold_s=180), t_queued)
    assert s.diagnosis == "READY_UNCLAIMED"          # per-run event counted as a pending claim event


def test_dependents_of_a_queued_predecessor_are_not_traced(conn):
    """STALL-TRACER-V1.3: pending tickets behind a READY predecessor that is
    itself queued behind a saturated lane are waiting on live work."""
    run_a = _run(conn); run_b = _run(conn)
    conn.execute(
        """INSERT INTO worker_registrations (worker_id, worker_type, pid, host)
           VALUES ('w-busy-2', 'extract-probe', 5252, 'probe')
           ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()""")
    _ticket(conn, run_a, "intake", "done"); _ticket(conn, run_b, "intake", "done")
    t_busy = _ticket(conn, run_a, "extract", "leased", lease_owner="w-busy-2")
    conn.execute("UPDATE stage_tickets SET lease_expires_at = now() + interval '10 min', updated_at = now() "
                 "WHERE ticket_id = %s", (t_busy,))
    t_queued = _ticket(conn, run_b, "extract", "ready")
    conn.execute(
        """INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
           VALUES (%s, 'extract.v1', %s::jsonb, %s)""",
        (run_b, '{"ticket_id": "%s"}' % t_queued, "idem_probe_" + uuid.uuid4().hex[:12]))
    t_dep = _ticket(conn, run_b, "profile_document", "pending")
    ids = {s.unit_id for s in collect_stalls(conn, threshold_s=180)}
    assert t_queued not in ids and t_dep not in ids
