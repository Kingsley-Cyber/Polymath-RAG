---
change_id: CONSOLIDATION-MIGRATION-PHASE8-GOVERNED-DOSSIER
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — the imported engine's existing report mapping and renderer are extended; no runtime, contract, manifest or Trail change. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 8: the governed dossier

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 8: reuse the existing AutoResearch renderer; do not build another; expand the governed ReportModel / input mapping; clearly distinguish POLYMATH
KNOWLEDGE, LIVE-WORLD OBSERVATION, AGENT INFERENCE, TRAIL DETERMINATION, TRAIL REGISTRY. Gate: a fixture-driven report renders the complete product-oriented structure. Decision `AUTO_DECISIONS.md` M-013.

## Changes
- `adapters/ecommerce/python/report.py`
  - `build_model_from_governed` (the TG4 mapping from a governed-run JOURNAL) now prefers what `ecommerce.product_research` really returns: the typed `product_concepts` with their variations
    (instead of ONE concept synthesized from `product_opportunity`), the domain's supplier JOIN (`leads`: concept, mechanism, supplier name or "not named on the listing", parsed price / MOQ,
    the role TrailSignal admitted it under — instead of leads re-derived from receipt metrics), `sourcing_coverage`, and — in the governed block — `mechanisms`, `lived_situations`,
    `lived_clusters`, `population_leads`, `lenses`, `corpus_questions` and the `registry_snapshot` the run was decided against. For the older adapter's result the previous behaviour is unchanged.
  - Rendering: a new `_render_lived_world` (populations worth looking at · lived clusters · lived situations) and an `AUTHORITY` badge on every governed block — registry snapshot (TRAIL
    REGISTRY), TrailSignal's record (TRAIL DETERMINATION), reasoning bridge (AGENT INFERENCE + TRAIL DETERMINATION), field observations and lived clusters (LIVE-WORLD OBSERVATION + TRAIL
    DETERMINATION), populations (AGENT INFERENCE + TRAIL REGISTRY), lived situations and product directions (AGENT INFERENCE), corpus evidence packets (POLYMATH KNOWLEDGE). In governed mode
    "Qualified Leads" is titled "Supplier Leads" and says a lead is not a qualification.
- The renderer stays HOST-SIDE, as in TG4: the host keeps the journal (`governed_run.py`) and runs `governed_run.py report`. No domain operation renders or writes a file (M-013).
- Tests: `tests/determinism/test_adapter_ecommerce_dossier.py` (2). The scripted knowledge executor now stores the real evidence-boundary output shape, so knowledge packets appear in the journal.

## Proof
- A complete scripted run is journaled exactly as `governed_run.py` documents (every `adapter_next` payload, every submission with the adapter's answer, the result) and rendered OUT OF PROCESS
  through the engine's own CLI. The dossier carries all five authority labels; 3 product directions each with 2 variations; the third honestly `UNSOURCED`; 2 supplier leads with `$1.2 / unit`,
  `MOQ 500`, a named supplier and one "supplier not named on the listing"; lived clusters (ANCHOR), lived situations (FIELD_ANCHORED) and population leads; TrailSignal's score record and its
  two refusals verbatim; the registry snapshot id; and NO "evidence score" anywhere.
- A run the portfolio law refused renders as a refusal: the typed gap, no leads, no score.
- Against the REAL embedded TrailSignal core (ad hoc, under TrailSignal's interpreter): verdict `GOVERNED — TRAIL REFUSED TO SCORE`, 15 admitted observations, rejections by reason
  `SOURCE_UNREGISTERED × 1` / `SOURCE_ROLE_UNSUITABLE × 2`, three `HARD_GATE_UNMET` refusals, all three concepts `unsourced`, all five labels present.
- Engine suite 609 / 609 + `doctor` after the report changes; end-to-end, seam, neutrality and provenance tests green; database-free. Guards 0 / 0 / 0 / READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN` on scripted runs. No real evidence has been rendered.

## Rejected claims
- "The dossier is the owner's confirmed specification." The earlier dossier specification was never confirmed by the owner and stays UNCONFIRMED; this renders the structure the plan lists.
- "Reviews, comments and product links of competing products are shown." Product-reality observations appear as admitted / rejected field observations; a dedicated competing-products block
  does not exist yet.

## Open contract gaps
- `ADAPTER_RUNTIME`, `MCP_SURFACE` — NOT_AFFECTED. The journal drops the `materials` sibling key (it stores the step and its readable evidence) — sufficient for the report; noted, not changed.
