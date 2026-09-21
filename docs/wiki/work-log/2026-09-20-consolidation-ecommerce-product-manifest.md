---
change_id: CONSOLIDATION-MIGRATION-ECOMMERCE-PRODUCT-MANIFEST
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "ADR-0020 addendum: `service.next_step` may return a sibling `materials` key (prior step outputs a manifest chose to SHOW an agent-answered step); a knowledge step's `config.source` may name a prior step output. New product manifest `config/adapters/ecommerce.product_research.json`. `shared/` + `workers/` change on branch `migration/ecommerce-consolidation` only — NOT merged, live fleet untouched, a bounce is needed at merge."
last_reviewed: 2026-09-20
---

# Consolidation migration — the ecommerce product manifest and one complete run through the existing runtime

## Contract
`docs/migration/EXECUTION_PLAN.md` Phases 5 (compose the restored intelligence) and 11 rungs E (mechanical governed smoke — "no expensive open-world research until internal
contracts work") and G (negative control), in TEST form. `AUTO_DECISIONS.md` M-009 §5 (a NEW manifest; `trail.product_discovery.json` is not edited) and M-011.

## Changes
- `config/adapters/ecommerce.product_research.json` (v0.1.0, 53 steps) — GENERATED from `trail.product_discovery.json`: its 28 steps are copied unchanged in content (Trail operations, harness
  blocks, θ steps, budgets as a floor, `evidence_roles`, `X_compile`), and the domain is inserted in the M-009 shape: 16 `DOMAIN_OPERATION` steps, 5 more `AGENT_REASON` steps (primitives,
  bridges, lived situations, product concepts + the existing ones), 4 law `BRANCH`es that return a failed draft through reasoning and, once the repair budget is spent, route to a
  `law.refuse` step (typed gap carrying the law's own errors), and a post-admission knowledge step whose need is the domain's field-grounded corpus questions. The evidence loop is bounded
  by the research ROUND the cards operation counts (the shared `branch_loops` counter would let law repairs starve it). No source, search engine, browser or harness is named.
- `shared/polymath_shared/adapter/service.py` — `next_step` adds a sibling `materials` key when the manifest step declares `config.show` (ADR-0020 addendum). `manifest.py` validates
  `config.show` (agent-answered steps only; dotted paths under `outputs.` / `input.`).
- `workers/workers/adapter_step_worker.py` — `_query_text`: `config.source` may name a prior step output.
- `adapters/ecommerce/binding.py` — `law.refuse`; an empty admission is an OUTPUT (no card / no lead — TrailSignal still judges), research rounds accumulate (`prior_field_records`,
  `round`), hop refs are checked against the run's own rows, `supply.plan` with `require_directive` refuses `SUPPLY_DIRECTIVE_MISSING` instead of letting supplier research run under an
  older stage's directive (external-review finding M1-07), `research.plan` accepts the two lead lists.
- Tests: `tests/determinism/test_adapter_ecommerce_product_research_e2e.py` (3); the Phase 3 compatibility pin now names the three pre-existing adapters.

## Proof
- COMPLETE RUN — `test_one_complete_ecommerce_product_research_run`: `service.start / advance / next_step / submit / result`, the real `EXECUTORS` with the real out-of-process domain
  operations, a scripted agent that answers only from what the runtime shows it, a scripted harness, a stub TrailSignal behind the production `TrailMCPClient`, the in-memory store.
  Status `completed`. 15 domain steps `executed`; three laws each sent one draft back (unclassified citation · one mechanism three times · one product idea) and the agent was SHOWN
  the law's errors; TrailSignal's eleven calls in order; an ANCHOR cluster from 5 admitted records over 5 of TrailSignal's independence groups; the harness actions are contract-valid and
  carry TrailSignal's intent first and the domain's compiled intents after (per concept for supply); the post-admission knowledge need is the field-grounded question, not a hypothesis
  statement; the RESULT holds 3 concepts × 2 variations, 2 parsed leads (1.2 USD / MOQ 500; a null supplier name where the listing said "unresolved"; no `evidence_score`), per-concept
  coverage incl. one `unsourced`, the lived situation, and TrailSignal's one score + two refusals.
- NEGATIVE CONTROL — an agent that never offers more than one product idea ends `terminal_gap` / `PRODUCT_PORTFOLIO_LAW_UNSATISFIED` with the law's message; nothing was sourced or scored.
  (A wrong `authority` value in my own first fixture produced `LINEAGE_LAW_UNSATISFIED` the same way — an unplanned second control.)
- Existing adapters: the three pre-existing manifests are byte-identical to `production`; neutrality, contract, MCP parity, worker evidence surface, runtime purity, R5 audit and MCP server
  suites green; engine suite 609 / 609. Everything database-free with `POLYMATH_PG_DSN` unset. Guards 0 / 0 / 0 / READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN`. This is NOT a live run: no live TrailSignal, no live host, no real evidence, no real corpus.

## Rejected claims
- "Ecommerce works end to end." The MACHINERY completes a scripted run. A real run still needs: the branch merged + one bounce, a live TrailSignal that accepts these payloads (D1, M1-01..03
  are Trail-side and unfixed), a commerce corpus (Phase 10, needs Item 2D), a host that writes the observation-context convention, and the dossier (Phase 8).
- "M1-08 / M1-07 / D2 are fixed." They are addressed FOR THIS MANIFEST (materials; `require_directive`; corpus questions after admission). `trail.product_discovery` is unchanged.
- "The first knowledge pass is fixed." `F_retrieve` still sends hypothesis statements (D2) — there are no lived clusters before the first admission.

## Open contract gaps
- `ADAPTER_RUNTIME` — UPDATED (additive: `materials` sibling key; `config.show`; `config.source` over outputs). `MCP_SURFACE` — TESTED_UNCHANGED (`adapter_next` passes the response through;
  parity + server suites green). Database-backed adapter suites — DEFERRED to the merge window (unchanged).
- `max_branch_loops` is ONE counter shared by every BRANCH; the manifest works around it (round-bounded evidence loop). A per-branch budget would be a runtime change; not needed yet.
