---
change_id: CONSOLIDATION-MIGRATION-PHASE6-TRAIL-CORE-EMBEDDED
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "ADR-0021: TrailSignal's deterministic research core is imported byte-identical under `governance/trail/` and reachable in process through the unchanged `TrailMCPClient` when `POLYMATH_TRAIL_MODE=embedded` (default `daemon`). New dependency-map owner `trail_governance`. `workers/` changes on branch `migration/ecommerce-consolidation` only — NOT merged, live fleet untouched."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 6: the TrailSignal core, embedded, and the first complete run against it

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 6: deterministic dependency analysis; import the minimum required core; preserve deterministic behaviour, the source registry, LAW 1, LAW 2 and Trail's
logical ownership; write the embedding ADR. Gate: embedded operations pass equivalence / contract tests. `MIGRATION_POLICY.md` INV-5, stop conditions 1 and 5. Design recorded BEFORE the import:
`docs/migration/ADR-TRAIL-EMBEDDING.md` (source-verified) + `AUTO_DECISIONS.md` M-012 (`production` `71075d1`).

## Changes
- `governance/trail/` — 30 files via `git archive de64d84` from `~/trail-signal-os-worktrees/A41` (tracked files only): the 16-module closure under `src/trail_signal/`, `config/` (3), `data/` (10
  registry CSVs), `LICENSE` (MIT). `PROVENANCE.json` pins every sha256; each was also compared to the git OBJECT at `de64d84`. Privacy scan: no home path, e-mail address or key-like string.
- `governance/trail/embedded.py` — the only authored file: `build_service`, `SqliteResearchStore` (TrailSignal's store port incl. `load_admitted`; first commit wins; durable on a file path),
  `polymath_principal`, `operate`, `transport` (JSON-RPC `tools/call`; a refusal or an invalid request is `isError: true`, as the daemon reports it).
- `workers/workers/adapter_step_worker.py` — `trail()` builds the same client over the embedded transport when `POLYMATH_TRAIL_MODE=embedded` (module loaded by file path); otherwise unchanged.
- `config/adapters/ecommerce.product_research.json` (54 steps) — NEW step `S_gaps`: TrailSignal compiles the SUPPLY directive with `gaps.compile` `stage: supply` from the market
  qualification's open gaps. Found by running against the real core: `opportunity.qualify` returns NO directive, so without this step supplier research would run under an older stage's
  directive (external-review finding M1-07 — confirmed against real code; `trail.product_discovery` still has it).
- `architecture/dependencies.json` owner `trail_governance`; ADR-0021; refactor 0015; architecture changelog.
- Tests: `tests/contracts/test_trail_core_embedding.py` (4, no third-party import), `tests/determinism/test_trail_core_embedded.py` (4), `tests/determinism/
  test_adapter_ecommerce_product_research_embedded_trail.py` (1); the scripted stub in the e2e test now behaves like real TrailSignal for the supply directive.

## Proof
- Byte identity: 30 / 30 files equal their pinned sha256 AND the git objects at `de64d84`; nothing else sits beside them but `embedded.py` + `PROVENANCE.json`; `embedded.py` imports nothing of the runtime.
- Through Polymath's UNCHANGED `TrailMCPClient`: a real `registry.project` (TrailSignal's registry compiled from the embedded data: 27 source roles, priors returned), idempotent replay equal, a wrong
  snapshot id and a mismatched operation kind surface as the same typed `TrailToolError`, and the audit store replays the first commit after a simulated restart (one operation row).
- **COMPLETE RUN AGAINST THE REAL CORE** (`POLYMATH_TRAIL_MODE=embedded`, the worker's own switch; in-memory Polymath store; scripted agent and harness): status `completed`, every
  `EXTERNAL_OPERATION` and `DOMAIN_OPERATION` executed. TrailSignal ADMITTED 5 of 5 community observations on each of 3 research rounds; the domain built an ANCHOR cluster counting 5 of
  TRAILSIGNAL'S independence groups; TrailSignal REJECTED the fabricated product-review source (`SOURCE_UNREGISTERED`) and both fabricated supplier listings (`SOURCE_ROLE_UNSUITABLE`);
  qualifications `UNPROVEN` / `NO_DEFENSIBLE_BRIDGE`; the score was REFUSED for all three hypotheses with `HARD_GATE_UNMET` naming the unmet market and supply gates. Result: 3 concepts × 2
  variations, 0 leads, 0 scores, 3 refusals, no supply claim. A defensible rejection, produced by TrailSignal's own code — not a software failure.
- Interpreters: the three TrailSignal-dependent tests pass under TrailSignal's interpreter (`~/trail-signal-os-worktrees/A41/.venv`, which has `packageurl`); under this repo's they SKIP with the
  reason printed. Everything else — scripted e2e + negative control, all seam tests, provenance pin, contract / parity / neutrality / purity / audit / MCP suites, engine 609 / 609 — passes under
  this repo's interpreter, database-free, `POLYMATH_PG_DSN` unset. Guards 0 / 0 / 0 / READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN`. Not merged, not deployed, not a live run; sources and agent are scripted.

## Rejected claims
- "Equivalence with the daemon is proven." Byte identity of the code is; the recorded-envelope replay (`pmv4-m1-repro` fixtures) and TrailSignal's own operation tests are NOT yet ported.
- "D1 / M1-01..03 are fixed." Untouched. This run did not hit D1 (its admissions admitted observations); a zero-admission round still would.
- "Embedded mode is ready for the fleet." `packageurl` is not in this repo's environment; default mode is `daemon`.

## Open contract gaps
- `ADAPTER_RUNTIME` — UPDATED (client factory switch; additive). `TRAIL_WIRE` — TESTED_UNCHANGED through the production client against the embedded core.
- Dependency: `packageurl` → `pyproject.toml` + install in the merge window (a live-environment change): DEFERRED.
- Database-backed adapter suites: DEFERRED to the merge window (unchanged).
