# unit: control/control/tickets.py
anchor: control/control/tickets.py:1-833

## purpose
CONTROL-PLANE-V2 stage tickets (ADR-0014): a stage's work event exists ONLY after the control plane verifies the predecessor's artifacts, receipts, and contract; run chains progress independently (pipelined fan-out); per-stage pending high watermarks pause new intake tickets (backpressure); promotion to query_ready is a generation barrier — control/control/tickets.py:1-8 [DERIVED]. Consumed by the control-plane tick/reconciliation side: census.py, main.py, reconciliation.py, scheduler.py, stall_tracer.py (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| is_blocking | def | (stage: str) -> bool | control/control/tickets.py:80-81 | — |
| ticket_id | def | (run_id: str, stage: str, generation: int = 1) -> str | control/control/tickets.py:89-90 | — |
| ensure_run_tickets | def | (conn, run_id, corpus_id, execution_contract: dict \| None = None) -> list[str] | control/control/tickets.py:93-137 | — |
| receipt_scope_for | def | (stage: str) -> str | control/control/tickets.py:229-230 | — |
| advance_tickets | def | (conn) -> int | control/control/tickets.py:308-362 | — |
| generation_barrier | def | (conn, corpus_id, missing_by_projection: dict \| None = None) -> dict | control/control/tickets.py:599-652 | — |
| extract_active_count | def | (conn) -> int | control/control/tickets.py:659-664 | — |
| backpressure_decision | def | (conn, corpus_id) -> tuple[bool, str] | control/control/tickets.py:667-680 | — |
| backpressure_paused | def | (conn, stage="extract", watermark=DEFAULT_HIGH_WATERMARK) -> bool | control/control/tickets.py:683-690 | — |
| eligible_page | def | (conn, *, stage: str, corpus_id: str, limit: int = 256) -> tuple[list[tuple], int] | control/control/tickets.py:702-732 | — |
| refresh_corpus_runtime_state | def | (conn, *, watermark: int \| None = None) -> dict | control/control/tickets.py:737-780 | — |
| eligible_creation_corpora | def | (conn, window: int = 32) -> list[str] | control/control/tickets.py:783-795 | — |
| fair_ensure_tickets_backpressure_gated | def | (conn, *, window: int = 32) -> int | control/control/tickets.py:798-832 | — |
| STAGE_DAG | const | 14 tuples (stage, event_type, artifacts, receipts) | control/control/tickets.py:24-58 | — |
| NON_BLOCKING_STAGES | const | frozenset, 8 stage names | control/control/tickets.py:63-77 | — |
| CORPUS_STAGES | const | ("corpus_summary", "vocabulary") | control/control/tickets.py:226 | — |
| DEFAULT_HIGH_WATERMARK | const | 64 | control/control/tickets.py:86 | — |
| GLOBAL_EXTRACT_LIMIT | const | 256 | control/control/tickets.py:655 | — |
| CORPUS_EXTRACT_WATERMARK | const | 64 | control/control/tickets.py:656 | — |

"used by" is file-level only (FACTS.importers): census.py, main.py, reconciliation.py, scheduler.py, stall_tracer.py; per-symbol callers unknown.

Private helpers: `_stage_attempt_ok` :140-163, `_artifacts_present` :166-178, `_verdict_get` :202-211, `_verdict_put` :214-217, `_run_doc_ids` :233-242, `_receipts_present` :245-302, `_eligible_all_stages` :365-391, `_corpora_with_missing_chunk_receipts` :394-420, `_advance_pending_corpus` :423-455, `_try_advance_one` :461-507, `_corpus_of` :512-516, `_emit_ticket_event` :519-548, `_release_expired_leases` :551-596, `_reset_cursor` :693-699.

## contracts

**ensure_run_tickets — control/control/tickets.py:93-137**
- in: run_id, corpus_id, optional execution_contract.
- out: list of newly created ticket_ids; existing rows skipped (`continue`, :111-112).
- pre: stage_tickets unique on (run_id, stage, generation); runs row exists for the contract UPDATE (:132-136).
- post: intake ticket born `status="ready"` and its event emitted immediately (:113-114, :129-131); stage with ok attempt/DONE ticket born `"done"` (:115-116, :140-163); all others `"pending"` (:117-118).
- idempotent: `ON CONFLICT (run_id, stage, generation) DO NOTHING` (:119-127).

**advance_tickets — control/control/tickets.py:308-362**
- in: conn. out: count of advanced tickets this tick.
- post: missing_by_projection computed ONCE per tick for ("qdrant", "neo4j") (:324-328); per-corpus advancement (:329-331); READY backfill re-emits undelivered claim events `LIMIT 256`, skipping stages not in `_STAGE_SPEC` (:333-353); `_release_expired_leases` runs last (:361). One full pass per tick maximum (:311-314).

**generation_barrier — control/control/tickets.py:599-652**
- in: corpus_id; missing_by_projection defaults to per-projection gap sets (:608-610).
- out: `{"open_tickets", "open_by_status", "incomplete_projections", "passed"}` (:647-651); `passed == not pending and incomplete_receipts == 0`.
- open work = status IN ('pending','ready','leased'), archived_at IS NULL, stage != ALL(sorted(NON_BLOCKING_STAGES)), excluding PENDING tickets behind a FAILED ticket of the same run via `array_position` over DAG_ORDER (:625-635).
- incomplete_receipts += len(run_ids) per projection whose gap set contains the corpus (:644-646).

**backpressure_decision — control/control/tickets.py:667-680**
- out: (True, "global_ceiling") when extract_active_count >= 256; (True, "corpus_watermark") when per-corpus extract active >= 64; else (False, "").

**fair_ensure_tickets_backpressure_gated — control/control/tickets.py:798-832**
- in: window=32. out: total tickets created.
- post: refresh_corpus_runtime_state(watermark=CORPUS_EXTRACT_WATERMARK) first (:802-803); `last_creation_tick` stamped BEFORE checking for work (:808-816); quota `per = max(1, window // max(len(eligible), 1))` (:806); chains minted with `default_execution_contract()` (:829-831).

**eligible_page — control/control/tickets.py:702-732**
- out: (rows, next_seq) over PENDING tickets with seq > cursor; empty page rewinds cursor to 0 (:719-724).

**_release_expired_leases — control/control/tickets.py:551-596**
- out: count of released tickets; released -> status='ready', lease fields NULLed.
- owner_stale := COALESCE(heartbeat_at < now() - interval '90 seconds', TRUE) (:566-568); attempt += 1 only when owner_stale (:578); stale owners quarantined (:589-594).

**_emit_ticket_event — control/control/tickets.py:519-548**
- the ONLY path by which stage work becomes claimable (:520-521); payload = original stage outbox payload + `ticket_id` (:525-534); upsert keyed by content_hash idempotency_key, re-delivers only if delivered_at IS NOT NULL (:535-543); ticket set to 'ready' (:545-548).

## effect surface
- Postgres read (FACTS.tables_read): archived_corpora (:791-792), artifacts (:171), chunks (:285), corpora (:750, :820), corpus_runtime_state (:758, :789), documents (:239), outbox_events (:339, :526), projection_receipts (:289), runs (:238-241, :513, :638, :749, :819), scheduler_cursors (:367, :711), stage_attempts (:142), stage_tickets (throughout), worker_registrations (:526, :592). FACTS also lists `expired` — that is the CTE name in :566, not a table [INFERRED].
- Postgres written (FACTS.tables_written): stage_tickets (:119-127, :545-548, :574-586, :1001-1003 → source :545/:574), outbox_events (:537-543), runs (:133-136), scheduler_cursors (:354-359, :385-390, :696-698, :721-731), corpus_runtime_state (:768-777, :814-816), worker_registrations (:591-594). FACTS also lists `set` — artifact of `_SIDE_STAGE_SEEN: set[str] = set()` (:458), not a table [INFERRED].
- External imports: polymath_shared.execution.default_execution_contract (:16-17), polymath_shared.identity.content_hash (:18), polymath_shared.projection_want.{corpora_with_missing_chunk_receipts, missing_chunk_receipts_for_docs} (:279, :417-419).
- 'qdrant' / 'neo4j' appear only as projection-name strings (:327, :440, :610, :644); no direct Qdrant/Neo4j client, file, subprocess, or env-flag access in SOURCE [INFERRED].

## invariants
INVARIANT: len(STAGE_DAG) == 14 and "parent_enrichment" ∉ DAG_ORDER and "doc_parent_map" ∉ DAG_ORDER while both ∈ NON_BLOCKING_STAGES — control/control/tickets.py:24-58, :63-77 [DERIVED]
  fails-if: `DAG_ORDER.index(stage)` ValueError kills the whole tick (measured 10,191 consecutive failures, :463-468).
INVARIANT: _RECEIPT_TTL[RECEIPT_STATE_PRESENT] == 90.0 < _RECEIPT_TTL[RECEIPT_STATE_MISSING] == 900.0 — control/control/tickets.py:195-198 [DERIVED]
  fails-if: MISSING expiring sooner than PRESENT lets advancement be decided by stale absence — the bool-encoding bug VERDICT-STORE-V2 fixed (:181-185).
INVARIANT: a MISSING verdict only delays (`ok = False`, :491-492); it can never create advancement — control/control/tickets.py:181-192 [DERIVED]
  fails-if: measured-MISSING read back as present falsely advances a run (:181-185).
INVARIANT: CORPUS_STAGES == ("corpus_summary", "vocabulary"); receipt_scope_for returns "corpus" only for those, else "run" — control/control/tickets.py:226, :229-230 [DERIVED]
  fails-if: corpus-wide anti-join per stage stalls sibling documents (measured >5 min, :220-225).
INVARIANT: GLOBAL_EXTRACT_LIMIT (256) > CORPUS_EXTRACT_WATERMARK (64) == DEFAULT_HIGH_WATERMARK (64) — control/control/tickets.py:86, :655-656 [DERIVED]
  fails-if: per-corpus watermark above the global ceiling makes the two-tier decision degenerate (global_ceiling always wins).
INVARIANT: hysteresis resume threshold eff_wm // 2 < pause threshold eff_wm — control/control/tickets.py:762-765 [DERIVED]
  fails-if: equal thresholds flip `creation_paused` every tick (:738-740).
INVARIANT: verify_projections required artifact keys == ("qdrant", "routing_qdrant", "neo4j", "canonical") — control/control/tickets.py:38-39 [DERIVED]
  fails-if: a stale declared key ('docs') fails the artifact check → summary stages never ready → corpus cannot promote (:32-37).
INVARIANT: expired-lease attempt increment ⟺ owner_stale (heartbeat_at < now() - interval '90 seconds') — control/control/tickets.py:568, :578 [DERIVED]
  fails-if: live worker's missed renewal burns retry budget and quarantines it (measured: all 24 projections of release-books-v1 silently failed, :553-559).
INVARIANT: barrier passed ⟺ open_tickets == 0 AND incomplete_receipts == 0 — control/control/tickets.py:651 [DERIVED]
  fails-if: counting superseded/failed history rows or dead chains as open work permanently blocks reconciled corpora (:611-624).
INVARIANT: ticket_id == "tkt_" + content_hash({"run": run_id, "stage": stage, "gen": generation})[:32], generation default 1 — control/control/tickets.py:89-90 [DERIVED]
  fails-if: divergent ID minting breaks the (run_id, stage, generation) ON CONFLICT dedupe (:124).

## determinism & idempotency
determinism: NONDETERMINISTIC — `time.monotonic()` verdict TTLs (:204, :209, :216), SQL `now()` (:358, :384, :543, :568, :583, :696, :722, :730, :769, :815), and DB state.
idempotency: SAFE — ticket insert `ON CONFLICT (run_id, stage, generation) DO NOTHING` (:124), outbox upsert on idempotency_key that only re-opens delivered rows (:540-541). Caveat: `_RECEIPT_VERDICT_STORE` (:199) and `_SIDE_STAGE_SEEN` (:458) are process-local module globals; restart forgets verdicts (PRESENT "can flip on store loss", :188-189 — the safe direction) [INFERRED].

## failure behaviour
- Only explicit raise: `assert state in (RECEIPT_STATE_PRESENT, RECEIPT_STATE_MISSING)` in _verdict_put (:215).
- Stray PENDING side-stage ticket: skipped, never advanced, one warning per stage via logger "control-tickets" (:469-473); the READY backfill likewise `continue`s on stages not in `_STAGE_SPEC` (:347-352).
- Expired lease: ticket returns to 'ready' with `last_error_note` = 'lease expired: executing worker gone' or 'lease_expired_while_owner_alive (no retry consumed)' (:579-582).
- Missing base outbox payload degrades to `base = {"run_id": run_id}` (:529-532).
- Run without resolvable source_name: `_run_doc_ids` returns [] → `_receipts_present` falls back to corpus scope (:234-236, :267-274).
- No retries/exceptions elsewhere; unmet predecessors simply return False (:504-505, :959-960 → source :504-505).

## dumb-code flags
- `backpressure_paused` ignores its `stage` and `watermark` params; body only reads GLOBAL_EXTRACT_LIMIT; comment marks it SUPERSEDED (:683-690).
- `_reset_cursor` has no call site in this file (:693-699) [INFERRED].
- Literal `256` reused for four distinct knobs: ADVANCE_PAGE (:305), GLOBAL_EXTRACT_LIMIT (:655), eligible_page default limit (:703), READY backfill LIMIT (:343). Literal `64`: DEFAULT_HIGH_WATERMARK (:86) and CORPUS_EXTRACT_WATERMARK (:656). `90` means both PRESENT TTL seconds (:196) and heartbeat staleness '90 seconds' (:568).
- Tuple ("qdrant", "neo4j") duplicated 4× (:327, :440, :610, :644).
- `_eligible_all_stages` (:365-391) and `eligible_page` (:702-732) duplicate keyset+wrap logic under different cursor keys ('__all__' vs stage).
- Function-local imports: `import time as _time` (:204, :216), `import logging` (:471), projection_want imports (:279, :417).
- DAG_ORDER / `_STAGE_SPEC` frozen at import time (:83-84) — stage list edits need a process restart to take effect [INFERRED].

## refactor notes
- STAGE_DAG order is semantic: predecessors = DAG_ORDER[:idx] (:475-476) and the barrier dead-chain exclusion uses `array_position(%s::text[], ...)` over DAG_ORDER (:633, :635). Reordering or inserting changes advancement and barrier semantics.
- DOCUMENT-PROFILE-V1 phase B moves "doc_profile" ahead of verify_projections AND removes it from NON_BLOCKING_STAGES — both edits together, else QUERY_READY semantics change (:52-57, :66).
- Side stages (parent_enrichment, doc_parent_map) must stay absent from STAGE_DAG; both guards exist because violations killed whole ticks (:346-352, :462-474).
- `_emit_ticket_event` is the single claimability path with three call sites (:131, :353, :506) — any new emission route breaks the "ONLY path" contract (:520-521).
- Verdict-store key shapes are a cross-function contract: corpus key (run_id, projection) vs run key (run_id, projection, "run") (:275, :444-446, :494).
- The chunk-receipt want rule is owned by polymath_shared.projection_want — do not re-localize (:277-279, :415-416).
- ON CONFLICT targets assume unique constraints: (run_id, stage, generation) on stage_tickets (:124), (idempotency_key) on outbox_events (:540), (stage, corpus_id) on scheduler_cursors (:357, :387, :729), (corpus_id) on corpus_runtime_state (:771).
- Run-status filter ('intake','reconciling','degraded') duplicated at :751 and :821.
- Importers (file-level): census.py, main.py, reconciliation.py, scheduler.py, stall_tracer.py — removing `backpressure_paused` or changing public signatures requires checking those five.

## VERIFY
```verify
grep -Fq 'GLOBAL_EXTRACT_LIMIT = 256' control/control/tickets.py
grep -Fq 'CORPUS_EXTRACT_WATERMARK = 64' control/control/tickets.py
grep -Fq 'RECEIPT_STATE_MISSING: 900.0' control/control/tickets.py
grep -Fq '("qdrant", "routing_qdrant", "neo4j", "canonical")' control/control/tickets.py
grep -Fq 'WITH expired AS' control/control/tickets.py
! grep -Fq 'RECEIPT_STATE_UNKNOWN' control/control/tickets.py
test "$(grep -c -F 'ensure_run_tickets(' control/control/tickets.py)" -ge 2
```
