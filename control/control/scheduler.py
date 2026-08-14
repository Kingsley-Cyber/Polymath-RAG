"""Outbox scheduling: materialize census gaps as outbox events.

Enqueueing is idempotent (unique idempotency key) and happens in the
same tick transaction as the census, so a crash between census and
schedule re-computes the same gaps next tick.
"""
from __future__ import annotations

from psycopg import Connection

from polymath_shared.identity import content_hash
from control.census import Census, Gap


def schedule_gaps(conn: Connection, census: Census) -> int:
    scheduled = 0
    for gap in census.gaps:
        payload = _gap_payload(conn, gap)
        if payload is None:
            continue
        key = content_hash({"run": gap.run_id, "type": gap.event_type, "payload": payload})
        # ON CONFLICT resets delivered_at so a retry after a failed stage
        # actually re-delivers: the payload is identical (same content
        # hash), so the same outbox row is re-armed instead of duplicated.
        inserted = conn.execute(
            """
            INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO UPDATE SET delivered_at = NULL
            """,
            (gap.run_id, gap.event_type, _dumps(payload), key),
        ).rowcount
        scheduled += inserted
    return scheduled


def apply_promotions(conn: Connection, census: Census) -> None:
    for run_id in census.promote:
        conn.execute(
            "UPDATE runs SET status = 'query_ready', updated_at = now() WHERE run_id = %s AND status != 'query_ready'",
            (run_id,),
        )


def apply_failures(conn: Connection, census: Census) -> None:
    for run_id in census.fail:
        conn.execute(
            "UPDATE runs SET status = 'failed', updated_at = now() WHERE run_id = %s",
            (run_id,),
        )


def _gap_payload(conn: Connection, gap: Gap) -> dict | None:
    """Rebuild the minimal payload for the gap's event type. For intake
    gaps the original intake payload lives in the first outbox row (or
    the metadata), so a crashed first-event window can be repaired
    without asking the user to re-upload (ISSUES_REPORT §1.4 fix).

    Projection and verify stages only need the run identity: the
    workers read the authoritative Postgres rows themselves."""
    if gap.event_type == "intake.v1":
        row = conn.execute(
            "SELECT payload FROM outbox_events WHERE run_id = %s AND event_type = 'intake.v1' ORDER BY event_id LIMIT 1",
            (gap.run_id,),
        ).fetchone()
        if row:
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        metadata = conn.execute(
            "SELECT metadata FROM runs WHERE run_id = %s", (gap.run_id,)
        ).fetchone()
        if metadata and metadata[0].get("intake_payload"):
            return metadata[0]["intake_payload"]
        return None

    if gap.event_type == "chunked.v1":
        row = conn.execute(
            "SELECT payload FROM outbox_events WHERE run_id = %s AND event_type = 'chunked.v1' ORDER BY event_id LIMIT 1",
            (gap.run_id,),
        ).fetchone()
        if row:
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return None

    # project_qdrant.v1 / project_neo4j.v1 / verify.v1: identity only.
    return {"run_id": gap.run_id}


def _dumps(payload: dict) -> str:
    import json

    return json.dumps(payload)
