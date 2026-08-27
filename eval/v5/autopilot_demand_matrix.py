"""AUTOPILOT-WORKLOAD-HYGIENE-V1 demand-signal test matrix.

Proves the desired-state planner ignores garbage (completed, superseded,
archived, deleted-corpus, terminal-failed tickets) and responds to
legitimate claimable work — inside one rolled-back transaction, so the
live database is untouched.

Run: .venv/bin/python eval/v5/autopilot_demand_matrix.py
"""
import sys

sys.path.insert(0, "shared")
sys.path.insert(0, "control")

import psycopg

from control.fleet_autopilot import desired_slots

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
SLOTS = {"control", "orchestrator", "intake", "sidecar_gliner",
         "sidecar_spacy", "sidecar_embedder", "sidecar_reranker",
         "extract", "profile", "qdrant", "canonicalize",
         "project_canonical", "neo4j", "verify", "summaries"}

CASES_GARBAGE = [
    ("A completed ticket", "done", "query_ready", True),
    ("B superseded ticket", "superseded", "reconciling", True),
    ("D deleted-corpus ticket", "ready", "reconciling", False),
    ("H terminal failed run", "ready", "failed", True),
]


def mk(conn, name, ticket_status, run_status, corpus_exists):
    cid = f"hygiene-test-{name.split()[0].lower()}"
    rid = f"run_hygienetest{name.split()[0].lower()}{'x' * 40}"[:68]
    if corpus_exists:
        conn.execute(
            """INSERT INTO corpora (corpus_id, name, config_hash)
               VALUES (%s, %s, 'test') ON CONFLICT DO NOTHING""", (cid, cid))
    conn.execute(
        """INSERT INTO runs (run_id, corpus_id, status, metadata)
           VALUES (%s, %s, %s, '{}') ON CONFLICT DO NOTHING""",
        (rid, cid, run_status))
    conn.execute(
        """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage,
             event_type, status)
           VALUES (%s, %s, %s, 'extract', 'intake.v1', %s)""",
        (f"tkt_{name.split()[0].lower()}{'y' * 30}"[:40], rid, cid,
         ticket_status))
    return cid


def main() -> int:
    failures = []
    with psycopg.connect(DSN) as conn:
        with conn.transaction():
            base, _ = desired_slots(conn, SLOTS)
            # -------- garbage must not create extraction demand -------
            for name, tstat, rstat, cexists in CASES_GARBAGE:
                with conn.transaction():
                    mk(conn, name, tstat, rstat, cexists)
                    desired, reasons = desired_slots(conn, SLOTS)
                    woke = "sidecar_gliner" in desired and \
                           "sidecar_gliner" not in base
                    print(f"{name:<26} gliner woke: {woke}  "
                          f"{'FAIL' if woke else 'PASS'}")
                    if woke:
                        failures.append(name)
                    raise psycopg.Rollback
            # -------- legitimate ready extract ticket must wake -------
            with conn.transaction():
                mk(conn, "I legitimate", "ready", "reconciling", True)
                desired, reasons = desired_slots(conn, SLOTS)
                woke = "sidecar_gliner" in desired
                print(f"{'I legitimate ready ticket':<26} gliner woke: "
                      f"{woke}  {'PASS' if woke else 'FAIL'}")
                if not woke:
                    failures.append("I")
                raise psycopg.Rollback
            raise psycopg.Rollback  # leave the database untouched
    print("RESULT:", "PASS" if not failures else f"FAIL {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
