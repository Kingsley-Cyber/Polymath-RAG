"""RECEIPT-VERDICT-STORE-V2 semantics (Phase correction 2026-08-25).

Directive invariants:
  1. A cached MISSING verdict NEVER becomes PRESENT from cache.
  2. A cached PRESENT verdict NEVER becomes MISSING from cache.
  3. An expired entry re-queries (stale verdict may delay, not decide).
  4. A cached MISSING can NEVER create illegal advancement.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "shared"))

import pytest

from control.tickets import (
    RECEIPT_STATE_MISSING,
    RECEIPT_STATE_PRESENT,
    _RECEIPT_VERDICT_STORE,
    _verdict_get,
    _verdict_put,
    _runs_with_missing_receipts,
    _try_advance_one,
)

KEY = ("run_x", "qdrant")


@pytest.fixture(autouse=True)
def _clean_store():
    _RECEIPT_VERDICT_STORE.clear()
    yield
    _RECEIPT_VERDICT_STORE.clear()


def _expire(key=KEY):
    written_at, state = _RECEIPT_VERDICT_STORE[key]
    _RECEIPT_VERDICT_STORE[key] = (written_at - 10_000.0, state)


def test_missing_never_becomes_present_from_cache():
    _verdict_put(KEY, RECEIPT_STATE_MISSING)
    for _ in range(5):
        assert _verdict_get(KEY) == RECEIPT_STATE_MISSING


def test_present_never_becomes_missing_from_cache():
    _verdict_put(KEY, RECEIPT_STATE_PRESENT)
    for _ in range(5):
        assert _verdict_get(KEY) == RECEIPT_STATE_PRESENT


def test_expired_entry_requeries_not_decides():
    class MustNotQuery:
        def execute(self, *a, **k):
            raise AssertionError("expired entry must trigger re-query")
    _verdict_put(KEY, RECEIPT_STATE_MISSING)
    _expire(KEY)
    assert _verdict_get(KEY) is None          # expired -> caller requeries
    # and a fresh store with no entry also reports None (no invention)
    _RECEIPT_VERDICT_STORE.clear()
    assert _verdict_get(KEY) is None


def test_cached_missing_blocks_advancement_without_db(monkeypatch):
    """Invariant 4: with a cached MISSING, _try_advance_one must return
    False WITHOUT touching the database at all — a stale MISSING may
    delay work but can never fabricate advancement."""
    import control.tickets as T

    _verdict_put((("run_missing", "qdrant")), RECEIPT_STATE_MISSING)

    class ExplodingConn:
        def execute(self, *a, **k):
            raise AssertionError(
                "cached-MISSING decision must not query the database")

    monkeypatch.setattr(T, "_stage_attempt_ok", lambda c, r, s: True)
    monkeypatch.setattr(T, "_artifacts_present", lambda c, r, s, k: True)
    monkeypatch.setattr(T, "_corpus_of", lambda c, r: "corpus_x")
    emitted = []
    monkeypatch.setattr(T, "_emit_ticket_event",
                        lambda conn, tid, run_id, stage: emitted.append(tid))

    ok = _try_advance_one(ExplodingConn(), "tkt_1", "run_missing",
                          "canonicalize")   # predecessors carry receipts
    assert ok is False
    assert emitted == []


def test_set_based_helper_maps_states_to_missing_set(monkeypatch):
    """_runs_with_missing_receipts returns ONLY runs whose cached state
    is MISSING; PRESENT runs are excluded without any query."""
    class MustNotQuery:
        def execute(self, *a, **k):
            raise AssertionError("present runs must be served from cache")
    _verdict_put(("run_p", "neo4j"), RECEIPT_STATE_PRESENT)
    _verdict_put(("run_m", "neo4j"), RECEIPT_STATE_MISSING)
    out = _runs_with_missing_receipts(MustNotQuery(),
                                      ["run_p", "run_m"], "neo4j")
    assert out == {"run_m"}
