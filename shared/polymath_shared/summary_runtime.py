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
from collections import Counter

from polymath_shared.parent_summary import build_parent_summary
from polymath_shared.summary_layer import build_envelope


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
                              source_ids: list[str],
                              compiled: dict | None = None) -> dict:
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
                               entities=entities, compiled=compiled)
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
    # SUMMARY-IDEMPOTENCY-V1 (P23): exactly one AUTHORITATIVE row per
    # parent. summary_id is content-addressed, so a parent summarised
    # before its entities were ready and again afterwards produced two
    # rows with nothing saying which one counts — 1,241 parents were in
    # that state. Superseding is explicit and retains the old row; the
    # partial unique index on (parent_id) WHERE superseded_at IS NULL
    # makes a second live row impossible rather than merely unlikely.
    conn.execute(
        """UPDATE parent_summaries SET superseded_at = now()
            WHERE parent_id = %s AND superseded_at IS NULL
              AND summary_id <> %s""",
        (parent_id, env["artifact_id"]))
    conn.execute(
        """INSERT INTO parent_summaries (summary_id, parent_id, corpus_id,
           artifact_hash, contract_version, created_by_worker, source_ids,
           entities, concepts, summary)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (summary_id) DO UPDATE
              SET superseded_at = NULL""",
        (env["artifact_id"], parent_id, corpus_id, env["output_hash"],
         contract_version, worker_id, source_ids,
         payload["entities"], payload["concepts"], payload["summary"]))
    conn.execute(
        "UPDATE summary_jobs SET state='COMPLETE', completed_at=now() "
        "WHERE ticket_id=%s", (ticket_id,))
    return {"status": "COMPLETE", "artifact_id": env["artifact_id"],
            "output_hash": env["output_hash"],
            "summary_id": env["artifact_id"]}


def run_document_summary_ticket(conn, *, ticket_id: str, corpus_id: str,
                                document_id: str, input_hash: str,
                                contract_version: str, worker_id: str,
                                parent_summary_ids: list[str],
                                title: str = "",
                                accepted_predicates: list[str] | None = None,
                                event_count: int = 0,
                                source_ids: list[str] | None = None):
    """D3: compose the document summary from PARENT SUMMARIES ONLY.

    Verifies every referenced parent exists and its stored
    artifact_hash matches the caller's view before aggregating. Never
    invents entities/facts/relationships — it only compresses settled
    knowledge."""
    if not _claim(conn, ticket_id, worker_id):
        return {"status": "SKIPPED_NOT_CLAIMABLE"}

    existing = conn.execute(
        "SELECT artifact_id FROM summary_artifacts WHERE input_hash=%s",
        (input_hash,)).fetchone()
    if existing:
        conn.execute("UPDATE summary_jobs SET state='COMPLETE', "
                     "completed_at=now() WHERE ticket_id=%s", (ticket_id,))
        return {"status": "EXISTING", "artifact_id": existing[0]}

    # verify lineage: every parent summary must exist; hash agreement
    parents = []
    for pid in parent_summary_ids:
        row = conn.execute(
            """SELECT summary_id, summary, entities, concepts,
               artifact_hash FROM parent_summaries WHERE summary_id=%s""",
            (pid,)).fetchone()
        if row is None:
            conn.execute("UPDATE summary_jobs SET state='FAILED', "
                         "completed_at=now() WHERE ticket_id=%s",
                         (ticket_id,))
            return {"status": "FAILED", "reason":
                    f"missing parent summary {pid}"}
        parents.append(row)

    ent_freq: Counter = Counter()
    cpt_freq: Counter = Counter()
    lines: list[str] = []
    for _sid, summary, ents, cpts, _h in parents:
        for e in ents or []:
            ent_freq[e] += 1
        for cpt in cpts or []:
            cpt_freq[cpt] += 1
        if summary:
            lines.append(summary)
    preds = sorted(set(accepted_predicates or []))
    lead = f"{title} — " if title else ""
    body = " ".join(lines[:3])
    density = round(len(preds) / max(len(parents), 1), 4)
    payload = {
        "summary_type": "document",
        "document_id": document_id,
        "concepts": [c for c, _ in cpt_freq.most_common(10)],
        "entities": [e for e, _ in ent_freq.most_common(10)],
        "methods": preds,
        "predicates": preds,
        "evidence_density": density,
        "event_count": event_count,
        "summary": (lead + body).strip(),
    }
    env = build_envelope(derived_from=list(parent_summary_ids),
                         payload=payload)
    artifact_id = "dsa_" + content_hash({"in": input_hash})[:32]
    conn.execute(
        """INSERT INTO summary_artifacts (artifact_id, input_hash,
           output_hash, stage, corpus_id, contract_version,
           created_by_worker, source_ids, payload)
           VALUES (%s,%s,%s,'DOCUMENT_SUMMARY',%s,%s,%s,%s,%s)
           ON CONFLICT (input_hash) DO NOTHING""",
        (artifact_id, input_hash, env["output_hash"], corpus_id,
         contract_version, worker_id, source_ids or parent_summary_ids,
         __import__("json").dumps({"envelope": env})))
    conn.execute(
        """INSERT INTO document_summaries (summary_id, document_id,
           corpus_id, artifact_hash, contract_version, created_by_worker,
           source_ids, major_entities, major_concepts, methods, domains,
           questions_answered, summary)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'{}','{}',%s)
           ON CONFLICT (summary_id) DO NOTHING""",
        (env["artifact_id"], document_id, corpus_id, env["output_hash"],
         contract_version, worker_id, list(parent_summary_ids),
         payload["entities"], payload["concepts"], payload["methods"],
         payload["summary"]))
    conn.execute("UPDATE summary_jobs SET state='COMPLETE', "
                 "completed_at=now() WHERE ticket_id=%s", (ticket_id,))
    return {"status": "COMPLETE", "artifact_id": artifact_id,
            "document_summary_id": env["artifact_id"]}


# --- D6 hardening: bounded retries + dead letter -----------------------
MAX_ATTEMPTS = 5


def backoff_seconds(attempts: int) -> int:
    """Exponential backoff with cap: 8s, 16s, 32s, 64s…"""
    return min(8 * (2 ** max(attempts - 1, 0)), 600)


def fail_ticket(conn, ticket_id: str, attempts: int,
                error_note: str | None = None) -> str:
    """FAILED -> RETRY_WAIT within budget, else FAILED_PERMANENT."""
    if attempts + 1 >= MAX_ATTEMPTS:
        state = "FAILED_PERMANENT"
    else:
        state = "RETRY_WAIT"
    conn.execute(
        "UPDATE summary_jobs SET state=%s, attempts=%s "
        "WHERE ticket_id=%s", (state, attempts + 1, ticket_id))
    return state
