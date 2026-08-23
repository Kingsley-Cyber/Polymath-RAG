"""SUMMARY RUNTIME D2: parent-summary stage worker.

Consumes a PARENT_SUMMARY ticket and produces the deterministic
artifact inside ONE transaction:
  1. idempotency gate — artifact_exists(input_hash) -> EXISTING
  2. compose via build_parent_summary (settled structures only)
  3. persist parent_summaries + summary_artifacts
  4. ticket -> COMPLETE

Canonical-only inputs per dedup realignment: callers pass canonical
entity surfaces / accepted facts, never raw mentions.
"""
from __future__ import annotations

from polymath_shared.identity import content_hash
from polymath_shared.parent_summary import build_parent_summary


def _ticket_state(conn, ticket_id: str) -> str | None:
    row = conn.execute("SELECT state FROM summary_jobs "
                       "WHERE ticket_id=%s", (ticket_id,)).fetchone()
    return row[0] if row else None


def _claim(conn, ticket_id: str, worker_id: str) -> bool:
    cur = conn.execute(
        "UPDATE summary_jobs SET state='RUNNING', worker_id=%s "
        "WHERE ticket_id=%s AND state IN ('READY','RETRY_WAIT')",
        (worker_id, ticket_id))
    return cur.rowcount == 1


def run_parent_summary_ticket(conn, *, ticket_id: str, corpus_id: str,
                              parent_id: str, input_hash: str,
                              contract_version: str,
                              worker_id: str,
                              parent_text: str,
                              children: list[dict],
                              facts: list[dict],
                              entities: list[dict],
                              source_ids: list[str]) -> dict:
    if not _claim(conn, ticket_id, worker_id):
        return {"status": "SKIPPED_NOT_CLAIMABLE"}

    existing = conn.execute(
        "SELECT artifact_id FROM summary_artifacts WHERE input_hash=%s",
        (input_hash,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE summary_jobs SET state='COMPLETE', completed_at=now() "
            "WHERE ticket_id=%s", (ticket_id,))
        return {"status": "EXISTING", "artifact_id": existing[0]}

    env = build_parent_summary(parent_id=parent_id, parent_text=parent_text,
                               children=children, facts=facts,
                               entities=entities)
    payload = env["payload"]
    artifact_id = "psa_" + content_hash({"in": input_hash})[:32]
    conn.execute(
        """INSERT INTO summary_artifacts (artifact_id, input_hash,
           output_hash, stage, corpus_id, contract_version,
           created_by_worker, source_ids, payload)
           VALUES (%s,%s,%s,'PARENT_SUMMARY',%s,%s,%s,%s,%s)
           ON CONFLICT (input_hash) DO NOTHING""",
        (artifact_id, input_hash, env["output_hash"], corpus_id,
         contract_version, worker_id, source_ids, __import__("json").dumps(
             {"envelope": env})))
    conn.execute(
        """INSERT INTO parent_summaries (summary_id, parent_id, corpus_id,
           artifact_hash, contract_version, created_by_worker, source_ids,
           entities, concepts, summary)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (summary_id) DO NOTHING""",
        (env["artifact_id"], parent_id, corpus_id, env["output_hash"],
         contract_version, worker_id, source_ids,
         payload["entities"], payload["concepts"], payload["summary"]))
    conn.execute(
        "UPDATE summary_jobs SET state='COMPLETE', completed_at=now() "
        "WHERE ticket_id=%s", (ticket_id,))
    return {"status": "COMPLETE", "artifact_id": env["artifact_id"],
            "output_hash": env["output_hash"],
            "summary_id": env["artifact_id"]}
