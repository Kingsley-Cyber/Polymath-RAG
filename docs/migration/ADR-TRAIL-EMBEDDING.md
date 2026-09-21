# ADR — Trail Deterministic Core Deployment Boundary

Status: PROPOSED — source verified 2026-09-20 (A41 @ `de64d84`, read-only); NOT yet implemented. Decision record: `AUTO_DECISIONS.md` M-012.

## Context
Today Polymath reaches Trail's seven bounded research operations over an authenticated MCP daemon (`:8767`) that also needs its own
Postgres and Temporal. The consolidation direction (owner, 2026-09-20) authorizes embedding the required deterministic core in
`polymath-v4/governance/trail/` "if repository inspection confirms the previously demonstrated in-process seam".
Verified so far: `ResearchOperationService.operate` ran in-process with an in-memory store and the compiled A41 registry
(branch `review/m1-reproductions`, `tests/review_m1/trail/_trail_harness.py`). Size: evidence 487 + planning 782 + scoring 347
lines + part of `contexts/workflow` + 12 registry CSVs, out of 37,132 lines.

## Existing ADR-063 constraints
A41 `docs/adr/063_harness_executed_opportunity_research_boundary.md`, lines 26-31, 44, 53-54 (read 2026-09-20): Polymath owns
knowledge, durable hypothesis state, hypothesis evolution, retrieval lineage and mechanism reasoning; Trail owns the compiled
registry snapshot, evidence-gap compilation, evidence admission, source and evidence-role policy, product-domain qualification
and the deterministic score; the host harness owns live-world execution; "TrailSignal never writes Polymath state and never
implements retrieval, embedding, graph, or hypothesis storage"; each operation "runs a pure deterministic function, and
atomically commits one terminal audit operation and one immutable result without creating workflow state".

## What is changing
The PROCESS boundary only. Today `workers/adapter_step_worker.exec_external` → `TrailMCPClient` → HTTP → the Trail daemon (`:8767`, its own Postgres + Temporal) →
`ResearchOperationService`. After: the same `exec_external` and the same `TrailMCPClient`, but the client's TRANSPORT is an in-process handler that routes `tools/call` to a
`ResearchOperationService` built inside `polymath-v4/governance/trail/`. The wire shape (request envelope, result envelope, registry snapshot ref, refusal codes) is unchanged, so every existing
worker test that uses `httpx.MockTransport` keeps testing the real path. The daemon mode stays available behind a switch until parity is proven (INV-9).

## What is explicitly NOT changing
Trail's seven operations, their pure functions, the registry-driven policy, LAW 1 (the only score is Trail's), LAW 2, the ownership split of ADR-063 quoted above, and the
rule that Trail never writes Polymath state. The imported files are BYTE-IDENTICAL to A41 @ `de64d84` (sha-pinned); no Trail source line is edited by the embedding itself.

## Logical ownership
Unchanged: Trail = registry / admission / freshness / independence / judgement / territory / qualification / score + refusal. Polymath = runtime, state, ledger, lineage. Ecommerce domain = research craft. A directory move is not an authority move.

## Process/deployment ownership
Polymath's worker process hosts the embedded core. Trail's daemon, its Temporal and its platform contexts are NOT imported. The embedded audit store is Trail's store logically
(one terminal audit operation + one immutable result per operation, replay on the same identity), implemented against the two-method `ResearchStorePort` (`commit`, `load`).

## LAW 1 preservation
The scoring engine (`contexts/scoring/domain/engine.py`, 264 lines) is imported unmodified and is the only code that produces a score; governed domain operations emit none (M-010); `W_interpret` may only cite score record ids.

## LAW 2 preservation
Evidence admission (`contexts/evidence/domain/admission.py`, 235 lines) is imported unmodified; the domain consumes ADMITTED evidence only (M-009 §3) and takes role, freshness, polarity and independence group as given.

## Imported dependency closure
VERIFIED by AST import walk from `src/trail_signal/contexts/workflow/application/research_operations.py` (2026-09-20): **16 modules, 6,944 lines**, third party `pydantic`, `typing_extensions`,
`packageurl`.
| Lines | Module (under `src/trail_signal/`) | Why it is in the closure |
|---|---|---|
| 315 | `contexts/workflow/application/research_operations.py` | the service |
| 969 | `contexts/workflow/public/operations.py` | wire models — ALSO imports `data_os` + `discovery` contracts for non-research models |
| 235 / 87 / 121 / 44 | `contexts/evidence/{domain/admission, domain/qualification, public/contracts, public/ports}.py` | admission, qualification |
| 200 / 140 / 267 / 133 | `contexts/planning/{domain/gap_compiler, domain/judgement, domain/registry_compiler, public/contracts}.py` | gaps, judgement, registry snapshot |
| 264 / 83 | `contexts/scoring/{domain/engine, public/contracts}.py` | the score |
| 147 | `kernel/contracts.py` | base models |
| 2,363 / 394 / 1,182 | `contexts/{data_os, discovery, platform}/public/contracts.py` | UNRELATED to research: pulled by `operations.py` (2 names + 1 name) and by `research_operations.py` (`PrincipalCapabilityV6`, `PrincipalContextV6`); `platform` is what needs `packageurl` |
Data the registry compiler reads: `data/<CURATED_CSVS>.csv`, `data/source_capabilities.csv`, `config/evidence_gates.json`, `config/scoring_weights.json`, `config/weights.yaml`.
Composition today: `entrypoints/daemon/composition.py:1081-1090` (store = Postgres adapter `contexts/data_os/adapters/postgres/research.py`, table `v2_research_operations`).
Noted weakness to carry into the embedding design, NOT to copy: `ResearchOperationService.admitted` is an in-memory dict ("this daemon's memory of its own commits") — a restart forgets admissions.
Licence: MIT (`LICENSE`), `THIRD_PARTY_NOTICES.md` lists no vendored code inside the closure → stop condition 1 does not apply.

## Registry ownership
Trail's registry stays the ONE governance registry (its CSVs + config travel with the embedded core). The ecommerce engine's own registry copy (`adapters/ecommerce/registry/`, compiled in
memory for population priors) is a second physical copy with known drift (+6 seeds, +10 friction families, +6 niche candidates) — reconciling them is Phase 7, after the core is embedded.

## Compatibility implications
`packageurl` (pure Python, `packageurl-python`) is MISSING from `polymath-v4/.venv` — it must be added to `pyproject.toml` and installed in the merge window (a live-environment change), or the
`platform` contracts import must be avoided by trimming (rejected for the first embedding: it edits Trail source and breaks byte-identity). A41 has its own `.venv`, so the embedded closure can be proven
standalone there before polymath-v4's environment changes. `shared/` + `workers/` change only by a transport switch.

## Decision
PROPOSED (M-012): embed the exact closure, byte-identical and sha-pinned, under `governance/trail/src/trail_signal/…` with its registry data and Trail's own tests for the seven operations; add one
composition module `governance/trail/embedded.py` (service + `ResearchStorePort` implementation + an `httpx`-compatible in-process transport); select it with `POLYMATH_TRAIL_MODE=embedded|daemon` (default
`daemon` until parity). Trimming the three unrelated contract modules and fixing D1 / M1-01..03 are SEPARATE, later changes with their own written contracts.

## Consequences
One checkout can run the governed loop without the Trail daemon, its Postgres or Temporal. ~57 % of the imported lines are unrelated contract models until trimmed. The embedded store needs a durability decision (see Validation).

## Validation
1. sha256 of every imported file == A41 @ `de64d84`. 2. Trail's own `tests/integration/research/test_research_operations_store.py` + the e2e research-operation tests pass against the embedded copy (in A41's
venv first). 3. EQUIVALENCE: the recorded request envelopes under `pmv4-m1-repro/tests/review_m1/fixtures/` produce the same result from the embedded service as the recorded daemon results. 4. The complete
scripted run (`test_adapter_ecommerce_product_research_e2e.py`) passes with the EMBEDDED core in place of the stub. OPEN: where the embedded audit store persists (SQLite under the runtime dir vs Polymath
Postgres tables — the latter needs a migration and a live window).

