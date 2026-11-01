# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY: `POST /upload` -> `orchestrator/orchestrator/api/ui.py:533` `upload` (web class: write).

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `upload(corpus_id: str = Form(...), file: UploadFile = File(...), allow_near_duplicate: str = Form(""))` accepts the multipart POST | `orchestrator/orchestrator/api/ui.py:533-535` [DERIVED] | form fields + file -> handler invocation | malformed form (not shown in SOURCE) |
| 2 | `require_corpus(corpus_id, write=True)` (FRIENDS-ACCESS-V1 D5) -> `can_see`: write requires `corpus_id in p.writable_corpus_ids`; a write grant is explicit, the wildcard never opens a library for writing | `orchestrator/orchestrator/api/ui.py:542` [DERIVED], `orchestrator/orchestrator/web_scope.py:94-105` [DERIVED] | principal grant -> bool | refusal raises `_refuse("CORPUS_NOT_ALLOWED", "that library is not open to this account for writing")` = HTTPException 403 (`web_scope.py:70-71`) |
| 3 | extension allowlist: `ext = os.path.splitext(source_name)[1].lower()`; `if ext not in _UPLOAD_EXTENSIONS` -> 422 | `orchestrator/orchestrator/api/ui.py:549-554` [DERIVED] | filename -> ext | 422 `unsupported extension` |
| 4 | size cap: `max_bytes = int(os.environ.get("POLYMATH_UPLOAD_MAX_MB", "200")) * 1024 * 1024`; seek-end/tell check -> 413 | `orchestrator/orchestrator/api/ui.py:555,562-564` [DERIVED] | file handle -> byte count | 413 `file exceeds {max_bytes} bytes` |
| 5 | `spool_write` via `anyio.to_thread.run_sync`: re-streams in 1 MiB chunks, sha256 in flight -> `ref` `{store, key, sha256, bytes}`; `ref["bytes"] == 0` -> 422 | `orchestrator/orchestrator/api/ui.py:557-568` [DERIVED] | file handle -> spool ref | 422 `empty file`; bytes never sit in process memory as one buffer |
| 6 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1: `SELECT source_name FROM documents WHERE corpus_id = %s AND source_hash = %s` -> 409 | `orchestrator/orchestrator/api/ui.py:569-586` [DERIVED] | (corpus_id, sha256) -> dup row or none | 409 `{"error_code": "duplicate_document", ...}` naming the existing `source_name` |
| 7 | NEAR-DUPLICATE-GUARD-V1 override: `keep_both = allow_near_duplicate.strip().lower() in ("1", "true", "yes", "on")`; rides as `config={"allow_near_duplicate": True}` inside the canonical payload; layers 1 and 2 are never overridable | `orchestrator/orchestrator/api/ui.py:587-597` [DERIVED] | form flag -> payload config | layer-2 (same text, different container) lives in the intake worker, not in SOURCE |
| 8 | `canonical_intake_payload`: exactly one of `content_b64` / `content_ref` required; `content_ref` must carry `store`, `key`, `sha256`, `bytes` | `shared/polymath_shared/intake_submission.py:24-57` [DERIVED] | fields -> canonical payload dict | `ValueError("exactly one of content_b64 / content_ref is required")` / `content_ref missing {field!r}` |
| 9 | `tx()` hands a pooled connection (min_size=1, max_size=8, autocommit=False); commits on clean exit, rolls back on exception | `shared/polymath_shared/db.py:23-31,34-40,44-54` [DERIVED] | -> Connection | exception rolls back run + outbox together |
| 10 | `rid = run_id(corpus_id, payload)` = `f"run_{content_hash({'corpus': corpus_id, 'intake': intake_payload})}"` over `canonicalize` (sort_keys JSON, UTF-8, `separators=(",", ":")`) — run identity stays content-addressed via the sha256 inside the payload | `shared/polymath_shared/intake_submission.py:75-76` [DERIVED], `shared/polymath_shared/identity.py:16-30,59-62` [DERIVED] | payload -> run_id | none |
| 11 | idempotency check: `SELECT 1 FROM runs WHERE run_id = %s` -> `{"run_id": rid, "accepted": True, "already_exists": True}` | `shared/polymath_shared/intake_submission.py:79-81` [DERIVED] | run_id -> verdict | silent no-op replay of the same file |
| 12 | `INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', %s)` (metadata carries `source_name` + full `intake_payload`) and `INSERT INTO outbox_events ... 'intake.v1' ... ON CONFLICT (idempotency_key) DO NOTHING` with `outbox_key = content_hash({"run": rid, "type": "intake.v1", "payload": canonical_payload})` — one transaction | `shared/polymath_shared/intake_submission.py:64-100` [DERIVED] | payload -> run row + outbox event | outbox conflict silently skipped (idempotent by design) |
| 13 | response: `{**out, "corpus_id", "source_name", "bytes": ref["bytes"], "sha256": ref["sha256"], "near_duplicate_override": keep_both}` | `orchestrator/orchestrator/api/ui.py:601-603` [DERIVED] | submit result -> JSON | none |
| 14 | `ensure_run_tickets` mints the ticket chain (idempotent): intake born `ready` and `_emit_ticket_event` fires the work event at birth; a stage whose latest attempt is ok is born `done` (CHAIN-CREATION-RECONCILES-HISTORY); ticket_id = `"tkt_" + content_hash(...)[:32]` | `control/control/tickets.py:89-131` [DERIVED] | run_id -> stage_tickets rows | minting `pending` for already-ok stages forces full model re-execution and barrier-blocks the corpus (`tickets.py:99-104`) |
| 15 | blocking chain in STAGE_DAG order: `extract` (artifact `manifest`) -> `profile_document` -> `project_qdrant` (receipts `qdrant`) -> `project_neo4j` (receipts `neo4j`) -> `canonicalize` -> `project_canonical` -> `verify_projections` (keys `qdrant, routing_qdrant, neo4j, canonical`); a stage's work event exists ONLY after the control plane verifies the predecessor's artifacts, receipts, contract | `control/control/tickets.py:3-7,24-39` [DERIVED] | pending ticket -> work event | stale declared key `docs` blocked advancement for every post-rewrite run (`tickets.py:32-37`) |
| 16 | background stages `compile_objects, parent_summary, document_summary, corpus_summary, vocabulary, doc_profile` are in NON_BLOCKING_STAGES — a failure degrades summaries, never blocks QUERY_READY; `doc_parent_map` is ABSENT from STAGE_DAG, minted by the flag-gated `auto_map_parents_on_chunks` scheduler phase | `control/control/tickets.py:40-77` [DERIVED] | — | incomplete pMAP ticket can never hold promotion |
| 17 | census tick `compute_census` over runs `status IN ('intake', 'reconciling', 'degraded')`, ordered by `created_at, run_id`; mode `auto` -> `incremental` when a watermark exists, else `full`; `POLYMATH_CENSUS_AUDIT=1` forces full | `control/control/census.py:140-179` [DERIVED] | db state -> `Census{gaps, promote, fail, degrade}` | cold controller must seed via one full pass |
| 18 | dirty set (incremental) = recent `stage_attempts.started_at` + `stage_tickets.updated_at` (CENSUS-DIRTY-SIGNAL-V2) + new runs + any active run not in `_VERDICT_CACHE` (CENSUS-UNCACHED-DIRTY-V1), over a 1 s replay window | `control/control/census.py:182-217` [DERIVED] | watermark -> changed run set | missing signal pinned runs at `reconciling` forever (see failure 5/6) |
| 19 | `chain_verdict` first-gap walk (CENSUS-FIRST-GAP-V1): `ok` continues; `failed` with `count < max_attempts` (default 3) -> retry gap; `failed` beyond budget -> run fails; missing stage -> the one gap; gaps re-arm `STAGE_EVENTS[stage]` | `control/control/census.py:277-309,386-410` [DERIVED] | last/count by stage -> (gaps, complete, failed) | run lands in `census.fail`; replayed gap would re-arm unclaimable events forever (guard: gap verdicts never cached) |
| 20 | projection receipt census before promotion: qdrant want-set = run-scoped chunk receipts (RUN-SCOPED-RECEIPTS-V1) + `routing_document_summary, routing_section_summary, routing_child, routing_procedure, routing_concept` via one set-based anti-join; neo4j = eligible `fact` + `chunk`; canonical = `canonical_entity, canonical_membership, evidence_chunk`; missing receipts re-drive the projector (PLAN Phase F gate 1/2) | `control/control/census.py:313-328,433-575` [DERIVED] | want-set vs `projection_receipts` -> missing list | missing -> gap, `complete = False`; MENTION_ONLY-dependent facts are intentionally parked, not failures (`census.py:579-581`) |
| 21 | EXTRACTION-COVERAGE-V1 barrier on a complete chain: `coverage_verdict(extraction_stats(...))` reasons -> `census.degrade[run_id]`; no reasons -> `census.promote.append(run_id)`; promotion to query_ready is a generation barrier | `control/control/census.py:330-339,413-430` [DERIVED], `control/control/tickets.py:7` [DERIVED] | artifacts payload `llm_extraction.stats` -> promote/degrade | dropped/unaccounted neighborhoods keep the run degraded, never query_ready |
| 22 | watermark advance: `max_seen_us` over attempts + `created_at` + `max(stage_tickets.updated_at)` written to `scheduler_cursors (stage='__census__', corpus_id='__global__')` inside the caller's transaction — crash rolls watermark and tick work back together | `control/control/census.py:91-92,364-378` [DERIVED] | timings -> last_seq epoch-micros | watermark past a ticket close without re-evaluation (fixed by uncached-dirty guard) |

## state written

| store | what | anchor |
|---|---|---|
| spool volume | blob streamed in 1 MiB chunks; ref `{store, key, sha256, bytes}` | `orchestrator/orchestrator/api/ui.py:543,566` [DERIVED], `shared/polymath_shared/intake_submission.py:53-56` [DERIVED] |
| Postgres `runs` | row (run_id, corpus_id, status `'intake'`, metadata with `source_name` + `intake_payload`) | `shared/polymath_shared/intake_submission.py:83-92` [DERIVED] |
| Postgres `outbox_events` | `intake.v1` event with `idempotency_key` = content hash | `shared/polymath_shared/intake_submission.py:93-100` [DERIVED] |
| Postgres `stage_tickets` | one ticket per stage; `ready` at intake birth, `pending`/`done` otherwise | `control/control/tickets.py:119-127` [DERIVED] |
| Postgres `scheduler_cursors` | census watermark `('__census__', '__global__', last_seq)` | `control/control/census.py:122-128` [DERIVED] |
| Postgres `projection_receipts` | read here as the promotion contract (qdrant routing kinds, neo4j fact/chunk/canonical kinds); written by the projectors that the gaps re-drive | `control/control/census.py:492-497,504-575` [DERIVED] |
| Postgres `documents.source_hash` | original-bytes hash the layer-1 dup guard matches against | `orchestrator/orchestrator/api/ui.py:577-581` [DERIVED] |
| Postgres `artifacts` | extract-stage `payload->'llm_extraction'->'stats'` feeds the coverage barrier | `control/control/census.py:416-421` [DERIVED] |
| Qdrant | child chunk vectors and neural routing representations whose receipts must converge (R1B) | `control/control/census.py:450-477` [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `allow_near_duplicate` (form) | `""` | truthy strings `("1", "true", "yes", "on")` put `config={"allow_near_duplicate": True}` in the payload — overrides near-dup layer 3 only; layers 1/2 never overridable | `orchestrator/orchestrator/api/ui.py:587-597` [DERIVED] |
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | upload byte cap in MiB -> 413 over | `orchestrator/orchestrator/api/ui.py:555` [DERIVED] |
| `POLYMATH_CENSUS_MODE` | `"auto"` | `auto` -> incremental iff a watermark exists, else full | `control/control/census.py:158-167` [DERIVED] |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces the authoritative full sweep | `control/control/census.py:159-160` [DERIVED] |
| `auto_map_parents_on_chunks` | not stated in SOURCE | flag-gated scheduler phase mints `doc_parent_map` tickets (never chain advancement) | `control/control/tickets.py:72-76` [DERIVED] |

## failure modes

1. 403 `CORPUS_NOT_ALLOWED` -> principal lacks an explicit write grant for the corpus -> `orchestrator/orchestrator/web_scope.py:98-105` [DERIVED]
2. 409 `duplicate_document` -> uploaded raw sha256 already equals `documents.source_hash` in the corpus -> `orchestrator/orchestrator/api/ui.py:569-586` [DERIVED]
3. 422/413/422 -> extension outside `_UPLOAD_EXTENSIONS`, bytes over cap, or `ref["bytes"] == 0` -> `orchestrator/orchestrator/api/ui.py:551-568` [DERIVED]
4. Silent replay no-op -> same canonical payload hashes to the same run_id -> `already_exists: True`, no new run or event -> `shared/polymath_shared/intake_submission.py:75-81` [DERIVED]
5. Run pinned at `reconciling` forever -> summary stages complete tickets without writing `stage_attempts`, so a cached non-promote verdict replayed forever (cysa-study-v1, 13:48->14:01 until a forced full pass); guards: dirty signal tracks `stage_tickets.updated_at` and gap verdicts are never cached -> `control/control/census.py:60-90,343-348` [DERIVED]
6. Sibling promotes while this run sits at `reconciling` -> uncached active run whose ticket close fell under the lookback after the global watermark advanced (Netnography, ~5 s skew); guard: an ACTIVE run with no cached verdict is dirty by definition -> `control/control/census.py:207-217` [DERIVED]
7. Corpus barrier-blocked with full model re-execution -> chain minted stages `pending` despite latest attempt `ok`; fix: such stages are born `done` -> `control/control/tickets.py:99-104` [DERIVED]
8. Summary stages never ready, corpus cannot promote -> verifier writes `{qdrant, routing_qdrant, neo4j, canonical}` but the stale declared key `docs` failed the artifact check (VERIFY-DAG-KEYS-V2) -> `control/control/tickets.py:32-39` [DERIVED]
9. Run fails outright -> a stage's last outcome `failed` at `count_by_stage >= max_attempts` (3) -> `control/control/census.py:401-407` [DERIVED]
10. Run degraded, never query_ready -> complete chain but extract recorded dropped/unaccounted neighborhoods (EXTRACTION-COVERAGE-V1 barrier) -> `control/control/census.py:54-57,330-339` [DERIVED]
11. Tick transaction held open for minutes, worker claims queue behind it -> per-entity SELECT loop for routing receipts inside the tick; fix: one set-based anti-join -> `control/control/census.py:450-456` [DERIVED]

## invariants

- INVARIANT: the request body is transport, never pipeline state; Postgres never holds the bytes — `orchestrator/orchestrator/api/ui.py:537-540` [DERIVED]
- INVARIANT: run identity is content-addressed (`run_` + sha256 of canonicalized `{'corpus', 'intake'}`), so replaying the same intake over a corpus is a no-op at the Postgres level — `shared/polymath_shared/identity.py:59-62` [DERIVED], `shared/polymath_shared/intake_submission.py:79-81` [DERIVED]
- INVARIANT: exactly one content variant per payload (`content_b64` xor `content_ref`); a ref must carry `store`, `key`, `sha256`, `bytes` — `shared/polymath_shared/intake_submission.py:34-36,41-56` [DERIVED]
- INVARIANT: identical-bytes and identical-text guards are never overridable; only the near-duplicate layer rides the config — `orchestrator/orchestrator/api/ui.py:587-590` [DERIVED]
- INVARIANT: a write grant is explicit; the wildcard never opens a library for writing — `orchestrator/orchestrator/web_scope.py:98-99` [DERIVED]
- INVARIANT: a stage's work event exists only after the control plane verifies the predecessor's artifacts, receipts, and contract — `control/control/tickets.py:3-5` [DERIVED]
- INVARIANT: projection stages carry distinct event types so two projectors never race over one shared outbox row; canonicalize/project_canonical run before verify_projections — `control/control/census.py:21-27` [DERIVED]
- INVARIANT: a census verdict carrying gaps is never cached — `control/control/census.py:76-79,343-348` [DERIVED]
- INVARIANT: the census watermark is written in the same transaction as the tick's resulting work — `control/control/census.py:88-90,374-377` [DERIVED]
- INVARIANT: background summary/vocabulary/doc_profile stages degrade, never block QUERY_READY — `control/control/tickets.py:40-43,60-66` [DERIVED]

## VERIFY

```verify
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'duplicate_document' orchestrator/orchestrator/api/ui.py
grep -Fq 'SPOOL-CLAIM-CHECK-V1' shared/polymath_shared/intake_submission.py
grep -Fq 'ON CONFLICT (idempotency_key) DO NOTHING' shared/polymath_shared/intake_submission.py
grep -Fq 'POLYMATH_CENSUS_AUDIT' control/control/census.py
grep -Fq 'doc_parent_map' control/control/tickets.py
test "$(grep -c -F 'stage_tickets' control/control/census.py)" -ge 3
```
