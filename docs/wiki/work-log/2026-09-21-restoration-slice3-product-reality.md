---
change_id: RESTORATION-SLICE-3-PRODUCT-REALITY
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "Engine (adapters/ecommerce) gains the product-reality pair the supply lane already had: product_reality.plan (per-concept research jobs bound from the concept's market vocabulary) and product_reality.join (existing products linked to a concept by the explicit concept tag). Manifest ecommerce.product_research 0.4.0 adds two DOMAIN_OPERATION steps, O_plan and Q_join; no stage is moved or removed. No shared/, workers/, contract, Trail or receipt-schema change. Not merged, not deployed."
last_reviewed: 2026-09-21
---

# Restoration Slice 3 — product-reality fidelity (reference §10)

## Contract
Owner build reference §10, exit §10.6: two concepts → distinct per-concept jobs compiled from `product_terms` / concept / mechanism vocabulary; competitors join to the right concept; one concept can be contradicted without the other. Stage ORDER unchanged (§10.1); reuse the `supply.plan` / `supply.leads` pattern (§5.13); no new product engine (§6). Branch `restoration/product-reality` (worktree `../pmv4-product-reality`) STACKED on Slice 2 `4bcf17d`.

## Changes
- NEW `adapters/ecommerce/python/product_reality.py` (pure). `plan`: per concept → `market_phrase` = form factor (what separates sibling concepts under one mechanism) + the mechanism's first `product_terms` entry; jobs = one guaranteed `direct` competitor search · TrailSignal's stage templates bound with that phrase as `{product_territory}` and the hypothesis's `{activity}` · one `direct_competitor` job per variation (variation id = `<concept_id>.v<n>`, delta D-c) · ONE `substitute` job per hypothesis (how the physical JOB is solved today; `applies_to_concepts` names the siblings). Every job carries `concept_id, variation_id, hypothesis_id, mechanism_id, job_class, query`; the job id IS the intent id the harness receives. `join`: admitted observations → `existing_products[]` linked ONLY through the `concept:` tag the job asked for (the supply lane's convention) — no tag or an unknown concept → `unjoined` with a reason, never inferred from a name; `relation: competitor | substitute | current_solution | validates | solves`; a product marked `solves`, or admitted by TrailSignal as contradicting, CONTESTS that one concept → `concept_reality[].status` ∈ `EXISTING_PRODUCT_CONTESTS | EXISTING_PRODUCTS_FOUND | NO_EXISTING_PRODUCT_JOINED | NOT_RESEARCHED`. No score, no verdict (`authority: DOMAIN_JOIN_ONLY`).
- `query_semantics.bind_template(..., overrides=)`: a caller-compiled slot value (the concept's market phrase).
- `binding.py`: operations `product_reality.plan` / `product_reality.join` (typed refusals `REALITY_DIRECTIVE_MISSING`, `PRODUCT_CONCEPTS_MISSING`, `REALITY_PLAN_UNBOUND`); governance fields untouched (`governance_unchanged`), TrailSignal's slot-free intents kept first, round-robin per concept inside TrailSignal's query budget, what did not fit is counted.
- Manifest 0.4.0: `O_territory → O_plan → P_reality → Q_admit → Q_join → R_qualify` (56 steps). `O_plan` reads `context.semantics.product_reality` (Slice 1's projection); `P_reality` is shown `reality_plan`, `mechanisms`, `planned` and its objective states the tag convention; `W_interpret` is shown `existing_products` + `concept_reality` and told a contested concept is not an open opportunity; `X_compile.include` += `existing_products`, `concept_reality`, `reality_plan`.
- Tests: NEW `tests/determinism/test_adapter_product_reality.py` (8; fixture = run 5's real product stage and the vocabulary it never searched). `test_adapter_ecommerce_product_research_e2e.py`: the pinned list of domain steps gains `O_plan`, `Q_join`; the scripted harness records the concept tag; new assertions on per-concept intents and the join.

## Proof
EXECUTED in the worktree, no database, no network: new file 8 / 8 (binding run OUT OF PROCESS through its own protocol); DB-free adapter suites + Slices 1–2 = 229 / 229 (includes the scripted full ecommerce run through the 56-step manifest with a fake TrailSignal); engine suite 609 / 609 (Hermes venv, temp loop DB). UNIT_PROVEN + WORKTREE_INTEGRATION_PROVEN for the engine. Run-5 contrast (HISTORICAL → fixture): the run received `{activity} {product_territory} review problem` ×4 unbound and joined nothing; the same directive now yields `hiking photography strap clamp mount backpack camera clip review problem` for `pc_1` and a different query for its sibling `pc_2`, and `PGYTECH … relation: solves` contests `pc_1` only. Guards 0 / 0 / 0 / READY.

## Rejected claims
- "Stage order changed." Two steps were ADDED between existing ones; `N_concepts` still precedes `P_reality`.
- "The join decides a concept is dead." It reports `EXISTING_PRODUCT_CONTESTS` with the evidence ids; qualification and the score stay TrailSignal's, interpretation stays `W_interpret`'s.
- "Territory ids are now resolved." They are not used: the query vocabulary is the run's own `product_terms`; the territory NAME is Slice 4's to return.
- "Hypothesis-relative contradiction exists." Only at concept level through the tag convention; the receipt / admission relation is Slice 4 (all four copies).

## Open contract gaps
- ADAPTER_RUNTIME: TESTED_UNCHANGED (no `shared/` or `workers/` change; the manifest is a product adapter's config). MCP_SURFACE: NOT_AFFECTED.
- DEPLOYED SKILL COPY: engine files changed (`binding.py`, `query_semantics.py`, new `product_reality.py`) → `scripts/deploy_ecommerce_skill.py` after the merge; `SKILL.md` should teach the `concept:` / `relation:` convention for product reality at that point (the step objective already does for governed runs).
- Owed live: L9 `O_plan.reality_plan` has ≥ 1 job per concept and zero `{`; L10 a `P_reality` receipt with concept tags → `Q_join.joined.joined > 0`; L11 `W_interpret` materials carry `concept_reality`.
- `R_qualify` still counts per hypothesis (TrailSignal's); feeding concept-level contests into qualification is a Trail-side question, not decided here.
