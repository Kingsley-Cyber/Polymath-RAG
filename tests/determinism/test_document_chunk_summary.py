"""DOCUMENT-CHUNK-SUMMARY-V1 (execution authority follow-up to §20A) — the pure
derivation (`compute_chunk_summary`) that replaces `document_status.py::
corpus_document_summaries`'s two `COUNT(*) ... GROUP BY` scans over the full
`chunks` table with a narrow per-document projection (migration 0058), populated
at the SAME write time `intake_worker.py` already computes `children`/`parents`
for its `routing_card` artifact — no new query against `chunks` on the write path.

Pure-function suite: no Postgres.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_chunk_summary import compute_chunk_summary  # noqa: E402


def test_counts_children_and_parents():
    children = [{"region_role": None}, {"region_role": None}, {"region_role": None}]
    parents = [{"region_role": None}]
    out = compute_chunk_summary(children, parents)
    assert out == {"child_count": 3, "parent_count": 1, "map_eligible_count": 1}


def test_noisy_parent_is_not_map_eligible():
    parents = [{"region_role": "front_matter"}, {"region_role": None}]
    out = compute_chunk_summary([], parents)
    assert out["parent_count"] == 2
    assert out["map_eligible_count"] == 1


def test_missing_region_role_key_is_never_noisy():
    """A parent dict with no 'region_role' key at all (not even None) must not
    crash and must count as eligible — matches the old reader's
    COALESCE(region_role,'') semantics for a NULL column."""
    out = compute_chunk_summary([], [{}])
    assert out["map_eligible_count"] == 1


def test_empty_document_is_all_zero():
    assert compute_chunk_summary([], []) == {
        "child_count": 0, "parent_count": 0, "map_eligible_count": 0}


def test_all_parents_noisy_gives_zero_eligible_but_nonzero_parent_count():
    from polymath_shared.document_region import NOISY_ROLES

    parents = [{"region_role": r} for r in NOISY_ROLES]
    out = compute_chunk_summary([], parents)
    assert out["parent_count"] == len(NOISY_ROLES)
    assert out["map_eligible_count"] == 0
