---
title: "WORK LOG — P6: typed subquery provenance (SUBQUERY-PROVENANCE-V1)"
change_id: SUBQUERY-PROVENANCE-P6
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Adds deterministic per-subquery lineage. CompiledQuery gains additive provenance fields (role/reason/inspired_by_profile/profile_surface/target, all defaulted); a new pure module subquery_provenance.py consumes PROFILE_SCOUT_OUTPUT and annotates each subquery so a receipt can reconstruct why every subquery exists and whether the scout influenced it — while q0 stays authoritative and fabricated scout links are rejected. No planner signature change, no I/O, no LLM. The runtime call site (ui.py, after _profile_scout + compile_plan) lands in the pre-live wiring slice; the shared core here is unit-proven in the worktree."
---

## Contract
Each generated subquery must carry enough lineage to reconstruct: `q0 → information need →
subquery → why → role/purpose → scout influence (if any) → evidence`. Owner invariants
(PROFILE-SCOUT-V1): `q0` is authoritative and always searched; the scout *informs*, never gates;
a subquery may be scout-inspired but the scout never rewrites `q0`; routing artifacts are not
factual evidence. Acceptance (mission §4/§17): **100 % provenance completeness** (every executed
subquery has a role + reason) and **100 % q0 preservation** (the PRIMARY subquery is `direct`,
never scout-derived, text untouched). Reuse existing fields; do not invent fields to reproduce prose.

## Changes
- `shared/polymath_shared/chat_plan.py`:
  - `ROLE_TYPES` (`direct/prerequisite/complement/bridge/contrast/inversion/resolution`) +
    `_TYPE_ROLE` + `derive_role(qtype)` + `default_reason(qtype, role)` — the deterministic
    type→role map (`resolution` reserved for P10 resolution-round subqueries).
  - `CompiledQuery` gains additive fields `role / reason / inspired_by_profile / profile_surface
    / target` (all defaulted) + `__post_init__` that derives `role`/`reason` from `type` when not
    supplied and coerces a list `inspired_by_profile` to a tuple. Every existing construction
    site (fallback, compare-sides rebuild, corpus-seed) keeps working unchanged.
  - `validate_plan` reads OPTIONAL planner-supplied `role`/`reason`/`inspired_by`(`_profile`)/
    `profile_surface`/`target` per query (validated; invalid role → derived), tracks which were
    explicit, and after the compiler's type-normalization (ADJACENT demotion, PRIMARY
    enforcement) re-derives `role`/`reason` for the rest so a type flip never leaves a stale role.
  - `plan_receipt` surfaces `subquery_provenance` first-class (per-query fields already ride in
    `queries` via `asdict`).
- `shared/polymath_shared/subquery_provenance.py` (NEW): pure `annotate_subquery_provenance(plan,
  scout)` — forces the PRIMARY subquery to `direct` with empty scout linkage (q0 authority);
  for non-primary subqueries keeps ONLY `inspired_by_profile` doc_ids the scout actually
  nominated (drops fabricated links) and a `profile_surface` only if it is among the kept
  nominations' matched surfaces; guarantees role+reason on all; writes a receipt block
  (`scout_present`, `scout_nominations`, per-subquery rows, `q0_preserved`,
  `provenance_complete`, `provenance_completeness`). Plus `q0_preserved` / `provenance_complete`
  / `provenance_completeness` metric helpers. No I/O, no LLM.

## Proof
`tests/determinism/test_subquery_provenance.py` — 14 asserting tests, all green: type→role map
over every `QUERY_TYPES`; post_init derivation; explicit-role preservation (the `resolution`
override); `validate_plan` reads supplied provenance + drops an invalid role; **role follows the
FINAL type after ADJACENT demotion** (no stale `bridge`); annotate preserves q0 and ignores a
scout link claimed on a PRIMARY; **fabricated non-nominated doc_id dropped**; surface-not-in-
matched dropped; `None` scout degrades cleanly; completeness 1.0 on a normal plan; no-retrieval
plan vacuously preserved; fallback plan preserved+complete; receipt carries lineage.
Executed-path verified per §2b: `polymath_shared.subquery_provenance.__file__` and
`chat_plan.__file__` both resolve to the **worktree** (`pmv4-librarian/shared/...`) under the
test — so this is a genuine **UNIT_PROVEN**, not a MAIN-checkout artifact. Regression: the
chat-compiler / funnel / hygiene / synthesis / runtime / scope / compiler-context / profile-scout
determinism files stay green (additive fields, no positional CompiledQuery construction in tests,
no existing reader of the new fields).

## Rejected claims
- Change `compile_plan`'s signature to take the `ProfileScoutResult` (rejected — kept the planner
  signature stable, matching the P5b-b discipline; provenance annotation is an explicit,
  separately-testable post-step `annotate_subquery_provenance(plan, scout)`, smallest blast radius,
  no QUERY_PLANNER contract break).
- Let the scout attach `inspired_by_profile` by fuzzy-matching subquery text to nomination
  snippets (rejected — that fabricates lineage; only a doc the scout actually nominated may be
  cited, and even then only when the planner declared the link).
- Derive a semantic `capability`/`target` inside the deterministic layer (rejected — `target` is
  planner-supplied or None; the deterministic layer never invents interpretation, mirroring the
  P5 "no capability" rule).
- Wire the runtime call into `ui.py` in this slice (rejected — `orchestrator` is not
  worktree-importable (editable `.pth` → MAIN), so a ui.py edit here could not be honestly
  unit-proven; the call site lands in the pre-live wiring slice and is qualified live L1–L5).

## Open contract gaps (impact dispositions)
- `SUBQUERY_PROVENANCE`: **UPDATED** — pending → live; `paths` = `subquery_provenance.py` +
  `chat_plan.py`; tests filled. Unit-proven; the ui.py call site is the one remaining live gate.
- `QUERY_PLANNER` (`chat_plan.py`): **UPDATED (additive, TESTED)** — new fields + validate_plan
  reads; `compile_plan`/`validate_plan`/`plan_receipt` signatures unchanged; funnel test green.
- `PROFILE_SCOUT_OUTPUT`: **TESTED_UNCHANGED** — consumed read-only (`nominations`,
  `matched_surfaces`); the P5 schema is untouched.
- `RETRIEVAL_RECEIPT` / `CANDIDATE_ENGINE`: **NOT_AFFECTED** yet — `plan_receipt` gained an
  additive key; candidate_engine reads its own `SubQuery` type (`sq.qtype/text/weight`), not
  `CompiledQuery`. Verify at integration that no receipt consumer rejects the new key.
- `PROFILE_YIELD_RECEIPT` (pending, P11) / `RESOLUTION_STATE` (deferred, P10): **DEFERRED** — the
  next two slices consume this contract's output (`subquery_provenance` block + role vocabulary);
  no change owed here.
- `ACCEPTANCE`: **NOT_AFFECTED** — the cross-domain routing integration test does not assert on
  subquery provenance yet; the qualification harness (mission §17) will read the new receipt block.
- LIVE GATE: call `annotate_subquery_provenance(plan, scout_result)` in `ui._compile_chat_plan`
  (after `_profile_scout` + `compile_plan`) in the pre-live wiring slice; qualify provenance
  completeness + q0 preservation on the real path (L1–L5).
