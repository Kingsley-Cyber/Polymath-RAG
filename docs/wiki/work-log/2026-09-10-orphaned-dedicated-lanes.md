---
title: "WORK LOG — orphaned dedicated lanes: 5 active provider lanes served no stage after the lane reassignment"
change_id: ORPHANED-DEDICATED-LANES-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (config fix; proven against the lane registry; lands on the next fleet bounce)
register: 11.194
package: "config/cloud_providers.json"
architecture_impact: "none (no new topology). Restores the lane→function assignment that PROVIDER-LANE-REASSIGNMENT-V1 (11.193) already declared: gemini5/5b/6/6b + nvidia rejoin the general GRAPH_EXTRACTION ring instead of being dedicated to a stage pin that no longer exists."
---

> **Ledger:** found during the post-bounce verification of 11.193 (owner-authorized fleet bounce
> 2026-09-10). Register **11.194**. Config only; no code, no new provider, no spend.

## Contract

Requested outcome: the live graph-extraction ring must equal what register 11.193 declared —
`gemini1–6` + `gemini1b–6b` + `nvidia`,`nvidia2` + `siliconflow1–3`.

- **Smallest acceptance:** `lane_registry.build_registry()` assigns `GRAPH_EXTRACTION` to every enabled,
  credentialed Google/NVIDIA/SiliconFlow lane, and NO enabled+active lane resolves to `dedicated_unpinned`.
- **Owner / public contract:** provider capacity available to graph extraction; no model added or removed.
- **Inputs/outputs/persistence:** `config/cloud_providers.json` only; no state written.
- **Dependency edges:** `config/cloud_providers.json` → `lane_registry.build_registry()` →
  `control_plane_status.pool_lanes_detail()` (UI) and `llm_extraction/pool.select_endpoint_for_stage()`
  (dispatch). Reverse dependents: the `/control_plane/pool/GRAPH_EXTRACTION` surface.
- **Verifier / rollback:** registry assertion below; rollback = restore `"dedicated": true` on the 5 lanes.

## Changes

- `config/cloud_providers.json` — `"dedicated": true` → `false` on `gemini5`, `gemini5b`, `gemini6`,
  `gemini6b`, `nvidia`.

## Proof

- **The defect, measured live after the 11.193 bounce:** `/control_plane/pool/GRAPH_EXTRACTION` returned only
  `gemini1–4`, `gemini1b–4b`, `nvidia2`, `siliconflow1–3` — 8 Google lanes, not the declared 12.
  `build_registry()` classified `gemini5, gemini5b, gemini6, gemini6b, nvidia` as **`dedicated_unpinned`**:
  `enabled=true`, `credential_present=true`, `reachability=active`, and present in **no** `stage_pins` group.
  Per DEDICATED-V1 (`llm_extraction/pool.py:68-70`, `:293-294`) a dedicated endpoint "serves ONLY stages pinned
  to it; it never joins the general extraction sharding" — so those five lanes served **zero** stages. They were
  dedicated to the profile fallbacks (`profile_fallback_gemini1/2` on `GEMINI_API_KEY_5/6`) that 11.193 disabled;
  the flag was not cleared with them.
- **Why 11.193's own validation missed it:** it validated that all four PINS resolve to active endpoints (0 dark)
  — a pin-side check. An un-pinned dedicated lane is invisible to that check: it is not dark, it is unreachable
  *by construction*. `unreachable_pins()` deliberately skips `dedicated_unpinned` (`lane_registry.py:322`).
- **After (offline, provider-free):** `build_registry()` → `GRAPH_EXTRACTION` = 18 lanes
  (`gemini1–6`, `gemini1b–6b`, `nvidia`, `nvidia2`, `primary`, `siliconflow1–3`); enabled+active lanes resolving
  to `dedicated_unpinned` = **NONE**; `unreachable_pins()` = **NONE**. The remaining 12 `dedicated_unpinned`
  entries are all `enabled=false` (the superseded `compiler1–4`, `profile_groq2–6`,
  `profile_fallback_gemini1/2`, `map_groq1`), i.e. inert by intent.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok · `bundle_integrity` READY (config is
  not in the 8-file semantic bundle). Fence-safe: ready/leased tickets = 0 at edit time.

## Rejected claims

- **"The 8-lane ring was a display bug in the control plane."** REJECTED — the same `dedicated` flag drives
  DISPATCH (`select_endpoint_for_stage` excludes dedicated lanes from the non-dedicated roster), not only the
  registry view. The five lanes were genuinely unreachable capacity, not merely mislabelled.
- **"This adds provider topology."** REJECTED — no provider, key, or model is added. Five already-configured,
  already-credentialed lanes are returned to the ring 11.193 declared them part of.
- **"Raise `MAP_RELIABILITY_CAP` / add a third graph model while we are here."** REJECTED — out of slice and
  owner-declined (2026-09-10: convergence, not topology).

## Open contract gaps

- **Inert until the next fleet bounce.** The running fleet keeps the 8-lane ring until `boot_polymath.sh`.
- **No throughput measurement.** That the ring is 18 lanes is proven; that graph throughput actually rises is
  NOT measured here (no ingestion is running). Any future third-lane decision needs a measured ring-throughput
  number, not a lane count.
- **No guard prevents recurrence.** A lane can still be `dedicated: true` and pinned to nothing without any
  check failing. A registry assertion ("no enabled+active lane is `dedicated_unpinned`") would close it; not
  built in this slice.
