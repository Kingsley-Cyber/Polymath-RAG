---
change_id: bulk-acceptance-verify-fix
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (verify reconciliation scope fix)
---

# Bulk-acceptance fix: verify must not delete other corpora's chunks

## Contract

The 4-document mini bulk-ingestion acceptance run (temporary corpus,
real pipeline) discovered that `reconcile_neo4j` compared the SHARED
Neo4j chunk store against CORPUS-SCOPED receipts: one corpus's verify
deleted legitimately-receipted chunk nodes of every other corpus
(observed: gate7 test-corpus chunks removed; the bulk corpus's own
chunks removed by later verifies). Fix the orphan criterion to
GLOBAL receipts (a chunk is an orphan only with no active receipt
anywhere), and make the report value match the actual deletion set.
No extraction logic was touched.

## Changes

- `workers/workers/verify_worker.py` `reconcile_neo4j`: orphan
  deletion set = `store_ids - global_receipts`; the returned
  `orphans_in_store` now reports that same set (was the corpus-scoped
  difference, which misreported and mis-degraded runs).
- Regression test in
  `tests/integration/test_canonical_projection_e2e.py`:
  `test_verify_does_not_delete_other_corpora_chunks` — a foreign
  receipted chunk survives this corpus's verify.
- Recovery applied to the live stores: bulk corpus's Neo4j projection
  rebuilt via project_neo4j/project_canonical re-drive; all 4 runs
  verified to `query_ready`.

## Proof

- Bulk acceptance corpus: 4/4 documents, 0 failed attempts, 0
  degraded runs, 0 facts without evidence/provenance, canonicalization
  converged, lineage resolves.
- 152 unit (23 skipped) + 20 integration (2 skipped) tests green;
  three guards green.

## Rejected claims

- No extraction change (compiler/rules/ontology/GLiNER/thresholds
  untouched). No Q1-corpus or other frozen artifact modified.

## Open contract gaps

- The entity-proposal recall gap observed in the smoke run
  (docs 01/03/04 extracted zero entities) is classified in the
  acceptance report; it is a coverage gap of the GLiNER label layer,
  not a compiler defect, and is not addressed by this fix.
