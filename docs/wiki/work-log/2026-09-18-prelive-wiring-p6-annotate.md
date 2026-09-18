---
title: "WORK LOG — Pre-live wiring 1/N: P6 subquery-provenance annotation in the compiler"
change_id: PRELIVE-WIRING-P6-ANNOTATE
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Wires P6 into the live compiler path. _profile_scout now also returns the fused ProfileScoutResult; _compile_chat_plan annotates every returned plan with annotate_subquery_provenance(plan, scout_result) via a fail-open _finish() on all four exits. Flag-gated with the scout (scout_result is None when POLYMATH_PROFILE_SCOUT is off, so annotate still runs and gives q0/aspect subqueries their role+reason — provenance completeness — with no scout links). orchestrator/, so NOT worktree-testable: IMPLEMENTED, runtime INVALIDATED until the live window (L1-L5)."
---

## Contract
The live compiler must attach P6 provenance (SUBQUERY-PROVENANCE-V1) to the plan it emits, so the
receipt reconstructs why each subquery exists and whether the scout influenced it. q0 stays
authoritative; a scout miss/off must not break the turn (fail-open); no planner signature change.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - `_profile_scout(...)` now returns `(source_names, ProfileScoutResult | None, receipt)` — the
    fused result (previously discarded) is threaded out for annotation; None on off/no-corpus/error.
  - `_compile_chat_plan(...)` unpacks `scout_result` and defines a fail-open `_finish(plan)` that
    calls `annotate_subquery_provenance(plan, scout_result)`; all four return paths go through
    `_finish` (no-lane fallback, per-attempt success, exhausted loop, exception fallback).

## Proof
`ast.parse(ui.py)` OK. `ruff --select F,E9` on ui.py: the 6 findings are the SAME pre-existing
ELITE debt as P5b-b (1050/1075 + `offset`/2515/3099/3100, now shifted +12 by the added lines) —
NONE in the added code. `_profile_scout` has exactly one caller (`_compile_chat_plan`), updated.
The pure annotation it calls is unit-proven (P6, 16/16). **Runtime INVALIDATED** — `orchestrator`
resolves from MAIN via the editable `.pth`, so the flag-on path is qualified only in the live
window (L1-L5): with `POLYMATH_PROFILE_SCOUT=1` the plan receipt shows role/reason/origin on every
subquery and `subquery_provenance` block; flag-off, annotate still runs (scout_result=None) and
gives provenance completeness with no scout links.

## Rejected claims
- Unit-test `_compile_chat_plan` in the worktree (rejected — orchestrator is MAIN-resolved; that
  proves MAIN, not this edit; the pure annotate is unit-proven and the wiring is live-qualified).

## Open contract gaps (impact dispositions)
- `SUBQUERY_PROVENANCE` (`ui.py` wiring): **UPDATED** — the pure core was already live; this adds
  the runtime call site (INVALIDATED until L1-L5).
- `QUERY_PLANNER` / `PROFILE_SCOUT_OUTPUT`: **TESTED_UNCHANGED** — `compile_plan` unchanged;
  `ProfileScoutResult` consumed read-only.
- LIVE GATE: `POLYMATH_PROFILE_SCOUT=1` + bounce → assert the plan receipt carries provenance +
  100% completeness on the real path.
