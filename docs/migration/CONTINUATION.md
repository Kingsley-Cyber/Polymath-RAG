# Migration Continuation

> Agent-owned restart boundary. Update at every meaningful phase transition. A fresh session continues from this file, the
> controlling documents and the repositories — never from chat history.
>
> **Instruction hierarchy:** 1. user / repository constitutional rules · 2. `MIGRATION_POLICY.md` · 3. `BOOTSTRAP_CONTEXT.md` ·
> 4. `EXECUTION_PLAN.md` · 5. applicable ADRs · 6. `AUTO_DECISIONS.md` · 7. `CONTINUATION.md` · 8. current source + tests + git
> state. Repository facts can invalidate stale factual claims; they do not silently invalidate migration intent. Material
> contradictions are handled under the policy's stop conditions.

## Mission
Polymath ecommerce consolidation migration: one `polymath-v4` checkout carries the complete governed ecommerce reference
implementation — `adapters/ecommerce/` (harvested `TRAIL_AGENT_AUTORESEARCH` intelligence) + `governance/trail/` (the required
deterministic Trail core) on the EXISTING adapter runtime. Harvest behaviour, not architecture. Ecommerce first; no speculative
generic infrastructure.

## Current Phase
**Phases 0–5 — DONE on the migration branch** (`072f1cc` import · `076eb6b` seam, ADR-0020 · `f20cf22` evidence intake · `92b9d76` / `4a938bd` / `7f87e57` the domain operations ·
`92efc79` the product manifest `ecommerce.product_research` v0.1.0 + ONE COMPLETE RUN through the existing runtime IN TEST FORM, plus a negative control — acceptance-ladder rungs A–C, E and G as tests).
**NEXT: Phase 6 — embed the required TrailSignal core** (source verification first), then Phase 8 (the dossier: reuse the engine's renderer), then merge + bounce + the live rungs.
All code on branch `migration/ecommerce-consolidation` (worktree `../pmv4-consolidation`), NOT merged; the live fleet is untouched; nothing pushed.

## Repository State
- polymath-v4 `production`: clean, docs only since `758ff8a`; 130+ commits ahead of `origin/main`, nothing pushed.
- **Migration worktree `~/Documents/polymath-rebuild/pmv4-consolidation`, branch `migration/ecommerce-consolidation`** = `production@758ff8a` + `072f1cc` (Phase 2) + `076eb6b` (Phase 3). Clean. It has no `.venv`: run with `/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python` and `PYTHONPATH=$PWD`.
- Parked worktrees: `pmv4-atom-scope` (Item 2D, UNCOMMITTED, 7 files) · `pmv4-m1-repro` (`review/m1-reproductions` @ `eb63bef`, red on purpose). Merged, removable: `pmv4-governed`, `pmv4-packet-text`.
- AutoResearch: `main` @ `a7baa66` (v2.3.0), clean, 3 commits ahead of GitHub. PUBLIC. Still the engine the Hermes skill runs (the import is a copy; nothing was removed — INV-9).
- Trail: `~/trail-signal-os-worktrees/A41` @ `de64d84`, clean. Untouched.
- Hermes: deployed copy `standalone/opportunity-research` v2.3.0; three skill text files uncommitted (owner's commit).

## Current HEAD / Branch
`production` (docs) · `migration/ecommerce-consolidation` @ `92efc79` (code).

## Completed
- Owner reframe recorded in the plan of record; harvest map written (registers 11.362; commits `59a4b60`, `9dfd3c3`).
- `docs/migration/` complete: owner-controlling `MIGRATION_POLICY.md`, `BOOTSTRAP_CONTEXT.md`, `EXECUTION_PLAN.md` (+ `README.md`,
  `NEW_SESSION_BOOTSTRAP_PROMPT.md`) installed BYTE-IDENTICAL from `~/Documents/polymath-rebuild/polymath_migration_bootstrap.zip`; the earlier,
  longer owner text kept as `BOOTSTRAP_CONTEXT_EXTENDED.md` (the bundle wins on any difference; it alone states the target tree
  `adapters/ecommerce/` + `governance/trail/` and the report acceptance list). Agent-owned: `CAPABILITY_MAP.md`, `PARITY_MATRIX.md`,
  `AUTO_DECISIONS.md` (M-001…M-005), `ADR-TRAIL-EMBEDDING.md` (DRAFT), `FINAL_MIGRATION_REPORT.md` (skeleton), this file.
- `/polymath-bootstrap` verified: detects `docs/migration/`, reads the documents in order, stops when the policy or plan is
  missing, baseline-first search, Trail / AutoResearch / wrapper names, test isolation, evidence vocabulary (10 of 10).
- Tools discovered: `graphify` and `graft` present; CodeGraph and Ponytail absent.

## Current Architecture
On the migration branch: `adapters/ecommerce/` (the engine, its own layout, its own 609-check suite) · `adapters/ecommerce/binding.py` (the ONE door: 14 operations, JSON in / JSON out) ·
`DOMAIN_OPERATION` in the existing runtime (`exec_domain`, out of process, minimal environment, typed gap / `STEP_EXECUTOR_ERROR`) · `next_step` sibling `materials` (a manifest shows an agent step selected prior
outputs) · `config/adapters/ecommerce.product_research.json` (53 steps: the 28 governed steps of `trail.product_discovery` + the domain). TrailSignal is still a DAEMON reached over MCP (Phase 6 changes that).
Domain code computes and never owns state; no engine score or verdict leaves the domain. `trail.product_discovery.json` and the other two manifests are byte-identical to `production`. Live system: unchanged.

## Capabilities Migrated
IMPORTED: all. BOUND (14 operations): `knowledge.corpus_evidence` · `understanding.lenses` · `understanding.validate_primitives` · `population.nominate` · `population.evidence_cards` ·
`population.validate_situations` · `knowledge.corpus_questions` · `hypotheses.validate_bridge` (+ lived-anchor laws) · `research.plan` · `products.validate_concepts` · `supply.plan` · `supply.leads` · `law.refuse`.
COMPOSED: `ecommerce.product_research` v0.1.0 — one complete scripted run + a negative control pass. NOT bound: the advisory semantic review (`evaluator.py`), the report (`report.py`, Phase 8).

## Authority Map
Polymath: knowledge, EvidencePacket, adapter runtime, ledger, lineage, MCP · ecommerce adapter (to be harvested): niche /
population / planning / hypothesis structure / ideation + variations / sourcing / parsers / lead join / report · Trail:
admission, freshness, independence, judgement, territory, qualification, score / refusal, registry · agent host: execution.
Full table: `CAPABILITY_MAP.md` "Duplicate Authority Map".

## Important Auto Decisions
M-002 docs on `production`, code in the migration worktree · M-003 the bundle controls · M-004 baseline = existing runs · M-005 commerce corpus at Phase 10 after Item 2D ·
**M-006** import via `git archive` (tracked files only), three exclusions, history: the engine lived here as `research/` until 11.274 retired it to the Hermes skill — the O6 dead-path guard stays green ·
**M-007** the seam = one step type + out-of-process binding (rejected: `EXTERNAL_OPERATION` reuse, `VALIDATE` overload, in-process import, host-side only, SDK) ·
**M-012** (PROPOSED) embed the EXACT 16-module Trail closure byte-identical under `governance/trail/`, reached through the unchanged `TrailMCPClient` with an in-process transport, `POLYMATH_TRAIL_MODE` default `daemon`; trimming / D1 / registry reconciliation are separate later changes ·
**M-011** `materials`: a manifest may SHOW an agent-answered step selected prior outputs (sibling key, additive); law loops end in a typed `law.refuse` gap; the evidence loop is bounded by research rounds ·
**M-010** domain hypotheses ride in the θ step output addressed by LEDGER id (no second ledger); mechanism support is DERIVED from the ledger status; no engine score or verdict leaves the domain (`join_leads` extracted) ·
**M-009** Phase 5 shape: population discovery = research PLANNING; TrailSignal WHAT / engine HOW via the `research_directive` key (no runtime change); cards + lived situations AFTER admission using Trail's independence groups; governed operations compile the engine registry in memory ·
**M-008** ONE evidence id space in governed mode (the runtime's ids; the engine's `polymath:chunk:` prefix is dropped at the binding); the engine's schema byte copies stay, pinned against this repo.

## Tests Passed
In the migration worktree, all database-free, `POLYMATH_PG_DSN` unset: engine suite 609 / 609 + `doctor` · `test_ecommerce_engine_import.py` 5 (INV-7 privacy pins incl. a negative control) ·
`test_adapter_domain_operation.py` 25 · `test_adapter_ecommerce_knowledge_intake.py` 6 · `test_adapter_ecommerce_population_research.py` 6 · `test_adapter_ecommerce_lived_world.py` 7 · `test_adapter_ecommerce_products_supply.py` 7 · `test_adapter_ecommerce_product_research_e2e.py` 3 (one complete run + negative control) · existing `test_adapter_contract_v1` / `_worker_evidence_surface` / `test_mcp_adapter_parity` / `_runtime_neutrality` / `_runtime_pure` / `_r5_audit` /
`test_mcp_server_v2` / `test_research_package_removed` green · guards 0 / 0 / 0 / READY. Reusable asset: `tests/determinism/_adapter_memory_store.py` (runtime tests with NO Postgres).

## Known Failures
- LIVE path: nothing here has run against a live TrailSignal, a live host or real evidence. D1 and M1-01..03 are TRAIL-side and unfixed; they will bite a live run at `L_judge` / admission exactly as in R2a.
- `trail.product_discovery` keeps D2–D7 and M1-04..M1-12 (unchanged by design, INV-9). `ecommerce.product_research` addresses M1-07, M1-08 and (after admission) D2 for itself.
- NOT RUN on the branch (deliberately): `test_adapter_evidence_boundary.py`, `test_adapter_product_discovery_loop.py`, `test_adapter_service_store.py`, `test_adapter_harness_action.py` — they use the shared Postgres
  (the loop test commits `running` runs). Run them in the merge window with the fleet drained. `service.py` changed additively (`materials`), so this matters at merge.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not baselined). Historical baseline fails canary 2 of 9.

## Current Blocker
None. (The commerce corpus is pre-authorized by the policy and scheduled for Phase 10 — M-005. Item 2D must be merged before it.)

## Next Exact Action
**Phase 6 — embed the required TrailSignal core.** Source verification is DONE (2026-09-20: `ADR-TRAIL-EMBEDDING.md` now PROPOSED with the verified closure table; decision M-012). Steps 1–2 below are complete — START AT STEP 3. Facts: closure = 16 modules / 6,944 lines under `src/trail_signal/`; MIT; `packageurl` missing from `polymath-v4/.venv` (A41 has its own `.venv` — prove the embedded copy there first); store port = `commit` + `load`; registry compiler reads `data/<CURATED_CSVS>.csv`, `data/source_capabilities.csv`, `config/evidence_gates.json`, `config/scoring_weights.json`, `config/weights.yaml`; Trail's operation tests = `tests/integration/research/test_research_operations_store.py`, `tests/e2e/research/test_research_mcp_operations.py`. (Original step list:)
1. In `~/trail-signal-os-worktrees/A41` (never the stale `~/trail-signal-os` main): confirm the import closure of `contexts/workflow/application/research_operations.py` (recorded: 16 modules / 6,944 lines; third party
   `pydantic`, `typing_extensions`, `packageurl`), read `workflow/public/operations.py` (can the research wire models stand alone without `data_os` / `platform` / `discovery` contract modules = 57 % of the lines?), the
   store port (how operations / results are persisted), `THIRD_PARTY_NOTICES.md` + LICENSE (stop condition 1), and check `packageurl` is installable in `polymath-v4/.venv`.
2. Decide and record M-012: target `governance/trail/` (new top-level, dependency-map owner, may import nothing of the runtime); the smallest closure; how `trail_client` reaches it — keep the wire shape and swap the
   TRANSPORT (an in-process transport behind the same `TrailMCPClient` interface keeps `exec_external` and every test unchanged) vs a new client. Amend ADR-063 narrowly as the policy allows; Trail's laws stay.
3. Import with `git archive` from A41 @ `de64d84` (tracked files only), port Trail's own tests for the seven operations, prove EQUIVALENCE: same request → same result from the daemon build and the embedded build
   (fixtures: the recorded envelopes under `pmv4-m1-repro/tests/review_m1/fixtures/`).
4. Only then look at D1 / M1-01..03 inside the embedded core — with documented intent, because they touch Trail behaviour (stop condition 5 applies to SEMANTIC changes, not to bug fixes with a written contract).
**Then Phase 8**: bind `report.py` (`adapters/ecommerce/python/report.py`, the existing renderer + ReportModel; `governed_run.py` already maps a governed journal to it) as `report.render` fed from the run RESULT; the five
authority labels. **Then** merge window: drain → merge → DB-backed suites → one bounce → Hermes MCP reload → live rungs E / F / G (Phase 10 corpus needs Item 2D merged first).

## DO NOT REDO
- The comparison, the dependency facts, the registry-drift check, the historical-run inspection (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (never re-run against the shared Postgres).
- The import (Phase 2) and the seam decision (M-007 lists the rejected alternatives with reasons — do not re-litigate).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, in-process import of the engine's flat modules, or import of private ledgers.

## Relevant Commits
`production`: `59a4b60` · `9dfd3c3` · `23d517e` · `758ff8a` owner bundle · `988070a` M-006 + M-007 · `4e627dc` continuation after phases 2–3 · this commit (M-008, phase 4).
`migration/ecommerce-consolidation`: `072f1cc` Phase 2 (11.363) · `076eb6b` Phase 3 (11.364, ADR-0020) · `f20cf22` + `b794b3a` Phase 4 (11.365) · `92b9d76` Phase 5a (11.366) · `4a938bd` Phase 5b (11.367) · `7f87e57` Phase 5c (11.368) · `92efc79` product manifest + complete run in test form (11.369). Branch `review/m1-reproductions` `eb63bef`.

