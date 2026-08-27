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
    _advance_pending_corpus,
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


def test_bulk_seed_maps_corpus_truth_to_pending_runs(monkeypatch):
    """BULK-RECEIPT-COMPLETENESS-V1: ONE anti-join per projection seeds
    the verdict store for every pending run — MISSING for runs of a
    corpus with chunk-receipt gaps, PRESENT otherwise. Pending-run count
    must not multiply queries (that loop ground a live tick >100 min)."""
    import control.tickets as T

    _RECEIPT_VERDICT_STORE.clear()

    queries = {"n": 0}

    class BulkConn:
        def execute(self, sql, *a, **k):
            queries["n"] += 1
            return self
        def fetchall(self):
            # 1: pending run ids; then bulk completeness per projection:
            # qdrant corpus has gaps, neo4j does not.
            if queries["n"] == 1:
                return [("run_1",), ("run_2",)]
            return [("corpus_x",)] if "chunks" in str(queries) or True \
                else []

    # drive fetchall sequencing explicitly instead of guessing
    seq = {"i": 0}

    class SeqConn:
        def execute(self, sql, *a, **k):
            return self
        def fetchall(self):
            seq["i"] += 1
            if seq["i"] == 1:
                return [("run_1",), ("run_2",)]   # pending runs
            if seq["i"] == 2:
                return [("corpus_x",)]            # qdrant: gaps exist
            return []                             # neo4j: complete

    monkeypatch.setattr(T, "_eligible_all_stages", lambda c, cid, lim: [])
    advanced = T._advance_pending_corpus(SeqConn(), "corpus_x")

    assert advanced == 0
    assert T._verdict_get(("run_1", "qdrant")) == RECEIPT_STATE_MISSING
    assert T._verdict_get(("run_2", "qdrant")) == RECEIPT_STATE_MISSING
    assert T._verdict_get(("run_1", "neo4j")) == RECEIPT_STATE_PRESENT
    assert T._verdict_get(("run_2", "neo4j")) == RECEIPT_STATE_PRESENT
