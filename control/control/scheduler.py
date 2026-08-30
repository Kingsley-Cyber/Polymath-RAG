"""Outbox scheduling: materialize census gaps as outbox events.

Enqueueing is idempotent (unique idempotency key) and happens in the
same tick transaction as the census, so a crash between census and
schedule re-computes the same gaps next tick.

SCHEDULER-BULK-V1 (2026-08-25): MEASURED live phase telemetry showed
schedule_gaps at 51-55s of every tick — one to two queries PER GAP
(payload lookup + INSERT) across tens of thousands of replayed gaps.
Payloads for projection/verify/canonicalize/profile stages are pure
identity (`{"run_id": …}`), so their keys are computed with ZERO reads;
intake/chunked payloads come from ONE DISTINCT ON query per type; all
inserts go out in chunked multi-row statements. Idempotency keys are
byte-identical to the per-gap loop, so the same outbox rows re-arm.
"""
from __future__ import annotations

from psycopg import Connection

from polymath_shared.identity import content_hash
from control.census import Census, Gap

_INSERT_CHUNK = 1000

#: stages whose gap payload needs only the run identity.
_IDENTITY_ONLY = {
    "profile_document.v1", "project_qdrant.v1", "project_neo4j.v1",
    "verify.v1", "canonicalize.v1", "project_canonical.v1",
}


def schedule_gaps(conn: Connection, census: Census) -> int:
    scheduled = 0
    rows: list[tuple] = []
    by_type: dict[str, list[Gap]] = {}
    # ARCHIVED-CHAIN-SUPPRESSION: one batched query identifies runs whose
    # ticket chains were deliberately superseded/archived; their events
    # are never re-armed (measured live: 44k armed debris events
    # occupied the claim FIFO after ticket archival).
    all_run_ids = [g.run_id for g in census.gaps]
    archived = _archived_run_ids(conn, all_run_ids) if all_run_ids else set()
    for gap in census.gaps:
        if gap.run_id in archived:
            continue
        by_type.setdefault(gap.event_type, []).append(gap)

    for event_type, gaps in by_type.items():
        run_ids = [g.run_id for g in gaps]

        def key(rid: str, payload: dict) -> str:
            return content_hash(
                {"run": rid, "type": event_type, "payload": payload})

        if event_type in _IDENTITY_ONLY:
            for rid in run_ids:
                payload = {"run_id": rid}
                rows.append((rid, event_type, _dumps(payload), key(rid,
                                                                   payload)))
        elif event_type == "chunked.v1":
            found = _bulk_first_outbox_payload(conn, "chunked.v1", run_ids)
            for rid in run_ids:
                payload = found.get(rid)
                if payload is None:
                    continue     # unchanged from the per-gap loop
                rows.append((rid, event_type, _dumps(payload),
                             key(rid, payload)))
        elif event_type == "intake.v1":
            found = _bulk_first_outbox_payload(conn, "intake.v1", run_ids)
            missing = [r for r in run_ids if r not in found]
            metas = _bulk_intake_metadata(conn, missing) if missing else {}
            for rid in run_ids:
                payload = found.get(rid) or metas.get(rid)
                if payload is None:
                    continue
                rows.append((rid, event_type, _dumps(payload),
                             key(rid, payload)))

    for i in range(0, len(rows), _INSERT_CHUNK):
        chunk = rows[i:i + _INSERT_CHUNK]
        # ON CONFLICT resets delivered_at so a retry after a failed stage
        # actually re-delivers: the payload is identical (same content
        # hash), so the same outbox row is re-armed, never duplicated.
        # The WHERE guard makes re-arming an already-armed row a no-op:
        # without it every gap rewrote its row EVERY tick — dead tuples
        # bloated outbox_events to 206 MB over 204 live rows and pushed
        # the id sequence past 155M (measured, STALL-2026-08-27).
        scheduled += conn.execute(
            """
            INSERT INTO outbox_events (run_id, event_type, payload,
                                       idempotency_key)
            SELECT x.run_id, x.event_type, x.payload::jsonb,
                   x.idempotency_key
              FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[])
                   AS x(run_id, event_type, payload, idempotency_key)
            ON CONFLICT (idempotency_key) DO UPDATE SET delivered_at = NULL
            WHERE outbox_events.delivered_at IS NOT NULL
            """,
            ([r[0] for r in chunk], [r[1] for r in chunk],
             [r[2] for r in chunk], [r[3] for r in chunk]),
        ).rowcount

    _reopen_receipt_gap_tickets(conn, census)
    return scheduled


#: RECEIPT-GAP-REOPENS-TICKET-V1 (2026-08-26). The summary waterfall
#: writes retrieval summaries AFTER the first projection pass; the
#: census then correctly flags the run's projection receipts as
#: incomplete and re-arms the projection event — but claiming requires
#: the stage ticket to be 'ready', and nothing re-opened a 'done'
#: ticket. MEASURED LIVE: transcript-qual-v1 sat in 'degraded' with 5
#: armed-but-unclaimable project_qdrant events while every worker
#: polled idle. Receipts prove state; a DONE ticket whose receipts the
#: census says are missing is not done. Re-opening stops the moment
#: receipts land (the gap disappears).
#:
#: ONE RE-DRIVE PER (CORPUS, STAGE) — STALL-2026-08-27. The desired
#: state these stages project is CORPUS-scoped (census and verify both
#: join through runs.corpus_id), so re-opening every flagged run's
#: ticket dispatched the identical corpus-wide projection N times over.
#: MEASURED LIVE: cysa-study-v1 (12 runs, one corpus) rewrote each
#: neo4j entity ~20x per 15 minutes — 286k receipt writes over 14.6k
#: distinct entities — while pending tickets starved behind the
#: receipt barrier. One open ticket per (corpus, stage) carries the
#: whole re-drive; further reopens wait until it settles.
_RECEIPT_GAP_STAGES = {
    "project_qdrant.v1": "project_qdrant",
    "project_neo4j.v1": "project_neo4j",
    "project_canonical.v1": "project_canonical",
}


def _reopen_receipt_gap_tickets(conn: Connection, census: Census) -> int:
    flagged: dict[tuple[str, str], set[str]] = {}
    for g in census.gaps:
        if (g.event_type in _RECEIPT_GAP_STAGES
                and "receipts missing" in (g.reason or "")):
            key = (g.corpus_id, _RECEIPT_GAP_STAGES[g.event_type])
            flagged.setdefault(key, set()).add(g.run_id)
    if not flagged:
        return 0
    reopened = 0
    for (corpus_id, stage), run_ids in sorted(flagged.items()):
        # A re-drive already in flight (any open ticket for this
        # corpus+stage) covers the corpus-scoped desired state; do not
        # stack duplicates behind it.
        open_row = conn.execute(
            """SELECT 1 FROM stage_tickets
                WHERE corpus_id = %s AND stage = %s
                  AND archived_at IS NULL
                  AND status IN ('pending', 'ready', 'leased', 'repair')
                LIMIT 1""",
            (corpus_id, stage)).fetchone()
        if open_row:
            continue
        reopened += conn.execute(
            """
            UPDATE stage_tickets
               SET status = 'ready', lease_owner = NULL,
                   lease_expires_at = NULL, updated_at = now()
             WHERE ticket_id = (
                   SELECT ticket_id FROM stage_tickets
                    WHERE corpus_id = %s AND stage = %s
                      AND run_id = ANY(%s)
                      AND status = 'done' AND archived_at IS NULL
                    ORDER BY run_id LIMIT 1)
            """,
            (corpus_id, stage, sorted(run_ids)),
        ).rowcount
    return reopened


def _bulk_first_outbox_payload(conn: Connection, event_type: str,
                               run_ids: list[str]) -> dict[str, dict]:
    """First recorded payload per run for this event type, ONE query."""
    if not run_ids:
        return {}
    rows = conn.execute(
        """
        SELECT DISTINCT ON (run_id) run_id, payload
          FROM outbox_events
         WHERE event_type = %s AND run_id = ANY(%s)
         ORDER BY run_id, event_id
        """,
        (event_type, sorted(set(run_ids))),
    ).fetchall()
    out: dict[str, dict] = {}
    for run_id, payload in rows:
        if payload is None:
            continue
        out[run_id] = payload if isinstance(payload, dict) \
            else _loads(payload)
    return out


def _bulk_intake_metadata(conn: Connection,
                          run_ids: list[str]) -> dict[str, dict]:
    """Crashed-first-event repair source: runs.metadata.intake_payload."""
    if not run_ids:
        return {}
    rows = conn.execute(
        """
        SELECT run_id, metadata FROM runs
         WHERE run_id = ANY(%s)
        """,
        (sorted(set(run_ids)),),
    ).fetchall()
    out: dict[str, dict] = {}
    for run_id, metadata in rows:
        if metadata and metadata.get("intake_payload"):
            out[run_id] = metadata["intake_payload"]
    return out


def _archived_run_ids(conn: Connection, run_ids: list[str]) -> set[str]:
    """Runs whose scheduling lifecycle is deliberately closed: either a
    superseded (archived) ticket chain OR membership in the
    ARCHIVED-CORPUS-REGISTRY (the durable marker that survives runtime
    cleanup)."""
    if not run_ids:
        return set()
    ids = sorted(set(run_ids))
    rows = conn.execute(
        """SELECT DISTINCT run_id FROM stage_tickets
            WHERE status='superseded' AND run_id = ANY(%s)
           UNION
           SELECT r.run_id FROM runs r
            JOIN archived_corpora ac ON ac.corpus_id = r.corpus_id
            WHERE r.run_id = ANY(%s)""",
        (ids, ids),
    ).fetchall()
    return {r[0] for r in rows}


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


def _loads(text: str) -> dict:
    import json
    return json.loads(text)


def _dumps(payload: dict) -> str:
    import json

    return json.dumps(payload)
