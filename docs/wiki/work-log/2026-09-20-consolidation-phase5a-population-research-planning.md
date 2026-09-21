---
change_id: CONSOLIDATION-MIGRATION-PHASE5A-POPULATION-RESEARCH-PLANNING
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — two more operations behind the DOMAIN_OPERATION door and an environment switch in the imported engine's registry loader. No runtime, contract, manifest or Trail change. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 5a: population discovery and research planning

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 5 "Population" + "Field research" (reconnect gaps, channel planning, source-specific queries, acquisition
directives; "do not improvise queries that existing planners already know how to compile"). Shape decided BEFORE coding: `AUTO_DECISIONS.md` M-009
(`production` `214e0e9`): population discovery becomes research PLANNING; TrailSignal says WHAT, the engine says HOW through the `research_directive`
key the runtime already reads; no runtime change; no Trail change.

## Changes
- `adapters/ecommerce/binding.py`
  - `population.nominate` — wraps `lived_world.nominate` + `rank_leads` + `eligible_leads`: leads from the seed signal, the populations and latent
    structures the agent read out of the knowledge, registry situations and prior field rows, each with compiled channel queries and a VOI; the batch is
    the top `batch_size` eligible leads. The engine's `queue` (status mutation + wall-clock stamps) is deliberately NOT used, so the output is a pure
    function of its inputs.
  - `research.plan` — re-emits TrailSignal's `research_directive`: every governance field untouched, every Trail intent first and unmodified, then
    channel-specific intents compiled by `executors.channel_queries` from the evidence gaps (else the live hypothesis statements) and the top population
    leads. A channel serves an intent only when the roles it yields (the ONE static `adapter_receipt.ROLE_MAP`) overlap the roles Trail asked for.
    Bounded by the directive's `budget.max_queries`; what did not fit is COUNTED (`dropped_over_budget`), what no intent could host is counted too.
  - the binding sets `OPPORTUNITY_RESEARCH_REGISTRY=compile`.
- `adapters/ecommerce/python/registry.py` — with that variable set, `load_snapshot()` compiles from the CSVs in memory (~80 ms) and never reads or
  writes `registry/compiled/`. Standalone behaviour (variable unset) is unchanged.
- Tests: `tests/determinism/test_adapter_ecommerce_population_research.py` (6), fixture manifest `fixture.research_planning.json` (its hypothesis,
  registry-projection, gap-compilation and harness steps are COPIED from `trail.product_discovery.json`, so the runtime path is the product's).

## Proof
- GATE — `test_the_existing_runtime_hands_the_enriched_directive_to_the_harness`: knowledge → θ hypotheses (the real ledger) → `registry.project` →
  `gaps.compile` (stub TrailSignal over `httpx.MockTransport`, the production `TrailMCPClient`) → `research.plan` → `HARNESS_ACTION`. The issued
  `HarnessActionV1` validates against its contract, carries TrailSignal's two intents first and the engine's channel intents after, keeps the manifest's
  harness budget, freshness (14 d), minimum independent sources (3) and disallowed roles, and its `evidence_gaps` hash equals TrailSignal's. Receipt
  accepted; run `completed`. `service.py` untouched.
- Population: all four lanes present incl. a LATENT lead (a population nobody named, searched by its friction language); every lead carries channel
  queries and a VOI; ranking is VOI-descending; two runs are equal (no clock, no cache); the registry build cache's mtime is unchanged.
- Smoke against the REAL directive of the first governed run (`r2a_cinema_smoke/action_I_research.json`, read-only): 11 TrailSignal intents with
  unfilled `{activity} {task}` templates kept, 13 compiled channel intents added, 22 counted as over budget, governance unchanged.
- Engine suite 609 / 609 + `doctor` after the `registry.py` edit; seam + intake + population + neutrality tests 40 green; database-free. Guards 0/0/0/READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN` with a stub TrailSignal. NOT proven against the live Trail daemon or a live harness.

## Rejected claims
- "Defect D6 (generic templates) is fixed." TrailSignal's own intents are still generic and still occupy budget slots first; the engine's compiled
  intents are ADDED. Whether Trail's unfilled templates should yield their slots is a Trail-side question (Phase 7), not decided here.
- "Population scouting is restored." Nomination, ranking and query compilation are. Instantiation from admitted observations (evidence cards, lived
  clusters, lived situations) is the next slice.
- "The registry is one authority." The engine still compiles ITS copy; TrailSignal's snapshot is the governance authority. Phase 7.

## Open contract gaps
- `ADAPTER_RUNTIME` — NOT_AFFECTED (no runtime file changed in this slice).
- `HARNESS_ACTION` contract — TESTED_UNCHANGED (the enriched action validates; only `search_intents` grows, within `maxItems` and the item schema).
- Trail wire — TESTED_UNCHANGED at the client boundary (the stub answers the production client); live Trail NOT exercised.
