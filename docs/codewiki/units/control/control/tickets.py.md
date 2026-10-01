# unit: control/control/tickets.py
anchor: control/control/tickets.py:1-819

## purpose
CONTROL-PLANE-V2 stage-ticket engine (ADR-0014): a stage's work event is emitted only after the control plane verifies the predecessor's artifacts, receipts, and contract (explicit handoff). Per-run chains pipeline independently; pending high watermarks pause new intake (backpressure); corpus promotion to QUERY_READY is a generation barrier. — control/control/tickets.py:1-8 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| is_blocking | def | (stage: str) -> bool | control/control/tickets.py:80-81 | ¹ |
| ticket_id | def | (run_id: str, stage: str, generation: int = 1) -> str | control/control/tickets.py:89-90 | ¹ |
| ensure_run_tickets | def | (conn, run_id, corpus_id, execution_contract: dict \| None = None) -> list[str] | control/control/tickets.py:93-137 | ¹ |
| receipt_scope_for | def | (stage: str) -> str | control/control/tickets.py:229-230 | ¹ |
| advance_tickets | def | (conn) -> int | control/control/tickets.py:308-362 | ¹ |
| generation_barrier | def | (conn, corpus_id, missing_by_projection: dict \| None = None) -> dict | control/control/tickets.py:599-639 | ¹ |
| extract_active_count | def | (conn) -> int | control/control/tickets.py:646-651 | ¹ |
| backpressure_decision | def | (conn, corpus_id) -> tuple[bool, str] | control/control/tickets.py:654-667 | ¹ |
| backpressure_paused | def | (conn, stage="extract", watermark=DEFAULT_HIGH_WATERMARK) -> bool | control/control/tickets.py:670-677 | ¹ |
| eligible_page | def | (conn, *, stage, corpus_id, limit: int = 256) -> tuple[list[tuple], int] | control/control/tickets.py:689-719 | ¹ |
| refresh_corpus_runtime_state | def | (conn, *, watermark: int \| None = None) -> dict | control/control/tickets.py:724-767 | ¹ |
| eligible_creation_corpora | def | (conn, window: int = 32) -> list[str] | control/control/tickets.py:770-782 | ¹ |
| fair_ensure_tickets_backpressure_gated | def | (conn, *, window: int = 32) -> int | control/control/tickets.py:785-819 | ¹ |

¹ FACTS.importers (module-level only): control/control/census.py, control/control/main.py, control/control/reconciliation.py, control/control/scheduler.py, control/control/stall_tracer.py — material-6207205376-901887955763333.md:344-350. Per-symbol callers not recorded.

Stage chain (STAGE_DAG, ORDERED — each entry gated on all before it): intake → extract → profile_document → project_qdrant → project_neo4j → canonicalize → project_canonical → verify_projections → compile_objects → parent_summary → document_summary → corpus_summary → vocabulary → doc_profile — control/control/tickets.py:24-58 [DERIVED]

## contracts

**ensure_run_tickets** — control/control/tickets.py:93-137
- in: existing run row; optional execution_contract dict.
- out: list of newly created ticket_ids; empty on re-run.
- pre: `stage_tickets` has unique key (run_id, stage, generation) — ON CONFLICT DO NOTHING, idempotent.
- post: intake ticket status "ready" + event emitted at birth; any other stage born "done" if latest `stage_attempts.outcome == "ok"` or a DONE ticket already exists (CHAIN-CREATION-RECONCILES-HISTORY), else "pending" — control/control/tickets.py:113-118, 140-163.
- post: execution_contract, when given, is written to `runs.execution_contract` as JSON — control/control/tickets.py:132-136.

**advance_tickets** — control/control/tickets.py:308-362
- in: conn; no args.
- out: count of advanced/backfilled tickets.
- post: per corpus with PENDING tickets, walks pages of `ADVANCE_PAGE = 256` past the `scheduler_cursors` row for stage `'__all__'`; empty page resets cursor to 0 → at most one full pass per tick — control/control/tickets.py:305, 365-391, 448-455.
- post: bulk receipt gaps for `("qdrant", "neo4j")` computed ONCE per tick and pre-seeded into the verdict store for every pending run — control/control/tickets.py:324-331, 440-446.
- post: READY backfill re-emits missing claim events (limit 256, undelivered only) — control/control/tickets.py:333-360.
- post: `_release_expired_leases(conn)` runs at the end of every tick — control/control/tickets.py:361.

**generation_barrier** — control/control/tickets.py:599-639
- out: dict with exactly `open_tickets` (int), `open_by_status` (dict "stage/status" -> count), `incomplete_projections` (int), `passed` (bool).
- post: `passed` is True iff zero non-blocking-stage tickets in `('pending','ready','leased')` (archived_at IS NULL) AND corpus absent from both projection gap sets — control/control/tickets.py:616-638.

**backpressure_decision** — control/control/tickets.py:654-667
- out: `(True, "global_ceiling")` when active extract tickets >= `GLOBAL_EXTRACT_LIMIT = 256`; `(True, "corpus_watermark")` when corpus extract tickets >= `CORPUS_EXTRACT_WATERMARK = 64`; else `(False, "")`.

**eligible_page** — control/control/tickets.py:689-719
- out: `(rows, next_seq)` of PENDING tickets with seq strictly > stored cursor; empty page rewinds cursor to 0 and returns `([], 0)`.

**fair_ensure_tickets_backpressure_gated** — control/control/tickets.py:785-819
- post: refreshes hysteresis, round-robins the window (default 32) over non-paused, non-archived corpora; marks `last_creation_tick` BEFORE checking for work; mints chains for runs in `('intake','reconciling','degraded')` with no tickets — control/control/tickets.py:793-818.

**_release_expired_leases** (internal) — control/control/tickets.py:551-596
- pre: ticket status "leased" AND `lease_expires_at < now()`.
- post: owner stale (no worker row, or `heartbeat_at < now() - interval '90 seconds'`) → back to "ready", attempt += 1, worker set `status='quarantined'`; owner alive → "ready", attempt unchanged, note `'lease_expired_while_owner_alive (no retry consumed)'` — control/control/tickets.py:566-595.

**_emit_ticket_event** (internal) — control/control/tickets.py:519-548
- the ONLY path marking a ticket READY and upserting its outbox event; idempotency_key = `content_hash({"run", "type", "payload"})` with `ticket_id` added to the producing stage's original payload — control/control/tickets.py:520-535.

## effect surface

| kind | item | anchor |
|---|---|---|
| PG read | stage_tickets, runs, stage_attempts, artifacts, outbox_events, scheduler_cursors, chunks, documents, projection_receipts, corpora, corpus_runtime_state, archived_corpora, worker_registrations | control/control/tickets.py:109, 238-241, 143-147, 171, 339/526, 367/698, 285-293, 241/286, 289, 737/761/806, 745/776, 778, 567 |
| PG write | stage_tickets (INSERT 120-127, UPDATE 545-548, 574-586), outbox_events (537-543), runs (133-135), scheduler_cursors (354-359, 385-390, 708-718, 801-803), corpus_runtime_state (755-764, 801-803), worker_registrations (591-594) | control/control/tickets.py:120-135 |
| module import | polymath_shared.execution.default_execution_contract; polymath_shared.identity.content_hash; polymath_shared.projection_want.{corpora_with_missing_chunk_receipts, missing_chunk_receipts_for_docs} | control/control/tickets.py:16-18, 279, 417-419 |
| no direct | files, network, subprocesses, env flags, Qdrant collections — none in SOURCE | — |

FACTS tables_read also lists "expired" — that is the SQL CTE name at control/control/tickets.py:566, not a table; FACTS tables_written lists "set" — that is the annotation `_SIDE_STAGE_SEEN: set[str] = set()` at control/control/tickets.py:458 — material-6207205376-901887955763333.md:360-384 [DERIVED].

## invariants

INVARIANT: MISSING verdict TTL 900.0 == 10 × PRESENT TTL 90.0 — control/control/tickets.py:195-198 [DERIVED]
  fails-if: a stale MISSING could outlive real receipts (delay only, never advances) or a stale PRESENT could mask real gaps (false advancement).
INVARIANT: len(STAGE_DAG) == 14; side stages `parent_enrichment` and `doc_parent_map` are ABSENT from it and in NON_BLOCKING_STAGES — control/control/tickets.py:24-58, 63-77 [DERIVED]
  fails-if: `DAG_ORDER.index(stage)` raises ValueError and kills the whole tick (measured 10,191 consecutive failures) — control/control/tickets.py:463-468.
INVARIANT: GLOBAL_EXTRACT_LIMIT 256 > CORPUS_EXTRACT_WATERMARK 64 == DEFAULT_HIGH_WATERMARK 64 — control/control/tickets.py:86, 642-643 [DERIVED]
  fails-if: one corpus could exhaust the global ceiling (or the ceiling stops binding).
INVARIANT: hysteresis — pause enters at n >= watermark, resumes only at n <= watermark // 2 (32 at default 64) — control/control/tickets.py:749-752 [DERIVED]
  fails-if: creation gate flip-flops at the boundary.
INVARIANT: verdict cache keys — corpus scope `(run_id, projection)`; run scope `(run_id, projection, "run")` — control/control/tickets.py:275, 444, 489 [DERIVED]
  fails-if: a sibling document's missing chunks wrongly veto this run's stages (RUN-SCOPED-RECEIPTS-V1).
INVARIANT: CORPUS_STAGES == ("corpus_summary", "vocabulary") and both are members of NON_BLOCKING_STAGES — control/control/tickets.py:226, 63-77 [DERIVED]
  fails-if: corpus-scoped receipt waits would block promotion the frozenset is supposed to allow.
INVARIANT: `passed` == (no open non-blocking-excluded tickets AND incomplete_receipts == 0) — control/control/tickets.py:634-638 [DERIVED]
INVARIANT: ticket_id == "tkt_" + content_hash({"run", "stage", "gen"})[:32] — control/control/tickets.py:89-90 [DERIVED]
INVARIANT: _RECEIPT_VERDICT_STORE entries are only ever overwritten, never deleted — control/control/tickets.py:199, 214-217 [DERIVED]
  fails-if: unbounded growth over a long-lived process. [INFERRED: no del/clear path exists in SOURCE]

## determinism & idempotency
determinism: NONDETERMINISTIC (Postgres reads via psycopg Connection — control/control/tickets.py:14; `time.monotonic()` TTL checks — control/control/tickets.py:204, 211, 672; SQL `now()` — e.g. control/control/tickets.py:568, 715; cross-call module globals `_RECEIPT_VERDICT_STORE`, `_SIDE_STAGE_SEEN` — control/control/tickets.py:199, 458).
idempotency: SAFE (ticket INSERT ON CONFLICT (run_id, stage, generation) DO NOTHING — control/control/tickets.py:124; outbox upsert on idempotency_key re-nulls delivered_at only if previously delivered — control/control/tickets.py:538-542; all cursor writes are upserts — control/control/tickets.py:385-390, 713-718).

## failure behaviour
- `assert state in (RECEIPT_STATE_PRESENT, RECEIPT_STATE_MISSING)` in _verdict_put — AssertionError is the only explicit raise — control/control/tickets.py:215.
- Stray PENDING ticket for a side stage: skipped, never advanced, one warning per stage via `logging.getLogger("control-tickets")`; caller sees `False` from `_try_advance_one` — control/control/tickets.py:469-474.
- Expired lease: never raises; requeues ticket and, only when owner is stale, quarantines the worker (`status='quarantined'`, `last_error='lease expired without completion'`) — control/control/tickets.py:564-595.
- Barrier never throws on unknown stages; it excludes `sorted(NON_BLOCKING_STAGES)` via `!= ALL(...)` — control/control/tickets.py:617-622.
- Documented historical failures (comment record, guard now present): TypeError killed 1,864 consecutive ticks after verdict-store cutover — control/control/tickets.py:316-320; KeyError on owner-triggered stages left census dead 2h — control/control/tickets.py:346-352; per-run anti-join ground >100 minutes — control/control/tickets.py:395-403.

## dumb-code flags
- **Param-binding defect in READY backfill**: the SELECT fetches `(seq, ticket_id, run_id, stage)` — no corpus_id — but the cursor INSERT is `VALUES ('__ready__',%s,%s)` executed with `(stage, seq)`, binding the *stage name* into the `corpus_id` column — control/control/tickets.py:336, 354-359 [DERIVED].
- `backpressure_paused` accepts `watermark: int = DEFAULT_HIGH_WATERMARK` and never uses it; body checks only `extract_active_count(conn) >= GLOBAL_EXTRACT_LIMIT`; comment marks it "SUPERSEDED by backpressure_decision" — control/control/tickets.py:670-677 [DERIVED].
- `_reset_cursor` has no caller in this file; `eligible_page` re-implements the same rewind inline — control/control/tickets.py:680-686 vs 707-711 [INFERRED: likely dead within this unit].
- Repeated literals: `('pending','ready','leased')` at control/control/tickets.py:618-621, 648-650, 662-664, 703-704, 730-732; `("qdrant", "neo4j")` pairs at control/control/tickets.py:327, 440, 610, 631.
- `import time as _time` re-imported locally in three functions — control/control/tickets.py:204, 211, 672.
- Magic numbers: `ADVANCE_PAGE = 256` (305), backfill `LIMIT 256` (343), `eligible_page` default `limit: int = 256` (690), `window: int = 32` (771, 787), staleness `'90 seconds'` (568).
- `doc_profile` sits in NON_BLOCKING_STAGES marked "rollout phase A only — removed in phase B" — a scheduled semantic switch, not a stable default — control/control/tickets.py:52-57, 66.
- `conn.commit()` mid-advance inside `_eligible_all_stages` — a transaction boundary buried in a paging helper — control/control/tickets.py:380.

## refactor notes
- STAGE_DAG order is the advancement authority: `_try_advance_one` gates on `DAG_ORDER[:idx]` predecessors and their artifact keys — reordering re-gates every corpus; the stale `'docs'` verify key already blocked all post-rewrite chains (VERIFY-DAG-KEYS-V2) — control/control/tickets.py:32-39, 475-483.
- NON_BLOCKING_STAGES is consumed by both `is_blocking` and the barrier SQL `stage != ALL(%s)` — removing `doc_profile` (phase B) makes QUERY_READY require the profile for every corpus — control/control/tickets.py:80-81, 617-622, 66.
- Side stages must stay OUT of STAGE_DAG: two guards depend on `stage not in _STAGE_SPEC` (READY backfill and `_try_advance_one`) — control/control/tickets.py:346-352, 462-474.
- Verdict-cache key shapes are a cross-function contract shared by `_receipts_present`, `_advance_pending_corpus`, `_try_advance_one` — changing the tuple shape silently orphans cached verdicts — control/control/tickets.py:275, 444, 489.
- Want rules are owned by `polymath_shared.projection_want` (WANT-SET-AUTHORITY-V1); a third local copy previously wedged the barrier — do not duplicate — control/control/tickets.py:415-419, 279.
- Fixing the `__ready__` cursor binding requires adding `corpus_id` to the backfill SELECT before reordering its params — control/control/tickets.py:334-359.
- Five importers (census, main, reconciliation, scheduler, stall_tracer) — material-6207205376-901887955763333.md:344-350; renaming any public symbol above touches all five.

## VERIFY
```verify
grep -Fq 'GLOBAL_EXTRACT_LIMIT = 256' control/control/tickets.py
grep -Fq 'RECEIPT_STATE_MISSING: 900.0' control/control/tickets.py
grep -Fq 'return "tkt_" + content_hash' control/control/tickets.py
grep -Eq 'interval .90 seconds.' control/control/tickets.py
grep -Fq 'SUPERSEDED by backpressure_decision' control/control/tickets.py
grep -Eq '__ready__.,%s,%s' control/control/tickets.py
grep -Fq 'last_creation_tick ASC NULLS FIRST' control/control/tickets.py
test "$(grep -c -F 'stage_tickets' control/control/tickets.py)" -ge 12
```
