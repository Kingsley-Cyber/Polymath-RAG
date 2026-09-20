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

## Proof
- **CE1 UNIT_PROVEN** (executed path = worktree copy, verified: `import polymath_shared.corpus_activation`
  -> `pmv4-explorer/shared/...`). `tests/determinism/test_corpus_activation.py` 10/10 green:
  builder determinism (input order irrelevant, exact); **Scout-independence (scout=None + real atoms ->
  valid ActivationCandidate[] -> concepts produced)**; cross-doc concept aggregation + provenance; Scout
  corroboration additive-only (same concept set, tagged + slightly higher score, non-corroborated
  unchanged); min_grounding filter; max_activations bound; sort determinism; malformed hits skipped;
  activate_corpus fail-open per corpus; receipt shape.

## Rejected claims
- NOT claimed: live activation stability (same NL q0 -> same concepts). CE1 proves BUILDER determinism
  only (identical retrieved atoms -> identical candidates); live/ANN stability is MEASURED in CE7.
- NOT claimed: any orchestrator/ui.py behavior (CE4, live-only).

## Open contract gaps
CE2 (explorer expansion reusing compile_bridges under origin=CORPUS_EXPLORE), CE3 (ORIGIN_TYPES +
lineage_class + bridges_to_subqueries origin param), CE4 (ui.py gate + LATENT_ORIGINS routing + request
flag), CE5 (flag-off equivalence), CE6/CE7 (live smoke + activation-reliability qualification), CE-UI.
