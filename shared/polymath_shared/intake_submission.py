"""The single-document intake writer — the ONLY execution path.

Both the orchestrator's POST /intake endpoint and the I1 manifest
submission producer call this function: one transactional write of the
run row and the intake.v1 outbox event with a content-derived
idempotency key. Replaying identical canonical input returns the
existing run_id and creates no second run (ADR-0001 §4).

The control plane picks the event up from here; nothing below this
function is bypassed (outbox, leases, receipts, census, verification).
"""
from __future__ import annotations

import base64
import json
from typing import Optional

import psycopg
from psycopg import Connection

from polymath_shared.identity import content_hash, run_id


def canonical_intake_payload(
    corpus_id: str,
    source_name: str,
    media_type: str,
    content_b64: Optional[str] = None,
    config: Optional[dict] = None,
    content_ref: Optional[dict] = None,
) -> dict:
    """The canonical payload whose hash defines run identity.

    Exactly one content variant:
      content_b64 — bytes inline (small texts; the original path)
      content_ref — SPOOL-CLAIM-CHECK-V1 reference {store, key,
                    sha256, bytes}; the sha256 is inside the payload,
                    so run identity stays content-addressed and replays
                    of the same file remain no-ops.
    """
    if (content_b64 is None) == (content_ref is None):
        raise ValueError(
            "exactly one of content_b64 / content_ref is required")
    payload = {
        "corpus_id": corpus_id,
        "source_name": source_name,
        "media_type": media_type,
        "config": config or {},
    }
    if content_b64 is not None:
        payload["content_b64"] = content_b64
    else:
        for field in ("store", "key", "sha256", "bytes"):
            if field not in (content_ref or {}):
                raise ValueError(f"content_ref missing {field!r}")
        payload["content_ref"] = content_ref
    return payload


def submit_intake(
    conn: Connection,
    canonical_payload: dict,
) -> dict:
    """Write one run row + intake.v1 outbox event in a single
    transaction; idempotent by content identity. Returns
    {run_id, accepted, already_exists}."""
    if "content_b64" in canonical_payload:
        try:
            base64.b64decode(canonical_payload["content_b64"], validate=True)
        except Exception as exc:
            raise ValueError("content_b64 is not valid base64") from exc
    elif "content_ref" not in canonical_payload:
        raise ValueError("payload carries neither content_b64 nor content_ref")

    corpus_id = canonical_payload["corpus_id"]
    rid = run_id(corpus_id, canonical_payload)
    outbox_key = content_hash({"run": rid, "type": "intake.v1", "payload": canonical_payload})

    existing = conn.execute("SELECT 1 FROM runs WHERE run_id = %s", (rid,)).fetchone()
    if existing:
        return {"run_id": rid, "accepted": True, "already_exists": True}

    conn.execute(
        """
        INSERT INTO runs (run_id, corpus_id, status, metadata)
        VALUES (%s, %s, 'intake', %s)
        """,
        (rid, corpus_id, json.dumps({
            "source_name": canonical_payload["source_name"],
            "intake_payload": canonical_payload,
        })),
    )
    conn.execute(
        """
        INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
        VALUES (%s, 'intake.v1', %s, %s)
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        (rid, json.dumps(canonical_payload), outbox_key),
    )
    return {"run_id": rid, "accepted": True, "already_exists": False}
