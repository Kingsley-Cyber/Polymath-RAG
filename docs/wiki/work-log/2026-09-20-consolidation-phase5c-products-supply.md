---
change_id: CONSOLIDATION-MIGRATION-PHASE5C-PRODUCTS-SUPPLY
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — three more operations behind the DOMAIN_OPERATION door and one behaviour-preserving extraction in the imported engine. No runtime, contract, manifest or Trail change. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 5c: product concepts, sourcing plan, supplier normalization and the lead join

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 5 "Products" (multiple concepts, multiple variations, mechanism / population / evidence links) and "Supply"
(sourcing plan, Alibaba, CJ, normalization, price parsing, MOQ parsing, lead assembly). `MIGRATION_POLICY.md` INV-3 / INV-5 and the standing rule "No LLM
or skill score touches a Trail score": the engine's own verdict and `evidence_score` are NOT carried into governed mode. Decision `AUTO_DECISIONS.md` M-010.

## Changes
- `adapters/ecommerce/python/executors.py` — the mechanism × supplier join that was inlined in `scoring()` is ONE function, `join_leads(mech, d, pol)`,
  carrying no score and no verdict; `scoring()` calls it and adds its own score exactly as before (engine suite 609 / 609).
- `adapters/ecommerce/binding.py`
  - `_ledger_hypotheses` — a θ step's stored output keeps the agent's proposals and, in parallel, the ledger ids the runtime minted; the binding zips
    them so every domain hypothesis is addressed by its LEDGER id. Used by `hypotheses.validate_bridge` and `population.evidence_cards` (friction family).
  - `_mechanisms` — a mechanism's `status` is DERIVED from the ledger (SUPPORTED only while its hypothesis is `proposed / retained / revised / split /
    strengthened / promoted`), never taken from the agent; ineligible ones are listed in `mechanism_notes`.
  - `products.validate_concepts` — engine concept schema + `ideation.validate_concepts` (3–6 distinct form factors, ≥ 2 distinct variations each, a
    SUPPORTED mechanism, admitted field evidence cited). Invalid is an OUTPUT.
  - `supply.plan` — `executors.sourcing_plan_compiler` (one job per concept per channel) and, when TrailSignal's supply directive is supplied, the same
    WHAT / HOW enrichment as `research.plan`, round-robin across concepts, within the query budget, overflow counted.
  - `supply.leads` — ADMITTED supply observations → supplier candidates (listing / supplier / price / MOQ / concept read from the observation context the
    engine's receipt builder writes) → `executors.supplier` (the engine's price / MOQ parsers, channel MOQ defaults marked as defaults, concept
    resolution, per-concept coverage) → `join_leads` for ledger-eligible mechanisms → `interleave_leads` → policy lead cap.
- Tests: `tests/determinism/test_adapter_ecommerce_products_supply.py` (7).

## Proof
- Portfolio law: one concept, a duplicated form factor ("Magnetic Belt-Clip" vs "magnetic belt clip"), a single variation, duplicate variations and an
  uncited / unknown evidence id are each refused with the engine's message; a lawful set of 3 concepts × 2 variations returns exactly valid.
- Ledger-derived support: a mechanism the agent CLAIMS is SUPPORTED but whose hypothesis is `weakened` is refused; a `contradicted` hypothesis yields
  candidates and coverage but NO lead.
- Parsers: `US$1.20-1.80 / piece` + `500 pieces` → 1.2 / 1.8 / 500; a CJ listing without MOQ gets 1 WITH `moq_note`; `¥8.5` and `1-10` → refuse to guess.
- Honesty pins: "unresolved" is not a supplier name (`supplier_name: null`, counted); a listing-less admission is counted; a concept with only unparsed
  candidates is `unparsed`, never covered by another concept's listing; leads carry NO `evidence_score`, the output has NO verdict.
- Sourcing plan: 6 jobs for 3 concepts × 2 channels; the enriched supply directive keeps governance, puts Trail's intent first, gives every concept one
  job before any gets its second, drops 2 over a budget of 5 and says so.
- Engine suite 609 / 609 after the extraction; all seam tests green; database-free; guards 0 / 0 / 0 / READY. `WORKTREE_INTEGRATION_PROVEN` per operation.

## Rejected claims
- "Supplier identity is fixed." The engine's Exa harvester still hard-codes the name as unresolved (`sourcing_exa.py:49`); governed mode now refuses to
  treat that as a name and counts it. Resolving names at harvest time is host-side work, not done.
- "Leads are qualified." They are a domain JOIN. TrailSignal's `opportunity.qualify` and `opportunity.score` decide.

## Open contract gaps
- `ADAPTER_RUNTIME` — NOT_AFFECTED. Receipt / admission contracts — TESTED_UNCHANGED (read only).
- The observation-context convention (`listing: … · supplier: … · price as listed: … · MOQ as listed: … · concept: …`) is the engine's receipt-builder
  format, not a contract. A structured supply observation in the receipt contract would be better; that is a Trail-side contract question (Phase 6 / 7).
