---
change_id: CORPUS-EXPLORER-V1-BUILD
owner: "@king"
date: 2026-09-19
status: in-progress
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

## Rejected claims
- NOT claimed: live activation stability (same NL q0 -> same concepts). CE1 proves BUILDER determinism
  only (identical retrieved atoms -> identical candidates); live/ANN stability is MEASURED in CE7.
- NOT claimed: any orchestrator/ui.py behavior (CE4, live-only).

## Open contract gaps
CE1-CE3 COMPLETE (shared, UNIT_PROVEN). Remaining: CE4 (ui.py gate + `LATENT_ORIGINS` C4/C5 routing +
per-request flag threaded through `_compile_chat_plan`; live-only), CE5 (flag-off equivalence), merge +
port-gated bounce, CE6/CE7 (live smoke + activation-reliability qualification), CE-UI (request field +
capabilities key + Chat.tsx toggle). Contract dispositions: `chat_plan.ORIGIN_TYPES` UPDATED (additive);
`ranked_fusion.lineage_class` UPDATED (CORPUS_EXPLORE→BRIDGE class); `bridge_integration.bridges_to_subqueries`
UPDATED (additive origin/id_prefix params, BRIDGE default unchanged) — all backward-compatible, existing
tests green.
