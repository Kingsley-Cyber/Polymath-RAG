# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY: POST /upload -> `upload` (orchestrator/orchestrator/api/ui.py:485)

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | POST /upload enters `upload(corpus_id: Form, file: UploadFile, allow_near_duplicate: Form(""))` | orchestrator/orchestrator/api/ui.py:485-487 | multipart form -> handler; Starlette parser already streamed body to a disk-spooled temp file | malformed multipart handled upstream of the handler (ui.py:509-512) |
| 2 | Write-scope check `require_corpus(corpus_id, write=True)` -> `can_see` -> `allowed_corpora` | orchestrator/orchestrator/api/ui.py:494; orchestrator/orchestrator/web_scope.py:80-87, 72-77 | corpus_id + `current_principal()` -> ok / raise | 403 `CORPUS_NOT_ALLOWED` ("not open to this account for writing") |
| 3 | Extension gate: `ext` must be in `_UPLOAD_EXTENSIONS` | orchestrator/orchestrator/api/ui.py:501-506 | filename -> ext | 422 `unsupported extension {ext!r}` |
| 4 | Size gate: `POLYMATH_UPLOAD_MAX_MB` * 1024 * 1024 | orchestrator/orchestrator/api/ui.py:507, 513-516 | temp file size -> bool | 413 `file exceeds {max_bytes} bytes` |
| 5 | `spool_write` re-streams 1 MiB chunks to the spool volume, sha256 in flight (SPOOL-CLAIM-CHECK-V1) | orchestrator/orchestrator/api/ui.py:488-492, 518 | `file.file` -> `ref = {store, key, sha256, bytes}` | any spool error aborts before any DB write [INFERRED: no tx opened yet] |
| 6 | Empty-file gate | orchestrator/orchestrator/api/ui.py:519-520 | `ref["bytes"] == 0` | 422 `empty file` |
| 7 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1: `SELECT source_name FROM documents WHERE corpus_id=%s AND source_hash=%s` | orchestrator/orchestrator/api/ui.py:521-538 | (corpus_id, sha256) -> dup row or none | 409 `duplicate_document`; layers 1 and 2 are never overridable (ui.py:539-542) |
| 8 | `keep_both` parse: `allow_near_duplicate` in ("1","true","yes","on"); override rides in payload `config={"allow_near_duplicate": True}` | orchestrator/orchestrator/api/ui.py:542-549 | form string -> bool + config | near-duplicate refusal surfaces later in the intake worker (layer 3) |
| 9 | `canonical_intake_payload` builds the canonical dict | shared/polymath_shared/intake_submission.py:24-57 | fields -> payload with `content_ref` | `ValueError` "exactly one of content_b64 / content_ref is required" or "content_ref missing {field!r}" |
| 10 | `submit_intake` computes `rid = run_id(corpus_id, payload)` = `run_<content_hash({'corpus':..., 'intake':...})>` | shared/polymath_shared/intake_submission.py:75-76; shared/polymath_shared/identity.py:59-62 | payload -> run_id | none (pure hash) |
| 11 | Idempotency probe: `SELECT 1 FROM runs WHERE run_id = %s` | shared/polymath_shared/intake_submission.py:79-81 | rid -> existing row? | silent no-op: returns `already_exists: True`, no new work |
| 12 | `INSERT INTO runs (status 'intake', metadata = {source_name, intake_payload})` + `INSERT INTO outbox_events ('intake.v1', idempotency_key) ON CONFLICT DO NOTHING`, one `tx()` | shared/polymath_shared/intake_submission.py:83-101; shared/polymath_shared/db.py:44-54 | payload -> run row + outbox event | any exception -> `conn.rollback()` |
| 13 | Response `{**out, corpus_id, source_name, bytes, sha256, near_duplicate_override}` | orchestrator/orchestrator/api/ui.py:553-555 | out + ref -> JSON dict | — |
| 14 | Census tick: `SELECT ... FROM runs WHERE r.status IN ('intake','reconciling','degraded') ORDER BY r.created_at, r.run_id` | control/control/census.py:170-179 | runs table -> candidate set | cold controller with no watermark falls back to full mode (census.py:163-167) |
| 15 | Dirty select (incremental): `stage_attempts.started_at` + `stage_tickets.updated_at` inside lookback (1 s overlap) + new runs + uncached active runs | control/control/census.py:182-217 | watermark -> changed set | miss = run keeps prior cached verdict (fixed by CENSUS-UNCACHED-DIRTY-V1) |
| 16 | `chain_verdict` first-gap walk over STAGE_CHAIN with retry budget `max_attempts=3` | control/control/census.py:386-410 | last/count by stage -> (gaps, complete, failed) | failed beyond budget -> run in `census.fail`; only the FIRST non-ok stage becomes a gap |
| 17 | Each gap re-arms the stage's outbox event via `STAGE_EVENTS[stage]` | control/control/census.py:28-37, 304-309 | gap -> event type (intake.v1, chunked.v1, ...) | — |
| 18 | `ensure_run_tickets` mints the chain: intake born `ready` (event emitted immediately); stages with an ok attempt born `done`; others `pending` | control/control/tickets.py:93-137 | run -> `stage_tickets` rows | minting `pending` for already-ok stages forced full model re-execution (fixed, tickets.py:99-104) |
| 19 | Stage DAG handoff: extract(`manifest`) -> profile_document(`documents_profiled`) -> project_qdrant(`chunk_count` + qdrant receipts) -> project_neo4j(`facts` + neo4j) -> canonicalize(`canonical_entities`) -> project_canonical(`memberships` + neo4j) -> verify_projections(`qdrant`,`routing_qdrant`,`neo4j`,`canonical`) | control/control/tickets.py:24-39; control/control/census.py:19, 22-27 | ticket -> work event only after predecessor artifacts + receipts verified | stale declared artifact key blocked advancement (VERIFY-DAG-KEYS-V2, tickets.py:32-38) |
| 20 | Receipt census on a complete chain: qdrant chunks + routing kinds (`routing_document_summary`,`routing_section_summary`,`routing_child`,`routing_procedure`,`routing_concept`); neo4j facts + chunks + canonical entities/memberships/evidence | control/control/census.py:313-328, 433-576 | want-set -> missing list | any missing -> gap "N projection receipts missing", `complete = False`, projector re-drives |
| 21 | EXTRACTION-COVERAGE-V1 barrier: `coverage_verdict(extraction_stats(...))` | control/control/census.py:330-339, 413-430 | extract stats -> reasons | silent degrade: chain complete but run lands in `census.degrade`, never promoted |
| 22 | Verdict: complete + not failed + no barrier reasons -> `census.promote`; gap verdicts never cached | control/control/census.py:330-339, 341-355 | chain state -> promote/degrade/fail | cached gap would re-arm unclaimable events forever (guard, census.py:76-80) |
| 23 | Watermark advance over max(stage_attempt time, ticket `updated_at`, run `created_at`), written in the caller's transaction | control/control/census.py:361-378 | max_seen_us -> `scheduler_cursors` | crash rolls watermark back with the tick's work (safe replay) |
| 24 | Background non-blocking stages after settlement: `compile_objects`, `parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`, `doc_profile` (rollout phase A) | control/control/tickets.py:40-66 | admitted mentions + chunk text -> artifacts | failure degrades summaries to DEGRADED, never blocks QUERY_READY |
| 25 | `doc_parent_map` and `parent_enrichment` tickets minted ONLY by the flag-gated `auto_map_parents_on_chunks` scheduler phase / enrichment buttons; absent from STAGE_DAG | control/control/tickets.py:67-77 | owner action -> ticket | lingering ticket can never hold promotion |

## state written

| store | what | anchor |
|---|---|---|
| spool volume (blob store) | streamed file bytes; `content_ref = {store, key, sha256, bytes}` via `spool_write` | orchestrator/orchestrator/api/ui.py:488-492, 518 |
| Postgres `runs` | (run_id, corpus_id, status `'intake'`, metadata = `{source_name, intake_payload}`) | shared/polymath_shared/intake_submission.py:83-92 |
| Postgres `outbox_events` | (run_id, event_type `'intake.v1'`, payload, idempotency_key = content_hash of {run, type, payload}) | shared/polymath_shared/intake_submission.py:77, 93-100 |
| Postgres `documents.source_hash` | original-bytes hash recorded by the intake worker (read here for the duplicate guard) | orchestrator/orchestrator/api/ui.py:521-524 |
| Postgres `stage_tickets` | (ticket_id = `tkt_` + hash[:32], run_id, corpus_id, stage, event_type, status) | control/control/tickets.py:89-90, 119-127 |
| Postgres `stage_attempts` | written inside stage transactions; read as census history | control/control/census.py:60-63, 224-237, 280-284 |
| Postgres `scheduler_cursors` | stage `'__census__'`, corpus_id `'__global__'`, last_seq = epoch-micros watermark | control/control/census.py:91-92, 122-128, 374-378 |
| Postgres `projection_receipts` | projection `'qdrant'` (chunk + routing kinds) and `'neo4j'` (`fact`, `chunk`, `canonical_entity`, `canonical_membership`, `evidence_chunk`); cleared by VERIFY on store loss | control/control/census.py:313-316, 493-497, 517-534, 546-560 |
| Qdrant | chunk vectors + neural routing representations (document/section/child/procedure/concept) — production dependencies for query-ready (R1B) | control/control/census.py:450-456, 459-491 |
| Neo4j | eligible facts + chunk nodes (I3R-R5), canonical entities/memberships, evidence chunks | control/control/census.py:505-507, 540-560 |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | upload cap in MiB (*1024*1024); larger -> 413 | orchestrator/orchestrator/api/ui.py:507 |
| `allow_near_duplicate` (form) | `""` | in ("1","true","yes","on") sets payload config `{"allow_near_duplicate": True}`; overrides only layer 3 (near-duplicate) | orchestrator/orchestrator/api/ui.py:487, 539-549 |
| `POLYMATH_CENSUS_MODE` | `"auto"` | auto -> incremental if watermark exists else full; `"full"` forces full sweep | control/control/census.py:158-167 |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces mode full (recovery/audit) | control/control/census.py:159-160 |
| `auto_map_parents_on_chunks` | not stated in SOURCE | flag-gated scheduler phase that auto-mints `doc_parent_map` tickets (never chain advancement) | control/control/tickets.py:73-75 |

## failure modes

1. 403 `CORPUS_NOT_ALLOWED` -> principal's `writable_corpus_ids` excludes the corpus -> orchestrator/orchestrator/web_scope.py:72-87
2. 422 `unsupported extension` / `empty file` -> ext outside `_UPLOAD_EXTENSIONS`, or `ref["bytes"] == 0` -> orchestrator/orchestrator/api/ui.py:502-506, 519-520
3. 413 `file exceeds` -> size over `POLYMATH_UPLOAD_MAX_MB` MiB -> orchestrator/orchestrator/api/ui.py:507, 513-516
4. 409 `duplicate_document` -> byte-identical file already in corpus (`documents.source_hash` match); layers 1/2 never overridable -> orchestrator/orchestrator/api/ui.py:521-542
5. Silent replay no-op -> same canonical payload -> same `run_id` -> `already_exists: True`, no new run/outbox row -> shared/polymath_shared/intake_submission.py:79-81; shared/polymath_shared/identity.py:59-62
6. Run pinned at `reconciling` forever -> verdict cached while summary tickets still pending (summary stages write no `stage_attempts`); guards: ticket `updated_at` tracked + gap verdicts never cached (CENSUS-DIRTY-SIGNAL-V2) -> control/control/census.py:60-80, 341-345
7. Active run never re-evaluated -> sibling's later ticket advanced the global watermark past its close within one tick; guard: uncached active runs are dirty (CENSUS-UNCACHED-DIRTY-V1) -> control/control/census.py:207-217
8. Chain complete but corpus never query_ready (silent) -> extraction coverage reasons -> `census.degrade` instead of promote -> control/control/census.py:54-57, 330-339, 426-430
9. Ok stage with missing receipts -> store loss cleared by VERIFY -> gap "N projection receipts missing" re-drives the projector -> control/control/census.py:313-328
10. Stage failed at/after `max_attempts` (default 3) -> run fails, not retried -> control/control/census.py:402-407
11. Ticket advancement blocked after the verifier rewrite -> stale declared artifact key `'docs'` vs actual `{qdrant, routing_qdrant, neo4j, canonical}` -> control/control/tickets.py:32-38
12. Forced full model re-execution on chain creation -> stages minted `pending` despite ok attempts; fix: born `done` -> control/control/tickets.py:99-104, 115-117

## invariants

- INVARIANT the request body is transport, never pipeline state; Postgres never holds the bytes (orchestrator/orchestrator/api/ui.py:488-492) [DERIVED]
- INVARIANT run identity is content-addressed: `run_id = f"run_{content_hash({'corpus': corpus_id, 'intake': intake_payload})}"`; replaying the same intake is a Postgres-level no-op (shared/polymath_shared/identity.py:59-62)
- INVARIANT a payload carries exactly one of `content_b64` / `content_ref`; `content_ref` must contain `store`, `key`, `sha256`, `bytes` (shared/polymath_shared/intake_submission.py:41-43, 52-56)
- INVARIANT the run row and the `intake.v1` outbox event commit in a single transaction; the outbox insert is idempotent on `idempotency_key` (shared/polymath_shared/intake_submission.py:64-65, 95-98)
- INVARIANT census is deterministic: runs sorted by `created_at, run_id`; attempts by `run_id, stage, started_at` (control/control/census.py:144-148, 170-178, 224-229)
- INVARIANT the chain walk stops at the first non-ok stage — exactly one gap, nothing after it (control/control/census.py:388-396)
- INVARIANT a verdict carrying gaps is never cached (control/control/census.py:76-79, 341-345)
- INVARIANT a complete chain with extraction coverage reasons is degraded, never promoted (control/control/census.py:54-57, 330-339)
- INVARIANT a stage's work event exists only after the control plane verifies predecessor artifacts, receipts, and contract (control/control/tickets.py:2-7)
- INVARIANT `canonicalize`/`project_canonical` run before `verify_projections` (control/control/census.py:22-27)
- INVARIANT summary/vocabulary/`doc_profile` (phase A) failures degrade summaries, never block QUERY_READY (control/control/tickets.py:60-66)

## VERIFY

```verify
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'duplicate_document' orchestrator/orchestrator/api/ui.py
grep -Fq 'content_ref' shared/polymath_shared/intake_submission.py
grep -Fq 'run_{content_hash' shared/polymath_shared/identity.py
grep -Fq 'POLYMATH_CENSUS_MODE' control/control/census.py
grep -Fq 'NON_BLOCKING_STAGES' control/control/tickets.py
test "$(grep -c -F 'projection_receipts' control/control/census.py)" -ge 5
grep -Fq 'CORPUS_NOT_ALLOWED' orchestrator/orchestrator/web_scope.py
```
