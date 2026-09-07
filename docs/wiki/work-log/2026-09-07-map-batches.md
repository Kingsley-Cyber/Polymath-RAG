---
title: "WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S3: token packer / capacity model"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S3
date: 2026-09-07
owner: shared (deterministic policy)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.132
package: shared/polymath_shared/document_profile/map_batches.py (new), tests/determinism/test_map_batches.py (new), scripts/scaffold_polymath_v4.py
architecture_impact: "New deterministic-policy capacity model + packer. A `DensityModel` (per-parent input / billed / visible token density) seeded from the measured 40-parent Compound-Mini stress test (135.7 / 87 / 29) and refined by an EMA `update` from real receipts — never a permanent constant. `mapping_only_capacity` returns the parents-per-request (the smaller of the ~60 production target and what the 6.5k billed-completion envelope supports; 40 proven; the ~74 theoretical edge is never packed to). `combined_capacity` sizes the one-call global-profile + MAP fast path from the global profile's MEASURED billed output. `token_feasible_rpm` is the §14.4 guard (4 RPM is a ceiling, only under the 15k-token/request cap; above it, drop to what 70k TPM allows). `plan_batches(manifest, density)` cuts a document's eligible parents into deterministic `MapBatch` manifests (optional combined first batch + mapping-only overflow), each with input/billed/total token estimates and a batch hash, and a plan hash over them. Additive: no worker, no API, no persistence, no schema change; the S9 worker will mint tickets from these manifests, S7 will meter requests against the RPM/TPM guard."
---

# WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S3

## Contract

Slice S3 (plan §12-§14, §21-§22, §36.3, §40). A deterministic capacity model and
packer so the pipeline extracts everything under ONE call whenever it physically
fits and batches only the overflow, never re-running a mapped parent. Exit (§40
S3): "40 proven, 60 target pack, combined capacity formula tested." No API.

Owner: `shared` (deterministic policy). Public contract: `DensityModel`
(+`update`), `mapping_only_capacity`, `combined_capacity`, `request_total_tokens`,
`token_feasible_rpm`, `skeleton_prompt_tokens` / `estimate_input_tokens`,
`plan_batches(manifest, density) -> BatchPlan` with frozen `MapBatch` / `BatchPlan`.
Inputs: the S1 skeleton manifest + a density model. Outputs: an in-memory plan (no
persistence this slice). Failure modes: none external — pure arithmetic with a
minimum-1 floor everywhere a divisor or count could be zero. Dependency edge:
imports the S1 `parent_skeleton` types (intra-shared, allowed). Reverse dependents
(future): S7 shared budget (meters against the RPM/TPM guard), S9 worker (mints a
batch ticket per `MapBatch`), S6 combined canary (uses `combined_capacity`).
Verifier: `tests/determinism/test_map_batches.py`. Rollback: additive module +
test, deletable.

## Changes

- **`shared/polymath_shared/document_profile/map_batches.py`** (new):
  - `DensityModel` — seeded 135.7 / 87 / 29 tokens/parent (§12.2); `update` is a
    per-parent EMA (alpha 0.3) from one request's totals. `DEFAULT_DENSITY` is the
    seed. §43.2: capacity uses BILLED density (87), never the visible ~29.
  - `mapping_only_capacity` = `min(target 60, floor((envelope 6500 - safety 512) /
    billed_per_parent))`; 40 is proven, ~74 (the theoretical edge) is never reached.
  - `combined_capacity(density, global_profile_billed_tokens)` = §13.2 formula —
    parents that fit alongside the global profile's measured billed output; 0 when
    it does not fit.
  - `request_total_tokens` = parents × (input + billed) + global; at the baseline,
    40 parents => 8908 and 60 => 13362, matching §14.5.
  - `token_feasible_rpm` = the §14.4 guard.
  - `plan_batches` — optional combined first batch (sized by `combined_capacity`)
    then mapping-only batches of `mapping_only_capacity`; deterministic boundaries;
    `MapBatch` carries est input/billed/total tokens + a batch hash; `BatchPlan`
    carries the capacities + a plan hash. `BATCH_PLANNER_VERSION = map-batches-v1`.
  - `skeleton_prompt_tokens` — deterministic per-skeleton prompt-token estimate
    (alias + heading + excerpt + terms + identifiers, ~4 chars/token, matching
    `context.est_tokens`).
- **`tests/determinism/test_map_batches.py`** (new): 12 pure pins.
- **`scripts/scaffold_polymath_v4.py`**: declared module, test and this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_map_batches.py -q  -> 12 passed
.venv/bin/python -m pytest tests/determinism/test_parent_skeleton.py tests/determinism/test_parent_map_compiler.py -q -> 28 passed (S1/S2 seam)
.venv/bin/python scripts/repo_guard.py       -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py  -> preflight: ok
```

Pins the §36.3 shape against REAL S1 manifests: `mapping_only_capacity` == 60 at
the baseline with 40 ≤ 60 (proven); a 40-parent manifest is one request
(`request_total_tokens` == 8908, billed 3480 ≤ 6500 envelope, RPM 4); a 60-parent
manifest is one request (13362 tokens, RPM 4) respecting the target; a 150-parent
document splits deterministically into [60, 60, 30] with every batch under the
envelope and the aliases partitioning exactly once; the packer never exceeds the
completion envelope across 1/5/40/61/120/181 parents; the RPM guard drops below 4
above the 15k cap (20000 -> 3, 60000 -> 1) and holds 4 under it; `combined_capacity`
leaves room for the global profile (1200 billed -> 55, 7000 -> 0) and the combined
first batch is followed by mapping-only overflow; the EMA moves toward a new
measurement (100/parent -> 90.9); determinism (same inputs -> identical plan hash);
and a static AST purity pin.

## Rejected claims

- **Not** a hard-coded capacity (§13.1, §43.9): the density is an EMA to update
  from receipts; the constants are canaryable planning defaults, not truths.
- **Not** the theoretical edge: the packer targets ~60, never ~74.
- Capacity uses BILLED completion density (87/parent), never the visible ~29
  (§43.2) — the measured Compound internal-agentic overhead is respected.
- No runtime path claimed working (AGENTS.md §9): S3 is a pure library slice.

## Open contract gaps

- Nothing mints tickets from these manifests yet. Next: **S4 — SQL durability**
  (`stores/postgres/migrations/<next>_document_parent_maps.sql`): the
  `document_parent_map_batches` (resumable substage: status pending/leased/partial/
  done/error, expected/valid counts, alias_manifest, input/raw hashes, lease) and
  `document_parent_maps` (final authoritative map: unique active per doc_id +
  parent_id + map_contract) tables, plus the parent-exclusion record, with
  idempotent insert/update and the one-active-map uniqueness — no worker yet.
  Contract/migration changes need a work log (repo_guard companion rule).
- The combined-capacity path needs the global profile's MEASURED billed output
  (S5/S6); until S6 canaries it, `plan_batches` without
  `combined_global_profile_billed_tokens` is the mapping-only path.
- The EMA has no persistence yet; the durable shared budget (S7) will own the
  measured density and the per-key accounting.
