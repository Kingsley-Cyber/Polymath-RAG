# unit: control/control/scheduler.py
anchor: control/control/scheduler.py:1-479

## purpose
Outbox scheduling for the control loop: materializes census gaps as `outbox_events` rows (idempotent, same tick transaction as the census), re-opens receipt-gap stage tickets, auto-mints enrichment / doc-parent-map / doc_profile-early events, and applies census promote/degrade/fail transitions to `runs`. Consumed by `control/control/main.py` (sole importer, FACTS.importers). [DERIVED — scheduler.py:1-14, 32-103, 397-467]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `schedule_gaps` | def | `(conn: Connection, census: Census) -> int` | scheduler.py:32-103 | control/control/main.py (module importer) |
| `_reopen_receipt_gap_tickets` | def (private) | `(conn: Connection, census: Census) -> int` | scheduler.py:133-170 | `schedule_gaps` (scheduler.py:102) |
| `_bulk_first_outbox_payload` | def (private) | `(conn: Connection, event_type: str, run_ids: list[str]) -> dict[str, dict]` | scheduler.py:173-193 | `schedule_gaps` (scheduler.py:60, 68) |
| `_bulk_intake_metadata` | def (private) | `(conn: Connection, run_ids: list[str]) -> dict[str, dict]` | scheduler.py:196-212 | `schedule_gaps` (scheduler.py:70) |
| `_archived_run_ids` | def (private) | `(conn: Connection, run_ids: list[str]) -> set[str]` | scheduler.py:215-232 | `schedule_gaps` (scheduler.py:41) |
| `auto_enrich_on_chunks` | def | `(conn: Connection) -> int` | scheduler.py:235-298 | control/control/main.py (module importer) |
| `auto_map_parents_on_chunks` | def | `(conn: Connection) -> int` | scheduler.py:301-394 | control/control/main.py (module importer) |
| `apply_promotions` | def | `(conn: Connection, census: Census) -> None` | scheduler.py:397-431 | control/control/main.py (module importer) |
| `apply_degrades` | def | `(conn: Connection, census: Census) -> int` | scheduler.py:434-459 | control/control/main.py (module importer) |
| `apply_failures` | def | `(conn: Connection, census: Census) -> None` | scheduler.py:462-467 | control/control/main.py (module importer) |
| `_loads` / `_dumps` | def (private) | `(text: str) -> dict` / `(payload: dict) -> str` | scheduler.py:470-478 | internal |

FACTS list only the importing module, not per-symbol call sites. [DERIVED]

## contracts

**schedule_gaps** — scheduler.py:32-103
- in: `census.gaps` — Gap objects with `.run_id`, `.event_type` (scheduler.py:40, 45)
- out: `int` — summed `rowcount` of the chunked INSERTs (scheduler.py:87, 100)
- pre: census computed in the same tick transaction; a crash between census and schedule re-computes identical gaps next tick (scheduler.py:3-5)
- post: one `outbox_events` row per (run, type, payload) with `idempotency_key = content_hash({"run": rid, "type": event_type, "payload": payload})` (scheduler.py:50-52); conflict only re-arms when `delivered_at IS NOT NULL` (scheduler.py:95-97); runs in `_archived_run_ids` skipped (scheduler.py:41-44); `_reopen_receipt_gap_tickets` always runs (scheduler.py:102)
- payload sources: `_IDENTITY_ONLY` types get `{"run_id": rid}` with zero reads (scheduler.py:54-58); `chunked.v1` from first outbox payload (scheduler.py:59-66); `intake.v1` from first outbox payload, else `runs.metadata.intake_payload` (scheduler.py:67-76)

**_reopen_receipt_gap_tickets** — scheduler.py:133-170
- in: gaps with `event_type in _RECEIPT_GAP_STAGES` and `"receipts missing" in g.reason` (scheduler.py:136-138)
- out: count of tickets flipped `done -> ready` (scheduler.py:156-168, 170)
- pre: none
- post: skipped entirely if any open ticket (`status IN ('pending','ready','leased','repair')`, `archived_at IS NULL`) exists for the `(corpus_id, stage)` (scheduler.py:147-155); the one reopened ticket gets `lease_owner = NULL, lease_expires_at = NULL` (scheduler.py:158-160)

**auto_enrich_on_chunks** — scheduler.py:235-298
- in: none (reads DB)
- out: `int` minted count; `0` if `worker.enrichment_auto` falsy or `worker.enrichment_provider == "disabled"` (scheduler.py:246-250)
- post: first-mint only (`NOT EXISTS` on `stage_tickets.stage = 'parent_enrichment'`, scheduler.py:260-262) plus rescue of stranded `ready`/`failed` tickets with no undelivered event (scheduler.py:273-283); archived corpora and superseded runs excluded (scheduler.py:259-265)

**auto_map_parents_on_chunks** — scheduler.py:301-394
- in: none; gated by `doc_parent_map_enabled()`, scoped by `doc_parent_map_corpus_scope()` / `doc_parent_map_since()` (scheduler.py:309-318)
- out: `int` pMAP mint count (profile-early emits are NOT counted, scheduler.py:394)
- post: pMAP mint mirrors `auto_enrich_on_chunks` (scheduler.py:328-367); additionally emits `doc_profile` events for scoped runs whose `doc_profile` ticket is `pending` via `_emit_ticket_event` (scheduler.py:374-393); disabled flag = zero tickets, byte-identical behavior (scheduler.py:305-307)

**apply_promotions** — scheduler.py:397-431
- in: `census.promote` run ids
- out: `None`
- post: `runs.status = 'query_ready'` only when it differed (scheduler.py:398-405); on success runs `generation_swap.swap` in the same transaction (scheduler.py:409-410); then promotion-time `mint_parent_enrichment` backstop, same settings gate, fail-open (scheduler.py:411-431)

**apply_degrades** — scheduler.py:434-459
- in: `census.degrade` — `{run_id: reasons}`
- out: `int` changed rows
- post: `status = 'degraded'`, metadata merged with `degraded_reasons` (sorted JSON) and `degraded_contract = 'extraction-coverage-v1'`; no-op when already degraded with identical reason set (scheduler.py:441-457)

**apply_failures** — scheduler.py:462-467
- post: `runs.status = 'failed'` for each `census.fail` run id, unguarded UPDATE (scheduler.py:464-466)

## effect surface

| surface | detail | anchor |
|---|---|---|
| Postgres read | `outbox_events` (DISTINCT ON first payload) | scheduler.py:179-185 |
| Postgres read | `runs` (metadata; auto-mint candidate scans) | scheduler.py:201-207, 251-265, 328-340, 374-385 |
| Postgres read | `stage_tickets` (open-ticket check; superseded; NOT EXISTS guards; stranded) | scheduler.py:147-153, 223-231, 255-262, 273-283, 331-338, 345-357, 377-384 |
| Postgres read | `archived_corpora` | scheduler.py:227-230, 263-264, 338-339 |
| Postgres write | `outbox_events` — chunked INSERT via `unnest`, ON CONFLICT re-arm | scheduler.py:88-100 |
| Postgres write | `stage_tickets` — reopen UPDATE | scheduler.py:158-168 |
| Postgres write | `runs` — promote / degrade / fail UPDATEs | scheduler.py:399-401, 443-457, 464-466 |
| Settings/env | `get_settings().worker.enrichment_auto` (getattr default `True`), `worker.enrichment_provider` (getattr default `"disabled"`) | scheduler.py:247-249, 417-421 |
| Settings/env | `doc_parent_map_enabled()`, `doc_parent_map_corpus_scope()`, `doc_parent_map_since()` from `polymath_shared.document_profile.map_trigger` | scheduler.py:309-318 |
| Delegated writes | `mint_parent_enrichment`, `mint_doc_parent_map`, `_emit_ticket_event` receive `conn` — effects live outside this unit | scheduler.py:287-291, 361, 388 |

No files, network, or subprocess in this unit. [DERIVED — absent from SOURCE]

## invariants

INVARIANT: `_INSERT_CHUNK == 1000` — scheduler.py:23 [DERIVED]
  fails-if: INSERT batch size changes; no correctness impact, only statement size.
INVARIANT: idempotency_key == `content_hash({"run": rid, "type": event_type, "payload": payload})` — scheduler.py:50-52 [DERIVED]
  fails-if: key shape drifts → same gap mints a second outbox row instead of re-arming (byte-identical requirement stated at scheduler.py:12-14).
INVARIANT: `_IDENTITY_ONLY` payloads are exactly `{"run_id": rid}` — scheduler.py:26-29, 56-57 [DERIVED]
  fails-if: adding a field changes the content hash → duplicate events.
INVARIANT: conflict update fires only `WHERE outbox_events.delivered_at IS NOT NULL` — scheduler.py:95-97 [DERIVED]
  fails-if: every gap rewrites its row every tick — measured 206 MB bloat over 204 live rows, id sequence past 155M (scheduler.py:83-86).
INVARIANT: ≤ 1 open re-drive ticket per `(corpus_id, stage)` — scheduler.py:147-155 [DERIVED]
  fails-if: identical corpus-wide projection dispatched N× — measured 286k receipt writes over 14.6k entities per 15 min (scheduler.py:117-125).
INVARIANT: run in `_archived_run_ids` ⟹ zero outbox rows — scheduler.py:41-44 [DERIVED]
  fails-if: 44k armed debris events reclaim the claim FIFO after archival (scheduler.py:36-39).
INVARIANT: first payload per (run, type) = row with MIN `event_id` (`DISTINCT ON ... ORDER BY run_id, event_id`) — scheduler.py:180-184 [DERIVED]
  fails-if: a later payload is reused → different hash → duplicate outbox row.
INVARIANT: degrade write is no-op ⟺ `status == 'degraded'` AND `metadata->'degraded_reasons' == sorted(reasons)` — scheduler.py:455-456 [DERIVED]
  fails-if: pre-2026-09-02 behavior — runs stuck at `reconciling` with reasons already recorded (scheduler.py:450-454).
INVARIANT: early-enrich mint fires only when no `stage_tickets` row `stage = 'parent_enrichment'` exists — scheduler.py:260-262 [DERIVED]
  fails-if: finished enrichment reopened every tick (scheduler.py:243-245).

## determinism & idempotency
determinism: NONDETERMINISTIC (DB state: outbox first-payload scheduler.py:179-185, ticket/run tables throughout; SQL `now()` in UPDATEs scheduler.py:160, 400, 445, 465; settings flags scheduler.py:247-249, 315-318). `_dumps` uses `json.dumps` without `sort_keys` — scheduler.py:478 [INFERRED: key order follows dict insertion; stable only for the single-key identity payload].
idempotency: SAFE — inserts keyed by unique `idempotency_key` with guarded ON CONFLICT (scheduler.py:88-97); degrade/promote/fail guarded by status predicates (scheduler.py:399-401, 448-456, 464-466); auto-mints guarded by NOT EXISTS (scheduler.py:260-262, 336-338). `apply_failures` UPDATE is unguarded but sets the same value repeatedly — scheduler.py:464-466.

## failure behaviour
- Four broad `except Exception` handlers, all fail-open per run ("handled: import, log", FACTS.fallbacks): early-enrich mint scheduler.py:293, pMAP mint scheduler.py:363, doc_profile-early emit scheduler.py:389, promotion-time enrich mint scheduler.py:427. Tick continues; caller sees a warning log only.
- Logged error codes: `AUTO_ENRICH_MINT_FAILED` (scheduler.py:528, 431 numbering per SOURCE: 297-298, 431), `AUTO_PMAP_MINT_FAILED` (scheduler.py:367), `AUTO_PROFILE_EARLY_FAILED` (scheduler.py:393) — all via `logging.getLogger("control-schedule")`.
- `apply_promotions` generation swap is NOT wrapped: a swap failure rolls back the whole tick transaction and the successor stays hidden (scheduler.py:406-410).
- Unhandled exceptions in `schedule_gaps`/`apply_*` SQL propagate to the tick transaction; crash-safety comes from re-computing gaps next tick (scheduler.py:3-5).

## dumb-code flags
- FACTS `tables_written` includes `"set"` — no such table; static-analysis artifact of `UPDATE ... SET` (scheduler.py:158, 399, 443, 464). Same class of artifact: `"unnest"` listed under `tables_read` is a set-returning function (scheduler.py:93). [DERIVED from FACTS vs SOURCE]
- Settings gate duplicated verbatim: `getattr(w, "enrichment_auto", True)` / `getattr(w, "enrichment_provider", "disabled")` at scheduler.py:248-249 AND scheduler.py:419-421 — defaults must stay in sync.
- Run-status tuple `('intake', 'reconciling', 'degraded', 'query_ready')` repeated 3× — scheduler.py:257-258, 334, 383.
- Substring coupling: `"receipts missing" in (g.reason or "")` — scheduler.py:137 [INFERRED: silently breaks if census rewords its reason strings].
- `_loads`/`_dumps` re-`import json` on every call — scheduler.py:471, 477.
- Logger fetched per-exception instead of module-level — scheduler.py:295, 365, 391, 429.
- `apply_degrades` sorts reasons before dumping (scheduler.py:441); `_dumps` does not sort — two serialization conventions in one file (scheduler.py:441 vs 478).

## refactor notes
- Sole importer is `control/control/main.py` (FACTS.importers) — every rename/delete must update it.
- Idempotency-key dict shape `{"run", "type", "payload"}` is frozen: changing it orphans all armed rows and duplicates work (scheduler.py:12-14, 50-52).
- The `WHERE outbox_events.delivered_at IS NOT NULL` guard and the one-open-ticket-per-`(corpus, stage)` check are load-bearing against measured incidents (scheduler.py:83-86, 117-125) — do not "simplify" them away.
- `_RECEIPT_GAP_STAGES` values must equal `stage_tickets.stage` names (`project_qdrant`, `project_neo4j`, `project_canonical`) used in the open-ticket and reopen queries (scheduler.py:126-130, 149, 163).
- doc_profile-early must keep using `control.tickets._emit_ticket_event` — it is the canonical idempotent emission the chain advancement later observes (scheduler.py:372-374, 388).
- Census contract consumed here: `Gap.run_id`, `Gap.event_type`, `Gap.corpus_id`, `Gap.reason`; `Census.gaps/promote/degrade/fail` (scheduler.py:40, 45, 136-139, 398, 440, 463) — changes to `control.census` ripple directly.

## VERIFY

```verify
grep -Fq '_INSERT_CHUNK = 1000' control/control/scheduler.py
grep -Fq 'DO UPDATE SET delivered_at = NULL' control/control/scheduler.py
grep -Fq 'WHERE outbox_events.delivered_at IS NOT NULL' control/control/scheduler.py
grep -Fq '"receipts missing"' control/control/scheduler.py
grep -Fq 'extraction-coverage-v1' control/control/scheduler.py
test "$(grep -c -F 'AUTO_ENRICH_MINT_FAILED' control/control/scheduler.py)" -ge 2
! grep -Fq 'sort_keys' control/control/scheduler.py
```
