# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY: `POST /upload` → `orchestrator/orchestrator/api/ui.py:485` `upload` (write scope).

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `require_corpus(corpus_id, write=True)` checks the principal's writable corpora | orchestrator/orchestrator/api/ui.py:494, orchestrator/orchestrator/web_scope.py:85-87 | corpus_id -> allow/deny | 403 `CORPUS_NOT_ALLOWED` |
| 2 | Extension gate against `_UPLOAD_EXTENSIONS` | orchestrator/orchestrator/api/ui.py:501-506 | filename ext -> accept | 422 `unsupported extension` |
| 3 | Size cap: `POLYMATH_UPLOAD_MAX_MB` (default `"200"`) × 1024 × 1024; seek-end + `tell()` | orchestrator/orchestrator/api/ui.py:507, 513-516 | file handle -> byte count | 413 `file exceeds N bytes` |
| 4 | `spool_write` via `anyio.to_thread.run_sync` re-streams in 1 MiB chunks, sha256 in flight | orchestrator/orchestrator/api/ui.py:517-518 | file.file -> `ref` `{store, key, sha256, bytes}` | 422 `empty file` when `ref["bytes"] == 0` |
| 5 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1: raw sha256 vs `documents.source_hash` | orchestrator/orchestrator/api/ui.py:521-538 | (corpus_id, sha256) -> dup row | 409 `duplicate_document`; renaming does not bypass |
| 6 | `keep_both` parse: `("1", "true", "yes", "on")` -> payload `config={"allow_near_duplicate": True}` | orchestrator/orchestrator/api/ui.py:539-549 | form field -> config override | layers 1 and 2 are never overridable |
| 7 | `canonical_intake_payload` builds the canonical payload with `content_ref` | shared/polymath_shared/intake_submission.py:24-57 | corpus/name/media/ref -> payload dict | `ValueError` if both/neither content variant, or `content_ref` missing `store`/`key`/`sha256`/`bytes` |
| 8 | `submit_intake` in `tx()`: `run_id = run_{content_hash({corpus, intake})}`; existing row -> `already_exists` | shared/polymath_shared/intake_submission.py:75-81, shared/polymath_shared/identity.py:59-62 | payload -> run_id | silent no-op replay (by design) |
| 9 | INSERT `runs` (status `'intake'`, metadata = source_name + intake_payload) + `outbox_events` `'intake.v1'` `ON CONFLICT (idempotency_key) DO NOTHING`; `tx()` commits | shared/polymath_shared/intake_submission.py:83-101, shared/polymath_shared/db.py:44-54 | payload -> run row + outbox event | exception rolls back both together |
| 10 | Response: `{run_id, accepted, already_exists, corpus_id, source_name, bytes, sha256, near_duplicate_override}` | orchestrator/orchestrator/api/ui.py:552-555 | run outcome -> JSON | — |
| 11 | `ensure_run_tickets` mints the STAGE_DAG chain; intake ticket born `ready` and `_emit_ticket_event` fires immediately; stages with ok attempts born `done` | control/control/tickets.py:93-137 | (run_id, corpus_id) -> ticket chain | full model re-execution if legacy stages minted pending (fixed by CHAIN-CREATION-RECONCILES-HISTORY) |
| 12 | Census tick picks dirty runs: `stage_attempts.started_at` and `stage_tickets.updated_at` within lookback (1 s overlap), new runs, uncached actives | control/control/census.py:182-217 | watermark -> changed set | uncached active run skipped forever (historical, CENSUS-UNCACHED-DIRTY-V1) |
| 13 | `chain_verdict` walks STAGE_CHAIN, stops at first non-ok stage: failed < 3 attempts -> retry gap; failed ≥ 3 -> run fails; missing -> the one gap; gap re-arms the stage's STAGE_EVENTS event | control/control/census.py:386-410, 28-37 | attempts -> (gaps, complete, failed) | one bad stage masks all later gaps (CENSUS-FIRST-GAP-V1) |
| 14 | extract (`chunked.v1`, artifact key `manifest`) -> profile_document (`documents_profiled`) | control/control/tickets.py:25-27 | intake receipt -> chunks + profile | retry gap or run fail per hop 13 |
| 15 | project_qdrant: artifact `chunk_count`, receipts projection `'qdrant'` | control/control/tickets.py:28 | chunks -> vectors + receipts | missing receipts re-drive (hop 19) |
| 16 | project_neo4j: artifact `facts`, receipts projection `'neo4j'`; `fact_eligible_sql` parks MENTION_ONLY facts in Postgres | control/control/tickets.py:29, control/control/census.py:577-583 | facts/chunks -> graph nodes | ineligible facts intentionally receipt-less (not failures) |
| 17 | canonicalize (artifact `canonical_entities`) -> project_canonical (artifact `memberships`, neo4j receipts) — both before verify | control/control/tickets.py:30-31, control/control/census.py:24-27 | local entities -> canonical graph | receipt gap re-arms projector |
| 18 | verify_projections: verifier artifact keys `{qdrant, routing_qdrant, neo4j, canonical}` | control/control/tickets.py:32-39 | projections -> verify artifact | stale key `'docs'` historically blocked all advancement (VERIFY-DAG-KEYS-V2) |
| 19 | Complete chain -> receipt census per projection stage; missing active receipts re-arm that projector | control/control/census.py:313-328, 433-833 | want-sets vs `projection_receipts` | ok stage with store loss loops re-drive |
| 20 | EXTRACTION-COVERAGE-V1 barrier: `coverage_verdict` on extract stats; reasons -> `census.degrade`, else `census.promote` | control/control/census.py:330-339, 413-430 | extract stats -> promote/degrade | dropped/unaccounted neighborhoods -> degraded, never query_ready |
| 21 | Background stages after settlement: `compile_objects`, `parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`, `doc_profile` — all NON_BLOCKING | control/control/tickets.py:40-57, 63-77 | admitted mentions + chunk text -> summaries/vocabulary/profile | failure degrades summaries, never blocks promotion |
| 22 | `doc_parent_map` minted only by flag-gated `auto_map_parents_on_chunks` phase; `parent_enrichment` only by owner buttons; both absent from STAGE_DAG and non-blocking | control/control/tickets.py:67-76 | flags/buttons -> tickets | lingering ticket cannot hold promotion |
| 23 | Watermark advanced over attempt + ticket time, written in the same transaction as the tick's work | control/control/census.py:364-378 | tick results -> scheduler_cursors | crash rolls work + watermark back together (safe replay) |

## state written

| store | what | anchor |
|---|---|---|
| spool volume | content object referenced by `{store, key, sha256, bytes}`; Postgres never holds the bytes | shared/polymath_shared/intake_submission.py:36-37 |
| Postgres `runs` | run_id, corpus_id, status `'intake'`, metadata (source_name, intake_payload); execution_contract | shared/polymath_shared/intake_submission.py:83-92, control/control/tickets.py:168-171 |
| Postgres `outbox_events` | `(run_id, 'intake.v1', payload, idempotency_key)` | shared/polymath_shared/intake_submission.py:93-101 |
| Postgres `documents.source_hash` | original-bytes hash; read by the layer-1 duplicate guard | orchestrator/orchestrator/api/ui.py:529-533 |
| Postgres `stage_tickets` | full per-run ticket DAG with status | control/control/tickets.py:119-127 |
| Postgres `stage_attempts` | per-stage outcome rows; dirty signal for the census | control/control/census.py:186-200 |
| Postgres `scheduler_cursors` | census watermark: stage `'__census__'`, corpus_id `'__global__'`, last_seq = epoch-micros | control/control/census.py:356-362, 87-90 |
| Postgres `projection_receipts` | (projection, entity_kind, entity_id, active) for qdrant + neo4j kinds | control/control/census.py:493-497, 517-520 |
| Postgres `artifacts` | extract stats at `payload->'llm_extraction'->'stats'` | control/control/census.py:416-421 |
| Qdrant receipts expected | kinds `routing_document_summary`, `routing_section_summary`, `routing_child`, `routing_procedure`, `routing_concept`, plus chunk receipts | control/control/census.py:459-501 |
| Neo4j receipts expected | kinds `fact`, `chunk`, `canonical_entity`, `canonical_membership`, `evidence_chunk` | control/control/census.py:517-520, 543-560 |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | upload byte cap = value × 1024 × 1024 | orchestrator/orchestrator/api/ui.py:507 |
| `allow_near_duplicate` (form) | `""` | truthy in `1/true/yes/on` -> payload config `{"allow_near_duplicate": True}`; overrides only near-duplicate layer 3 | orchestrator/orchestrator/api/ui.py:542-549 |
| `POLYMATH_CENSUS_MODE` | `"auto"` | auto -> incremental if a watermark exists, else full; `full` forces the authoritative sweep | control/control/census.py:158-167 |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces full mode | control/control/census.py:159-160 |
| `auto_map_parents_on_chunks` | not stated in SOURCE | gates the scheduler phase that mints `doc_parent_map` tickets | control/control/tickets.py:72-76 |

## failure modes

1. 403 `CORPUS_NOT_ALLOWED` -> principal's `writable_corpus_ids` excludes the corpus -> orchestrator/orchestrator/web_scope.py:85-87, 72-77
2. 422 `unsupported extension` / `empty file` -> ext outside `_UPLOAD_EXTENSIONS`, or `ref["bytes"] == 0` -> orchestrator/orchestrator/api/ui.py:501-506, 518-520
3. 413 `file exceeds` -> upload larger than `POLYMATH_UPLOAD_MAX_MB` cap -> orchestrator/orchestrator/api/ui.py:513-516
4. 409 `duplicate_document` -> byte-identical file already in corpus (`documents.source_hash`); layers 1/2 not overridable by `allow_near_duplicate` -> orchestrator/orchestrator/api/ui.py:521-542
5. Silent no-op replay -> same canonical payload yields the same run_id; `already_exists: True`, no new work minted -> shared/polymath_shared/identity.py:59-62, shared/polymath_shared/intake_submission.py (line out of range)
6. `ValueError` on payload shape -> both/neither of `content_b64`/`content_ref`, or `content_ref` missing a field -> shared/polymath_shared/intake_submission.py:41-43, 53-56
7. Run pinned at `reconciling` with chain + tickets done -> dirty signal missed ticket-only transitions (summary stages write no `stage_attempts`); fixed by tracking `stage_tickets.updated_at` and treating uncached actives as dirty -> control/control/census.py:66-80, 207-217
8. Workers churn on unclaimable re-armed events -> cached gap verdict replayed every tick; fixed by never caching gap verdicts (ticket gate refuses non-ready tickets) -> control/control/census.py:76-80, 343-345
9. Complete chain never query_ready -> extract stage recorded dropped/unaccounted neighborhoods -> `census.degrade[run] = reasons`, run marked degraded not promoted -> control/control/census.py:53-57, 330-337
10. ok projection stage re-driven repeatedly -> missing active receipts (store loss cleared by VERIFY) -> control/control/census.py:313-328
11. Stage failed at/after `max_attempts` (default 3) -> run lands in `census.fail` -> control/control/census.py:405-407, 376-377
12. Summary tickets never advance (historical) -> `_stage_attempt_ok` permanently False for stages that write no attempts; fixed by treating a DONE ticket as completion proof -> control/control/tickets.py:149-163
13. Corpus promotion blocked after verifier rewrite (historical) -> stale declared artifact key `'docs'`; fixed to `{qdrant, routing_qdrant, neo4j, canonical}` -> control/control/tickets.py:32-39
14. MENTION_ONLY facts show no neo4j receipts -> intentional: parked in Postgres, not projection failures, no synthetic receipts -> control/control/census.py:577-583
15. Silent fallbacks on this path: cold controller falls back incremental -> full (control/control/census.py:164-167); 1 s replay overlap window on the dirty lookback (control/control/census.py:183); legacy runs without a resolvable document fall back to the corpus-wide chunk-receipt check (control/control/census.py:441-449)

## invariants

- INVARIANT: the request body is transport, never pipeline state; Postgres never holds the bytes (SPOOL-CLAIM-CHECK-V1) — orchestrator/orchestrator/api/ui.py:487-492
- INVARIANT: run identity is content-addressed (sha256 inside the payload); replaying the same intake over a corpus is a no-op at the Postgres level — shared/polymath_shared/intake_submission.py:32-39, shared/polymath_shared/identity.py:59-62
- INVARIANT: the runs row and the `intake.v1` outbox event commit in one transaction; the outbox insert is idempotent on `idempotency_key` — shared/polymath_shared/intake_submission.py:63-71, 93-101
- INVARIANT: exactly one of `content_b64` / `content_ref` per canonical payload — shared/polymath_shared/intake_submission.py:34-43
- INVARIANT: `canonicalize`/`project_canonical` run before `verify_projections` so the verifier reconciles only when due — control/control/census.py:24-27
- INVARIANT: projection stages carry distinct event types so two projectors never race over one shared outbox row — control/control/census.py:21-23
- INVARIANT: the chain walk emits only the first non-ok stage as a gap; nothing after it — control/control/census.py:390-396
- INVARIANT: a verdict carrying gaps is never cached — control/control/census.py:343-345
- INVARIANT: a complete chain with dropped/unaccounted extraction neighborhoods is never query_ready — control/control/census.py:330-337
- INVARIANT: promotion waits for the run's own documents' chunk receipts, not every document of the corpus — control/control/census.py:441-449
- INVARIANT: incomplete NON_BLOCKING_STAGES never block promotion (knowledge=READY while summaries=DEGRADED) — control/control/tickets.py:60-77
- INVARIANT: `tx()` commits on clean exit and rolls back on any exception; the census watermark rides the same transaction as the tick's work — shared/polymath_shared/db.py:44-54, control/control/census.py:374-378

## VERIFY

```verify
grep -Fq 'SPOOL-CLAIM-CHECK-V1' orchestrator/orchestrator/api/ui.py
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'intake.v1' shared/polymath_shared/intake_submission.py
grep -Eq 'STAGE_CHAIN = \["intake", "extract"' control/control/census.py
grep -Fq 'verify_projections' control/control/census.py
test "$(grep -c -F 'NON_BLOCKING_STAGES' control/control/tickets.py)" -ge 2
! grep -Fq 'POLYMATH_UPLOAD_MAX_GB' orchestrator/orchestrator/api/ui.py
```
