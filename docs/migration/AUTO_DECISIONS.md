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

### M-008 — Phase 4: one evidence id space in governed mode, and the engine's schema byte copies stay

#### Question
(a) The engine names corpus rows `polymath:chunk:<id>`; the adapter runtime shows the agent raw evidence ids in `context.evidence_refs` and enforces citations against them. Which
id does a governed run use? (b) Should the engine's two schema byte copies (`schemas/evidence_packet.json` dialect, `schemas/harness_receipt.schema.json`) be replaced by reads of
`contracts/` now that both live in one checkout?

#### Evidence
(a) The `polymath:` prefix is read in three non-critical places only (`utilization.py:39`, `report.py:202`, `provenance.py:366`, the last with an `or rid in corpus row ids` fallback).
The engine's lineage law compares refs to `corpus_evidence[].id`, whatever they are. (b) The three cross-repo pins (packet schema sha, receipt byte equality, Polymath's own
`validate_receipt`) already execute against THIS repo on every engine-suite run since Phase 2, and `tests/contracts/test_ecommerce_engine_import.py` runs that suite.

#### Applicable migration invariants
INV-3 one authority per responsibility · INV-6 evidence-first · INV-2 · INV-9 reversible.

#### Decision
(a) ONE id space: `knowledge.corpus_evidence` emits the runtime's evidence id; the prefix is dropped at the binding. What the agent is shown is what the engine's law checks and what
Polymath's citation check enforces. (b) Keep the byte copies and their pins: drift now fails a test in this checkout, and the standalone engine still runs. Removing the copies is Phase 12 cleanup.

#### Alternatives rejected
Teaching the agent the prefixed ids (two id spaces, and Polymath's citation check would reject them). Rewriting the engine's row mapping (INV-2: the binding WRAPS `rows_from_packet`).

#### Why this is the smallest reversible choice
One line at the boundary; no engine function changed for it.

#### Reversibility
Delete the line.

#### Validation / proof
`test_adapter_ecommerce_knowledge_intake.py`: ids equal the runtime rows' ids; the id shown in `context.evidence_refs` is the id the lineage law accepted.

#### Affected files / commits
`migration/ecommerce-consolidation` `f20cf22` (register 11.365).

### M-009 — Phase 5 shape: the engine's "field first, hypotheses second" order inside a runtime whose research requires a live hypothesis

#### Question
The engine scouts populations and builds lived situations BEFORE it hypothesizes. The governed runtime cannot: `service._compile_harness_action` returns None without a live hypothesis and a
compiled `research_directive`, and Trail's admission rejects an observation not linked to a LIVE hypothesis (`HYPOTHESIS_LINK_MISSING`, `admission.py:209-211`). How is the engine's behaviour preserved
without changing Trail's semantics (stop condition 5) or adding a second research loop?

#### Evidence
- `_compile_harness_action` reads the NEWEST prior step output that carries the key `research_directive` (`_gather(state.outputs, "research_directive", order)`), whoever produced it. Its
  `search_intents[]` items allow `intent`, `evidence_goal`, `evidence_roles` and a free `template` string (`contracts/adapter/v1/harness_action.schema.json`).
- The governed loop already is hypothesize → research → admit → revise (θ `REVISE` / `SPLIT`) → judge → loop (`M_loop`, 2 loops).
- Engine population code is pure over a state dict: `lived_world.nominate` / `rank_leads` (VOI) / `cards` / `gate`, `executors.channel_queries` (7 channel procedures), `compile_corpus_questions`.
  `registry.compile_registry()` builds the snapshot in memory in ~80 ms; `load_snapshot()` otherwise reads — and on a fresh checkout WRITES — `registry/compiled/`, and never rebuilds a stale file.
- `tests/determinism/test_adapter_runtime_neutrality.py` forbids source and harness names in the runtime and in MANIFESTS; run-time DATA is not constrained.

#### Applicable migration invariants
INV-3 · INV-4 preserve proven behaviour · INV-5 Trail stays the deterministic judge · EXECUTION_PLAN Phase 5 ("Do not improvise queries that existing planners already know how to compile").

#### Decision
Harvest the behaviour onto the EXISTING loop; do not port the engine's order.
1. **Population discovery becomes research PLANNING.** `population.nominate` runs after the primitives are accepted: leads, VOI ranking and per-lead channel queries are step output. First-round hypotheses
   are generated WITH the leads in view, so every scouting query has a live hypothesis to attach to.
2. **Trail says WHAT, the engine says HOW.** A domain operation placed after Trail's `gaps.compile` re-emits the `research_directive` unchanged in its governance fields (gaps, roles, freshness,
   budget, hypothesis ids) and fills each search intent's `template` with the engine's compiled channel query — plus population-lead queries as extra intents under the same roles — within the intent
   cap. The runtime picks it up with NO runtime change. Source names appear only in run-time data, never in a manifest or the runtime.
3. **Evidence cards and lived situations move AFTER admission.** They are computed from ADMITTED observations and use Trail's independence groups as given (the engine's own independence arithmetic
   stays standalone-only). Lived situations then ground `K_revise` (θ `REVISE` / `SPLIT`), which is where the engine's "anchor a hypothesis on a lived cluster" law applies.
4. **Governed operations never touch the engine's registry build cache**: `OPPORTUNITY_RESEARCH_REGISTRY=compile` (set by the binding) makes `registry.load_snapshot()` compile in memory. Registry
   AUTHORITY is unchanged here and is Phase 7.
5. A NEW manifest `config/adapters/ecommerce.product_research.json` carries this shape. `trail.product_discovery.json` is not edited (INV-9).

#### Alternatives rejected
A pre-hypothesis scouting `HARNESS_ACTION` (needs a runtime change AND Trail would refuse its observations) · synthetic "population hypotheses" just to satisfy admission (pollutes the ledger with
things nobody believes) · harness-side query planning only (host-specific; the R2a run showed hosts improvise) · editing Trail's admission rule (stop condition 5).

#### Why this is the smallest reversible choice
No runtime change, no Trail change; a new manifest plus wrapped engine functions.

#### Reversibility
Delete the manifest and the operations.

#### Validation / proof
Per operation: executor tests on the real engine code. Per segment: fixture runs through `service.advance` on the in-memory store with a stub Trail. The pin for point 2: the governance fields of the
directive are byte-equal before and after enrichment, and the issued `HarnessActionV1` validates against its schema.

#### Affected files / commits
Planned on `migration/ecommerce-consolidation`: `adapters/ecommerce/binding.py`, `adapters/ecommerce/python/registry.py` (env switch), `config/adapters/ecommerce.product_research.json`, tests.

### M-010 — Hypotheses onto the ONE ledger, mechanism support from the ledger, and no engine score in governed mode

#### Question
(a) The engine's hypotheses carry bridge fields the ledger's `HypothesisStateV1` does not (`path`, `evidence_boundary`, `hop_refs`, `target_mechanism`, `gaps`, `lived_anchor_ids`). Where do they
live without a second ledger? (b) The engine's product and supply code keys on mechanisms with `status == "SUPPORTED"` — who decides that in governed mode? (c) The engine's `scoring()` computes its own
verdict and `evidence_score` while assembling leads.

#### Evidence
(a) `service._apply_theta` stores the agent's full proposals in the θ step output and adds a parallel `hypothesis_ids`; `hypotheses.generate` builds the ledger state from the fields it knows and
ignores the rest; a manifest step's `output_schema` decides which extra fields an agent may send. (b) The ledger status enum is `proposed, filtered, retained, revised, split, merged, weakened,
strengthened, contradicted, killed, promoted`; only TrailSignal's φ verdicts and θ revisions move it. (c) The join was inlined in `scoring()` (`executors.py:555-575`).

#### Applicable migration invariants
INV-3 one hypothesis ledger · INV-5 Trail is the deterministic judge · the standing rule "No LLM or skill score touches a Trail score".

#### Decision
(a) Bridge fields ride in the θ step OUTPUT beside the ledger ids; the binding zips them (`_ledger_hypotheses`) so every domain hypothesis is addressed by its ledger id. The ledger stays the only hypothesis STATE.
(b) A mechanism is SUPPORTED only while the hypothesis it builds on is `proposed / retained / revised / split / strengthened / promoted` in the ledger; the agent's own `status` is ignored and ineligible
mechanisms are listed. (c) The join is one engine function `join_leads` with no score; governed `supply.leads` emits leads with NO `evidence_score` and NO verdict; standalone `scoring()` is unchanged and is
LEGACY_STANDALONE (non-authoritative in governed mode).

#### Alternatives rejected
Extending `HypothesisStateV1` with domain fields (a contract change that would put ecommerce vocabulary into a neutral runtime) · a domain-side hypothesis store (a second ledger) · trusting the
agent's `status` · carrying the engine score "for information" (it would sit beside Trail's score in the dossier and be read as one).

#### Why this is the smallest reversible choice
No contract or runtime change; one extraction in the engine proven by its own suite.

#### Reversibility
Revert the binding helpers; `scoring()` still works standalone.

#### Validation / proof
`test_adapter_ecommerce_products_supply.py`: claimed-SUPPORTED on a `weakened` hypothesis is refused; `contradicted` yields no lead; leads carry no score; engine suite 609 / 609.

#### Affected files / commits
`migration/ecommerce-consolidation` `7f87e57` (register 11.368).

### M-011 — An agent-answered step may be shown prior step outputs (`materials`), and law loops end in a typed refusal

#### Question
Composing `ecommerce.product_research` showed that an `AGENT_REASON` / `HARNESS_ACTION` step sees only `context` (evidence refs + live hypotheses). The agent could not see a domain law's errors, the
lived clusters it must write situations on, the sourcing plan, or TrailSignal's score records (external-review finding M1-08). And a BRANCH that loops a failed draft back needs an honest end when the
repair budget is spent.

#### Evidence
`service.next_step` already returns a SIBLING `evidence` key beside the step (TG2a) and the API / MCP layers pass the response through unchanged. `max_branch_loops` is one counter shared by every BRANCH.
Gap and failure codes are an open pattern.

#### Applicable migration invariants
INV-8 minimal, additive · existing adapters stay compatible · INV-6 (materials are not evidence) · "A defensible rejection is success. A software / runtime failure is not."

#### Decision
(a) A manifest step the agent / harness answers may declare `config.show` (`name → outputs.<step>.<key>` | `input.<key>`); `next_step` returns them as a sibling `materials` key (`values`, `missing`,
`too_large`, `authority`), bounded at 400 kB, never raised on failure, absent when not declared. The `AdapterStepV1` contract and citation rules are unchanged. (b) A knowledge step's `config.source` may
name a prior step output. (c) Each domain law gets a BRANCH with two arms — failed + budget left → back through reasoning; failed + budget spent → a `law.refuse` domain step that ends the run with a
typed gap carrying the law's own errors. (d) The evidence-gap loop is bounded by the research ROUND the cards operation counts, not by the shared counter, so law repairs cannot starve it.

#### Alternatives rejected
Putting prior outputs INTO `step.context` (changes the step contract and its hash) · letting the run continue with an unlawful draft once the loop budget is spent (a silent fallback) · a per-branch
budget in the runtime (a bigger change than the manifest-level workaround needs).

#### Why this is the smallest reversible choice
One sibling key, one validation rule, one extra scope entry; manifests that do not opt in see nothing.

#### Reversibility
Remove `_materials`; manifests that declare `config.show` still load if the validation line is kept.

#### Validation / proof
`test_adapter_ecommerce_product_research_e2e.py`: the scripted agent answers ONLY from `context` + `materials` and completes the run; the law errors, the ANCHOR cluster and TrailSignal's records are
asserted to have been shown; the negative control ends in `PRODUCT_PORTFOLIO_LAW_UNSATISFIED`. The three pre-existing manifests are byte-identical and their suites green.

#### Affected files / commits
`migration/ecommerce-consolidation` `92efc79` (register 11.369; ADR-0020 addendum).

### M-012 — Phase 6: how the TrailSignal core is embedded (IMPLEMENTED on the migration branch `b766678`; default mode `daemon`)

#### Question
The policy pre-authorizes embedding "subject to dependency / license / source verification". What exactly is imported, how does Polymath reach it, and what must NOT be done in the same change?

#### Evidence
`ADR-TRAIL-EMBEDDING.md` "Imported dependency closure" (AST walk, A41 @ `de64d84`): 16 modules / 6,944 lines; `pydantic`, `typing_extensions`, `packageurl` (the last MISSING from `polymath-v4/.venv`);
MIT; no vendored code in the closure; store port = two async methods; registry compiler reads five known data / config locations; `ResearchOperationService.admitted` is an in-memory dict.
`workers/…/exec_external` reaches Trail only through `TrailMCPClient`, whose transport is injectable (every worker test already injects `httpx.MockTransport`).

#### Applicable migration invariants
INV-5 Trail stays deterministic · INV-3 · INV-9 reversible · stop conditions 1 (licence — clear) and 5 (no semantic change without documented intent).

#### Decision
Embed the EXACT closure byte-identical + its registry data + Trail's own operation tests under `governance/trail/`; one composition module provides the service, a `ResearchStorePort` implementation and an
in-process transport for the unchanged `TrailMCPClient`; `POLYMATH_TRAIL_MODE=embedded|daemon`, default `daemon` until parity is proven. NOT in the same change: trimming the three unrelated contract
modules, fixing D1 / M1-01..03, or reconciling the two registries.

#### Alternatives rejected
Trimming on import (edits Trail source, breaks byte-identity, makes equivalence a claim instead of a fact) · a new in-process client API (forks `exec_external` and its tests) · importing Trail's daemon
composition (pulls Temporal, Postgres adapters and the platform contexts).

#### Why this is the smallest reversible choice
No Trail line edited; one switch; the daemon path keeps working.

#### Reversibility
Set the mode back to `daemon`; delete `governance/trail/`.

#### Validation / proof
The four checks in `ADR-TRAIL-EMBEDDING.md` "Validation". Open: durability of the embedded audit store.

#### Affected files / commits
`migration/ecommerce-consolidation` `b766678` (register 11.370, repo ADR-0021, refactor 0015). Audit-store durability resolved: SQLite behind TrailSignal's own store port.

### M-013 — Phase 8: where the dossier renders, and from what

#### Question
"Reuse the existing AutoResearch renderer. Do not build another." Should a `DOMAIN_OPERATION` render the HTML inside the run, or does the host render from its journal as it does since TG4?

#### Evidence
`report.build_model_from_governed(journal)` + `governed_run.py report` already exist (TG4) and are covered by the engine suite; the worker caps a domain response at 1 MB and a domain operation must not
write files; a dossier is a presentation of a FINISHED run, not a step a later step depends on.

#### Applicable migration invariants
INV-2 reuse before rewrite · EXECUTION_PLAN Phase 8 · the owner's dossier specification is UNCONFIRMED.

#### Decision
Render HOST-SIDE from the journal, as today. Extend only the mapping and the renderer: use the governed result's typed concepts + variations, supplier join, coverage, mechanisms, lived world and registry
snapshot; put one of the five authority labels on every governed block. No `report.render` domain operation.

#### Alternatives rejected
A render step inside the manifest (adds a step nothing depends on, pushes HTML through the run store) · a second renderer in the runtime (forbidden by the plan).

#### Why this is the smallest reversible choice
Two functions in one engine file; the older adapter's result renders exactly as before.

#### Reversibility
Revert the mapping block; the synthesized single concept returns.

#### Validation / proof
`test_adapter_ecommerce_dossier.py` (journal recorded from a complete scripted run, rendered out of process through the engine's CLI) + the ad hoc render of the real-TrailSignal run.

#### Affected files / commits
`migration/ecommerce-consolidation` `a1e886f` (register 11.371).

### M-014 — Phase 7: "one registry" — what was decided here, and what is the owner's

#### Question
Two physical registries now sit in one checkout (TrailSignal's byte-pinned `governance/trail/data`, the engine's mirror `adapters/ecommerce/registry/trailsignal`). Can governed population nomination
simply read TrailSignal's tables, making the mirror deletable?

#### Evidence
Row-level diff (2026-09-20): identical headers on the nine shared tables; the mirror is a STRICT SUPERSET (+10 friction families, +6 niche candidates, +6 seeds); nothing of TrailSignal's is missing from
it. The redirect was tried: the engine's fail-closed registry compiler returns 236 errors on TrailSignal's tables — 236 of TrailSignal's own seeds reference friction families its `friction_library.csv`
never defines; the mirror's 10 extra family rows are exactly those definitions. TrailSignal's own compiler tolerates the gap.

#### Applicable migration invariants
INV-3 one authority · INV-5 embedding changes the deployment boundary only · the standing rule "never tune a registry, gate, threshold or freshness window to pass" · stop condition 5.

#### Decision
Decided here: (1) the engine's compiler check is NOT relaxed; (2) TrailSignal's byte-pinned registry is NOT edited; (3) the state is pinned by `tests/contracts/test_registry_single_authority_state.py` so
it can only change deliberately; (4) `population.nominate` names the registry source it used; (5) an unused hook (`OPPORTUNITY_RESEARCH_REGISTRY_SRC`) is ready. There is ONE GOVERNANCE registry
(TrailSignal's: every admission, judgement, qualification, score); population PRIORS still come from the superset mirror.
NOT decided here — the OWNER'S: upstream the 22 rows into TrailSignal's registry (re-pin `PROVENANCE.json`, delete the mirror, set the hook) or drop them (236 seeds then cannot be nominated). It
changes what the governance registry can project, so it is not an "ordinary migration question".

#### Alternatives rejected
Relaxing the compiler · silently merging the 22 rows into the byte-pinned data · deleting the mirror now (population nomination would lose its registry lane).

#### Why this is the smallest reversible choice
Nothing authoritative changed; the facts are pinned.

#### Reversibility
n/a — no behaviour changed.

#### Validation / proof
The three contract pins; engine suite 609 / 609; `PROVENANCE.json` untouched.

#### Affected files / commits
`migration/ecommerce-consolidation` `4ebcd41` (register 11.372).

### M-015 — The merge window: what was done, what was refused, and how pre-merge uncertainty was removed anyway

#### Question
`AGENT_OPERATING_DOCTRINE.md` §7 names "merge-window validation" as the step after the embedded-Trail dependency. The Postgres-backed adapter suites commit `running` runs, so they may run only when no
worker can claim them (§14). How is the merged code validated, and who performs the production merge?

#### Evidence
Preflight (read-only): 0 open adapter runs; no ingestion ticket or run had moved for 7+ days; 13 worker types healthy on bundle `9cb421b4eeed`. `git merge-tree` = clean. Migration 0061 has no step-type
constraint. After the fleet was stopped, `git merge` into `production` was DENIED by the session's permission gate as a production deploy.

#### Applicable migration invariants
Doctrine §14 live-system discipline · §10 classify failures · the standing rule that a refused action is refused (it is not retried by another route).

#### Decision
(1) The denial stands: the merge was NOT retried or routed around. (2) Service first: the fleet was rebooted at once from the UNCHANGED `production` checkout with the standard boot script. (3) The merge's
uncertainty was removed WITHOUT deploying: a throwaway Postgres (local image, 65 migrations, removed afterwards) ran the Postgres-backed adapter suites and a new real-store complete run against the branch
code. (4) The production merge + ONE bounce + Hermes MCP reload stay with the owner (run them, or permit them).

#### Alternatives rejected
Running the suites against the fleet's database with the fleet stopped but WITHOUT the merge (proves nothing about the branch) · porting every Postgres-backed suite to the in-memory store first (slower,
and it would not test the real store) · any second attempt at the merge.

#### Why this is the smallest reversible choice
Nothing was deployed; the throwaway database is gone; the only live-environment change is one additive pure-Python package.

#### Reversibility
`uv pip uninstall packageurl-python` (nothing live imports it).

#### Validation / proof
Isolated Postgres: 40 / 41 → one DEFECT in this branch found (`materials` leaked through its error path for steps that never opted in) → fixed → 41 / 41; the complete scripted ecommerce run `completed` on
the real store. Side effect recorded: the restore boot made live the already-committed TG4 change `6708301` that was waiting for its next bounce (bundle → `fa72e3b1adde`).

#### Affected files / commits
`migration/ecommerce-consolidation` `82624aa` (dependency) · `e176962` (fix + isolated-Postgres test, register 11.374).

### M-016 — Phase 9: a physical deployed copy stays; it is produced by a script and proven by the engine's own verifier

#### Question
Why does Hermes load a physical copy, and how do we stop maintaining two sources by hand?

#### Evidence
`launchctl list` shows `ai.hermes.gateway` (launchd); launchd processes on this machine cannot read `~/Documents` (standing TCC finding); register 11.274 made `~/.hermes/standalone/opportunity-research` the
engine's home. The engine already ships the parity VERIFIER (`tests/mirror_check.py` → `MIRROR_RECEIPT.json`); only the copy step was manual. Evidence class READ — the gateway was not made to read a
`~/Documents` path.

#### Applicable migration invariants
INV-2 reuse · INV-7 (never deploy private artifacts) · EXECUTION_PLAN Phase 9 (one source, version receipt, parity verification).

#### Decision
Keep the physical copy. `scripts/deploy_ecommerce_skill.py` copies `adapters/ecommerce/` to a target (dry run by default, new / changed files only, never deletes, refuses a dirty source) and then runs the
engine's own verifier, adapted so the receipt names THIS repository's commit and subdirectory. The real deploy to `~/.hermes` happens only after the production merge, from merged `production`.

#### Alternatives rejected
A symlink into `~/Documents` (launchd cannot read it) · a second verifier · `rsync --delete` (destructive on the owner's host).

#### Why this is the smallest reversible choice
One script around an existing verifier; nothing on any host changed.

#### Reversibility
Delete the script; the verifier still works standalone.

#### Validation / proof
`tests/contracts/test_deploy_ecommerce_skill.py` on temp targets; read-only dry run against the real copy: 182 / 190 identical, 8 to write (exactly this migration's adaptations).

#### Affected files / commits
`migration/ecommerce-consolidation` `1d97536` (register 11.375).
