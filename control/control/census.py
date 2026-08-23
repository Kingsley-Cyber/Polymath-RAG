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


def compute_census(conn: Connection, *, max_attempts: int = 3) -> Census:
    """Deterministic census over non-terminal runs.

    Sort orders are explicit (ISSUES_REPORT §2.3 fix): runs by created
    time, attempts by stage + started time, so two ticks over the same
    state produce the same schedule.
    """
    census = Census()

    runs = conn.execute(
        """
        SELECT run_id, corpus_id, status
          FROM runs
         WHERE status IN ('intake', 'reconciling', 'degraded')
         ORDER BY created_at, run_id
        """
    ).fetchall()

    attempts = conn.execute(
        """
        SELECT run_id, stage, outcome, started_at
          FROM stage_attempts
         ORDER BY run_id, stage, started_at
        """
    ).fetchall()
    attempts_by_run: dict[str, list[tuple[str, str, object]]] = {}
    for row in attempts:
        attempts_by_run.setdefault(row[0], []).append((row[1], row[2], row[3]))

    for run_id, corpus_id, _status in runs:
        history = attempts_by_run.get(run_id, [])
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
                missing = _missing_projection_receipts(conn, run_id, stage)
                if missing:
                    census.gaps.append(Gap(
                        run_id=run_id, corpus_id=corpus_id, stage=stage,
                        event_type=STAGE_EVENTS[stage],
                        reason=f"{len(missing)} projection receipts missing",
                    ))
                    complete = False

        if complete and not census.fail:
            census.promote.append(run_id)

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
