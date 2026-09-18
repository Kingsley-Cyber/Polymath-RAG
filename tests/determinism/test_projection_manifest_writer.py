"""PROJECTION-LIFECYCLE-V1 (P1/P2 slice b) — the lifecycle-aware writer over the
projection_receipts manifest: back-compatible legacy claims, PROJECTED/PENDING/FAILED
transitions, and the manifest read helper. Fake connection (no live DB)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import receipts as R  # noqa: E402


class _Cur:
    def __init__(self, row=None): self._row = row
    def fetchone(self): return self._row


class FakeConn:
    def __init__(self, row=None): self.calls = []; self._row = row
    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params)); return _Cur(self._row)


def _claim(conn):
    # calls[0] = the immutable attempt; calls[1] = the projection_receipts claim
    return conn.calls[1]


def test_legacy_call_writes_no_lifecycle_columns_and_is_migration_independent():
    conn = FakeConn()
    R.record_projection_attempt(conn, projection="qdrant", entity_kind="chunk", entity_id="c1", receipt_hash="h")
    sql, params = _claim(conn)
    assert "state" not in sql and "artifact_hash" not in sql          # legacy INSERT — no new columns
    assert params == ("qdrant", "chunk", "c1", "h")


def test_projected_claim_writes_lifecycle_columns_and_is_active():
    conn = FakeConn()
    R.record_projection_attempt(conn, projection="qdrant", entity_kind="doc_profile", entity_id="d1",
                                receipt_hash="ph", state="PROJECTED", artifact_hash="ah",
                                observed_ref="pointid", projection_version="doc-profile-projection-v1")
    sql, params = _claim(conn)
    assert "state" in sql and "artifact_hash" in sql and "observed_ref" in sql
    # (projection, kind, id, receipt_hash, active, state, artifact_hash, projection_version, observed_ref)
    assert params[4] is True and params[5] == "PROJECTED" and params[6] == "ah" and params[8] == "pointid"


def test_pending_claim_is_not_active():
    conn = FakeConn()
    R.record_projection_attempt(conn, projection="neo4j", entity_kind="doc_profile", entity_id="d2",
                                receipt_hash="", state="PENDING", artifact_hash="ah")
    _sql, params = _claim(conn)
    assert params[4] is False and params[5] == "PENDING"              # PENDING is intended, not present


def test_mark_failed_sets_failed_inactive_with_the_error():
    conn = FakeConn()
    R.mark_projection_failed(conn, projection="qdrant", entity_kind="doc_profile", entity_id="d3",
                             error="embedder timeout", projection_version="v1")
    sql, params = conn.calls[0]
    assert "'FAILED'" in sql and "active" in sql.lower()
    assert params == ("qdrant", "doc_profile", "d3", "v1", "embedder timeout")


def test_manifest_row_reads_the_current_state_or_none():
    row = ("qdrant", "doc_profile", "d1", "ph", "ah", "v1", "pointid", "PROJECTED", True, None, "ts")
    m = R.projection_manifest_row(FakeConn(row=row), projection="qdrant", entity_kind="doc_profile", entity_id="d1")
    assert m["state"] == "PROJECTED" and m["observed_ref"] == "pointid" and m["artifact_hash"] == "ah"
    assert R.projection_manifest_row(FakeConn(row=None), projection="q", entity_kind="k", entity_id="x") is None
