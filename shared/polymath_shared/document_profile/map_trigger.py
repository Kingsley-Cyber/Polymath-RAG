"""ONE mint path for the auto-minted doc_parent_map (pMAP) stage
(RAG-PIPELINE-FINISH). Mirrors `latent/trigger.mint_parent_enrichment`: the pMAP
stage is deliberately OUTSIDE `STAGE_DAG` (like parent_enrichment) and minted by a
flag-gated scheduler phase, so enabling it can never silently re-map existing
corpora — the forensic-hold-safe way to make FRESH uploads produce grounded maps.

Gate (owner):
  POLYMATH_DOC_PARENT_MAP_ENABLED   off by default — no ticket is minted, current
                                    behavior byte-identical, zero provider spend.
  POLYMATH_DOC_PARENT_MAP_CORPUS    optional single-corpus scope: when set, only runs
                                    in that corpus are minted (used for the bounded
                                    canary so the cinema corpus is never touched).
"""
from __future__ import annotations

import json
import os

from polymath_shared.identity import content_hash

STAGE = "doc_parent_map"
EVENT_TYPE = "doc_parent_map.v1"


def doc_parent_map_enabled() -> bool:
    return os.environ.get("POLYMATH_DOC_PARENT_MAP_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def doc_parent_map_corpus_scope() -> str | None:
    v = os.environ.get("POLYMATH_DOC_PARENT_MAP_CORPUS", "").strip()
    return v or None


def mint_doc_parent_map(conn, *, corpus_id: str, run_id: str) -> dict:
    """Mint/re-arm the doc_parent_map ticket + event for a run. One ticket per (run,
    stage); a re-mint re-arms it and re-opens the event (idempotent, restart-safe)."""
    ticket_id = "tkt_" + content_hash({"run": run_id, "stage": STAGE})[:40]
    conn.execute(
        """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status)
           VALUES (%s,%s,%s,%s,%s,'ready')
           ON CONFLICT (ticket_id) DO UPDATE
              SET status='ready', lease_owner=NULL, lease_expires_at=NULL,
                  archived_at=NULL, archived_reason=NULL, updated_at=now()""",
        (ticket_id, run_id, corpus_id, STAGE, EVENT_TYPE))
    key = f"pmap:{run_id}"
    conn.execute(
        """INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
           VALUES (%s,%s,%s,%s)
           ON CONFLICT (idempotency_key) DO UPDATE SET delivered_at=NULL, payload=EXCLUDED.payload""",
        (run_id, EVENT_TYPE, json.dumps({"run_id": run_id}), key))
    return {"run_id": run_id, "ticket_id": ticket_id, "corpus_id": corpus_id}
