# flow: upload-to-searchable

A file uploaded on the Files screen becomes searchable: POST /upload, intake, the stage DAG (extract, canonicalize, project to Qdrant / Neo4j, summaries, document profile, parent map), readiness.

ENTRY: POST /upload -> `orchestrator/orchestrator/api/ui.py:485` `upload` (web class: write)

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Write-scope check: `require_corpus(corpus_id, write=True)` -> `can_see` -> `allowed_corpora` (principal's `writable_corpus_ids`; `None` = every library) | `orchestrator/orchestrator/api/ui.py:494` [DERIVED], `orchestrator/orchestrator/web_scope.py:85-87` [DERIVED], `web_scope.py:80-82` [DERIVED], `web_scope.py:72-77` [DERIVED] | corpus_id -> None | HTTP 403 `CORPUS_NOT_ALLOWED` (`web_scope.py:79`) |
| 2 | Extension gate: basename + lowercase ext must be in `_UPLOAD_EXTENSIONS` | `orchestrator/orchestrator/api/ui.py:501-506` [DERIVED] | filename -> ext | HTTP 422 `unsupported extension {ext!r}; accepted: ...` |
| 3 | Size gate: `POLYMATH_UPLOAD_MAX_MB` (default `"200"`) * 1024 * 1024; seek-to-end check on the multipart temp file | `orchestrator/orchestrator/api/ui.py:507` [DERIVED], `ui.py:513-516` [DERIVED] | file handle -> byte count | HTTP 413 `file exceeds {max_bytes} bytes` |
| 4 | SPOOL-CLAIM-CHECK-V1: `spool_write` in a worker thread re-streams in 1 MiB chunks, sha256 in flight; bytes never sit in memory as one buffer | `orchestrator/orchestrator/api/ui.py:509-518` [DERIVED] | file.file -> `ref` = `{store, key, sha256, bytes}` | `ref["bytes"] == 0` -> HTTP 422 `empty file` (`ui.py:519-520`) |
| 5 | DUPLICATE-DOCUMENT-GUARD-V1 layer 1 (byte-identical): raw sha256 vs `documents.source_hash` | `orchestrator/orchestrator/api/ui.py:521-533` [DERIVED] | (corpus_id, sha256) -> dup source_name or none | HTTP 409 `{"error_code": "duplicate_document", ...}` (`ui.py:534-538`) |
| 6 | NEAR-DUPLICATE-GUARD-V1 override: `allow_near_duplicate` in `("1","true","yes","on")` -> `config={"allow_near_duplicate": True}`; layers 1 and 2 are never overridable | `orchestrator/orchestrator/api/ui.py:539-549` [DERIVED] | form field -> payload config | override rides only into intake-worker layer 3 |
| 7 | Canonical payload built: exactly one of `content_b64` / `content_ref`; `content_ref` must carry `store`,`key`,`sha256`,`bytes` | `shared/polymath_shared/intake_submission.py:24-57` [DERIVED] | corpus/source/media/config + ref -> payload dict | `ValueError` on zero or two content variants, or missing ref field |
| 8 | `submit_intake`: validates base64-or-ref; `run_id(corpus_id, payload)`; idempotency probe on `runs` | `shared/polymath_shared/intake_submission.py:60-81` [DERIVED] | payload -> `{run_id, accepted, already_exists}` | existing run -> early return `already_exists: True`, no writes |
| 9 | Run identity: `run_` + `content_hash({'corpus':..., 'intake':...})` = sha256 over `canonicalize` (JSON `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8) | `shared/polymath_shared/identity.py:59-62` [DERIVED], `identity.py:28-30` [DERIVED], `identity.py:16-25` [DERIVED] | payload -> stable run_id | same file re-uploaded = same run_id, silent no-op |
| 10 | One transaction: INSERT `runs` (status `'intake'`, metadata embeds the full intake_payload) + INSERT `outbox_events` `intake.v1` with `idempotency_key` = content_hash of `{run, type, payload}`, `ON CONFLICT (idempotency_key) DO NOTHING` | `shared/polymath_shared/intake_submission.py:83-100` [DERIVED], `shared/polymath_shared/db.py:44-54` [DERIVED] | payload -> runs row + outbox event | exception -> rollback (`db.py:50-53`) |
| 11 | Response to caller: run fields plus `corpus_id`, `source_name`, `bytes`, `sha256`, `near_duplicate_override` | `orchestrator/orchestrator/api/ui.py:551-555` [DERIVED] | submit result -> JSON dict | — |
| 12 | Ticket chain minted (`ensure_run_tickets`, idempotent): intake ticket born READY and `_emit_ticket_event` fires immediately; stages whose latest attempt is `ok` are born DONE; all others PENDING | `control/control/tickets.py:93-137` [DERIVED], `tickets.py:129-131` [DERIVED], `tickets.py:99-117` [DERIVED] | run_id/corpus_id -> stage_tickets rows | replay after chain existed would force re-execution; mitigated by DONE-at-birth rule |
| 13 | Stage work proceeds along STAGE_DAG: intake -> extract (`chunked.v1`, artifact `manifest`) -> profile_document -> project_qdrant (receipt `qdrant`) -> project_neo4j (receipt `neo4j`) -> canonicalize -> project_canonical -> verify_projections; a stage is handed work only when predecessors' durable evidence exists; per-stage pending high watermark 64 pauses new intake tickets (backpressure) | `control/control/tickets.py:24-58` [DERIVED], `tickets.py:20-23` [DERIVED], `tickets.py:86` [DERIVED] | outbox events -> artifacts + receipts + stage_attempts | stage fails -> retry gap until budget, then run fails (hop 16) |
| 14 | Census tick (`compute_census`) over runs with status `('intake','reconciling','degraded')`, ordered by `created_at, run_id`; dirty set = new `stage_attempts` + `stage_tickets.updated_at` + brand-new runs + uncached active runs | `control/control/census.py:140-217` [DERIVED], `census.py:171-178` [DERIVED] | DB state -> `Census{gaps, promote, fail, degrade}` | wrong dirty signal -> stale verdict replayed forever (failure modes 3-4) |
| 15 | `chain_verdict` (CENSUS-FIRST-GAP-V1): walk stops at the first stage that is not `ok`; `failed` within `max_attempts` (default 3) -> retry gap; beyond budget -> run fails; missing -> exactly one gap, nothing after it | `control/control/census.py:386-410` [DERIVED], `census.py:140` [DERIVED] | last outcome per stage -> (gaps, complete, failed) | emitting every missing gap at once relied entirely on the ticket gate (fixed) |
| 16 | Projection receipt census for `project_qdrant` / `project_neo4j` / `project_canonical` on complete chains: want-set anti-joins — qdrant: chunk receipts + routing kinds `routing_document_summary`, `routing_section_summary`, `routing_child`, `routing_procedure`, `routing_concept`; neo4j: eligible facts + chunks; canonical: `canonical_entities`, `canonical_memberships`, `evidence` | `control/control/census.py:313-328` [DERIVED], `census.py:433-576` [DERIVED] | run_id -> missing id list | missing receipts -> gap re-arms the projector stage (`complete = False`) |
| 17 | EXTRACTION-COVERAGE-V1 barrier: latest extract artifact's `payload->'llm_extraction'->'stats'` run through `coverage_verdict` with `coverage_floor` / `drop_tolerance` | `control/control/census.py:330-339` [DERIVED], `census.py:413-430` [DERIVED] | stats -> degrade reasons | reasons -> `census.degrade[run_id]`, NOT promoted |
| 18 | verify_projections stage writes keys `{qdrant, routing_qdrant, neo4j, canonical}` (VERIFY-DAG-KEYS-V2; the stale key `docs` used to block advancement) | `control/control/tickets.py:32-39` [DERIVED] | projections -> verify artifact | wrong declared key -> ticket check fails, summaries never ready |
| 19 | Background stages run after settlement and are NON_BLOCKING: `compile_objects`, `parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`, `doc_profile` (phase A); `parent_enrichment` and `doc_parent_map` are absent from STAGE_DAG and minted by the enrichment buttons / the flag-gated `auto_map_parents_on_chunks` scheduler phase | `control/control/tickets.py:40-57` [DERIVED], `tickets.py:60-77` [DERIVED] | admitted mentions + chunk text -> summaries/vocab/profile | failure degrades summaries to DEGRADED, never blocks QUERY_READY (phase A) |
| 20 | Promotion: chain complete + no failures + no missing receipts + no coverage reasons -> `census.promote`; promotion to query_ready is a generation barrier; watermark advances over attempts, ticket time, and created_at in the same transaction as the tick's work | `control/control/census.py:330-339` [DERIVED], `census.py:364-378` [DERIVED], `control/control/tickets.py:7` [DERIVED] | Census -> promoted run | crash rolls watermark back with the tick's work (safe replay) |

## state written

| store | what | anchor |
|---|---|---|
| spool volume | streamed object via `spool_write`; ref `{store, key, sha256, bytes}`; Postgres never holds the bytes | `orchestrator/orchestrator/api/ui.py:488-492` [DERIVED], `ui.py:518` [DERIVED] |
| Postgres `runs` | row `(run_id, corpus_id, status='intake', metadata)` with `source_name` + full `intake_payload` | `shared/polymath_shared/intake_submission.py:83-92` [DERIVED] |
| Postgres `outbox_events` | `intake.v1` event keyed by content-hash idempotency key | `shared/polymath_shared/intake_submission.py:93-100` [DERIVED] |
| Postgres `documents.source_hash` | original-bytes hash recorded by intake; read here for the layer-1 duplicate guard | `orchestrator/orchestrator/api/ui.py:521-533` [DERIVED] |
| Postgres `stage_tickets` | chain rows (READY/PENDING/DONE); `updated_at` is a census dirty signal | `control/control/tickets.py:119-127` [DERIVED], `control/control/census.py:196-200` [DERIVED] |
| Postgres `stage_attempts` | per-stage outcome history, written inside stage transactions | `control/control/census.py:62-64` [DERIVED], `census.py:224-237` [DERIVED] |
| Postgres `scheduler_cursors` | census watermark `('__census__','__global__')` = started_at epoch-micros | `control/control/census.py:87-92` [DERIVED], `census.py:114-128` [DERIVED] |
| Postgres `projection_receipts` | read here for want-set anti-joins (kinds: chunk, routing_*, fact, canonical_entity, canonical_membership, evidence_chunk) | `control/control/census.py:493-497` [DERIVED], `census.py:548-560` [DERIVED] |
| Postgres `artifacts` | extract-stage stats read via `payload->'llm_extraction'->'stats'` | `control/control/census.py:416-422` [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_UPLOAD_MAX_MB` | `"200"` | upload cap in MiB; over -> 413 | `orchestrator/orchestrator/api/ui.py:507` [DERIVED] |
| `POLYMATH_CENSUS_MODE` | `"auto"` | `auto` -> incremental when a watermark exists, else full; `full` forces authoritative sweep | `control/control/census.py:158-167` [DERIVED] |
| `POLYMATH_CENSUS_AUDIT` | unset | `"1"` forces full mode | `control/control/census.py:159-160` [DERIVED] |
| `allow_near_duplicate` (form field) | `""` | truthy in `("1","true","yes","on")` -> keep-both config rides the payload to intake-worker layer 3 | `orchestrator/orchestrator/api/ui.py:542-549` [DERIVED] |
| `auto_map_parents_on_chunks` (scheduler phase) | — | flag-gated phase that mints `doc_parent_map` tickets (stage deliberately absent from STAGE_DAG) | `control/control/tickets.py:73-76` [DERIVED] |

## failure modes

1. Upload refused with 403 `CORPUS_NOT_ALLOWED` -> principal's `writable_corpus_ids` excludes the corpus -> `orchestrator/orchestrator/web_scope.py:79-87`.
2. 409 `duplicate_document` -> uploaded raw sha256 already in `documents.source_hash` for the corpus -> `orchestrator/orchestrator/api/ui.py:529-538`.
3. Run pinned at `reconciling` forever (cysa-study-v1, both runs, 13:48->14:01) -> summary stages complete tickets without `stage_attempts`, so a cached non-promote verdict replayed forever -> guards: dirtiness tracks `stage_tickets.updated_at` and gap verdicts are never cached -> `control/control/census.py:66-80`, `census.py:343-345`.
4. Active run with uncached verdict stuck when a sibling advanced the global watermark past its ticket close (Netnography, ~5 s skew) -> uncached active runs are now dirty by definition -> `control/control/census.py:207-217`.
5. Summary stages never become ready after the verifier rewrite -> stale declared key `docs` failed the artifact check -> fixed to `{qdrant, routing_qdrant, neo4j, canonical}` -> `control/control/tickets.py:32-39`.
6. One tick after intake enqueued profile/canonicalize/neo4j/verify all at once -> walk emitted a gap per missing stage, ordering rested entirely on the ticket gate -> first-gap-only walk -> `control/control/census.py:390-396`.
7. Stage failed beyond `max_attempts` (3) -> run lands in `census.fail` -> `control/control/census.py:405-407`.
8. "ok" projection stage with missing receipts (store loss cleared by VERIFY) -> promotion blocked, stage re-armed -> `control/control/census.py:313-328`.
9. Complete chain with dropped/unaccounted extraction neighborhoods -> run degraded, never query_ready -> `control/control/census.py:330-339`.
10. Tick held open for MINUTES, worker claims queued -> per-entity receipt SELECT loop inside the tick transaction -> set-based anti-join -> `control/control/census.py:452-456`.
11. Silent no-op replay: same file uploaded again -> same run_id -> `already_exists: True`, nothing new written -> `shared/polymath_shared/intake_submission.py:79-81`, `shared/polymath_shared/identity.py:59-62`.
12. Legacy run without a resolvable document -> qdrant receipt wait falls back to corpus-wide check -> `control/control/census.py:443-450`.
13. MENTION_ONLY-dependent facts parked in Postgres with no neo4j receipts -> intentional, not a projection failure; no synthetic receipts -> `control/control/census.py:579-581`.

## invariants

- INVARIANT: the request body is transport, never pipeline state; Postgres never holds the uploaded bytes — only the spool `content_ref` (`orchestrator/orchestrator/api/ui.py:488-492`).
- INVARIANT: exactly one of `content_b64` / `content_ref` per canonical payload (`shared/polymath_shared/intake_submission.py:41-43`).
- INVARIANT: run identity is content-addressed — replaying the same intake over a corpus yields the same run_id, so re-intake is a no-op at the Postgres level (`shared/polymath_shared/identity.py:59-62`).
- INVARIANT: the run row and the `intake.v1` outbox event commit in a single transaction (`shared/polymath_shared/intake_submission.py:64-65`).
- INVARIANT: a stage is handed work only after its predecessors' durable evidence exists; the intake ticket is READY at birth (`control/control/tickets.py:20-23`, `tickets.py:113-114`).
- INVARIANT: projection stages carry distinct event types so two projectors never race over one shared outbox row (`control/control/census.py:21-27`).
- INVARIANT: the chain walk stops at the first non-ok stage; nothing after it is emitted (`control/control/census.py:390-396`).
- INVARIANT: a verdict carrying gaps is never cached (`control/control/census.py:343-345`).
- INVARIANT: a complete chain with extraction-coverage failures is degraded, never promoted (`control/control/census.py:330-339`).
- INVARIANT: summary/vocabulary/`doc_profile` failures degrade summaries and never block QUERY_READY in rollout phase A (`control/control/tickets.py:40-42`, `tickets.py:60-77`).

## VERIFY

```verify
grep -Fq 'POLYMATH_UPLOAD_MAX_MB' orchestrator/orchestrator/api/ui.py
grep -Fq 'duplicate_document' orchestrator/orchestrator/api/ui.py
grep -Fq 'ON CONFLICT (idempotency_key) DO NOTHING' shared/polymath_shared/intake_submission.py
grep -Fq 'POLYMATH_CENSUS_AUDIT' control/control/census.py
grep -Fq 'routing_qdrant' control/control/tickets.py
grep -Fq 'parent_enrichment' control/control/tickets.py
test "$(grep -c -F 'query_ready' control/control/tickets.py)" -ge 1
```
