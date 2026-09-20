---
change_id: CORPUS-EXPLORER-V1-BUILD
owner: "@king"
date: 2026-09-19
status: complete
architecture_impact: "Living build log for CORPUS-EXPLORER-V1 CE1->CE-UI. NEW non-generative concept-keyed corpus-activation path (shared, pure) feeding the EXISTING WLK2C bridge compiler under a distinct CORPUS_EXPLORE origin, two-layer gated. Additive + fail-open + flag-gated; flag-off = pre-feature-equivalent V2. Updated per phase."
last_reviewed: 2026-09-19
---

## Contract
Execute CORPUS-EXPLORER-V1 per `docs/wiki/plans/CORPUS-EXPLORER-V1.md` (admitted, register 11.335) with
the LOCKED DESIGN: reuse WLK2C bridge machinery unchanged; NEW = a non-generative concept path from
CONCEPT/THEORY atoms via `search_atoms`, INDEPENDENT of Scout; distinct origin `CORPUS_EXPLORE` mapped to
the existing BRIDGE fusion class/weight (no new tunable); two-layer gate (capability
`POLYMATH_CORPUS_EXPLORER` x per-request `corpus_explorer` x `not plan.fallback`); flag-off =
pre-feature-equivalent V2. shared/ is unit-provable in the worktree; ui.py is live-only (editable-.pth).

## Changes
- **CE1 (activation contract, shared, pure).** NEW `shared/polymath_shared/corpus_activation.py`:
  `ActivationCandidate` (concept_id/concept/source_document_ids/evidence_types/score/provenance) +
  `build_activation_candidates(atom_hits, *, scout_nominations=None, max_activations, min_grounding, rrf_k)`
  (pure aggregation of CONCEPT/THEORY atom hits; RRF over global atom rank; Scout = optional additive
  corroboration only) + `activate_corpus(*, corpus_ids, fetch_atoms, ...)` (fail-open live loop over an
  injected fetch closure) + `activation_receipt`. `CONCEPT_ATOM_KINDS=("CONCEPT","THEORY")`.
- **CE3 (origin + lineage + fusion, shared).** `chat_plan.ORIGIN_TYPES` += `"CORPUS_EXPLORE"` (MUST-FIX —
  else `__post_init__` coerces to USER). `ranked_fusion.lineage_class`: `CORPUS_EXPLORE` → the EXISTING
  `CLASS_BRIDGE` (same weight; no new tunable). `bridge_integration.bridges_to_subqueries` gains
  `origin="BRIDGE"` + `id_prefix="br"` params (backward-compatible defaults → BRIDGE path byte-identical).
- **CE2 (explorer expansion, shared, pure).** NEW `shared/polymath_shared/corpus_explore.py`:
  `activations_to_concepts` (ActivationCandidate → bridge_compiler.Concept) + `plan_corpus_explore_expansion`
  (reuses `compiler_eligible`/`compile_bridges`/`parse_and_validate`; emits origin=CORPUS_EXPLORE, id_prefix
  `ce`; text-dedups; `_stash` receipt `corpus_explore_expansion`). NOT a second compiler — same machinery,
  concept-level grounding, distinct origin.
- **CE4 (gate + routing, ui.py — live-only).** `StreamChatRequest.corpus_explorer: bool = False`;
  `_compile_chat_plan` gains kw-only `corpus_explorer` threaded from the single call site
  (`req.corpus_explorer`, ThreadPool submit-time). NEW `_add_corpus_explore_expansion(plan, message,
  corpus_ids, scout_result, *, enabled)` runs LAST in `_finish` (after annotate, so activation
  `inspired_by_profile` survives): two-layer gate (capability `POLYMATH_CORPUS_EXPLORER` x per-request
  `enabled` x `not plan.fallback`), embeds q0 + `search_atoms(CONCEPT/THEORY)` -> `activate_corpus` ->
  `plan_corpus_explore_expansion` with the REUSED gemma bridge closure; fail-open; stashes
  `corpus_activation` + `corpus_explore_expansion` receipts. `LATENT_ORIGINS=("BRIDGE","CORPUS_EXPLORE")`
  widens the two `=="BRIDGE"` latent filters (C4 grading dict + `latent_bridge_ids`).
- **CE-UI (additive, off critical path).** `capabilities.py` advertises a dynamic `"corpus-explorer"` key
  (reflects the env flag) so the UI hides/disables when off. `frontend-v2/src/screens/Chat.tsx`: a boolean
  "Corpus Explore" toggle (capability-gated visibility) that sets `body.corpus_explorer`. `.env.example`
  documents `POLYMATH_CORPUS_EXPLORER` + bounds.

## Proof
- **CE1 UNIT_PROVEN** (executed path = worktree copy, verified: `import polymath_shared.corpus_activation`
  -> `pmv4-explorer/shared/...`). `tests/determinism/test_corpus_activation.py` 10/10 green:
  builder determinism (input order irrelevant, exact); **Scout-independence (scout=None + real atoms ->
  valid ActivationCandidate[] -> concepts produced)**; cross-doc concept aggregation + provenance; Scout
  corroboration additive-only (same concept set, tagged + slightly higher score, non-corroborated
  unchanged); min_grounding filter; max_activations bound; sort determinism; malformed hits skipped;
  activate_corpus fail-open per corpus; receipt shape.
- **CE2/CE3 UNIT_PROVEN** (executed path = worktree; import sources verified). `test_corpus_explore.py`
  13/13 + backward-compat GREEN (bridge_integration + bridge_compiler + ranked_fusion unchanged; 53 total),
  plus affected-module regression GREEN (subquery_provenance/ranked_lane/candidate_engine/latent_fusion_seam/
  latent_selection, 83). Pins: **origin registered not coerced** (`CompiledQuery(origin="CORPUS_EXPLORE")`
  survives); CORPUS_EXPLORE → CLASS_BRIDGE; expansion appends `ce*` subqueries (q0 untouched, receipt
  stashed); factual intent + no-primary + no-concepts skip the compiler (generate NOT called); invented
  derived_from dropped (inherited anti-invention); fail-open when generate raises; text-dedup;
  **coexists with Scout BRIDGE with no id collision** (br* vs ce*, both origins present, q0 primary).
- **CE2/CE3 contract-impact closure:** pre-commit flagged QUERY_PLANNER (`chat_plan.ORIGIN_TYPES`) +
  SUBQUERY_PROVENANCE (additive). Ran the full impacted set — determinism 106 GREEN (candidate_engine,
  chat_funnel, chat_retrieval_v2, evidence_resolution, profile_yield, projection_manifest_writer,
  subquery_provenance). Dispositions: QUERY_PLANNER UPDATED (additive origin) · SUBQUERY_PROVENANCE
  TESTED_UNCHANGED · transitive (ACCEPTANCE/CANDIDATE_ENGINE/PROFILE_YIELD_RECEIPT/RESOLUTION_STATE/
  RETRIEVAL_RECEIPT) TESTED_UNCHANGED. `tests/integration/test_cross_domain_routing.py` = pre-existing
  worktree COLLECTION error (`import orchestrator.orchestrator` under editable-.pth; identical at the
  checkpoint tag) → deferred to live proof after merge.
- **CE4/CE-UI IMPLEMENTED, live-only** (editable-.pth: `orchestrator` resolves to MAIN under pytest, so
  ui.py is not worktree-unit-provable). `py_compile` ui.py OK; `agent_preflight`=0.
- **DEPLOYED (merge `e84d7cc` → production; port-gated bounce).** Deployed shared code re-proven on MAIN
  (import source = MAIN; 103 determinism tests green incl. the new `test_corpus_explore_origin_flows_into_
  lane_provenance` closing the RankedLane leg, and `test_corpus_ablation_removes_the_family`). Fleet: one
  bundle `99f6c44e6f33`, 22 healthy workers, `/ready` true; orchestrator process env carries
  `POLYMATH_CORPUS_EXPLORER=1` (+ V2 flags). Frontend built clean (`npm run build`, /v2 dist).
- **CE5 flag-off equivalence — LIVE_PATH_PROVEN.** With `corpus_explorer` omitted (capability on): receipt
  `corpus_activation`=null, `corpus_explore_expansion`=null, origins = USER/PROFILE/**BRIDGE** only (bridge
  path intact, added 3) — pre-feature-equivalent V2. No CORPUS_EXPLORE work/receipts/model calls.
- **CE5/CE6 + LIVE SEAM (DoD) — LIVE_PATH_PROVEN.** Flag-on (wc07 "silent authority"): q0 → **8 concept
  ActivationCandidates** (CONCEPT/THEORY atoms + Scout corroboration, source_document_ids present) → **4
  CORPUS_EXPLORE subqueries** (`ce0-3`, target=concept, derived_from clean, 0 invented) coexisting with
  BRIDGE (`br*`, no id collision) → RankedLane (origin carried — unit-closed) → CA4 (RELATED bucket). The
  WLK2C latent second-pass receipt is null because V2 fusion (on) preserves candidates upstream (empty
  rescue pool) — pre-existing, not a defect.
- **CE7 activation-reliability (`CE7-ACTIVATION-RELIABILITY-2026-09-19.json`, 18 live FAST, budget-bounded;
  see `analysis_corrected`).** Honest firing-aware verdict: **firing 14/18 (0.778)**; **content stability
  when fired = 1.0** (identical q0 → byte-identical concept set); paraphrase stability 0.318 mean (related
  neighborhoods, not keyword-locked); **negative-control leakage 0.143** (birthday) / none (cooking,
  vacation activated nothing — clean); provenance complete on all fired; target eligibility 0.917. Caveat:
  2 on-target runs produced no activation (firing consistency ~78%; a run-to-run FIRING gap from empty
  `search_atoms`/intent nondeterminism — content is stable when it fires). NOT tuned. (The raw headline
  `same_query_stability=0.333`/`leakage=1.0` were empty-set-Jaccard artifacts, corrected offline + the
  metric fixed in-harness.)
- **Safety sentinel (`CE-SAFETY-SENTINEL-2026-09-19.json`, feature ON, 9-query scoped subset).**
  unsupported-hallucination **0**, q0_preserved failures **0**, provenance-incomplete **0**. One supported
  gold-miss (pmap_savecat, HYBRID) is on a feature-INERT query (`ce_added=0`) and a re-probe is
  flag-off==flag-on → pre-existing HYBRID retrieval variance, **not a CORPUS-EXPLORER regression**
  (`regression_verdict.material_regression_vs_v2=false`).

## LEVEL-VERDICT (the one V1 architecture question)
**Does non-generative concept-keyed corpus activation reliably expose useful corpus neighborhoods the
document-level Scout→BRIDGE path does not?** ANSWER (with data): **Architecture VALIDATED + SAFE, activation
content DETERMINISTIC-when-fired, with a measured FIRING-consistency caveat.** It is a genuine second,
Scout-independent grounding source (CE1 independence proven); it activates concept neighborhoods live
(14/18), content-identical on repeats, provenance-complete, clean on negative controls, and rides the
existing C4/C5/CA4 spine with zero safety regression. It is NOT yet a *reliability* win end-to-end: firing
consistency is ~78% (empty `search_atoms`/intent nondeterminism), so run-to-run it sometimes activates
nothing. That is the identified follow-up (harden firing: retry/warm atom search, stabilize intent) — a V2
enrichment, NOT a V1 blocker: the feature is opt-in, two-layer-gated, fail-open, and provably safe.

## Rejected claims
- NOT claimed: end-to-end run-to-run activation RELIABILITY. Measured firing 14/18 (0.778); content is
  stable when fired (1.0) but firing itself is inconsistent. Reported honestly; NOT tuned to pass.
- NOT claimed: CORPUS_EXPLORER caused the pmap_savecat gold-miss (feature inert there; flag-off==flag-on).
- REJECTED (my own harness artifact): `same_query_stability=0.333`/`negative_leakage=1.0` — empty-set
  Jaccard scored 1.0; corrected to firing-aware metrics (content stability 1.0, leakage 0.143).
- NOT claimed: live activation stability (same NL q0 -> same concepts). CE1 proves BUILDER determinism
  only (identical retrieved atoms -> identical candidates); live/ANN stability is MEASURED in CE7.
- NOT claimed: any orchestrator/ui.py behavior (CE4, live-only).

## Open contract gaps
CE0-CE7 + CE-UI COMPLETE + DEPLOYED + LIVE-PROVEN (merge `e84d7cc`, bundle `99f6c44e6f33`). Contract
dispositions (all backward-compatible, existing tests green + live-verified): `chat_plan.ORIGIN_TYPES`
UPDATED (additive `CORPUS_EXPLORE`); `ranked_fusion.lineage_class` UPDATED (→BRIDGE class, no new weight);
`bridge_integration.bridges_to_subqueries` UPDATED (additive origin/id_prefix, BRIDGE default byte-identical);
QUERY_PLANNER/SUBQUERY_PROVENANCE/PROFILE_SCOUT_WIRING UPDATED (additive, live-proven); consumers
(ACCEPTANCE/CANDIDATE_ENGINE/RETRIEVAL_RECEIPT/PROFILE_YIELD/RESOLUTION_STATE) TESTED_UNCHANGED.
FOLLOW-UP (V2, not a V1 blocker): harden activation FIRING consistency (~78% → higher): retry/warm
`search_atoms`, stabilize intent classification; then re-measure paraphrase/same-query reliability.
Deferred (out of V1 scope, unchanged): parent-map/entity-card/graph activation signals.
REVERSIBLE: `POLYMATH_CORPUS_EXPLORER=0` + bounce → pre-feature V2 (the CE5 flag-off smoke IS this behavior;
capability=0 returns even earlier). End state: capability ON (safe — inert unless the per-request toggle is set).
