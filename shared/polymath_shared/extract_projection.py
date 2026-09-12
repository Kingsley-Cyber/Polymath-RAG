"""EXTRACT-OPERATIONAL-PROJECTION-V1 (execution authority §20A, 2026-09-12).

The ONE deterministic derivation from a stage='extract' artifact's
`payload` to its narrow operational-read columns on `artifacts`
(migration 0057). Both known writers of `stage='extract'` artifacts —
`receipts.py::StageTransaction.artifact` and `control/reconciliation.py`'s
carry-forward INSERT — call `derive_extract_projection` so a provider,
model, or contract change cannot silently create projection drift
between them (one worker correct, another stale or NULL).

Mirrors the exact semantics of the old hot readers it replaces
(`control_plane_status.py::_graph_provider`,
`document_status.py::corpus_document_summaries`):
`jsonb_exists(payload, 'llm_extraction')` for presence, then
`payload->'llm_extraction'->'stats'->>'<field>'` per counter. Presence is
KEY EXISTENCE (matching `jsonb_exists`), not "value is a dict" — a
present-but-malformed value still counts as present; its counters just
come back None rather than an invented 0.
"""
from __future__ import annotations

from typing import Any, Optional

#: Exact column order the migration (0057) and both writers agree on.
EXTRACT_PROJECTION_COLUMNS = (
    "extract_stats_present",
    "extract_llm_calls",
    "extract_entity_count",
    "extract_relation_count",
    "extract_neighborhoods_sent",
    "extract_neighborhoods_unaccounted",
    "extract_neighborhoods_dropped",
)

_STATS_FIELD_BY_COLUMN = {
    "extract_llm_calls": "calls",
    "extract_entity_count": "entities",
    "extract_relation_count": "relations",
    "extract_neighborhoods_sent": "neighborhoods_sent",
    "extract_neighborhoods_unaccounted": "neighborhoods_unaccounted",
    "extract_neighborhoods_dropped": "neighborhoods_dropped",
}


def _int_or_none(v: Any) -> Optional[int]:
    """Safe, never-raising coercion — a malformed stat reads as None (an
    honest "unknown"), never an invented 0. The old SQL `(...)::int` cast
    would raise on non-numeric input instead; every current row is a
    clean number (phase A semantic inventory, 2026-09-12), so this is a
    strict robustness improvement, not a behavior change for real data."""
    if v is None:
        return None
    if isinstance(v, bool):          # bool is an int subclass in Python; stats are never booleans
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def derive_extract_projection(payload: dict) -> dict[str, Any]:
    """`payload` is a stage='extract' artifact payload dict (native Python,
    already JSON-decoded) — the FULL payload as of this call, not
    necessarily the final merged row (callers that only ever see a
    PARTIAL payload without the `llm_extraction` key should not call this
    at all; see `extract_projection_columns_for` below)."""
    has_key = isinstance(payload, dict) and "llm_extraction" in payload
    llm = payload.get("llm_extraction") if has_key else None
    stats = llm.get("stats") if isinstance(llm, dict) else None
    stats = stats if isinstance(stats, dict) else {}
    out: dict[str, Any] = {"extract_stats_present": has_key}
    for column, field in _STATS_FIELD_BY_COLUMN.items():
        out[column] = _int_or_none(stats.get(field))
    return out


def extract_projection_columns_for(payload: dict) -> Optional[dict[str, Any]]:
    """Returns the projection dict for `payload`, or None when `payload`
    does not mention `llm_extraction` at all. `StageTransaction.artifact`
    calls this per-call (a stage may write several partial payloads that
    JSONB-merge into the final row, e.g. extract_worker.py writes
    `{"manifest": ...}` before it ever writes `{"llm_extraction": ...}`);
    None tells the caller to leave the projection columns untouched on
    this write rather than recompute a False/None state that would
    clobber a value an earlier call in the same stage already set."""
    if not isinstance(payload, dict) or "llm_extraction" not in payload:
        return None
    return derive_extract_projection(payload)
