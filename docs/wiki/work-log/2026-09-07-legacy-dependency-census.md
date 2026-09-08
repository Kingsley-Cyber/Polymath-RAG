---
title: "WORK LOG — legacy dependency census (migration slice S1)"
change_id: RETRIEVAL-MIGRATION-DEPENDENCY-V1-S1-CENSUS
date: 2026-09-07
owner: governance (repository-only: a read-only scanner + test)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.140
package: scripts/legacy_dependency_census.py, tests/determinism/test_legacy_dependency_census.py, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds the automated, drift-proof dependency census the retirement half of the migration gates on (RETRIEVAL-MIGRATION-DEPENDENCY-V1 §S1). Read-only over repository source: no DB, no models, no network, no fleet, no spend; scripts/ does not trip the execution-bundle fence. It is the successor to the hand-maintained BE-AWARE §10-§11 classifications and the CI-checkable evidence for the goal's 'prove zero legacy readers' step. No runtime/schema/prompt/chunker change."
---

# WORK LOG — legacy dependency census (S1)

## Contract

`RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` §S1 requires a repo inventory of the legacy
semantic symbols/tables/stages, each occurrence classified reader/writer/producer/
config/test/migration, with the gate "no unknown runtime occurrence before retirement
work" (§12 GAP-01, §22, §S16). The migration law is eliminate readers → stop writers →
delete state, so retirement (§S15-§S18) is BLOCKED until the runtime dependency surface
of each legacy symbol is enumerated and classified. The repo had only
`scripts/semantic_lane_census.py` (durable-state LANE liveness for concept/procedure
compilers) — not the code-dependency census.

Owner: `governance` (a read-only scanner + its test; script registry + TREE). Public
contract: `collect() -> list[Occurrence]` + a CLI. Rollback: delete both files + revert
the registry/TREE lines. Verifier: `tests/determinism/test_legacy_dependency_census.py`.

Explicitly OUT of scope: no DB/durable-state read (that is `semantic_lane_census.py`);
no retirement action (this only REPORTS); no runtime/prompt/schema/chunker change.

## Changes

- **`scripts/legacy_dependency_census.py`** (new, read-only): scans repository source
  (`.py/.sql/.yaml/.yml/.toml/.json/.md/.ts/.tsx/.js`, pruning `.git`/venvs/
  `node_modules`/`dist`/`var`/`graphify-out`/caches) for the legacy symbol groups —
  summaries (`retrieval_summaries`/`parent_summaries`/`document_summaries`/
  `corpus_summaries`/`summary_artifacts`/`summary_jobs`), representation kinds
  (`REPRESENTATION_KIND_*_SUMMARY`/`section_summary`/`document_summary`), enrichment+
  latent (`parent_enrichment`/`parent_enrichments`/`LATENT-TRANSFER`/`latent_transfer`),
  `compile_objects`/`concept_artifacts`/`procedure_artifacts`, and compiler title
  context (`POLYMATH_CHAT_COMPILER_TITLES_RANK`/`_compiler_titles`). Word-boundary
  matching (so `document_summary` is not counted inside `document_summaries`). Each
  occurrence gets an owner-layer, a deterministic KIND by path (migration/test/eval/
  doc/config/runtime/script/frontend/other), and a heuristic runtime ROLE
  (writer > producer > reader > reference). Report / `--runtime-only` / `--symbol` /
  `--json`; the tool excludes itself.
- **test + registry + scaffold**: 8 determinism pins; `scripts/README.md` registry
  row; two TREE lines; this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_legacy_dependency_census.py -q  -> 8 passed
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
```

Ground-truth pins: the **GAP-04 legacy reader** is found and classified `reader` at
`workers/workers/doc_profile_worker.py:102` (`SELECT major_concepts FROM
document_summaries`); an **enrichment writer** is found and classified `writer` at
`shared/polymath_shared/latent/runtime.py:90` (`INSERT INTO parent_enrichments`);
migration-kind occurrences all live under `stores/postgres/migrations/`; the tool
excludes itself; the live bridge symbols (`document_summaries`, `parent_enrichments`,
`retrieval_summaries`) each have ≥1 runtime occurrence.

**Census snapshot at admission (HEAD 2c94c31 + this slice):** 3,877 total occurrences;
**332 runtime** (reader 72, writer 43, producer 3, **reference 214**). Top runtime
files: `orchestrator/orchestrator/api/ui.py` (48), `workers/workers/summary_worker_impl.py`
(32), `workers/workers/verify_worker.py` (20), `shared/polymath_shared/candidate_engine.py`
(19), `shared/polymath_shared/summary_runtime.py` (18),
`shared/polymath_shared/corpus_mapping.py` (16) — empirically confirming BE-AWARE §10
(summaries + enrichment are still-read live dependencies).

## Rejected claims

- **Not** a durable-state census: it reads SOURCE, not Postgres; `semantic_lane_census.py`
  owns durable-state liveness.
- **Not** a retirement action: it reports only. No writer stopped, no reader removed.
- **Not** a perfect classifier: ROLE is a best-effort heuristic; the 214 `reference`
  runtime occurrences are the explicit human-review queue the §S1 gate names ("no
  unknown runtime before retirement") — not a claim that all 214 are dead.

## Open contract gaps

- **Plan-vs-repo path discrepancy (recorded):** the plan §3 names the query chain as
  `chat/candidate_engine.py`, `chat/retrieval.py`, `chat/query_compiler.py`, etc., but
  the repo has these under `shared/polymath_shared/` (e.g.
  `shared/polymath_shared/candidate_engine.py`); there is no top-level `chat/` package.
  The census reports the true repo paths. The ledger's §3 reference should be read with
  this mapping; amend the plan body's §3 paths in a later docs pass.
- The 214 `reference` runtime occurrences are unclassified; before any §S15-§S18
  retirement each owning symbol's references must be confirmed non-reading. A future
  `--check` mode could fail CI on a NEW unclassified runtime reference to a
  retirement-scheduled symbol (deferred until a symbol is actually scheduled).
- The census does not yet scan the frontend `.ts/.tsx` `latent` request-flag path
  end-to-end (it matches the symbols but the flag plumbing classification is manual).
