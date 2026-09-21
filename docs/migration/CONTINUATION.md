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
**Phases 0–6 — DONE on the migration branch.** `072f1cc` import · `076eb6b` seam (ADR-0020) · `f20cf22` evidence intake · `92b9d76` / `4a938bd` / `7f87e57` domain operations · `92efc79` product
manifest + complete scripted run + negative control · **`b766678` Phase 6: TrailSignal's core embedded byte-identical under `governance/trail/` (ADR-0021) and the FIRST COMPLETE RUN AGAINST THE REAL
TRAILSIGNAL CODE — `completed`, a defensible rejection.**
**NEXT: Phase 8 — the dossier (reuse the engine's renderer), then Phase 7 (one registry), then the merge window.** All code on branch `migration/ecommerce-consolidation` (worktree
`../pmv4-consolidation`), NOT merged; the live fleet is untouched; nothing pushed.

## Repository State
- polymath-v4 `production`: clean, docs only since `758ff8a`; 130+ commits ahead of `origin/main`, nothing pushed.
- **Migration worktree `~/Documents/polymath-rebuild/pmv4-consolidation`, branch `migration/ecommerce-consolidation`** = `production@758ff8a` + `072f1cc` (Phase 2) + `076eb6b` (Phase 3). Clean. It has no `.venv`: run with `/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python` and `PYTHONPATH=$PWD`.
- Parked worktrees: `pmv4-atom-scope` (Item 2D, UNCOMMITTED, 7 files) · `pmv4-m1-repro` (`review/m1-reproductions` @ `eb63bef`, red on purpose). Merged, removable: `pmv4-governed`, `pmv4-packet-text`.
- AutoResearch: `main` @ `a7baa66` (v2.3.0), clean, 3 commits ahead of GitHub. PUBLIC. Still the engine the Hermes skill runs (the import is a copy; nothing was removed — INV-9).
- Trail: `~/trail-signal-os-worktrees/A41` @ `de64d84`, clean. Untouched.
- Hermes: deployed copy `standalone/opportunity-research` v2.3.0; three skill text files uncommitted (owner's commit).

## Current HEAD / Branch
`production` (docs) · `migration/ecommerce-consolidation` @ `b766678` (code).

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
On the migration branch, ONE checkout now holds all three parts: `adapters/ecommerce/` (the engine + `binding.py`, 14 operations, out of process) · `governance/trail/` (TrailSignal's 16-module research
core + registry data, byte-identical to A41 @ `de64d84`, + `embedded.py`: service, SQLite store port, in-process transport) · the EXISTING Polymath adapter runtime with `DOMAIN_OPERATION`, the `materials` sibling key
and `POLYMATH_TRAIL_MODE=embedded|daemon` (default `daemon`). `config/adapters/ecommerce.product_research.json` (54 steps) composes them. Domain code computes and never owns state; TrailSignal alone admits, judges,
qualifies and scores; the three pre-existing manifests are byte-identical to `production`. Live system: unchanged (still the TrailSignal daemon).

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
**M-012** (IMPLEMENTED `b766678`) embed the EXACT 16-module Trail closure byte-identical under `governance/trail/`, reached through the unchanged `TrailMCPClient` with an in-process transport, `POLYMATH_TRAIL_MODE` default `daemon`; trimming / D1 / registry reconciliation are separate later changes ·
**M-011** `materials`: a manifest may SHOW an agent-answered step selected prior outputs (sibling key, additive); law loops end in a typed `law.refuse` gap; the evidence loop is bounded by research rounds ·
**M-010** domain hypotheses ride in the θ step output addressed by LEDGER id (no second ledger); mechanism support is DERIVED from the ledger status; no engine score or verdict leaves the domain (`join_leads` extracted) ·
**M-009** Phase 5 shape: population discovery = research PLANNING; TrailSignal WHAT / engine HOW via the `research_directive` key (no runtime change); cards + lived situations AFTER admission using Trail's independence groups; governed operations compile the engine registry in memory ·
**M-008** ONE evidence id space in governed mode (the runtime's ids; the engine's `polymath:chunk:` prefix is dropped at the binding); the engine's schema byte copies stay, pinned against this repo.

## Tests Passed
In the migration worktree, database-free, `POLYMATH_PG_DSN` unset, under this repo's interpreter (`/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python`, `PYTHONPATH=$PWD`): engine suite 609 / 609 + `doctor`
(via `test_ecommerce_engine_import.py` 5) · `test_adapter_domain_operation.py` 25 · `…_knowledge_intake` 6 · `…_population_research` 6 · `…_lived_world` 7 · `…_products_supply` 7 · `…_product_research_e2e` 3 ·
`test_trail_core_embedding.py` 4 · the existing contract / evidence-surface / MCP parity / neutrality / purity / R5 audit / MCP server / research-package-removed suites · guards 0 / 0 / 0 / READY.
Under TRAILSIGNAL'S interpreter (`~/trail-signal-os-worktrees/A41/.venv/bin/python`, it has `packageurl`): `test_trail_core_embedded.py` 4 · `test_adapter_ecommerce_product_research_embedded_trail.py` 1 — these two
files SKIP with the reason printed under this repo's interpreter. Reusable: `tests/determinism/_adapter_memory_store.py`.

## Known Failures
- NOTHING here is a live run: agent, harness and sources are scripted; TrailSignal is the real code but in process; no real corpus, no real host.
- `packageurl` is missing from `polymath-v4/.venv` → embedded mode cannot run in the fleet until it is added to `pyproject.toml` and installed (merge window). Default mode is `daemon`.
- TrailSignal-side defects D1, M1-01..03 are in the embedded code, UNFIXED (fixing them = a documented TrailSignal behaviour change that re-pins `PROVENANCE.json`). A zero-admission round would still hit D1.
- `trail.product_discovery` keeps D2–D7 and M1-04..12 (unchanged by design). It also lacks the supply `gaps.compile` step (M1-07 confirmed on real TrailSignal code).
- NOT RUN on the branch (deliberately): the Postgres-backed adapter suites (`test_adapter_evidence_boundary`, `_product_discovery_loop`, `_service_store`, `_harness_action`). Run them in the merge window, fleet drained.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not baselined). Historical baseline fails canary 2 of 9.

## Current Blocker
None. (The commerce corpus is pre-authorized by the policy and scheduled for Phase 10 — M-005. Item 2D must be merged before it.)

## Next Exact Action
**Phase 8 — the dossier.** Work in `../pmv4-consolidation`. Reuse the engine's renderer; do NOT build another.
1. Read `adapters/ecommerce/python/report.py` (ReportModel + HTML renderer) and `governed_run.py` (TG4: it already maps a GOVERNED journal / result to the report model — that mapping is the starting point). Find what
   the model needs and what `ecommerce.product_research`'s RESULT now offers beyond the old one: `product_concepts` + variations, `leads`, `sourcing_coverage`, `supplier_candidates`, `lived_situations`,
   `lived_clusters`, `participant_cards`, `population_leads`, `lenses`, `corpus_questions`, `qualifications`, `trail_scores`, `score_refusals`, `evidence_admissions`, lineage.
2. Bind `report.render` in `binding.py` (input = the run result + the step journal; output = HTML text + a report-model JSON). The five authority labels are mandatory and must be visible per block: POLYMATH
   KNOWLEDGE · LIVE-WORLD OBSERVATION · AGENT INFERENCE · TRAIL DETERMINATION · TRAIL REGISTRY. A domain operation must not write files: return the HTML as output (mind `DOMAIN_OUTPUT_MAX_BYTES` = 1 MB in the worker)
   or render host-side from the result. Decide and record (M-013).
3. Gate: a fixture-driven report renders the complete product-oriented structure — feed it the RESULT of the scripted run and of the real-TrailSignal run (the rejection must read as a rejection: refusals, unmet
   gates, unsourced concepts, remaining unknowns).
**Then Phase 7** (one registry: the engine's `adapters/ecommerce/registry/` vs `governance/trail/data/` — drift +6 seeds / +10 friction families / +6 niche candidates; Trail's is the governance authority),
**then the merge window**: add `packageurl`; port TrailSignal's operation tests + recorded-envelope equivalence; drain → merge → Postgres-backed suites → ONE bounce → Hermes MCP reload; **then** Phase 9 (Hermes
deployment from this checkout), Phase 10 (commerce corpus — Item 2D must be merged first), Phase 11 live rungs E / F / G.

## DO NOT REDO
- The comparison, the dependency facts, the registry-drift check, the historical-run inspection (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (never re-run against the shared Postgres).
- The import (Phase 2) and the seam decision (M-007 lists the rejected alternatives with reasons — do not re-litigate).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, in-process import of the engine's flat modules, or import of private ledgers.

## Relevant Commits
`production`: `59a4b60` · `9dfd3c3` · `23d517e` · `758ff8a` owner bundle · `988070a` M-006 + M-007 · `4e627dc` continuation after phases 2–3 · this commit (M-008, phase 4).
`migration/ecommerce-consolidation`: `072f1cc` Phase 2 (11.363) · `076eb6b` Phase 3 (11.364, ADR-0020) · `f20cf22` + `b794b3a` Phase 4 (11.365) · `92b9d76` Phase 5a (11.366) · `4a938bd` Phase 5b (11.367) · `7f87e57` Phase 5c (11.368) · `92efc79` product manifest + complete run in test form (11.369) · `b766678` Phase 6 Trail core embedded + first run against real TrailSignal code (11.370, ADR-0021). Branch `review/m1-reproductions` `eb63bef`.

