---
change_id: WLK2C-C5-GROUNDING-SPLIT
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C5 grounding-split (owner adjustment; shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). `latent_portfolio.seat_portfolio` + `latent_selection.grade_and_seat_latent` gain two grounding gates: COMPLEMENTARY is admitted only when the answer HAS grounding (`establishes_need`, the CA4 DIRECT|PARTIAL signal); DIVERGENT is admitted only when there is ACTUAL DIRECT grounding (`has_direct_grounding` = CA4 n_direct ≥ 1) — never on PARTIAL alone and never absent. So establishes_need False ⇒ no COMPLEMENTARY + no DIVERGENT; PARTIAL-only ⇒ COMPLEMENTARY may seat but DIVERGENT capacity is 0. Preserves the hierarchy DIRECT→PARTIAL→COMPLEMENTARY→DIVERGENT: the librarian EXPANDS a grounded answer, never SUBSTITUTES for one. `direct_per_rep_cap=3` confirmed as a SOFT anti-monopoly cap (required DIRECT still fills leftover capacity beyond the cap); `max_divergent=2` a hard ceiling."
last_reviewed: 2026-09-18
---

## Contract
Owner approval-with-adjustment of the C5 bounds. `direct_per_rep_cap=3` (soft anti-monopoly, not an
answer-completeness limit — required DIRECT may exceed it via the fill step when capacity allows) and
`max_divergent=2` (hard) are approved. The adjustment: do NOT gate DIVERGENT on `establishes_need`
alone (which PARTIAL can satisfy). Split: COMPLEMENTARY ← establishes_need + C4 admission; DIVERGENT ←
establishes_need AND n_direct ≥ 1. A DIVERGENT candidate may never compensate for absent DIRECT grounding.

## Changes
- `shared/polymath_shared/latent_portfolio.py`: `seat_portfolio(..., establishes_need=True,
  has_direct_grounding=None)`. STEP 2 now computes `direct_grounded` (= `has_direct_grounding` when
  supplied by CA4, else seated C4-DIRECT ≥ `min_adequate_direct`) and `divergent_allowed`
  (= establishes_need AND direct_grounded). STEP 3 seats COMPLEMENTARY only when `establishes_need`.
  STEP 4 seats DIVERGENT only when `divergent_allowed`. Trace: `establishes_need`, `direct_grounded`,
  `divergent_allowed` (replaced `adequate_direct`).
- `shared/polymath_shared/latent_selection.py`: `grade_and_seat_latent` threads `establishes_need` +
  `has_direct_grounding` to `seat_portfolio` (C5-live passes CA4's real epistemic).
- `tests/determinism/test_latent_portfolio.py`: updated + 3 new invariants.
- Register row 11.324; this work-log; scaffold TREE declaration.

## Proof
`UNIT_PROVEN` — executed path = the worktree copy. 20 green (C5 13 + latent_selection 7):
DIVERGENT needs DIRECT grounding; **DIVERGENT never compensates for absent DIRECT** (establishes_need
True + has_direct_grounding False ⇒ divergent_allowed False, 0 divergent); COMPLEMENTARY blocked without
establishes_need; PARTIAL-only ⇒ complementary 1, divergent 0; plus the retained INVARIANT_A/B, the
per-rep anti-monopoly, ordering + determinism, and the latent_selection end-to-end anti-hijack.

## Rejected claims
- REJECTED "establishes_need alone gates DIVERGENT" — PARTIAL-only support must not unlock exploratory
  slots (the answer would be constructed around adjacent knowledge, not the question). Corrected per owner.

## Open contract gaps
`contract_impact` = no impacted production contract (isolated shared modules). Live wiring (next) passes
CA4's `epistemic.establishes_need` + (n_direct ≥ 1) into `grade_and_seat_latent`. Then C6 receipt + C7
merge/bounce/qual. Bounds config-driven; `direct_per_rep_cap=3`/`max_divergent=2` owner-approved.
