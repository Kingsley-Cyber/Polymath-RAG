# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY POST /upload -> `orchestrator/orchestrator/api/ui.py:534` `upload` (web class: write)

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | POST /upload enters `upload(corpus_id: Form, file: UploadFile, allow_near_duplicate: Form default "")` | ui.py:534-536 [DERIVED] | multipart form -> response dict | — |
| 2 | Write check `require_corpus(corpus_id, write=True)` (FRIENDS-ACCESS-V1 D5); a write grant must name the corpus; the wildcard never grants write | web_scope.py:103-105, 94-100 [DERIVED] | corpus_id + principal grant -> pass | 403 `CORPUS_NOT_ALLOWED` |
| 3 | Extension gate: basename ext must be in `_UPLOAD_EXTENSIONS` | ui.py:550-555 [DERIVED] | filename -> ext | 422, message lists `sorted(_UPLOAD_EXTENSIONS)` |
| 4 | Size gate: `POLYMATH_UPLOAD_MAX_MB` default "200" x 1024 x 1024; seek-end + tell check | ui.py:556, 563-565 [DERIVED] | file.file -> byte count | 413 "file exceeds N bytes" |
| 5 | `spool_write` via `anyio.to_thread.run_sync` re-streams the Starlette disk-spooled temp file in 1 MiB chunks, sha256 computed in flight; bytes never sit in process memory as one buffer | ui.py:537-542, 558-567 [DERIVED] | file.file -> content_ref `{store, key, sha256, bytes}` | 422 "empty file" when `ref["bytes"] == 0` (ui.py:568-569) |
| 6 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1 (byte-identical): `documents.source_hash` match inside the corpus | ui.py:570-587 [DERIVED] | (corpus_id, sha256) -> existing source_name | 409 `duplicate_document` |
| 7 | Parse `allow_near_duplicate` in ("1","true","yes","on") -> keep_both; the override rides in the payload config; layers 1 and 2 are never overridable | ui.py:589-598 [DERIVED] | form string -> config | — |
| 8 | `canonical_intake_payload` with content_ref (must hold `store`, `key`, `sha256`, `bytes`); exactly one of content_b64 / content_ref | intake_submission.py:24-57 [DERIVED] | fields -> canonical payload dict | `ValueError` on both/neither or a missing content_ref field |
| 9 | Run identity: `run_` + sha256 over canonical JSON `{corpus, intake}` (sort_keys, compact separators, UTF-8) | identity.py:59-62, 16-30 [DERIVED] | payload -> run_id | — |
| 10 | `submit_intake` idempotency: existing run_id -> `{"run_id": rid, "accepted": True, "already_exists": True}`, nothing written | intake_submission.py:75-81 [DERIVED] | run_id -> early return | silent no-op replay (by design) |
| 11 | One `tx()` transaction: INSERT `runs` (status `'intake'`, metadata = source_name + intake_payload) and INSERT `outbox_events` (`'intake.v1'`, idempotency_key = content hash) ON CONFLICT DO NOTHING; commit on clean exit, rollback on exception | intake_submission.py:83-100; db.py:44-54 [DERIVED] | payload -> runs row + outbox row | exception rolls the whole transaction back |
| 12 | Response: `{**out, corpus_id, source_name, bytes, sha256, near_duplicate_override}` | ui.py:600-604 [DERIVED] | — | — |
| 13 | `ensure_run_tickets` mints the chain: intake ticket READY (work event emitted at birth), others PENDING; a stage whose latest attempt is ok is born DONE (CHAIN-CREATION-RECONCILES-HISTORY) | tickets.py:93-131 [DERIVED] | run_id -> stage_tickets rows | — |
| 14 | Backpressure: per-stage pending high watermarks (`DEFAULT_HIGH_WATERMARK = 64`) pause new intake tickets | tickets.py:5-7, 86 [DERIVED] | ticket counts -> intake pause | new uploads stall (by design) |
| 15 | Census tick: select non-terminal runs `status IN ('intake','reconciling','degraded')`, ordered by created_at then run_id | census.py:170-179 [DERIVED] | runs -> active set | — |
| 16 | Incremental dirty select: `stage_attempts.started_at` + `stage_tickets.updated_at` + new runs + uncached active runs, inside watermark + 1 s replay window (scheduler_cursors `'__census__'`/`'__global__'`) | census.py:182-217, 87-92 [DERIVED] | watermark -> changed set | cold controller without a watermark falls back to full (census.py:162-167) |
| 17 | `chain_verdict` first-gap walk: the first non-ok stage is the only gap; failed within `max_attempts` (default 3) -> retry gap; failed beyond -> run fails; missing -> one gap, nothing after it | census.py:386-410 [DERIVED] | attempts -> (gaps, complete, failed) | run pinned behind one stage |
| 18 | Gaps become re-drive events via STAGE_EVENTS (own event type per stage: `chunked.v1`, `profile_document.v1`, `project_qdrant.v1`, ...), so two projectors never race over one shared outbox row | census.py:304-309, 22-37 [DERIVED] | Gap -> scheduler re-arm | — |
| 19 | Ticket DAG advancement per STAGE_DAG: extract needs `"manifest"`; profile_document `"documents_profiled"`; project_qdrant `"chunk_count"` + `"qdrant"` receipts; project_neo4j `"facts"` + `"neo4j"`; canonicalize `"canonical_entities"`; project_canonical `"memberships"` + `"neo4j"`; verify_projections `"qdrant"`, `"routing_qdrant"`, `"neo4j"`, `"canonical"` | tickets.py:24-39 [DERIVED] | artifacts + receipts -> next ticket ready | stale artifact key blocks advancement (VERIFY-DAG-KEYS-V2, tickets.py:32-38) |
| 20 | Receipt census on a complete chain: qdrant — run-scoped chunk receipts (RUN-SCOPED-RECEIPTS-V1) + routing wants (`routing_document_summary`, `routing_section_summary`, `routing_child` on chunks tier `'child'`, `routing_procedure`, `routing_concept`) in one set-based anti-join; neo4j — eligible facts (`fact_eligible_sql`) + chunks; canonical — `canonical_entity`, `canonical_membership`, `evidence_chunk`; missing receipts re-arm the projector | census.py:313-328, 433-576 [DERIVED] | receipts vs want-set -> missing list | ok stage re-driven on store loss cleared by VERIFY (by design) |
| 21 | Promotion barrier: complete chain -> extract stats (artifacts payload `llm_extraction.stats`) through `coverage_verdict`; reasons -> `census.degrade`, else `census.promote` | census.py:330-339, 413-430 [DERIVED] | stats -> promote or degrade | dropped/unaccounted neighborhoods keep the run degraded |
| 22 | Background stages after settlement: `compile_objects`, `parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`, `doc_profile` are NON_BLOCKING; failure degrades summaries, never blocks QUERY_READY; doc_profile phase B moves it ahead of verify_projections ("ingested != query_ready") | tickets.py:40-66 [DERIVED] | — | summaries DEGRADED only |
| 23 | Off-DAG stages: `parent_enrichment` is owner-triggered (enrichment buttons); `doc_parent_map` is minted by the flag-gated `auto_map_parents_on_chunks` scheduler phase; both non-blocking | tickets.py:67-76 [DERIVED] | — | a lingering ticket cannot hold promotion |
| 24 | Verdict cache + watermark: a verdict carrying gaps is never cached; the watermark advances over attempt time and ticket time, written in the same transaction as the tick's work | census.py:343-348, 363-378 [DERIVED] | — | crash rolls the watermark back with the work (safe replay) |
| 25 | Promotion to query_ready is a generation barrier | tickets.py:6-7 [DERIVED] | — | — |

## state written

| store | what | anchor |
|---|---|---|
| spool volume blob | content_ref `{store, key, sha256, bytes}` written by `spool_write` | ui.py:537-542, 567 [DERIVED]; intake_submission.py:53-56 [DERIVED] |
| Postgres `runs` | run_id, corpus_id, status `'intake'`, metadata `{source_name, intake_payload}` | intake_submission.py:83-92 [DERIVED] |
| Postgres `outbox_events` | run_id, `'intake.v1'`, payload, idempotency_key = content hash, ON CONFLICT DO NOTHING | intake_submission.py:93-100 [DERIVED] |
| Postgres `documents` | read here for the dup guard (`corpus_id`, `source_hash`); `source_hash` is the original-bytes hash intake records; layer 2 (identical text) lives in the intake worker | ui.py:570-582 [DERIVED] |
| Postgres `stage_tickets` | ticket_id (`tkt_` + content hash prefix), run_id, corpus_id, stage, event_type, status | tickets.py:89-90, 119-127 [DERIVED] |
| Postgres `stage_attempts` | run_id, stage, outcome, started_at; written inside stage transactions; the census dirty signal and chain walk read it | census.py:63-65, 186-199, 225-229 [DERIVED] |
| Postgres `scheduler_cursors` | census watermark: stage `'__census__'`, corpus_id `'__global__'`, last_seq = epoch-micros | census.py:87-92, 114-128 [DERIVED] |
| Postgres `artifacts` | extract-stage payload `llm_extraction.stats` read for the coverage barrier | census.py:413-423 [DERIVED] |
| Postgres `projection_receipts` | projection `'qdrant'` / `'neo4j'`, entity_kind, entity_id, active | census.py:493-497, 516-534, 544-560 [DERIVED] |
| Postgres `retrieval_summaries` | kinds `'document_retrieval_summary'`, `'section_retrieval_summary'`, active flag | census.py:459-471 [DERIVED] |
| Postgres `chunks` (tier `'child'`), `facts`, `evidence`, `canonical_entities`, `canonical_memberships`, `procedure_artifacts`, `concept_artifacts`, `corpora` | want-set sources for receipt convergence | census.py:472-490, 509-575, 173-175 [DERIVED] |
| Qdrant / Neo4j stores | not written on the path shown in SOURCE; convergence is proven only via `projection_receipts` (routing representations are production dependencies, R1B) | census.py:450-452 [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | upload cap in MiB; over -> 413 | ui.py:556 [DERIVED] |
| `allow_near_duplicate` (form field) | `""` | `"1"`/`"true"`/`"yes"`/`"on"` -> config `{"allow_near_duplicate": True}` in the canonical payload; layer 3 override only | ui.py:592-598 [DERIVED] |
| `POLYMATH_CENSUS_MODE` | `"auto"` | `"full"` forces a full sweep; auto -> incremental when a watermark exists, else full; incremental without a watermark -> full | census.py:158-167 [DERIVED] |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces mode = full | census.py:158-159 [DERIVED] |
| `max_attempts` (compute_census kwarg) | `3` | failed-stage retry budget before the run fails | census.py:140, 401-407 [DERIVED] |
| `coverage_floor` (compute_census kwarg) | `0.0` | extraction coverage floor for the promote/degrade verdict | census.py:141, 330-339 [DERIVED] |
| `drop_tolerance` (compute_census kwarg) | `None` | forwarded to `coverage_verdict` | census.py:142, 426-430 [DERIVED] |
| `auto_map_parents_on_chunks` | not stated in SOURCE | flag-gated scheduler phase that auto-mints `doc_parent_map` tickets | tickets.py:72-76 [DERIVED] |

## failure modes

1. 403 `CORPUS_NOT_ALLOWED` for writing -> principal grant lacks an explicit write entry; the wildcard never opens a library for writing -> web_scope.py:98-105.
2. 422 unsupported extension -> ext not in `_UPLOAD_EXTENSIONS` -> ui.py:552-555.
3. 413 file exceeds N bytes -> size over `POLYMATH_UPLOAD_MAX_MB` x 1024 x 1024 -> ui.py:556-565.
4. 422 empty file -> spool ref `bytes == 0` -> ui.py:568-569.
5. 409 `duplicate_document` -> the same raw sha256 is already in `documents.source_hash` for the corpus -> ui.py:578-587.
6. Upload accepted, nothing new happens -> the identical canonical payload already has a run: `already_exists: True`, no writes -> intake_submission.py:75-81; identity.py:59-62 (silent by design).
7. Run sits at `'reconciling'`, chain done -> extract recorded dropped/unaccounted neighborhoods; promotion withheld, degrade reasons recorded -> census.py:54-57, 330-339.
8. A projection stage keeps re-running -> an ok stage with missing receipts is re-armed (store loss cleared by VERIFY) -> census.py:313-328.
9. Run fails outright -> stage outcome `'failed'` at count >= `max_attempts` (default 3) -> census.py:401-407.
10. New uploads stall -> per-stage pending tickets reach the high watermark (64), intake tickets pause -> tickets.py:5-7, 86.
11. MENTION_ONLY facts look unprojected -> they are intentionally parked in Postgres; receipt expectations obey `fact_eligible_sql`; no synthetic receipts -> census.py:577-582.
12. Run pinned at `'reconciling'` forever (historical) -> summary stages close tickets without writing stage_attempts; a cached non-promote verdict replayed forever -> guards: ticket-time dirtiness, uncached actives dirty, gap verdicts never cached -> census.py:66-80, 207-217, 343-348.
13. Every downstream stage enqueued at once after intake (historical) -> the walk emitted a gap per missing stage; now first-gap only (CENSUS-FIRST-GAP-V1) -> census.py:390-396.
14. Corpus could not promote; summary tickets never ready (historical) -> the verifier writes `{qdrant, routing_qdrant, neo4j, canonical}` but the ticket declared the stale key `'docs'` (VERIFY-DAG-KEYS-V2) -> tickets.py:32-38.
15. One document promoted ~17 min behind its sibling (historical) -> promotion waited on corpus-wide chunk receipts; now run-scoped (RUN-SCOPED-RECEIPTS-V1) -> census.py:441-449.
16. Tick transaction held open for minutes, worker claims queue behind it (historical) -> per-entity SELECT loop for routing receipts; now one set-based anti-join -> census.py:453-456.

## invariants

- INVARIANT: the request body is transport, never pipeline state; Postgres never holds the bytes — ui.py:537-542 [DERIVED]
- INVARIANT: a canonical payload carries exactly one content variant — `content_b64` or `content_ref` — intake_submission.py:41-43 [DERIVED]
- INVARIANT: run identity is content-addressed; replaying the same intake over a corpus yields the same run id — identity.py:59-62 [DERIVED]
- INVARIANT: duplicate-guard layers 1 (identical bytes) and 2 (identical text) are never overridable — ui.py:589-592 [DERIVED]
- INVARIANT: a write grant is explicit; the wildcard never opens a library for writing — web_scope.py:98-99 [DERIVED]
- INVARIANT: two ticks over the same state produce the same schedule (explicit sort orders) — census.py:144-148 [DERIVED]
- INVARIANT: a verdict carrying gaps is never cached — census.py:343-348 [DERIVED]
- INVARIANT: the census watermark is written in the same transaction as the tick's work; a crash rolls both back — census.py:373-378 [DERIVED]
- INVARIANT: a stage's work event exists only after the control plane verifies the predecessor's artifacts, receipts and contract — tickets.py:1-7 [DERIVED]
- INVARIANT: background stage failure degrades summaries to DEGRADED, never blocks QUERY_READY (knowledge=READY while summaries=DEGRADED) — tickets.py:40-43, 60-66 [DERIVED]
- INVARIANT: a complete chain whose extract stage dropped or lost track of neighborhoods is never query_ready — census.py:330-336 [DERIVED]
- INVARIANT: each projection stage has its own event type; two projectors never race over one shared outbox row — census.py:22-27 [DERIVED]
- INVARIANT: promotion to query_ready is a generation barrier — tickets.py:6-7 [DERIVED]

## VERIFY

```verify
grep -Fq 'SPOOL-CLAIM-CHECK-V1' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'duplicate_document' orchestrator/orchestrator/api/ui.py
grep -Fq 'already_exists' shared/polymath_shared/intake_submission.py
grep -Fq 'intake.v1' shared/polymath_shared/intake_submission.py
test "$(grep -c -F 'STAGE_EVENTS' control/control/census.py)" -ge 2
grep -Fq 'NON_BLOCKING_STAGES' control/control/tickets.py
grep -Fq 'DEFAULT_HIGH_WATERMARK' control/control/tickets.py
```
