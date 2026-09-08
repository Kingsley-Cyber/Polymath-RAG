---
title: "WORK LOG — vNext readiness report (migration slice S11, report-only)"
change_id: RETRIEVAL-MIGRATION-DEPENDENCY-V1-S11-READINESS
date: 2026-09-07
owner: governance (repository-only: a read-only verifier VIEW + test)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.141
package: scripts/vnext_readiness_report.py, tests/determinism/test_vnext_readiness_report.py, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "Adds the report-only vNext parent-map backfill-completeness VIEW (RETRIEVAL-MIGRATION-DEPENDENCY-V1 §2/§16/§19; §S11 'report-only first'). Reads durable state only (documents/chunks/runs + the 0054 parent-map tables); no writes, no models, no network, no availability effect; scripts/ is fence-free. It is a readiness VIEW, not a scheduler, and does not redefine query_ready — it quantifies the generation-invariant gap the owner-gated backfill must close. No runtime/schema/prompt/chunker change."
---

# WORK LOG — vNext readiness report (S11, report-only)

## Contract

`RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` §S11 sequences a "report-only vNext readiness
verifier" before any cutover, producing per-document contract verdicts without
affecting availability (§2 `document_retrieval_readiness` view, §16 backfill
completeness report, §19 readiness floor `unresolved_eligible_parents = 0`). It also
answers the /goal's standing questions ("what is still serving on the legacy
contract? what remains dependent on legacy state?") with real numbers, and makes the
GENERATION INVARIANT measurable (a partially-mapped document is never vNext-complete).

Owner: `governance` (a read-only verifier VIEW + its test; script registry + TREE).
Public contract: `document_state(eligible, mapped, excluded) -> state` +
`backfill_report(conn, corpus_id) -> dict` + a CLI. Rollback: delete both files +
revert registry/TREE. Verifier: `tests/determinism/test_vnext_readiness_report.py`.

Explicitly OUT of scope: it does NOT redefine `query_ready` (SEMANTIC-READINESS-V1 and
the control contract own that); it takes NO retirement/cutover action; it writes
nothing.

## Changes

- **`scripts/vnext_readiness_report.py`** (new, read-only): per corpus reads
  `documents`, eligible parents (`chunks tier='parent'` minus `document_region.NOISY_ROLES`
  — the same eligibility rule as the skeleton), active maps (`document_parent_maps
  WHERE active`), exclusions (`document_parent_exclusions`), batch status
  (`document_parent_map_batches`), and legacy `runs.status='query_ready'`. Classifies
  each document NO_ELIGIBLE_PARENTS / NOT_STARTED / MAP_PARTIAL / MAP_COMPLETE, where
  COMPLETE == every eligible parent resolved (mapped OR excluded) — the §19 floor.
  `--corpus` / `--json`; availability-neutral (no DB → clean no-op exit).
  Complementary to `semantic_readiness.py` (legacy semantic-lane verdict); both are
  readiness VIEWS, not schedulers.
- **test + registry + scaffold**: 3 pins (generation-invariant classification, no-DB
  no-op exit, live-DB report shape — DB pin skips without Postgres); registry row; two
  TREE lines; this work-log.

## Proof

```
set -a; . ./.env; set +a
.venv/bin/python -m pytest tests/determinism/test_vnext_readiness_report.py -q  -> 3 passed (live DB)
# without a DB (CI): 2 passed, 1 skipped
.venv/bin/python scripts/repo_guard.py        -> repo guard: ok
.venv/bin/python scripts/wiki_worm.py --check -> wiki: ok
.venv/bin/python scripts/agent_preflight.py   -> preflight: ok
```

**Live baseline (dev store, HEAD 00d2bd0 + this slice)** — the concrete scope of the
owner-gated parent-map backfill:

| corpus | docs | legacy query_ready runs | eligible parents | mapped | state |
|---|--:|--:|--:|--:|---|
| cinema | 67 | 4 | 11,993 | 0 | 67 NOT_STARTED |
| ecom-meta-v1 | 10 | 10 | 1,346 | 0 | 10 NOT_STARTED |
| d7-h1-test | 3 | 0 | 78 | 0 | 3 NOT_STARTED |

Every document is legacy-only; the vNext parent-map substrate (0054 tables) is empty
by design — no map worker has run (S9 is code-pending and RUN is Groq-gated). This is
the generation-invariant baseline the backfill will move.

## Rejected claims

- **Not** a redefinition of `query_ready`: the control contract and
  SEMANTIC-READINESS-V1 own readiness; this VIEW only reports the parent-map gap.
- **Not** a scheduler or a second job engine (plan §2): it reads, it does not arm
  tickets or mint work.
- **Not** availability-affecting: no document is demoted; the legacy contract is
  untouched (a document with 0 vNext maps is still legacy-serveable).

## Open contract gaps

- `legacy_query_ready_runs` is a raw `runs.status='query_ready'` count, not a
  per-document legacy-readiness verdict (cinema shows 4 vs 67 docs because readiness is
  run/generation-scoped); a per-document legacy verdict is a later refinement.
- vNext PROFILE readiness (fingerprint-based profile present per doc) is not yet a
  column — the vNext profile is not generated (S8 gated); this report covers the
  parent-map scale only. Extend with a profile column when S8 lands.
- Promoting this VIEW into `semantic_readiness.py` as a first-class
  `document_retrieval_readiness` verdict is the S11-proper step; kept as a report-only
  `scripts/` tool now (fence-free, "report-only first").
