"""CONTROL-PLANE-V2 evaluation snapshot barrier (ADR-0014).

An evaluation must NEVER run against a reconciling/degraded corpus
(the retrieval 0/30 class). Evaluators acquire a snapshot token for a
generation; if the corpus's state hash changes during evaluation,
validation fails loudly and the evaluation must abort.
"""
from __future__ import annotations

from psycopg import Connection

from polymath_shared.identity import content_hash


def corpus_state_hash(conn: Connection, corpus_id: str) -> str:
    """Deterministic digest of the corpus's authoritative + projection
    state: run statuses + execution contracts, ticket statuses, and
    corpus-scoped durable counts (docs/chunks/facts/mentions)."""
    parts: list[str] = []
    for (run_id, status, contract) in conn.execute(
        "SELECT run_id, status, execution_contract::text FROM runs "
        "WHERE corpus_id=%s ORDER BY run_id", (corpus_id,),
    ).fetchall():
        parts.append(f"{run_id}:{status}:{contract}")
    for row in conn.execute(
        "SELECT stage, status, COUNT(*) FROM stage_tickets WHERE corpus_id=%s "
        "GROUP BY 1,2 ORDER BY 1,2", (corpus_id,),
    ).fetchall():
        parts.append(f"{row[0]}:{row[1]}:{row[2]}")
    for label, sql in (
        ("docs", "SELECT COUNT(*) FROM documents WHERE corpus_id=%s"),
        ("chunks", "SELECT COUNT(*) FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE d.corpus_id=%s"),
        ("facts", "SELECT COUNT(DISTINCT f.fact_id) FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s"),
        ("mentions", "SELECT COUNT(*) FROM mentions WHERE corpus_id=%s"),
    ):
        row = conn.execute(sql, (corpus_id,)).fetchone()
        parts.append(f"{label}:{row[0] if row else 0}")
    return content_hash({"corpus": corpus_id, "state": parts})


def acquire_snapshot(conn: Connection, corpus_id: str,
                     require_query_ready: bool = True) -> str:
    """Freeze the current view. Requires the generation barrier unless
    the caller explicitly opts out (never in evaluation paths)."""
    if require_query_ready:
        barrier = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE corpus_id=%s AND status != 'query_ready'",
            (corpus_id,),
        ).fetchone()
        open_tickets = conn.execute(
            "SELECT COUNT(*) FROM stage_tickets WHERE corpus_id=%s AND status != 'done'",
            (corpus_id,),
        ).fetchone()
        if (barrier[0] or 0) > 0 or (open_tickets[0] or 0) > 0:
            raise RuntimeError(
                f"snapshot refused: corpus {corpus_id} not at the generation "
                f"barrier (non-query_ready runs={barrier[0]}, open tickets={open_tickets[0]})"
            )
    state = corpus_state_hash(conn, corpus_id)
    snapshot_id = "snap_" + content_hash({"c": corpus_id, "h": state})[:24]
    conn.execute(
        """
        INSERT INTO corpus_snapshots (snapshot_id, corpus_id, generation, state_hash)
        VALUES (%s, %s, 1, %s)
        ON CONFLICT (snapshot_id) DO UPDATE SET valid = TRUE,
            invalidated_at = NULL, invalid_reason = NULL
        """,
        (snapshot_id, corpus_id, state),
    )
    return snapshot_id


def validate_snapshot(conn: Connection, snapshot_id: str) -> None:
    """Raise (abort the evaluation loudly) if the snapshot is invalid or
    the live state hash has drifted from the frozen view."""
    row = conn.execute(
        "SELECT corpus_id, state_hash, valid, invalid_reason "
        "FROM corpus_snapshots WHERE snapshot_id=%s", (snapshot_id,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"unknown snapshot {snapshot_id}")
    corpus_id, frozen_hash, valid, reason = row
    if not valid:
        raise RuntimeError(f"snapshot {snapshot_id} invalidated: {reason}")
    live = corpus_state_hash(conn, corpus_id)
    if live != frozen_hash:
        # Invalidate in its OWN committed transaction: the caller's
        # transaction may roll back when this exception unwinds it.
        from polymath_shared.db import tx as _tx

        with _tx() as c2:
            c2.execute(
                "UPDATE corpus_snapshots SET valid=FALSE, invalidated_at=now(), "
                "invalid_reason=%s WHERE snapshot_id=%s",
                ("state drift during evaluation", snapshot_id),
            )
        raise RuntimeError(
            f"snapshot {snapshot_id} ABORT: corpus state changed during "
            "evaluation (live hash != frozen hash)"
        )
