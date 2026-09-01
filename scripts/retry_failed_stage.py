"""Owner strike-reset for a SAME-contract retry (RETRY-TOOL-V1).

A ticket goes 'failed' when its attempts budget is exhausted — the
control plane is REFUSING, not lagging, and that refusal is right
until the failure's cause is fixed. When the fix lands WITHOUT a
contract change (so no successor mints a fresh budget — e.g. the
2026-09-01 413 storm fixed by THROUGHPUT-V2 dispatch), this is the
first-class reset: status → ready, attempt → 0, lease cleared. The
stage_attempts audit rows are never touched. Contract-DRIFT retries
need no tool at all: successors always mint fresh budgets
(FRESH-BUDGET invariant, pinned in test_reconciliation_convergence).

    python scripts/retry_failed_stage.py <corpus_id> <stage>            # dry run
    python scripts/retry_failed_stage.py <corpus_id> <stage> --execute
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.settings import get_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_id")
    ap.add_argument("stage")
    ap.add_argument("--execute", action="store_true",
                    help="apply (default: dry-run print)")
    args = ap.parse_args()
    with psycopg.connect(get_settings().postgres.dsn,
                         connect_timeout=5) as conn:
        rows = conn.execute(
            """SELECT t.ticket_id, t.run_id, t.attempt
                 FROM stage_tickets t JOIN runs r ON r.run_id = t.run_id
                WHERE r.corpus_id = %s AND t.stage = %s
                  AND t.status = 'failed'""",
            (args.corpus_id, args.stage)).fetchall()
        if not rows:
            print(f"no failed {args.stage!r} tickets in {args.corpus_id!r}")
            return 0
        for tid, run_id, attempt in rows:
            print(f"{'EXECUTE' if args.execute else 'DRY-RUN'}: "
                  f"{run_id[-12:]} {args.stage} (attempts spent: "
                  f"{attempt}) -> ready, budget reset")
            if args.execute:
                conn.execute(
                    """UPDATE stage_tickets SET status='ready', attempt=0,
                           lease_owner=NULL, lease_expires_at=NULL,
                           updated_at=now()
                        WHERE ticket_id=%s AND status='failed'""", (tid,))
        conn.commit() if args.execute else conn.rollback()
        if args.execute:
            print("done — workers claim on their next poll")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
