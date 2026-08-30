---
change_id: STORAGE-PROJECTIONS-S11-V1
owner: control
date: 2026-08-30
status: complete
architecture_impact: one authority, three projections — generation stamping (migration 0042), routing_entity cards, sparse BM25 lane (projection side), compile_objects stage; §11 recorded with the contract audit
last_reviewed: 2026-08-30
---

# WORK LOG — STORAGE-PROJECTIONS-S11-V1 (2026-08-30, session 4)

Owner directive: "RECORD §11 AND START THE BUILD ORDER … confirm this is
contracted and embedded in the control plane." Build order executed as
given: stamping → entity cards → BM25 sparse → compile_objects.

## Contract

1. The governing principle — the model proposes, deterministic Python
   owns truth — must be verifiable claim by claim against code, and the
   audit recorded in the register (§11.0), not asserted from memory.
2. Every extraction row must carry its generation, indexable
   (`extractor_version`), and the open type vocabulary must survive
   storage (entities.raw_types, deterministic set union).
3. Graph extractions must be first-class FAST citizens: one bounded,
   content-addressed routing card per (entity, corpus), reconciled by the
   verifier exactly like every other routing lane, with ONE shared id
   derivation.
4. Exact-name lexical recall: a named `bm25` sparse vector on the routing
   collection whose tokenizer is a single shared function — index side
   and query side must import the same code or recall silently zeroes.
5. The concept/procedure compilers run as their own provider-agnostic
   stage with contract hash, attempts, receipts, artifact, and
   opportunity accounting — never as a bolt-on inside a provider branch.

## Changes

- `stores/postgres/migrations/0042_generation_stamping.sql` (applied
  live): `entities.extractor_version/generated_by_bundle_hash/raw_types`,
  `facts.extractor_version`, both indexed.
- `workers/workers/llm_direct.py` — GENERATION-STAMPING-V1: entities
  upsert with containment-guarded jsonb set-union for raw_types (replay
  stays rowcount 0 — idempotency observable in `written`); facts insert
  carries `llm-direct-v1`.
- `shared/polymath_shared/projection_contracts.py` — `entity_card_id`
  (SHARED derivation: projector writes it, verifier reconciles it).
- `workers/workers/project_qdrant_worker.py` — ROUTING-ENTITY-CARDS-V1
  (`routing_entity` kind, batched corpus-scoped alias + predicate-capsule
  queries, bounded 600-char card, payload {entity_id, doc_ids}) and
  SPARSE-BM25-V1 writes ({"": dense, "bm25": SparseVector}), legacy
  collections detected per process and skipped LOUDLY
  (`SPARSE_LANE_SKIPPED_LEGACY_COLLECTION`); ROUTING_CONTRACT_VERSION
  1.0.0 → 1.1.0 (receipt hashes move → one-time full routing
  re-projection per corpus, by design).
- `shared/polymath_shared/sparse_bm25.py` — the tokenizer contract
  (lowercase, [a-z0-9]+, ≥2 chars, blake2b-64 mod 2^31), Modifier.IDF
  server-side.
- `scripts/migrate_routing_sparse.py` — legacy-collection migration
  (copy-out → recreate sparse-native → copy-back, dense preserved, no
  re-embedding; owner-gated `--apply`).
- `workers/workers/verify_worker.py` — `routing_entity` joined to
  ROUTING_KINDS, desired ids from mentions via `entity_card_id`,
  receipts scoped by the desired id set.
- `control/control/tickets.py` — STAGE_DAG + NON_BLOCKING_STAGES:
  `compile_objects` / `compile_objects.v1` between verify and
  parent_summary.
- `workers/workers/compile_objects_worker.py` — the stage (documents via
  `document_processing_runs`, source-name fallback; admitted mention
  surfaces + child-chunk text → `_persist_knowledge_artifacts`).
- `control/control/process_supervisor.py` + `config/runtime_budget.yaml`
  — `compile_objects` slot; pipeline/converge profiles.
- `workers/workers/extract_worker.py` — the llm_live KNOWLEDGE-ARTIFACT
  bolt-on removed (superseded by the stage); the legacy GLiNER inline
  call stays frozen behind the seam for rollback.
- Register §11: governing principle + §11.0 contract audit (claim →
  enforcement point → verdict) + rows 11.1–11.6.

## Proof

- Contract audit performed against code, not memory; the two design
  claims that FAILED verification are recorded as measured:
  (a) qdrant 1.13.4 refuses sparse-config addition to an existing
  collection (400 "Not existing vector name") — hence sparse-native
  creation + the migration script; (b) the cloud AIMD ceiling had
  saturated at 16 with zero 429s (fixed earlier this session, 16→32).
- Tests (all green): `test_sparse_bm25` (tokenizer contract pinned,
  query-side == index-side), `test_llm_direct_facts` extended
  (facts.extractor_version == 'llm-direct-v1', entities.raw_types
  carries the open type), `test_compile_objects_stage` (stage attempt ok
  + receipt committed + artifact with opportunity accounting + concept
  rows == artifact count), plus the session's census/term-gate suites
  unchanged.
- Live e2e receipt (fresh corpus through the restarted fleet): recorded
  in the session log / S4 packet addendum — compile_objects ticket done,
  concepts/procedures written BY THE STAGE, `routing_entity` points +
  sparse vectors present in the (sparse-native) collection, stamped rows
  queryable by `extractor_version='llm-direct-v1'`.

## Rejected claims

- "Facts were indistinguishable by generation" — PARTIALLY REJECTED by
  audit: `facts.provenance->>'contract'` already distinguished them; what
  was missing was an INDEXABLE column and any stamping at all on
  entities. 11.1 closes both.
- "predicate_raw/raw types live only in artifacts" — REJECTED for
  mentions/evidence (both already persisted per row: mentions.raw_label,
  evidence span_offsets.predicate_raw/predicate_method); TRUE for
  entities (fixed).
- "Add sparse to the live collection in place" — REJECTED, measured 400;
  recreation is the only path on 1.13.
- "compile_objects should block query_ready" — REJECTED: knowledge
  objects are enrichment; NON_BLOCKING like the summary layer
  (deterministic-floor law: enrichment never blocks retrieval).

## Open contract gaps

1. 11.6 query-side: FAST does not yet read `routing_entity` cards;
   HYBRID does not yet fuse the `bm25` lane (§4.5 work, next session —
   the tokenizer import contract is the one hard rule).
2. Legacy corpus collections stay dense-only until the owner runs
   `scripts/migrate_routing_sparse.py <corpus> --apply`.
3. Legacy-era GLiNER inline compile call still lives in the extract
   legacy branch (frozen seam; retire with §6 GLiNER retirement).
4. compile_objects for already-query_ready runs: minted pending by
   `ensure_run_tickets` on the next ensure pass and completed by the
   DAG — verify the backfill behaves on cysa-study-v1 (expected: cards
   and objects appear without re-extraction).
