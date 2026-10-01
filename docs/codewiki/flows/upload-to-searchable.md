# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY: `POST /upload` -> `upload` (web class: write) at `orchestrator/orchestrator/api/ui.py:467`.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Multipart form parsed: `corpus_id`, `file`, `allow_near_duplicate=""` | orchestrator/orchestrator/api/ui.py:467-469 [DERIVED] | HTTP form -> endpoint args | missing form fields (FastAPI `Form(...)`/`File(...)`) |
| 2 | Write-scope gate: `require_corpus(corpus_id, write=True)` -> `can_see` -> `allowed_corpora(write)`; `None` = every library (owner / trusted local caller) | orchestrator/orchestrator/web_scope.py:85-87, 80-82, 72-77 [DERIVED] | principal -> allow decision | 403 `CORPUS_NOT_ALLOWED` "that library is not open to this account for writing" (web_scope.py:57-58) |
| 3 | Filename normalized (`os.path.basename`, lower ext); ext checked against `_UPLOAD_EXTENSIONS` | orchestrator/orchestrator/api/ui.py:483-488 [DERIVED] | filename -> ext | 422 `unsupported extension {ext!r}; accepted: ...` |
| 4 | Size cap: `max_bytes = int(POLYMATH_UPLOAD_MAX_MB, default "200") * 1024 * 1024`; seek(END)/tell check | orchestrator/orchestrator/api/ui.py:489, 496-498 [DERIVED] | file handle -> byte count | 413 `file exceeds {max_bytes} bytes` |
| 5 | Spool write off-thread: `anyio.to_thread.run_sync(spool_write, file.file)` — 1 MiB chunks, sha256 in flight (SPOOL-CLAIM-CHECK-V1); bytes never sit in memory as one buffer | orchestrator/orchestrator/api/ui.py:491-500 [DERIVED] | file handle -> `ref` `{store, key, sha256, bytes}` | 422 `empty file` when `ref["bytes"] == 0` |
| 6 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1 (byte-identical): `SELECT source_name FROM documents WHERE corpus_id = %s AND source_hash = %s` | orchestrator/orchestrator/api/ui.py:511-520 [DERIVED] | sha256 -> dup row or none | 409 `{"error_code": "duplicate_document", "message": ...}` |
| 7 | Near-dup override parsed: `allow_near_duplicate` in `("1","true","yes","on")` -> `config={"allow_near_duplicate": True}`; layers 1 and 2 never overridable | orchestrator/orchestrator/api/ui.py:522-531 [DERIVED] | form string -> keep_both bool | override silently ignored for layers 1/2 |
| 8 | Canonical payload built: exactly one of `content_b64` / `content_ref`; upload uses `content_ref` requiring fields `store`, `key`, `sha256`, `bytes` | shared/polymath_shared/intake_submission.py:24-57 [DERIVED] | ref -> payload dict | `ValueError` "exactly one of content_b64 / content_ref is required" or "content_ref missing {field!r}" |
| 9 | Transaction opened via `tx()`: pool connection, commit on clean exit, rollback on exception | shared/polymath_shared/db.py:44-54 [DERIVED] | pool (min 1, max 8, autocommit False) -> Connection | exception -> rollback |
| 10 | Run identity: `run_id = f"run_{content_hash({'corpus': corpus_id, 'intake': payload})}"`; canonicalize = JSON sort_keys, UTF-8, compact separators | shared/polymath_shared/identity.py:59-62, 28-30, 16-25 [DERIVED] | payload -> `run_...` id | none (pure hash) |
| 11 | Idempotency check: `SELECT 1 FROM runs WHERE run_id = %s`; existing -> `{"run_id", "accepted": True, "already_exists": True}`, nothing written | shared/polymath_shared/intake_submission.py:79-81 [DERIVED] | run_id -> exists flag | silent no-op on replay (by design) |
| 12 | Writes: `INSERT INTO runs (..., status 'intake', metadata {source_name, intake_payload})` + `INSERT INTO outbox_events ('intake.v1', payload, idempotency_key=content_hash({"run","type","payload"})) ON CONFLICT (idempotency_key) DO NOTHING` — one transaction | shared/polymath_shared/intake_submission.py:83-101 [DERIVED] | payload -> run row + outbox event | rollback of both on exception |
| 13 | HTTP response: `{**out, corpus_id, source_name, bytes, sha256, near_duplicate_override}` | orchestrator/orchestrator/api/ui.py:533-537 [DERIVED] | submit result -> JSON | none |
| 14 | Ticket chain minted (`ensure_run_tickets`): intake ticket born `ready` and emits its work event immediately; stages with prior ok attempt born `done`; others `pending`; `execution_contract` stamped on `runs` | control/control/tickets.py:93-137 [DERIVED] | run_id -> stage_tickets rows | replay of legacy runs forced full re-execution before the born-done fix (tickets.py:99-104) |
| 15 | Census tick selects non-terminal runs: `status IN ('intake','reconciling','degraded')` ORDER BY `created_at, run_id`; mode `auto` -> `incremental` if watermark exists else `full` | control/control/census.py:171-179, 158-167 [DERIVED] | runs table -> candidate runs | none |
| 16 | Dirty selection (incremental): `stage_attempts.started_at` and `stage_tickets.updated_at` within lookback (`1_000_000` us replay window), new runs, and uncached active runs | control/control/census.py:182-217 [DERIVED] | watermark -> changed set | stuck-at-reconciling races (see failure modes 8-9) |
| 17 | Chain verdict per run: first-gap walk over STAGE_CHAIN `intake -> extract -> profile_document -> project_qdrant -> project_neo4j -> canonicalize -> project_canonical -> verify_projections`; failed within `max_attempts=3` -> retry gap; beyond -> run fails; missing -> single gap | control/control/census.py:19, 386-410 [DERIVED] | attempts -> (gaps, complete, failed) | run pinned `failed` after 3 failed attempts |
| 18 | Gaps scheduled: each gap -> `Gap(run_id, corpus_id, stage, event_type=STAGE_EVENTS[stage], reason)` re-arms the stage's work event | control/control/census.py:306-309, 28-37 [DERIVED] | verdict -> census.gaps | gap verdicts must never be cached (re-arms unclaimable events) |
| 19 | Projection receipt census on complete chains: qdrant (run-scoped chunk receipts + routing kinds), neo4j (eligible facts + chunks), canonical (entities/memberships/evidence); missing -> re-arm stage with "N projection receipts missing" | control/control/census.py:313-328, 433-576 [DERIVED] | projection_receipts anti-join -> missing list | store loss cleared by VERIFY re-drives projector |
| 20 | Extraction coverage barrier: `coverage_verdict` over `artifacts.payload->'llm_extraction'->'stats'`; reasons -> `census.degrade[run_id]`, never promote | control/control/census.py:331-339, 413-430 [DERIVED] | extract stats -> degrade reasons | corpus lands `degraded`, not query_ready |
| 21 | Promote: complete + not failed + receipts converge + no barrier -> `census.promote` (query_ready is a generation barrier) | control/control/census.py:330-339; control/control/tickets.py:7 [DERIVED] | verdict -> promote list | degraded/fail branches above |
| 22 | Background stages run after settlement, non-blocking: `compile_objects`, `parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`, `doc_profile` (rollout phase A); failure degrades summaries, never blocks QUERY_READY | control/control/tickets.py:40-66 [DERIVED] | chain -> background tickets | DEGRADED summaries only |
| 23 | `doc_parent_map` / `parent_enrichment` are ABSENT from STAGE_DAG: minted by the flag-gated `auto_map_parents_on_chunks` scheduler phase / enrichment buttons; non-blocking | control/control/tickets.py:67-76 [DERIVED] | flags/buttons -> tickets | lingering ticket can never hold promotion |
| 24 | Watermark advanced over max(attempt time, created_at, ticket `updated_at`) and written to `scheduler_cursors` in the SAME transaction as the tick's work | control/control/census.py:364-378 [DERIVED] | timings -> watermark | crash rolls watermark back with the work (safe replay) |

## state written

| store | what | anchor |
|---|---|---|
| spool volume file | content blob `{store, key, sha256, bytes}`; Postgres never holds the bytes | orchestrator/orchestrator/api/ui.py:470-475, 500 [DERIVED] |
| Postgres `runs` | row `run_id, corpus_id, status 'intake', metadata {source_name, intake_payload}`; later `execution_contract` UPDATE | shared/polymath_shared/intake_submission.py:83-92; control/control/tickets.py:133-136 [DERIVED] |
| Postgres `outbox_events` | `intake.v1` event keyed by `idempotency_key` | shared/polymath_shared/intake_submission.py:94-101 [DERIVED] |
| Postgres `stage_tickets` | full per-run ticket chain (INSERT ... ON CONFLICT (run_id, stage, generation) DO NOTHING) | control/control/tickets.py:119-127 [DERIVED] |
| Postgres `scheduler_cursors` | census watermark `stage='__census__'`, `corpus_id='__global__'`, `last_seq` epoch-micros | control/control/census.py:91-92, 122-128 [DERIVED] |
| Postgres `projection_receipts` | read here via NOT EXISTS anti-joins; kinds: `routing_document_summary`, `routing_section_summary`, `routing_child`, `routing_procedure`, `routing_concept` (qdrant); `fact`, `chunk`, `canonical_entity`, `canonical_membership`, `evidence_chunk` (neo4j) — written by the projectors, not on this path | control/control/census.py:492-499, 508-539, 543-575 [DERIVED] |
| Postgres `documents.source_hash` | checked at upload (layer 1); recorded by the intake worker where the original-bytes hash lives | orchestrator/orchestrator/api/ui.py:504-515 [DERIVED] (write side [INFERRED] from the comment) |
| Postgres `artifacts` | read: `payload->'llm_extraction'->'stats'` for stage `extract` | control/control/census.py:416-422 [DERIVED] |
| Qdrant projection | receipts incl. neural routing representations (R1B: production dependencies for query-ready) | control/control/census.py:450-456 [DERIVED] |
| Neo4j projection | receipts for eligible facts, chunk nodes, canonical entities/memberships, evidence | control/control/census.py:504-576 [DERIVED] |
| process memory | `_HISTORY_CACHE`, `_VERDICT_CACHE` (pruned when runs leave the active set) | control/control/census.py:93-94, 357-362 [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | `max_bytes = value * 1024 * 1024`; larger file -> 413 | orchestrator/orchestrator/api/ui.py:489 |
| `allow_near_duplicate` (form field) | `""` | truthy in `("1","true","yes","on")` -> payload config `{"allow_near_duplicate": True}`; overrides layer 3 only | orchestrator/orchestrator/api/ui.py:469, 525-531 |
| `POLYMATH_CENSUS_MODE` | `"auto"` | `auto` -> incremental when a watermark exists, else full; `"full"` forces authoritative sweep | control/control/census.py:158-167 |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces mode `full` | control/control/census.py:159 |
| `auto_map_parents_on_chunks` | not shown | flag-gated scheduler phase mints `doc_parent_map` tickets (stage absent from STAGE_DAG) | control/control/tickets.py:73-76 |
| `max_attempts` (census param) | `3` | failed stage beyond budget fails the run | control/control/census.py:140, 402-407 |
| `coverage_floor` / `drop_tolerance` (census params) | `0.0` / `None` | thresholds for the extraction coverage barrier | control/control/census.py:141-143, 426-430 |

## failure modes

1. 403 at entry -> principal's `writable_corpus_ids` excludes the corpus -> orchestrator/orchestrator/web_scope.py:72-87.
2. 422 `unsupported extension` -> ext not in `_UPLOAD_EXTENSIONS` -> orchestrator/orchestrator/api/ui.py:483-488.
3. 413 `file exceeds {max_bytes} bytes` -> `POLYMATH_UPLOAD_MAX_MB` cap -> orchestrator/orchestrator/api/ui.py:489, 496-498.
4. 422 `empty file` -> `ref["bytes"] == 0` after spooling -> orchestrator/orchestrator/api/ui.py:501-502.
5. 409 `duplicate_document` -> same sha256 already in `documents.source_hash`; not overridable by `allow_near_duplicate` -> orchestrator/orchestrator/api/ui.py:511-524.
6. `ValueError` "content_ref missing {field!r}" -> spool ref lacks `store`/`key`/`sha256`/`bytes` -> shared/polymath_shared/intake_submission.py:53-56.
7. Silent no-op replay -> identical payload yields identical `run_id` -> `already_exists: True`, no rows written; looks like success with no new ingestion -> shared/polymath_shared/identity.py:59-62, shared/polymath_shared/intake_submission.py:79-81.
8. Run pinned at `reconciling` forever (historical, cysa-study-v1) -> summary stages complete tickets without `stage_attempts`, cached non-promote verdict replayed -> fixed by dirty-tracking `stage_tickets.updated_at` and never caching gap verdicts -> control/control/census.py:66-80.
9. Run stuck at `reconciling` while a sibling promotes (CENSUS-UNCACHED-DIRTY-V1) -> uncached active run's ticket close fell under the advanced global watermark -> fixed by treating uncached actives as dirty -> control/control/census.py:207-217.
10. Corpus `degraded` instead of query_ready -> extract stage dropped/unaccounted neighborhoods -> `coverage_verdict` reasons in `census.degrade` -> control/control/census.py:331-339, 426-430.
11. Run fails -> stage `failed` with `count_by_stage >= max_attempts (3)` -> `census.fail` -> control/control/census.py:402-407.
12. Complete chain but stage re-armed -> missing projection receipts (store loss cleared by VERIFY) -> gap "N projection receipts missing" -> control/control/census.py:313-328.
13. Ticket advancement blocked after verifier rewrite (historical, VERIFY-DAG-KEYS-V2) -> verify ticket required stale artifact key `'docs'` -> now requires `qdrant, routing_qdrant, neo4j, canonical` -> control/control/tickets.py:32-39.
14. Legacy run re-minted `pending` forced full model re-execution -> chain creation now reconciles history (ok attempt -> born `done`) -> control/control/tickets.py:99-104.
15. Summary-stage successors never advance -> summary layer writes no `stage_attempts`; `_stage_attempt_ok` falls back to a durably committed DONE ticket -> control/control/tickets.py:151-158.
16. Tick held open for minutes, workers queued (historical, R1B) -> per-entity receipt SELECT loop inside the tick transaction -> replaced by one set-based anti-join -> control/control/census.py:450-456.

## invariants

- INVARIANT: Postgres never holds the bytes; the request body is transport, never pipeline state (SPOOL-CLAIM-CHECK-V1). orchestrator/orchestrator/api/ui.py:470-475
- INVARIANT: run identity is content-addressed — replaying the same intake over a corpus yields the same `run_id`, so re-intake is a no-op. shared/polymath_shared/identity.py:59-62
- INVARIANT: a canonical payload carries exactly one content variant — `content_b64` xor `content_ref`. shared/polymath_shared/intake_submission.py:34-43
- INVARIANT: run row + `intake.v1` outbox event commit in a single transaction; outbox conflict is `DO NOTHING`. shared/polymath_shared/intake_submission.py:64-65, 94-101
- INVARIANT: duplicate layers 1 (identical bytes) and 2 (identical text) are never overridable; only near-duplicate layer 3 rides the config override. orchestrator/orchestrator/api/ui.py:521-531
- INVARIANT: two censuses over the same state produce the same schedule — explicit sort orders (runs by `created_at`, attempts by `stage, started_at`). control/control/census.py:146-149
- INVARIANT: a verdict carrying gaps is never cached; gaps are transient by definition. control/control/census.py:341-348
- INVARIANT: the census watermark is written in the same transaction as the tick's work — a crash rolls both back together. control/control/census.py:374-378
- INVARIANT: a stage is handed work only when its predecessors' durable artifacts, receipts, and contract exist (verified readiness, ordered DAG). control/control/tickets.py:20-23
- INVARIANT: non-blocking stage failure degrades summaries to DEGRADED, never blocks QUERY_READY. control/control/tickets.py:60-62

## VERIFY

```verify
grep -Fq 'SPOOL-CLAIM-CHECK-V1' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'ON CONFLICT (idempotency_key) DO NOTHING' shared/polymath_shared/intake_submission.py
grep -Fq 'CENSUS-UNCACHED-DIRTY-V1' control/control/census.py
grep -Fq 'NON_BLOCKING_STAGES' control/control/tickets.py
test "$(grep -c -F 'routing_' control/control/census.py)" -ge 5
! grep -Fq 'POLYMATH_CENSUS_AUDIT' orchestrator/orchestrator/api/ui.py
```
