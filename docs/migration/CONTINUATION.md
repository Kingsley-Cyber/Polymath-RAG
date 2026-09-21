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
**Phases 0–4 — DONE** (`072f1cc` import · `076eb6b` seam, ADR-0020 · `f20cf22` evidence intake).
**Phase 5 — operations BOUND (5a `92b9d76` · 5b `4a938bd` · 5c `7f87e57`); NOT yet composed into a product manifest.** Thirteen operations sit behind `adapters/ecommerce/binding.py`.
**NEXT: compose them — `config/adapters/ecommerce.product_research.json` + a full fixture run through `service.advance` (stub TrailSignal, in-memory store).** Then Phase 6 (embed the Trail core).
All code on branch `migration/ecommerce-consolidation` (worktree `../pmv4-consolidation`), NOT merged; the live fleet is untouched.

## Repository State
- polymath-v4 `production`: clean, docs only since `758ff8a`; 130+ commits ahead of `origin/main`, nothing pushed.
- **Migration worktree `~/Documents/polymath-rebuild/pmv4-consolidation`, branch `migration/ecommerce-consolidation`** = `production@758ff8a` + `072f1cc` (Phase 2) + `076eb6b` (Phase 3). Clean. It has no `.venv`: run with `/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python` and `PYTHONPATH=$PWD`.
- Parked worktrees: `pmv4-atom-scope` (Item 2D, UNCOMMITTED, 7 files) · `pmv4-m1-repro` (`review/m1-reproductions` @ `eb63bef`, red on purpose). Merged, removable: `pmv4-governed`, `pmv4-packet-text`.
- AutoResearch: `main` @ `a7baa66` (v2.3.0), clean, 3 commits ahead of GitHub. PUBLIC. Still the engine the Hermes skill runs (the import is a copy; nothing was removed — INV-9).
- Trail: `~/trail-signal-os-worktrees/A41` @ `de64d84`, clean. Untouched.
- Hermes: deployed copy `standalone/opportunity-research` v2.3.0; three skill text files uncommitted (owner's commit).

## Current HEAD / Branch
`production` (docs) · `migration/ecommerce-consolidation` @ `7f87e57` (code).

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
On the migration branch: `adapters/ecommerce/` (the engine, its own layout, its own suite) + `adapters/ecommerce/binding.py` (the ONE door: `OPERATIONS` table, JSON in / JSON out)
+ `DOMAIN_OPERATION` in the existing runtime (`exec_domain` in the existing `EXECUTORS`; out of process; minimal environment; typed gap / `STEP_EXECUTOR_ERROR`). Domain code computes and never
owns state. `service.py`, `transitions.py`, `store.py` and the three shipped manifests are unchanged. Live system: unchanged (four locations; governed adapter → Trail daemon over MCP).

## Capabilities Migrated
IMPORTED: all (609 / 609 in place). BOUND (`adapters/ecommerce/binding.py` `OPERATIONS`, 13): `knowledge.corpus_evidence` · `understanding.lenses` · `understanding.validate_primitives` ·
`population.nominate` · `population.evidence_cards` · `population.validate_situations` · `knowledge.corpus_questions` · `hypotheses.validate_bridge` (+ lived-anchor laws) · `research.plan` ·
`products.validate_concepts` · `supply.plan` · `supply.leads`. NOT bound yet: the advisory semantic review (`evaluator.py`), the report (`report.py`, Phase 8). In a product manifest: none yet.

## Authority Map
Polymath: knowledge, EvidencePacket, adapter runtime, ledger, lineage, MCP · ecommerce adapter (to be harvested): niche /
population / planning / hypothesis structure / ideation + variations / sourcing / parsers / lead join / report · Trail:
admission, freshness, independence, judgement, territory, qualification, score / refusal, registry · agent host: execution.
Full table: `CAPABILITY_MAP.md` "Duplicate Authority Map".

## Important Auto Decisions
M-002 docs on `production`, code in the migration worktree · M-003 the bundle controls · M-004 baseline = existing runs · M-005 commerce corpus at Phase 10 after Item 2D ·
**M-006** import via `git archive` (tracked files only), three exclusions, history: the engine lived here as `research/` until 11.274 retired it to the Hermes skill — the O6 dead-path guard stays green ·
**M-007** the seam = one step type + out-of-process binding (rejected: `EXTERNAL_OPERATION` reuse, `VALIDATE` overload, in-process import, host-side only, SDK) ·
**M-010** domain hypotheses ride in the θ step output addressed by LEDGER id (no second ledger); mechanism support is DERIVED from the ledger status; no engine score or verdict leaves the domain (`join_leads` extracted) ·
**M-009** Phase 5 shape: population discovery = research PLANNING; TrailSignal WHAT / engine HOW via the `research_directive` key (no runtime change); cards + lived situations AFTER admission using Trail's independence groups; governed operations compile the engine registry in memory ·
**M-008** ONE evidence id space in governed mode (the runtime's ids; the engine's `polymath:chunk:` prefix is dropped at the binding); the engine's schema byte copies stay, pinned against this repo.

## Tests Passed
In the migration worktree, all database-free, `POLYMATH_PG_DSN` unset: engine suite 609 / 609 + `doctor` · `test_ecommerce_engine_import.py` 5 (INV-7 privacy pins incl. a negative control) ·
`test_adapter_domain_operation.py` 25 · `test_adapter_ecommerce_knowledge_intake.py` 6 · `test_adapter_ecommerce_population_research.py` 6 · `test_adapter_ecommerce_lived_world.py` 7 · `test_adapter_ecommerce_products_supply.py` 7 · existing `test_adapter_contract_v1` / `_worker_evidence_surface` / `test_mcp_adapter_parity` / `_runtime_neutrality` / `_runtime_pure` / `_r5_audit` /
`test_mcp_server_v2` / `test_research_package_removed` green · guards 0 / 0 / 0 / READY. Reusable asset: `tests/determinism/_adapter_memory_store.py` (runtime tests with NO Postgres).

## Known Failures
- Governed path: D1–D7 and M1-01..M1-12 — none fixed (they are scheduled inside Phases 4–7, where the code they live in is reworked).
- NOT RUN on the branch (deliberately): `test_adapter_evidence_boundary.py`, `test_adapter_product_discovery_loop.py` — they commit `running` runs into the shared Postgres. Run them in the merge window with the fleet drained, or port them onto the memory store.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not baselined). Historical baseline fails canary 2 of 9.

## Current Blocker
None. (The commerce corpus is pre-authorized by the policy and scheduled for Phase 10 — M-005. Item 2D must be merged before it.)

## Next Exact Action
**Compose the product manifest.** Work in `../pmv4-consolidation`.
1. Write `config/adapters/ecommerce.product_research.json` — START from `trail.product_discovery.json` (copy its Trail steps, harness blocks, budgets, `evidence_roles`, `X_compile`) and insert the domain steps in the
   M-009 shape: knowledge → `knowledge.corpus_evidence` → `understanding.lenses` → AGENT primitives (objective from `adapters/ecommerce/prompts/opportunity_primitives.md`) → `understanding.validate_primitives` → BRANCH →
   `population.nominate` → θ hypotheses (its `output_schema` item must ALLOW the bridge fields: `path`, `evidence_boundary`, `hop_refs`, `target_mechanism`, `gaps`, `alternatives`, `falsifiers`, `grounding`,
   `lived_anchor_ids`, `exploratory`, `status`) → `hypotheses.validate_bridge` (inputs `hypotheses` + `hypothesis_ids` from the θ output) → BRANCH → `registry.project` → judge(filter) → knowledge per hypothesis →
   mechanisms → `gaps.compile` → `research.plan` → HARNESS research → `evidence.admit` → `population.evidence_cards` → AGENT lived situations → `population.validate_situations` → BRANCH → `K_revise` → judge → loop →
   AGENT product concepts (objective from `prompts/product_ideation.md`) → `products.validate_concepts` → BRANCH → `territory.project` → HARNESS product reality → admit → qualify(market_delta) → `supply.plan` →
   HARNESS supply → admit → `supply.leads` → qualify(supply) → score → interpret → compile (include concepts, variations, leads, coverage, lived situations, qualifications, trail_scores, score_refusals).
   Rules: NO source or harness name in the manifest (`test_adapter_runtime_neutrality.py` scans `config/adapters/*.json`); budgets must cover the extra steps; `max_branch_loops` is shared by every BRANCH.
2. Small worker change needed for D2: `_query_text` cannot read a step OUTPUT — add `config.source: outputs.<step>.<key>` support (it already takes a dotted `source` over `input` / `options`), so `F_retrieve` can use
   `knowledge.corpus_questions.need`. Before admission there are no clusters: keep the hypothesis-statement need for the first pass and use corpus questions on the loop pass (a BRANCH, or two knowledge steps).
3. Prove it: ONE fixture-driven end-to-end run through `service.advance` on `_adapter_memory_store.py` with a stub TrailSignal answering all seven operations (extend the `_Trail` class in
   `test_adapter_ecommerce_population_research.py`; the shapes are in `test_adapter_product_discovery_loop.py` `StubTrail` — that module skips without a DSN, so copy shapes, do not import it). Assert: step order,
   every DOMAIN step `executed`, ≥ 3 concepts × ≥ 2 variations in the result, leads without any engine score, TrailSignal's score / refusal present. This is acceptance-ladder rung E in test form.
4. Also run `tests/determinism/test_adapter_runtime_neutrality.py` and `tests/contracts/test_adapter_contract_v1.py` (they load every manifest in `config/adapters/`).
5. Then Phase 6: verify `ADR-TRAIL-EMBEDDING.md` (DRAFT) against source — the 16-module closure, `packageurl`, the store port, `THIRD_PARTY_NOTICES.md` — before importing anything from `~/trail-signal-os-worktrees/A41`.

## DO NOT REDO
- The comparison, the dependency facts, the registry-drift check, the historical-run inspection (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (never re-run against the shared Postgres).
- The import (Phase 2) and the seam decision (M-007 lists the rejected alternatives with reasons — do not re-litigate).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, in-process import of the engine's flat modules, or import of private ledgers.

## Relevant Commits
`production`: `59a4b60` · `9dfd3c3` · `23d517e` · `758ff8a` owner bundle · `988070a` M-006 + M-007 · `4e627dc` continuation after phases 2–3 · this commit (M-008, phase 4).
`migration/ecommerce-consolidation`: `072f1cc` Phase 2 (11.363) · `076eb6b` Phase 3 (11.364, ADR-0020) · `f20cf22` + `b794b3a` Phase 4 (11.365) · `92b9d76` Phase 5a (11.366) · `4a938bd` Phase 5b (11.367) · `7f87e57` Phase 5c (11.368). Branch `review/m1-reproductions` `eb63bef`.

