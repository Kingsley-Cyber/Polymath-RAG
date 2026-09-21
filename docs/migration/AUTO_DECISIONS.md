# Autonomous Migration Decisions

> Agent-owned. Material autonomous decisions only (architecture, governance, compatibility, authority, migration seams).

## Decision template
`### M-XXX — <title>` with `####` Question · Evidence · Applicable migration invariants · Decision · Alternatives rejected ·
Why this is the smallest reversible choice · Reversibility · Validation / proof · Affected files / commits.

## Decisions

### M-001 — Do Phase 0 (read-only) although two controlling documents were not supplied — RESOLVED 2026-09-20: the owner's bundle supplied them

#### Question
The document-bootstrap task says to install `MIGRATION_POLICY.md` and `EXECUTION_PLAN.md` "from the exact owner-authored content
supplied with this task", then begin Phase 0 from the plan. No content for either file accompanied the task, and neither file exists on disk.

#### Evidence
Searched `polymath-v4/docs/migration/`, both other repos, `handoff-drafts/`, `~/Downloads`, `~/Desktop` (2026-09-20): absent.
`BOOTSTRAP_CONTEXT.md` was supplied earlier and is installed. The same task defines "Initial Phase 0 work" explicitly
(repository truth for four locations, tool discovery, a factual `CAPABILITY_MAP.md`).

#### Applicable migration invariants
Owner-authored controlling files are installed faithfully, never invented. `/polymath-bootstrap`: a missing policy or plan is a
stop for AUTONOMOUS execution, because the policy defines the stop conditions.

#### Decision
Do not write or paraphrase the two missing files. Create the agent-owned operational files and perform exactly the Phase 0 work
the task itself spells out (read-only discovery + documents). Take no code, manifest, contract, Trail, Hermes or fleet action.

#### Alternatives rejected
Drafting the policy / plan myself (they are owner-authored and constitutional). Stopping entirely (the Phase 0 scope is explicit,
read-only and does not depend on the missing text).

#### Why this is the smallest reversible choice
Documents only, all under `docs/migration/`; nothing executes.

#### Reversibility
`git revert` of the bootstrap commit.

#### Validation / proof
Static guards = 0; `/polymath-bootstrap` verified to honour the doc set (10 of 10 required behaviours present).

#### Affected files / commits
`docs/migration/*`, `scripts/scaffold_polymath_v4.py`, `docs/wiki/plans/CONTINUITY-REPORT.md` — the document-bootstrap commit.

### M-002 — Where the migration documents and future migration code live under the repo's own rules

#### Question
polymath-v4 enforces its own discipline (`repo_guard`: every file declared in the scaffold `TREE`; `wiki_worm`: front matter for
`docs/wiki/**`; the stale-bundle fence on `shared/`, `workers/`, `control/`). How does `docs/migration/` coexist with it?

#### Evidence
`repo_guard` passed with `docs/migration/*.md` declared in `scripts/scaffold_polymath_v4.py`; `wiki_worm` ignores paths outside
`docs/wiki`. Docs commits on `production` are fence-safe; code under the fence set quarantines the live fleet until one bounce.

#### Applicable migration invariants
Do not reorganize unrelated Polymath documentation. Use a migration branch / worktree if repository policy calls for one.

#### Decision
Documents: committed directly on `production` (docs only), each declared in the scaffold `TREE`, no front matter.
Code: every migration code change happens in a dedicated worktree / branch and reaches `production` only as a deliberate merge;
new top-level packages (`adapters/`, `governance/`) sit outside the fence set.

#### Alternatives rejected
A docs branch (adds merge overhead for fence-safe files). Putting migration docs under `docs/wiki` (would force wiki front matter and mix two document systems).

#### Why this is the smallest reversible choice
No existing file moves; one `TREE` line per new file.

#### Reversibility
Revert the commit; remove the `TREE` lines.

#### Validation / proof
`agent_preflight` 0 · `repo_guard` 0 · `wiki_worm --check` 0 · `bundle_integrity` READY.

#### Affected files / commits
`scripts/scaffold_polymath_v4.py`; commits `23d517e`, `c583dc6`, and the document-bootstrap commit.

### M-003 — Two owner-authored bootstrap contexts: which one controls

#### Question
The owner pasted a long `BOOTSTRAP_CONTEXT` in chat (installed in commit `23d517e`), then supplied `polymath_migration_bootstrap.zip` whose
`BOOTSTRAP_CONTEXT.md` is a compact rewrite. The bundle README says to copy its files into `docs/migration/`.

#### Evidence
Bundle file timestamps 2026-09-20 23:42 (later than the paste). The compact set moves tool / token / test discipline, privacy and stop
conditions into `MIGRATION_POLICY.md`. NOT restated anywhere in the bundle: the starting repository states, the target tree
`adapters/ecommerce/` + `governance/trail/`, the explicit graph-preservation wording, the Trail import list, the report acceptance list.

#### Applicable migration invariants
Controlling documents are installed faithfully and not silently rewritten; preserve history.

#### Decision
The bundle's three controlling files are installed byte-identical and CONTROL. The earlier text is kept, unedited in substance, as
`BOOTSTRAP_CONTEXT_EXTENDED.md` with a header saying the bundle wins on any difference. The agent-owned files already populated from
evidence are kept (the bundle's copies are empty skeletons with the same headings); `AUTO_DECISIONS.md` adopts the bundle's title and template.

#### Alternatives rejected
Overwriting and relying on git history only (the target tree and the report list would drop out of a fresh session's reading path).
Merging the two texts into one file (that would be the agent rewriting an owner-authored controlling document).

#### Why this is the smallest reversible choice
One rename, five copied files, no owner text altered.

#### Reversibility
`git revert`; the zip stays at `~/Documents/polymath-rebuild/polymath_migration_bootstrap.zip`.

#### Validation / proof
`cmp` = byte-identical for all five installed files; static guards = 0.

#### Affected files / commits
`docs/migration/{MIGRATION_POLICY,BOOTSTRAP_CONTEXT,EXECUTION_PLAN,README,NEW_SESSION_BOOTSTRAP_PROMPT,BOOTSTRAP_CONTEXT_EXTENDED}.md` — the consolidation commit.

### M-004 — Baseline tests are established from today's existing runs, not re-run

#### Question
Phase 0 says "establish baseline tests once". Re-running the polymath determinism suite touches the Postgres the live fleet polls.

#### Evidence
Code is unchanged since the runs: polymath-v4 `tests/determinism` + `tests/contracts` ran today at `a125103` (only docs have changed since) → 8 failures,
none in adapter / atom / activation code: 3 attributed pre-existing (`test_query_receipts::test_all_three_query_handlers…`,
`test_chat_runtime::test_compiler_on_drives…`, `test_chat_hygiene::test_live_transform_turn_skips_retrieval…`), 5 not yet attributed
(`test_chat_synthesis…[brainrot_transform]`, `test_document_profile_stage…`, `test_fact_endpoint_eligibility…`, `test_graph_lifecycle_v2…`,
`test_killchain_pass2…`). AutoResearch `tests/run_all.py` = 609 checks + doctor green at `a7baa66` today. Trail A41: no baseline run yet.

#### Applicable migration invariants
Test discipline: smallest test that resolves the uncertainty; broad suites at phase gates only. Skill law: know what a test run touches.

#### Decision
Those results ARE the Phase 0 baseline. Trail's research-operation tests are baselined at Phase 6, immediately before the embed, where the
equivalence question actually arises.

#### Alternatives rejected
Re-running everything now (repeats unchanged suites and touches the shared database for no new information).

#### Why this is the smallest reversible choice
No action; a later gate can always re-run.

#### Reversibility
n/a.

#### Validation / proof
Saved outputs: branch `review/m1-reproductions` `tests/review_m1/results/`; M1 verification work-log.

#### Affected files / commits
none.

### M-005 — The commerce corpus: the policy's pre-authorization versus the earlier "drop ecom meta" instruction

#### Question
Register 11.359 records the owner's word "DELETE ECOM META ITS NOT PART OF MY CURRENT CORPUS. DROP IT FROM PLAN." `MIGRATION_POLICY.md` (later, controlling)
pre-authorizes: "Do not restore old indexes. Reconstruct from preserved sources using current V4 ingestion. Prove corpus isolation before activating
ecommerce beside other corpora." Do these contradict (stop condition 4)?

#### Evidence
The owner clarified afterwards: "Treat the earlier instruction to ignore ecommerce as specific to the cinema mechanical smoke run, not the product's
overall purpose." The policy is dated after both. Preserved sources exist (verified 2026-09-20, read-only): 11 content-addressed blobs of the former v4
corpus in `~/PolymathRuntime/polymath-v4/spool/` (sha-verified, 6.2 MiB) and the 117-file markdown library they came from in
`~/PolymathRuntime/volumes/ingest-files/9dc27284-5012-44c0-84f9-864bb8193062/` (71 MB). Old indexes no longer exist. Corpus isolation (Item 2D) is
implemented but parked, uncommitted, in worktree `pmv4-atom-scope`.

#### Applicable migration invariants
INV-7 privacy (books are third-party texts: they are INGESTED, never committed to the repo). EXECUTION_PLAN Phase 10. Skill law: no second corpus before atom search is corpus-scoped.

#### Decision
No contradiction: evidence resolves it. The 11.359 drop removed `ecom-meta-v1` from the OLD plan's TG5; the policy governs this migration. Phase 10 will
reconstruct "the smallest useful preserved ecommerce source set" (the 10-document set first, not all 117) through current V4 ingestion, under a NEW
corpus id, AFTER Item 2D is merged and its isolation proof passes. Nothing is ingested before Phase 10.

#### Alternatives rejected
Stopping to ask (the policy explicitly pre-authorizes this). Restoring old indexes (forbidden, and they are gone).

#### Why this is the smallest reversible choice
A new corpus id is removable with `polymath_delete_corpus`; no existing corpus is touched.

#### Reversibility
Delete the new corpus; `cinema` unaffected once isolation is proven.

#### Validation / proof
Phase 10 gate: profiles, parents / chunks, embeddings, atoms, graph, provenance, corpus-scoped retrieval.

#### Affected files / commits
none yet.

### M-006 — Phase 2 import: what came across, what was left out, and the engine's earlier life in this repo

#### Question
How is the engine imported "additively, no redesign on import" while INV-7 holds, and does re-importing it contradict register 11.274, which REMOVED it from this repo?

#### Evidence
`git archive a7baa66` of `TRAIL_AGENT_AUTORESEARCH` exports TRACKED files only, so nothing that repo git-ignores (run state, candidates, exports, compiled registry, review
patches, the private field-evidence ledger, SQLite) can ride along. History: the engine lived here as `research/` (207 tracked files) until commit `d118078` (register 11.274,
HARNESS-RESEARCH-MIGRATION-V1 O6, 2026-09-15) retired it and preserved it as the standalone Hermes skill at `~/.hermes/standalone/opportunity-research` — which also answers
`CAPABILITY_MAP.md` Unknown 4: the deployed copy exists because O6 made it the engine's home, not because of a verified launchd / TCC restriction (that remains untested until Phase 9).
The O6 dead-path guard `tests/contracts/test_research_package_removed.py` forbids a `research/` directory, the six `research_*` MCP tools and the `research-harness` workflow.

#### Applicable migration invariants
INV-2 reuse before rewrite · INV-7 privacy by default · INV-8 additive · policy "Consolidation: authorized; `polymath-v4` is the destination".

#### Decision
Import to `adapters/ecommerce/` with the source layout intact (193 files). Exclude `MIRROR_RECEIPT.json`, `.github/`, and `registry/friction_library.upstream.patch` (its diff
header carries a machine-local home path). One adaptation only: the engine suite's three cross-repo pins compare against the CONTAINING repo instead of a sibling checkout — they
were falling back to a pass. 11.274 is not contradicted: the policy (2026-09-20, later and controlling) authorizes consolidation, and the O6 guard stays green because the old
path is NOT revived — no `research/`, no `research_*` MCP tools; the engine is bound through the adapter runtime (M-007).

#### Alternatives rejected
Copying the working directory (would carry git-ignored private artifacts). Restoring `research/` from history (older than v2.3.0, and revives the retired path). Sanitising the
patch file in place (INV-7: "if uncertain, exclude and document"; its ten rows already sit in `registry/` and their fate is Phase 7).

#### Why this is the smallest reversible choice
One directory, no importer, no runtime package touched.

#### Reversibility
`git rm -r adapters/ecommerce` + drop the `TREE` block and the guard prefixes; nothing else references it.

#### Validation / proof
Engine suite 609 / 609 + `doctor` 0 in the new location under the Hermes interpreter AND this repo's `.venv` (606 + 3 skipped before the adaptation); 9 contract pins green with a
negative control; privacy scan clean; guards 0 / 0 / 0 / READY. `WORKTREE_INTEGRATION_PROVEN`.

#### Affected files / commits
Branch `migration/ecommerce-consolidation` `072f1cc` (register 11.363, work-log `2026-09-20-consolidation-phase2-engine-import.md`).

### M-007 — The domain binding seam: how a manifest-defined adapter invokes substantial domain Python

#### Question
`BOOTSTRAP_CONTEXT.md` names this as the one architectural seam that may need implementation. What is the smallest extension of the EXISTING runtime that lets a manifest step run
ecommerce domain code, with no second scheduler, state machine or ledger, existing adapters unchanged, and domain failures mapped into existing typed semantics?

#### Evidence
- `service.advance` already takes an injected `executors: dict[step_type → Executor]`; an executor exception becomes a typed `STEP_EXECUTOR_ERROR` failure and an executor `gap`
  becomes a typed `terminal_gap` (`service.py:380-410`). Gap / failure codes are an open `^[A-Z][A-Z0-9_]{2,60}$` pattern. `BRANCH` predicates read step outputs, so a domain
  validator's verdict can already route a run back to reasoning.
- The step-type vocabulary is CLOSED and pinned: `contracts.py:16` + four schema enums + `tests/contracts/test_adapter_contract_v1.py:18-44` (`set(node) == STEP_TYPES`).
- `EXTERNAL_OPERATION` is Trail-specific end to end: schema `external.system` enum `["trailsignal"]`, `exec_external` builds Trail payloads, checks Trail response identity,
  feeds φ verdicts to the ledger, and spends the `max_external_operations` budget.
- `tests/determinism/test_adapter_runtime_neutrality.py`: the runtime, the worker AND every manifest may not name an adapter id, a domain word, a source or a harness.
- The engine is ~40 FLAT top-level modules (`executors`, `report`, `store`, `bridge`, …) that import each other by bare name after `sys.path.insert(0, python/)`; it passes its
  suite under this repo's interpreter.

#### Applicable migration invariants
INV-1 ecommerce first · INV-2 · INV-3 one authority per responsibility · INV-5 Trail stays deterministic and separate · INV-8 · EXECUTION_PLAN Phase 3 requirements.

#### Decision
One new AUTOMATIC step type, `DOMAIN_OPERATION`, executed by the existing worker through the existing `EXECUTORS` table:
- manifest step `config`: `{"domain": "<dir under adapters/>", "operation": "<dotted id>", "inputs": {"<name>": "<dotted path over input / outputs / context>"}}`;
- the executor runs `<repo>/adapters/<domain>/binding.py` OUT OF PROCESS with the worker's interpreter, one JSON request on stdin, one JSON response on stdout, a hard timeout;
  `domain` must match `^[a-z][a-z0-9_]{1,40}$` and the binding file must exist inside the repo's `adapters/` directory;
- response `{"ok": true, "output": {...}}` becomes the step output; `{"ok": false, "code", "message"}` becomes a typed gap with the domain's own code; a crash, a timeout or an
  unparseable response raises, which the runtime already records as `STEP_EXECUTOR_ERROR`;
- the output carries `_domain` lineage (domain, operation, sha256 of the binding file) — the engine is read from disk per call and is not part of the worker bundle hash;
- `adapters/ecommerce/binding.py` holds ONE table `OPERATIONS: dict[str, callable]` that wraps existing engine functions. No engine function is rewritten to fit.
No new budget counter (`max_steps` bounds it), no ledger access from domain code, no change to `service.py`, `transitions.py`, `store.py` or any existing manifest.

#### Alternatives rejected
- `EXTERNAL_OPERATION` with `system=<domain>`: mixes domain planning into the executor that enforces Trail identity and LAW 1, and spends Trail's budget (INV-3, INV-5).
- Overloading `VALIDATE`: it is documented "closed and schema-free"; ranking and planning are not validation.
- In-process import: puts ~40 generic top-level module names (`store`, `report`, `executors`) on the worker's `sys.path`, or forces a package rewrite of every engine import
  (a redesign on import). It would also put the engine inside the stale-bundle fence.
- Host-side only (the agent runs the engine as a tool): not governed, not deterministic, and fails the Phase 3 gate ("executes through the existing adapter runtime").
- A plugin SDK / entry-point registry: speculative (INV-1).

#### Why this is the smallest reversible choice
One enum value, one executor function, one thin file per domain. Existing manifests stay valid (adding an enum member is backward compatible within v1).

#### Reversibility
Remove the enum value, the executor and `binding.py`; no stored run uses the type until an ecommerce manifest does.

#### Validation / proof
The contract pin `test_adapter_contract_v1.py` is a closed-vocabulary pin: it is EXTENDED by exactly one member in the same slice as the ADR — a declared contract change, not a
weakened assertion; every other existing test stays untouched and green. New tests: manifest validation of the step type; the executor against a real engine operation (the
executed path asserted to be this worktree); typed gap on a domain refusal; typed failure on a crash / timeout / malformed response; path-traversal refusal; the neutrality test
still green. Gate: a real ecommerce domain operation runs through `service.advance` with the real executor table.

#### Affected files / commits
Planned: `shared/polymath_shared/adapter/{contracts,manifest}.py`, four `contracts/adapter/v1/*.schema.json` enums, `workers/workers/adapter_step_worker.py`,
`adapters/ecommerce/binding.py`, ADR-0020 + changelog + refactor entry + `architecture/dependencies.json` owner for `adapters/`. Fence-set files change only in the migration
worktree; a bounce is needed only when the branch is merged.
