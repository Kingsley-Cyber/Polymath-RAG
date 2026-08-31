"""Owner-triggered corpus re-ingest (REINGEST-TRIGGER-V1, Phase 0).

`reconcile_contract_drift` rescues STRANDED runs only (status
intake/reconciling/degraded with open tickets) — a healthy query_ready
run is historical, not stranded, so a deliberate generation swap
(e.g. the tier_v3 chunker) never touches it. This script is the
missing first half: it makes a corpus's live runs stranded ON PURPOSE
— status → 'reconciling', intake ticket re-armed — and then the
PROVEN pipeline does everything else on the next control tick:
reconciliation mints successors pinned to the current contract, stale
stages (chunker → intake+extract) regenerate, unchanged-dependency
stages carry, intake re-chunks from the spool (GENERATION-PURGE
removes old-contract rows per doc), the census re-arms any stage
whose receipts no longer cover the new rows, and promotion returns
the corpus to query_ready.

The claim window is safe: a worker polling the re-armed intake ticket
is refused by the era fence (the old run pins the OLD chunker), and
reconciliation supersedes the ticket on its tick.

    python scripts/reingest_corpus.py <corpus_id>            # dry run
    python scripts/reingest_corpus.py <corpus_id> --execute
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.execution import default_execution_contract  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_id")
    ap.add_argument("--execute", action="store_true",
                    help="apply (default: dry-run print)")
    args = ap.parse_args()

    current = json.dumps(default_execution_contract(), sort_keys=True)
    with psycopg.connect(get_settings().postgres.dsn,
                         connect_timeout=5) as conn:
        rows = conn.execute(
            """
            SELECT run_id, status, execution_contract::text
              FROM runs
             WHERE corpus_id = %s
               AND status IN ('query_ready', 'reconciling')
               AND superseded_by_run_id IS NULL
            """,
            (args.corpus_id,)).fetchall()
        stale = [(r, s) for r, s, pin in rows if pin != current]
        fresh = [r for r, s, pin in rows if pin == current]
        if fresh:
            print(f"already on current contract (untouched): {fresh}")
        if not stale:
            print("nothing to re-ingest: no live run pins a stale contract")
            return 0
        for run_id, status in stale:
            print(f"{'EXECUTE' if args.execute else 'DRY-RUN'}: "
                  f"{run_id} ({status}) -> reconciling + intake re-armed")
            if not args.execute:
                continue
            # DEAD-SUCCESSOR DETACH: a parked husk from a past
            # restoration (status superseded, superseded_by NULL) can
            # still occupy the one-successor pointer; reconciliation
            # would then skip this run forever (successor_pointer_
            # occupied — the 2026-08-31 control-plane wedge). Detach
            # the husk (row and evidence preserved; only the lineage
            # pointer clears) so a fresh successor can mint.
            detached = conn.execute(
                "UPDATE runs SET supersedes_run_id=NULL, updated_at=now() "
                "WHERE supersedes_run_id=%s AND status='superseded' "
                "AND superseded_by_run_id IS NULL", (run_id,)).rowcount
            if detached:
                print(f"  dead successor husks detached: {detached}")
            conn.execute(
                "UPDATE runs SET status='reconciling', updated_at=now() "
                "WHERE run_id=%s AND status='query_ready'", (run_id,))
            armed = conn.execute(
                "UPDATE stage_tickets SET status='ready', updated_at=now() "
                "WHERE run_id=%s AND stage='intake' AND status<>'ready'",
                (run_id,)).rowcount
            print(f"  intake tickets re-armed: {armed}")
        if args.execute:
            conn.commit()
            print("done — the next control tick reconciles these runs; "
                  "watch runs/chunks until the successors are query_ready")
        else:
            conn.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
