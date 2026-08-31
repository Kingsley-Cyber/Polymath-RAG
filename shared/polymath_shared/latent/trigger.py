"""ONE mint path for parent_enrichment work (§0a buttons + AUTO-ENRICH).

AUTO-ENRICH-ON-INGEST (owner 2026-08-31, amends §0a): enrichment now
also kicks in AUTOMATICALLY — the control timer is the census tick, and
the trigger point is RUN PROMOTION to query_ready. Rationale: retrieval
comes up first (enrichment is additive, §0b absence-invisible), parents
are settled, and the (stage, input_hash) idempotency makes re-triggers
free. The buttons remain the GAP-FILLING path (transient failures,
re-enrichment after edits)."""
from __future__ import annotations

import json

from polymath_shared.identity import content_hash


def mint_parent_enrichment(conn, *, corpus_id: str, run_id: str,
                           doc_id: str | None = None) -> dict:
    """Mint/re-arm the owner-triggered (or auto) enrichment ticket +
    event for a scope. One ticket per (run, stage); re-mint re-arms it
    and re-opens the event."""
    ticket_id = "tkt_" + content_hash(
        {"run": run_id, "stage": "parent_enrichment"})[:40]
    conn.execute(
        """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage,
               event_type, status)
           VALUES (%s,%s,%s,'parent_enrichment','parent_enrichment.v1',
                   'ready')
           ON CONFLICT (ticket_id) DO UPDATE
              SET status='ready', lease_owner=NULL, lease_expires_at=NULL,
                  archived_at=NULL, archived_reason=NULL, updated_at=now()""",
        (ticket_id, run_id, corpus_id))
    key = f"enrich:{run_id}:{doc_id or '*'}"
    payload = {"run_id": run_id}
    if doc_id:
        payload["doc_id"] = doc_id
    conn.execute(
        """INSERT INTO outbox_events (run_id, event_type, payload,
               idempotency_key)
           VALUES (%s,'parent_enrichment.v1',%s,%s)
           ON CONFLICT (idempotency_key)
           DO UPDATE SET delivered_at=NULL, payload=EXCLUDED.payload""",
        (run_id, json.dumps(payload), key))
    return {"run_id": run_id, "ticket_id": ticket_id,
            "scope": doc_id or "corpus"}
