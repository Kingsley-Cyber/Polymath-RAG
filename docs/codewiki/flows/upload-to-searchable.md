# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY: `POST /upload` → `orchestrator/orchestrator/api/ui.py:467` `upload` (write scope).

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Entry: form fields `corpus_id`, `file`, `allow_near_duplicate` (default `""`) | `orchestrator/orchestrator/api/ui.py:467-469` | multipart form -> handler | — |
| 2 | Write-scope gate: `require_corpus(corpus_id, write=True)` -> `can_see` -> `allowed_corpora(write)`; principal `None` = every library, else membership in `p.writable_corpus_ids` | `orchestrator/orchestrator/api/ui.py:476`, `orchestrator/orchestrator/web_scope.py:85-87`, `web_scope.py:80-82`, `web_scope.py:72-77` | corpus_id -> allow/refuse | 403 `CORPUS_NOT_ALLOWED` via `_refuse` (`web_scope.py:57-58`) |
| 3 | Filename gate: `os.path.basename`, ext lowercased, must be in `_UPLOAD_EXTENSIONS` | `orchestrator/orchestrator/api/ui.py:483-488` | filename -> ext | 422 `unsupported extension` |
| 4 | Size cap: `POLYMATH_UPLOAD_MAX_MB` (default `"200"`) × 1024 × 1024; seek-END/tell check on the Starlette temp file | `orchestrator/orchestrator/api/ui.py:489-498` | file handle -> byte count | 413 `file exceeds ... bytes` |
| 5 | Spool write: `spool_write` off-thread via `anyio.to_thread.run_sync`, 1 MiB chunks, sha256 computed in flight (SPOOL-CLAIM-CHECK-V1); bytes never sit in process memory | `orchestrator/orchestrator/api/ui.py:495-500` | `file.file` -> `content_ref` `{store, key, sha256, bytes}` | 422 `empty file` when `ref["bytes"] == 0` (`ui.py:501-502`) |
| 6 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1 (byte-identical): `SELECT source_name FROM documents WHERE corpus_id = %s AND source_hash = %s` | `orchestrator/orchestrator/api/ui.py:511-520` | (corpus_id, raw sha256) -> dup row | 409 `duplicate_document`; layer 1 never overridable |
| 7 | NEAR-DUPLICATE-GUARD-V1 override: `allow_near_duplicate.strip().lower()` in `("1","true","yes","on")` -> `config={"allow_near_duplicate": True}` rides in the payload so worker layer 3 sees it | `orchestrator/orchestrator/api/ui.py:521-531` | form flag -> payload config | layers 1 and 2 are never overridable |
| 8 | `canonical_intake_payload`: base `{corpus_id, source_name, media_type, config}` + exactly one of `content_b64` / `content_ref`; validates `store,key,sha256,bytes` fields | `shared/polymath_shared/intake_submission.py:24-57` | fields -> canonical payload dict | `ValueError` "exactly one of content_b64 / content_ref is required" (:41-43) or "content_ref missing {field!r}" (:53-56) |
| 9 | Transaction: `tx()` takes a pooled connection (`min_size=1`, `max_size=8`, `autocommit=False`); commits on clean exit, rolls back on exception | `shared/polymath_shared/db.py:44-54`, `db.py:34-40`, `db.py:23-31` | payload -> Connection | any exception rolls back run+outbox together |
| 10 | `submit_intake` (idempotent): `run_id = "run_" + content_hash({'corpus','intake'})` where hash = sha256 of canonicalized JSON (sort_keys, compact separators, `ensure_ascii=False`, UTF-8); existing run row -> `already_exists=True`; else `INSERT INTO runs (... status 'intake' ...)` + `INSERT INTO outbox_events (... 'intake.v1' ... ON CONFLICT (idempotency_key) DO NOTHING)` | `shared/polymath_shared/intake_submission.py:60-101`, `shared/polymath_shared/identity.py:59-62`, `identity.py:28-30`, `identity.py:16-25` | payload -> `{run_id, accepted, already_exists}` | `ValueError` "content_b64 is not valid base64" / "payload carries neither..." (:67-73); replay is a no-op |
| 11 | Response: submit result plus `corpus_id`, `source_name`, `bytes`, `sha256`, `near_duplicate_override` | `orchestrator/orchestrator/api/ui.py:535-537` | out -> JSON | — |
| 12 | Census picks the run up: `compute_census` selects runs with `status IN ('intake','reconciling','degraded')` ordered by `created_at, run_id`; mode `auto` -> `incremental` if a watermark exists else `full` | `control/control/census.py:140-179` | runs rows -> Census | cold controller without watermark falls back to full pass (:162-167) |
| 13 | Dirty selection (incremental): `stage_attempts.started_at` and `stage_tickets.updated_at` within lookback (watermark + 1 s overlap), plus new runs and any active run with no cached verdict | `control/control/census.py:182-217` | watermark -> changed set | missed dirty signal pins run at `reconciling` (guards at :186-217) |
| 14 | `chain_verdict` first-gap walk over `STAGE_CHAIN = ["intake","extract","profile_document","project_qdrant","project_neo4j","canonicalize","project_canonical","verify_projections"]`: stops at first non-ok stage; `failed` under `max_attempts=3` -> retry gap; `failed` at budget -> run fails; missing -> one gap, nothing after emitted | `control/control/census.py:386-410`, `census.py:19` | attempts -> (gaps, complete, failed) | run lands in `census.fail` (:406-407, :310-311) |
| 15 | Each gap re-arms its stage's outbox event via `STAGE_EVENTS` (`intake.v1`, `chunked.v1`, `profile_document.v1`, `project_qdrant.v1`, `project_neo4j.v1`, `canonicalize.v1`, `project_canonical.v1`, `verify.v1`) | `control/control/census.py:304-309`, `census.py:28-37` | Gap -> outbox event | cached gap verdict would re-arm unclaimable events forever — guard: gap verdicts never cached (:343-348) |
| 16 | `ensure_run_tickets` mints the per-run ticket chain from `STAGE_DAG`; intake born `ready` (work event emitted immediately, `_emit_ticket_event`); stages whose latest attempt is `ok` or that hold a `done` ticket are born DONE (SUMMARY-ATTEMPT-EQUIVALENCE) | `control/control/tickets.py:93-137`, `tickets.py:140-163`, `tickets.py:24-58` | run -> stage_tickets rows | minting completed stages PENDING forced full model re-execution (:99-104) |
| 17 | DAG progression, each gated on predecessor artifacts + receipts: `extract`(`manifest`) -> `profile_document`(`documents_profiled`) -> `project_qdrant`(`chunk_count`, receipt `qdrant`) -> `project_neo4j`(`facts`, receipt `neo4j`) -> `canonicalize`(`canonical_entities`) -> `project_canonical`(`memberships`, receipt `neo4j`) -> `verify_projections`(artifacts `qdrant, routing_qdrant, neo4j, canonical`) | `control/control/tickets.py:24-39` | artifacts + receipts -> next ticket ready | stale declared key `docs` blocked every post-rewrite run (:32-38) |
| 18 | Background stages after settlement: `compile_objects`, `parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`, `doc_profile` — all in `NON_BLOCKING_STAGES`; failure degrades summaries, never blocks QUERY_READY | `control/control/tickets.py:40-77`, `tickets.py:80-81` | admitted mentions + chunk text -> summaries / concepts / procedures | degraded summaries only |
| 19 | Owner/auto-minted extras: `parent_enrichment` (enrichment buttons) and `doc_parent_map` (flag-gated `auto_map_parents_on_chunks` phase) are absent from STAGE_DAG and non-blocking | `control/control/tickets.py:67-76` | trigger -> ticket | lingering ticket cannot hold promotion |
| 20 | Receipt census on complete chains: qdrant — run-scoped chunk receipts (`_run_doc_ids`, legacy falls back corpus-wide) + routing kinds (`routing_document_summary`, `routing_section_summary`, `routing_child`, `routing_procedure`, `routing_concept`) via one set-based anti-join; neo4j — eligible facts + chunks; canonical — `canonical_entities`, `canonical_memberships`, `evidence_chunk` | `control/control/census.py:433-576` | want-set vs `projection_receipts` -> missing ids | missing receipts -> gap re-drives the projector (:322-328); per-entity loop variant held ticks open for minutes (:452-456) |
| 21 | EXTRACTION-COVERAGE-V1 barrier: complete chain's extract stats (`artifacts.payload->'llm_extraction'->'stats'`) run through `coverage_verdict(floor, drop_tolerance)`; reasons -> `census.degrade`, else `census.promote`; verdict cache + watermark (`scheduler_cursors` stage `__census__`, corpus `__global__`) written inside the caller's transaction | `control/control/census.py:326-339`, `census.py:413-430`, `census.py:341-378`, `census.py:91-92` | extract stats -> promote / degrade | dropped/unaccounted neighborhoods -> degraded, never query_ready |

## state written

| store | what | anchor |
|---|---|---|
| spool volume | blob file referenced by `content_ref` `{store, key, sha256, bytes}`; Postgres never holds the bytes | `orchestrator/orchestrator/api/ui.py:470-475`, `ui.py:500` |
| Postgres `runs` | `run_id`, `corpus_id`, `status 'intake'`, `metadata` carrying `source_name` + full `intake_payload` | `shared/polymath_shared/intake_submission.py:83-92` |
| Postgres `outbox_events` | `intake.v1` event with `idempotency_key` = content hash of `{run, type, payload}` | `shared/polymath_shared/intake_submission.py:93-100` |
| Postgres `documents.source_hash` | original-bytes hash recorded by the intake worker; matched by upload layer-1 guard | `orchestrator/orchestrator/api/ui.py:503-515` |
| Postgres `stage_attempts` | written inside stage transactions; the census's mutator signal | `control/control/census.py:60-65` |
| Postgres `stage_tickets` | full per-run DAG; intake `ready`, others `pending`/`done` | `control/control/tickets.py:119-127` |
| Postgres `projection_receipts` | rows `(projection 'qdrant'/'neo4j', entity_kind, entity_id, active)` for chunks, routing ids, facts, canonical entities/memberships, evidence | `control/control/census.py:457-475`, `census.py:509-575` |
| Postgres `scheduler_cursors` | census watermark (`stage='__census__'`, `corpus_id='__global__'`, `last_seq` epoch-micros), written in the tick transaction | `control/control/census.py:91-92`, `census.py:122-128`, `census.py:374-378` |
| Postgres `artifacts` | per-stage artifacts incl. extract stats under `payload->'llm_extraction'->'stats'`; verify writes `{qdrant, routing_qdrant, neo4j, canonical}` | `control/control/census.py:416-423`, `control/control/tickets.py:32-38` |
| Qdrant / Neo4j | projection stores whose convergence is proven by the receipts above | `control/control/census.py:313-328` [INFERRED: receipts are the observable; the writes live in worker code not shown] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | upload size cap in MiB (×1024×1024 bytes) | `orchestrator/orchestrator/api/ui.py:489` |
| `allow_near_duplicate` (form) | `""` | truthy in `("1","true","yes","on")` sets `config={"allow_near_duplicate": True}` for worker layer 3 | `orchestrator/orchestrator/api/ui.py:469`, `ui.py:525-531` |
| `POLYMATH_CENSUS_MODE` | `"auto"` | `auto` -> incremental when watermark exists, else full; `full` forces full sweep | `control/control/census.py:158-163` |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces full mode | `control/control/census.py:159-160` |
| `max_attempts` | `3` | per-stage retry budget before a failed run enters `census.fail` | `control/control/census.py:141`, `census.py:402-407` |
| `coverage_floor` | `0.0` | extraction coverage floor for the promotion barrier | `control/control/census.py:142`, `census.py:426-430` |
| `drop_tolerance` | `None` | tolerance passed to `coverage_verdict` | `control/control/census.py:143` |
| `DEFAULT_HIGH_WATERMARK` | `64` | per-stage pending high watermarks pause new intake tickets (backpressure) | `control/control/tickets.py:86`, `tickets.py:2-7` |

## failure modes

1. 403 `CORPUS_NOT_ALLOWED` -> corpus not in the principal's `writable_corpus_ids` (principal `None` = owner, all allowed) -> `orchestrator/orchestrator/web_scope.py:85-87`, `web_scope.py:72-77`.
2. 422 `unsupported extension` -> ext not in `_UPLOAD_EXTENSIONS` -> `orchestrator/orchestrator/api/ui.py:485-488`.
3. 413 `file exceeds ... bytes` -> spooled temp file larger than cap -> `orchestrator/orchestrator/api/ui.py:496-498`.
4. 422 `empty file` -> `ref["bytes"] == 0` after spool -> `orchestrator/orchestrator/api/ui.py:501-502`.
5. 409 `duplicate_document` -> byte-identical file already in corpus under `documents.source_hash`; not overridable -> `orchestrator/orchestrator/api/ui.py:511-520`.
6. `ValueError` on payload shape -> both/neither of `content_b64`/`content_ref`, or `content_ref` missing a field -> `shared/polymath_shared/intake_submission.py:41-43`, `:53-56`, `:67-73`.
7. Run pinned at `reconciling` forever -> summary stages complete tickets without `stage_attempts`, so a cached non-promote verdict replayed indefinitely -> guards: dirtiness also tracks `stage_tickets.updated_at` and gap verdicts are never cached -> `control/control/census.py:60-80`, `:186-200`, `:343-348`.
8. Stuck active run while a sibling promotes -> run with no cached verdict whose last ticket close fell under the lookback after the global watermark advanced -> guard: uncached actives are dirty by definition -> `control/control/census.py:207-217`.
9. Ticket advancement blocked after verifier rewrite -> stale declared artifact key `docs`; verifier actually writes `{qdrant, routing_qdrant, neo4j, canonical}` -> `control/control/tickets.py:32-38`.
10. Whole-tick stall -> receipt census as a per-entity SELECT loop inside the tick transaction (hundreds of round trips, ticks held open for minutes) -> replaced by one set-based anti-join -> `control/control/census.py:452-456`.
11. Silent degradation instead of promotion -> complete chain but extract recorded dropped/unaccounted neighborhoods -> run enters `census.degrade` with reasons, never `query_ready` -> `control/control/census.py:54-57`, `:331-339`.
12. Legacy-history replay -> minting already-completed stages PENDING forced full model re-execution and barrier-blocked the corpus -> ok-attempt / done-ticket stages now born DONE -> `control/control/tickets.py:99-104`, `:140-163`.
13. Same text, different container (layer 2) and near-duplicate (layer 3) -> decided in the intake worker where extracted text exists, not on this path -> `orchestrator/orchestrator/api/ui.py:508-510`, `:521-524`.

## invariants

- INVARIANT Postgres never holds the uploaded bytes; the request body is transport, content lives behind `content_ref` — SPOOL-CLAIM-CHECK-V1 (`orchestrator/orchestrator/api/ui.py:470-475`).
- INVARIANT Run identity is content-addressed: `run_` + sha256 of the canonical payload; replaying the same intake over a corpus yields the same run id, so re-intake is a no-op at the Postgres level (`shared/polymath_shared/identity.py:59-62`).
- INVARIANT A payload carries exactly one content variant: `content_b64` or `content_ref` (`shared/polymath_shared/intake_submission.py:34-43`).
- INVARIANT The run row and the `intake.v1` outbox event commit in a single transaction, idempotent by content identity (`shared/polymath_shared/intake_submission.py:64-66`, `:79-100`).
- INVARIANT Duplicate layers 1 (identical bytes) and 2 (identical text) are never overridable; only near-duplicate layer 3 is (`orchestrator/orchestrator/api/ui.py:521-524`).
- INVARIANT A verdict carrying gaps is never cached; gaps are transient by definition (`control/control/census.py:343-348`).
- INVARIANT The census watermark is written in the same transaction as the tick's resulting work — a crash rolls both back together (`control/control/census.py:374-378`, `:86-90`).
- INVARIANT A stage's work event exists only after the control plane verifies the predecessor's artifacts, receipts, and contract (`control/control/tickets.py:2-7`).
- INVARIANT Stages in `NON_BLOCKING_STAGES` can never hold promotion: knowledge=READY while summaries=DEGRADED (`control/control/tickets.py:60-77`).
- INVARIANT A complete chain whose extract stage dropped or lost track of neighborhoods is never query_ready (`control/control/census.py:331-339`).

## VERIFY

```verify
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'duplicate_document' orchestrator/orchestrator/api/ui.py
grep -Fq 'intake.v1' shared/polymath_shared/intake_submission.py
grep -Fq 'POLYMATH_CENSUS_MODE' control/control/census.py
grep -Fq 'NON_BLOCKING_STAGES' control/control/tickets.py
grep -Fq 'DEFAULT_HIGH_WATERMARK = 64' control/control/tickets.py
```
