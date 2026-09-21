# Migration Continuation

> Agent-owned restart boundary. Update at every meaningful phase transition. A fresh session continues from this file, the
> controlling documents and the repositories — never from chat history.
>
> **How to operate:** `AGENT_OPERATING_DOCTRINE.md` (owner-authored, 2026-09-20): UNDERSTAND → INSPECT → DECIDE → IMPLEMENT → PROVE → RECORD → CONTINUE; one NOW / one NEXT; evidence classes; do not ask
> "should I proceed?" when the policy authorizes the action. It does not replace the documents below.
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
**Phases 0–8 — DONE on the migration branch; PRE-MERGE VALIDATION DONE (`e176962`).** Repository acceptance (doctrine §17) is met in the worktree: one checkout contains and operates the engine, the embedded TrailSignal
core and the runtime; every Postgres-backed adapter suite passes against it on an isolated real Postgres (41 / 41); the complete scripted run passes on the in-memory store, on the real store, and against the REAL
TrailSignal code.
**NOT done: LOCAL PRODUCTION acceptance.** The production merge was attempted inside a proper window and DENIED by the session's permission gate (M-015). The fleet was restored from unchanged `production`.
**QUEUE — NOW:** the owner merges (or permits the merge) + ONE bounce. **NEXT:** local production acceptance checks. **LATER:** Phase 9 Hermes deploy · Item 2D merge · Phase 10 commerce corpus · Phase 11 live rungs ·
hosted MCP acceptance (doctrine §17).

## Repository State
- polymath-v4 `production`: clean, docs only since `758ff8a`; nothing pushed. **LIVE FLEET (rebooted 2026-09-21T02:01Z from unchanged `production`): 13 worker types healthy, ONE bundle `fa72e3b1adde`** (was
  `9cb421b4eeed`: the boot made live the already-committed TG4 change `6708301` that was waiting for a bounce), MCP :8930 up, 0 open adapter runs. `packageurl-python 0.17.6` is installed in `.venv` (additive).
- **Migration worktree `~/Documents/polymath-rebuild/pmv4-consolidation`, branch `migration/ecommerce-consolidation` @ `1d97536`** — clean; `git merge-tree production` = no conflicts. It has no `.venv`: run with
  `/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python` and `PYTHONPATH=$PWD`.
- **Item 2D is COMMITTED and merge-ready**: worktree `pmv4-atom-scope`, branch `item2/corpus-scoped-atoms` @ `5cd3cc1` = `production` + `migration/ecommerce-consolidation` + Item 2D (`221b95c`, register 11.376); register conflicts already resolved in numeric order; guards 0 / 0 / 0 / READY; 59 tests. Other worktree: `pmv4-m1-repro` (`review/m1-reproductions` @ `eb63bef`, red on purpose). Merged, removable: `pmv4-governed`, `pmv4-packet-text`.
- AutoResearch `main` @ `a7baa66` (public, 3 ahead of GitHub) and Trail A41 @ `de64d84`: untouched. Hermes: deployed skill copy v2.3.0; three skill text files uncommitted (owner's).

## Current HEAD / Branch
`production` (docs only; the branch is NOT merged) · `migration/ecommerce-consolidation` @ `1d97536` (code).

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
**M-017** Item 2D committed on its own branch and pre-merged with `production` + the migration branch so the owner's merge is conflict-free ·
**M-016** the Hermes copy stays physical (launchd cannot read `~/Documents`); it is produced by `scripts/deploy_ecommerce_skill.py` and proven by the engine's own verifier ·
**M-015** the merge was refused by the permission gate and NOT retried; fleet restored from unchanged `production`; merged-code uncertainty removed on an isolated Postgres instead ·
**M-014** ONE governance registry (TrailSignal's); the engine mirror is a strict superset whose 10 extra friction families repair a gap in TrailSignal's own data — NOT merged, NOT relaxed: owner decision ·
**M-013** the dossier renders HOST-SIDE from the journal with the engine's existing renderer; only the mapping + the five authority labels were added ·
**M-012** (IMPLEMENTED `b766678`) embed the EXACT 16-module Trail closure byte-identical under `governance/trail/`, reached through the unchanged `TrailMCPClient` with an in-process transport, `POLYMATH_TRAIL_MODE` default `daemon`; trimming / D1 / registry reconciliation are separate later changes ·
**M-011** `materials`: a manifest may SHOW an agent-answered step selected prior outputs (sibling key, additive); law loops end in a typed `law.refuse` gap; the evidence loop is bounded by research rounds ·
**M-010** domain hypotheses ride in the θ step output addressed by LEDGER id (no second ledger); mechanism support is DERIVED from the ledger status; no engine score or verdict leaves the domain (`join_leads` extracted) ·
**M-009** Phase 5 shape: population discovery = research PLANNING; TrailSignal WHAT / engine HOW via the `research_directive` key (no runtime change); cards + lived situations AFTER admission using Trail's independence groups; governed operations compile the engine registry in memory ·
**M-008** ONE evidence id space in governed mode (the runtime's ids; the engine's `polymath:chunk:` prefix is dropped at the binding); the engine's schema byte copies stay, pinned against this repo.

## Tests Passed
In the migration worktree, database-free, `POLYMATH_PG_DSN` unset, under this repo's interpreter (`/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python`, `PYTHONPATH=$PWD`): engine suite 609 / 609 + `doctor`
(via `test_ecommerce_engine_import.py` 5) · `test_adapter_domain_operation.py` 25 · `…_knowledge_intake` 6 · `…_population_research` 6 · `…_lived_world` 7 · `…_products_supply` 7 · `…_product_research_e2e` 3 ·
`test_trail_core_embedding.py` 4 · `test_adapter_ecommerce_dossier.py` 2 · `test_registry_single_authority_state.py` 3 · the existing contract / evidence-surface / MCP parity / neutrality / purity / R5 audit / MCP server / research-package-removed suites · guards 0 / 0 / 0 / READY.
Under TRAILSIGNAL'S interpreter (`~/trail-signal-os-worktrees/A41/.venv/bin/python`, it has `packageurl`): `test_trail_core_embedded.py` 4 · `test_adapter_ecommerce_product_research_embedded_trail.py` 1 · `test_trail_core_recorded_equivalence.py` 3 — these three
files SKIP with the reason printed under this repo's interpreter. Reusable: `tests/determinism/_adapter_memory_store.py`.

## Known Failures
- NOTHING here is a live run: agent, harness and sources are scripted; TrailSignal is the real code but in process; no real corpus, no real host.
- `packageurl-python` is now declared (`workers/pyproject.toml`) and installed; the 12 TrailSignal-dependent tests pass under this repo's interpreter. Embedded mode is still NOT live (unmerged); default mode is `daemon`.
- TrailSignal-side defects D1, M1-01..03 are in the embedded code, UNFIXED (fixing them = a documented TrailSignal behaviour change that re-pins `PROVENANCE.json`). A zero-admission round would still hit D1.
- `trail.product_discovery` keeps D2–D7 and M1-04..12 (unchanged by design). It also lacks the supply `gaps.compile` step (M1-07 confirmed on real TrailSignal code).
- The Postgres-backed adapter suites were run against the branch on an ISOLATED Postgres: 41 / 41 (one branch defect found and fixed — `materials` opt-in). They have NOT been run in the MAIN checkout because the merge has not happened.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not baselined). Historical baseline fails canary 2 of 9.

## Current Blocker
**The production merge.** It is a production deploy and this session's permission gate refuses it; a refused action is not retried by another route. Everything it depends on is proven. The owner either runs the
block in "Next Exact Action" or permits the session to. Not blocking, recorded for the owner: the 22 drifted registry rows (M-014), the unconfirmed dossier specification.

## Next Exact Action
**NOW — the production merge (owner runs it, or permits it).** From `~/Documents/polymath-rebuild/polymath-v4`, with 0 open adapter runs:
```bash
pgrep -f control.process_supervisor | xargs kill -TERM      # wait for 0 supervisors and no listener on :7200
git merge --no-ff migration/ecommerce-consolidation        # the migration only — OR, to take Item 2D in the same window (it contains the migration branch):
# git merge --no-ff item2/corpus-scoped-atoms
.venv/bin/python scripts/agent_preflight.py && .venv/bin/python scripts/repo_guard.py && .venv/bin/python scripts/wiki_worm.py --check && .venv/bin/python shared/polymath_shared/bundle_integrity.py
mkdir -p /private/tmp/polymath_fleet && nohup bash scripts/boot_polymath.sh > /private/tmp/polymath_fleet/boot.log 2>&1 &
```
Rollback: `git revert -m 1 <merge commit>` + the same boot. No Postgres migration is needed (no step-type constraint in 0061). Keep `POLYMATH_TRAIL_MODE` unset (= `daemon`).
**NEXT — local production acceptance (doctrine §17), after the bounce:** `/ready` true with embedder + reranker; ONE bundle hash; `adapter_list` (MCP :8930 and Server B) shows `ecommerce.product_research` beside the three
existing adapters; an `adapter_start` of `ecommerce.product_research` on corpus `cinema` reaches its first agent step and is then CANCELLED (mechanical, no spend); the full database-free suite passes in the MAIN checkout
(execution path = the live code); Hermes MCP reload. Then rewrite the top of `docs/wiki/plans/CONTINUITY-REPORT.md`.
**LATER (dependency order):** Phase 9 — the MECHANISM is done (`1d97536`, M-016: `scripts/deploy_ecommerce_skill.py`, proven on temp targets; a physical copy stays because the Hermes gateway is a launchd job). After the merge run it for real, from merged `production`: `python3 scripts/deploy_ecommerce_skill.py --target ~/.hermes/standalone/opportunity-research` (dry run: expect 8 files to write) then `--execute`; it is a change to the owner's agent host · Item 2D merged (branch ready, see Repository State) → Phase 10
commerce corpus (10 documents, NEW corpus id; needs Item 2D LIVE — merged + bounced) · Phase 11 live rungs E (mechanical smoke, `POLYMATH_TRAIL_MODE=embedded`) → F (one real ecommerce run; 5–8 staged live runs first) → G (negative control) · hosted MCP
acceptance from OUTSIDE the host (auth, tool discovery, knowledge calls, adapter start / next / submit / status / result, isolation, failure behaviour, a real ecommerce workflow).

## DO NOT REDO
- The comparison, the dependency facts, the registry-drift check, the historical-run inspection (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (never re-run against the shared Postgres).
- The import (Phase 2) and the seam decision (M-007 lists the rejected alternatives with reasons — do not re-litigate).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, in-process import of the engine's flat modules, or import of private ledgers.

## Relevant Commits
`production`: `59a4b60` · `9dfd3c3` · `23d517e` · `758ff8a` owner bundle · `988070a` M-006 + M-007 · `4e627dc` continuation after phases 2–3 · this commit (M-008, phase 4).
`migration/ecommerce-consolidation`: `072f1cc` Phase 2 (11.363) · `076eb6b` Phase 3 (11.364, ADR-0020) · `f20cf22` + `b794b3a` Phase 4 (11.365) · `92b9d76` Phase 5a (11.366) · `4a938bd` Phase 5b (11.367) · `7f87e57` Phase 5c (11.368) · `92efc79` product manifest + complete run in test form (11.369) · `b766678` Phase 6 Trail core embedded + first run against real TrailSignal code (11.370, ADR-0021) · `a1e886f` Phase 8 governed dossier (11.371) · `4ebcd41` Phase 7 registry state (11.372) · `4f89d4c` Phase 6 replay equivalence (11.373) · `82624aa` dependency · `e176962` pre-merge validation + `materials` opt-in fix (11.374) · `1d97536` Phase 9 deploy mechanism (11.375). `item2/corpus-scoped-atoms`: `221b95c` Item 2D (11.376) · `5cd3cc1` contains production + migration. Branch `review/m1-reproductions` `eb63bef`.

