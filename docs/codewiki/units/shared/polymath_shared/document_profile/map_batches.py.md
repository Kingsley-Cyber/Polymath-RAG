# unit: shared/polymath_shared/document_profile/map_batches.py
anchor: shared/polymath_shared/document_profile/map_batches.py:1-294

## purpose
Deterministic token packer / capacity model for parent mapping (plan slice S3). Given the S1 parent skeletons and a measured per-parent density model, it computes how many parents safely fit one Compound-Mini request and cuts a document's parents into deterministic batch manifests — map_batches.py:1-8, map_batches.py:237-244 [DERIVED]. Pure shared policy: no I/O, no model — map_batches.py:6 [DERIVED].

Module importers (FACTS): `shared/polymath_shared/document_profile/_small-modules`, `workers/workers/doc_parent_map_worker.py`.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `DensityModel` | class | `(input_tokens_per_parent=135.7, billed_tokens_per_parent=87.0, visible_tokens_per_parent=29.0)`; `update(*, input_tokens, billed_tokens, visible_tokens, parents, alpha=0.3) -> DensityModel` | map_batches.py:65-90 | — |
| `DEFAULT_DENSITY` | const | `DensityModel()` | map_batches.py:93 | — |
| `skeleton_prompt_tokens` | def | `(skeleton: ParentSkeleton) -> int` | map_batches.py:96-110 | — |
| `estimate_input_tokens` | def | `(skeletons: Sequence[ParentSkeleton]) -> int` | map_batches.py:113-114 | — |
| `mapping_only_capacity` | def | `(density=DEFAULT_DENSITY, *, envelope=6500, target=60, safety=512, reliability_cap=15) -> int` | map_batches.py:117-131 | — |
| `combined_capacity` | def | `(density, *, global_profile_billed_tokens, envelope=6500, safety=512) -> int` | map_batches.py:134-146 | — |
| `request_total_tokens` | def | `(density, parents, *, global_profile_billed_tokens=0) -> float` | map_batches.py:149-153 | — |
| `token_feasible_rpm` | def | `(total_tokens_per_request, *, target_rpm=4, tpm_ceiling=70000, per_request_cap=15000) -> int` | map_batches.py:156-173 | — |
| `MapBatch` | class | frozen dataclass: `ordinal, aliases, est_input_tokens, est_billed_tokens, est_total_tokens, is_combined, batch_hash`; property `parent_count` | map_batches.py:177-188 | — |
| `BatchPlan` | class | frozen dataclass: `contract, density, batches, mapping_only_capacity, combined_capacity, plan_hash`; property `total_parents` | map_batches.py:192-202 | — |
| `BATCH_PLANNER_VERSION` | const | `"map-batches-v2"` | map_batches.py:205 | — |
| `plan_batches` | def | `(manifest, density=DEFAULT_DENSITY, *, combined_global_profile_billed_tokens=None, contract="map-batches-v2", grounding_hash="", reliability_cap=15) -> BatchPlan` | map_batches.py:235-293 | workers/workers/doc_parent_map_worker.py — comment: the pMAP pool worker passes its pool's qualified cap, map_batches.py:253-256 [DERIVED] |

## contracts

**`mapping_only_capacity`** — map_batches.py:117-131
- in: defaults as in the table; `theoretical = int((envelope - safety) // max(1.0, density.billed_tokens_per_parent))` — map_batches.py:130 [DERIVED]
- out: `max(1, min(target, theoretical, reliability_cap))` — map_batches.py:131 [DERIVED]
- with defaults: `(6500 - 512) // 87.0 = 68`, so `min(60, 68, 15) = 15` — the reliability cap dominates, not tokens — map_batches.py:130-131 [DERIVED]
- post: result `>= 1` — map_batches.py:131 [DERIVED]

**`combined_capacity`** — map_batches.py:134-146
- in: requires the global profile's MEASURED billed output — map_batches.py:141-142 [DERIVED]
- out: `room = envelope - global_profile_billed_tokens - safety`; `0` if `room <= 0`, else `max(0, int(room // max(1.0, density.billed_tokens_per_parent)))` — map_batches.py:143-146 [DERIVED]

**`request_total_tokens`** — map_batches.py:149-153
- out: `parents * (density.input_tokens_per_parent + density.billed_tokens_per_parent) + global_profile_billed_tokens`; 222.7/parent under `DEFAULT_DENSITY` — map_batches.py:153 [DERIVED]

**`token_feasible_rpm`** — map_batches.py:156-173
- out: `total <= 0` → `target_rpm` (4) unclamped — map_batches.py:169-170 [DERIVED]; else `max(1, min(ceiling, tpm_bound))` where `tpm_bound = 70000 // total`, `ceiling = 4 if total <= 15000 else 3` — map_batches.py:171-173 [DERIVED]
- boundary: total `15000` → 4 RPM; total `15001` → 3 RPM (the pre-TPM drop is the whole point of the guard) — map_batches.py:172 [DERIVED]

**`DensityModel.update`** — map_batches.py:73-90
- EMA blend `(1 - alpha) * old + alpha * (new / parents)`, `alpha=0.3`; `parents <= 0` returns `self` unchanged — map_batches.py:80-85 [DERIVED]

**`plan_batches`** — map_batches.py:235-293
- out: first batch is combined IFF `combined_global_profile_billed_tokens is not None and comb_cap > 0 and aliases` — map_batches.py:267 [DERIVED]; remainder are mapping-only chunks of `cap` aliases in S1 ordinal order — map_batches.py:251, map_batches.py:273-278 [DERIVED]
- `batch_hash = _sha256("\x1f".join([contract, manifest_hash, str(is_combined)] + [f"{alias}\x1e{skeleton_hash}" ...] [+ "grounding\x1e" + grounding_hash]))` — map_batches.py:220-223 [DERIVED]
- `plan_hash = _sha256("\x1d".join([contract, manifest_hash] + [batch_hash ...] [+ grounding part]))` — map_batches.py:282-285 [DERIVED]
- post: `total_parents == len(manifest.skeletons)` (loop consumes every alias) — map_batches.py:200-202, map_batches.py:273-278 [DERIVED]

## effect surface
None. `tables_read` and `tables_written` are empty in FACTS; no Qdrant, file, network, subprocess, or env access — module docstring "no I/O, no model" — map_batches.py:6 [DERIVED]. Imports only `hashlib`, `math`, `dataclasses`, `typing`, and `parent_skeleton` — map_batches.py:19-24 [DERIVED].

## invariants
INVARIANT: `mapping_only_capacity()` under defaults `== 15 == MAP_RELIABILITY_CAP` (min of target 60, theoretical 68, cap 15) — map_batches.py:130-131 [DERIVED]
  fails-if: raising the cap without re-checking density makes the token envelope or the 60 target binding; a bad batch size silently loses large-doc maps (comment at map_batches.py:38-40).
INVARIANT: every mapping-only batch `parent_count <= cap = mapping_only_capacity(...)`; only the final chunk may be smaller — map_batches.py:273-278 [DERIVED]
  fails-if: oversized batches hit compound-mini empty/partial structured output (15 → 98.8% durable vs 35 → 50.8%, map_batches.py:42-46).
INVARIANT: `BatchPlan.total_parents == len(manifest.skeletons)` — map_batches.py:200-202, map_batches.py:273-278 [DERIVED]
  fails-if: dropped parents are never mapped.
INVARIANT: combined batch exists only when combined tokens given AND `comb_cap > 0` AND aliases non-empty — map_batches.py:267 [DERIVED]
  fails-if: a combined call that cannot fit the global profile would truncate its output.
INVARIANT: `skeleton_prompt_tokens >= 1` (`max(1, ceil(chars/4))`) — map_batches.py:110 [DERIVED]
INVARIANT: `token_feasible_rpm >= 1` whenever `total_tokens_per_request > 0` — map_batches.py:173 [DERIVED]
INVARIANT: two documents sharing aliases `P0001..P0060` cannot produce colliding `batch_hash` (manifest_hash + per-alias skeleton_hash bound into the hash) — map_batches.py:213-220 [DERIVED]
INVARIANT: `grounding_hash == ""` reproduces the legacy v1 hash byte-for-byte; non-empty changes every batch/plan hash — map_batches.py:217-222, map_batches.py:280-284 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC (pure computation; only `hashlib`/`math`; no clock/random/uuid/network/db/env — map_batches.py:19-24, map_batches.py:6) [DERIVED]
idempotency: SAFE (no side effects; same `(manifest, density)` ⇒ identical batch boundaries — map_batches.py:248-249) [DERIVED]

## failure behaviour
No try/except handlers anywhere in the file; nothing is swallowed — FACTS list no fallbacks [DERIVED]. Errors escape to the caller: unknown alias raises `KeyError` via `by_alias[a]` — map_batches.py:210 [DERIVED]; division is guarded by `max(1.0, density.billed_tokens_per_parent)` at both division sites — map_batches.py:130, map_batches.py:146 [DERIVED].

## dumb-code flags
- `MAPPING_ONLY_PROVEN = 40` is defined and never referenced anywhere in the file — dead constant here — map_batches.py:32 [DERIVED].
- Three ceilings coexist (target 60, envelope-derived 68, reliability cap 15) and only the smallest is active; the 60/68 numbers are effectively decorative under defaults — map_batches.py:31, map_batches.py:49, map_batches.py:130-131 [DERIVED].
- `DensityModel` defaults are the frozen measured baseline (135.7 / 87.0 / 29.0) while the docstring insists it is "an EMA... never a permanent constant" — tension lives in code vs comment — map_batches.py:13-15 vs map_batches.py:69-71 [DERIVED].
- `token_feasible_rpm` returns the FULL `target_rpm` for zero/negative totals instead of flagging nonsense input — map_batches.py:169-170 [DERIVED].
- `_CHARS_PER_TOKEN = 4` duplicates the estimate in `document_profile.context.est_tokens` (comment admits the copy) — map_batches.py:56-57 [DERIVED].

## refactor notes
- The hash recipe (separators `\x1e` / `\x1f` / `\x1d`, part order, `str(is_combined)`) is a durable batch identity; changing it invalidates stored identities and both importers (`workers/workers/doc_parent_map_worker.py`, `shared/polymath_shared/document_profile/_small-modules`) — map_batches.py:213-223, map_batches.py:282-285 [DERIVED].
- `grounding_hash=""` must keep reproducing the v1 hash exactly, or legacy SKELETON-ONLY maps get re-run — map_batches.py:217-219 [DERIVED].
- `plan_batches`'s `reliability_cap` is caller-supplied (pool's qualified cap, min over active lanes); re-hardcoding 15 inside would regress lane qualification — map_batches.py:253-257 [DERIVED].
- `BATCH_PLANNER_VERSION` is hashed into `contract`; bumping `"map-batches-v2"` changes every `batch_hash`/`plan_hash` — map_batches.py:205, map_batches.py:220 [DERIVED].
- Hard dependency on `ParentSkeleton` fields `alias, heading_path, lead_excerpt, salient_excerpt, key_terms, identifiers, skeleton_hash` and `SkeletonManifest.skeletons/manifest_hash` — changes in `parent_skeleton.py` ripple directly — map_batches.py:24, map_batches.py:102-108, map_batches.py:210, map_batches.py:220 [DERIVED].

## VERIFY
```verify
grep -Fq 'MAP_RELIABILITY_CAP = 15' shared/polymath_shared/document_profile/map_batches.py
grep -Fq 'COMPLETION_ENVELOPE_TOKENS = 6500' shared/polymath_shared/document_profile/map_batches.py
grep -Fq 'MAPPING_ONLY_PROVEN = 40' shared/polymath_shared/document_profile/map_batches.py
grep -Fq 'BATCH_PLANNER_VERSION = "map-batches-v2"' shared/polymath_shared/document_profile/map_batches.py
grep -Fq 'return max(1, min(ceiling, tpm_bound))' shared/polymath_shared/document_profile/map_batches.py
grep -Fq 'plan_hash = _sha256("\x1d".join(plan_parts))' shared/polymath_shared/document_profile/map_batches.py
test "$(grep -c -F 'reliability_cap' shared/polymath_shared/document_profile/map_batches.py)" -ge 3
```
