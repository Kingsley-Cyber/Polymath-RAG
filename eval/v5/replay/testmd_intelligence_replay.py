"""TEST.md INTELLIGENCE REPLAY — production functions, zero pollution.

Runs the REAL extract stage (GLiNER -> rescue -> admission -> mentions
-> candidates -> compiler v2 frame lane -> F-gates -> decisions) for
TEST.md's successor run inside a single Postgres transaction that is
ROLLED BACK after measurement. The live drain never sees it.

Env scoped to THIS PROCESS ONLY:
  POLYMATH_RELATION_PIPELINE=kimi_v1
  POLYMATH_PREDICATE_V2=shadow

Outputs the OBJECTIVE_1 measurement set: entities by admission class,
candidate funnel, admitted facts w/ provenance, rejected w/ reason,
evidence support.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))

os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"
os.environ["POLYMATH_PREDICATE_V2"] = "shadow"
os.environ["POLYMATH_SYNTAX_PROVIDER"] = "spacy"
os.environ.setdefault(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

import psycopg  # noqa: E402

RUN_ID = "run_3f7954d5df151520336a53f0acaadc55d240737716f6896bc4671046457b7dc4"


def main() -> dict:
    # import AFTER env so cached settings see the replay configuration
    from polymath_shared.db import tx  # noqa: F401 (pattern reference)
    from workers.extract_worker import process_event

    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False)
    conn.execute("SET lock_timeout='10s'")
    cur = conn.cursor()

    cur.execute("""
        SELECT event_type, payload::text, idempotency_key
          FROM outbox_events WHERE run_id=%s AND event_type='chunked.v1'
         ORDER BY event_id LIMIT 1""", (RUN_ID,))
    row = cur.fetchone()
    if row:
        event = {"run_id": RUN_ID, "event_type": row[0],
                 "payload": json.loads(row[1]), "idempotency_key": row[2]}
    else:
        # lineage-root originals live on ancestor runs; extract needs only
        # doc_id — synthesize the anchor from the corpus document row
        cur.execute("""
            SELECT d.doc_id, d.corpus_id FROM runs r
              JOIN documents d ON d.corpus_id=r.corpus_id
             WHERE r.run_id=%s AND d.source_name ILIKE %s
             LIMIT 1""", (RUN_ID, "%TEST.md%"))
        doc = cur.fetchone()
        if not doc:
            raise SystemExit("TEST.md document not found for run lineage")
        event = {"run_id": RUN_ID, "event_type": "chunked.v1",
                 "payload": {"run_id": RUN_ID, "doc_id": doc[0],
                             "corpus_id": doc[1]},
                 "idempotency_key": "replay-synthetic"}

    print(f"replaying extract for {RUN_ID[:20]}… "
          f"doc={event['payload'].get('doc_id', '?')[:16]}")

    process_event(conn, event)

    # ---- measure INSIDE the transaction --------------------------------
    doc_id = event["payload"]["doc_id"]

    mentions = cur.execute("""
        SELECT admission_class, count(*) FROM mentions WHERE doc_id=%s
        GROUP BY 1""", (doc_id,)).fetchall()
    rpe = cur.execute("""
        SELECT count(*) FROM raw_predicate_evidence WHERE doc_id=%s
        """, (doc_id,)).fetchone()[0]
    cands = cur.execute("""
        SELECT decision, reason, predicate, subject_surface, object_surface,
               trigger_surface, evidence_class
          FROM relation_candidates WHERE doc_id=%s
        """, (doc_id,)).fetchall()
    facts = cur.execute("""
        SELECT f.predicate, f.subject_id, f.object_id
          FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
         WHERE ev.doc_id=%s GROUP BY 1,2,3""", (doc_id,)).fetchall()
    evidence_n = cur.execute("""
        SELECT count(*) FROM evidence WHERE doc_id=%s""", (doc_id,)).fetchone()[0]

    result = {
        "mode": {"pipeline": os.environ["POLYMATH_RELATION_PIPELINE"],
                 "predicate": os.environ["POLYMATH_PREDICATE_V2"]},
        "entities_by_admission_class": {k: v for k, v in mentions},
        "raw_predicate_evidence": rpe,
        "candidates_total": len(cands),
        "candidates_by_decision": {},
        "admitted_facts": [{"predicate": p} for p, s, o in facts],
        "facts_admitted": len(facts),
        "evidence_rows": evidence_n,
        "rejected": [
            {"subject": s, "predicate": p, "object": o, "reason": r,
             "evidence_class": ec}
            for d, r, p, s, o, t, ec in cands if d not in ("ACCEPT",)
        ],    }
    for d, _r, _p, _s, _o, _t, _ec in cands:
        result["candidates_by_decision"][d] = \
            result["candidates_by_decision"].get(d, 0) + 1
    result["accepted_candidates"] = [
        {"subject": s, "predicate": p, "object": o,
         "trigger": t, "evidence_class": ec}
        for d, r, p, s, o, t, ec in cands if d == "ACCEPT"]

    conn.rollback()  # ZERO PERSISTENCE
    conn.close()
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
