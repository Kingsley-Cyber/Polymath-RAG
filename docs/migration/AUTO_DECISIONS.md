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
