"""PROJECTION-LIFECYCLE-V1 migration (P1/P2) — CAPACITY ONLY: 0065 must extend the existing
projection_receipts manifest additively, with no destructive or fabricating operation, and
must never open a second projection authority. (Asserts SQL properties; does not apply DDL.)"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "stores/postgres/migrations/0065_projection_lifecycle.sql"


def test_extends_projection_receipts_additively_with_the_lifecycle_columns():
    up = MIG.read_text().upper()
    for col in ("STATE", "ARTIFACT_HASH", "PROJECTION_VERSION", "OBSERVED_REF", "ERROR", "UPDATED_AT"):
        assert f"ADD COLUMN IF NOT EXISTS {col}" in up, col
    assert "ALTER TABLE PROJECTION_RECEIPTS" in up
    assert "PROJECTION_RECEIPTS_STATE_IDX" in up


def test_constrains_state_to_the_four_lifecycle_values():
    up = MIG.read_text().upper()
    assert "CHECK (STATE IN (" in up
    for v in ("'PENDING'", "'PROJECTED'", "'STALE'", "'FAILED'"):
        assert v in up


def test_is_capacity_only_no_destructive_or_fabricating_ops():
    up = MIG.read_text().upper()
    for banned in ("DROP TABLE", "DROP COLUMN", "DELETE FROM", "TRUNCATE"):
        assert banned not in up, banned
    updates = [" ".join(l.split()) for l in up.splitlines() if l.strip().startswith("UPDATE ")]
    assert len(updates) == 1                                   # exactly ONE backfill
    assert "SET STATE = 'STALE'" in updates[0] and "WHERE NOT ACTIVE" in updates[0]   # faithful active→STALE relabel


def test_targets_the_existing_manifest_never_a_second_authority():
    up = MIG.read_text().upper()
    assert "CREATE TABLE" not in up                            # extends, never a parallel authority
