"""DOC-PARENT-MAP AUTO-MINT (RAG-PIPELINE-FINISH) — the flag-gated mint path.

Provider-free, DB-free: proves the pMAP stage is minted like parent_enrichment (outside
STAGE_DAG, non-blocking), that the scheduler phase is a true no-op when the owner flag is
off (hold-safe / byte-identical), and the mint writes the right ticket + event.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "control"):
    sys.path.insert(0, str(_p))

from polymath_shared.document_profile import map_trigger as MT  # noqa: E402


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_ENABLED", raising=False)
    assert MT.doc_parent_map_enabled() is False
    for v in ("1", "true", "yes", "on", "ON"):
        monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_ENABLED", v)
        assert MT.doc_parent_map_enabled() is True
    monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_ENABLED", "off")
    assert MT.doc_parent_map_enabled() is False


def test_corpus_scope(monkeypatch):
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_CORPUS", raising=False)
    assert MT.doc_parent_map_corpus_scope() is None
    monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_CORPUS", "canary-corpus")
    assert MT.doc_parent_map_corpus_scope() == "canary-corpus"


def test_doc_parent_map_is_non_blocking_and_absent_from_stage_dag():
    from control.tickets import STAGE_DAG, NON_BLOCKING_STAGES, is_blocking
    dag_stages = {s for s, *_ in STAGE_DAG}
    assert "doc_parent_map" not in dag_stages         # frozen DAG unchanged
    assert "doc_parent_map" in NON_BLOCKING_STAGES     # never holds promotion
    assert is_blocking("doc_parent_map") is False


class _RaisingConn:
    def execute(self, *a, **k):
        raise AssertionError("scheduler phase must not touch the DB when the flag is off")


def test_scheduler_phase_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_ENABLED", raising=False)
    from control.scheduler import auto_map_parents_on_chunks
    # disabled => returns 0 without ANY database access (proven by the raising conn).
    assert auto_map_parents_on_chunks(_RaisingConn()) == 0


class _CapConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))
        return self


def test_mint_writes_ticket_and_event():
    conn = _CapConn()
    out = MT.mint_doc_parent_map(conn, corpus_id="corpA", run_id="runA")
    assert out["run_id"] == "runA" and out["ticket_id"].startswith("tkt_")
    sqls = [c[0] for c in conn.calls]
    # a stage_tickets upsert (stage doc_parent_map, ready) + an outbox_events upsert (doc_parent_map.v1)
    assert any("INSERT INTO stage_tickets" in s and "doc_parent_map" in str(p) for s, p in conn.calls)
    assert any("INSERT INTO outbox_events" in s for s in sqls)
    assert any("doc_parent_map.v1" in str(p) for _s, p in conn.calls)
    # idempotency key is per-run so a re-mint re-arms the same ticket/event.
    assert any("pmap:runA" in str(p) for _s, p in conn.calls)


def test_since_helper(monkeypatch):
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_SINCE", raising=False)
    assert MT.doc_parent_map_since() is None
    monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_SINCE", "2026-09-09T00:00:00Z")
    assert MT.doc_parent_map_since() == "2026-09-09T00:00:00Z"


class _SqlCapConn:
    """Records SQL; returns no rows (so the phase mints nothing) — for asserting the guards."""
    def __init__(self):
        self.sqls = []
    def execute(self, sql, params=()):
        self.sqls.append(" ".join(sql.split()))
        conn = self
        class _C:
            def fetchall(self_):
                return []
        return _C()


def test_since_guard_adds_created_after_boundary(monkeypatch):
    monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_ENABLED", "1")
    monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_SINCE", "2026-09-09T00:00:00Z")
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_CORPUS", raising=False)
    from control.scheduler import auto_map_parents_on_chunks
    conn = _SqlCapConn()
    auto_map_parents_on_chunks(conn)
    # NEW-UPLOADS-ONLY: the mint + doc_profile-early selects carry the created-after boundary,
    # so historical/cinema runs (created before it) are excluded even with no corpus scope.
    assert any("r.created_at > %s" in s for s in conn.sqls), conn.sqls


def test_no_since_means_no_created_after_boundary(monkeypatch):
    monkeypatch.setenv("POLYMATH_DOC_PARENT_MAP_ENABLED", "1")
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_SINCE", raising=False)
    monkeypatch.delenv("POLYMATH_DOC_PARENT_MAP_CORPUS", raising=False)
    from control.scheduler import auto_map_parents_on_chunks
    conn = _SqlCapConn()
    auto_map_parents_on_chunks(conn)
    assert not any("created_at > %s" in s for s in conn.sqls)
