"""Desired-vs-observed artifact census (the v3.3 algorithm, new substrate).

The census drives work from "what should exist" rather than "what's in a
queue" — a planner-eligible gap is by construction a planner-actionable
gap (ISSUES_REPORT §2.3: this pattern was correct in v3.3).

v1 desired stage chain per run: intake -> extract (the chunked.v1 event
commits in the same transaction as the intake receipt, so the event gap
is impossible by construction; the census still covers it for crash
forensics).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from psycopg import Connection

STAGE_CHAIN = ["intake", "extract", "profile_document", "project_qdrant", "project_neo4j", "canonicalize", "project_canonical", "verify_projections"]

# Each stage's re-drive event type. Projection stages have their own
# event types so the census can schedule them independently — two
# projectors never race over one shared outbox row.
# Order note (Q1): canonicalize/project_canonical run BEFORE
# verify_projections so the verifier reconciles the canonical graph
# only when it is due (no false degraded states on incremental
# ingestion).
STAGE_EVENTS = {
    "intake": "intake.v1",
    "extract": "chunked.v1",
    "profile_document": "profile_document.v1",
    "project_qdrant": "project_qdrant.v1",
    "project_neo4j": "project_neo4j.v1",
    "verify_projections": "verify.v1",
    "canonicalize": "canonicalize.v1",
    "project_canonical": "project_canonical.v1",
}


@dataclass
class Gap:
    run_id: str
    corpus_id: str
    stage: str
    event_type: str
    reason: str


@dataclass
class Census:
    gaps: list[Gap] = field(default_factory=list)
    promote: list[str] = field(default_factory=list)
    fail: list[str] = field(default_factory=list)


# INCREMENTAL-CENSUS-V1 (2026-08-25): the routine control pass no longer
# re-derives state for every historical run. stage_attempts is the
# sufficient mutator signal for a run's gap verdict — receipt writes and
# clears happen inside stage transactions that record attempts — so runs
# without post-watermark attempts reuse their previous tick's verdict.
#
#   NORMAL OPERATION              RECOVERY / AUDIT
#   incremental (dirty only)      full sweep
#
# Full mode remains authoritative and is forced by:
#   POLYMATH_CENSUS_MODE=full  or  POLYMATH_CENSUS_AUDIT=1
# Watermark lives in scheduler_cursors (stage='__census__',
# corpus_id='__global__', last_seq = started_at epoch-micros) and is
# written in the SAME transaction as the tick's resulting work, so a
# crash rolls both back together (no lost changes, safe replay).
_CENSUS_CURSOR_STAGE = "__census__"
_CENSUS_CURSOR_CORPUS = "__global__"
_HISTORY_CACHE: dict[str, list[tuple[str, str, object]]] = {}
_VERDICT_CACHE: dict[str, dict] = {}

# CENSUS-PHASE-TIMING-V1: always-on phase telemetry for the tick that
# just ran. Overhead is a handful of perf_counter pairs; consumers call
# pop_census_timing() after compute_census returns.
_TIMING_KEYS = (
    "runs_query_ms", "dirty_select_ms", "attempts_fetch_ms",
    "python_loop_ms", "receipt_checks_ms", "receipt_queries",
    "mode", "runs_evaluated",
)
_LAST_TIMING: dict | None = None


def pop_census_timing() -> dict | None:
    """Return (and clear) the phase timings of the last compute_census."""
    global _LAST_TIMING
    out, _LAST_TIMING = _LAST_TIMING, None
    return out


def _watermark_read(conn: Connection):
    row = conn.execute(
        """SELECT last_seq FROM scheduler_cursors
           WHERE stage=%s AND corpus_id=%s""",
        (_CENSUS_CURSOR_STAGE, _CENSUS_CURSOR_CORPUS)).fetchone()
    return row[0] if row else None


def _watermark_write(conn: Connection, epoch_us: int) -> None:
    conn.execute(
        """INSERT INTO scheduler_cursors (stage, corpus_id, last_seq)
           VALUES (%s,%s,%s)
           ON CONFLICT (stage, corpus_id)
           DO UPDATE SET last_seq=EXCLUDED.last_seq, updated_at=now()""",
        (_CENSUS_CURSOR_STAGE, _CENSUS_CURSOR_CORPUS, epoch_us))


def _epoch_us(dt) -> int:
    import datetime as _dt
    if dt is None:
        return 0
    if isinstance(dt, _dt.datetime):
        return int(dt.timestamp() * 1_000_000)
    return int(dt)


def compute_census(conn: Connection, *, max_attempts: int = 3,
                   mode: str | None = None) -> Census:
    """Deterministic census over non-terminal runs.

    Sort orders are explicit (ISSUES_REPORT §2.3 fix): runs by created
    time, attempts by stage + started time, so two ticks over the same
    state produce the same schedule.
    """
    global _LAST_TIMING
    census = Census()

    import os as _os
    import time as _time
    _t_all = _time.perf_counter()
    timing: dict = {"receipt_checks_ms": 0.0, "receipt_queries": 0}

    mode = (mode or os.environ.get("POLYMATH_CENSUS_MODE", "auto")).lower()
    if os.environ.get("POLYMATH_CENSUS_AUDIT") == "1":
        mode = "full"
    wm_us = _watermark_read(conn)
    if mode == "auto":
        mode = "incremental" if wm_us is not None else "full"
    if mode == "incremental" and wm_us is None:
        # no durable watermark yet: a cold controller must seed via one
        # authoritative full pass before narrowing to dirty runs.
        mode = "full"
    timing["mode"] = mode

    _t0 = _time.perf_counter()
    runs = conn.execute(
        """
        SELECT run_id, corpus_id, status, created_at
          FROM runs
         WHERE status IN ('intake', 'reconciling', 'degraded')
          ORDER BY created_at, run_id
        """
    ).fetchall()
    timing["runs_query_ms"] = round((_time.perf_counter() - _t0) * 1000, 1)

    if mode == "incremental":
        overlap_us = 1_000_000  # 1s replay window; derivation is idempotent
        _t0 = _time.perf_counter()
        changed = {
            r[0] for r in conn.execute(
                """SELECT DISTINCT run_id FROM stage_attempts
                   WHERE started_at > now() - %s::interval""",
                (f"{(_time.time()*1e6 - wm_us + overlap_us)/1e6:.3f} seconds",),
            ).fetchall()}
        timing["dirty_select_ms"] = round(
            (_time.perf_counter() - _t0) * 1000, 1)
        # brand-new active runs have no attempts yet but need first census
        new_runs = {r[0] for r in runs
                    if _epoch_us(r[3]) > wm_us - overlap_us}
        changed |= new_runs
    else:
        changed = None  # full sweep

    attempts_by_run: dict[str, list[tuple[str, str, object]]] = {}
    if changed is None:
        _t0 = _time.perf_counter()
        attempts = conn.execute(
            """
            SELECT run_id, stage, outcome, started_at
              FROM stage_attempts
             ORDER BY run_id, stage, started_at
            """
        ).fetchall()
        timing["attempts_fetch_ms"] = round(
            (_time.perf_counter() - _t0) * 1000, 1)
        for row in attempts:
            attempts_by_run.setdefault(row[0], []).append(
                (row[1], row[2], row[3]))
        _HISTORY_CACHE.clear()
        _HISTORY_CACHE.update(attempts_by_run)
    else:
        # merge only changed runs' histories into the durable cache;
        # unchanged runs reuse cached history AND their previous verdict.
        fresh = changed & {r[0] for r in runs}
        if fresh:
            _t0 = _time.perf_counter()
            rows = conn.execute(
                """
                SELECT run_id, stage, outcome, started_at
                  FROM stage_attempts
                 WHERE run_id = ANY(%s)
                 ORDER BY run_id, stage, started_at
                """,
                (sorted(fresh),),
            ).fetchall()
            timing["dirty_select_ms"] = timing.get("dirty_select_ms", 0.0) \
                + round((_time.perf_counter() - _t0) * 1000, 1)
            by_run: dict[str, list] = {}
            for row in rows:
                by_run.setdefault(row[0], []).append(
                    (row[1], row[2], row[3]))
            _HISTORY_CACHE.update(by_run)

    max_seen_us = wm_us or 0
    _t_loop = _time.perf_counter()

    for run_id, corpus_id, _status, created_at in runs:
        if changed is not None and run_id not in changed:
            verdict = _VERDICT_CACHE.get(run_id)
            if verdict is not None:
                census.gaps.extend(verdict["gaps"])
                if verdict["promote"]:
                    census.promote.append(run_id)
                if verdict["fail"]:
                    census.fail.append(run_id)
                continue
            # no prior verdict (cache cold after restart): fall through to
            # full per-run evaluation using cached history; history cache
            # may be empty here, so backfill this run's history.
            if run_id not in _HISTORY_CACHE:
                rows = conn.execute(
                    """SELECT stage, outcome, started_at FROM stage_attempts
                       WHERE run_id=%s ORDER BY started_at""",
                    (run_id,)).fetchall()
                _HISTORY_CACHE[run_id] = list(rows)

        history = _HISTORY_CACHE.get(run_id, [])
        max_seen_us = max(max_seen_us,
                          max((_epoch_us(h[2]) for h in history), default=0),
                          _epoch_us(created_at))
        last_by_stage: dict[str, tuple[str, object]] = {}
        count_by_stage: dict[str, int] = {}
        for stage, outcome, started_at in history:
            last_by_stage[stage] = (outcome, started_at)
            count_by_stage[stage] = count_by_stage.get(stage, 0) + 1

        if not last_by_stage:
            census.gaps.append(Gap(
                run_id=run_id, corpus_id=corpus_id, stage="intake",
                event_type="intake.v1",
                reason="no intake attempt recorded",
            ))
            continue

        complete = True
        for stage in STAGE_CHAIN:
            outcome = last_by_stage.get(stage, (None, None))[0]
            if outcome == "ok":
                continue
            if outcome == "failed" and count_by_stage.get(stage, 0) < max_attempts:
                census.gaps.append(Gap(
                    run_id=run_id, corpus_id=corpus_id, stage=stage,
                    event_type=STAGE_EVENTS[stage],
                    reason=f"stage {stage} failed; retry {count_by_stage.get(stage, 0)}/{max_attempts}",
                ))
                complete = False
            elif outcome == "failed":
                census.fail.append(run_id)
                complete = False
            else:
                complete = False
                census.gaps.append(Gap(
                    run_id=run_id, corpus_id=corpus_id, stage=stage,
                    event_type=STAGE_EVENTS[stage],
                    reason=f"stage {stage} missing",
                ))

        if complete and not census.fail:
            # Projection receipt census: an ok projection stage can still
            # have missing receipts (store loss cleared by VERIFY). Re-arm
            # the stage so the projector re-drives (PLAN Phase F gate 1/2).
            for stage in ("project_qdrant", "project_neo4j", "project_canonical"):
                _t0 = _time.perf_counter()
                missing = _missing_projection_receipts(conn, run_id, stage)
                timing["receipt_checks_ms"] += round(
                    (_time.perf_counter() - _t0) * 1000, 1)
                if missing:
                    census.gaps.append(Gap(
                        run_id=run_id, corpus_id=corpus_id, stage=stage,
                        event_type=STAGE_EVENTS[stage],
                        reason=f"{len(missing)} projection receipts missing",
                    ))
                    complete = False

        if complete and not census.fail:
            census.promote.append(run_id)

        # INCREMENTAL-CENSUS-V1: remember each run's derived outcome so
        # unchanged runs can be replayed verbatim next tick.
        _VERDICT_CACHE[run_id] = {
            "gaps": [g for g in census.gaps if g.run_id == run_id],
            "promote": run_id in census.promote,
            "fail": run_id in census.fail,
        }

    # prune cache entries for runs that left the active set
    active_ids = {r[0] for r in runs}
    for stale in list(_VERDICT_CACHE):
        if stale not in active_ids:
            _VERDICT_CACHE.pop(stale, None)
            _HISTORY_CACHE.pop(stale, None)

    # Full passes SEED the watermark; incremental passes advance it.
    # Written inside the caller's transaction so a crash rolls the
    # watermark back together with the tick's work (safe replay).
    if max_seen_us > (wm_us or 0):
        _watermark_write(conn, max_seen_us)
    timing["python_loop_ms"] = round((_time.perf_counter() - _t_loop) * 1000, 1)
    timing["census_total_ms"] = round((_time.perf_counter() - _t_all) * 1000, 1)
    timing["runs_evaluated"] = len(runs)
    _LAST_TIMING = timing
    return census


def _missing_projection_receipts(conn: Connection, run_id: str, stage: str) -> list[str]:
    if stage == "project_qdrant":
        rows = conn.execute(
            """
            SELECT c.chunk_id FROM chunks c
              JOIN documents d ON d.doc_id = c.doc_id
              JOIN runs r ON r.corpus_id = d.corpus_id
             WHERE r.run_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'qdrant'
                      AND pr.entity_kind = 'chunk'
                      AND pr.active
                      AND pr.entity_id = c.chunk_id)
            """,
            (run_id,),
        ).fetchall()
        missing = [r[0] for r in rows]
        # R1B: neural routing representations are production dependencies
        # for a query-ready corpus — their receipts must also converge.
        # SET-BASED ANTI-JOIN: this used to be a per-entity SELECT loop
        # inside the tick transaction — hundreds of round trips per
        # complete run, observed live holding the tick open for MINUTES
        # while every worker claim queued behind it. One query, same
        # result, deterministic order.
        routing_missing = conn.execute(
            """
            WITH want AS (
                SELECT rs.summary_id AS id,
                       'routing_document_summary' AS kind
                  FROM retrieval_summaries rs
                  JOIN runs r ON r.corpus_id = rs.corpus_id
                 WHERE r.run_id = %s
                   AND rs.kind = 'document_retrieval_summary'
                UNION ALL
                SELECT rs.summary_id, 'routing_section_summary'
                  FROM retrieval_summaries rs
                  JOIN runs r ON r.corpus_id = rs.corpus_id
                 WHERE r.run_id = %s
                   AND rs.kind = 'section_retrieval_summary'
                UNION ALL
                SELECT c.chunk_id, 'routing_child'
                  FROM chunks c
                  JOIN documents d ON d.doc_id = c.doc_id
                  JOIN runs r ON r.corpus_id = d.corpus_id
                 WHERE r.run_id = %s AND c.tier = 'child'
            )
            SELECT w.id FROM want w
             WHERE NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'qdrant'
                      AND pr.entity_kind = w.kind
                      AND pr.active AND pr.entity_id = w.id)
            ORDER BY w.id
            """,
            (run_id, run_id, run_id),
        ).fetchall()
        missing.extend(r[0] for r in routing_missing)
        return missing
    if stage == "project_neo4j":
        # I3R-R5: eligible facts and chunk nodes are part of the
        # query-ready contract; missing active neo4j receipts re-drive
        # the projector (in-flight-edge convergence path).
        from polymath_shared.neo4j_eligibility import fact_eligible_sql
        fact_rows = conn.execute(
            """
            SELECT f.fact_id FROM facts f
              JOIN evidence ev ON ev.fact_id = f.fact_id
              JOIN documents d ON d.doc_id = ev.doc_id
              JOIN runs r ON r.corpus_id = d.corpus_id
             WHERE r.run_id = %s
               AND """ + fact_eligible_sql("f") + """
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'neo4j' AND pr.entity_kind = 'fact'
                      AND pr.active AND pr.entity_id = f.fact_id)
            """,
            (run_id,),
        ).fetchall()
        missing = [r[0] for r in fact_rows]
        chunk_rows = conn.execute(
            """
            SELECT c.chunk_id FROM chunks c
              JOIN documents d ON d.doc_id = c.doc_id
              JOIN runs r ON r.corpus_id = d.corpus_id
             WHERE r.run_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'neo4j' AND pr.entity_kind = 'chunk'
                      AND pr.active AND pr.entity_id = c.chunk_id)
            """,
            (run_id,),
        ).fetchall()
        missing.extend(r[0] for r in chunk_rows)
        return missing
    if stage == "project_canonical":
        rows = conn.execute(
            """
            SELECT ce.canonical_id FROM canonical_entities ce
              JOIN runs r ON r.corpus_id = ce.corpus_id
             WHERE r.run_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'neo4j'
                      AND pr.entity_kind = 'canonical_entity'
                      AND pr.active
                      AND pr.entity_id = ce.canonical_id)
            UNION ALL
            SELECT cm.local_entity_id FROM canonical_memberships cm
              JOIN runs r ON r.corpus_id = cm.corpus_id
             WHERE r.run_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'neo4j'
                      AND pr.entity_kind = 'canonical_membership'
                      AND pr.active
                      AND pr.entity_id = cm.local_entity_id)
            UNION ALL
            SELECT ev.evidence_id FROM evidence ev
              JOIN documents d ON d.doc_id = ev.doc_id
              JOIN runs r ON r.corpus_id = d.corpus_id
             WHERE r.run_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM projection_receipts pr
                    WHERE pr.projection = 'neo4j'
                      AND pr.entity_kind = 'evidence_chunk'
                      AND pr.active
                      AND pr.entity_id = ev.evidence_id)
            """,
            (run_id, run_id, run_id),
        ).fetchall()
        return [r[0] for r in rows]
    from polymath_shared.neo4j_eligibility import fact_eligible_sql

    # Receipt expectations must obey the Neo4j-eligibility predicate:
    # MENTION_ONLY-dependent facts are intentionally parked in Postgres
    # and are NOT projection failures (no synthetic receipts).
    rows = conn.execute(
        """
        SELECT e.fact_id FROM evidence e
          JOIN documents d ON d.doc_id = e.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
          JOIN facts f ON f.fact_id = e.fact_id
         WHERE r.run_id = %s
           AND """ + fact_eligible_sql("f") + """
           AND NOT EXISTS (
               SELECT 1 FROM projection_receipts pr
                WHERE pr.projection = 'neo4j'
                  AND pr.entity_kind = 'fact'
                  AND pr.active
                  AND pr.entity_id = e.fact_id)
        """,
        (run_id,),
    ).fetchall()
    return [r[0] for r in rows]
