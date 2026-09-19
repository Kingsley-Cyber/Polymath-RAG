---
change_id: WLK2C-LATENT-SELECTION
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C4-live/C5-live ORCHESTRATION (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure `shared/polymath_shared/latent_selection.py`: ties C4 (latent_eligibility) + C5 (latent_portfolio) into ONE bounded step over the judged candidate pool, with the cross-encoder INJECTED (`rerank`) so the whole grade+seat flow is unit-testable; only the real scoring is live. Score reuse + bounded budget (owner lock 2): q0↔chunk REUSED from the pool (never recomputed), q0↔bridge computed ONCE for all bridges (1 call, cached), bridge↔chunk once per bridge over its candidates — extra cost = 1 + (#distinct bridges) rerank calls, never per-candidate. Many-to-one preserved (lock 1, via evaluate_candidate); q0-primary + non-displacement (lock 3, via seat_portfolio). Fail-open: a rerank error → no latent additions, the DIRECT/q0 portfolio unaffected. No caller yet — the pool-plumbing into select_evidence/ui.py is the remaining live-only piece (proven at C7)."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C4-live/C5-live. The judged pool contains q0-sub-floor bridge candidates that q0-only selection
drops; this orchestration grades them (C4) and seats the bounded latent-aware portfolio (C5). Owner
locks: many-to-one preserved (evaluate every bridge path), score reuse (q0↔chunk reused, q0↔bridge
cached once/bridge, only bridge↔chunk is new) in one score space, and DIRECT protected but not
monopolizing (seat_portfolio). The cross-encoder is injected so the flow is deterministic + testable.

## Changes
- NEW `shared/polymath_shared/latent_selection.py` (pure over injected `rerank`):
  `grade_and_seat_latent(*, q0_text, pool, bridges, rerank, capacity, floor, bridge_valid_floor,
  divergent_local_floor, direct_per_rep_cap, max_divergent, min_adequate_direct, complementary_cap)` →
  `(seated, trace)`. `pool` = judged candidates `{chunk_id, doc_id, parent_id, text, query_ids,
  q0_score}` (q0_score REUSED). `bridges` = `{bridge_id: {query, proposed_role}}`. Computes bridge↔q0
  once for all bridges (cached) + bridge↔chunk once per bridge (batched over its candidates), then
  `evaluate_candidate` (many-to-one) per candidate, then `seat_portfolio`. `seated` items carry
  `seat_role` + the C4 `eligibility` dict; `trace` = bridge_q0 + the C5 counts. `_score_map` fail-open.
- NEW `tests/determinism/test_latent_selection.py` (7 tests).
- Register row 11.323; this work-log; scaffold TREE declarations.

## Proof
`UNIT_PROVEN` — executed path = the worktree copy. 7/7 green: a VALID bridge seats a q0-sub-floor
candidate COMPLEMENTARY; **ANTI-HIJACK end-to-end — an INVALID bridge with excellent local relevance
(+6) never grants latent status** (demoted, never COMPLEMENTARY); q0↔chunk is reused (exactly one
q0-side rerank call, scoring the bridge not chunks); the extra budget is `1 + #bridges` calls; INVARIANT
B end-to-end (a redundant same-representation DIRECT yields its slot to a distinct COMPLEMENTARY); a
rerank exception fails open (DIRECT kept, no latent added); deterministic.

## Rejected claims
- No per-candidate model call (the extra scoring is 1 + #bridges rerank calls, batched). No recompute of
  q0↔chunk. A locally excellent chunk on an invalid bridge is never seated as latent evidence.

## Open contract gaps
`contract_impact` = no impacted production contract (new isolated `shared/` module; imports C4 + C5).
REMAINING live-only piece (deferred to C7, owner reviews C5 first): expose the judged pool (prefix
candidates with text + q0 rerank score + query_ids) from `chat_retrieve_v2`/`select_evidence`; build
`bridges` from the plan's BRIDGE-origin subqueries in `ui.py`; call `grade_and_seat_latent` with
`_rerank_children` as `rerank` at synthesis capacity; apply `seat_role` to the CA4 evidence bundle;
adequate-DIRECT via CA4 `establishes_need`. Then C6 (the calibration receipt) + C7 (merge + port-gated
bounce + WLK2C qual + full CA5 64×4). Bounds (`direct_per_rep_cap=3`, `max_divergent=2`) config-driven,
pending owner confirmation.
