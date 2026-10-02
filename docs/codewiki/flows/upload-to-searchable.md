# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.
ENTRY POST /upload -> orchestrator/orchestrator/api/ui.py:485 upload (web class: write)

Readiness in this flow = promotion to `query_ready`, a generation barrier; literal rule in source: ingested != query_ready — control/control/tickets.py:5-6, 52-57 [DERIVED]

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | write-scope gate `require_corpus(corpus_id, write=True)` | orchestrator/orchestrator/api/ui.py:494 | corpus_id + principal -> pass | 403 `CORPUS_NOT_ALLOWED` when corpus not in `writable_corpus_ids` — orchestrator/orchestrator/web_scope.py:57-58, 72-87 |
| 2 | filename gate: `os.path.basename`, ext must be in `_UPLOAD_EXTENSIONS` | orchestrator/orchestrator/api/ui.py:501-506 | `file.filename` -> `source_name`, `ext` | 422 `unsupported extension`; no name falls back to `upload.bin` |
| 3 | size cap `POLYMATH_UPLOAD_MAX_MB` * 1024 * 1024, seek-END tell check | orchestrator/orchestrator/api/ui.py:507, 513-516 | `file.file` -> `max_bytes` | 413 `file exceeds {max_bytes} bytes` |
| 4 | SPOOL-CLAIM-CHECK-V1: `spool_write` re-streams in 1 MiB chunks off-thread (`anyio.to_thread.run_sync`), sha256 in flight | orchestrator/orchestrator/api/ui.py:487-493, 509-518 | `file.file` -> `ref` {store, key, sha256, bytes} | bytes never sit in process memory as one buffer; Postgres never holds the bytes |
| 5 | empty-file guard | orchestrator/orchestrator/api/ui.py:519-520 | `ref["bytes"]` -> guard | 422 `empty file` when 0 |
| 6 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1 (byte-identical): `SELECT source_name FROM documents WHERE corpus_id = %s AND source_hash = %s` | orchestrator/orchestrator/api/ui.py:521-538 | `ref["sha256"]` -> dup row | 409 `duplicate_document` naming the existing `source_name`; refuses loudly instead of minting a silently no-op run |
| 7 | NEAR-DUPLICATE-GUARD-V1 override: `keep_both = allow_near_duplicate.strip().lower() in ("1", "true", "yes", "on")` | orchestrator/orchestrator/api/ui.py:539-543 | form field -> bool | layers 1 and 2 are never overridable; override only rides the payload config |
| 8 | `canonical_intake_payload(..., content_ref=ref, config={"allow_near_duplicate": True} if keep_both else None)`; `media_type = file.content_type or "application/octet-stream"` | orchestrator/orchestrator/api/ui.py:544-550; shared/polymath_shared/intake_submission.py:24-57 | ref -> payload {corpus_id, source_name, media_type, config, content_ref} | ValueError `exactly one of content_b64 / content_ref is required`; ValueError `content_ref missing {field!r}` for store/key/sha256/bytes |
| 9 | run identity: `run_` + `content_hash({'corpus': ..., 'intake': ...})` over canonical JSON (sort_keys, separators `(",", ":"`, utf-8) | shared/polymath_shared/identity.py:59-62, 28-30, 16-25 | payload -> `run_id` | deterministic: same intake over a corpus = same run_id, re-intake is a no-op at the Postgres level |
| 10 | idempotency probe: `SELECT 1 FROM runs WHERE run_id = %s` | shared/polymath_shared/intake_submission.py:75-81 | run_id -> existing? | replay returns `{run_id, accepted: True, already_exists: True}`, writes nothing — silent no-op by design |
| 11 | single-transaction writes: INSERT `runs` (status `'intake'`, metadata = source_name + intake_payload); INSERT `outbox_events` (`'intake.v1'`, payload, idempotency_key = content_hash({run, type, payload})) `ON CONFLICT (idempotency_key) DO NOTHING`; pooled conn (min_size=1, max_size=8, autocommit False) | shared/polymath_shared/intake_submission.py:83-100; shared/polymath_shared/db.py:23-31, 44-54 | payload -> run row + outbox event | `tx()` rolls back both on any exception |
| 12 | response `{**out, corpus_id, source_name, bytes, sha256, near_duplicate_override}` | orchestrator/orchestrator/api/ui.py:551-555 | -> client dict | — |
| 13 | census tick: `compute_census` over runs `status IN ('intake', 'reconciling', 'degraded')` ORDER BY created_at, run_id; dirty set = stage_attempts + stage_tickets `updated_at` in a 1s replay window + new runs + uncached actives | control/control/census.py:170-217 | runs -> `Census{gaps, promote, fail, degrade}` | verdict-replay races are the historical stuck-run causes (failure modes 6-7) |
| 14 | `chain_verdict` first-gap walk over STAGE_CHAIN (intake, extract, profile_document, project_qdrant, project_neo4j, canonicalize, project_canonical, verify_projections): ok -> continue; failed under `max_attempts` -> retry gap; failed beyond -> run fails; missing -> the one gap | control/control/census.py:13, 22-31, 386-410 | last_by_stage + count_by_stage -> (gaps, complete, failed) | nothing after the first non-ok stage is emitted; ordering rests on the ticket gate |
| 15 | ticket chain minted `ensure_run_tickets`: intake born `ready` and emits its work event immediately; others `pending`; stages whose latest attempt is ok born `done` | control/control/tickets.py:93-131 | run -> stage_tickets rows | minting `pending` against already-ok history forced full model re-execution (CHAIN-CREATION-RECONCILES-HISTORY) — control/control/tickets.py:99-104 |
| 16 | STAGE_DAG gates: extract needs artifact `manifest`; profile_document `documents_profiled`; project_qdrant `chunk_count` + receipt `qdrant`; project_neo4j `facts` + `neo4j`; canonicalize `canonical_entities`; project_canonical `memberships` + `neo4j`; verify_projections keys (`qdrant`, `routing_qdrant`, `neo4j`, `canonical`) | control/control/tickets.py:24-39 | predecessor artifacts/receipts -> ready ticket | stale declared key `docs` blocked advancement for every post-rewrite chain (VERIFY-DAG-KEYS-V2) — control/control/tickets.py:32-38 |
| 17 | Qdrant receipt want-set: run-scoped chunk receipts (`missing_chunk_receipts_for_docs`, fallback `missing_chunk_receipts_for_run`) + routing kinds `routing_document_summary` / `routing_section_summary` / `routing_child` / `routing_procedure` / `routing_concept`, one set-based anti-join | control/control/census.py:434-503 | want-set minus active projection_receipts -> missing ids | missing -> gap `N projection receipts missing` re-arms project_qdrant.v1 — control/control/census.py:313-328 |
| 18 | Neo4j + canonical want-sets: eligible facts (`fact_eligible_sql`) + chunks; canonical_entities + memberships (`local_entity_id`) + evidence (`evidence_id`, kind `evidence_chunk`) | control/control/census.py:504-598 | -> missing ids | MENTION_ONLY-dependent facts are intentionally parked in Postgres, NOT projection failures — control/control/census.py:579-581 |
| 19 | background stages after settlement: compile_objects, parent_summary, document_summary, corpus_summary, vocabulary, doc_profile — all in NON_BLOCKING_STAGES; doc_parent_map tickets minted only by the flag-gated `auto_map_parents_on_chunks` scheduler phase, absent from STAGE_DAG | control/control/tickets.py:40-77, 80-81 | -> summary artifacts | failure degrades summaries to DEGRADED, never blocks QUERY_READY; phase B moves doc_profile ahead of verify_projections — control/control/tickets.py:52-57 |
| 20 | EXTRACTION-COVERAGE-V1 promotion barrier: `coverage_verdict` over artifacts `payload->'llm_extraction'->'stats'` with coverage_floor / drop_tolerance | control/control/census.py:313-339, 413-430 | stats -> reasons | reasons -> `census.degrade[run_id]`; the scheduler marks the run degraded — control/control/census.py:54-57 |
| 21 | settle: complete + not failed + no barrier reasons -> `census.promote`; watermark (max of attempts, created_at, stage_tickets.updated_at) written in the same transaction as the tick's work | control/control/census.py:339, 357-378, 87-90; control/control/tickets.py:5-6 | Census -> promote/fail/degrade + scheduler_cursors | crash rolls watermark and tick work back together (safe replay) |

## state written

| store | what | anchor |
|---|---|---|
| spool volume file | `ref` dict {store, key, sha256, bytes}; Postgres never holds the bytes | orchestrator/orchestrator/api/ui.py:487-493, 518; shared/polymath_shared/intake_submission.py:36-39 [DERIVED] |
| Postgres `runs` | run_id, corpus_id, status `'intake'`, metadata {source_name, intake_payload} | shared/polymath_shared/intake_submission.py:83-92 [DERIVED] |
| Postgres `outbox_events` | run_id, event_type `'intake.v1'`, payload, idempotency_key | shared/polymath_shared/intake_submission.py:94-100 [DERIVED] |
| Postgres `stage_attempts` | run_id, stage, outcome, started_at; written inside stage transactions | control/control/census.py:66-69, 224-230 [DERIVED] |
| Postgres `stage_tickets` | ticket_id (`"tkt_" + content_hash(...)[:32]`), run_id, corpus_id, stage, event_type, status | control/control/tickets.py:89-90, 119-127 [DERIVED] |
| Postgres `scheduler_cursors` | stage `'__census__'`, corpus_id `'__global__'`, last_seq = epoch-micros watermark | control/control/census.py:91-92, 122-128 [DERIVED] |
| Postgres `artifacts` | extract-stage payload carrying `llm_extraction` stats | control/control/census.py:416-421 [DERIVED] |
| Postgres `projection_receipts` | projection `'qdrant'`/`'neo4j'`, entity_kind, entity_id, active | control/control/census.py:492-497, 517-520 [DERIVED] |
| Qdrant / Neo4j projections | no collection or bucket names appear in SOURCE; convergence is observed only via projection_receipts | control/control/census.py:457-503 [INFERRED: receipts are the only projection evidence shown] |
| process-local caches | `_HISTORY_CACHE`, `_VERDICT_CACHE` — cold after restart, rebuilt by backfill/full pass | control/control/census.py:93-94, 236-237, 279-284 [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| POLYMATH_UPLOAD_MAX_MB | `"200"` | max bytes = MB*1024*1024; beyond -> 413 | orchestrator/orchestrator/api/ui.py:507 |
| allow_near_duplicate (form field) | `""` | truthy in ("1", "true", "yes", "on") -> config `{"allow_near_duplicate": True}` inside the canonical payload; layers 1/2 not overridable | orchestrator/orchestrator/api/ui.py:487, 542-549 |
| POLYMATH_CENSUS_MODE | `"auto"` | `full` forces the authoritative full sweep; `auto` -> incremental only when a watermark exists | control/control/census.py:158-167, 85-86 |
| POLYMATH_CENSUS_AUDIT | unset | `1` forces mode full | control/control/census.py:159-160 |
| max_attempts (compute_census kwarg) | `3` | per-stage retry budget; failed beyond it fails the run | control/control/census.py:140, 402-407 |
| coverage_floor | `0.0` | coverage floor for the promotion barrier | control/control/census.py:142, 334-336 |
| drop_tolerance | `None` | drop allowance passed to coverage_verdict | control/control/census.py:143, 334-336 |
| auto_map_parents_on_chunks | not stated in SOURCE | gates the scheduler phase that mints doc_parent_map tickets (absent from STAGE_DAG) | control/control/tickets.py:73-76 |
| DEFAULT_HIGH_WATERMARK | `64` | per-stage pending high watermark pauses new intake tickets (backpressure) | control/control/tickets.py:5-6, 86 |

## failure modes

1. 403 `CORPUS_NOT_ALLOWED` -> principal's `writable_corpus_ids` excludes the corpus (None = owner/trusted local caller = all) -> orchestrator/orchestrator/web_scope.py:57-58, 72-87
2. 422 unsupported extension / 413 exceeds max / 422 empty file -> ext gate, seek-END size check, zero-byte guard -> orchestrator/orchestrator/api/ui.py:502-520
3. 409 `duplicate_document` -> raw sha256 already in `documents.source_hash` for the corpus, whatever the file is named; layer 1 never overridable -> orchestrator/orchestrator/api/ui.py:521-542
4. Silent no-op on replay -> identical canonical payload -> identical run_id -> `submit_intake` returns `already_exists: True` without writing (by design, not a bug) -> shared/polymath_shared/intake_submission.py:75-81; shared/polymath_shared/identity.py:59-62
5. ValueError at payload build -> both/neither of content_b64/content_ref, or content_ref missing store/key/sha256/bytes -> shared/polymath_shared/intake_submission.py:41-56
6. Run pinned at `reconciling` forever -> ticket-DAG stages complete without stage_attempts, cached non-promote verdict replayed every tick -> guards: dirtiness over `stage_tickets.updated_at` and gap verdicts never cached -> control/control/census.py:65-80, 195-200, 341-348
7. Active run stuck while a sibling promotes -> uncached active whose ticket close fell under a global watermark advanced by the sibling within the same tick -> CENSUS-UNCACHED-DIRTY-V1 re-evaluates uncached actives -> control/control/census.py:207-217
8. Run fails outright -> stage outcome `failed` with count >= max_attempts (3) -> `census.fail` -> control/control/census.py:402-407
9. Chain complete but corpus never query_ready -> extract dropped or lost track of neighborhoods -> `census.degrade[run_id]` with coverage_verdict reasons, scheduler marks degraded -> control/control/census.py:54-57, 330-339
10. Ok stage keeps re-arming -> missing active projection_receipts (store loss cleared by VERIFY) -> gap `N projection receipts missing` re-drives the projector -> control/control/census.py:313-328
11. Ticket advancement blocked after the verifier rewrite -> stale declared artifact key `docs` vs verifier keys {qdrant, routing_qdrant, neo4j, canonical} -> summary stages never ready, corpus cannot promote -> control/control/tickets.py:32-39
12. Full model re-execution on chain creation -> tickets minted `pending` although attempts were ok -> stages now born `done` -> control/control/tickets.py:99-104
13. Summary successors never advance -> summary stages write no stage_attempts so the ok-probe is permanently False -> durable `done` ticket counts as completion proof (SUMMARY-ATTEMPT-EQUIVALENCE) -> control/control/tickets.py:151-163
14. Tick transaction held open for minutes -> per-entity receipt SELECT loop inside the tick queued every worker claim behind it -> set-based anti-join, one query, deterministic order -> control/control/census.py:452-456, 457-503
15. Near-duplicate decision invisible at upload -> layer 3 (same text, different container) lives in the intake worker where extracted text exists; keep_both reaches it via the payload config -> orchestrator/orchestrator/api/ui.py:526-528, 539-549

## invariants

- INVARIANT SPOOL-CLAIM-CHECK-V1: the request body is transport, never pipeline state; Postgres never holds the bytes (orchestrator/orchestrator/api/ui.py:487-492) [DERIVED]
- INVARIANT: run identity is content-addressed via the sha256 inside the payload; replaying the same intake over a corpus is a no-op at the Postgres level (shared/polymath_shared/identity.py:59-62) [DERIVED]
- INVARIANT: the run row and its intake.v1 outbox event commit in one transaction (shared/polymath_shared/intake_submission.py:64-65) [DERIVED]
- INVARIANT CENSUS-FIRST-GAP-V1: the chain walk stops at the first stage that is not ok; nothing after it is emitted (control/control/census.py:390-410) [DERIVED]
- INVARIANT CENSUS-DIRTY-SIGNAL-V2 guard 2: a verdict carrying GAPS is never cached (control/control/census.py:77-80, 343-348) [DERIVED]
- INVARIANT EXTRACTION-COVERAGE-V1: a complete chain whose extract stage dropped or lost track of neighborhoods is never query_ready (control/control/census.py:330-339) [DERIVED]
- INVARIANT: projection stages carry their own event types so two projectors never race over one shared outbox row (control/control/census.py:15-23) [DERIVED]
- INVARIANT: a stage is handed work only when its predecessors' durable evidence exists — ordered STAGE_DAG artifact/receipt checks (control/control/tickets.py:20-23) [DERIVED]
- INVARIANT: non-blocking stage incompleteness never blocks promotion — knowledge=READY while summaries=DEGRADED (control/control/tickets.py:60-62, 80-81) [DERIVED]
- INVARIANT: duplicate layers 1 and 2 are never overridable; only layer 3 accepts keep_both (orchestrator/orchestrator/api/ui.py:540-542) [DERIVED]
- INVARIANT: the census watermark is written in the same transaction as the tick's work; a crash rolls both back together (control/control/census.py:87-90, 374-378) [DERIVED]

## VERIFY

```verify
grep -Fq 'SPOOL-CLAIM-CHECK-V1' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'ON CONFLICT (idempotency_key) DO NOTHING' shared/polymath_shared/intake_submission.py
grep -Fq 'run_' shared/polymath_shared/identity.py
grep -Fq 'POLYMATH_CENSUS_MODE' control/control/census.py
grep -Fq 'routing_qdrant' control/control/tickets.py
grep -Fq 'NON_BLOCKING_STAGES' control/control/tickets.py
test "$(grep -c -F 'stage_tickets' control/control/census.py)" -ge 3
```
