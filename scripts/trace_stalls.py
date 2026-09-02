"""STALL-TRACER-V1 operator view: what is stuck right now, and why.

    .venv/bin/python scripts/trace_stalls.py            # open traces + live collect
    .venv/bin/python scripts/trace_stalls.py --live     # live collect only (read-only)
    .venv/bin/python scripts/trace_stalls.py --threshold 60

Read-only: the live collect runs the control plane's own diagnosis in a
transaction that is rolled back, so it can be pointed at a running fleet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("shared", "control"):
    sys.path.insert(0, str(ROOT / sub))

import psycopg  # noqa: E402

from polymath_shared.settings import get_settings  # noqa: E402
from control.stall_tracer import (STALL_THRESHOLD_S, collect_stalls,  # noqa: E402
                                  fleet_slots_alive)


def _control_heartbeat(conn) -> str:
    row = conn.execute(
        "SELECT owner_id, extract(epoch FROM now() - last_seen_at)::int "
        "FROM control_owners ORDER BY last_seen_at DESC LIMIT 1").fetchone()
    if not row:
        return "control plane: no owner row (never ticked)"
    return f"control plane: owner {row[0][:12]} last seen {row[1]} s ago"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="skip the stored traces")
    ap.add_argument("--threshold", type=int, default=None)
    args = ap.parse_args()
    threshold = args.threshold or int(getattr(
        get_settings().control, "stall_threshold_s", STALL_THRESHOLD_S))

    with psycopg.connect(get_settings().postgres.dsn, autocommit=False) as conn:
        print(_control_heartbeat(conn))
        if not args.live:
            rows = conn.execute(
                """SELECT unit_kind, unit_id, stage, age_s, diagnosis, detail,
                          first_traced_at, last_traced_at
                     FROM stall_traces WHERE resolved_at IS NULL
                    ORDER BY first_traced_at""").fetchall()
            print(f"stored open traces: {len(rows)}")
            for kind, uid, stage, age, diag, detail, first, last in rows:
                print(f"  {kind:11s} {uid[:44]:44s} {stage or '-':18s} {age:>6d}s "
                      f"{diag}  (since {first:%H:%M:%S}, last {last:%H:%M:%S})")
                print(f"      {json.dumps(detail, default=str)[:300]}")
        stalls = collect_stalls(conn, threshold_s=threshold,
                                slots_alive=fleet_slots_alive())
        conn.rollback()
    print(f"live collect (threshold {threshold} s): {len(stalls)} stalled unit(s)")
    for s in stalls:
        print(f"  {s.unit_kind:11s} {s.unit_id[:44]:44s} {s.stage or '-':18s} "
              f"{s.age_s:>6d}s {s.diagnosis}")
        print(f"      {json.dumps(s.detail, default=str)[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
