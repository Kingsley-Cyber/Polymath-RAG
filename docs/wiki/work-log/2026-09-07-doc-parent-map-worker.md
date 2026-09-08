---
title: "WORK LOG — durable doc_parent_map worker (slice S9 / migration §S5)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S9-MAP-WORKER
date: 2026-09-07
owner: worker (durable stage logic — not yet fleet-registered)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.142
package: workers/workers/doc_parent_map_worker.py, tests/determinism/test_doc_parent_map_worker.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds the DURABLE ORCHESTRATION of parent mapping over the migration-0054 tables: build_parent_skeletons (S1) -> plan_batches (S3) -> [injected inference] -> compile_maps (S2) -> persist active maps + exclusions (S4). The inference boundary is INJECTED (no provider call, no spend); the module holds NO fleet wiring and is NOT registered in STAGE_DAG/the supervisor, so it changes no live ingestion — the same 'build the durable core, wire the live call later' sequencing S1-S4 used ('no worker consumes it yet'). Enforces the §28 short-tx-around-inference pattern, §18.4 partial-persist-and-repair-only-missing, and §36.5 restart idempotency. Touching workers/ trips the ~2-min HASH-FENCE auto-heal; the added module is not imported by any running slot, so the heal is clean."
---

# WORK LOG — durable doc_parent_map worker (S9)

## Contract

Plan of record §20/§36.5; migration authority `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md`
§S5 (durable map worker/manifests), §28 (inference transaction pattern), §10
(long-document fairness). The next dependency in the /goal chain after the map SQL
substrate (S4): the durable worker that fills it. Build the durable orchestration +
store operations so that the map worker, once its live Groq `infer` closure and stage
registration are wired (owner-gated: spend + live-ingestion change), is crash-safe,
partial-safe, and idempotent by construction.

Owner: `worker` (durable stage logic). Public contract: `run_document_mapping(tx, *,
run_id, doc_id, corpus_id, parents, infer, ...) -> MappingOutcome`, plus the store
ops `prepare_batches` / `claim_batch` / `persist_maps` / `record_batch_result` /
`active_parent_ids`. Rollback: delete the module + test (nothing imports/dispatches
it). Verifier: `tests/determinism/test_doc_parent_map_worker.py`.

Explicitly OUT of scope (owner-gated): the live Groq-backed `infer` closure (builds
the map prompt + calls the provider — spend), the S7 shared-budget routing that
governs that call, registering the stage in `STAGE_DAG`/the supervisor (changes live
ingestion), and the Qdrant projection of maps (S10). No chunker change.

## Changes

- **`workers/workers/doc_parent_map_worker.py`** (new): the durable orchestration and
  its store ops over the 0054 tables.
  - `run_document_mapping(tx, ..., infer)`: PREPARE (one short tx inserts batch
    manifests + exclusions) → per batch: claim (lease, short tx) → compute the
    remaining unmapped parents from durable state → `infer` OUTSIDE any tx → `compile_maps`
    → persist valid + record status (short tx) → repair loop re-infers ONLY the still-
    missing aliases, capped at `max_attempts`. Never holds a tx across `infer` (§28).
  - `prepare_batches`: `batch_id = batch_hash` (source-bound) → `ON CONFLICT DO
    NOTHING` = idempotent re-prepare; exclusions inserted for furniture parents.
  - `persist_maps`: supersede-then-upsert (`map_id = map_hash`) so the partial unique
    index (one active per (doc_id, parent_id, map_contract)) is never violated and
    re-persisting identical content is a no-op that keeps the row active.
  - `claim_batch`: leases pending/partial/expired-lease batches; a `done` batch is
    never re-claimed; an expired lease is reclaimable (dead-worker recovery).
  - `active_parent_ids`: the restart/repair skip set.
  - Reuses S1/S2/S3 verbatim; `infer` is injected (`Infer` type); no provider import.
- **test + scaffold**: 5 durability pins; two TREE lines; this work-log.

## Proof

```
set -a; . ./.env; set +a
.venv/bin/python -m pytest tests/determinism/test_doc_parent_map_worker.py -q   -> 5 passed (live dev PG)
# without a PG server (CI): the fixture skips cleanly (as the S4 store test does)
.venv/bin/python scripts/repo_guard.py       -> repo guard: ok   (forbidden-import check: worker imports only polymath_shared.*)
.venv/bin/python scripts/agent_preflight.py  -> preflight: ok
```

Pins (real Postgres, fake `infer`, no spend): full mapping (6 parents mapped, 1
furniture excluded, batch `done`); **partial-then-repair** — a response missing one
alias persists the rest and re-infers ONLY the missing one (`infer.calls == 2`),
ending complete (§18.4); **restart idempotency** — a second `run_document_mapping`
re-infers NOTHING (`counting.seen == []`) and the active map set is unchanged (§36.5);
supersede — persisting a different map for a parent flips the old one inactive
(exactly one active, the superseded row retained, not deleted); lease recovery —
an unexpired lease blocks a second claimer, an expired lease is reclaimed.

## Rejected claims

- **Not** live: no provider call happens; `infer` is injected and the tests use a
  deterministic fake. The Groq-backed closure + shared-budget routing (S7) + the
  500/1000/1500/2000 map canary are owner-gated (spend).
- **Not** fleet-wired: the module is not in `STAGE_DAG` or the supervisor, so no live
  ingestion changes and no `doc_parent_map` ticket is minted (that is the gated
  wiring). Dormant like S1-S4 were before their consumers existed.
- **Not** a projection: maps live in Postgres only; the Qdrant parent-map collection
  + receipts + purge coverage is S10.

## Open contract gaps

- Live wiring (S7 routing + the Groq `infer` closure that builds the map prompt and
  respects the shared account budget + the stage registration) is the next
  owner-gated step; running it spends provider quota and changes live ingestion.
- A committed deterministic map-prompt builder (the 11.136 canary used a scratchpad
  prompt) is still owed for that closure; kept out of this slice so no unqualified
  prompt ships as production-ready.
- The Qdrant projector (S10) and its verifier/purge coverage remain unbuilt.
