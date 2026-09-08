#!/usr/bin/env python
"""VNEXT-READINESS-REPORT-V1 — report-only parent-map backfill completeness.

Slice S11 (report-only first) of RETRIEVAL-MIGRATION-DEPENDENCY-V1: the availability-
neutral verifier/readiness VIEW (plan §2 `document_retrieval_readiness`, §16 backfill
completeness report, §19 readiness floor `unresolved_eligible_parents = 0`). It reads
DURABLE state only (no writes, no models, no network, no availability effect) and
answers the goal's standing question: *what is still on the legacy contract, and how
much of the vNext parent-map substrate is actually built?*

It preserves the GENERATION INVARIANT framing: a document is vNext-map-complete only
when EVERY retrieval-eligible parent has an active map OR an explicit exclusion; a
partially-mapped document is NOT complete (never an accidental legacy/vNext mixture).

    .venv/bin/python scripts/vnext_readiness_report.py --corpus <id>
    .venv/bin/python scripts/vnext_readiness_report.py            # every corpus
    .venv/bin/python scripts/vnext_readiness_report.py --json

Read-only; `scripts/` is fence-free. Complementary to `semantic_readiness.py`
(SEMANTIC-READINESS-V1, the legacy semantic-lane verdict) — this is the vNext parent-
map view; both are readiness VIEWS, not schedulers. Eligibility defers to the single
region-role authority `document_region.NOISY_ROLES` (same rule as the skeleton).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(_p))

from polymath_shared import document_region  # noqa: E402

# Per-document parent-map states (a report-only subset of plan §2's semantic states).
NO_ELIGIBLE_PARENTS = "NO_ELIGIBLE_PARENTS"
NOT_STARTED = "NOT_STARTED"
MAP_PARTIAL = "MAP_PARTIAL"
MAP_COMPLETE = "MAP_COMPLETE"


def document_state(eligible: int, mapped: int, excluded: int) -> str:
    """Pure classification. MAP_COMPLETE == every eligible parent is resolved
    (mapped OR explicitly excluded) — the §19 floor unresolved_eligible_parents == 0.
    A document with mapped>0 but unresolved>0 is MAP_PARTIAL, never complete (the
    generation invariant: no partial vNext generation counts as ready)."""
    if eligible <= 0:
        return NO_ELIGIBLE_PARENTS
    resolved = mapped + excluded
    if resolved <= 0:
        return NOT_STARTED
    if resolved >= eligible:
        return MAP_COMPLETE
    return MAP_PARTIAL


def backfill_report(conn, corpus_id: str) -> dict:
    """One deterministic read of the vNext parent-map substrate for a corpus."""
    doc_ids = [r[0] for r in conn.execute(
        "SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus_id,)).fetchall()]
    total = len(doc_ids)
    legacy_ready = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status='query_ready'",
        (corpus_id,)).fetchone()[0]
    if not doc_ids:
        return {"contract": "vnext-readiness-report-v1", "corpus_id": corpus_id,
                "total_documents": 0, "legacy_query_ready_runs": legacy_ready,
                "documents_by_state": {}, "parents": {}, "map_batches_by_status": {},
                "map_contracts": [], "vnext_maps_complete_documents": 0}

    noisy = list(document_region.NOISY_ROLES)
    eligible = dict(conn.execute(
        "SELECT c.doc_id, COUNT(*) FROM chunks c JOIN documents d ON d.doc_id=c.doc_id "
        "WHERE d.corpus_id=%s AND c.tier='parent' AND COALESCE(c.region_role,'') <> ALL(%s) "
        "GROUP BY c.doc_id", (corpus_id, noisy)).fetchall())
    mapped = dict(conn.execute(
        "SELECT doc_id, COUNT(DISTINCT parent_id) FROM document_parent_maps "
        "WHERE doc_id = ANY(%s) AND active GROUP BY doc_id", (doc_ids,)).fetchall())
    excluded = dict(conn.execute(
        "SELECT doc_id, COUNT(*) FROM document_parent_exclusions "
        "WHERE doc_id = ANY(%s) GROUP BY doc_id", (doc_ids,)).fetchall())
    batches = dict(conn.execute(
        "SELECT status, COUNT(*) FROM document_parent_map_batches "
        "WHERE doc_id = ANY(%s) GROUP BY status", (doc_ids,)).fetchall())
    contracts = [r[0] for r in conn.execute(
        "SELECT DISTINCT map_contract FROM document_parent_maps WHERE doc_id = ANY(%s)",
        (doc_ids,)).fetchall()]

    states = {NO_ELIGIBLE_PARENTS: 0, NOT_STARTED: 0, MAP_PARTIAL: 0, MAP_COMPLETE: 0}
    tot_elig = tot_map = tot_excl = 0
    for d in doc_ids:
        e, m, x = eligible.get(d, 0), mapped.get(d, 0), excluded.get(d, 0)
        states[document_state(e, m, x)] += 1
        tot_elig += e
        tot_map += m
        tot_excl += x
    return {
        "contract": "vnext-readiness-report-v1",
        "corpus_id": corpus_id,
        "total_documents": total,
        "legacy_query_ready_runs": legacy_ready,
        "documents_by_state": states,
        "vnext_maps_complete_documents": states[MAP_COMPLETE],
        "parents": {
            "eligible": tot_elig, "mapped": tot_map, "excluded": tot_excl,
            "unresolved": max(0, tot_elig - tot_map - tot_excl),
        },
        "map_batches_by_status": batches,
        "map_contracts": sorted(contracts),
    }


def _corpora(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT corpus_id FROM corpora ORDER BY corpus_id").fetchall()]


def _print(rep: dict) -> None:
    p = rep["parents"]
    print(f"[{rep['corpus_id']}] docs={rep['total_documents']} "
          f"legacy_query_ready_runs={rep['legacy_query_ready_runs']}")
    print(f"    parent-map states: {rep['documents_by_state']}  "
          f"vnext_complete={rep['vnext_maps_complete_documents']}")
    print(f"    parents: eligible={p.get('eligible',0)} mapped={p.get('mapped',0)} "
          f"excluded={p.get('excluded',0)} unresolved={p.get('unresolved',0)}")
    if rep["map_batches_by_status"]:
        print(f"    map batches: {rep['map_batches_by_status']}  contracts={rep['map_contracts']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report-only vNext parent-map backfill completeness.")
    ap.add_argument("--corpus", help="one corpus id (default: every corpus)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        from polymath_shared.db import tx
        with tx() as conn:
            if conn.execute("SELECT to_regclass('public.document_parent_maps')").fetchone()[0] is None:
                print("migration 0054 not applied; nothing to report", file=sys.stderr)
                return 0
            corpora = [args.corpus] if args.corpus else _corpora(conn)
            reports = [backfill_report(conn, c) for c in corpora]
    except Exception as exc:  # pragma: no cover - environment gate
        print(f"database unavailable: {exc}", file=sys.stderr)
        return 0
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for rep in reports:
            _print(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
