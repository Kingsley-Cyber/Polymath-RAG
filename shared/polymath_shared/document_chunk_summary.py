"""DOCUMENT-CHUNK-SUMMARY-V1 (execution authority follow-up to §20A, 2026-09-12).

The one deterministic derivation from a document's chunk rows to its narrow
operational summary (migration 0058) — child/parent/map-eligible counts,
replacing `document_status.py::corpus_document_summaries`'s two `COUNT(*) ...
GROUP BY` scans over the full `chunks` table (proportional to a corpus's raw
chunk volume: ~150ms on `cinema`, which owns 87% of the table's 96k rows).

Computed from the SAME `children`/`parents` row lists `intake_worker.py` already
builds immediately after inserting a document's chunks (for the `routing_card`
artifact) — no new query against `chunks` is needed to populate it.
"""
from __future__ import annotations

from polymath_shared.document_region import is_noisy


def compute_chunk_summary(children: list[dict], parents: list[dict]) -> dict:
    """`children`/`parents` are chunk row dicts already filtered by tier (as
    intake_worker.py already produces them) — each needs at least
    `region_role` (parents only). Mirrors the exact semantics of the old
    reader's `tier='parent' AND COALESCE(region_role,'') <> ALL(noisy_roles)`:
    `is_noisy(None)` is False (an absent role is never noisy — legacy-safety
    rule v3.3), so a parent with no region_role is counted eligible, same as
    the old COALESCE-to-empty-string comparison was."""
    map_eligible = sum(1 for p in parents if not is_noisy(p.get("region_role")))
    return {
        "child_count": len(children),
        "parent_count": len(parents),
        "map_eligible_count": map_eligible,
    }
