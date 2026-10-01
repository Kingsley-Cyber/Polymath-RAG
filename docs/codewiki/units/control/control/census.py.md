# unit: control/control/census.py
anchor: control/control/census.py:1-600

## purpose
Desired-vs-observed artifact census for the control plane: walks each non-terminal run against the fixed stage chain and emits the exact gaps, promotions, failures and degradations the scheduler should act on (control/control/census.py:1-10, 140-144). Consumed by `control/control/main.py` and `control/control/scheduler.py` (FACTS.importers). Runs in two modes: incremental (dirty runs only) for normal operation, full sweep for recovery/audit (control/control/census.py:82-86).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Gap | class | fields: run_id, corpus_id, stage, event_type, reason | control/control/census.py:41-46 | — |
| Census | class | fields: gaps list[Gap], promote list[str], fail list[str], degrade dict[str, list[str]] | control/control/census.py:50-57 | — |
| pop_census_timing | def | () -> dict \| None (returns and clears `_LAST_TIMING`) | control/control/census.py:107-111 | main.py, scheduler.py (module importers) |
| compute_census | def | (conn: Connection, *, max_attempts=3, mode=None, coverage_floor=0.0, drop_tolerance=None) -> Census | control/control/census.py:140-143 | main.py, scheduler.py (module importers) |
| chain_verdict | def | (last_by_stage: dict, count_by_stage: dict, *, max_attempts=3) -> (gaps, complete, failed) | control/control/census.py:386-387 | compute_census (control/control/census.py:304) |
| extraction_stats | def | (conn: Connection, run_id: str) -> dict \| None | control/control/census.py:413-414 | — |

Private: `_watermark_read` (114-119), `_watermark_write` (122-128), `_epoch_us` (131-137), `_extraction_barrier` (426-430), `_missing_projection_receipts` (433-599).

## contracts

**compute_census** — control/control/census.py:140-383
- in: psycopg `Connection`; keyword-only `max_attempts=3`, `mode=None`, `coverage_floor=0.0`, `drop_tolerance=None` (140-143).
- mode resolution order: `mode or os.environ["POLYMATH_CENSUS_MODE"]` default `"auto"` → `POLYMATH_CENSUS_AUDIT == "1"` forces `"full"` → `"auto"` becomes `"incremental"` iff watermark exists else `"full"` → `"incremental"` with no watermark falls back to `"full"` (158-167).
- pre: tables `runs`, `corpora`, `stage_attempts`, `stage_tickets`, `scheduler_cursors` readable (170-179, 186-200, 114-119).
- scope: only runs with `r.status IN ('intake', 'reconciling', 'degraded')`, joined to `corpora`, `ORDER BY r.created_at, r.run_id` (171-178).
- out: `Census`; `promote` only when chain complete, not failed, zero missing projection receipts for the 3 projection stages, and no extraction-coverage reasons; coverage failures go to `degrade` instead (313-339).
- post: watermark advanced iff `max_seen_us > (wm_us or 0)`, written inside the caller's transaction (374-378); `_LAST_TIMING` set (382); gap verdicts evicted from `_VERDICT_CACHE`, gap-free verdicts cached (341-355); cache entries for runs leaving the active set pruned (357-362).
- dirty set (incremental): runs with `stage_attempts.started_at` or `stage_tickets.updated_at` inside a lookback of `now() - (time.time()*1e6 - wm_us + 1_000_000)/1e6` seconds, plus new runs, plus every active run missing from `_VERDICT_CACHE` (183-217).

**chain_verdict** — control/control/census.py:386-410
- in: `last_by_stage` {stage: (outcome, started_at)}, `count_by_stage` {stage: int}.
- out: walks `STAGE_CHAIN` in order, stops at first non-ok stage: `failed` with `count < max_attempts` → one retry gap `"stage {stage} failed; retry {n}/{max}"`, `(gaps, False, False)`; `failed` at budget → `(gaps, False, True)`; absent → one gap `"stage {stage}" + " missing"`, `(gaps, False, False)`; all ok → `([], True, False)` (397-410).
- pure: no I/O; deterministic order from `STAGE_CHAIN` (398).

**extraction_stats** — control/control/census.py:413-423
- in: conn, run_id. out: latest `artifacts` row with `stage = 'extract'` and `jsonb_exists(payload, 'llm_extraction')`, returning `payload->'llm_extraction'->'stats'`, else `None` (417-423).

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `runs`, `corpora`, `stage_attempts`, `stage_tickets`, `scheduler_cursors`, `artifacts`, `retrieval_summaries`, `chunks`, `documents`, `procedure_artifacts`, `concept_artifacts`, `projection_receipts`, `facts`, `evidence`, `canonical_entities`, `canonical_memberships` | control/control/census.py:171-178, 186-200, 245-251, 369, 417-421, 459-498, 511-538, 543-571 |
| Postgres write | `scheduler_cursors` only (INSERT ... ON CONFLICT DO UPDATE on `("stage","corpus_id")`) | control/control/census.py:122-128 |
| env | `POLYMATH_CENSUS_MODE` = `'auto'`; `POLYMATH_CENSUS_AUDIT` (compared to `"1"`) | control/control/census.py:158-159 |
| Qdrant / Neo4j / files / network / subprocess | none — projection stores are only referenced via receipt tables and shared predicates | control/control/census.py:433-599 |

## invariants

- INVARIANT: `STAGE_EVENTS` keys == `STAGE_CHAIN` entries (8 stages; `verify_projections` -> `"verify.v1"`) — control/control/census.py:19, 28-37 [DERIVED]
  fails-if: `STAGE_EVENTS[stage]` raises KeyError when appending a gap (control/control/census.py:311).
- INVARIANT: dirty replay overlap == `1_000_000` µs (1 s) — control/control/census.py:183 [DERIVED]
  fails-if: watermark/clock skew beyond 1 s drops a changed run from the dirty set (mitigated by uncached-active guard, 217).
- INVARIANT: every active run absent from `_VERDICT_CACHE` is treated as dirty — control/control/census.py:217 [DERIVED]
  fails-if: a run whose last ticket closed before the global watermark advanced is never re-evaluated (the Netnography `reconciling` pin, 207-216).
- INVARIANT: verdicts carrying gaps are never cached (`_VERDICT_CACHE.pop(run_id, None)`) — control/control/census.py:346-349 [DERIVED]
  fails-if: replayed gap re-arms unclaimable outbox events every tick (comment 343-345).
- INVARIANT: `promote` ⇒ chain complete ∧ not failed ∧ 0 missing receipts for `project_qdrant`, `project_neo4j`, `project_canonical` ∧ `coverage_verdict(...)` returns no reasons — control/control/census.py:313-339 [DERIVED]
  fails-if: incomplete corpus marked query_ready.
- INVARIANT: `fail` ⇒ some stage outcome `failed` with `count_by_stage >= max_attempts` (default 3) — control/control/census.py:402-407, 140 [DERIVED]
  fails-if: runs either retried forever (budget too high) or failed early (too low).
- INVARIANT: watermark strictly increases; written only when `max_seen_us > (wm_us or 0)`, and `max_seen_us` covers attempts, `runs.created_at`, and `stage_tickets.updated_at` — control/control/census.py:287-289, 364-378 [DERIVED]
  fails-if: incremental mode re-derives everything each tick, or a ticket-only change is never seen.
- INVARIANT: dirty signal covers both `stage_attempts.started_at` and `stage_tickets.updated_at` — control/control/census.py:186-200 [DERIVED]
  fails-if: summary stages (which write no `stage_attempts`) never mark their run dirty — the cysa-study-v1 permanent `reconciling` bug (66-80).

## determinism & idempotency
determinism: NONDETERMINISTIC (wall clock `_time.time()` in the lookback, `now()` in dirty SQL — control/control/census.py:185, 189, 199; db state). Schedule order itself is deterministic: runs `ORDER BY r.created_at, r.run_id` (177-178), attempts `ORDER BY run_id, stage, started_at` (229, 249), routing anti-join `ORDER BY w.id` (498).
idempotency: SAFE — derivation is idempotent by design ("1s replay window; derivation is idempotent", 183) and the watermark write shares the caller's transaction so a crash rolls both back (374-378, 122-128).

## failure behaviour
- No try/except anywhere in the module; SQL errors, KeyError on `STAGE_EVENTS[stage]` (311), and ImportError from the lazy `polymath_shared` / `control.tickets` imports (427-439, 446-447, 508) propagate to the scheduler caller [DERIVED].
- A cold controller with no watermark degrades to a full pass instead of an empty census (162-167) [DERIVED].

## dumb-code flags
- `import os as _os` at control/control/census.py:153 is unused; module-level `os` is used at 158-159 [DERIVED].
- `_TIMING_KEYS` (control/control/census.py:99-103) is never referenced; timing keys are written literally, and the dict also gains `"census_total_ms"` (380-381) which is not in the tuple [DERIVED].
- Default `max_attempts=3` duplicated at control/control/census.py:140 and :387 — they can drift [DERIVED].
- FACTS lists `tables_written` entry `"set"` and `tables_read` entry `"want"` — artifacts of static analysis over Python set literals (`changed |= {...}`, 195) and the SQL CTE named `want` (459) [INFERRED].
- Fall-through branch of `_missing_projection_receipts` (control/control/census.py:577-599) is unreachable from `compute_census`, which only passes the three named stages (317) [INFERRED].

## refactor notes
- Adding/removing a `STAGE_CHAIN` stage requires a matching `STAGE_EVENTS` key (KeyError at control/control/census.py:311) and, for projection stages, both the loop tuple at 317 and a branch in `_missing_projection_receipts`.
- Gap/eligibility semantics are delegated: `polymath_shared.projection_want.missing_chunk_receipts_{docs,run}` (437-449), `polymath_shared.neo4j_eligibility.fact_eligible_sql` (508-516, 577-589), `polymath_shared.extraction_coverage.coverage_verdict` (427-429) — changing any shared predicate changes census output for every caller.
- `control.tickets._run_doc_ids` is imported by private name (control/control/census.py:446); renaming it in `control.tickets` breaks this module.
- `_HISTORY_CACHE` / `_VERDICT_CACHE` are process-global dicts (91-94); a second controller process would diverge from the watermark/caches — single-process assumption is implicit [INFERRED].
- The cursor row `('__census__', '__global__')` in `scheduler_cursors` gates incremental mode; deleting it forces a full sweep (114-119, 162-167).

## VERIFY
```verify
grep -Fq 'STAGE_CHAIN = ["intake", "extract", "profile_document", "project_qdrant", "project_neo4j", "canonicalize", "project_canonical", "verify_projections"]' control/control/census.py
grep -Fq '_CENSUS_CURSOR_STAGE = "__census__"' control/control/census.py
grep -Fq 'mode = "incremental" if wm_us is not None else "full"' control/control/census.py
grep -Fq 'overlap_us = 1_000_000' control/control/census.py
grep -Fq 'POLYMATH_CENSUS_AUDIT' control/control/census.py
test "$(grep -c -F 'projection_receipts' control/control/census.py)" -ge 5
! grep -Fq 'except' control/control/census.py
```
