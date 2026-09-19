---
change_id: WLK2C-C3-BRIDGE-INTEGRATION
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C3 pure core (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure `shared/polymath_shared/bridge_integration.py`: turns admitted concept-bridges into BRIDGE-origin subqueries on the compiled plan (mirrors PROFILE-EXPANSION-V1) under the tiered policy — tier-1 reuse (a concept already covered by a C1-admissible existing subquery is NOT re-compiled) then the bounded compiler (injected `generate`) for the uncovered concepts, only when the plan's INTENT permits latent expansion. `chat_plan.ORIGIN_TYPES` extended with BRIDGE + WILDCARD (additive) so a bridge subquery keeps origin=BRIDGE. C2 `LATENT_INTENTS` corrected to the real query_intent vocabulary (SYNTHESIS/APPLICATION/EXPLORATORY/RELATIONSHIP) discovered during integration. Additive: q0 + existing subqueries untouched; a plan with no PRIMARY gets no expansion (q0 authority). The live gemma call + this function's invocation are the C3-live wiring (orchestrator, flag-gated, proven at C7)."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C3 (plan-of-record step 3–4): carry lineage end-to-end + retrieve/deepen against origin_query.
This slice lands the pure integration that converts admitted bridges into BRIDGE-origin subqueries and
appends them to the plan (so they run their retrieval lanes like any subquery — the "deepen against
origin_query" is the existing subquery machinery). The live gemma `generate` closure + the ui.py
invocation (`_add_bridge_expansion`) are C3-live (live-only proof at C7). Eligibility is INTENT-based,
never mode-based (owner lock).

## Changes
- NEW `shared/polymath_shared/bridge_integration.py` (pure except injected `generate`):
  `concepts_from_nominations(noms)` (scout noms → grounded `Concept{key=doc_id,label,source}`);
  `covered_concept_keys(plan_queries, root)` (tier-1 reuse — concept keys covered by a C1-admissible
  existing subquery via its inspired_by_profile); `bridges_to_subqueries(bridges, concepts)` (admitted
  `CompiledBridge` → BRIDGE-origin `CompiledQuery` with full lineage: origin=BRIDGE, role=bridge,
  inspired_by_profile=[concept source], target=concept key, reason naming the concept + relation_to_q0);
  `plan_bridge_expansion(plan, nominations, *, generate)` (build concepts → subtract covered → INTENT
  eligibility → compile the uncovered → dedup → append; additive; never raises; diag on plan.compiler).
- `shared/polymath_shared/chat_plan.py`: `ORIGIN_TYPES += ("BRIDGE", "WILDCARD")` (additive — a bridge
  subquery's origin is no longer sanitized to USER).
- `shared/polymath_shared/bridge_compiler.py`: `LATENT_INTENTS` corrected to the real classify_intent
  vocabulary — `("SYNTHESIS","APPLICATION","EXPLORATORY","RELATIONSHIP")` (was placeholder strings);
  factual EXACT/DEFINITION/MECHANISM/COMPARISON/PROCEDURE/RECALL deliberately excluded.
- NEW `tests/determinism/test_bridge_integration.py` (10 tests); `test_bridge_compiler.py` intents updated.
- Register row 11.319; this work-log; scaffold TREE declarations.

## Proof
`UNIT_PROVEN` — executed path = the worktree copy. C3 10/10 + C2 12/12 + C0/C1 22/22 green; the touched
`chat_plan` ORIGIN_TYPES verified safe by `test_subquery_provenance` (17) + `test_chat_compiler` (14)
green. Pins: scout noms → concepts; tier-1 reuse covers an admissible existing subquery's concept (a
paraphrase subquery does NOT cover); admitted bridge → BRIDGE-origin subquery carrying lineage
(origin survives); expansion appends a bridge subquery while q0 + existing subqueries stay untouched; a
factual (DEFINITION) intent skips the compiler entirely (no call); no PRIMARY → no expansion; all
concepts covered → skip; an invented bridge adds nothing; dedup vs existing.

## Rejected claims
- No live behavior change (no caller yet — `plan_bridge_expansion` is not invoked in the orchestrator
  until C3-live). Eligibility is NOT mode-based (a creative FAST query is eligible; a factual WILDCARD
  query is not) — enforced by keying on plan.intent.

## Open contract gaps
`contract_impact` (chat_plan.py touches QUERY_PLANNER + SUBQUERY_PROVENANCE; transitive: ACCEPTANCE,
CANDIDATE_ENGINE, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, RETRIEVAL_RECEIPT) — the change is an ADDITIVE
enum extension (two new `ORIGIN_TYPES` values, no existing path emits them yet), so every impacted
contract is **TESTED_UNCHANGED**: 101 determinism tests green (test_candidate_engine, test_chat_funnel,
test_chat_retrieval_v2, test_evidence_resolution, test_profile_yield, test_projection_manifest_writer,
test_subquery_provenance + chat_compiler). `tests/integration/test_cross_domain_routing.py` skips offline
(needs the live fleet) → **DEFERRED** to the C7 live qualification. `bridge_integration` is a new
isolated module (no impacted contract). LIVE
WIRING deferred to C3-live: `_add_bridge_expansion(plan, scout_result)` in `ui.py._compile_chat_plan.
_finish` (after profile expansion), building the ONE low-temp cloud-Gemma JSON `generate` closure
(chat catalog), flag `POLYMATH_CHAT_BRIDGE_COMPILER` default-off, run once after Scout nominations
exist. Then C4 (semantic bridge↔q0 + chunk↔origin_query rerank) + C5 (authoritative roles). Proven live
at C7 (merge + port-gated bounce + CA5 qual).
