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

STAGE_CHAIN = ["intake", "extract", "profile_document", "project_qdrant", "project_neo4j", "verify_projections"]

# Each stage's re-drive event type. Projection stages have their own
# event types so the census can schedule them independently — two
# projectors never race over one shared outbox row.
STAGE_EVENTS = {
    "intake": "intake.v1",
    "extract": "chunked.v1",
    "profile_document": "profile_document.v1",
    "project_qdrant": "project_qdrant.v1",
    "project_neo4j": "project_neo4j.v1",
    "verify_projections": "verify.v1",
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
            for stage in ("project_qdrant", "project_neo4j"):
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
        return [r[0] for r in rows]
    rows = conn.execute(
        """
        SELECT e.fact_id FROM evidence e
          JOIN documents d ON d.doc_id = e.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
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
