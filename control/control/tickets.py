"""CONTROL-PLANE-V2 stage tickets (ADR-0014).

Explicit handoff: a stage's work event exists ONLY after the control
plane verifies the predecessor's artifacts, receipts, and contract.
The ticket chains of different runs progress independently (pipelined
fan-out); per-stage pending high watermarks pause new intake tickets
(backpressure); promotion to query_ready is a generation barrier.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from psycopg import Connection

from polymath_shared.execution import (
    default_execution_contract)
from polymath_shared.identity import content_hash

# The per-run ticket DAG: (stage, event_type, required artifact keys,
# required receipt projections). ORDERED — each entry's readiness is
# verified against the completion of everything before it (a stage is
# only handed work when its predecessors' durable evidence exists).
STAGE_DAG: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    ("intake", "intake.v1", (), ()),
    ("extract", "chunked.v1", ("manifest",), ()),
    ("profile_document", "profile_document.v1", ("documents_profiled",), ()),
    ("project_qdrant", "project_qdrant.v1", ("chunk_count",), ("qdrant",)),
    ("project_neo4j", "project_neo4j.v1", ("facts",), ("neo4j",)),
    ("canonicalize", "canonicalize.v1", ("canonical_entities",), ()),
    ("project_canonical", "project_canonical.v1", ("memberships",), ("neo4j",)),
    # VERIFY-DAG-KEYS-V2 (measured 2026-08-25, Stage-K pilot): the
    # verifier writes {qdrant, routing_qdrant, neo4j, canonical}; the
    # stale declared key 'docs' blocked ticket advancement for every
    # run whose chain was minted after the verifier's reconciliation
    # rewrite (artifact check failed -> summary stages never became
    # ready -> corpus could not promote).
    ("verify_projections", "verify.v1",
     ("qdrant", "routing_qdrant", "neo4j", "canonical"), ()),
    # SUMMARY-VOCABULARY-LAYER: background intelligence stages. They run
    # AFTER settlement consumes nothing from the critical ingestion path:
    # a failure degrades summaries to DEGRADED, never blocks QUERY_READY.
    # COMPILE-OBJECTS-STAGE-V1 (§11): the deterministic concept/procedure
    # compilers as their own provider-agnostic stage — no longer a
    # bolt-on call inside the extract branch. Consumes admitted mentions
    # + chunk text; identical under either provider era.
    ("compile_objects", "compile_objects.v1", (), ()),
    ("parent_summary", "parent_summary.v1", (), ()),
    ("document_summary", "document_summary.v1", (), ()),
    ("corpus_summary", "corpus_summary.v1", (), ()),
    ("vocabulary", "vocabulary.v1", (), ()),
]

# Stages whose incompleteness must NOT block corpus promotion
# (SUMMARY-VOCABULARY-LAYER production rule: knowledge=READY while
# summaries=DEGRADED).
NON_BLOCKING_STAGES = frozenset({
    "compile_objects",
    "parent_summary", "document_summary", "corpus_summary", "vocabulary",
    # LATENT-TRANSFER-LAYER-V1 §0a: OWNER-TRIGGERED — its tickets are
    # minted by the enrichment buttons, never by chain advancement, so
    # it is deliberately ABSENT from STAGE_DAG. Non-blocking so a
    # lingering enrichment ticket can never hold promotion.
    "parent_enrichment",
})


def is_blocking(stage: str) -> bool:
    return stage not in NON_BLOCKING_STAGES

DAG_ORDER = [stage for stage, _evt, _art, _rec in STAGE_DAG]
_STAGE_SPEC = {stage: (evt, art, rec) for stage, evt, art, rec in STAGE_DAG}

DEFAULT_HIGH_WATERMARK = 64


def ticket_id(run_id: str, stage: str, generation: int = 1) -> str:
    return "tkt_" + content_hash({"run": run_id, "stage": stage, "gen": generation})[:32]


def ensure_run_tickets(conn: Connection, run_id: str, corpus_id: str,
                        execution_contract: dict | None = None) -> list[str]:
    """Create the full ticket chain for a run (idempotent). The intake
    ticket is READY immediately; every other stage starts PENDING and is
    advanced only by verified predecessor completion.

    CHAIN-CREATION-RECONCILES-HISTORY (measured live, Stage-K pilot):
    when a run's stages already completed via the legacy census/event
    path before its chain existed, minting them PENDING forced full
    model re-execution AND barrier-blocked the corpus until the replay
    drained. Stages whose latest attempt is ok are born DONE instead —
    the durable attempt IS the completion proof."""
    created = []
    for stage, event_type, _art, _rec in STAGE_DAG:
        tid = ticket_id(run_id, stage)
        row = conn.execute(
            "SELECT 1 FROM stage_tickets WHERE ticket_id=%s", (tid,)
        ).fetchone()
        if row:
            continue
        if stage == "intake":
            status = "ready"
        elif _stage_attempt_ok(conn, run_id, stage):
            status = "done"
        else:
            status = "pending"
        conn.execute(
            """
            INSERT INTO stage_tickets
                (ticket_id, run_id, corpus_id, stage, event_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, stage, generation) DO NOTHING
            """,
            (tid, run_id, corpus_id, stage, event_type, status),
        )
        created.append(tid)
        if stage == "intake" and status == "ready":
            # readiness at birth emits the work event immediately
            _emit_ticket_event(conn, tid, run_id, stage)
    if execution_contract:
        conn.execute(
            "UPDATE runs SET execution_contract=%s WHERE run_id=%s",
            (json.dumps(execution_contract), run_id),
        )
    return created


def _stage_attempt_ok(conn: Connection, run_id: str, stage: str) -> bool:
    row = conn.execute(
        """
        SELECT outcome FROM stage_attempts
         WHERE run_id=%s AND stage=%s
         ORDER BY started_at DESC LIMIT 1
        """,
        (run_id, stage),
    ).fetchone()
    if bool(row) and row[0] == "ok":
        return True
    # SUMMARY-ATTEMPT-EQUIVALENCE (measured Stage-K pilot): the summary
    # layer completes tickets WITHOUT stage_attempt rows, so the ok-
    # attempt probe is permanently False for parent/document/corpus/
    # vocabulary stages and their successors could never advance. A
    # durably committed DONE ticket is equivalent completion proof.
    t = conn.execute(
        """
        SELECT 1 FROM stage_tickets
         WHERE run_id=%s AND stage=%s AND status='done' LIMIT 1
        """,
        (run_id, stage),
    ).fetchone()
    return bool(t)


def _artifacts_present(conn: Connection, run_id: str, stage: str,
                       keys: tuple[str, ...]) -> bool:
    if not keys:
        return True
    row = conn.execute(
        "SELECT payload FROM artifacts WHERE run_id=%s AND stage=%s "
        "ORDER BY artifact_id DESC LIMIT 1",
        (run_id, stage),
    ).fetchone()
    if not row:
        return False
    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return all(k in payload for k in keys)


# RECEIPT-VERDICT-STORE-V2 (2026-08-25): explicit semantic states.
# The previous encoding stored `not present` as a bool and one call site
# read it back as `present` — a measured-MISSING verdict could then
# falsely ADVANCE a run. Forbidden. States are now explicit strings;
# there is exactly ONE writer and ONE reader representation.
#
# Contract:
#   state PRESENT -> all desired receipts exist   TTL  90s (can flip on
#                                                    store loss)
#   state MISSING -> at least one receipt absent  TTL 900s (flips only
#                                                    when receipts land)
# A stale MISSING may DELAY advancement; it can never create it.
RECEIPT_STATE_PRESENT = "PRESENT"
RECEIPT_STATE_MISSING = "MISSING"
_RECEIPT_TTL = {
    RECEIPT_STATE_PRESENT: 90.0,
    RECEIPT_STATE_MISSING: 900.0,
}
_RECEIPT_VERDICT_STORE: dict = {}


def _verdict_get(key) -> str | None:
    """Return the cached STATE if fresh, else None (expired/absent)."""
    import time as _time
    hit = _RECEIPT_VERDICT_STORE.get(key)
    if hit is None:
        return None
    written_at, state = hit
    if _time.monotonic() - written_at < _RECEIPT_TTL[state]:
        return state
    return None


def _verdict_put(key, state: str) -> None:
    assert state in (RECEIPT_STATE_PRESENT, RECEIPT_STATE_MISSING)
    import time as _time
    _RECEIPT_VERDICT_STORE[key] = (_time.monotonic(), state)


def _receipts_present(conn: Connection, run_id: str, corpus_id: str,
                      projection: str,
                      cache: dict | None = None) -> bool:
    """Desired == actual for this projection (per-object).

    RECEIPT-VERDICT-STORE-V2: the authoritative cross-tick cache is the
    explicit-state store (PRESENT/MISSING with asymmetric TTL). The
    optional `cache` dict remains only as an intra-pass memo for legacy
    callers; both layers share the same EXISTS query shape pinned by
    tests. A stale MISSING delays advancement; it can never create it.
    """
    cache_key = (run_id, projection)
    state = _verdict_get(cache_key)
    if state is not None:
        return state == RECEIPT_STATE_PRESENT
    row = conn.execute(
        """
        SELECT NOT EXISTS (
          SELECT 1 FROM chunks c
             JOIN documents d ON d.doc_id = c.doc_id
             JOIN runs r ON r.corpus_id = d.corpus_id
            WHERE r.run_id = %s
              AND NOT EXISTS (SELECT 1 FROM projection_receipts pr
                              WHERE pr.projection = %s AND pr.active
                                AND pr.entity_kind = 'chunk'
                                AND pr.entity_id = c.chunk_id)
              LIMIT 1)
        """,
        (run_id, projection),
    ).fetchone()
    result = bool(row) and bool(row[0])
    _verdict_put(cache_key,
                 RECEIPT_STATE_PRESENT if result else RECEIPT_STATE_MISSING)
    if cache is not None:
        cache[cache_key] = result
    return result


ADVANCE_PAGE = 256


def advance_tickets(conn: Connection) -> int:
    """D7-H1: keyset advancement over the eligible work set.

    Per (stage, corpus): walk PENDING tickets strictly past the stored
    scheduler cursor, verify predecessors, emit events. An empty page
    wraps the cursor (full-cycle scan); one full pass per tick maximum,
    so processing is bounded regardless of table size."""
    advanced = 0
    # RECEIPT-VERDICT-STORE-V2: the cross-tick memo is the explicit-state
    # verdict store inside _advance_pending_corpus; no per-tick dict is
    # threaded through anymore (the stale third argument crashed every
    # live tick with a TypeError between the store cutover and this fix —
    # measured: 1,864 consecutive failed ticks).
    corpora = [r[0] for r in conn.execute(
        """SELECT DISTINCT corpus_id FROM stage_tickets
           WHERE status='pending' ORDER BY corpus_id""").fetchall()]
    # TICK-CACHE-V1: completeness anti-joins are corpus-independent —
    # compute ONCE for the whole tick.
    missing_by_projection = {
        p: _corpora_with_missing_chunk_receipts(conn, p)
        for p in ("qdrant", "neo4j")} if corpora else {}
    for corpus_id in corpora:
        advanced += _advance_pending_corpus(
            conn, corpus_id, missing_by_projection)

    # READY backfill: re-emit missing claim events, keyset on seq
    ready_rows = conn.execute(
        """
        SELECT t.seq, t.ticket_id, t.run_id, t.stage FROM stage_tickets t
        WHERE t.status = 'ready'
          AND NOT EXISTS (
              SELECT 1 FROM outbox_events e
               WHERE e.run_id = t.run_id AND e.event_type = t.event_type
                 AND e.delivered_at IS NULL
                 AND e.payload->>'ticket_id' = t.ticket_id)
        ORDER BY t.seq LIMIT 256
        """
    ).fetchall()
    for seq, tid, run_id, stage in ready_rows:
        if stage not in _STAGE_SPEC:
            # OWNER-TRIGGERED stages (parent_enrichment, §0a) live outside
            # STAGE_DAG and mint their OWN events at the button; sweeping
            # them here KeyError'd the whole advance phase (measured
            # 2026-08-31: census dead 2h, every corpus frozen mid-chain).
            continue
        _emit_ticket_event(conn, tid, run_id, stage)
        conn.execute(
            """INSERT INTO scheduler_cursors (stage, corpus_id, last_seq)
               VALUES ('__ready__',%s,%s)
               ON CONFLICT (stage, corpus_id)
               DO UPDATE SET last_seq=EXCLUDED.last_seq,
                             updated_at=now()""", (stage, seq))
        advanced += 1
    _release_expired_leases(conn)
    return advanced


def _eligible_all_stages(conn, corpus_id: str, limit: int):
    after_row = conn.execute(
        "SELECT last_seq FROM scheduler_cursors "
        "WHERE stage='__all__' AND corpus_id=%s",
        (corpus_id,)).fetchone()
    after = after_row[0] if after_row else 0
    rows = conn.execute(
        """SELECT seq, ticket_id, run_id, stage FROM stage_tickets
           WHERE corpus_id=%s AND status='pending' AND seq > %s
           ORDER BY seq LIMIT %s""",
        (corpus_id, after, limit)).fetchall()
    if not rows and after:
        conn.execute(
            "UPDATE scheduler_cursors SET last_seq=0, updated_at=now() "
            "WHERE stage='__all__' AND corpus_id=%s", (corpus_id,))
        conn.commit()
        rows = []
        after = 0
    else:
        next_seq = rows[-1][0] if rows else after
        conn.execute(
            """INSERT INTO scheduler_cursors (stage, corpus_id, last_seq)
               VALUES ('__all__',%s,%s)
               ON CONFLICT (stage, corpus_id)
               DO UPDATE SET last_seq=EXCLUDED.last_seq, updated_at=now()""",
            (corpus_id, next_seq))
    return rows


def _corpora_with_missing_chunk_receipts(conn, projection: str) -> set[str]:
    """BULK-RECEIPT-COMPLETENESS-V1.

    MEASURED LIVE 2026-08-25: the previous implementation looped one
    per-run EXISTS anti-join over chunks×documents×runs — 4,316 pending
    runs × 2 projections inside ONE tick transaction ground for >100
    minutes (live reproduction of the historical 53.8-minute cold seed;
    process CPU ~0, Postgres DataFileRead-bound; documents table carried
    390k dead tuples with last_analyze=NULL, so every per-run plan was a
    bloated seq scan).

    Receipt completeness is CORPUS-scoped (chunks join documents join
    runs by corpus_id — every pending run of a corpus observes the same
    chunk gaps), so ONE set-based anti-join answers ALL runs at once:

      cost = O(chunks + receipts-index-probes) per projection per tick,
      independent of pending-run count.

    Semantics unchanged: MISSING only DELAYS advancement; a cached/
    derived MISSING can never create advancement (VERDICT-STORE-V2).
    """
    # WANT-SET-AUTHORITY-V1: rule owned by projection_want (the third
    # copy of the F6 rule lived here and wedged the barrier, 2026-08-31).
    from polymath_shared.projection_want import (
        corpora_with_missing_chunk_receipts,
    )
    return corpora_with_missing_chunk_receipts(conn, projection)


def _advance_pending_corpus(conn, corpus_id: str,
                            missing_by_projection: dict | None = None) -> int:
    # BULK-RECEIPT-COMPLETENESS-V1 + TICK-CACHE-V1: completeness truth
    # is GLOBAL (corpus-scoped anti-join over all chunks), so it is
    # computed ONCE per tick by the caller and reused for every corpus.
    # Calling it per-corpus multiplied identical 2 s anti-joins by the
    # pending-corpus count (measured 110 s advance_tickets).
    pending_runs = [r[0] for r in conn.execute(
        """SELECT DISTINCT t.run_id FROM stage_tickets t
           WHERE t.corpus_id=%s AND t.status='pending'""",
        (corpus_id,)).fetchall()]
    if not pending_runs:
        return 0
    if missing_by_projection is None:
        missing_by_projection = {
            p: _corpora_with_missing_chunk_receipts(conn, p)
            for p in ("qdrant", "neo4j")}
    for projection in ("qdrant", "neo4j"):
        corpus_is_missing = corpus_id in missing_by_projection[projection]
        state = RECEIPT_STATE_MISSING if corpus_is_missing \
            else RECEIPT_STATE_PRESENT
        for rid in pending_runs:
            if _verdict_get((rid, projection)) != state:
                _verdict_put((rid, projection), state)
    advanced = 0
    while True:
        rows = _eligible_all_stages(conn, corpus_id, ADVANCE_PAGE)
        if not rows:
            break
        for seq, tid, run_id, stage in rows:
            if _try_advance_one(conn, tid, run_id, stage):
                advanced += 1
    return advanced


def _try_advance_one(conn, tid: str, run_id: str, stage: str) -> bool:
    idx = DAG_ORDER.index(stage)
    predecessors = DAG_ORDER[:idx]
    ok = all(_stage_attempt_ok(conn, run_id, pr) for pr in predecessors)
    if ok:
        for pr in predecessors:
            _evt, art, rec = _STAGE_SPEC[pr]
            if not _artifacts_present(conn, run_id, pr, art):
                ok = False
                break
            for projection in rec:
                key = (run_id, projection)
                state = _verdict_get(key)
                if state == RECEIPT_STATE_MISSING:
                    ok = False          # stale MISSING delays; never advances
                    break
                if state is None:
                    present = _receipts_present(
                        conn, run_id, _corpus_of(conn, run_id), projection)
                    _verdict_put(key, RECEIPT_STATE_PRESENT
                                 if present else RECEIPT_STATE_MISSING)
                    if not present:
                        ok = False
                        break
            if not ok:
                break
    if not ok:
        return False
    _emit_ticket_event(conn, tid, run_id, stage)
    return True




def _corpus_of(conn: Connection, run_id: str) -> str:
    row = conn.execute(
        "SELECT corpus_id FROM runs WHERE run_id=%s", (run_id,)
    ).fetchone()
    return row[0] if row else ""


def _emit_ticket_event(conn: Connection, tid: str, run_id: str, stage: str) -> None:
    """Mark READY and upsert the stage's outbox event — the ONLY path by
    which stage work becomes claimable. Every ticket event carries the
    ORIGINAL stage payload from the producing stage's outbox row (the
    scheduler's _gap_payload contract); ticket_id is added on top."""
    event_type, _art, _rec = _STAGE_SPEC[stage]
    row = conn.execute(
        "SELECT payload FROM outbox_events WHERE run_id=%s AND event_type=%s "
        "ORDER BY event_id LIMIT 1", (run_id, event_type),
    ).fetchone()
    if row and row[0]:
        base = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    else:
        base = {"run_id": run_id}
    payload = dict(base)
    payload["ticket_id"] = tid
    key = content_hash({"run": run_id, "type": event_type, "payload": payload})
    conn.execute(
        """
        INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (idempotency_key) DO UPDATE SET delivered_at = NULL
        WHERE outbox_events.delivered_at IS NOT NULL
        """,
        (run_id, event_type, json.dumps(payload), key),
    )
    conn.execute(
        "UPDATE stage_tickets SET status='ready', updated_at=now() WHERE ticket_id=%s",
        (tid,),
    )


def _release_expired_leases(conn: Connection) -> int:
    """Lease timeout: a claimed-but-uncompleted ticket returns to READY.

    LONG-STAGE-LEASE-CORRECTNESS-V1. An expired lease is only evidence of
    a failed execution when the OWNER IS GONE. A live, heartbeating worker
    whose lease lapsed is a control-plane fault (renewal missed a beat),
    not a stage failure, so it must not burn the ticket's retry budget or
    quarantine a healthy worker — that combination silently failed all 24
    projections of release-books-v1 without one real failure.

      owner stale  -> attempt += 1, quarantine  (the executor vanished)
      owner alive  -> attempt unchanged, no quarantine, reason recorded
    """
    rows = conn.execute(
        """
        WITH expired AS (
            SELECT t.ticket_id, t.lease_owner,
                   COALESCE(w.heartbeat_at < now() - interval '90 seconds', TRUE)
                       AS owner_stale
              FROM stage_tickets t
              LEFT JOIN worker_registrations w ON w.worker_id = t.lease_owner
             WHERE t.status = 'leased' AND t.lease_expires_at < now()
        )
        UPDATE stage_tickets t SET
               status = 'ready',
               lease_owner = NULL,
               lease_expires_at = NULL,
               attempt = t.attempt + CASE WHEN e.owner_stale THEN 1 ELSE 0 END,
               last_error_note = CASE
                   WHEN e.owner_stale THEN 'lease expired: executing worker gone'
                   ELSE 'lease_expired_while_owner_alive (no retry consumed)'
               END,
               updated_at = now()
          FROM expired e
         WHERE t.ticket_id = e.ticket_id
         RETURNING e.lease_owner, e.owner_stale
        """
    ).fetchall()
    for owner, owner_stale in rows:
        if owner and owner_stale:
            conn.execute(
                "UPDATE worker_registrations SET status='quarantined', "
                "last_error='lease expired without completion' WHERE worker_id=%s",
                (owner,),
            )
    return len(rows)


def generation_barrier(conn: Connection, corpus_id: str,
                       missing_by_projection: dict | None = None) -> dict:
    """QUERY_READY for a corpus generation requires: all tickets DONE,
    zero pending/ready/leased/repair tickets, and projection desired ==
    actual. Returns the barrier verdict + what blocks it.

    TICK-CACHE-V1: callers looping over corpora pass precomputed
    missing_by_projection sets so the global anti-joins run once per
    tick, not once per corpus."""
    missing_by_projection = missing_by_projection or {
        p: _corpora_with_missing_chunk_receipts(conn, p)
        for p in ("qdrant", "neo4j")}
    # BARRIER-OPEN-WORK-V2 (2026-08-24): two measured defects fixed.
    # 1) psycopg3 rewrites %s to server-side $n placeholders where tuple
    #    adaptation cannot produce an IN-list -> SyntaxError every tick
    #    once any promotion existed. `!= ALL(list)` binds correctly.
    # 2) superseded/failed HISTORY rows are not open work; counting them
    #    kept reconciled corpora permanently barrier-blocked.
    pending = conn.execute(
        "SELECT stage, status, COUNT(*) FROM stage_tickets "
        "WHERE corpus_id=%s AND status IN ('pending','ready','leased') "
        "AND archived_at IS NULL "
        "AND stage != ALL(%s) GROUP BY 1,2",
        (corpus_id, sorted(NON_BLOCKING_STAGES)),
    ).fetchall()
    runs = conn.execute(
        "SELECT run_id FROM runs WHERE corpus_id=%s", (corpus_id,)
    ).fetchall()
    incomplete_receipts = 0
    run_ids = [r[0] for r in runs]
    # BULK-RECEIPT-COMPLETENESS-V1: receipt truth is corpus-scoped, so
    # the barrier consults the (precomputed) gap sets per projection.
    for projection in ("qdrant", "neo4j"):
        if corpus_id in missing_by_projection[projection]:
            incomplete_receipts += len(run_ids)
    return {
        "open_tickets": sum(count for _s, _st, count in pending),
        "open_by_status": {f"{s}/{st}": c for s, st, c in pending},
        "incomplete_projections": incomplete_receipts,
        "passed": not pending and incomplete_receipts == 0,
    }


GLOBAL_EXTRACT_LIMIT = 256
CORPUS_EXTRACT_WATERMARK = 64


def extract_active_count(conn: Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM stage_tickets WHERE stage=%s "
        "AND status IN ('pending','ready','leased')", ("extract",)
    ).fetchone()
    return row[0] if row else 0


def backpressure_decision(conn: Connection,
                          corpus_id: str) -> tuple[bool, str]:
    """Two-tier hierarchy (owner D7 fix): GLOBAL resource ceiling first,
    then PER-CORPUS stage watermark. One busy corpus can never starve
    another, and N saturated corpora still respect the global limit."""
    if extract_active_count(conn) >= GLOBAL_EXTRACT_LIMIT:
        return True, "global_ceiling"
    row = conn.execute(
        "SELECT COUNT(*) FROM stage_tickets WHERE corpus_id=%s "
        "AND stage=%s AND status IN ('pending','ready','leased')",
        (corpus_id, "extract")).fetchone()
    if row and row[0] >= CORPUS_EXTRACT_WATERMARK:
        return True, "corpus_watermark"
    return False, ""


def backpressure_paused(conn: Connection, stage: str = "extract",
                        watermark: int = DEFAULT_HIGH_WATERMARK) -> bool:
    """High watermark: pause NEW intake ticket creation when a downstream
    stage's pending queue is deep (bounded queues; nothing is lost —
    ticket creation resumes as the queue drains)."""
    # SUPERSEDED by backpressure_decision (D7 fix): kept as the global
    # ceiling view only.
    return extract_active_count(conn) >= GLOBAL_EXTRACT_LIMIT


def _reset_cursor(conn, stage: str, corpus_id: str) -> int:
    """Wrap-around: after a full pass, restart from the beginning so no
    ticket is ever invisible because of its table position."""
    conn.execute(
        "UPDATE scheduler_cursors SET last_seq=0, updated_at=now() "
        "WHERE stage=%s AND corpus_id=%s", (stage, corpus_id))
    return 0


def eligible_page(conn, *, stage: str, corpus_id: str,
                  limit: int = 256) -> tuple[list[tuple], int]:
    """D7-H1: keyset page over the ELIGIBLE WORK SET.

    Returns (rows, next_seq). rows are PENDING tickets for
    (stage, corpus) with seq strictly greater than the stored cursor;
    an empty page wraps the cursor to zero (full-cycle scan), so every
    ticket becomes visible again exactly once per cycle."""
    row = conn.execute(
        "SELECT last_seq FROM scheduler_cursors "
        "WHERE stage=%s AND corpus_id=%s", (stage, corpus_id)).fetchone()
    after = row[0] if row else 0
    rows = conn.execute(
        """SELECT seq, ticket_id, run_id FROM stage_tickets
           WHERE stage=%s AND corpus_id=%s AND status='pending'
           AND seq > %s ORDER BY seq LIMIT %s""",
        (stage, corpus_id, after, limit)).fetchall()
    if not rows and after:
        # exhausted: signal empty page and rewind for the next cycle
        conn.execute(
            "UPDATE scheduler_cursors SET last_seq=0, updated_at=now() "
            "WHERE stage=%s AND corpus_id=%s", (stage, corpus_id))
        return [], 0
    next_seq = rows[-1][0] if rows else after
    conn.execute(
        """INSERT INTO scheduler_cursors (stage, corpus_id, last_seq)
           VALUES (%s,%s,%s)
           ON CONFLICT (stage, corpus_id)
           DO UPDATE SET last_seq=EXCLUDED.last_seq, updated_at=now()""",
        (stage, corpus_id, next_seq))
    return rows, next_seq


# --- D7-5d: creation fairness + hysteresis ------------------------------

def refresh_corpus_runtime_state(conn, *, watermark: int | None = None) -> dict:
    """Recompute per-corpus active extract counts and apply the sticky
    creation gate: pause enters at >= watermark; resumes only at
    <= watermark/2 (hysteresis kills the flip-flop)."""
    wm = watermark or CORPUS_EXTRACT_WATERMARK
    rows = conn.execute(
        """SELECT corpus_id, COUNT(*) FROM stage_tickets
           WHERE stage='extract' AND status IN ('pending','ready','leased')
           GROUP BY corpus_id""").fetchall()
    active = {r[0]: r[1] for r in rows}
    # corpora with ticketless runs still count as needing service
    for r in conn.execute(
            """SELECT DISTINCT r.corpus_id FROM runs r
               JOIN corpora c ON c.corpus_id = r.corpus_id
               WHERE r.status IN ('intake','reconciling','degraded')
               AND NOT EXISTS (SELECT 1 FROM stage_tickets t
                               WHERE t.run_id=r.run_id)""").fetchall():
        active.setdefault(r[0], 0)
    changed = {}
    for corpus_id, n in active.items():
        row = conn.execute(
            "SELECT creation_paused, watermark FROM corpus_runtime_state "
            "WHERE corpus_id=%s", (corpus_id,)).fetchone()
        was_paused = bool(row and row[0])
        eff_wm = (row[1] if row and row[1] else wm)
        if not was_paused and n >= eff_wm:
            paused = True
        elif was_paused and n <= eff_wm // 2:
            paused = False
        else:
            paused = was_paused
        conn.execute(
            """INSERT INTO corpus_runtime_state (corpus_id, active_tickets,
               watermark, creation_paused, updated_at)
               VALUES (%s,%s,%s,%s,now())
               ON CONFLICT (corpus_id) DO UPDATE SET
                 active_tickets=EXCLUDED.active_tickets,
                 watermark=EXCLUDED.watermark,
                 creation_paused=EXCLUDED.creation_paused,
                 updated_at=now()""",
            (corpus_id, n, eff_wm, paused))
        if paused != was_paused:
            changed[corpus_id] = paused
    return {"active": active, "changed": changed}


def eligible_creation_corpora(conn, window: int = 32) -> list[str]:
    """Fair share: non-paused, non-archived corpora round-robin by
    last_creation_tick (NULLS FIRST = never served before), oldest tick
    first. ARCHIVED-CORPUS-REGISTRY: archived corpora are out of the
    scheduling lifecycle entirely."""
    return [r[0] for r in conn.execute(
        """SELECT c.corpus_id FROM corpus_runtime_state c
           WHERE c.creation_paused = FALSE
             AND NOT EXISTS (SELECT 1 FROM archived_corpora ac
                              WHERE ac.corpus_id = c.corpus_id)
           ORDER BY c.last_creation_tick ASC NULLS FIRST,
                    c.corpus_id ASC LIMIT %s""",
        (window,)).fetchall()]


def fair_ensure_tickets_backpressure_gated(conn, *,
                                           window: int = 32) -> int:
    """D7-5d entry point: refresh hysteresis state, distribute the
    creation window round-robin across ELIGIBLE corpora."""
    refresh_corpus_runtime_state(
        conn, watermark=CORPUS_EXTRACT_WATERMARK)
    eligible = eligible_creation_corpora(conn, window=window)
    ensured = 0
    per = max(1, window // max(len(eligible), 1))
    for corpus_id in eligible:
        # CREATION-ROUND-ROBIN-V2: mark service BEFORE checking for
        # work. MEASURED LIVE: skipping the timestamp update for
        # work-less corpora pinned 35 stale entries at the front of the
        # rotation, starving new corpora past the window edge forever
        # (pilot-modern-v1 got zero ticket chains for 70 minutes while
        # position 36 of a 32-wide window).
        conn.execute(
            """UPDATE corpus_runtime_state SET last_creation_tick=now()
               WHERE corpus_id=%s""", (corpus_id,))
        runs = conn.execute(
            """SELECT r.run_id FROM runs r
               JOIN corpora c ON c.corpus_id = r.corpus_id
               WHERE r.corpus_id=%s
               AND r.status IN ('intake','reconciling','degraded')
               AND NOT EXISTS (SELECT 1 FROM stage_tickets t
                               WHERE t.run_id=r.run_id)
               ORDER BY r.created_at LIMIT %s""",
            (corpus_id, per)).fetchall()
        if not runs:
            continue
        for (run_id,) in runs:
            ensured += len(ensure_run_tickets(
                conn, run_id, corpus_id,
                default_execution_contract()))
    return ensured
