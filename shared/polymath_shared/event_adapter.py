"""EVENT-ADAPTER-V1: workers consume canonical payloads only.

Legacy writer generations minted stage events with bare
``{run_id, ticket_id}`` payloads (measured live: 408 reconciling-run
chunked.v1 events crashed extract workers on ``KeyError: 'doc_id'``).
This module is the single compatibility boundary:

    legacy payload -> normalize_event() -> canonical payload

Recovery consults durable state (intake artifacts) before giving up;
an unrecoverable poison raises :class:`LegacyEventUnrecoverable` so the
caller fails the ticket ONCE with a typed reason instead of crash-
looping on missing keys.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

log = logging.getLogger("event-adapter")

#: Payload keys each stage's process_event actually requires today.
_REQUIRED = {
    "chunked.v1": ("doc_id",),
    # MEASURED 2026-08-25: restart READY-backfill re-emits bare
    # {run_id, ticket_id} intake payloads when the original producing
    # event is gone -> intake workers crashed KeyError('corpus_id') x3
    # across 74 tickets in one restart cycle.
    "intake.v1": ("corpus_id",),
}


class LegacyEventUnrecoverable(Exception):
    """Typed, deterministic refusal: the payload cannot be normalized
    from any durable source. Carries the reason for last_error."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _recover_from_intake_artifact(
        conn: Callable[[str, tuple], Any], run_id: str) -> Optional[dict]:
    """EXECUTION-BUNDLE era recovery: the intake stage persists an
    artifact whose payload.routing_card carries doc_id + profile."""
    try:
        rows = conn.execute(
            """
            SELECT payload FROM artifacts
             WHERE run_id=%s AND stage='intake'
             ORDER BY created_at DESC LIMIT 1
            """,
            (run_id,),
        ).fetchall()
    except Exception:
        return None
    for (payload,) in rows:
        if payload is None:
            continue
        p = payload if isinstance(payload, dict) else json.loads(payload)
        card = p.get("routing_card") or {}
        if card.get("doc_id"):
            merged = {"doc_id": card["doc_id"]}
            if card.get("profile"):
                merged["profile"] = card["profile"]
            return merged
    return None


def normalize_event(conn: Callable[[str, tuple], Any],
                    event_type: str, payload: dict,
                    run_id: str) -> dict:
    """Return a CANONICAL payload for this event, recovering missing
    keys from durable state where possible.

    Fail-closed: raises LegacyEventUnrecoverable rather than returning a
    payload that would crash a worker on a missing key."""
    canonical = dict(payload or {})
    required = _REQUIRED.get(event_type, ())
    missing = [k for k in required if not canonical.get(k)]
    if not missing:
        return canonical

    if event_type == "chunked.v1" and "doc_id" in missing:
        recovered = _recover_from_intake_artifact(conn, run_id)
        if recovered:
            for k, v in recovered.items():
                canonical.setdefault(k, v)
            missing = [k for k in required if not canonical.get(k)]
            log.info("legacy chunked.v1 payload recovered from intake "
                     "artifact", extra={
                         "run_id": run_id,
                         "doc_id": recovered.get("doc_id")})

    if event_type == "intake.v1" and "corpus_id" in missing:
        try:
            row = conn.execute(
                "SELECT corpus_id FROM runs WHERE run_id=%s",
                (run_id,),
            ).fetchone()
        except Exception:
            row = None
        if row and row[0]:
            canonical.setdefault("corpus_id", row[0])
            missing = [k for k in required if not canonical.get(k)]
            log.info("legacy intake.v1 payload recovered corpus_id "
                     "from runs row", extra={"run_id": run_id})
    if missing:
        raise LegacyEventUnrecoverable(
            f"LEGACY_EVENT_UNRECOVERABLE {event_type}: missing "
            f"{missing} after adapter recovery")
    return canonical
