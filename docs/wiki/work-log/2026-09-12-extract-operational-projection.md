---
title: "WORK LOG — Control Plane / Files hot-path fix: narrow extract-artifact operational projection (execution authority §20A, mandatory gate)"
change_id: EXTRACT-OPERATIONAL-PROJECTION-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.214
architecture_impact: "additive migration (7 nullable columns on artifacts) + centralized write-path derivation + bounded backfill + reader cutover on two hot aggregates (control_plane_status.py::_graph_provider, document_status.py::corpus_document_summaries). artifacts.payload is untouched — still authoritative for forensic/replay/detail reads. No retrieval/ranking/extraction-algorithm change. No producer stopped, no schema deleted."
---

> Executor session, execution authority `POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md`
> §20A ("MANDATORY HOT-PATH PROJECTION MIGRATION... a REQUIRED repository-finalization
> task, not a parked optimization"). This explicitly supersedes the owner's earlier
> 2026-09-11 choice to defer this fix ("just report it, don't fix now") — the new
> authority document names this exact defect as a mandatory completion gate, with a
> full phase-by-phase spec (A-K) this work-log follows.

## Contract

Requested outcome: hot, frequently-polled Control Plane / Files operational reads
must not require detoasting the full extraction artifact payload, while
`artifacts.payload` remains fully intact for forensic/replay/detail use.

- **Smallest acceptance:** `control_plane_status.py::_graph_provider` and
  `document_status.py::corpus_document_summaries`'s graph/extraction counters read
  narrow scalar columns, never `artifacts.payload`; 100% shadow parity against the old
  derivation; before/after EXPLAIN proof; no regression to pMAP or readiness controls.
- **Owner / public contract:** `/control_plane`, `/documents/summary` — response shape
  unchanged (same fields, same semantics, same corpus isolation).
- **Inputs/outputs/persistence:** reads `artifacts`'s new narrow columns instead of
  `payload`; writes happen at the two known `stage='extract'` artifact-persistence
  seams (`receipts.py`, `control/reconciliation.py`), both calling one shared
  derivation function.
- **Dependency edges:** `shared/polymath_shared/extract_projection.py` is a new leaf
  module (no I/O, pure derivation) imported by `receipts.py`, `control/reconciliation.py`,
  and the backfill/verify scripts. No existing dependency edge changed direction.
- **Verifier / rollback:** `tests/determinism/test_extract_projection.py` (12 cases) +
  `scripts/verify_extract_projection_parity.py` (live shadow parity). Rollback: revert
  the two reader edits to read `payload` again (the migration is additive — nothing to
  undo at the schema level; the new columns simply go unread).

## Changes

- `stores/postgres/migrations/0057_extract_operational_projection.sql` — seven
  additive, nullable columns on `artifacts`: `extract_stats_present` (boolean, mirrors
  `jsonb_exists(payload,'llm_extraction')` — KEY existence, not value shape),
  `extract_llm_calls`, `extract_entity_count`, `extract_relation_count`,
  `extract_neighborhoods_sent`, `extract_neighborhoods_unaccounted`,
  `extract_neighborhoods_dropped` (all int, mirror the matching
  `payload->'llm_extraction'->'stats'->>'<field>'`).
- `shared/polymath_shared/extract_projection.py` — new module:
  `derive_extract_projection(payload)` (the pure derivation, phase-A-verified against
  the current semantic matrix: presence is key existence not value-is-dict; missing
  stats/fields read None, never an invented 0; non-numeric stats read None instead of
  raising, a strict robustness improvement over the old `::int` cast which would have
  thrown) and `extract_projection_columns_for(payload)` (returns None when
  `llm_extraction` is absent from THIS payload — see the write-path note below).
- `shared/polymath_shared/receipts.py::_StageWrite.artifact()` — the canonical
  persistence seam. `extract_worker.py` calls `.artifact()` several times per stage
  with PARTIAL payloads that JSONB-merge (`{"manifest":...}` first, `{"llm_extraction":
  ...}` later, more after) — so the projection columns are only added to the SQL
  (INSERT column list + `ON CONFLICT ... SET`) when THIS call's payload actually
  mentions `llm_extraction`; a call that doesn't (manifest/trace writes) omits them
  entirely rather than risk clobbering a value an earlier call in the same stage
  already set.
- `control/control/reconciliation.py` — the second, independent writer (blue/green
  run-supersession carries a prior run's COMPLETE artifact forward into a new
  `run_id`). Unlike the incremental writer above, this payload is always the full,
  final artifact, so the projection is computed unconditionally from it and included
  in the fresh INSERT. Both writers call the SAME `derive_extract_projection` —
  centralizing the FORMULA even though there are genuinely two INSERT call sites (a
  full `StageTransaction`-style centralization would have required a larger,
  out-of-scope refactor of the control-plane's run-supersession machinery).
- `shared/polymath_shared/control_plane_status.py::_graph_provider` — reads
  `SUM(a.extract_llm_calls)` etc. with `WHERE ... AND a.extract_stats_present`, never
  `payload`.
- `shared/polymath_shared/document_status.py::corpus_document_summaries` — its
  graph-entities/relations sub-query reads `a.extract_entity_count`,
  `a.extract_relation_count` directly, same `WHERE` gate. `document_status()` (the
  single-document DETAIL view) is intentionally UNCHANGED — it still reads
  `payload->'llm_extraction'` directly, which is correct: that is the forensic/detail
  path §20A explicitly preserves, not a hot poll.
- `scripts/backfill_extract_projection.py` — bounded, resumable, idempotent backfill
  (keyset-paginated on `artifact_id`, not on the mutation succeeding — a `--dry-run`
  that never writes still terminates, see Rejected claims). Calls the same
  `derive_extract_projection` the write path uses.
- `scripts/verify_extract_projection_parity.py` — the shadow-parity gate: per-row,
  per-corpus comparison of the old JSONB derivation against the new columns.
- `docs/wiki/experiments/extract-operational-projection-2026-09-12/` — README +
  `before-after.json` with full EXPLAIN (ANALYZE, BUFFERS) numbers, shadow-parity
  results, and the out-of-scope finding (see below).
- `scripts/README.md`, `scripts/scaffold_polymath_v4.py` — registry + TREE entries.

## Proof

- **Root cause confirmed by EXPLAIN, not assumed:** `_graph_provider` on `cinema`
  (largest corpus) showed `Seq Scan on artifacts ... Filter: (jsonb_exists(payload,
  'llm_extraction') AND stage='extract')`, **45,346 buffer reads (~354 MB), 605 ms**.
  `corpus_document_summaries`'s extract-join showed the identical pattern (46,857
  reads, ~362 MB, 489 ms).
- **After cutover, same corpus, same query shape:** `_graph_provider` **4.1 ms** (174
  buffers, ~1.4 MB) — **~147x**. `corpus_document_summaries` extract-join **5.7 ms**
  (180 buffers, ~4.6 MB) — **~85x**. Both plans now show zero payload/TOAST access.
- **Shadow parity: 100% of 108 eligible `stage='extract'` rows, 0 mismatches**, across
  all 4 corpora with extract artifacts (cinema 67, ecom-meta-v1 28, rag-canary 10,
  d7-h1-test 3) — `scripts/verify_extract_projection_parity.py`.
- **Backfill: 108/108 processed, 0 errors, idempotent** (a second run processes 0).
- **Controls did not regress:** `pipeline_health` 12.2 ms, `control_ready` 1.9 ms,
  `_pmap_provider` 13.7 ms, `_queue_by_pool` 14.5 ms — consistent with the
  CONTROL-PLANE-HONESTY-V1 session's numbers (register 11.211); pMAP's own read was
  not touched, matching the authority's explicit non-goal.
- **Regression tests:** `tests/determinism/test_extract_projection.py` (12 cases:
  full-stats derivation, key-absent, present-but-not-a-dict, stats-missing, zero
  vs. missing, non-numeric stat, empty/None payload, both write-path integrations) —
  all pass. `tests/determinism/test_control_plane_status.py`,
  `test_document_status.py`, `test_document_status_endpoint.py`,
  `test_pipeline_health.py` — 17 passed, no regression from the reader cutover.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: `shared/polymath_shared/{extract_projection,receipts,control_plane_status,
  document_status}.py` and `control/control/reconciliation.py` are ALL inside the
  HASH-FENCE-V2 fingerprinted dirs — 0 claimable/leased tickets at edit time (checked
  immediately before commit); a controlled `boot_polymath.sh` bounce follows.

## Rejected claims

- **"A STORED GENERATED column is the cleanest write-path guarantee."** REJECTED —
  correct in principle (Postgres would derive it automatically for every writer,
  present or future, with zero application code), but `ALTER TABLE ... ADD COLUMN ...
  GENERATED ALWAYS AS (...) STORED` on an EXISTING table forces a full table rewrite
  that must evaluate the expression (i.e. detoast `payload`) for every row, and holds
  an ACCESS EXCLUSIVE lock on `artifacts` for the whole rewrite — exactly the
  operational risk this migration exists to avoid, against a table live workers write
  to continuously. The authority document itself flags this exact tradeoff ("benchmark
  if considering them"). Used the plain nullable-column + explicit-write-path pattern
  instead, matching the doc's own stated default.
- **"Both writers should be centralized into one Python seam before this ships."**
  REJECTED for this slice — `control/reconciliation.py`'s carry-forward INSERT lives in
  a different transactional/architectural context (control-plane run supersession, not
  a stage worker's own transaction) than `receipts.py::_StageWrite`; forcing it through
  the same class would be a real refactor of run-supersession machinery, out of scope
  for a performance migration. Both writers call the SAME derivation function instead —
  centralizing the FORMULA, which is what phase D actually requires ("deterministic;
  centralized... covered by unit tests"), without forcing an unrelated architecture
  change.
- **"jsonb_exists(payload,'llm_extraction') present == payload['llm_extraction'] is a
  dict."** REJECTED — `jsonb_exists` is pure key existence; `derive_extract_projection`
  matches that exactly (a present-but-malformed value still counts as "present", with
  its counters reading None rather than an invented value) — the two are subtly
  different and the test suite pins the distinction explicitly
  (`test_llm_extraction_present_but_not_a_dict_is_still_present_with_no_invented_stats`).
- **A real bug caught during implementation, not shipped:** the backfill's own
  `--dry-run` initially re-queried `WHERE extract_stats_present IS NULL` every batch
  with no other progress signal — since dry-run never writes, that predicate never
  shrinks and the loop never terminated (caught in a sandboxed local run, killed
  immediately, confirmed zero database writes occurred — `extract_stats_present` was
  still 0/108 non-null afterward). Fixed to keyset-paginate on `artifact_id > last_seen`
  so pagination advances regardless of whether the batch actually wrote anything; this
  is the version that shipped and is what `tests/determinism/test_extract_projection.py`
  and the real backfill run above exercise.

## Open contract gaps

- **Found but explicitly out of scope for this gate:** `corpus_document_summaries()`'s
  OTHER counters (chunks-by-tier, map-eligible-parents — both query `chunks` directly,
  no JSONB/TOAST involved) cost ~150 ms end-to-end on `cinema` specifically (vs. 10.6 ms
  on `rag-canary`). `EXPLAIN` confirms this is the planner CORRECTLY choosing a
  sequential scan over `chunks` (96,391 rows / 215 MB) because cinema's 67 documents
  own 84,152 of those rows (87% of the table) — `chunks_doc_idx (doc_id,
  chunk_index)` exists and is correctly NOT chosen at that selectivity. This is a
  volume-proportional cost, not a TOAST-avoidable inefficiency, and fixing it would mean
  designing a new maintained per-document chunk-count summary/cache — a separate
  migration decision the authority's own non-goals list warns against bundling into
  this one ("do not refactor X merely because it happens to be nearby"). Documented in
  `before-after.json` for a future slice if the owner wants it.
- **outbox_events scoping (§20A phase H) — checked, no fix applied.** No
  unscoped-then-filtered anti-pattern exists in current code for either target reader;
  `outbox_events` is small (2,486 rows/12 MB) and already indexed
  (`outbox_events_run_type_idx`); EXPLAIN shows sub-2ms cost. Per phase H's own
  instruction, no index was added because the plan does not need one.
- Live re-fire (phase K: RUN 1 → PASS, RUN 2 → PASS against the running orchestrator
  after a fleet bounce) is not yet done — this work-log covers the code/migration/
  backfill/parity/regression-test proof; the bounce + post-bounce re-verification is
  the next step before this slice can be called fully closed per the authority's own
  re-fire definition.
