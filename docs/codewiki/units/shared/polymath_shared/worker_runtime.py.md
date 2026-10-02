# unit: shared/polymath_shared/worker_runtime.py
anchor: shared/polymath_shared/worker_runtime.py:1-637

## purpose
CONTROL-PLANE-V2 (ADR-0014) worker runtime: one loop for the whole worker fleet — register identity, heartbeat, claim ONLY ticket-gated events that are `ready` and compatible with the run's pinned execution contract, execute the stage, mark the ticket done — shared/polymath_shared/worker_runtime.py:1-12 [DERIVED]. Workers are dumb executors of exactly-scoped legal work units; the control plane owns what happens next — shared/polymath_shared/worker_runtime.py:3-6 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `run_worker` | def | (worker_type, event_types, process_event, poll_interval_s=2.0, batch_size=1, extra_env_check=None) -> None | 359-526 | 12 importer modules in FACTS.importers (intake, extract, profile, doc_profile, canonicalize, project_canonical, project_neo4j, project_qdrant, summary_worker_impl, verify, doc_parent_map_stage_worker, _small-modules) |
| `claim_ticket_events` | def | (conn, identity, event_types, limit, lane_affinity=None) -> list[dict] | 107-263 | — |
| `complete_ticket` | def | (conn, ticket_id) -> None | 266-273 | — |
| `TransientStageHold` | class | RuntimeError subclass | 535-541 | raised by stage code (importers) |
| `transient_backoff_s` | def | (exc: BaseException) -> float | 577-578 | — |
| `LEASE_SECONDS` | const | 300 | 33 | — |
| `CONTRACT_EXEMPT_EVENTS` | const | frozenset({"parent_enrichment.v1", "verify.v1"}) | 81-90 | — |

## contracts

### run_worker — 359-526
- in: `process_event(conn, event)` keeps its existing signature and stage logic (364-365); called at 479.
- pre: if `worker_type == "extract"` and `POLYMATH_EXTRACT_AFFINITY` set, value must be `local` or `cloud`, else `ValueError` (397-402).
- effect: registers worker once (410-417); heartbeats each loop (418); per-loop bundle-drift check against boot fingerprint (393-394, 419-427); claims `batch_size` events (447-449); per-event lease-keeper daemon thread (455-461); pre-stage heartbeat in its own short tx before the long stage tx (471-476).
- post: success ⇒ `process_event` + `complete_ticket` in one tx (477-480) then heartbeat with `processed_count=1` (481-483); `StageFailed`/`Exception` ⇒ transient release (no attempt) or `_fail_ticket` (attempt+1) (488-518).
- out: never returns (`while True` at 407).

### claim_ticket_events — 107-263
- in: `identity` keys used: `worker_type` (131), `worker_id` (191), `contracts` (183); `lane_affinity` ∈ {"local","cloud",None}.
- pre: lane filter built as `EXISTS (… documents d … d.byte_length > %s)` with threshold `effective_threshold(_gs().worker.cloud_min_bytes)` (121-130).
- out: claimed event dicts with payload passed through `normalize_event` (224-226).
- post: leased tickets `status='leased'`, `lease_expires_at = now() + LEASE_SECONDS` (204-211); claimed outbox rows `delivered_at=now()` (248-250); contract-refused event_ids recorded per worker_type, forgotten after `_REFUSED_TTL_S = 900.0` (63, 131, 186-195).
- fail-closed: ticketless events skipped unless `event_type == 'intake.v1'` (158-159, 175-176); `LegacyEventUnrecoverable` ⇒ ticket failed once with typed note, attempt+1 (227-245).
- steal: home lane dry ⇒ recursive global claim, logged `LANE_STEAL_CLAIM` (252-262).

### complete_ticket — 266-273
- post: `ticket_id` falsy ⇒ no-op (267-268); else `status='done'`, lease cleared, `WHERE ticket_id=%s` only — no `status='leased'` guard (269-272).

### _lease_keeper — 289-356
- renews EVERY ticket with `lease_owner = %s AND status = 'leased'` each `interval_s=60.0` (292-295, 319, 348-350), heartbeats with `current_ticket` (351-352).
- past `deadline_s` (default 14400): `attempt+1`, `failed` at cap 3 else `ready`, heartbeat `last_error`, `os._exit(70)` (320-344).

## effect surface
- Postgres read: `documents` (126-127), `outbox_events` (135), `stage_tickets` (139-140), `runs` (141).
- Postgres write: `stage_tickets` (204-211, 229-238, 329-339, 348-350, 606-613, 624-632), `outbox_events.delivered_at` (248-250), `worker_registrations` (quarantine, 437-442).
- Network: direct psycopg connects in keeper thread, `connect_timeout=5` (327, 346).
- Process: `os._exit(70)` (344); faulthandler stack dump on SIGUSR1 (375-378).
- Env: `POLYMATH_STAGE_DEADLINE_S = '14400'` (286, read once at import); `POLYMATH_EXTRACT_AFFINITY = ''` (398, read only when `worker_type == "extract"`, 399).
- Imports from: `polymath_shared.db`, `.execution`, `.logging`, `.receipts` (23-31); `.llm_extraction.policy`, `.settings` (123-124); `.event_adapter` (219-222); `.execution_bundle` (388-392); `.llm_extraction.client` (557); `.clients` (585).

## invariants
INVARIANT: initial lease window `LEASE_SECONDS = 300` (33, 211) vs keeper renewal `ttl_s = _gs().worker.claim_ttl_s` (458-459) — two independent lease lengths [DERIVED]
  fails-if: `claim_ttl_s` ≠ 300 makes renewal disagree with the granted lease; a stage longer than the renewed TTL gets reaped mid-run.
INVARIANT: `_STAGE_DEADLINE_S` default 14400 s (4 h) > documented longest legitimate stage ~2.3 h (284-286) [DERIVED]
  fails-if: deadline below the longest legit stage kills healthy workers via `os._exit(70)` (344).
INVARIANT: retry terminal condition `attempt + 1 >= 3` ⇒ `'failed'` else `'ready'` — duplicated verbatim at 333 and 628 [DERIVED]
  fails-if: the two literals diverge ⇒ keeper deadline path and `_fail_ticket` disagree on retry budget.
INVARIANT: claimable ⇔ `(t.status = 'ready' AND t.archived_at IS NULL) OR (t.ticket_id IS NULL AND e.event_type = 'intake.v1')` (158-159) [DERIVED]
  fails-if: strict gate starves intake uploads; loose gate ran SC-200 stages before extract (comment 144-158).
INVARIANT: transient release sets `status='ready'` with NO attempt increment (606-613) [DERIVED]
  fails-if: capacity 429/503 or booting sidecar counted as failure burns the 3-attempt budget (comment 544-550).
INVARIANT: `_REFUSED_TTL_S = 900.0` s refusal memory per worker_type (63, 67-72) [DERIVED]
  fails-if: too long stalls a lane after a semantic cutover; too short re-starves the scan head (comment 47-59).
INVARIANT: exception cause-chain walk bounded `seen < 8` (559, 568, 588) [DERIVED]
  fails-if: wrapping deeper than 8 hides `TransientStageHold`/`SidecarUnavailable` ⇒ transient treated as real failure.
INVARIANT: `_CAPACITY_BACKOFF_S = 60.0` > `_TRANSIENT_BACKOFF_S = 15.0` (553, 532) [DERIVED]
  fails-if: swapped values hammer a 429-ing provider pool or over-delay a booting sidecar.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.time` 68, `time.monotonic` 318/320; sleeps 491, 509, 526; env 286, 398; DB row races `FOR UPDATE OF e SKIP LOCKED` 168 and lease-race `rowcount == 0` check 213-214)
idempotency: SAFE (claim is conditional `UPDATE … WHERE ticket_id=%s AND status='ready'` plus race check 204-214; failure/deadline transitions guarded `WHERE … status='leased'` 235, 337, 611, 631) — except `complete_ticket`, which is unguarded (269-272)

## failure behaviour
- Swallowed with `pass`: keeper deadline cleanup failure (342-343) — exit proceeds regardless; `_release_ticket_transient` UPDATE failure (615-616) and `_fail_ticket` UPDATE failure (635-636) — caller sees nothing, ticket stays `leased` until the reaper.
- Swallowed with log: keeper renewal retry `lease_renew_failed` (354-356); pre-stage heartbeat `heartbeat_failed` (474-476); worker-loop generic `log.exception` (524-525); `psycopg.errors.OperationalError` backoff `pg_unavailable` (521-523).
- Handled branch: generic stage exception branches on `_is_sidecar_unavailable(exc)` ⇒ transient release + `time.sleep(transient_backoff_s(exc))` (498-509).
- Error codes emitted: `STAGE_DEADLINE_EXCEEDED` (324), `LEGACY_EVENT_UNRECOVERABLE` (241), `LANE_STEAL_CLAIM` (261), `TICKET_TRANSIENT_RELEASE` (603), `BUNDLE_STALE_CODE_DRIFT` (422), `BUNDLE_STALE_SEMANTIC_FILE_DRIFT` (426), `stage_failed` (495).
- Raised: `ValueError` on bad lane affinity (400-402); process exit code 70 on stage deadline (344).

## dumb-code flags
- Retry cap literal `3` duplicated in two SQL strings (333, 628).
- `LEASE_SECONDS = 300` at claim (33, 211) vs `claim_ttl_s` from settings in the keeper (458-459) — nothing ties the two lease durations together [INFERRED — separate sources with no shared constant].
- `extra_env_check` parameter (362) has no call site anywhere in this unit [INFERRED — absent from the body].
- `run_worker` rebinds `log = logging.getLogger(f"worker-{worker_type}")` (382), shadowing the module-level `log` (45) that exists specifically because `_lease_keeper` needs it (36-45).
- `complete_ticket` sets `status='done'` with no `status='leased'` guard (269-272), unlike every other ticket transition.
- `_fail_ticket` SQL duplicated by the keeper's deadline branch (329-339 vs 624-632).
- `POLYMATH_STAGE_DEADLINE_S` read once at module import (286) — env change requires a process restart.
- FACTS.constants records `CONTRACT_EXEMPT_EVENTS` as a list; SOURCE defines it as `frozenset({…})` (81).

## refactor notes
- All 12 FACTS.importers modules call `run_worker` and rely on the `process_event(conn, event)` contract (364-365, 479) — signature changes ripple across the entire fleet.
- Retry-cap `3`, lease durations, and backoff values are inline/duplicated in SQL — extract shared constants before touching retry or lease semantics (333, 628, 211, 459).
- Transient detection walks `__cause__`/`__context__` max depth 8 (556-593) — deeper exception re-wrapping in stages or clients silently breaks it.
- `CONTRACT_EXEMPT_EVENTS` + `_era_exempt` gate cross-era claims (81-104, 181) — adding an exempt event changes provenance fencing for mixed-era corpora.
- `claim_ticket_events` recurses for the lane steal (253-255) — any refactor must keep the steal logged (`LANE_STEAL_CLAIM`, 257-261) per silent-fallback accounting.
- `complete_ticket` unguarded UPDATE (269-272) — adding a status guard changes behaviour for tickets already reaped or re-leased.

## VERIFY
```verify
grep -Fq 'LEASE_SECONDS = 300' shared/polymath_shared/worker_runtime.py
test "$(grep -c -F 'attempt + 1 >= 3' shared/polymath_shared/worker_runtime.py)" -ge 2
grep -Fq 'FOR UPDATE OF e SKIP LOCKED' shared/polymath_shared/worker_runtime.py
grep -Fq 'os._exit(70)' shared/polymath_shared/worker_runtime.py
grep -Eq 'POLYMATH_STAGE_DEADLINE_S., .14400' shared/polymath_shared/worker_runtime.py
! grep -Fq 'extra_env_check()' shared/polymath_shared/worker_runtime.py
grep -Fq 'parent_enrichment.v1' shared/polymath_shared/worker_runtime.py
```
