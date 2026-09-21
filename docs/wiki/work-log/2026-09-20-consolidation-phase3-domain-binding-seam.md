---
change_id: CONSOLIDATION-MIGRATION-PHASE3-DOMAIN-BINDING-SEAM
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "ADR-0020: the adapter step vocabulary gains ONE automatic type, DOMAIN_OPERATION (manifest-named domain code run out of process by the existing worker). New dependency-map owner `domain_adapter` for `adapters/`. `shared/` + `workers/` change on branch `migration/ecommerce-consolidation` only — NOT merged, the live fleet is untouched, a bounce is needed at merge."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 3: the domain binding seam

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 3: extend the EXISTING adapter runtime minimally so an ecommerce adapter can invoke domain Python — no
second scheduler, no second durable state machine, no second hypothesis ledger, existing adapters stay compatible, ecommerce domain failures map
into existing typed adapter semantics. Gate: a real ecommerce domain operation executes through the existing adapter runtime. Decision recorded
BEFORE coding: `docs/migration/AUTO_DECISIONS.md` M-007 (`production` `988070a`). ADR-0020.

## Changes
- `shared/polymath_shared/adapter/contracts.py` — `STEP_TYPES` + `DOMAIN_OPERATION` (automatic). Four `contracts/adapter/v1/*.schema.json` step-type
  enums gain the same member (manifest, step, run status, step receipt).
- `shared/polymath_shared/adapter/manifest.py` — validation: `config.domain` (`^[a-z][a-z0-9_]{1,40}$`), `config.operation` (dotted id),
  `config.inputs` (name → dotted path); `config.domain` / `config.operation` refused on any other step type.
- `workers/workers/adapter_step_worker.py` — `exec_domain`, registered in the existing `EXECUTORS` table: resolves `adapters/<domain>/binding.py`
  (must sit inside `adapters/`), sends one `domain_operation_request.v1` on stdin, hard timeout (`POLYMATH_DOMAIN_OPERATION_TIMEOUT_S`, default 120),
  1 MB response cap, MINIMAL environment (PATH, LANG, PYTHONDONTWRITEBYTECODE only). `ok:false` → typed gap with the domain's own code; crash /
  timeout / malformed / untyped refusal → raises → the runtime's existing `STEP_EXECUTOR_ERROR`. Output carries `_domain` lineage.
- `adapters/ecommerce/binding.py` — the engine's one door. `OPERATIONS` table, first entry `hypotheses.validate_bridge`, which WRAPS
  `python/bridge.py` (`validate_all` + `validate_portfolio`) and `graph.load_policies()`; engine stdout is redirected to stderr.
- `architecture/dependencies.json` — owner `domain_adapter` (`adapters/`), may depend on nothing, forbidden to import `shared`, `orchestrator`,
  `worker`, `control`, `sidecar`. ADR-0020, refactor 0014, architecture changelog entry.
- Tests: `tests/determinism/test_adapter_domain_operation.py` (23), `tests/determinism/_adapter_memory_store.py` (in-memory double of
  `adapter.store` so runtime tests need no Postgres), fixture manifest `tests/fixtures/adapter_domain_binding/fixture.domain_binding.json`.
- `tests/contracts/test_adapter_contract_v1.py` — the closed-vocabulary pin `STEP_TYPES` gains the one declared member. This is the contract
  change itself (the pin asserts `set(enum) == STEP_TYPES`), made in the same slice as its ADR; no other assertion in any existing test changed.
- `service.py`, `transitions.py`, `store.py`, `hypotheses.py`, `trail_client.py`, every shipped manifest: UNCHANGED.

## Proof
- GATE — `test_a_real_domain_law_governs_a_run_through_the_existing_runtime`: `service.start → advance → submit → advance …` with the REAL
  `W.EXECUTORS`; the agent's first portfolio (one mechanism three times) is rejected by the engine's own portfolio law, the `BRANCH` returns the run
  to reasoning, the second portfolio is admissible, the run compiles. Step order `draft, check, route, draft, check, route, compile`; both `check`
  rows `DOMAIN_OPERATION` / `executed` with valid receipts; `branch_loops == 1`; status `completed`.
- Typed semantics: domain refusal → `terminal_gap` with the domain's code (`POPULATION_NOT_FOUND`, `HYPOTHESES_MISSING`); unknown operation /
  missing domain → typed gaps; crash → run `failed` / `STEP_EXECUTOR_ERROR` with no exception escaping `advance`; 6 malformed-response shapes incl.
  a timeout raise with a named reason; 7 malformed manifests refused incl. `../ecommerce`; environment isolation proven (no `POLYMATH_*` variable
  reaches domain code).
- Executed path: `test_the_code_under_test_is_this_checkout` asserts `contracts`, `manifest`, `service` and the worker module resolve inside this
  worktree (the editable install would otherwise resolve `workers` to the MAIN checkout).
- Regression, all database-free, run with `POLYMATH_PG_DSN` UNSET: new 23 + `test_adapter_contract_v1` + `test_adapter_worker_evidence_surface` +
  `test_mcp_adapter_parity` + `test_adapter_runtime_neutrality` + `test_adapter_runtime_pure` + `test_research_package_removed` = 96 passed;
  `test_adapter_r5_audit` 12 passed; `test_mcp_server_v2` 5 passed. Engine suite still 609 / 609 (the binding adds a file, changes none).
- Guards: `agent_preflight` 0 · `repo_guard` 0 (incl. `--base production` companions) · `wiki_worm --check` 0 · `bundle_integrity` READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN`. NOT `MERGED`, NOT `DEPLOYED`, NOT `LIVE_PATH_PROVEN`.

## Rejected claims
- "Ecommerce intelligence is restored." ONE operation is bound. Population discovery, lived situations, planning, ideation, sourcing, parsers, the
  lead join and the report are still unbound (Phases 4–8).
- "The engine's hypotheses and Polymath's ledger are reconciled." The bound law validates ENGINE-shaped bridge hypotheses carried in a step output.
  Mapping them onto `HypothesisStateV1` — one ledger, no second one — is Phase 5.
- "The full adapter regression suite passed." The database-backed suites were deliberately NOT run (below).
- "This runs in the live fleet." The live worker has no `DOMAIN_OPERATION` executor until this branch is merged and the fleet bounced; a manifest
  using the type before then would stop with the existing typed gap `STEP_TYPE_UNSUPPORTED`.

## Open contract gaps
- `ADAPTER_RUNTIME` — **UPDATED** (one enum member in four schemas + `STEP_TYPES`; pinned by `test_adapter_contract_v1.py`).
- `MCP_SURFACE` (transitive) — **TESTED_UNCHANGED** (`test_mcp_adapter_parity.py` 7, `test_mcp_server_v2.py` 5; the seven `adapter_*` tools pass step
  objects through and enumerate no step type).
- `contract_impact` also lists `test_adapter_evidence_boundary.py` and `test_adapter_product_discovery_loop.py`: **DEFERRED** — both open `tx()`
  against the shared Postgres the live fleet uses, and the loop test COMMITS `running` runs a live worker could claim. They are to be run in the
  merge window with the fleet drained, or ported onto `_adapter_memory_store.py`. Risk accepted for now because the change is additive: no existing
  step type, manifest, transition or store function is touched, and all three shipped manifests still load.
- No budget counter for `DOMAIN_OPERATION` (bounded by `max_steps`); revisit only if a real ecommerce manifest shows a need.
