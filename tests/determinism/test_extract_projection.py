"""EXTRACT-OPERATIONAL-PROJECTION-V1 (execution authority §20A) — the pure derivation
and both write-path integrations (receipts.py, control/reconciliation.py) that keep
`artifacts`'s narrow extract_* columns (migration 0057) from drifting away from
`payload->'llm_extraction'->'stats'`, the value they replace as the hot read.

Pure-function + fake-connection suite: no Postgres, no live fleet.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.extract_projection import (  # noqa: E402
    EXTRACT_PROJECTION_COLUMNS,
    derive_extract_projection,
    extract_projection_columns_for,
)

FULL_STATS = {
    "llm_extraction": {
        "stats": {
            "calls": 3, "entities": 42, "relations": 7,
            "neighborhoods_sent": 5, "neighborhoods_unaccounted": 1,
            "neighborhoods_dropped": 0,
        },
        "provider": "groq",
    },
}


def test_full_stats_object_derives_every_column():
    out = derive_extract_projection(FULL_STATS)
    assert out == {
        "extract_stats_present": True, "extract_llm_calls": 3, "extract_entity_count": 42,
        "extract_relation_count": 7, "extract_neighborhoods_sent": 5,
        "extract_neighborhoods_unaccounted": 1, "extract_neighborhoods_dropped": 0,
    }
    assert set(out) == set(EXTRACT_PROJECTION_COLUMNS)


def test_llm_extraction_key_absent_is_not_present_and_every_stat_is_none():
    out = derive_extract_projection({"manifest": {"doc_id": "d1"}})
    assert out["extract_stats_present"] is False
    assert all(out[c] is None for c in EXTRACT_PROJECTION_COLUMNS if c != "extract_stats_present")


def test_llm_extraction_present_but_not_a_dict_is_still_present_with_no_invented_stats():
    """Matches jsonb_exists semantics exactly: KEY existence, not value shape."""
    out = derive_extract_projection({"llm_extraction": "not-an-object"})
    assert out["extract_stats_present"] is True
    assert out["extract_entity_count"] is None


def test_stats_missing_from_a_present_llm_extraction_object():
    out = derive_extract_projection({"llm_extraction": {"provider": "groq"}})
    assert out["extract_stats_present"] is True
    assert out["extract_entity_count"] is None
    assert out["extract_llm_calls"] is None


def test_zero_is_not_confused_with_missing():
    out = derive_extract_projection({"llm_extraction": {"stats": {"entities": 0, "relations": 0}}})
    assert out["extract_entity_count"] == 0
    assert out["extract_relation_count"] == 0
    assert out["extract_llm_calls"] is None          # genuinely absent, not coerced to 0


def test_non_numeric_stat_reads_as_none_never_raises():
    out = derive_extract_projection({"llm_extraction": {"stats": {"entities": "not-a-number"}}})
    assert out["extract_entity_count"] is None


def test_empty_payload_and_non_dict_payload_are_handled():
    assert derive_extract_projection({})["extract_stats_present"] is False
    assert derive_extract_projection(None)["extract_stats_present"] is False  # type: ignore[arg-type]


def test_columns_for_returns_none_when_key_absent_and_a_dict_when_present():
    assert extract_projection_columns_for({"manifest": {}}) is None
    assert extract_projection_columns_for({"trace": {"mode": "shadow"}}) is None
    proj = extract_projection_columns_for(FULL_STATS)
    assert proj is not None and proj["extract_entity_count"] == 42


# ---------------------------------------------------------------------------------
# Write-path integration: receipts.py::_StageWrite.artifact() — a fake conn records
# the executed SQL text and params; no real Postgres involved.
# ---------------------------------------------------------------------------------

class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))


def _stage_write(conn, stage="extract"):
    from polymath_shared.receipts import _StageWrite

    return _StageWrite(conn, run_id="run-1", stage=stage, contract_hash="c1")


def test_artifact_call_without_llm_extraction_never_touches_the_projection_columns():
    conn = _FakeConn()
    w = _stage_write(conn)
    w.artifact({"manifest": {"doc_id": "d1"}})
    sql, params = conn.calls[-1]
    for col in EXTRACT_PROJECTION_COLUMNS:
        assert col not in sql, f"{col} must not appear in the SQL for a payload without llm_extraction"


def test_artifact_call_with_llm_extraction_sets_every_projection_column_both_places():
    conn = _FakeConn()
    w = _stage_write(conn)
    w.artifact(FULL_STATS)
    sql, params = conn.calls[-1]
    insert_cols, _, rest = sql.partition("VALUES")
    _, _, conflict_set = rest.partition("DO UPDATE")
    for col in EXTRACT_PROJECTION_COLUMNS:
        assert col in insert_cols, f"{col} must appear in the INSERT column list"
        assert f"{col} = EXCLUDED.{col}" in conflict_set, f"{col} must be set from EXCLUDED in ON CONFLICT"
    assert 42 in params and 7 in params and 3 in params


def test_a_later_call_without_llm_extraction_does_not_regress_an_earlier_ones_columns():
    """The real sequence in extract_worker.py: {"manifest": ...} first, then
    {"llm_extraction": ...}, then more manifest/trace-only calls after. Each call is
    independent SQL against the fake conn here (no real ON CONFLICT merge to
    exercise), so the guarantee under test is narrower but load-bearing: a
    columns-absent call must never emit SQL that could clobber the columns a prior
    call set — i.e. it must never mention them at all."""
    conn = _FakeConn()
    w = _stage_write(conn)
    w.artifact({"manifest": {"doc_id": "d1"}})
    w.artifact(FULL_STATS)
    w.artifact({"trace": {"mode": "live"}})
    first_sql, _ = conn.calls[0]
    third_sql, _ = conn.calls[2]
    for col in EXTRACT_PROJECTION_COLUMNS:
        assert col not in first_sql
        assert col not in third_sql


def test_non_extract_stage_payload_without_the_key_is_also_untouched():
    """The derivation is stage-agnostic by construction (it only looks at the
    payload dict), but no non-extract stage payload has ever carried
    llm_extraction (phase A inventory), so this documents that a doc_profile/
    doc_parent_map stage's own artifact() calls are unaffected."""
    conn = _FakeConn()
    w = _stage_write(conn, stage="doc_profile")
    w.artifact({"doc_profile": {"doc_id": "d1", "vnext": "true"}})
    sql, _ = conn.calls[-1]
    for col in EXTRACT_PROJECTION_COLUMNS:
        assert col not in sql
