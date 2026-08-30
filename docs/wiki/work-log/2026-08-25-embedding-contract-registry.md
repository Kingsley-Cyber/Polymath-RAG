---
change_id: EMBEDDING-CONTRACT-REGISTRY-V1
owner: governance
date: 2026-08-25
status: implemented
architecture_impact: embedding contract authority moves from application setting to per-corpus state in Postgres; production default flips to neural
last_reviewed: 2026-08-29
---

# EMBEDDING-CONTRACT-REGISTRY-V1 (G1 cutover, 2026-08-25)

## Contract

The embedding contract is CORPUS STATE (`corpora.embedding_contract_id`,
NOT NULL). A projection or query must never touch vectors under a
different contract than produced them. Production default for NEW
corpora: `neural-embed-v1` (Qwen/Qwen3-Embedding-0.6B @ pinned revision,
1024d cosine/l2, instruct query prefix) — frozen fields, unchanged from
the contract that passed the three-mode benchmark. hash-embed-v1 remains
registered as deterministic test/fallback provider, never the default.
Existing collections are NOT reinterpreted in place.

## Changes

1. Migration 0034: corpora.embedding_contract_id NOT NULL DEFAULT
   'neural-embed-v1' (+ index).
2. Measured backfill decision: live audit found 71 dual-projected,
   4 neural-only, **0 hash-only**, 9 empty corpora — every corpus with
   vectors already has its NEURAL collection, so the default is correct
   for all 84 rows with no data mutation.
3. project_qdrant_worker resolves `_corpus_contract(conn, corpus_id)`
   (pin first, settings fallback); unknown pin raises loudly.
4. intake pins the setting default at corpora creation for new corpora.
5. settings default flips hash→neural (description records the owner
   decision).
6. Tests: registry regressions (default-is-neural pin, hash survives as
   test provider, frozen-field pin incl. model_revision/dimension/
   prefix, worker resolves pin-over-default, unknown-pin fails closed).

## Proof

G1 qualification (eval/v5/retrieval/G1-HASH-VS-NEURAL.md, artifacts +
json committed): same 10 queries, same k=10, release-books-v1 dual
collections:

| provider | semantic | identifier/exact |
|---|---|---|
| hash-embed-v1 | 0/4 | 0/5 |
| neural-embed-v1 | **2/4** | **4/5** |

Hash retrieved ZERO of nine weak-labeled targets (char-3gram hashing
has no semantics); neural never lost an identifier/exact class.
Rule satisfied: neural materially beats hash on semantic classes while
never losing exact classes → **NEURAL CUTOVER QUALIFIED**.

pytest registry 4/4; focused core re-run green post-change.

## Rejected claims

- NOT changing model/dimension/serializer/instructions/ranking as part
  of G1 (one variable at a time, per owner directive).
- NOT migrating to Qdrant named-vectors; collection-per-contract
  topology already provides blue-green properties (old collection kept;
  alias work deferred until a measured need).
- NOT claiming sentence-level accuracy — weak source-level labels only.

## Open contract gaps

- /ask dense lane does not exist yet; when built it MUST resolve the
  per-corpus pin via the same helper (query-side half of the invariant).
- q01/q03 semantic misses recorded honestly; candidate cause is
  summary-text granularity of routing_document_summary, to be examined
  during Stage K — NOT patched in this slice.
