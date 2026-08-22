"""canonicalize stage: corpus-level canonical registry (C1, ADR 0009).

Consumes `canonicalize.v1` outbox events (scheduled by the census after
verify_projections). Recomputation is deterministic: the same corpus
state always produces the same canonical ids, memberships, and pair
decisions, so replay is a no-op and an incremental addition produces
only the required delta (delete-stale + insert-missing inside one
stage transaction).

Canonicalization NEVER mutates local entity/fact/evidence rows — the
registry is an additive corpus layer with full lineage back to the
source-local knowledge.
"""
from __future__ import annotations

import json
import logging
import time

import psycopg
from psycopg import Connection

from polymath_shared.canonicalizer import (
    CANONICALIZER_VERSION,
    canonicalize,
)
from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)

STAGE = "canonicalize"
EVENT_TYPE = "canonicalize.v1"
CONTRACT_VERSION = "1.0.0"

log = logging.getLogger("canonicalize")


def _corpus_entities(conn: Connection, corpus_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT DISTINCT e.entity_id, e.core_type, e.normalized_surface
          FROM entities e
          JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE d.corpus_id = %s
           AND e.admission_class IS DISTINCT FROM 'MENTION_ONLY'
           AND e.admission_class IS DISTINCT FROM 'DOCUMENT_SCOPED'
         ORDER BY e.entity_id
        """,
        (corpus_id,),
    ).fetchall()
    return [
        {"entity_id": r[0], "core_type": r[1], "normalized_surface": r[2]}
        for r in rows
    ]


def _corpus_aliases(conn: Connection, corpus_id: str) -> dict[str, list[str]]:
    row = conn.execute(
        "SELECT profile FROM corpora WHERE corpus_id = %s", (corpus_id,)
    ).fetchone()
    if row is None:
        return {}
    profile = row[0] or {}
    raw = profile.get("canonical_aliases") or {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(canon): [str(a) for a in aliases]
        for canon, aliases in raw.items()
        if isinstance(aliases, list)
    }


def _apply_registry(conn: Connection, corpus_id: str, out) -> dict:
    """Diff-apply the desired registry on the caller's connection (the
    stage transaction provides the atomic boundary): delete stale rows,
    insert missing ones. Identical recomputation is a no-op;
    incremental ingestion yields only the required delta."""
    conn.execute(
        "DELETE FROM canonicalization_decisions WHERE corpus_id = %s",
        (corpus_id,),
    )
    conn.execute(
        "DELETE FROM canonical_memberships WHERE corpus_id = %s",
        (corpus_id,),
    )
    conn.execute(
        "DELETE FROM canonical_entities WHERE corpus_id = %s",
        (corpus_id,),
    )
    for c in out.canonical_entities:
        conn.execute(
            """
            INSERT INTO canonical_entities
                (corpus_id, canonical_id, canonical_type, normalized_name,
                 canonicalizer_version)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (corpus_id, canonical_id) DO NOTHING
            """,
            (corpus_id, c.canonical_id, c.canonical_type,
             c.normalized_name, c.canonicalizer_version),
        )
    for m in out.memberships:
        conn.execute(
            """
            INSERT INTO canonical_memberships
                (corpus_id, canonical_id, local_entity_id, decision,
                 confidence, basis, canonicalizer_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (corpus_id, local_entity_id) DO NOTHING
            """,
            (corpus_id, m.canonical_id, m.local_entity_id, m.decision,
             m.confidence, json.dumps(m.basis), m.canonicalizer_version),
        )
    for d in out.decisions:
        conn.execute(
            """
            INSERT INTO canonicalization_decisions
                (corpus_id, decision_id, local_entity_a, local_entity_b,
                 decision, confidence, basis, canonical_id,
                 canonicalizer_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (decision_id) DO NOTHING
            """,
            (corpus_id, d.decision_id, d.local_entity_a, d.local_entity_b,
             d.decision, d.confidence, json.dumps(d.basis),
             d.canonical_id, d.canonicalizer_version),
        )
    return {
        "canonical_entities": len(out.canonical_entities),
        "memberships": len(out.memberships),
        "decisions": len(out.decisions),
    }


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    row = conn.execute(
        "SELECT corpus_id FROM runs WHERE run_id = %s", (run_id,)
    ).fetchone()
    if row is None:
        raise StageFailed(run_id, STAGE)
    corpus_id = row[0]

    contract = stage_contract_hash(STAGE, {
        "contract_version": CONTRACT_VERSION,
        "canonicalizer_version": CANONICALIZER_VERSION,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        entities = _corpus_entities(conn, corpus_id)
        aliases = _corpus_aliases(conn, corpus_id)
        out = canonicalize(corpus_id, entities, aliases)
        counts = _apply_registry(conn, corpus_id, out)
        writer.artifact({
            "corpus_id": corpus_id,
            "canonicalizer_version": CANONICALIZER_VERSION,
            **counts,
        })
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    """LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1.

    A worker executes tickets serially, so claiming ahead bought nothing
    but made "held" differ from "being processed" -- and a stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type.
    """
    from polymath_shared.worker_runtime import run_worker

    run_worker('canonicalize', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()
