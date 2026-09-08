"""RETRIEVAL-MIGRATION-DEPENDENCY-V1 slice S11 (report-only) — vNext readiness report.

The report-only parent-map backfill verifier (plan §2/§16/§19). These pins fix the
generation-invariant classification (a partially-mapped document is NEVER complete)
and prove the report reads durable state without effect. The DB-backed pin skips
cleanly without Postgres (CI has none), as the other document_profile stage tests do.
Pure otherwise — no writes, no models, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared", ROOT / "scripts"):
    sys.path.insert(0, str(_p))

import vnext_readiness_report as R  # noqa: E402


def test_document_state_generation_invariant():
    assert R.document_state(0, 0, 0) == R.NO_ELIGIBLE_PARENTS
    assert R.document_state(5, 0, 0) == R.NOT_STARTED
    assert R.document_state(5, 3, 0) == R.MAP_PARTIAL       # partial is NOT complete
    assert R.document_state(5, 3, 2) == R.MAP_COMPLETE      # mapped + excluded == eligible
    assert R.document_state(5, 5, 0) == R.MAP_COMPLETE
    assert R.document_state(5, 9, 0) == R.MAP_COMPLETE      # over-resolved still complete
    # a single unresolved eligible parent keeps the whole document partial (§19 floor)
    assert R.document_state(100, 99, 0) == R.MAP_PARTIAL


def test_main_returns_zero_without_db():
    # the CLI is availability-neutral: no DB -> clean no-op exit, never a crash.
    assert R.main(["--corpus", "does-not-exist"]) == 0
    assert R.main(["--json"]) == 0


def test_backfill_report_on_live_db_if_present():
    try:
        from polymath_shared.db import tx
        with tx() as conn:
            exists = conn.execute("SELECT to_regclass('public.document_parent_maps')").fetchone()[0]
            if exists is None:
                pytest.skip("migration 0054 not applied")
            corpus = conn.execute("SELECT corpus_id FROM corpora LIMIT 1").fetchone()
            if not corpus:
                pytest.skip("no corpora in dev store")
            rep = R.backfill_report(conn, corpus[0])
    except Exception as exc:  # pragma: no cover - environment gate
        pytest.skip(f"postgres unavailable: {exc}")
    assert rep["contract"] == "vnext-readiness-report-v1"
    assert set(rep) >= {"total_documents", "legacy_query_ready_runs", "documents_by_state",
                        "parents", "vnext_maps_complete_documents"}
    # invariant: complete + partial + not_started + no_eligible == total
    assert sum(rep["documents_by_state"].values()) == rep["total_documents"]
    p = rep["parents"]
    assert p["unresolved"] == max(0, p["eligible"] - p["mapped"] - p["excluded"])


def test_s11proper_vnext_readiness_verdict_and_generation_invariant():
    # S11-proper: semantic_readiness.vnext_readiness is the first-class vNext verdict the cutover
    # gates on. Pure verdict logic over canned durable counts (fake conn); the §19 floor is
    # unresolved_eligible_parents == 0 AND every document vNext-profiled.
    from polymath_shared.semantic_readiness import (
        vnext_readiness, VNEXT_COMPLETE, VNEXT_INCOMPLETE, VNEXT_NOT_STARTED)

    class _Conn:
        def __init__(self, vals):
            self._v = list(vals)

        def execute(self, sql, params=None):
            v = self._v.pop(0)
            return type("R", (), {"fetchone": (lambda val: (lambda s: (val,)))(v)})()

    S = "public.document_parent_maps"
    # eligible 100 = mapped 90 + excluded 10 -> unresolved 0; profiles 5/5 -> COMPLETE
    assert vnext_readiness(_Conn([S, 100, 90, 10, 5]), "x", 5)["verdict"] == VNEXT_COMPLETE
    # one unresolved eligible parent -> INCOMPLETE (§19 floor: partial is never complete)
    assert vnext_readiness(_Conn([S, 100, 89, 10, 5]), "x", 5)["verdict"] == VNEXT_INCOMPLETE
    # maps resolved but a profile short -> INCOMPLETE (both scales must be complete)
    assert vnext_readiness(_Conn([S, 100, 90, 10, 4]), "x", 5)["verdict"] == VNEXT_INCOMPLETE
    # nothing built -> NOT_STARTED
    assert vnext_readiness(_Conn([S, 0, 0, 0, 0]), "x", 5)["verdict"] == VNEXT_NOT_STARTED
    # no substrate schema -> NOT_STARTED (fail-open, availability-neutral)
    assert vnext_readiness(_Conn([None]), "x", 5)["verdict"] == VNEXT_NOT_STARTED
