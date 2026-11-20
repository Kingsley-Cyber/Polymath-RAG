---
change_id: TRUE-CORPUS-DELETE-V1
owner: orchestrator
date: 2026-11-20
status: in_progress
status_note: "Owner 2026-11-20: 'I SHOULD BE ABLE TO TRULY DELETE A CORPUS AND IT DOES WHAT ITS SUPPOSE TO DO ON MY MACHINE AND GIVES ME STORAGE.' Building on branch fix/true-corpus-delete. No live library is deleted by this change."
architecture_impact: "orchestrator/api/ui.py corpus delete (every library-linked table, projection_attempts by entity id, shared Qdrant collections by corpus filter, disk reclaim), a delete CLI, contract tests."
last_reviewed: 2026-11-20
---

# TRUE-CORPUS-DELETE-V1: deleting a library removes all of it and returns the disk space

## Contract
- Owner (2026-11-20): a deleted library is gone from every store on this machine, and the disk space comes back.
- Owner (2026-11-20): "POLYMATH RN SHOULDNT REALLY HAVE ANY CORPUS EXCEPT 1 'CINEMA' EVERYTHING ELSE IS A NO GO." Deleting the
  six other libraries is a separate, irreversible step that waits for the owner's explicit yes.

## Measured (live, read-only, 2026-11-20)
- `DELETE /corpora/{id}` (`orchestrator/orchestrator/api/ui.py:1134`) exists. It names 29 (table, column) pairs; one is broken:
  `projection_attempts` has no `run_id` column, so that step always fails and `optional=True` hides it.
- The evidence-receipt purge read evidence ids with a sub-select that ran after `DELETE FROM evidence` in the same
  transaction, so it purged nothing.
- Tables the delete never touched: the seeded-delete test on 14e8deb8 left rows in 19 tables (among them
  entity_admission_decisions 285 MB live, parent_enrichments, stall_traces, extraction_call_receipts, corpus_runtime_state,
  concept_vocabulary, llm_provider_attempts). A first count of 31 was wrong: it missed one list in the code and counted the
  `adapter_*` tables, whose run_id is a research run.
- Postgres is 20 GB on disk; `projection_attempts` alone is 12 GB (51,135,799 rows, 2026-08-14..2026-10-04: an append-only
  history, ~94 Neo4j attempts per entity). A DELETE never shrinks the files: no step runs VACUUM FULL.
- The delete sweeps Qdrant collections by the corpus-hash prefix; the shared collections (`polymath_document_parent_maps_*`,
  `polymath_document_profiles_*`, `polymath_document_profile_atoms_*`, `polymath_gnn_parent_*`) hold every library's points and
  are never filtered.

## Changes
- `orchestrator/orchestrator/api/ui.py`: `delete_corpus(..., reclaim=False)`; evidence ids read first; `projection_attempts`
  deleted by projected id (chunk, document, evidence, summary/object/canonical, orphan fact ids); `_sweep_library_tables` empties
  every table `library_linked_tables` lists (text columns corpus_id, doc_id, chunk_id, run_id, parent_id; kept: `query_receipts`,
  the owner's query log, and `adapter_*`); a table still pointed at retries on a later pass, and leftovers are reported as
  `tables_not_deleted`; `_delete_shared_collection_points` deletes the library's points from the parent-map, profile, profile-atom
  and GNN collections by payload corpus_id.
- `shared/polymath_shared/storage_reclaim.py`: compacts the tables a delete emptied (largest first), each only when the free disk
  holds its estimated copy x1.25 plus a 2 GB reserve.
- `scripts/delete_corpus.py`: the owner's command; prints rows removed, skipped compactions, and the store folders and free disk
  before and after.

## Proof
- `tests/contracts/test_true_corpus_delete.py`, sealed harness (throwaway Postgres, all migrations; fake Qdrant/Neo4j):
  4 passed on this branch. On 14e8deb8 the seeded-delete test fails with rows left in 19 tables (the other three fail on the
  missing functions).

## Contract impact (`scripts/contract_impact.py --staged`)
- EVIDENCE_BOUNDARY_API, PROFILE_SCOUT_WIRING (changed: `ui.py` maps to both): TESTED_UNCHANGED — only the corpus delete
  endpoint changed; no evidence, retrieval or profile path is touched. The transitive consumers (ACCEPTANCE, ADAPTER_RUNTIME,
  CANDIDATE_ENGINE, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE, RETRIEVAL_RECEIPT,
  SUBQUERY_PROVENANCE): TESTED_UNCHANGED by the full sealed run (tests/contracts + tests/determinism), compared with the
  2b894afa failure list.

## Rejected claims
- "Only cinema should stay, so delete the other six now": not done. Deleting is irreversible; it waits for the owner's yes.

## Open contract gaps
- Neo4j files keep their size (Neo4j reuses the space); entity nodes are shared and never deleted (unchanged rule).
- `projection_attempts` history of libraries that stay is untouched (51M rows, 12 GB; its design says "never deleted").

## Checkpoint (2026-11-20, for a fresh session)
- Done: Qdrant now on a host folder (production 14e8deb8, container re-created 00:5xZ). Cinema rebuild started: its 77
  `verify_projections` tickets re-opened (owner's "fix the repo"; cinema only); verify marks runs degraded, the scheduler then
  re-opens one `project_qdrant` ticket per corpus. Not rebuilt yet: parent maps, profiles, profile atoms (their own writers).
- In progress: this delete fix (worktree `../pmv4-corpus-delete`).
- Next: search latency (owner: "embedding and reranking should take ms to 3 secs"); baseline from receipts: cinema chat
  `phase_ms.retrieve` p50 4,321 ms, max 44,235 ms (53 receipts, 30 days); per-step timing inside retrieve is not recorded.
- Search latency measured 2026-11-20 (live sidecars, while the cinema projection also used the embedder): query embedding
  254-282 ms (one 4,185 ms spike under the projection's batches); Qwen3-Reranker-0.6B on the M1 Max (MPS, fp16, max length
  384) 2.8-7.3 s for 24 passages and 3.6-3.9 s for 32; Qdrant HNSW search 3-14 ms for 120 hits. The reranker is the cost;
  vector search is not. The Mac: 32 GB RAM, swap 18.4 of 19.5 GB used, disk 98% full (9.3 GB free of 460 GB).
- Cinema projection rate: 426 points/min (~3 h for 84,585 chunks).
- Test hygiene (found 2026-11-20): `tests/determinism/test_incremental_census.py:31` (also `test_summary_job_idempotency.py:18`,
  `test_stall_tracer.py:20`) hardcodes the live DSN. Two of this session's sealed runs wrote to the live database: 01:34Z
  (the full suite) and 01:58Z (a zsh slip passed the 48-file skip list as ONE argument, so nothing was skipped). Both hung and
  were killed; the probe rows were purged with the module's own `_purge_probe_rows` plus 47 `stall_traces` rows and 1
  `corpus_runtime_state` row (0 left). The live probes also wrote 10 query receipts (kept: query history). 48 test files name
  a live address; the owner started the follow-up task.
- Open for the owner: delete the six non-cinema libraries (irreversible); a retention rule for `projection_attempts` (its
  design says "never deleted"); how to make reranking fast (GPU box, smaller model, or shorter input).
