---
title: "WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S0: plan / bootstrap admission"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S0
date: 2026-09-07
owner: governance (owner plan of record 2026-09-07: POLYMATH_NEXT_PHASE_IMPLEMENTATION_PLAN_FINAL_2026-09-07.md)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.129
package: docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md (new), docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-START-HERE.md (new), docs/wiki/plans/CONTINUITY-REPORT.md, docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md, docs/wiki/reports/2026-09-07/README.md, docs/wiki/reports/2026-09-07/UNFINISHED_WORK.md, docs/wiki/reports/2026-09-07/DEPENDENCY_MAP.md, AGENTS.md, scripts/scaffold_polymath_v4.py
architecture_impact: "No runtime code. The owner's next-phase plan of record (document semantic index = one global document profile vNext + one deterministic ParentSkeleton and compact routing MAP per eligible parent + a deterministic Vocabulary Bridge, slices S0–S16) is installed into the living documentation system and hooked from every bootstrap surface a fresh or context-compacted session reads: AGENTS.md, CONTINUITY-REPORT, the dated handoff README, UNFINISHED_WORK, DEPENDENCY_MAP and PLAN-AUTHORITY-REGISTER. The plan supersedes the older U1/U2 items (they fold into slices S12/S15) and stands beside — does not restart — DOCUMENT-PROFILE-V1 (which the plan calls the global-profile scale and extends with the research-index surfaces and the parent-map scale). No chunk identity, graph identity, projection identity or persistence schema changes in this slice."
---

# WORK LOG — DOCUMENT-SEMANTIC-INDEX-V1 slice S0

## Contract

Admit the owner's finalized next-phase plan into the repository's living
documentation system so a fresh or context-compacted session discovers it from
the normal bootstrap, with no reliance on chat history. Exit criterion (plan
§40 S0): "fresh agent can discover this plan from normal bootstrap." No runtime
code in this slice.

Smallest acceptance criteria:

- the plan and its start-here hook exist under `docs/wiki/plans/` with
  wiki-compliant front matter (`last_reviewed`);
- both are declared in `scripts/scaffold_polymath_v4.py::TREE`;
- every AGENTS.md bootstrap surface points to the plan (CONTINUITY-REPORT read
  order + latest checkpoint, the dated handoff README, UNFINISHED_WORK,
  DEPENDENCY_MAP, PLAN-AUTHORITY-REGISTER, AGENTS.md current-state block);
- `agent_preflight`, `repo_guard`, `wiki_worm --check` all pass on the tree.

Owner: governance (repository-only change). Public contract: none (documentation
and file declarations only). Rollback boundary: `git revert` of the S0 commit
removes two additive plan files and reverts additive hook lines; nothing runtime
depends on them.

## Changes

- **Installed the plan of record.** `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`
  (byte-faithful copy of `~/Downloads/POLYMATH_NEXT_PHASE_IMPLEMENTATION_PLAN_FINAL_2026-09-07.md`
  plus a `last_reviewed` and an `installed_as` front-matter line) and
  `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-START-HERE.md` (the coding-agent
  bootstrap hook; `plan_of_record` and its in-body reference repointed to the
  installed path, `last_reviewed` added).
- **Declared both** in `scripts/scaffold_polymath_v4.py::TREE`, and declared this
  work-log entry.
- **CONTINUITY-REPORT.md** (the single bootstrap): read-order line now includes
  the plan + start-here; a new "Latest checkpoint (2026-09-07 — NEXT-PHASE PLAN
  ADMITTED)" block carries the required START-HERE ladder (repository truth →
  finalized next-phase plan → current implementation slice → completed
  dependencies → measured results → unfinished work → exact next action).
- **PLAN-AUTHORITY-REGISTER.md**: row 11.129 records the admission (this slice)
  and the slice ledger S0–S16; the register is the completion contract for the
  phase, one row per slice as it lands (as DOCUMENT-PROFILE-V1 did across
  11.125/11.126/11.128).
- **docs/wiki/reports/2026-09-07/README.md**: the reading sequence and the
  authority table name the plan as the plan of record for the next phase.
- **docs/wiki/reports/2026-09-07/UNFINISHED_WORK.md** and **DEPENDENCY_MAP.md**:
  a header note records that U1 folds into slice S12 (runtime profile/map lane)
  and U2 into slice S15 (QUERY_READY promotion), with S1–S11/S13/S14 the new
  prerequisite slices, and points at the plan for the full graph.
- **AGENTS.md**: the "Current Repository State" block names the plan + start-here
  as the next-phase plan of record.

## Proof

Governance slice — proof is the guards passing on the final tree and the
discovery path resolving:

```
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
```

Discovery check: from `AGENTS.md` §0 → `docs/wiki/plans/CONTINUITY-REPORT.md`
(read-order line + latest checkpoint) → `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-START-HERE.md`
→ `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`; and from
`PLAN-AUTHORITY-REGISTER.md` row 11.129. Every hook path resolves to an existing
file (declared in `TREE`, so `repo_guard`'s declared==actual check is the
machine proof of that).

Baseline recorded for the session: `agent_preflight.py` requires Python ≥ 3.11
(`import tomllib`); the Mac default `python3` is 3.9.6, so it must run under
`.venv/bin/python` / `python3.11` (as CI does with `setup-python 3.11`). Not a
regression — pre-existing environment fact.

## Rejected claims

- **Not** a new architecture. The plan reuses the existing stage DAG, tickets/
  leases, receipts/artifacts, the isolated profile pool, Qdrant/Neo4j/Postgres
  and the two MLX sidecars; it adds a deterministic skeleton, a map compiler, a
  map worker, a projection stage and a runtime lane — not a new mechanism.
- **Not** a restart of DOCUMENT-PROFILE-V1. That work (11.125/11.126/11.128) is
  the global-profile scale; the plan extends it (research-index surfaces,
  fingerprint vNext) and adds the parent-map scale.
- **Not** the old §13 per-parent latent enrichment (`parent-semantic-compiler-v1`,
  1/3/3/4 = 8 latent vectors/parent, build pending). The plan's parent map is
  ONE compact routing signature per parent produced in **packed** Compound Mini
  calls (never one LLM call per parent) with exact identifiers extracted
  deterministically in Python. S16 measures the old parent-semantic work for
  retirement; it is not resurrected here.
- No runtime entrypoint is claimed working by this slice (AGENTS.md §9); S0 is
  documentation admission only.

## Open contract gaps

- The plan is authoritative for this phase, but repository state remains the
  ultimate truth; if code or newer evidence conflicts with a slice, investigate,
  record, update the live plan deliberately, and continue from the corrected
  state (plan §0.1).
- Slices S1–S16 remain to build. Immediate next: **S1 — deterministic
  ParentSkeleton** (`shared/polymath_shared/document_profile/parent_skeleton.py`
  + `tests/determinism/test_parent_skeleton.py`); no prerequisites.
- `pinned_remote_head_for_planning` in the plan is `fa49448`; if HEAD moves,
  reconcile per plan §0.2 before applying any line-anchored change.
