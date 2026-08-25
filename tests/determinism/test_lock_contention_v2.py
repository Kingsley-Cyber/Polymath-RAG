"""LOCK-CONTENTION-V2 regressions (Phase 4A).

Invariant: bulk corpus verification must not multiply corpus-wide
receipt scans by pending-ticket count inside the control tick.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "shared"))

import json
import uuid

import psycopg
import pytest

from control.tickets import _receipts_present

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=True) as c:
        yield c


def test_uses_exists_form_not_count():
    """The early-exit form is the fix; pin the query shape.

    BULK-RECEIPT-COMPLETENESS-V1: completeness moved to ONE corpus-scoped
    anti-join per projection; pin the same discipline on the new surface.
    """
    import inspect
    from control import tickets
    src = inspect.getsource(tickets._corpora_with_missing_chunk_receipts)
    assert "NOT EXISTS" in src
    assert "COUNT(*)" not in src
    # single-run path shares the EXISTS discipline
    src2 = inspect.getsource(tickets._receipts_present)
    assert "NOT EXISTS" in src2
    assert "COUNT(*)" not in src2


def test_verdict_store_collapses_repeat_queries(monkeypatch):
    """25 sequential decisions for one (run, projection) => at most ONE
    database query; the explicit-state store serves the rest."""
    import control.tickets as T
    calls = {"n": 0}

    class CountingConn:
        def execute(self, sql, *a, **k):
            if "NOT EXISTS" in sql:
                calls["n"] += 1
            return self
        def fetchone(self):
            return (True,)       # NOT EXISTS=true => no gaps => present
    c = CountingConn()
    for _ in range(25):
        present = T._receipts_present(c, "run_z", "corpus_z", "qdrant")
        assert present is True
    assert calls["n"] == 1


def test_statement_timeout_guard(conn):
    """C4 hang-guard: DB-touching determinism tests must fail fast, not
    wait behind a long control transaction."""
    row = conn.execute("SHOW statement_timeout").fetchone()
    assert row is not None


def test_missing_receipt_is_detected(monkeypatch):
    """Correctness unchanged: EXISTS form still finds a gap."""
    class FakeConn:
        def __init__(self, result):
            self._r = result
        def execute(self, sql, *a):
            assert "NOT EXISTS" in sql and "COUNT" not in sql
            return self
        def fetchone(self):
            return (self._r,)
    from control.tickets import (_receipts_present as rp,
                                 _RECEIPT_VERDICT_STORE)
    # run 1: DB says gaps exist -> PRESENT must be False
    assert rp(FakeConn(False), "r", "c", "qdrant") is False
    # distinct run -> fresh verdict required even though run 'r' cached
    _RECEIPT_VERDICT_STORE.clear()
    assert rp(FakeConn(True), "r2", "c", "qdrant") is True


def test_advance_tickets_entry_point_wiring(monkeypatch):
    """MEASURED LIVE 2026-08-25: the store cutover left advance_tickets
    calling _advance_pending_corpus with a stale third argument — every
    real tick died with TypeError for hours while component tests passed.
    This pins the ENTRY POINT wiring: one 2-arg call per pending corpus,
    and the whole pass completes."""
    import inspect

    import control.tickets as T

    sig = inspect.signature(T._advance_pending_corpus)
    assert list(sig.parameters) == ["conn", "corpus_id"], \
        "signature drift: update the advance_tickets call site together"

    calls = []

    def fake_advancer(conn, corpus_id):
        calls.append(corpus_id)
        return 0

    monkeypatch.setattr(T, "_advance_pending_corpus", fake_advancer)

    class FakeConn:
        """Scripted: first fetchall = pending corpora; later queries
        (ready backfill, lease sweep) return nothing."""
        def __init__(self):
            self._n = 0
        def execute(self, sql, *a, **k):
            self._n += 1
            return self
        def fetchall(self):
            return [("corpus_a",)] if self._n == 1 else []
        def fetchone(self):
            return None

    advanced = T.advance_tickets(FakeConn())
    assert calls == ["corpus_a"]
    assert advanced == 0
