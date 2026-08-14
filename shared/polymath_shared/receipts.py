"""Receipts and outbox: the single transaction boundary for durable writes.

The rule (AGENTS.md rule 5): a stage's durable write + its receipt + its
status transition + required outbox event commit in ONE Postgres
transaction. If they are not, the stage is wrong.

Redelivery safety: outbox consumers re-run the same content-hashed key
and land on the same primary keys, so replays are no-ops.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any, Iterator, Optional
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from polymath_shared.identity import attempt_id, content_hash, receipt_id


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stage_contract_hash(stage: str, frozen: dict) -> str:
    return content_hash({"stage": stage, "frozen": frozen})


class StageFailed(RuntimeError):
    """Raised by stage_transaction after the failure receipt is durable."""

    def __init__(self, run_id: str, stage: str) -> None:
        super().__init__(f"stage {stage} failed for run {run_id}; failure receipt committed")
        self.run_id = run_id
        self.stage = stage


@contextmanager
def stage_transaction(
    conn: Connection,
    *,
    run_id: str,
    stage: str,
    contract_hash: str,
) -> Iterator["_StageWrite"]:
    """Yield a writer bound to one transaction. All writes the caller makes
    through the writer, plus the receipt, plus the status transition, plus
    any enqueued outbox events, commit together.

    Failure path: the stage writes roll back to a savepoint, the failure
    receipt + attempt record commit, and StageFailed propagates — so a
    crashed stage never leaves a dangling attempt and the control plane
    can count retries from durable state."""
    writer = _StageWrite(conn, run_id=run_id, stage=stage, contract_hash=contract_hash)
    writer._begin_attempt()
    conn.execute("SAVEPOINT stage_work")
    try:
        yield writer
    except BaseException as exc:
        conn.execute("ROLLBACK TO SAVEPOINT stage_work")
        conn.execute("RELEASE SAVEPOINT stage_work")
        writer._record_failure(exc)
        conn.commit()
        raise StageFailed(run_id, stage) from exc
    else:
        conn.execute("RELEASE SAVEPOINT stage_work")
        writer._commit_receipt()
        conn.commit()


class _StageWrite:
    def __init__(self, conn: Connection, *, run_id: str, stage: str, contract_hash: str) -> None:
        self.conn = conn
        self.run_id = run_id
        self.stage = stage
        self.contract_hash = contract_hash
        self.attempt = attempt_id(run_id, stage, contract_hash)

    def _begin_attempt(self) -> None:
        self.conn.execute(
            """
            INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, outcome)
            VALUES (%s, %s, %s, now(), 'ok')
            ON CONFLICT (run_id, stage, contract_hash) DO NOTHING
            """,
            (self.run_id, self.stage, self.contract_hash),
        )

    def _record_failure(self, exc: BaseException) -> None:
        # Runs AFTER a rollback-to-savepoint, so this transaction is clean
        # and these statements can commit.
        self.conn.execute(
            """
            UPDATE stage_attempts
               SET outcome = 'failed', error = %s, completed_at = now()
             WHERE run_id = %s AND stage = %s AND contract_hash = %s
            """,
            (str(exc)[:2000], self.run_id, self.stage, self.contract_hash),
        )
        self.conn.execute(
            """
            INSERT INTO receipts (receipt_id, run_id, stage, contract_hash, status, error)
            VALUES (%s, %s, %s, %s, 'failed', %s)
            ON CONFLICT (run_id, stage, contract_hash) DO UPDATE
               SET status = 'failed', error = EXCLUDED.error
            """,
            (receipt_id(self.run_id, self.stage, self.contract_hash),
             self.run_id, self.stage, self.contract_hash, str(exc)[:2000]),
        )

    def _commit_receipt(self) -> None:
        self.conn.execute(
            """
            UPDATE stage_attempts
               SET completed_at = now(), outcome = 'ok', error = NULL
             WHERE run_id = %s AND stage = %s AND contract_hash = %s
            """,
            (self.run_id, self.stage, self.contract_hash),
        )
        self.conn.execute(
            """
            INSERT INTO receipts (receipt_id, run_id, stage, contract_hash, status)
            VALUES (%s, %s, %s, %s, 'committed')
            ON CONFLICT (run_id, stage, contract_hash) DO UPDATE
               SET status = 'committed'
            """,
            (receipt_id(self.run_id, self.stage, self.contract_hash),
             self.run_id, self.stage, self.contract_hash),
        )

    # -- durable writes ----------------------------------------------------

    def artifact(self, payload: dict) -> str:
        """Store a stage artifact; the artifact id is content-derived."""
        artifact_id = content_hash({"run": self.run_id, "stage": self.stage, "payload": payload})
        self.conn.execute(
            """
            INSERT INTO artifacts (artifact_id, run_id, stage, contract_hash, payload)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (run_id, stage, contract_hash) DO NOTHING
            """,
            (artifact_id, self.run_id, self.stage, self.contract_hash, json.dumps(payload)),
        )
        return artifact_id

    def outbox(self, event_type: str, payload: dict) -> None:
        """Enqueue a delivery event in the SAME transaction as the receipt."""
        key = content_hash({"run": self.run_id, "type": event_type, "payload": payload})
        self.conn.execute(
            """
            INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (self.run_id, event_type, json.dumps(payload), key),
        )

    def run_status(self, status: str) -> None:
        self.conn.execute(
            "UPDATE runs SET status = %s, updated_at = now() WHERE run_id = %s",
            (status, self.run_id),
        )


# ---------------------------------------------------------------------------
# Projection claims (Phase F/G): immutable attempts + active claims
# ---------------------------------------------------------------------------


def record_projection_attempt(
    conn: Connection,
    *,
    projection: str,
    entity_kind: str,
    entity_id: str,
    receipt_hash: str,
    contract: str = "",
) -> None:
    """Append the immutable attempt AND (re)claim the projection.

    The attempt row is history — never deleted. The claim row is the
    active belief that the artifact is currently present; re-projection
    after a verified store loss re-activates it."""
    conn.execute(
        """
        INSERT INTO projection_attempts (projection, entity_kind, entity_id, receipt_hash, contract)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (projection, entity_kind, entity_id, receipt_hash, contract),
    )
    conn.execute(
        """
        INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash, active)
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (projection, entity_kind, entity_id) DO UPDATE
           SET active = TRUE, receipt_hash = EXCLUDED.receipt_hash, written_at = now()
        """,
        (projection, entity_kind, entity_id, receipt_hash),
    )


def supersede_projection_claims(
    conn: Connection,
    *,
    projection: str,
    entity_kind: str | None = None,
    entity_ids: list[str],
) -> None:
    """Invalidate active claims without erasing attempt history.

    Used by VERIFY_PROJECTIONS when a store lost artifacts or a claim's
    source row no longer exists. The census then sees the gap and
    schedules reconstruction."""
    if not entity_ids:
        return
    if entity_kind:
        conn.execute(
            """
            UPDATE projection_receipts SET active = FALSE
             WHERE projection = %s AND entity_kind = %s AND entity_id = ANY(%s)
            """,
            (projection, entity_kind, entity_ids),
        )
    else:
        conn.execute(
            """
            UPDATE projection_receipts SET active = FALSE
             WHERE projection = %s AND entity_id = ANY(%s)
            """,
            (projection, entity_ids),
        )


# ---------------------------------------------------------------------------
# Outbox consumption (workers + control plane)
# ---------------------------------------------------------------------------


def claim_events(conn: Connection, event_types: list[str], limit: int) -> list[dict]:
    """Claim a batch of undelivered outbox events with a short row lock.
    Delivery marks the row; the idempotency key makes redelivery safe."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, run_id, event_type, payload, idempotency_key
              FROM outbox_events
             WHERE delivered_at IS NULL
               AND event_type = ANY(%s)
             ORDER BY event_id
             LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (event_types, limit),
        )
        events = cur.fetchall()
        if events:
            cur.execute(
                "UPDATE outbox_events SET delivered_at = now() WHERE event_id = ANY(%s)",
                ([e["event_id"] for e in events],),
            )
    return events
