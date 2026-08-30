"""CENSUS-DIRTY-SIGNAL-V2 — the stuck-run class, pinned. DB-backed,
rolled back.

MEASURED (2026-08-30, cysa-study-v1): both runs finished every stage,
all 24 tickets done, and sat at `reconciling` for 13 minutes (forever,
absent intervention) because (a) the summary stages complete tickets
without writing stage_attempts, so attempt-based dirtiness never
re-evaluated the runs, and (b) the incremental census replayed a stale
cached non-promote verdict verbatim every tick.
"""
from __future__ import annotations

import pathlib
import sys

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from polymath_shared.settings import get_settings  # noqa: E402
from control import census as census_mod  # noqa: E402
from control.census import STAGE_CHAIN, compute_census  # noqa: E402


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch):
    monkeypatch.setattr(census_mod, "_VERDICT_CACHE", {})
    monkeypatch.setattr(census_mod, "_HISTORY_CACHE", {})


def _seed_complete_run(conn, corpus: str, run: str, *,
                       attempts_age: str = "2 hours") -> None:
    conn.execute(
        "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, 'census-test') "
        "ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata, created_at) "
        "VALUES (%s, %s, 'reconciling', '{}', now() - %s::interval)",
        (run, corpus, attempts_age))
    for stage in STAGE_CHAIN:
        conn.execute(
            "INSERT INTO stage_attempts (run_id, stage, contract_hash, outcome, started_at) "
            "VALUES (%s, %s, 'census-test', 'ok', now() - %s::interval)",
            (run, stage, attempts_age))


def test_ticket_close_dirties_a_run_pinned_by_a_stale_verdict(conn, monkeypatch):
    """Guard 1: a ticket transition re-evaluates the run even with no new
    stage_attempt — a poisoned cached non-promote verdict must NOT be
    replayed once a ticket closed after the watermark."""
    corpus, run = "census-test-corpus", "run_census_test_0001"
    _seed_complete_run(conn, corpus, run)
    # a summary-style ticket that closed JUST NOW, with no attempt row
    conn.execute(
        "INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, "
        "event_type, status, updated_at) "
        "VALUES ('tkt_census_test_1', %s, %s, 'parent_summary', "
        "'parent_summary.v1', 'done', now())", (run, corpus))
    # watermark newer than every attempt, older than the ticket close
    conn.execute(
        "INSERT INTO scheduler_cursors (stage, corpus_id, last_seq) "
        "VALUES ('__census__', '__global__', "
        "(extract(epoch from now() - interval '1 hour') * 1000000)::bigint) "
        "ON CONFLICT (stage, corpus_id) DO UPDATE SET last_seq = EXCLUDED.last_seq")
    # the poison: the measured stuck state — cached gaps, no promote
    census_mod._VERDICT_CACHE[run] = {
        "gaps": [], "promote": False, "fail": False, "degrade": None}
    out = compute_census(conn, mode="incremental")
    assert run in out.promote, (
        "ticket close after the watermark must dirty the run; the stale "
        "cached verdict was replayed instead")


def test_gap_verdicts_are_never_cached(conn):
    """Guard 2: a verdict carrying gaps must not enter the cache — a
    replayed gap re-arms unclaimable outbox events every tick."""
    corpus, run = "census-test-corpus", "run_census_test_0002"
    conn.execute(
        "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, 'census-test') "
        "ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata) "
        "VALUES (%s, %s, 'reconciling', '{}')", (run, corpus))
    conn.execute(
        "INSERT INTO stage_attempts (run_id, stage, contract_hash, outcome, started_at) "
        "VALUES (%s, 'intake', 'census-test', 'ok', now())", (run,))
    out = compute_census(conn, mode="full")
    assert any(g.run_id == run for g in out.gaps)      # extract missing
    assert run not in census_mod._VERDICT_CACHE


def test_one_failed_run_does_not_block_another_runs_promotion(conn):
    """`complete and not census.fail` read the GLOBAL fail list: one
    failed run blocked promotion of every later-sorted healthy run."""
    corpus = "census-test-corpus"
    failed_run, good_run = "run_census_test_0003", "run_census_test_0004"
    # older run: extract failed beyond the retry budget -> census.fail
    conn.execute(
        "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, 'census-test') "
        "ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata, created_at) "
        "VALUES (%s, %s, 'reconciling', '{}', now() - interval '3 hours')",
        (failed_run, corpus))
    conn.execute(
        "INSERT INTO stage_attempts (run_id, stage, contract_hash, outcome, started_at) "
        "VALUES (%s, 'intake', 'census-test', 'ok', now() - interval '3 hours')", (failed_run,))
    for i in range(3):
        conn.execute(
            "INSERT INTO stage_attempts (run_id, stage, contract_hash, outcome, started_at) "
            "VALUES (%s, 'extract', %s, 'failed', now() - interval '3 hours')",
            (failed_run, f"census-test-{i}"))
    _seed_complete_run(conn, corpus, good_run, attempts_age="1 hour")
    out = compute_census(conn, mode="full")
    assert failed_run in out.fail
    assert good_run in out.promote, (
        "a failed sibling run must not veto an unrelated complete run")
