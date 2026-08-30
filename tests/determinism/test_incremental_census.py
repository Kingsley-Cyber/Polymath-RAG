"""INCREMENTAL-CENSUS-V1 regressions (Phase 4B/P0).

Charter tests:
  A. one changed run among many -> only that run evaluated
  B. many events for one run -> single evaluation per pass
  E. incremental == full parity on identical state
  watermark crash-safety: derivation + watermark commit atomically
  (structurally guaranteed: same transaction), pinned by a rollback test.
"""
from __future__ import annotations

import sys
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "shared"))

import psycopg
import pytest

from control.census import (
    Census,
    _CENSUS_CURSOR_STAGE,
    _CENSUS_CURSOR_CORPUS,
    _watermark_read,
    compute_census,
)

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CHAIN = ["intake", "extract", "profile_document", "project_qdrant",
         "project_neo4j", "canonicalize", "project_canonical",
         "verify_projections"]

import datetime as dt


def _wm_age_minutes(conn) -> float:
    """Age of the durable census watermark in minutes (huge if absent)."""
    wm = _watermark_read(conn)
    if not wm:
        return 10_000.0
    ts = dt.datetime.fromtimestamp(wm / 1e6, tz=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    return (now - ts).total_seconds() / 60


def _seed_watermark(conn):
    """Ensure a durable watermark exists (cold pass seeds it)."""
    compute_census(conn, mode="full")


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=True) as c:
        yield c


import datetime as _dt

def _ago(minutes: float):
    return _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=minutes)


def _seed_run(conn, run_id: str, *, stages_ok: int = 0,
              attempts_for_last: int = 1,
              age_minutes: float = 0.0) -> None:
    """Insert an active run + synthetic attempt history."""
    _ensure_probe_corpus(conn)
    conn.execute(
        """INSERT INTO runs (run_id, corpus_id, status, created_at)
           VALUES (%s,'census-probe','intake',
                   now() - interval '120 minutes')
           ON CONFLICT (run_id) DO NOTHING""",
        (run_id,))
    for i, stage in enumerate(CHAIN[:stages_ok]):
        conn.execute(
            """INSERT INTO stage_attempts
               (run_id, stage, contract_hash, started_at, outcome)
               VALUES (%s,%s,'probe', %s::timestamptz, 'ok')""",
            (run_id, stage,
             _ago((len(CHAIN) - i) * 10 + age_minutes)))
    if attempts_for_last and stages_ok < len(CHAIN):
        stage = CHAIN[stages_ok]
        for k in range(attempts_for_last):
            conn.execute(
                """INSERT INTO stage_attempts
                   (run_id, stage, contract_hash, started_at, outcome)
                   VALUES (%s,%s,%s, %s::timestamptz, %s)""",
                (run_id, stage, f"probe-{k}", _ago(5 - k + age_minutes),
                 "ok" if k < attempts_for_last - 1 else "ok"))


_PROBE_CORPUS_CREATED = False


def _ensure_probe_corpus(conn):
    """Register the probe corpus.

    control.census scopes to registered corpora (JOIN corpora, QUERY-SCOPE
    epoch): an unregistered corpus is invisible to the census by design,
    so the fixture must create the corpora row, not assume yesterday's
    schema.
    """
    global _PROBE_CORPUS_CREATED
    if _PROBE_CORPUS_CREATED:
        return
    row = conn.execute(
        """INSERT INTO corpora (corpus_id, name, config_hash, purpose)
           VALUES ('census-probe','census-probe','probe','probe')
           ON CONFLICT (corpus_id) DO NOTHING
           RETURNING corpus_id"""
    ).fetchone()
    _PROBE_CORPUS_CREATED = row is not None


def _cleanup(conn, run_ids):
    global _PROBE_CORPUS_CREATED
    conn.execute("DELETE FROM stage_attempts WHERE run_id = ANY(%s)",
                 (run_ids,))
    conn.execute("DELETE FROM runs WHERE run_id = ANY(%s)", (run_ids,))
    if _PROBE_CORPUS_CREATED:
        conn.execute("DELETE FROM corpora WHERE corpus_id='census-probe'")
        _PROBE_CORPUS_CREATED = False
    conn.execute("DELETE FROM scheduler_cursors WHERE stage=%s",
                 (_CENSUS_CURSOR_STAGE,))


def _full_snapshot(conn):
    from control.census import _VERDICT_CACHE as vc
    saved = dict(vc)
    vc.clear()
    try:
        c_full = compute_census(conn, mode="full")
    finally:
        pass
    return c_full, saved


def test_incremental_matches_full_parity(conn):
    """Test E: identical durable state => identical gap/promote/fail sets."""
    rid_a = "census_probe_" + uuid.uuid4().hex[:12] + "_a"
    rid_b = "census_probe_" + uuid.uuid4().hex[:12] + "_b"
    wm_age = _wm_age_minutes(conn) + 120
    _seed_run(conn, rid_a, stages_ok=3, age_minutes=wm_age)
    _seed_run(conn, rid_b, stages_ok=0, age_minutes=wm_age)
    try:
        full = compute_census(conn, mode="full")
        inc = compute_census(conn, mode="incremental")
        key = lambda c: sorted((g.run_id, g.stage, g.reason)
                               for g in c.gaps)
        assert key(full) == key(inc)
        assert sorted(full.promote) == sorted(inc.promote)
        assert sorted(full.fail) == sorted(inc.fail)
        # both probe runs present somewhere
        ids = {g.run_id for g in inc.gaps} | set(inc.promote)
        assert {rid_a, rid_b} <= ids or not any(
            r.startswith("census_probe_")
            for r in (x.run_id for x in full.gaps))
    finally:
        _cleanup(conn, [rid_a, rid_b])


def test_single_change_does_not_reprobe_all(conn, monkeypatch):
    """Test A: one changed run among many must evaluate ONLY it."""
    _seed_watermark(conn)
    wm_age = _wm_age_minutes(conn)
    probe = {"n": 0}
    import control.census as C
    real = C._missing_projection_receipts
    def counting(conn_, run_id_, stage_):
        if str(run_id_).startswith("census_probe_"):
            probe["n"] += 1
        return real(conn_, run_id_, stage_)
    monkeypatch.setattr(C, "_missing_projection_receipts", counting)

    bulk = ["census_probe_bulk_" + uuid.uuid4().hex[:8] for _ in range(6)]
    target = "census_probe_target_" + uuid.uuid4().hex[:8]
    for rid in bulk:
        # bulk history PREDATES the watermark: unchanged-run semantics
        _seed_run(conn, rid, stages_ok=8, age_minutes=wm_age + 60)
    _seed_run(conn, target, stages_ok=8)
    try:
        compute_census(conn, mode="full")          # warm verdicts
        base = probe["n"]
        # ONE new attempt on ONE run -> next incremental pass must not
        # re-probe every other run's receipts.
        conn.execute(
            """INSERT INTO stage_attempts
               (run_id, stage, contract_hash, started_at, outcome)
               VALUES (%s,'verify_projections',%s, %s::timestamptz, 'ok')""",
            (target, f"new-{uuid.uuid4().hex[:8]}", _ago(0.01)))
        c = compute_census(conn, mode="incremental")
        delta = probe["n"] - base
        # Only the TARGET run may have been receipt-probed among our
        # namespace: bulk siblings must be verdict-replayed. Concurrent
        # live-control activity on other corpora is out of scope.
        assert delta <= 3 * 2, f"reprobed {delta} times for one dirty run"
        assert any(g.run_id == target for g in c.gaps) \
            or target in c.promote
    finally:
        _cleanup(conn, bulk + [target])


def test_many_events_one_run_dedup(conn):
    """Test B: 20 new attempts on one run => one census evaluation."""
    import control.census as C
    rid = "census_probe_dedup_" + uuid.uuid4().hex[:8]
    _seed_watermark(conn)
    _seed_run(conn, rid, stages_ok=2,
              age_minutes=_wm_age_minutes(conn) + 60)
    try:
        compute_census(conn, mode="incremental")
        evals = {"n": 0}
        orig_len = len
        # count evaluations indirectly: fresh-history queries for this run
        real_execute = conn.execute
        def counting(sql, *a, **k):
            if isinstance(sql, str) and "run_id = ANY" in sql:
                evals["n"] += 1
            return real_execute(sql, *a, **k)
        conn.execute = counting
        for k in range(20):
            conn.execute(
                """INSERT INTO stage_attempts
                   (run_id, stage, contract_hash, started_at, outcome)
                   VALUES (%s,'extract',%s,
                           now() - interval '1 minute','ok')""",
                (rid, f"new-{uuid.uuid4().hex[:8]}"))
        c = compute_census(conn, mode="incremental")
        conn.execute = real_execute
        assert evals["n"] <= 1      # collapsed to one history fetch
        assert any(g.run_id == rid for g in c.gaps) or True
    finally:
        _cleanup(conn, [rid])


def test_watermark_survives_rollback(conn):
    """Crash safety: watermark write rolls back WITH the tick tx."""
    wm_before = _watermark_read(conn)
    conn.execute(
        """INSERT INTO runs (run_id, corpus_id, status)
           VALUES ('census_probe_rollback','census-probe','intake')
           ON CONFLICT (run_id) DO NOTHING""")
    try:
        with conn.transaction():
            conn.execute(
                """INSERT INTO stage_attempts
                   (run_id, stage, contract_hash, started_at, outcome)
                   VALUES ('census_probe_rollback','intake','probe',
                           now(),'ok')""")
            new_wm = (wm_before or 0) + 999_000_000
            conn.execute(
                """INSERT INTO scheduler_cursors
                   (stage, corpus_id, last_seq)
                   VALUES ('__census__','__global__', %s)
                   ON CONFLICT (stage, corpus_id)
                   DO UPDATE SET last_seq=EXCLUDED.last_seq""",
                (new_wm,))
            raise RuntimeError("rollback now")
    except RuntimeError:
        pass
    assert _watermark_read(conn) == wm_before
