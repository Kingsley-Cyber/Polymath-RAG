---
title: "WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 corrective checkpoint: S2/S3 durable-identity + guard fixes"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S2S3-CORRECTIONS
date: 2026-09-07
owner: shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.133
package: shared/polymath_shared/document_profile/parent_skeleton.py, shared/polymath_shared/document_profile/map_compiler.py, shared/polymath_shared/document_profile/map_batches.py, tests/determinism/test_parent_skeleton.py, tests/determinism/test_parent_map_compiler.py, tests/determinism/test_map_batches.py, scripts/scaffold_polymath_v4.py
architecture_impact: "A corrective checkpoint on the S1-S3 contracts BEFORE S4 persists them (nothing durable exists yet, so these identity/guard changes cost no migration or backfill). Five defects closed: (1) `MapBatch.batch_hash` / `BatchPlan.plan_hash` now bind SOURCE identity (planner contract + manifest_hash + per-alias skeleton_hash + combined flag) so two documents that both alias P0001..P0060 can never share durable batch identity; (2) `token_feasible_rpm` now actually drops the RPM ceiling to 3 above the 15k/request cap (the old TPM-only floor left 15,001-17,500-token requests silently at 4); (3) durable parent identity is the parent chunk's `chunk_id` (content-derived Postgres PK) — `chunk_index` (positional, unstable across re-ingest) is rejected loudly, never used as a map key; (4) `completeness_hash` renamed/strengthened to `map_completeness_hash`, binding manifest + expected + valid + missing so a 73/90 partial, a different 73/90 partial, and a complete 90/90 of the same document all differ (§33); (5) a guarded regression pins the owner's REAL 40-parent Compound-Mini output the moment it is supplied, synthetic fixtures remaining supplemental. No new runtime path; no persistence/schema change."
---

# WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 corrective checkpoint (S2/S3)

## Contract

The owner's corrective goal identified five contract weaknesses in the S1-S3
deterministic core that must be fixed BEFORE S4 makes them durable (there is no
migration or backfill cost now — nothing is persisted). Fix each with a pin.

Owner: `shared` (deterministic policy). Public-contract change: `MapCompileResult`
field `completeness_hash` -> `map_completeness_hash`; `_identity` now raises on a
row lacking a durable chunk id. Rollback: `git revert` — the changes are edits to
un-persisted, un-wired library code. Verifier: the three determinism suites.

## Changes

- **Fix A — `batch_hash` source identity** (`map_batches.py`): `_batch` now hashes
  `contract + manifest_hash + is_combined + [alias⋯skeleton_hash]`; `plan_hash`
  also folds in `contract + manifest_hash` (so even an empty, noise-only document
  cannot collide). Different documents with identical alias strings now have
  distinct durable batch identity. Pin: `test_batch_hash_binds_source_identity_no_cross_document_collision`.
- **Fix B — `token_feasible_rpm` cap** (`map_batches.py`): the per-request cap now
  lowers the RPM ceiling to `target - 1` BEFORE the TPM bound applies, so
  15,001-17,500-token requests drop from 4 to 3 (previously `tpm_ceiling // total`
  still floored to 4 across that window). Pins:
  `test_token_feasible_rpm_boundary_at_15k` (15000→4, 15001→3, 17500→3, 17501→3).
- **Fix C — durable parent identity** (`parent_skeleton.py`): `_identity` reads
  `chunk_id` (the chunks table PK, `chunk_<sha256(doc_id|idx|text)>`) then a
  `parent_id` alias, and RAISES `ValueError` if only `chunk_index`/none is present.
  `chunk_index` is `UNIQUE(doc_id, chunk_index)` — positional and unstable across
  re-ingest, never a durable key. The S9 worker's parent-load query must therefore
  select `chunk_id` (the existing profile worker selects only `chunk_index`, which
  is fine for the fingerprint but NOT for map identity). Pin:
  `test_durable_identity_requires_chunk_id_not_chunk_index`.
- **Fix D — `map_completeness_hash`** (`map_compiler.py`): renamed from
  `completeness_hash` and strengthened to hash `manifest_hash + expected aliases +
  valid (alias, map_hash) + missing aliases` (§33 parent-map completeness hash).
  Pin: `test_map_completeness_hash_binds_manifest_and_missing_identity`.
- **Fix E — real fixture hook** (`test_parent_map_compiler.py`): a guarded
  `test_real_40_parent_mini_output_when_pinned` skips until
  `tests/determinism/fixtures/parent_map_mini_40.txt` exists, then asserts the
  REAL Compound-Mini output compiles 40/40. Synthetic fixtures remain the shape
  coverage.
- Test fixtures across the three suites now use `chunk_id` (the real column).
- `scripts/scaffold_polymath_v4.py`: declared this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_parent_skeleton.py tests/determinism/test_parent_map_compiler.py tests/determinism/test_map_batches.py -q  -> 44 passed, 1 skipped
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
```

The 1 skip is Fix E's guarded real-fixture pin (activates when the owner supplies
the raw output). New/updated pins prove each fix; the pre-existing pins still hold
under the strengthened contracts.

## Rejected claims

- No persistence existed to migrate: S4 (SQL) had not run, so changing these
  hashes and the identity field is free — this is exactly why the checkpoint runs
  before S4, not after.
- The fixes do NOT change the deterministic-core behaviour that was correct: alias
  assignment, DSL tolerance, partial recovery, packing capacities and the density
  model are unchanged; only identity/guard binding is corrected.
- No runtime path claimed working (AGENTS.md §9).

## Open contract gaps

- **S4 (SQL durability) now inherits the corrected contracts**: the
  `document_parent_maps` row keys on the parent `chunk_id`; the batch ledger keys
  on the source-bound `batch_hash`; the completeness receipt stores
  `map_completeness_hash`.
- **S9 worker obligation**: the parent-load query MUST `SELECT chunk_id … WHERE
  tier='parent'` (the current `doc_profile_worker._load_inputs` selects only
  `chunk_index`) so skeletons carry durable identity.
- Owner's real 40-parent Compound-Mini raw output still pending (Fix E hook ready).
