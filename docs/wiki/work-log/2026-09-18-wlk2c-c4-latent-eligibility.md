---
change_id: WLK2C-C4-LATENT-ELIGIBILITY
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C4 pure core (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure `shared/polymath_shared/latent_eligibility.py`: the safety-critical semantic gate as a PURE STATE MACHINE over cross-encoder scores — it emits eligibility STATES (DIRECT_ELIGIBLE / COMPLEMENTARY_ELIGIBLE / DIVERGENT_ELIGIBLE / INELIGIBLE), never a fused score and never a seat (C5 seats). Two independent facts per bridge candidate: BRIDGE VALIDITY (q0↔bridge, the anti-hijack gate) + LOCAL RELEVANCE (origin_query↔chunk). Both links must hold; a locally excellent chunk on an INVALID bridge is INELIGIBLE (strong local never compensates for weak bridge validity). q0 primary (DIRECT wins regardless of bridge); never max(q0,bridge). Owner-locked thresholds: bridge-validity bar = the EXISTING production floor (config-driven, default = floor — no new benchmark constant); DIVERGENT local bar config-driven, default = floor for v1. No caller yet (C4-live computes the scores + wires it; C5 seats)."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C4 (owner-reviewed, three locks): (1) bridge↔q0 validity bar = the existing relevance floor,
config-driven, no invented constant (C7 records distributions to justify tightening later); (2) reuse
the cross-encoder — bridge validity scores `(query=q0, document=bridge_query)` ONCE per distinct bridge
(cached for its candidates), local relevance scores `(query=origin_query, document=chunk)`; no new LLM
call; (3) C4 does NOT own slot caps — it establishes semantic eligibility only, C5 owns the portfolio.
Separation: C4 outputs facts/states; C5 converts to seats. Never `max(q0,bridge)`; strong local
relevance never compensates for weak bridge validity. Required chain: q0 →(valid)→ bridge →(relevant)→
chunk; both links must hold.

## Changes
- NEW `shared/polymath_shared/latent_eligibility.py` (pure): `latent_eligibility(*, q0_chunk_score,
  floor, bridge_id, proposed_role, origin_chunk_score, bridge_q0_score, bridge_valid_floor,
  divergent_local_floor)` → `LatentEligibility{state, direct, bridge_id, bridge_valid, local_relevant,
  proposed_role, reason, scores}`. q0 PRIMARY: DIRECT_ELIGIBLE when chunk↔q0 clears the floor (regardless
  of any bridge). Else a bridge candidate needs a VALID bridge (q0↔bridge ≥ bridge_valid_floor, default
  = floor) THEN local relevance (origin↔chunk ≥ local bar; the DIVERGENT bar = divergent_local_floor,
  the COMPLEMENTARY bar = floor; the C2 proposed_role hint selects which). An invalid bridge → INELIGIBLE
  (`bridge_invalid_semantic`) no matter how strong the local score. `bridge_validity(score, floor)`
  helper. All scores are cross-encoder logits; the sigmoid floor matches the existing `aspect_weak_floor`.
  `scores` dict carries q0_chunk/origin_chunk/bridge_q0 for C6 calibration.
- MANY-TO-ONE (owner lock 1): `evaluate_candidate(*, chunk_id, q0_chunk_score, bridge_paths, …)` →
  `CandidateEligibility{direct_eligible, lineage_results:[LatentEligibility per path]}` — evaluates EVERY
  admissible bridge path, NEVER collapsing to one origin before scoring. `best()` picks the strongest
  admissible path for C5 seating (DIRECT synthesized from q0, else best bridge path; ties by higher
  origin↔chunk) while retaining every path for the C6 receipt. `bridge_paths` items carry
  bridge_q0_score cached once per distinct bridge (lock 2).
- NEW `tests/determinism/test_latent_eligibility.py` (15 tests).
- Register row 11.321; this work-log; scaffold TREE declarations.

## Proof
`UNIT_PROVEN` — executed path = the worktree copy. 11/11 green: DIRECT wins even over an invalid bridge;
COMPLEMENTARY when both links hold; **ANTI-HIJACK — an excellent local chunk (logit 6.0) on an invalid
bridge (logit −5.0) is INELIGIBLE** (the safety-critical property); local-subfloor rejected even with a
valid bridge; DIVERGENT eligible on the role hint + uses the stricter local floor; pure-q0 sub-floor →
INELIGIBLE; bridge_valid_floor + divergent_local_floor configurable; floor boundary is logit 0; the
"neither link compensates" 2×2 matrix (only valid+relevant is eligible); scores recorded + JSON-native.

## Rejected claims
- No new numeric threshold invented (bar = existing floor, config-driven). No fused/`max` scoring. C4
  makes NO seating decision (no slot caps here). Strong `origin↔chunk` cannot rescue a weak `q0↔bridge`.

## Open contract gaps
`contract_impact` = no impacted production contract (new isolated `shared/` module; no caller). Deferred:
C4-live (compute the two cross-encoder facts in the retrieval/selection path — bridge_q0 once per bridge,
origin_chunk per bridge candidate — reusing `_rerank_children`; attach the `LatentEligibility` to each
candidate) + C5 (portfolio seating: DIRECT dominant; COMPLEMENTARY bounded; DIVERGENT ≤2 only atop
adequate DIRECT grounding via CA4 direct-coverage, capacity 0 without DIRECT; extend CA4 grade_evidence)
+ C6 (record the calibration row: bridge_q0/origin_chunk/q0_chunk/proposed_role/C4-state/C5-role/survived/
used). Proven live at C7.
