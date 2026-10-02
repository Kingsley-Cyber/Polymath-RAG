# unit: control/control/scheduler.py
anchor: control/control/scheduler.py:1-569

## purpose
Materializes census gaps as idempotent `outbox_events` rows inside the same tick transaction as the census, so a crash between census and schedule re-computes the same gaps next tick (control/control/scheduler.py:1-5) [DERIVED]. Also re-opens done stage tickets whose receipts went missing, re-drives unprojected knowledge objects, auto-mints enrichment/doc-parent-map tickets, and applies census promote/degrade/fail verdicts to `runs` (control/control/scheduler.py:32-557) [DERIVED]. Consumer: the control tick, imported by `control/control/main.py` (FACTS.importers) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `schedule_gaps` | def | `(conn: Connection, census: Census) -> int` | control/control/scheduler.py:32-103 | control/control/main.py |
| `_redrive_in_flight` | def | `(conn: Connection, corpus_id: str, stage: str) -> bool` | control/control/scheduler.py:133-150 | internal |
| `_reopen_receipt_gap_tickets` | def | `(conn: Connection, census: Census) -> int` | control/control/scheduler.py:153-194 | internal |
| `redrive_unprojected_objects` | def | `(conn: Connection) -> int` | control/control/scheduler.py:209-260 | control/control/main.py |
| `auto_enrich_on_chunks` | def | `(conn: Connection) -> int` | control/control/scheduler.py:325-388 | control/control/main.py |
| `auto_map_parents_on_chunks` | def | `(conn: Connection) -> int` | control/control/scheduler.py:391-484 | control/control/main.py |
| `apply_promotions` | def | `(conn: Connection, census: Census) -> None` | control/control/scheduler.py:487-521 | control/control/main.py |
| `apply_degrades` | def | `(conn: Connection, census: Census) -> int` | control/control/scheduler.py:524-549 | control/control/main.py |
| `apply_failures` | def | `(conn: Connection, census: Census) -> None` | control/control/scheduler.py:552-557 | control/control/main.py |

`used by` is module-level from FACTS.importers; per-symbol use inside `main.py` is not in the material.

## contracts

**schedule_gaps** — control/control/scheduler.py:32-103
- in: `census.gaps` (list of `Gap` from `control.census`) control/control/scheduler.py:42-45 [DERIVED]
- pre: runs in the same transaction as the census tick control/control/scheduler.py:3-5 [DERIVED]
- out: returns `scheduled`, the summed `rowcount` of chunked INSERTs control/control/scheduler.py:87-100,103 [DERIVED]
- post: gaps of archived runs skipped (`_archived_run_ids`) control/control/scheduler.py:40-44; identity-only stages get payload `{"run_id": rid}` control/control/scheduler.py:54-58; inserts batched by `_INSERT_CHUNK = 1000` control/control/scheduler.py:78; `_reopen_receipt_gap_tickets` always invoked control/control/scheduler.py:102 [DERIVED]

**redrive_unprojected_objects** — control/control/scheduler.py:209-260
- in: `procedure_artifacts`/`concept_artifacts` joined to `documents`, minus active `qdrant` receipts control/control/scheduler.py:212-224 [DERIVED]
- pre: skips corpus if `_redrive_in_flight(conn, corpus_id, "project_qdrant")` control/control/scheduler.py:228-229, or a non-archived `project_qdrant` ticket updated within `OBJECT_REDRIVE_COOLDOWN_S` seconds control/control/scheduler.py:230-236 [DERIVED]
- post: reopens one most-recently-updated `done` `project_qdrant` ticket control/control/scheduler.py:237-244 and re-arms a `project_qdrant.v1` outbox event control/control/scheduler.py:248-254; logs `OBJECT_PROJECTION_REDRIVE` control/control/scheduler.py:256-258 [DERIVED]
- out: count of reopened tickets control/control/scheduler.py:260 [DERIVED]

**auto_enrich_on_chunks** — control/control/scheduler.py:325-388
- pre: gated on `worker.enrichment_auto` (default `True`) and `worker.enrichment_provider` != `"disabled"` control/control/scheduler.py:337-340 [DERIVED]
- in: runs with `intake` ticket `done`, status in `('intake', 'reconciling', 'degraded', 'query_ready')`, not superseded, no existing `parent_enrichment` ticket, corpus not archived control/control/scheduler.py:341-355 [DERIVED]
- post: first-mint only (`NOT EXISTS` guard, re-arm-safe) control/control/scheduler.py:332-335; plus rescue of `ready`/`failed` `parent_enrichment` tickets with no undelivered `parent_enrichment.v1` event control/control/scheduler.py:356-373 [DERIVED]
- out: count of `mint_parent_enrichment` successes; failures fail-open per run control/control/scheduler.py:374-388 [DERIVED]

**auto_map_parents_on_chunks** — control/control/scheduler.py:391-484
- pre: gated on `doc_parent_map_enabled()` control/control/scheduler.py:405-406; optional single-corpus scope and/or `r.created_at > since` boundary control/control/scheduler.py:413-417 [DERIVED]
- post: mints `doc_parent_map` for eligible runs + rescues stranded tickets (scope-only rescue) control/control/scheduler.py:418-457; also emits early `doc_profile` events for pending `doc_profile` tickets of the same scoped runs via `_emit_ticket_event` control/control/scheduler.py:458-478 [DERIVED]
- out: count of mints; both mint and emit fail-open per run control/control/scheduler.py:448-484 [DERIVED]

**apply_promotions** — control/control/scheduler.py:487-521
- in: `census.promote` run IDs control/control/scheduler.py:488 [DERIVED]
- post: `UPDATE runs SET status = 'query_ready' ... WHERE status != 'query_ready' RETURNING corpus_id` control/control/scheduler.py:489-493; per promoted row runs `control.generation_swap.swap` atomically in the same transaction control/control/scheduler.py:496-500, then optional enrichment mint behind the same gate as above, fail-open control/control/scheduler.py:501-521 [DERIVED]

**apply_degrades** — control/control/scheduler.py:524-549
- post: sets `status = 'degraded'` with `degraded_reasons` (sorted JSON) and `degraded_contract = 'extraction-coverage-v1'` in `runs.metadata` control/control/scheduler.py:530-537; only from statuses `('intake', 'reconciling', 'degraded')`; no-op when reasons unchanged (`IS DISTINCT FROM` guard) control/control/scheduler.py:538-546 [DERIVED]
- out: count of changed rows control/control/scheduler.py:548 [DERIVED]

**apply_failures** — control/control/scheduler.py:552-557
- post: `UPDATE runs SET status = 'failed'` per `census.fail` run, no status guard control/control/scheduler.py:553-557 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| PG read | `archived_corpora`, `concept_artifacts`, `documents`, `outbox_events`, `procedure_artifacts`, `projection_receipts`, `runs`, `stage_tickets` | control/control/scheduler.py:212-224, 268-275, 291-297, 313-321, 341-355, 418-430, 467-475 (FACTS.tables_read) |
| PG write | `outbox_events` (INSERT ... ON CONFLICT), `runs` (status/metadata), `stage_tickets` (reopen UPDATEs) | control/control/scheduler.py:87-100, 180-193, 237-259, 489-493, 530-547, 553-557 |
| settings flags | `worker.enrichment_auto` = `True` (default), `worker.enrichment_provider` = `"disabled"` (default) | control/control/scheduler.py:337-340, 508-511 |
| settings flags | `doc_parent_map_enabled()` / `doc_parent_map_corpus_scope()` / `doc_parent_map_since()` from `polymath_shared.document_profile.map_trigger`; flag-gated, disabled by default per docstring | control/control/scheduler.py:399-406, 396-397 |
| none | no files, network, subprocess, or Qdrant calls in SOURCE | — |

`unnest` in FACTS.tables_read is the SQL function in the batched INSERT, not a table control/control/scheduler.py:93 [INFERRED — appears only as `unnest(...)` in the INSERT SELECT].

## invariants

INVARIANT: insert batch size == `_INSERT_CHUNK` == `1000` — control/control/scheduler.py:23,78 [DERIVED]
  fails-if: unbounded multi-row statements or per-gap inserts regress SCHEDULER-BULK-V1 (51-55s/tick measured) control/control/scheduler.py:7-9
INVARIANT: idempotency key == `content_hash({"run": rid, "type": event_type, "payload": payload})`, byte-identical across writers — control/control/scheduler.py:50-52, 254 [DERIVED]
  fails-if: key drift creates duplicate outbox rows for the same gap instead of re-arming
INVARIANT: ON CONFLICT re-arm only when `delivered_at IS NOT NULL` — control/control/scheduler.py:95-96,252 [DERIVED]
  fails-if: without the WHERE guard, every gap rewrote its row every tick — `outbox_events` bloated to `206 MB` over `204` live rows, id sequence past `155M` (STALL-2026-08-27) control/control/scheduler.py:83-86
INVARIANT: archived runs (`status='superseded'` tickets or `archived_corpora` member) are never re-armed — control/control/scheduler.py:36-44, 305-322 [DERIVED]
  fails-if: measured live `44k` armed debris events occupied the claim FIFO after archival control/control/scheduler.py:36-39
INVARIANT: at most one open receipt-gap re-drive ticket per `(corpus_id, stage)` for stages `{"project_canonical.v1", "project_neo4j.v1", "project_qdrant.v1"}` — control/control/scheduler.py:117-125, 154-159, 178-179 [DERIVED]
  fails-if: per-run reopens rewrote each neo4j entity ~20x/15 min — `286k` receipt writes over `14.6k` entities (cysa-study-v1, 12 runs) control/control/scheduler.py:117-124
INVARIANT: object re-drive at most once per `OBJECT_REDRIVE_COOLDOWN_S = 600` seconds per corpus — control/control/scheduler.py:203-206, 230-236 [DERIVED]
  fails-if: an unindexable object loops without bound control/control/scheduler.py:203-205
INVARIANT: pending ticket counts as in-flight only if no `failed` predecessor stage exists (DAG order) — control/control/scheduler.py:136-150, 168-177 [DERIVED]
  fails-if: cinema duplicate upload blocked every receipt-gap re-drive for `24` days, `73` runs held at reconciling control/control/scheduler.py:168-177
INVARIANT: `_IDENTITY_ONLY` stages (`canonicalize.v1`, `profile_document.v1`, `project_canonical.v1`, `project_neo4j.v1`, `project_qdrant.v1`, `verify.v1`) schedule with zero reads using payload `{"run_id": rid}` — control/control/scheduler.py:26-29, 54-58 [DERIVED]
  fails-if: a payload lookup per gap reintroduces the per-gap query cost control/control/scheduler.py:8-11

## determinism & idempotency
determinism: NONDETERMINISTIC (db: gap/ticket/outbox state drives every branch, e.g. control/control/scheduler.py:42-45, 212-225; db clock: `now()` in UPDATEs control/control/scheduler.py:184, 239, 490, 534, 555). Idempotency keys themselves are pure `content_hash` of inputs — control/control/scheduler.py:50-52 [DERIVED].
idempotency: SAFE (unique `idempotency_key` + `ON CONFLICT DO UPDATE ... WHERE delivered_at IS NOT NULL` control/control/scheduler.py:87-100; crash between census and schedule recomputes identical gaps control/control/scheduler.py:3-5; degrades no-op on unchanged reason set control/control/scheduler.py:538-546; promotion guarded by `status != 'query_ready'` control/control/scheduler.py:490). Minor exception: `apply_failures` rewrites `updated_at` on every call control/control/scheduler.py:553-557 [INFERRED — UPDATE lacks a status guard].

## failure behaviour
Four broad `except Exception` handlers, all "handled: import, log" (FACTS.fallbacks) and fail-open — the tick continues and the caller sees a normal return value:
- `auto_enrich_on_chunks` mint: warning `AUTO_ENRICH_MINT_FAILED` — control/control/scheduler.py:383-387 [DERIVED]
- `auto_map_parents_on_chunks` mint: warning `AUTO_PMAP_MINT_FAILED` — control/control/scheduler.py:453-457 [DERIVED]
- doc-profile early emit: warning `AUTO_PROFILE_EARLY_FAILED` — control/control/scheduler.py:479-483 [DERIVED]
- `apply_promotions` enrich mint: warning `AUTO_ENRICH_MINT_FAILED`; promotion itself already committed logic path, generation swap stays atomic in-transaction — control/control/scheduler.py:496-521 [DERIVED]

Informational log code `OBJECT_PROJECTION_REDRIVE` — control/control/scheduler.py:256-258 [DERIVED]. No exceptions raised by this module are visible in SOURCE.

## dumb-code flags
- `import logging` repeated inside except blocks / loop body: control/control/scheduler.py:255, 384, 454, 481, 518 [DERIVED]
- `import json` repeated locally in `apply_degrades`, `_loads`, `_dumps`: control/control/scheduler.py:528, 561, 566 [DERIVED]
- Enrichment gate duplicated verbatim in two functions: control/control/scheduler.py:337-340 vs 508-511 [DERIVED]
- `auto_map_parents_on_chunks` "Mirrors `auto_enrich_on_chunks` exactly" — duplicated mint+rescue pattern: control/control/scheduler.py:392-394, 418-457 vs 341-388 [DERIVED]
- Log truncation literal `[:20]` on run IDs repeated 5x: control/control/scheduler.py:386, 456, 482, 520, 524 [DERIVED]
- FACTS.tables_written lists `set` — static-analysis artifact of the `set()` return at control/control/scheduler.py:322, not a real table [INFERRED — no SQL writes to any table named `set` in SOURCE]
- Incident magic numbers frozen in comments only (`206 MB`, `155M`, `44k`, `51-55s`, `286k`, `14.6k`, `24 days`): control/control/scheduler.py:7-9, 36-39, 83-86, 121-124, 168-177 [DERIVED]

## refactor notes
- Idempotency-key layout `{"run": rid, "type": event_type, "payload": payload}` is a stored contract across all armed rows; changing it orphans/duplicates history — control/control/scheduler.py:50-52, 279-280 [DERIVED]
- The `WHERE outbox_events.delivered_at IS NOT NULL` re-arm guard must not be removed — measured 206 MB bloat regression — control/control/scheduler.py:83-96 [DERIVED]
- `_redrive_in_flight` imports `DAG_ORDER` from `control.tickets`; reordering stages there changes in-flight semantics for both call sites — control/control/scheduler.py:136-137, 179, 228 [DERIVED]
- `auto_map_parents_on_chunks` imports the private `_emit_ticket_event` from `control.tickets`; renaming it breaks this module — control/control/scheduler.py:464 [DERIVED]
- Importer `control/control/main.py` must keep census + schedule in one transaction (crash-safety contract) — control/control/scheduler.py:3-5 [DERIVED]
- Lowering `OBJECT_REDRIVE_COOLDOWN_S` below projection runtime risks reopen thrash; the cooldown is the only loop bound — control/control/scheduler.py:203-206 [INFERRED — comment states it "bounds any loop"]

## VERIFY
```verify
grep -Fq '_INSERT_CHUNK = 1000' control/control/scheduler.py
grep -Fq 'OBJECT_REDRIVE_COOLDOWN_S = 600' control/control/scheduler.py
grep -Fq 'WHERE outbox_events.delivered_at IS NOT NULL' control/control/scheduler.py
grep -Fq 'AUTO_PROFILE_EARLY_FAILED' control/control/scheduler.py
test "$(grep -c -F 'AUTO_ENRICH_MINT_FAILED' control/control/scheduler.py)" -ge 2
test "$(grep -c -F 'project_qdrant.v1' control/control/scheduler.py)" -ge 4
```
