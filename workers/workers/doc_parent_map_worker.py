"""DOCUMENT-SEMANTIC-INDEX-V1 slice S9 — the durable doc_parent_map worker.

Plan of record: docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §20, §36.5.
Migration authority: docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md §S5
(durable map worker/manifests), §28 (failure recovery / inference transaction
pattern), §10 (long-document fairness).

This module owns the DURABLE ORCHESTRATION of parent mapping over the migration-0054
tables (Postgres = workflow truth; Qdrant projection is a later slice, S10). It ties
the already-built deterministic pieces together:

    build_parent_skeletons (S1)  -> plan_batches (S3)  -> [ INFERENCE ]  ->
    compile_maps (S2)  -> persist active maps + exclusions (S4 tables)

with three load-bearing durability properties:

* **Never hold a DB transaction open across inference** (§28): a short tx PREPARES
  the batch manifests; the worker leases a batch, commits the lease, calls the model
  OUTSIDE any transaction, then a short tx persists the valid results.
* **Partial output is durable useful work** (§18.4): the valid lines of a partial
  response are persisted; only the missing aliases are re-inferred; a successfully
  mapped parent is never re-run.
* **Restart / retry is idempotent** (§36.5): batch identity is the S3 source-bound
  ``batch_hash`` and map identity is the S2 ``map_hash``, so a kill/restart produces
  exactly the same active map set — re-inference of an already-active parent is a
  no-op.

The INFERENCE BOUNDARY is injected as ``infer`` — a callable
``(skeletons, *, is_combined) -> raw_response``. This module makes NO provider call
and holds NO fleet wiring itself: the live Groq-backed ``infer`` closure and the
stage registration are the owner-gated wiring (they spend provider quota and change
live ingestion). Tests drive the full durable cycle with a deterministic fake
``infer``. This is the same "build the durable core, wire the live call later"
sequencing S1-S4 followed (each landed with "no worker consumes it yet").
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from polymath_shared.document_profile import map_batches, map_compiler
from polymath_shared.document_profile.parent_skeleton import (
    ParentSkeleton,
    SkeletonManifest,
    build_parent_skeletons,
)

MAP_WORKER_VERSION = "doc-parent-map-worker-v1"
DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3

#: The injected inference boundary. Real wiring supplies a Groq-backed closure that
#: builds the map prompt from the skeletons and returns the raw MAP-DSL response;
#: tests supply a deterministic fake. This module never calls a provider itself.
Infer = Callable[[Sequence[ParentSkeleton]], str]


@dataclass
class MappingOutcome:
    doc_id: str
    map_contract: str
    eligible_parents: int
    excluded_parents: int
    batches_total: int
    batches_done: int
    batches_partial: int
    parents_mapped: int
    unresolved_parent_ids: tuple[str, ...] = ()
    attempts_used: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        return not self.unresolved_parent_ids and self.batches_partial == 0


# --------------------------------------------------------------- durable store ops
# Each takes a live connection; the CALLER owns the transaction boundary (§28), so
# these compose into the short-tx PREPARE / persist steps of the orchestration. The
# SQL targets the migration-0054 tables verbatim.

def prepare_batches(
    conn, *, run_id: str, doc_id: str, corpus_id: str | None, map_contract: str,
    manifest: SkeletonManifest, plan: map_batches.BatchPlan,
) -> None:
    """Insert the batch manifests and the furniture exclusions. Idempotent: the
    batch_id IS the source-bound batch_hash, so re-preparing the same document is a
    no-op (ON CONFLICT DO NOTHING) and never resets a batch already in progress."""
    by_alias = {s.alias: s for s in manifest.skeletons}
    for batch in plan.batches:
        alias_manifest = {a: by_alias[a].parent_id for a in batch.aliases}
        input_hash = map_batches._sha256(
            "\x1f".join(f"{a}\x1e{by_alias[a].skeleton_hash}" for a in batch.aliases)
        )
        conn.execute(
            """INSERT INTO document_parent_map_batches
                 (batch_id, run_id, doc_id, corpus_id, map_contract, ordinal, is_combined,
                  status, expected_count, valid_count, alias_manifest, input_hash)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',%s,0,%s::jsonb,%s)
               ON CONFLICT (batch_id) DO NOTHING""",
            (batch.batch_hash, run_id, doc_id, corpus_id, map_contract, batch.ordinal,
             batch.is_combined, batch.parent_count, json.dumps(alias_manifest), input_hash),
        )
    for ex in manifest.excluded:
        conn.execute(
            """INSERT INTO document_parent_exclusions (doc_id, parent_id, map_contract, reason)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (doc_id, parent_id, map_contract) DO NOTHING""",
            (doc_id, ex.parent_id, map_contract, ex.reason),
        )


def claim_batch(conn, *, batch_id: str, owner: str, now, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
    """Lease a claimable batch (pending / partial / expired-lease). Returns True iff
    THIS caller now owns it. A `done`/`error` batch is never re-claimed; an expired
    lease is reclaimable (the dead-worker recovery path)."""
    row = conn.execute(
        """UPDATE document_parent_map_batches
              SET status='leased', lease_owner=%s,
                  lease_expires_at = %s + make_interval(secs => %s),
                  attempt_count = attempt_count + 1, updated_at = now()
            WHERE batch_id = %s
              AND status IN ('pending','partial','leased')
              AND (lease_expires_at IS NULL OR lease_expires_at < %s)
            RETURNING batch_id""",
        (owner, now, lease_seconds, batch_id, now),
    ).fetchone()
    return row is not None


def active_parent_ids(conn, *, doc_id: str, map_contract: str, parent_ids: Sequence[str]) -> set[str]:
    """Which of ``parent_ids`` already have an active map (the restart/repair skip
    set — §36.5 / §18.4)."""
    if not parent_ids:
        return set()
    rows = conn.execute(
        """SELECT parent_id FROM document_parent_maps
            WHERE doc_id=%s AND map_contract=%s AND active AND parent_id = ANY(%s)""",
        (doc_id, map_contract, list(parent_ids)),
    ).fetchall()
    return {r[0] for r in rows}


def persist_maps(
    conn, *, doc_id: str, corpus_id: str | None, map_contract: str, batch_id: str,
    maps: Sequence[map_compiler.CompiledMap], source_text_hash_by_alias: Mapping[str, str],
    provider: str | None = None, model: str | None = None,
) -> int:
    """Persist compiled maps as the active map per parent. Supersede-then-upsert so
    the partial unique index (one active per (doc_id, parent_id, map_contract)) is
    never violated, and re-persisting identical content (same map_hash) is a no-op
    that keeps the row active (idempotent restart)."""
    n = 0
    for m in maps:
        # 1) supersede any DIFFERENT active map for this parent (never delete).
        conn.execute(
            """UPDATE document_parent_maps SET active=false, updated_at=now()
                WHERE doc_id=%s AND parent_id=%s AND map_contract=%s AND active AND map_id<>%s""",
            (doc_id, m.parent_id, map_contract, m.map_hash),
        )
        # 2) upsert THIS map active. ON CONFLICT (map_id) reactivates identical content.
        conn.execute(
            """INSERT INTO document_parent_maps
                 (map_id, doc_id, parent_id, corpus_id, map_contract, alias, batch_id,
                  routing_signature, semantic_hooks, exact_identifiers, provider, model,
                  source_text_hash, map_hash, quality_flags, active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s::jsonb,true)
               ON CONFLICT (map_id) DO UPDATE
                 SET active=true, batch_id=EXCLUDED.batch_id, updated_at=now()""",
            (m.map_hash, doc_id, m.parent_id, corpus_id, map_contract, m.alias, batch_id,
             m.routing_signature, json.dumps(list(m.semantic_hooks)),
             json.dumps(list(m.exact_identifiers)), provider, model,
             source_text_hash_by_alias.get(m.alias), m.map_hash,
             json.dumps(list(m.quality_flags))),
        )
        n += 1
    return n


def record_batch_result(
    conn, *, batch_id: str, status: str, valid_count: int,
    raw_response_hash: str | None = None, last_error: str | None = None,
    provider: str | None = None, model: str | None = None,
) -> None:
    """Finalize a batch attempt and RELEASE its lease (lease_expires_at=NULL) so a
    partial batch is immediately re-claimable for repair."""
    conn.execute(
        """UPDATE document_parent_map_batches
              SET status=%s, valid_count=%s, raw_response_hash=COALESCE(%s, raw_response_hash),
                  last_error=%s, provider=COALESCE(%s, provider), model=COALESCE(%s, model),
                  lease_owner=NULL, lease_expires_at=NULL, updated_at=now()
            WHERE batch_id=%s""",
        (status, valid_count, raw_response_hash, last_error, provider, model, batch_id),
    )


# ------------------------------------------------------------------- orchestration

def run_document_mapping(
    tx, *, run_id: str, doc_id: str, corpus_id: str | None, parents: Sequence[Mapping[str, Any]],
    infer: Infer, map_contract: str = map_compiler.MAP_COMPILER_VERSION,
    density: map_batches.DensityModel = map_batches.DEFAULT_DENSITY,
    provider: str | None = None, model: str | None = None, lease_owner: str = MAP_WORKER_VERSION,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS, lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now_fn: Callable[[], Any] | None = None,
) -> MappingOutcome:
    """Map one document's parents durably. ``tx`` is a transaction context manager
    factory (``polymath_shared.db.tx`` in production); ``infer`` is the injected
    inference boundary. Never holds a tx across ``infer`` (§28)."""
    import datetime as _dt
    now_fn = now_fn or (lambda: _dt.datetime.now(_dt.timezone.utc))

    manifest = build_parent_skeletons(parents)
    plan = map_batches.plan_batches(manifest, density, contract=map_batches.BATCH_PLANNER_VERSION)
    by_alias = {s.alias: s for s in manifest.skeletons}
    text_hash_by_alias = {s.alias: s.text_hash for s in manifest.skeletons}

    # PREPARE — one short tx creates the manifests (§28).
    with tx() as conn:
        prepare_batches(conn, run_id=run_id, doc_id=doc_id, corpus_id=corpus_id,
                        map_contract=map_contract, manifest=manifest, plan=plan)

    outcome = MappingOutcome(
        doc_id=doc_id, map_contract=map_contract, eligible_parents=len(manifest.skeletons),
        excluded_parents=len(manifest.excluded), batches_total=len(plan.batches),
        batches_done=0, batches_partial=0, parents_mapped=0,
    )
    errors: list[str] = []
    attempts_used = 0

    for batch in plan.batches:
        batch_aliases = list(batch.aliases)
        for _attempt in range(max_attempts):
            now = now_fn()
            with tx() as conn:
                claimed = claim_batch(conn, batch_id=batch.batch_hash, owner=lease_owner,
                                      now=now, lease_seconds=lease_seconds)
            if not claimed:
                break  # done/error, or held by a live worker — leave it
            attempts_used += 1
            # Remaining = batch parents without an active map (restart/repair skip set).
            with tx() as conn:
                already = active_parent_ids(conn, doc_id=doc_id, map_contract=map_contract,
                                            parent_ids=[by_alias[a].parent_id for a in batch_aliases])
            remaining = [a for a in batch_aliases if by_alias[a].parent_id not in already]
            if not remaining:
                with tx() as conn:
                    record_batch_result(conn, batch_id=batch.batch_hash, status="done",
                                        valid_count=len(batch_aliases))
                break
            skels = [by_alias[a] for a in remaining]
            # INFERENCE — OUTSIDE any transaction (§28).
            try:
                raw = infer(skels, is_combined=batch.is_combined)  # type: ignore[call-arg]
            except TypeError:
                raw = infer(skels)  # a fake without the keyword
            except Exception as exc:  # provider/transport failure — durable, retryable
                errors.append(f"{batch.batch_hash[:12]}:{type(exc).__name__}")
                with tx() as conn:
                    record_batch_result(conn, batch_id=batch.batch_hash, status="partial",
                                        valid_count=0, last_error=str(exc)[:500],
                                        provider=provider, model=model)
                continue
            result = map_compiler.compile_maps(raw, manifest, contract=map_contract)
            valid_here = [m for m in result.maps if m.alias in remaining]
            with tx() as conn:
                persist_maps(conn, doc_id=doc_id, corpus_id=corpus_id, map_contract=map_contract,
                             batch_id=batch.batch_hash, maps=valid_here,
                             source_text_hash_by_alias=text_hash_by_alias,
                             provider=provider, model=model)
                still = active_parent_ids(conn, doc_id=doc_id, map_contract=map_contract,
                                          parent_ids=[by_alias[a].parent_id for a in batch_aliases])
                mapped_all = all(by_alias[a].parent_id in still for a in batch_aliases)
                record_batch_result(conn, batch_id=batch.batch_hash,
                                    status=("done" if mapped_all else "partial"),
                                    valid_count=len(still), raw_response_hash=result.raw_response_hash,
                                    provider=provider, model=model)
            if mapped_all:
                break
            batch_aliases = batch_aliases  # repair loop re-computes remaining from DB

    # Final tally from durable state.
    with tx() as conn:
        done = conn.execute(
            "SELECT status, COUNT(*) FROM document_parent_map_batches "
            "WHERE doc_id=%s AND map_contract=%s GROUP BY status",
            (doc_id, map_contract)).fetchall()
        status_counts = {s: n for s, n in done}
        all_eligible_parents = [s.parent_id for s in manifest.skeletons]
        mapped = active_parent_ids(conn, doc_id=doc_id, map_contract=map_contract,
                                   parent_ids=all_eligible_parents)
    unresolved = tuple(pid for pid in all_eligible_parents if pid not in mapped)
    outcome.batches_done = status_counts.get("done", 0)
    outcome.batches_partial = status_counts.get("partial", 0) + status_counts.get("leased", 0)
    outcome.parents_mapped = len(mapped)
    outcome.unresolved_parent_ids = unresolved
    outcome.attempts_used = attempts_used
    outcome.errors = tuple(errors)
    return outcome
