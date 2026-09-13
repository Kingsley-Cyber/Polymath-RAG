"""EXTRACT-OPERATIONAL-PROJECTION-V1 backfill (execution authority §20A phase E).

Populates the narrow extract_* columns (migration 0057) on existing
stage='extract' `artifacts` rows from their `payload`, using the exact
same `derive_extract_projection` the live write path
(receipts.py::_StageWrite.artifact, control/reconciliation.py) now calls
going forward — so a backfilled row and a freshly-written row are
computed identically, by construction.

Bounded, resumable, idempotent: selects only rows with
`extract_stats_present IS NULL` (never yet backfilled), in batches, and
commits per batch. Re-running after completion touches zero rows. Never
writes to `payload` — the full extraction artifact stays untouched.

Usage:
    .venv/bin/python scripts/backfill_extract_projection.py [--batch-size N] [--dry-run]

Owner: governance. Reads: artifacts (stage='extract'). Writes: artifacts
narrow extract_* columns only. Safe mode: --dry-run computes and reports
without writing. Verifier: scripts/verify_extract_projection_parity.py.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from polymath_shared.extract_projection import (  # noqa: E402
    EXTRACT_PROJECTION_COLUMNS,
    derive_extract_projection,
)


def backfill(conn: psycopg.Connection, *, batch_size: int = 200, dry_run: bool = False) -> dict:
    """Keyset-paginated on `artifact_id` (not OFFSET, not "re-select the NULL rows"):
    dry-run never writes, so a re-select of `extract_stats_present IS NULL` would
    return the same rows forever and never terminate. `artifact_id > last_seen`
    advances regardless of whether this call is mutating anything."""
    total = {"processed": 0, "updated": 0, "already_done": 0, "errors": 0}
    set_clause = ", ".join(f"{c} = %s" for c in EXTRACT_PROJECTION_COLUMNS)
    last_seen = ""
    while True:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT artifact_id, payload FROM artifacts "
                "WHERE stage='extract' AND extract_stats_present IS NULL AND artifact_id > %s "
                "ORDER BY artifact_id LIMIT %s",
                (last_seen, batch_size),
            )
            rows = cur.fetchall()
        if not rows:
            break
        last_seen = rows[-1][0]
        for artifact_id, payload in rows:
            total["processed"] += 1
            try:
                projection = derive_extract_projection(payload)
            except Exception as exc:  # noqa: BLE001 — stop on ambiguity, never invent a value
                total["errors"] += 1
                print(f"ERROR artifact_id={artifact_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE artifacts SET {set_clause} WHERE artifact_id = %s",
                        (*[projection[c] for c in EXTRACT_PROJECTION_COLUMNS], artifact_id),
                    )
            total["updated"] += 1
        if not dry_run:
            conn.commit()
        else:
            conn.rollback()
        print(f"batch done: processed={total['processed']} updated={total['updated']} "
              f"errors={total['errors']}", flush=True)
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true", help="compute and report, write nothing")
    args = ap.parse_args()

    dsn = os.environ["POLYMATH_PG_DSN"]
    conn = psycopg.connect(dsn)
    try:
        result = backfill(conn, batch_size=args.batch_size, dry_run=args.dry_run)
    finally:
        conn.close()
    print(f"DONE: {result}")
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
