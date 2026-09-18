---
title: "WORK LOG — P11: profile-yield receipt + observability (PROFILE-YIELD-RECEIPT-V1)"
change_id: PROFILE-YIELD-RECEIPT-P11
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Adds the checklist P11 killer metric profile_expansion_evidence_yield and a single librarian_receipt composer. New pure module profile_yield.py: distinguishes profile/scout expansion OCCURRED (a PROFILE-origin subquery ran) from expansion PRODUCED source evidence (that subquery surfaced a final selected child); a scout nomination is never counted as yield. librarian_receipt reconstructs q0 -> scout -> plan(+P6 provenance) -> mode/lanes -> evidence(per-item source-query provenance) -> resolution(P10) -> yield. Deterministic; no I/O, no LLM. Receipt-assembly wiring into the SSE/query receipt is orchestrator-side (pre-live)."
---

## Contract
Checklist P11: the receipt must let a single runtime query be reconstructed across q0, Profile
Scout, planner, subqueries, retrieval mode/lanes, profile/pMAP nominations, raw candidates, fusion,
reranking, final evidence, graph destinations, resolution rounds, synthesis. Emit
`profile_expansion_evidence_yield` — of the subqueries created because corpus profiles suggested
them, how many produced SUPPORTING SOURCE EVIDENCE. It must distinguish "expansion occurred" from
"expansion actually produced source evidence", and must NOT count scout nominations themselves as
yield.

## Changes
- `shared/polymath_shared/profile_yield.py` (NEW, pure):
  - `profile_expansion_evidence_yield(subqueries, evidence_items)` — numerator = PROFILE-origin
    (P6/P10 `origin`) subqueries whose id appears in the source-query provenance of a FINAL
    (selected) evidence item; denominator = PROFILE-origin subqueries executed. Returns
    `profile_subqueries` (occurred when > 0), `profile_subqueries_with_evidence` (produced evidence
    when > 0), the ratio, `expansion_occurred`, `expansion_yielded_evidence`, `yielded_query_ids`.
  - `selected_evidence_query_ids` / `evidence_provenance` (per-item normalization, verbatim
    pointers) / `evidence_yield_by_origin` (USER/PROFILE/GRAPH/EVIDENCE_GAP executed-vs-yielded).
  - `librarian_receipt(plan, evidence_items, *, scout, resolution, mode, lanes, q0)` — composes the
    full reconstructable receipt from already-produced parts (plan_receipt carries the P6 subquery
    provenance; resolution carries the P10 `resolution_receipt`).

## Proof
`tests/determinism/test_profile_yield.py` — 9 asserting tests: the metric counts a PROFILE
subquery ONLY when a final selected evidence item names it; expansion-occurred-but-no-evidence
(yield 0); no-profile-expansion; an UNSELECTED (reranked-away) item does not count; **a scout
nomination with an inspired_by link but no final child yields 0** (nominations are never evidence);
selected-id union excludes unselected; per-origin breakdown; single-id normalization; and
`librarian_receipt` composes q0 → scout → plan → evidence → resolution → yield. All green; executed
path = worktree (`polymath_shared.profile_yield.__file__` → `pmv4-librarian/shared/...`), genuine
UNIT_PROVEN. Consumes the P6 `origin` + P10 `resolution_receipt` contracts directly.

## Rejected claims
- Count scout nominations (or profile-derived candidates that were retrieved but reranked away) as
  yield (rejected — the metric's whole purpose is to separate synthetic association from real
  corpus-guided discovery; only a FINAL selected source child counts).
- Recompute retrieval inside the receipt (rejected — the receipt composes already-produced parts;
  it is an observability layer, not a retrieval path).
- Assemble the receipt into the live SSE stream here (rejected — orchestrator is not
  worktree-importable; the receipt-assembly call site lands in the pre-live wiring slice and is
  qualified live L1–L5, where §16's `profile_expansion_evidence_yield > 0` is demonstrated on real
  adversarial cross-domain examples).

## Open contract gaps (impact dispositions)
- `PROFILE_YIELD_RECEIPT`: **UPDATED** — pending → live; `paths`=`profile_yield.py`, tests filled.
  Unit-proven; the SSE/query-receipt assembly call site is the one remaining live gate.
- `QUERY_PLANNER` (`chat_plan.py`): **TESTED_UNCHANGED** — read-only use of `CompiledQuery.origin`
  + `plan_receipt`; no signature change.
- `RESOLUTION_STATE` / `PROFILE_SCOUT_OUTPUT`: **TESTED_UNCHANGED** — the resolution/scout receipts
  are consumed as opaque dicts; no schema change here.
- `RETRIEVAL_RECEIPT`: **NOT_AFFECTED** — `librarian_receipt` is a new composer; embedding it in the
  live receipt is orchestrator-side (pre-live).
- `ACCEPTANCE`: **DEFERRED** — the acceptance harness (mission §16/§27) reads
  `profile_expansion_evidence_yield` on the live run.
- LIVE GATE: call `librarian_receipt(...)` at the end of the chat retrieval turn (after scout,
  plan+provenance, retrieval, resolution) and surface it in the query receipt / SSE; demonstrate
  `profile_expansion_evidence_yield > 0` on genuine cross-domain discovery cases (L1–L5).
