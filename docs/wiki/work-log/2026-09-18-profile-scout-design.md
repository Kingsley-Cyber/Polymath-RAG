---
title: "WORK LOG — PROFILE-SCOUT-V1: frozen P5 semantic contract"
change_id: PROFILE-SCOUT-V1
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
status_note: "Frozen P5 contract shipped: profile_scout.py (11.289, 11.293), wired with title injection retired (11.294), live-proven in 11.301. (was: design)"
architecture_impact: "Freezes the P5 Profile Scout output schema + invariants BEFORE code, because the schema is a semantic contract P6 consumes. Design-only row (no runtime/schema change). Establishes: scout is ONE logical reconnaissance over TWO existing projections (DOCUMENT_PROFILE + PROFILE_ATOM), fused deterministically with per-hit provenance, no atom duplication into the profile point; the scout is the SOLE pre-plan recon — retires _compiler_titles / the title concept injection (B16); dualread untouched."
---

## Contract
Freeze P5 semantics as an owner-approved contract so P5a/P5b/P6 implement against a fixed
output schema. Acceptance: the doc states the position (pre-plan, feeds `compile_plan`), the
scout≠dualread separation, the dual-projection fusion, the `ProfileScoutResult` schema with
forbidden fields, the determinism rule, the 10 owner invariants, and the P5a→P5b→P6 build
sequence — with every reuse point named against real code.

## Changes
- New `docs/wiki/plans/PROFILE-SCOUT-V1.md` — the frozen P5 contract (owner-frozen 2026-09-18).
- Register row 11.287 (DESIGN). TREE: the plan doc + this work-log.
- No code, no schema, no flag flip in this row.

## Proof
Design grounded against the rebased librarian tree (`8f044b2`, on the ELITE base `4d95da2`):
- `PROFILE_ATOM` projection is real and searchable — `shared/polymath_shared/document_profile/profile_atom_projection.py`:
  `project_atoms()` upserts one dense vector per atom into `polymath_document_profile_atoms_<embedding_contract_id>`;
  `search_atoms(client, collection, query_vec, kinds, k=12)` (line 146) is the atom-lane vector search the scout reuses.
- `DOCUMENT_PROFILE` surface families are declared by `shared/polymath_shared/surface_registry.py`
  (`profile_vector` ∈ {dense, multi, None}); dense/multi = identity/theme + questions/searches/theories/concepts/seealso,
  the atom lane carries the discovery/lexical/rediscovery surfaces — so the two-projection fusion covers BRIDGE + discovery
  at v1 without any new projection.
- Planner seam confirmed untouched by the ELITE settlement: `compile_plan`/`ChatPlan`/`CompiledQuery`
  in `shared/polymath_shared/chat_plan.py` (ELITE's diff was confined to `orchestrator/api/{chat_retrieval,ui}.py`).

## Rejected claims
- That P5 requires an atom→document-profile projection first (rejected: owner directs one *logical* scout over two *physical* projections; do not duplicate atoms into the profile point).
- That the scout may emit mode/intent/subquery decisions (rejected: forbidden fields; the scout is not a hidden planner).
- That `_compiler_titles` (the title concept injection, B16) is kept alongside the scout (rejected — owner 2026-09-18: RETIRE it; the scout is the sole pre-plan reconnaissance and replaces it, the retirement landing in P5b atomic with the wiring).
- That a wall-clock budget may truncate results (rejected: breaks determinism; bound by K only).

## Open contract gaps
- The live `PROFILE_ATOM` collection is populated only for corpora whose `doc_profile` ran with the atom DAG wiring (11.283); P5b live qualification must confirm real atoms exist for the qualification corpus (queue L2/L5).
- `capability` text source (SUMMARY-else-top-surface) is fixed here; if a corpus lacks SUMMARY surfaces the fallback path is exercised — verify in P5a tests.
- The exact `DOCUMENT_PROFILE` search reuse (dedicated profile search vs the closure inside `dualread_search`) is deferred to P5b wiring; P5a takes it as an injected fn.
