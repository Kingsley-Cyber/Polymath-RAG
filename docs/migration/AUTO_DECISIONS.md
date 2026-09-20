# Auto Decisions

> Agent-owned. Material autonomous decisions only (architecture, governance, compatibility, authority, migration seams).

## M-001 — Do Phase 0 (read-only) although two controlling documents were not supplied

### Question
The document-bootstrap task says to install `MIGRATION_POLICY.md` and `EXECUTION_PLAN.md` "from the exact owner-authored content
supplied with this task", then begin Phase 0 from the plan. No content for either file accompanied the task, and neither file exists on disk.

### Evidence
Searched `polymath-v4/docs/migration/`, both other repos, `handoff-drafts/`, `~/Downloads`, `~/Desktop` (2026-09-20): absent.
`BOOTSTRAP_CONTEXT.md` was supplied earlier and is installed. The same task defines "Initial Phase 0 work" explicitly
(repository truth for four locations, tool discovery, a factual `CAPABILITY_MAP.md`).

### Applicable migration invariants
Owner-authored controlling files are installed faithfully, never invented. `/polymath-bootstrap`: a missing policy or plan is a
stop for AUTONOMOUS execution, because the policy defines the stop conditions.

### Decision
Do not write or paraphrase the two missing files. Create the agent-owned operational files and perform exactly the Phase 0 work
the task itself spells out (read-only discovery + documents). Take no code, manifest, contract, Trail, Hermes or fleet action.

### Alternatives rejected
Drafting the policy / plan myself (they are owner-authored and constitutional). Stopping entirely (the Phase 0 scope is explicit,
read-only and does not depend on the missing text).

### Why this is the smallest reversible choice
Documents only, all under `docs/migration/`; nothing executes.

### Reversibility
`git revert` of the bootstrap commit.

### Validation / proof
Static guards = 0; `/polymath-bootstrap` verified to honour the doc set (10 of 10 required behaviours present).

### Affected files / commits
`docs/migration/*`, `scripts/scaffold_polymath_v4.py`, `docs/wiki/plans/CONTINUITY-REPORT.md` — the document-bootstrap commit.

## M-002 — Where the migration documents and future migration code live under the repo's own rules

### Question
polymath-v4 enforces its own discipline (`repo_guard`: every file declared in the scaffold `TREE`; `wiki_worm`: front matter for
`docs/wiki/**`; the stale-bundle fence on `shared/`, `workers/`, `control/`). How does `docs/migration/` coexist with it?

### Evidence
`repo_guard` passed with `docs/migration/*.md` declared in `scripts/scaffold_polymath_v4.py`; `wiki_worm` ignores paths outside
`docs/wiki`. Docs commits on `production` are fence-safe; code under the fence set quarantines the live fleet until one bounce.

### Applicable migration invariants
Do not reorganize unrelated Polymath documentation. Use a migration branch / worktree if repository policy calls for one.

### Decision
Documents: committed directly on `production` (docs only), each declared in the scaffold `TREE`, no front matter.
Code: every migration code change happens in a dedicated worktree / branch and reaches `production` only as a deliberate merge;
new top-level packages (`adapters/`, `governance/`) sit outside the fence set.

### Alternatives rejected
A docs branch (adds merge overhead for fence-safe files). Putting migration docs under `docs/wiki` (would force wiki front matter and mix two document systems).

### Why this is the smallest reversible choice
No existing file moves; one `TREE` line per new file.

### Reversibility
Revert the commit; remove the `TREE` lines.

### Validation / proof
`agent_preflight` 0 · `repo_guard` 0 · `wiki_worm --check` 0 · `bundle_integrity` READY.

### Affected files / commits
`scripts/scaffold_polymath_v4.py`; commits `23d517e`, `c583dc6`, and the document-bootstrap commit.
