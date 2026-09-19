---
change_id: WLK2C-C5-LATENT-PORTFOLIO
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C5 pure core (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure `shared/polymath_shared/latent_portfolio.py`: converts C4 eligibility STATES into seats by the librarian pair of rules — (A) COMPLEMENTARY/DIVERGENT never displaces REQUIRED DIRECT; (B) redundant/nonessential DIRECT must not consume a slot a DISTINCT COMPLEMENTARY could occupy. Both fall out of the SEATING ORDER (required DIRECT → distinct COMPLEMENTARY → DIVERGENT → fill), so no eviction arithmetic + no invented scoring. q0 primary: DIRECT dominates but does NOT monopolize (per-representation cap so one document cannot eat the portfolio). DIVERGENT only atop adequate DIRECT grounding, ≤2, capacity 0 without DIRECT. Configurable + conservative. No caller yet (C5-live seats the live evidence; proven at C7)."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C5 (owner close-review target). Policy (owner-locked 5 steps): (1) seat REQUIRED/high-value
DIRECT; (2) establish adequate DIRECT grounding via CA4-style coverage; (3) COMPLEMENTARY that passed C4
+ adds distinct info + valid lineage + does not displace required DIRECT; (4) DIVERGENT only atop
adequate DIRECT, C4-eligible, capacity remaining, ≤2 seats; (5) fill remaining with ordinary evidence.
The pinned invariant PAIR: a complementary may never displace DIRECT required for q0, AND redundant
DIRECT must not automatically consume a slot a distinct complementary could take. "required/high-value
DIRECT", not "all DIRECT first" (else 24 DIRECT ⇒ portfolio full ⇒ 0 complementary, working while
accomplishing nothing).

## Changes
- NEW `shared/polymath_shared/latent_portfolio.py` (pure): `seat_portfolio(candidates, *, capacity,
  direct_per_rep_cap=3, max_divergent=2, min_adequate_direct=1, complementary_cap=None)` → `(seated,
  trace)`. `candidates` = rerank-ordered dicts `{chunk_id, rep_key|parent_id|doc_id, role}` (role = a C4
  state). Seats by the 5 steps: REQUIRED DIRECT capped at `direct_per_rep_cap` per representation (overflow
  = redundant); adequate = seated DIRECT ≥ `min_adequate_direct`; DISTINCT COMPLEMENTARY (a representation
  not already seated) BEFORE any redundant DIRECT; DIVERGENT only if adequate, ≤ `max_divergent`, new
  representation; then FILL (redundant DIRECT → redundant COMPLEMENTARY → ordinary). `seat_role` on each
  seated item; `trace` counts + `redundant_direct_yielded`/`complementary_yielded` for C6. Bounds default
  to the existing composer's per-doc soft max (3) — no benchmark constant.
- NEW `tests/determinism/test_latent_portfolio.py` (10 tests).
- Register row 11.322; this work-log; scaffold TREE declarations.

## Proof
`UNIT_PROVEN` — executed path = the worktree copy. 10/10 green, both invariants pinned:
**INVARIANT B** — a redundant DIRECT (same representation) YIELDS its slot to a distinct COMPLEMENTARY
(capacity 2: required D1 + C1 seated, redundant D2 yielded); **INVARIANT A** — at capacity 1 a required
DIRECT is kept and the COMPLEMENTARY is excluded (never displaces required DIRECT). Plus: DIRECT does not
monopolize (10 chunks/one rep, cap 3 ⇒ complementary still seated); DIVERGENT needs adequate DIRECT
(capacity 0 without it) and is ≤2; distinct-only complementary (a same-representation complementary drops
to fill); ordinary → RELATED fill; capacity 0 ⇒ empty; `complementary_cap` bounds; seating order
DIRECT→COMPLEMENTARY→DIVERGENT; deterministic.

## Rejected claims
- "DIRECT dominates" is NOT "DIRECT consumes every seat" — the per-rep cap + the required-vs-redundant
  split prevent monopolization. No complicated scoring arithmetic (roles + eligibility + ordering only).
  Distinctness = representation identity (parent/doc), not a tuned similarity threshold.

## Open contract gaps
`contract_impact` = no impacted production contract (new isolated `shared/` module; imports only the C4
state names). Deferred: C4-live (compute the two cross-encoder facts, attach `CandidateEligibility`) +
C5-live (map candidates → `{chunk_id, parent_id, role}`, call `seat_portfolio` at synthesis capacity,
apply `seat_role` to the evidence bundle extending CA4; adequate-DIRECT via CA4 `establishes_need`) + C6
(the calibration receipt). Proven live at C7 (merge + port-gated bounce + WLK2C qual + full CA5 64×4).
