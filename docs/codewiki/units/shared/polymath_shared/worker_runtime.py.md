# unit: shared/polymath_shared/worker_runtime.py
anchor: shared/polymath_shared/worker_runtime.py:1-632

## purpose
CONTROL-PLANE-V2 worker runtime (ADR-0014): one generic loop for every worker type in the fleet — register identity, heartbeat, claim only ticket-gated events that are `ready` and compatible with the run's pinned execution contract, execute, complete the ticket. Workers are dumb executors; the control plane owns sequencing. — shared/polymath_shared/worker_runtime.py:1-12 [DERIVED]

Used by 12 worker modules (FACTS.importers): intake, extract, profile, canonicalize, doc_profile, doc_parent_map_stage, summary_impl, project_canonical, project_neo4j, project_qdrant, verify, `_small-modules` — FACTS.importers [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| run_worker | def | (worker_type: str, event_types: list[str], process_event: Callable[..., None], poll_interval_s: float = 2.0, batch_size: int = 1, extra_env_check: Callable[[], None] \| None = None) -> None | 359-362 | worker entry scripts [INFERRED: importers import the module; per-symbol split not in FACTS] |
| claim_ticket_events | def | (conn, identity: dict, event_types: list[str], limit: int, lane_affinity: str \| None = None) -> list[dict] | 107-108 | run_worker + workers [INFERRED: same reason] |
| complete_ticket | def | (conn, ticket_id: str \| None) -> None | 266-268 | run_worker + workers [INFERRED] |
| transient_backoff_s | def | (exc: BaseException) -> float | 573-574 | run_worker (491, 509) |
| TransientStageHold | class | RuntimeError subclass; stage raises to yield ticket | 535-541 | stage workers raise it [INFERRED] |
| _refused_set / _era_exempt / _lease_keeper / _is_provider_capacity / _is_transient_hold / _is_sidecar_unavailable / _release_ticket_transient / _fail_ticket | def | internal | 67-72, 93-104, 289-291, 552-560, 563-570, 577-589, 592-612, 615-632 | — |

## contracts

**run_worker** (359-526)
- pre: `process_event(conn, event)` keeps its existing signature and stage logic — 363-365 [DERIVED]
- pre: `POLYMATH_EXTRACT_AFFINITY` honored only when `worker_type == "extract"`; must be `"local"` or `"cloud"`, else `ValueError` — 396-402 [DERIVED]
- in: `register_worker(conn, identity)` once per process, then `heartbeat` every loop tick — 410-418 [DERIVED]
- in: bundle fence — pins `fast_code_fingerprint()` + `semantic_file_hashes()` at boot; drift sets `bundle_stale_reason` (`BUNDLE_STALE_CODE_DRIFT` / `BUNDLE_STALE_SEMANTIC_FILE_DRIFT`), writes `worker_registrations.status = 'quarantined'`, refuses all claims — 383-394, 419-446 [DERIVED]
- post success: one tx runs `process_event` + `complete_ticket`, then heartbeat with `current_ticket=None, processed_count=1`, log `"ticket processed"` — 477-487 [DERIVED]
- post failure: `StageFailed` or generic `Exception` → if `_is_sidecar_unavailable(exc)`: `_release_ticket_transient` + `time.sleep(transient_backoff_s(exc))`; else `_fail_ticket` — 488-518 [DERIVED]
- out: never returns (`while True` at 407); the only process exit is `os._exit(70)` from the keeper thread — 344 [DERIVED]

**claim_ticket_events** (107-263)
- in: SELECT undelivered `outbox_events` of the given types, joined to `stage_tickets` and `runs`, gate `((t.status = 'ready' AND t.archived_at IS NULL) OR (t.ticket_id IS NULL AND e.event_type = 'intake.v1'))` — fail-closed for every non-intake event — 158-159, 175-176 [DERIVED]
- pre: non-era-exempt events with a non-empty contract require `compatible(identity["contracts"], contract)`; refusals are remembered per worker_type for `_REFUSED_TTL_S = 900.0` s so the scan advances — 180-195, 63 [DERIVED]
- out: claim = `UPDATE stage_tickets SET status='leased', lease_owner=%s, lease_expires_at = now() + make_interval(secs => %s)` with `LEASE_SECONDS` = 300, `WHERE ... status='ready'`; `rowcount == 0` → skip (lost race) — 204-214, 33 [DERIVED]
- post: claimed events get `outbox_events.delivered_at=now()` — 248-250 [DERIVED]
- post: `LegacyEventUnrecoverable` during `normalize_event` → ticket set `status='failed', attempt = attempt + 1`, event NOT returned — 228-245 [DERIVED]
- lane: affinity pass filters runs by `EXISTS (... d.byte_length > threshold)` with `threshold = effective_threshold(_gs().worker.cloud_min_bytes)`; empty home lane → recursive global steal, logged `LANE_STEAL_CLAIM` — 121-130, 252-262 [DERIVED]

**complete_ticket** (266-273)
- no-op when `ticket_id` falsy; otherwise `status='done'`, lease cleared — 267-272 [DERIVED]
- no `AND status='leased'` guard, unlike every other ticket UPDATE in this file — 269-272 [DERIVED]

**_lease_keeper** (289-356, daemon thread)
- renews ALL tickets `WHERE lease_owner = %s AND status = 'leased'` every `interval_s = 60.0`, plus heartbeat — 292-295, 348-352 [DERIVED]
- deadline defaults to `_STAGE_DEADLINE_S` from env `POLYMATH_STAGE_DEADLINE_S` = `"14400"` — 286, 316-317 [DERIVED]
- post on exceed: `attempt + 1`, `'failed'` if `attempt + 1 >= 3` else `'ready'`, `heartbeat(last_error=...)`, `os._exit(70)` — 320-344 [DERIVED]

**transient classification** (535-632)
- `_is_sidecar_unavailable` = `SidecarUnavailable` in ≤8-deep `__cause__`/`__context__` chain, OR `_is_provider_capacity`, OR `_is_transient_hold` — 577-589 [DERIVED]
- `_is_provider_capacity`: `ExtractionTransportError` whose str contains one of `("HTTP 429", "429 Too Many Requests", "lane refused", "LIMITER_REFUSED")` — 548, 552-560 [DERIVED]
- `transient_backoff_s` returns `_CAPACITY_BACKOFF_S` 60.0 for capacity, else `_TRANSIENT_BACKOFF_S` 15.0 — 532, 549, 573-574 [DERIVED]
- `_release_ticket_transient`: back to `status='ready'`, lease cleared, NO attempt change, only `WHERE ... status='leased'` — 604-609 [DERIVED]
- `_fail_ticket`: `attempt + 1`, `CASE WHEN attempt + 1 >= 3 THEN 'failed' ELSE 'ready' END`, only `WHERE ... status='leased'` — 621-628 [DERIVED]

## effect surface
- Postgres read: `outbox_events` (SELECT 134-168), `stage_tickets` (join 139-140), `runs` (join 141, `r.execution_contract` 137), `documents` (EXISTS lane check 126-127) — [DERIVED]
- Postgres written: `stage_tickets` (lease 204-212, done 269-272, deadline-fail 331-339, transient release 603-609, fail 621-628), `outbox_events.delivered_at` (249), `worker_registrations` (`last_error`, `status = 'quarantined'` 437-442) — [DERIVED]
- FACTS.tables_written also lists `of` — artifact of parsing `FOR UPDATE OF e` (168) [INFERRED: that literal is the only `of` in the SQL]
- Own Postgres connections per keeper tick: `_psycopg.connect(dsn, connect_timeout=5)` — 327, 347 [DERIVED]
- env: `POLYMATH_STAGE_DEADLINE_S` = `'14400'` (286); `POLYMATH_EXTRACT_AFFINITY` = `''` (398) — [DERIVED]
- process/signals: faulthandler dump on SIGUSR1, all threads (375-378); `os._exit(70)` (344) — [DERIVED]
- no files written, no Qdrant/Neo4j calls in this unit — absence across 1-632 [DERIVED]

## invariants
INVARIANT: LEASE_SECONDS = 300 — 33; initial lease window at claim — 207 [DERIVED]
  fails-if: renewal uses `settings.worker.claim_ttl_s` (459), a different source for the same lease; a settings value < stage duration lets the reaper revoke a healthy worker (documented CP2.1 failure, 298-304)
INVARIANT: retry cap identical at both fail sites: `attempt + 1 >= 3 THEN 'failed'` — 333, 624 [DERIVED]
  fails-if: changing one site gives deadline-failed and stage-failed tickets different retry budgets
INVARIANT: transient release never increments `attempt` (no attempt column in 604-609) while `_fail_ticket` always does (623) [DERIVED]
  fails-if: a booting sidecar would burn the 3-attempt budget (documented: 3 attempts in 8 s, 529-531)
INVARIANT: `_REFUSED_TTL_S` = 900.0 s refusal memory (63) and claim recency window `interval '15 minutes'` = 900 s (162) are equal but unlinked literals [DERIVED]
  fails-if: retuning one without the other makes refused-head skipping and new-run priority disagree
INVARIANT: only `intake.v1` may claim with `t.ticket_id IS NULL`; every other ticketless event is skipped — 158-159, 175-176 [DERIVED]
  fails-if: legacy harness events become permanently unclaimable (documented SC-200, TICKET-GATE-FAIL-CLOSED-V1 144-157)
INVARIANT: exception-chain walk depth ≤ 8 at all three classifiers — 555, 565, 583 [DERIVED]
  fails-if: a transient wrapped deeper than 8 is misclassified as a real failure and burns an attempt
INVARIANT: `batch_size` default 1; parallelism comes from multiple worker processes — 361, 367-371 [DERIVED]
  fails-if: batching >1 resurrects queued-ticket lease expiry (LONG-STAGE-LEASE-CORRECTNESS-V1, 197-203)
INVARIANT: era exemption set = frozenset `{"parent_enrichment.v1", "verify.v1"}` plus `project_qdrant.v1` events with `payload["reason"] == "latent_projection"` — 81-90, 101-103 [DERIVED]
  fails-if: era-refusing verify.v1 leaves old corpora stuck in reconciling (documented 2026-08-31, 83-89)

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.time` 68, `time.monotonic` 318/320; db: SELECT/UPDATE on 4 tables 134-250; concurrency: `FOR UPDATE OF e SKIP LOCKED` 168 + rowcount race 213-214; env: 286, 398; process: `os._exit(70)` 344; signal: SIGUSR1 377-378) [DERIVED]
idempotency: SAFE for leasing (guarded `WHERE status='ready'` + rowcount check, 204-214); UNSAFE for `complete_ticket` replay (no status guard, 269-272) and for `delivered_at=now()` (blind overwrite, 249) [DERIVED]

## failure behaviour
- `Exception` → `pass` in `_release_ticket_transient` (611-612): transient release silently lost; ticket stays `leased` until TTL/reaper; loop continues [DERIVED]
- `Exception` → `pass` in `_fail_ticket` (631-632): failure not recorded, attempt not burned; ticket returns via lease expiry [DERIVED]
- `Exception` → `pass` in the deadline branch (342-343): DB write skipped, but `os._exit(70)` still runs — 344 [DERIVED]
- `Exception` → log `lease_renew_failed`, retried next 60 s tick — 354-356 [DERIVED]
- `Exception` → log `heartbeat_failed`, stage still executes — 471-476 [DERIVED]
- `psycopg.errors.OperationalError` → log `pg_unavailable`, back off `poll_interval_s`; any other loop exception → `log.exception`, loop continues — 521-526 [DERIVED]
- generic `Exception` from the stage handled by branch at 498-518: sidecar-unavailable → transient release + backoff; else `_fail_ticket` [DERIVED]
- `LegacyEventUnrecoverable` → ticket failed once with typed note, event skipped — 227-245 [DERIVED]
- error codes emitted: `LEGACY_EVENT_UNRECOVERABLE` (241), `LANE_STEAL_CLAIM` (261), `STAGE_DEADLINE_EXCEEDED` (324), `BUNDLE_STALE_CODE_DRIFT` (422), `BUNDLE_STALE_SEMANTIC_FILE_DRIFT` (426), `lease_renew_failed` (355), `heartbeat_failed` (476), `pg_unavailable` (523), `stage_failed` (493-496), `TICKET_TRANSIENT_RELEASE` (599) [DERIVED]

## dumb-code flags
- `bundle_id` imported with the fence helpers but never used — 388-392 [DERIVED]
- `extra_env_check` parameter declared, never called anywhere in 359-526 — 361 [DERIVED]
- lease length set from constant `LEASE_SECONDS` = 300 at claim (211) but renewed with `settings.worker.claim_ttl_s` (459) — two sources for one lease [DERIVED both; divergence risk INFERRED]
- retry cap `3` duplicated (333, 624); reason truncation `[:500]` at 235, 338, 508, 609, 629 and `[:200]` at 244; chain cap `8` ×3 (555, 565, 583) [DERIVED]
- `complete_ticket` lacks the `AND status='leased'` guard used by 204-214, 337, 607, 627 — 269-272 [DERIVED]
- module logger `log = logging.getLogger("worker-runtime")` (45) shadowed by local `log` in `run_worker` (382); `claim_ticket_events` builds `logging.getLogger("worker-runtime")` inline 3× (189, 239, 257) — the exact shadowing class that caused the documented keeper NameError (37-44) [DERIVED]
- `_lease_keeper(deadline_s=...)` never receives a deadline from its only call site — always the env default — 290, 456-460 [DERIVED]
- mangled whitespace on the latent-projection check line — 103 [DERIVED]
- FACTS render `CONTRACT_EXEMPT_EVENTS` and `_CAPACITY_MARKERS` as lists; the code has a `frozenset` (81) and a tuple (548) [DERIVED]

## refactor notes
- 12 worker modules import this module (FACTS.importers); any change to `run_worker`'s signature or the `process_event(conn, event)` contract touches all of them — FACTS.importers, 363-365 [DERIVED]
- ticket state literals `'ready'`/`'leased'`/`'done'`/`'failed'` are inline SQL in five UPDATEs plus the claim gate (158-159, 204-212, 269-272, 331-339, 603-609, 621-628); reaper and lease semantics referenced at 197-203 and 308-313 depend on them [DERIVED]
- `claim_ticket_events` recurses without `lane_affinity` for the steal pass (255) — the function must stay callable with the affinity parameter defaulted [DERIVED]
- lazy imports inside functions: `effective_threshold`/`get_settings` (123-124), `normalize_event` (219-222), `ExtractionTransportError` (553), `SidecarUnavailable` (581), `get_settings`/`threading` (452-454) — moving those modules changes runtime, not import-time, failure modes [DERIVED]
- any logging refactor around `_lease_keeper` must use the module-level `log`; the local `log` in `run_worker` does not exist in the keeper thread (regression documented 37-44) [DERIVED]
- the `_lease_keeper` args tuple at 456-460 is the sole call site; its params (`ttl_s`, `deadline_s`) are effectively pinned to settings/env defaults [DERIVED]

## VERIFY
```verify
grep -Fq 'LEASE_SECONDS = 300' shared/polymath_shared/worker_runtime.py
grep -Fq 'attempt + 1 >= 3' shared/polymath_shared/worker_runtime.py
grep -Fq 'FOR UPDATE OF e SKIP LOCKED' shared/polymath_shared/worker_runtime.py
grep -Fq 'os._exit(70)' shared/polymath_shared/worker_runtime.py
grep -Fq '"POLYMATH_STAGE_DEADLINE_S", "14400"' shared/polymath_shared/worker_runtime.py
grep -Fq 'TransientStageHold(RuntimeError)' shared/polymath_shared/worker_runtime.py
! grep -Fq 'extra_env_check(' shared/polymath_shared/worker_runtime.py
test "$(grep -c -F 'logging.getLogger' shared/polymath_shared/worker_runtime.py)" -ge 5
```
