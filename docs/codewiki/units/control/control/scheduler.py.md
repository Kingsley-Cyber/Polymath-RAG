# unit: control/control/scheduler.py
anchor: control/control/scheduler.py:1-497

## purpose
Materializes `control.census` decisions into Postgres: turns census gaps into idempotent outbox events, re-opens receipt-gap stage tickets, auto-mints `parent_enrichment` / `doc_parent_map` tickets once intake is done, and applies promote/degrade/fail run-status transitions. Module docstring: "Outbox scheduling: materialize census gaps as outbox events." — control/control/scheduler.py:1-15 [DERIVED]. Imported by `control/control/main.py` (FACTS.importers) — control/control/scheduler.py [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `schedule_gaps` | def | `(conn: Connection, census: Census) -> int` | control/control/scheduler.py:32-103 | — (module imported by control/control/main.py) |
| `auto_enrich_on_chunks` | def | `(conn: Connection) -> int` | control/control/scheduler.py:254-317 | — |
| `auto_map_parents_on_chunks` | def | `(conn: Connection) -> int` | control/control/scheduler.py:320-413 | — |
| `apply_promotions` | def | `(conn: Connection, census: Census) -> None` | control/control/scheduler.py:416-450 | — |
| `apply_degrades` | def | `(conn: Connection, census: Census) -> int` | control/control/scheduler.py:453-478 | — |
| `apply_failures` | def | `(conn: Connection, census: Census) -> None` | control/control/scheduler.py:481-486 | — |

Private helpers: `_reopen_receipt_gap_tickets` (133-189), `_bulk_first_outbox_payload` (192-212), `_bulk_intake_metadata` (215-231), `_archived_run_ids` (234-251), `_loads` (489-491), `_dumps` (494-497). Per-symbol callers not in FACTS; only the module-level import by `control/control/main.py` is known.

## contracts

**`schedule_gaps(conn, census) -> int`**
- in: `conn` psycopg `Connection` (18), `census` a `control.census.Census` whose `.gaps` hold `Gap` with `run_id`, `event_type`, `corpus_id`, `reason` — control/control/scheduler.py:40-45,135-139 [DERIVED]
- pre: gaps for runs in `_archived_run_ids` (superseded tickets or `archived_corpora` membership) are skipped before any write — control/control/scheduler.py:41-44,234-251 [DERIVED]
- post: every non-archived gap of event type in `_IDENTITY_ONLY`, `"chunked.v1"`, or `"intake.v1"` has an `outbox_events` row keyed by `content_hash({"run": rid, "type": event_type, "payload": payload})`; conflicting rows only get `delivered_at = NULL` when previously delivered — control/control/scheduler.py:50-76,87-100 [DERIVED]
- out: `int` = summed `rowcount` of the chunked INSERTs (inserts + re-arms) — control/control/scheduler.py:87,100,102 [DERIVED]

**`apply_promotions(conn, census) -> None`**
- in: `census.promote` run_ids — control/control/scheduler.py:416-417 [DERIVED]
- post: run set to `status = 'query_ready'` only when `status != 'query_ready'`; on success, `control.generation_swap.swap` runs in the same transaction — control/control/scheduler.py:418-429 [DERIVED]
- post: promotion-time enrichment mint attempted when `enrichment_auto` truthy and `enrichment_provider != "disabled"`; mint failure swallowed — control/control/scheduler.py:435-450 [DERIVED]

**`apply_degrades(conn, census) -> int`**
- in: `census.degrade` mapping run_id -> reasons — control/control/scheduler.py:459 [DERIVED]
- post: run set `status = 'degraded'` with `metadata.degraded_reasons = json.dumps(sorted(reasons))` and `metadata.degraded_contract = 'extraction-coverage-v1'`; only from statuses `('intake','reconciling','degraded')` — control/control/scheduler.py:460-468 [DERIVED]
- post: no-op when already `'degraded'` with identical `degraded_reasons` (`IS DISTINCT FROM` guard, DEGRADE-IDEMPOTENCY-FIX 2026-09-02) — control/control/scheduler.py:469-475 [DERIVED]
- out: `int` changed row count — control/control/scheduler.py:477 [DERIVED]

**`apply_failures(conn, census) -> None`** — sets `status = 'failed'` per `census.fail` run_id, unconditional — control/control/scheduler.py:481-486 [DERIVED]

**`auto_enrich_on_chunks(conn) -> int`** — returns 0 when `enrichment_auto` falsy or `enrichment_provider == "disabled"`; else mints `parent_enrichment` for intake-done runs (NOT EXISTS ticket guard) plus stranded ready/failed tickets with no undelivered `parent_enrichment.v1` event; returns mint count — control/control/scheduler.py:265-317 [DERIVED]

**`auto_map_parents_on_chunks(conn) -> int`** — returns 0 when `doc_parent_map_enabled()` false; else mints `doc_parent_map` under optional corpus scope + `created_at > since` filters, rescues stranded tickets, and early-emits `doc_profile` ticket events for pending `doc_profile` tickets; returns mint count (early emits not counted) — control/control/scheduler.py:320-413 [DERIVED]

## effect surface
| kind | target | anchor |
|---|---|---|
| PG read | `runs` | control/control/scheduler.py:221-226,272-284,348-359,395-404 |
| PG read | `stage_tickets` | control/control/scheduler.py:161-172,242-248,272-284,294-302,351-358,368-376,397-402 |
| PG read | `outbox_events` | control/control/scheduler.py:198-204,298-302,372-376 |
| PG read | `archived_corpora` | control/control/scheduler.py:246-248,282-283,357-358,479-480 |
| PG write | `outbox_events` (chunked INSERT via `unnest`) | control/control/scheduler.py:87-100 |
| PG write | `stage_tickets` (reopen `done` -> `ready`) | control/control/scheduler.py:175-188 |
| PG write | `runs` (promote/degrade/fail) | control/control/scheduler.py:418-420,461-476,483-486 |
| settings flag | `worker.enrichment_auto` = `True` (getattr default), `worker.enrichment_provider` = `"disabled"` (getattr default) | control/control/scheduler.py:267-268,438-439 |
| settings flag | `doc_parent_map_enabled()` / `doc_parent_map_corpus_scope()` / `doc_parent_map_since()` (defaults live in `polymath_shared.document_profile.map_trigger`, not here) | control/control/scheduler.py:328-337 |
| side effect | mints via imported `mint_parent_enrichment` and `mint_doc_parent_map` (their tables not visible here) | control/control/scheduler.py:309-310,380,444-445 |

No file, network, or subprocess access visible in this unit.

## invariants
INVARIANT: `_INSERT_CHUNK` == `1000` rows per INSERT statement — control/control/scheduler.py:23 [DERIVED]
  fails-if: bigger arrays per `unnest` bind / smaller means more round trips per tick.
INVARIANT: idempotency_key == `content_hash({"run": rid, "type": event_type, "payload": payload})` — control/control/scheduler.py:50-52 [DERIVED]
  fails-if: key drift orphans existing `outbox_events` rows (never re-armed) and duplicates get inserted.
INVARIANT: payload for every `_IDENTITY_ONLY` type == `{"run_id": rid}` — control/control/scheduler.py:26-29,54-58 [DERIVED]
  fails-if: any payload change alters the content hash -> duplicate events for the same gap.
INVARIANT: ON CONFLICT re-arm fires only `WHERE outbox_events.delivered_at IS NOT NULL` — control/control/scheduler.py:95-96 [DERIVED]
  fails-if: every gap rewrites its row every tick — measured 206 MB table over 204 live rows, id sequence past 155M (STALL-2026-08-27) — control/control/scheduler.py:83-86.
INVARIANT: reopened tickets per `(corpus_id, stage)` per tick <= 1 (subquery `ORDER BY run_id LIMIT 1`) — control/control/scheduler.py:180-185 [DERIVED]
  fails-if: N runs re-drive the identical corpus-wide projection — measured cysa-study-v1, ~20x entity rewrites, 286k receipt writes — control/control/scheduler.py:117-125.
INVARIANT: a `'pending'` ticket counts as in-flight only when no unarchived `'failed'` ticket exists at an earlier `DAG_ORDER` stage for the same run — control/control/scheduler.py:159-170 [DERIVED]
  fails-if: dead chain reads as in-flight and blocks every receipt-gap re-drive — measured cinema, 73 runs held at reconciling 24 days — control/control/scheduler.py:149-158.
INVARIANT: degrade fires only when `status <> 'degraded'` OR `metadata->'degraded_reasons' IS DISTINCT FROM` the sorted-reasons JSON — control/control/scheduler.py:474-475 [DERIVED]
  fails-if: runs reset to `reconciling` with stale reasons never re-marked degraded (the 2026-09-02 bug) — control/control/scheduler.py:469-473.
INVARIANT: `degraded_reasons` stored as `json.dumps(sorted(reasons))` — control/control/scheduler.py:460,475 [DERIVED]
  fails-if: unsorted reasons break the DISTINCT FROM no-op comparison, causing a write every tick.

## determinism & idempotency
determinism: NONDETERMINISTIC (db: results depend on live `outbox_events`/`runs`/`stage_tickets`/`archived_corpora` state — control/control/scheduler.py:41,60-70,270-302; SQL `now()` timestamps on writes — control/control/scheduler.py:179,419,463,484). No Python clock/random/uuid/network use.
idempotency: SAFE (content-hash keys + guarded `ON CONFLICT ... WHERE delivered_at IS NOT NULL` — control/control/scheduler.py:50-52,95-96; degrade guarded — control/control/scheduler.py:474-475; promotion guarded by `status != 'query_ready'` — control/control/scheduler.py:419; mint sweeps guarded by `NOT EXISTS` ticket checks — control/control/scheduler.py:279-283,355-358).

## failure behaviour
All 4 handlers are `except Exception` (FACTS.fallbacks), fail-open, log a warning to logger `"control-schedule"`, and never re-raise:

| site | swallows | logged error_code | caller sees | anchor |
|---|---|---|---|---|
| enrich mint, per run | any mint error | `AUTO_ENRICH_MINT_FAILED` | lower `minted` count, tick continues | control/control/scheduler.py:312-316 |
| pMAP mint, per run | any mint error | `AUTO_PMAP_MINT_FAILED` | lower `minted` count | control/control/scheduler.py:382-386 |
| doc_profile early emit, per run | any emit error | `AUTO_PROFILE_EARLY_FAILED` | chain advancement remains backstop | control/control/scheduler.py:408-412 |
| promotion-time enrich mint | any mint error | `AUTO_ENRICH_MINT_FAILED` | promotion still commits | control/control/scheduler.py:446-450 |

No error codes are raised by this module; SQL/psycopg errors outside those handlers propagate to the caller's `conn` transaction.

## dumb-code flags
- `getattr(w, "enrichment_auto", True)` / `getattr(w, "enrichment_provider", "disabled")` default pair duplicated verbatim in two functions — control/control/scheduler.py:267-268,438-439.
- Stage/event string pairs repeated with no shared constant: `'parent_enrichment'` vs `'parent_enrichment.v1'` (279-281,297,300) and `'doc_parent_map'` vs `'doc_parent_map.v1'` (356,370,374).
- `_IDENTITY_ONLY` (26-29) and `_RECEIPT_GAP_STAGES` keys (126-130) both enumerate the three `project_*` types; consistency is manual.
- Event-type dispatch in `schedule_gaps` is `if _IDENTITY_ONLY / elif "chunked.v1" / elif "intake.v1"` with no else — a new payload-bearing event type yields zero rows silently — control/control/scheduler.py:47-77.
- `run_id[:20]` truncation magic number in all 4 log lines — control/control/scheduler.py:315,385,411,449.
- `logging.getLogger("control-schedule")` plus local `import logging` rebuilt inside every handler — control/control/scheduler.py:313-314,383-384,409-410,447-448.
- `key()` closure re-defined on every iteration of the `by_type` loop — control/control/scheduler.py:50-52.
- `_loads`/`_dumps` are bare `json.loads`/`json.dumps` wrappers — control/control/scheduler.py:489-497.
- `scheduled` counts inserts and re-arms identically (`rowcount` of the guarded upsert) — control/control/scheduler.py:87-100.
- FACTS.tables_written lists `"set"`; no such table appears in SOURCE — it is the SQL keyword / type-annotation artifact of the analyzer — control/control/scheduler.py:175-179 [INFERRED].

## refactor notes
- `control/control/main.py` imports this module (FACTS.importers); signature changes to any public function ripple there — control/control/scheduler.py [DERIVED].
- Idempotency keys must stay byte-identical (docstring: "Idempotency keys are byte-identical to the per-gap loop"); changing `key()` inputs, payload shape, or `_dumps` serialization orphans existing outbox rows — control/control/scheduler.py:50-52,245-246.
- Do not drop the `WHERE outbox_events.delivered_at IS NOT NULL` guard on the upsert; measured 206 MB bloat / sequence past 155M without it — control/control/scheduler.py:83-96.
- `_RECEIPT_GAP_STAGES` values must remain members of `control.tickets.DAG_ORDER` (`DAG_ORDER.index(stage)` raises `ValueError` otherwise) — control/control/scheduler.py:126-130,159.
- `control.tickets._emit_ticket_event` is imported private; renaming it in `control.tickets` breaks the doc_profile early emit — control/control/scheduler.py:393,407.
- `schedule_gaps`/`_reopen_receipt_gap_tickets` read `Gap` fields `run_id`, `event_type`, `corpus_id`, `reason` and match the literal substring `"receipts missing"` in `reason` — census reason-text change silently stops ticket reopens — control/control/scheduler.py:40-45,135-139.
- `auto_map_parents_on_chunks` mirrors `auto_enrich_on_chunks` "exactly" per its docstring; behavior-changing edits to one should be checked against the other — control/control/scheduler.py:320-327.

## VERIFY
```verify
grep -Fq '_INSERT_CHUNK = 1000' control/control/scheduler.py
grep -Fq 'ON CONFLICT (idempotency_key) DO UPDATE SET delivered_at = NULL' control/control/scheduler.py
grep -Fq 'WHERE outbox_events.delivered_at IS NOT NULL' control/control/scheduler.py
grep -Fq 'receipts missing' control/control/scheduler.py
grep -Eq 'def (schedule_gaps|apply_promotions|apply_degrades|apply_failures|auto_enrich_on_chunks|auto_map_parents_on_chunks)\(conn: Connection' control/control/scheduler.py
test "$(grep -c -F 'AUTO_ENRICH_MINT_FAILED' control/control/scheduler.py)" -ge 2
! grep -Fq 'VALUES' control/control/scheduler.py
```
