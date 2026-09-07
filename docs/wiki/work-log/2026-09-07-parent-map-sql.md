---
title: "WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S4: parent-map SQL durability"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S4
date: 2026-09-07
owner: store (Postgres workflow truth)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.135
package: stores/postgres/migrations/0054_document_parent_maps.sql (new), tests/determinism/test_document_parent_maps_store.py (new), scripts/scaffold_polymath_v4.py
architecture_impact: "Migration 0054 adds the parent-map persistence, Postgres as workflow truth (Qdrant stays a rebuildable projection). Three tables, keyed on the CORRECTED S2/S3 contracts (11.133): document_parent_map_batches (resumable substage ledger; batch_id IS the S3 source-bound batch_hash, so re-running the same document's mapping yields the same batch_id -> ON CONFLICT DO NOTHING means restart/retry never duplicates completed API work), document_parent_maps (final authoritative map; map_id IS the S2 map_hash, parent_id IS the parent chunk_id, and a PARTIAL unique index enforces exactly one ACTIVE map per (doc_id, parent_id, map_contract) — supersede flips active, never deletes), and document_parent_exclusions (furniture/noise parents accounted for, not mapped). No worker in this slice (S9). Idempotent (IF NOT EXISTS); additive; no existing table or stage touched."
---

# WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S4

## Contract

Slice S4 (plan §20, §36.4, §40). Persist the parent map durably so completeness
and identity are Postgres truth, inheriting the corrected S2/S3 contracts. Exit
(§40 S4): idempotent insert/update, partial batch state, one active map/parent/
contract. No worker.

Owner: `store` (schema). Public contract: three new tables + indexes. Inputs: the
S2 `CompiledMap` and S3 `MapBatch` values. Persistence effect: new tables; no
change to existing schema. Failure modes: a second active map for the same
(doc, parent, contract) is REJECTED by the partial unique index; a replayed batch
or map is a no-op (ON CONFLICT). Dependency edges: FK to `documents(doc_id)` (ON
DELETE CASCADE). Reverse dependents (future): S9 `doc_parent_map` worker (claims
batches, persists maps), S10 projection (reads active maps), S11 verifier (counts
active maps vs eligible parents). Verifier:
`tests/determinism/test_document_parent_maps_store.py`. Rollback: `DROP TABLE`
the three additive tables (nothing else references them yet).

## Changes

- **`stores/postgres/migrations/0054_document_parent_maps.sql`** (new, idempotent):
  - `document_parent_map_batches` — `batch_id` PK (= S3 source-bound `batch_hash`),
    `run_id`, `doc_id` (FK), `map_contract`, `ordinal`, `is_combined`, `status`
    CHECK(pending/leased/partial/done/error), `expected_count`, `valid_count`,
    `alias_manifest` JSONB, `input_hash`, `raw_response_hash`, provider/model,
    `attempt_count`, `lease_owner`, `lease_expires_at`, `last_error`, timestamps;
    a doc index and a claim index (status, lease_expires_at).
  - `document_parent_maps` — `map_id` PK (= S2 `map_hash`), `doc_id` (FK),
    `parent_id` (the parent chunk_id), `map_contract`, `alias`, `batch_id` (FK),
    `routing_signature`, `semantic_hooks`/`exact_identifiers`/`quality_flags`
    JSONB, provider/model, `source_text_hash`, `map_hash`, `active`, timestamps;
    a PARTIAL unique index `(doc_id, parent_id, map_contract) WHERE active` and a
    doc index.
  - `document_parent_exclusions` — PK `(doc_id, parent_id, map_contract)`, `reason`.
- **`tests/determinism/test_document_parent_maps_store.py`** (new): 5 pins against
  a real Postgres, skipped when none is reachable (`to_regclass` gate, matching
  `test_document_profile_stage.py`).
- **`scripts/scaffold_polymath_v4.py`**: declared the migration, test and work-log.

## Proof

Applied to the dev Postgres and re-applied (idempotent — every object
"already exists, skipping", no error). The partial unique index is present:
`document_parent_maps_active_idx UNIQUE (doc_id, parent_id, map_contract) WHERE active`.

```
# .env sourced (dev Postgres reachable):
.venv/bin/python -m pytest tests/determinism/test_document_parent_maps_store.py -q  -> 5 passed
# CI condition (no reachable Postgres): 5 skipped (to_regclass gate) — no error
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
```

Pins: a replayed batch insert (same source-bound `batch_id`) stays one row —
restart/retry does not duplicate completed API work; batch status transitions
pending → leased → partial (valid_count 2 of 3) persist; a second ACTIVE map for
the same (doc, parent, contract) raises `UniqueViolation`, and superseding
(deactivate v1, insert v2 active) leaves exactly one active map; a replayed map
insert stays one row; an exclusion is accounted for and idempotent.

## Rejected claims

- **Not** identity-by-position: `parent_id` is the chunk_id (Fix C, 11.133);
  `batch_id`/`map_id` are the source-bound/content hashes (Fix A/D). This is why
  the corrective checkpoint ran BEFORE this migration — the durable keys are correct.
- **Not** a worker: S4 is schema only; claiming/persisting/repair is S9.
- **Semantic artifacts persist independently of projection** (Part 4 gate,
  foundation): these rows are Postgres truth; the Qdrant projection (S10) is
  rebuildable from them and never the authority.
- CI does not exercise the DB (no Postgres service); the migration is guard-checked
  and applied at deploy, and the behaviour is proven on the dev Postgres here.

## Open contract gaps

- Next: **S5 — Profile vNext global compiler + fingerprint** (`document_profile/`
  context/prompt/compiler + the 500–2,000-token adaptive fingerprint + the
  research-index surfaces LATENT-PATTERN/ANCHOR/RECALLQ/TENSION/BRIDGE/INVERSION/
  BOUNDARY; canary 500/1000/1500/2000, pick the smallest quality plateau). Then
  S6 combined one-call canary (real API — provider spend), S7 wiring (the Groq
  router into pool.py + limiter.yaml), S8 `doc_profile` refactor, S9
  `doc_parent_map` worker.
- The migration must be applied on every environment (dev applied; a fresh clone
  runs all migrations in order; the deploy applies pending files) before the S9
  worker runs.
- The S9 worker's parent-load query must `SELECT chunk_id … WHERE tier='parent'`
  to populate `parent_id` (the current `doc_profile_worker` selects only
  `chunk_index`).
