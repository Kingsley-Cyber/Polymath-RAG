#!/usr/bin/env python
"""CLAIM-SETS-RETIREMENT-V1 — the prepared, owner-gated last step of the `claim_sets`
retirement (register 11.218 proved it DEAD_PROVEN; §11's retirement law reserves
"DELETE STATE/SCHEMA" for "rollback window + owner authority").

WHY THIS IS A SCRIPT AND NOT A MIGRATION
`make db-migrate` loops over EVERY `stores/postgres/migrations/*.sql` unconditionally
(Makefile:28-32 — there is no applied-migration tracking despite the target's comment).
A `00NN_drop_claim_sets.sql` file would therefore FIRE on the next routine `make migrate`
anyone runs, with no separate authorization step — arming a destructive action while
appearing to merely prepare it. A script is inert until someone deliberately passes
`--execute`.

WHAT IT DOES
Default (no flags) is READ-ONLY and re-proves the retirement from scratch, live, at the
moment of running -- it never trusts the days-old audit:

    1. the table still exists
    2. it is still empty                        (SELECT count(*))
    3. it has never been written                (pg_stat_user_tables ins/upd/del = 0)
    4. no tracked source file references it     (git grep, excluding its own migration,
                                                 this script, and docs/tests)

Only if ALL FOUR still hold does it print the exact DROP it would run. `--execute`
performs it inside a transaction, after re-running the same four checks — so a race
(someone starts using the table between authorization and execution) aborts instead of
destroying state.

    .venv/bin/python scripts/retire_claim_sets.py              # re-prove, print, change nothing
    .venv/bin/python scripts/retire_claim_sets.py --execute    # OWNER-AUTHORIZED drop

ROLLBACK: the table is empty by proof, so recreation is the original DDL verbatim
(stores/postgres/migrations/0026_identity_model.sql:28-35), reprinted by this script
before it drops anything.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

TABLE = "claim_sets"

#: The original DDL, verbatim from 0026_identity_model.sql — the rollback.
ORIGINAL_DDL = """CREATE TABLE IF NOT EXISTS claim_sets (
    claim_set_id TEXT PRIMARY KEY,
    subject_id   TEXT NOT NULL,
    predicate    TEXT NOT NULL,
    claims       JSONB NOT NULL,   -- [{value, evidence:[...]}]
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (subject_id, predicate)
);"""

#: Paths whose mention of the table is NOT a live reader/writer: the migration that
#: created it, this script, and this script's own registry entry (which necessarily
#: describes the table it retires). Prose under docs/ and tests/ is filtered
#: separately. Everything else counts against the retirement.
#:
#: The census also matches on a WORD boundary (`git grep -w`). Without it this
#: script's own FILENAME — retire_claim_sets.py — matched as a "reference" wherever
#: the file is registered, so registering the tool made it permanently refuse to run
#: (observed 2026-09-12 by FINAL-STATE-VERIFIER-V1). Fail-closed was the safe
#: direction, but it would have blocked a legitimately authorized deletion forever.
_ALLOWED = ("stores/postgres/migrations/0026_identity_model.sql",
            "scripts/retire_claim_sets.py",
            "scripts/README.md")


def dsn() -> str:
    return os.environ["POLYMATH_PG_DSN"]


def _exists(conn) -> bool:
    return conn.execute("SELECT to_regclass(%s) IS NOT NULL", (TABLE,)).fetchone()[0]


def _rowcount(conn) -> int:
    return conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]


def _write_stats(conn) -> dict:
    row = conn.execute(
        "SELECT n_tup_ins, n_tup_upd, n_tup_del, seq_scan, idx_scan "
        "FROM pg_stat_user_tables WHERE relname = %s", (TABLE,)).fetchone()
    if not row:
        return {"present_in_stats": False}
    ins, upd, dele, seq, idx = row
    return {"present_in_stats": True, "inserts": ins, "updates": upd, "deletes": dele,
            "seq_scans": seq, "idx_scans": idx}


#: A reader/writer is SQL that actually touches the table — not prose that names it.
#: Matching bare mentions turned this census into whack-a-mole: it flagged the script's
#: own filename, then its registry entry, then FINAL-STATE-VERIFIER-V1 merely for naming
#: the gate. Each time the "fix" was another allow-list entry, which is the wrong shape:
#: any future governance doc or tool that discusses the retirement would break it again.
#: So match the SQL context instead — FROM/JOIN/INTO/UPDATE/DELETE FROM/TABLE <name>.
_SQL_CONTEXT = r"(FROM|JOIN|INTO|UPDATE|TABLE)[[:space:]]+" + TABLE


#: POSITIVE CONTROL for the census. `chunks` is referenced by real SQL all over the
#: repository, so the same pattern shape MUST find it. Without this, a census that
#: silently matches nothing — a regex the local grep does not support, a wrong cwd, a
#: renamed pattern — is indistinguishable from "no code references the table", and that
#: reading is what authorises the DROP.
_CONTROL_TABLE = "chunks"


def _census(table: str) -> list[str]:
    pattern = r"(FROM|JOIN|INTO|UPDATE|TABLE)[[:space:]]+" + table
    try:
        res = subprocess.run(["git", "grep", "-lEi", "--", pattern],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"census failed ({type(exc).__name__}: {exc}) — refusing to proceed")
    return [l.strip() for l in res.stdout.splitlines() if l.strip()]


def _code_references() -> list[str]:
    """Tracked files whose SQL actually reads or writes the table.

    Prose under docs/ and tests/, this script, and its registry entry are excluded by
    path; everything else must contain a real SQL reference to count."""
    control = _census(_CONTROL_TABLE)
    if not control:
        raise SystemExit(
            f"census self-test FAILED: the same pattern finds no reference to "
            f"`{_CONTROL_TABLE}`, which the repository certainly does reference. The "
            f"census machinery is broken (unsupported regex? wrong cwd?), so its empty "
            f"result for {TABLE} proves nothing — refusing to proceed.")
    hits = _census(TABLE)
    return [h for h in hits
            if h not in _ALLOWED
            and not h.startswith("docs/")
            and not h.startswith("tests/")]


def reprove(conn) -> tuple[bool, dict]:
    """The four live checks. Returns (all_hold, findings)."""
    findings: dict = {}
    findings["exists"] = _exists(conn)
    if not findings["exists"]:
        findings["verdict"] = "ALREADY GONE — nothing to do"
        return False, findings
    findings["rows"] = _rowcount(conn)
    findings["write_stats"] = _write_stats(conn)
    findings["code_references"] = _code_references()

    ws = findings["write_stats"]
    # ABSENT statistics are not evidence of no writes. `pg_stat_user_tables` loses a row
    # after `pg_stat_reset()`, on a replica, or for a schema this query does not cover —
    # and the old code read "no statistics" as "never written", which is NOT_TESTED
    # counted as green (§18) on the one verdict that authorises an irreversible DROP.
    if not ws.get("present_in_stats"):
        findings["verdict"] = ("UNPROVEN — no row in pg_stat_user_tables for this table, "
                               "so 'never written' cannot be established (stats reset? "
                               "replica? different schema?). Refusing to call it dead.")
        return False, findings
    never_written = ((ws.get("inserts") or 0) == 0 and (ws.get("updates") or 0) == 0
                     and (ws.get("deletes") or 0) == 0)
    holds = (findings["rows"] == 0 and never_written and not findings["code_references"])
    findings["verdict"] = ("DEAD_PROVEN still holds — safe to drop on authorization"
                           if holds else
                           "PROOF NO LONGER HOLDS — do NOT drop; investigate")
    return holds, findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--execute", action="store_true",
                    help="OWNER-AUTHORIZED: actually DROP the table (default: prove only)")
    a = ap.parse_args()

    conn = psycopg.connect(dsn(), autocommit=True)
    holds, f = reprove(conn)

    print(f"table                {TABLE}")
    print(f"exists               {f.get('exists')}")
    if f.get("exists"):
        print(f"rows                 {f.get('rows')}")
        ws = f.get("write_stats") or {}
        print(f"lifetime ins/upd/del {ws.get('inserts')}/{ws.get('updates')}/{ws.get('deletes')}")
        print(f"code references      {f.get('code_references') or 'NONE'}")
    print(f"\nVERDICT  {f['verdict']}")

    if not f.get("exists"):
        return 0
    if not holds:
        print("\nRefusing to drop: the retirement proof does not currently hold.")
        return 1

    print("\nRollback DDL (the table is empty by proof, so this is a complete restore):")
    print("\n".join("    " + l for l in ORIGINAL_DDL.splitlines()))
    print(f"\nStatement that would run:\n    DROP TABLE {TABLE};")

    if not a.execute:
        print("\nDRY RUN — nothing dropped. Re-run with --execute ONLY with owner "
              "authorization (§1: destructive production schema deletion).")
        return 0

    # Re-prove inside the transaction: a race between authorization and execution aborts.
    with psycopg.connect(dsn()) as w:
        ok, f2 = reprove(w)
        if not ok:
            print(f"\nABORTED at execution time — {f2['verdict']}")
            return 1
        w.execute(f"DROP TABLE {TABLE}")
        w.commit()
    print(f"\nDROPPED {TABLE}. Rollback = the DDL printed above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
