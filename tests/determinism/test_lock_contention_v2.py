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
    """The early-exit form is the fix; pin the query shape."""
    import inspect
    from control import tickets
    src = inspect.getsource(tickets._receipts_present)
    assert "SELECT NOT EXISTS" in src
    assert "COUNT(*)" not in src


def test_memo_prevents_repeat_queries(conn, monkeypatch):
    """Charter invariant: one (run_id, projection) => at most ONE query
    per advance pass, regardless of candidate ticket count."""
    calls = {"n": 0}
    real_execute = conn.execute

    def counting_execute(sql, *a, **k):
        if "NOT EXISTS" in sql and "projection_receipts" in sql:
            calls["n"] += 1
        return real_execute(sql, *a, **k)

    monkeypatch.setattr(conn, "execute", counting_execute)
    cache: dict = {}
    run_id = "run_does_not_exist_" + uuid.uuid4().hex[:8]
    for _ in range(25):
        # 25 candidate tickets of the same run share predecessor state
        assert _receipts_present(conn, run_id, "c", "qdrant", cache) is True
    assert calls["n"] == 1          # queried exactly once
    assert len(cache) == 1


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
    monkeypatch.syspath_prepend(str(ROOT / "control"))
    from control.tickets import _receipts_present as rp
    assert rp(FakeConn(False), "r", "c", "qdrant") is False
    assert rp(FakeConn(True), "r", "c", "qdrant") is True
