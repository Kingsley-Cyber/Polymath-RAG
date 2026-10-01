# unit: control/control/_small-modules
anchor: control/control/__init__.py:1-2

## purpose
Control-plane support modules for the Polymath orchestrator: single-controller lease + append-only liveness evidence (`heartbeat.py:1-7`), evaluation snapshot barrier against reconciling corpora (`snapshots.py:1-7`), worker fleet supervision (`worker_supervisor.py:1-7`), a sidecar-supervisor stub (`supervisor.py:1-7`), and validation-only Pydantic models (`contracts.py:1`). Package docstring defers the process-role contract to AGENTS.md (`control/control/__init__.py:1`). Sole known importer: `control/control/main.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Heartbeat | class | BaseModel: control_id str, occurred_at str, last_tick_ok bool, last_census_size int | contracts.py:7-11 | main.py* |
| CorpusCensus | class | BaseModel: corpus_id str, desired int, observed int, missing list[str] | contracts.py:14-18 | main.py* |
| CensusReport | class | BaseModel: corpora list[CorpusCensus], generated_at str | contracts.py:21-23 | main.py* |
| acquire_lease | def | (conn, *, lease_ttl_s: int) -> tuple[bool, str] | heartbeat.py:42-93 | main.py* |
| renew_lease | def | (conn, owner, *, lease_ttl_s: int) -> bool | heartbeat.py:96-108 | main.py* |
| record_heartbeat | def | (conn, owner, *, tick_ok: bool, census_size: int) -> None | heartbeat.py:111-118 | main.py* |
| corpus_state_hash | def | (conn, corpus_id: str) -> str | snapshots.py:15-38 | acquire/validate_snapshot; main.py* |
| acquire_snapshot | def | (conn, corpus_id: str, require_query_ready: bool = True) -> str | snapshots.py:41-70 | main.py* |
| validate_snapshot | def | (conn, snapshot_id: str) -> None | snapshots.py:73-100 | main.py* |
| supervise_sidecars | async def | () -> None | supervisor.py:18-26 | — (raises NotImplementedError) |
| mark_stale_workers | def | (conn) -> list[str] | worker_supervisor.py:15-25 | sweep (worker_supervisor.py:73) |
| revoke_leases_for | def | (conn, worker_id: str) -> int | worker_supervisor.py:28-37 | sweep (worker_supervisor.py:74) |
| fleet_status | def | (conn) -> dict | worker_supervisor.py:40-52 | main.py* |
| prune_dead_registrations | def | (conn, retention_s: int = REGISTRATION_RETENTION_S) -> int | worker_supervisor.py:63-68 | sweep (worker_supervisor.py:75) |
| sweep | def | (conn) -> dict | worker_supervisor.py:71-76 | main.py* |
| ROLE | const | = "control" | heartbeat.py:17 | acquire_lease (heartbeat.py:49) |
| _hostname | def | () -> str | heartbeat.py:20-21 | acquire_lease only (heartbeat.py:48) |

\* FACTS.importers lists only `control/control/main.py` at unit level; per-symbol call sites not recorded.

## contracts

**acquire_lease** — heartbeat.py:42-93
- in: `conn`; keyword-only `lease_ttl_s: int`
- out: `(True, oid)` on fresh insert (heartbeat.py:76-77) or when already held — expiry extended (heartbeat.py:82-92); `(False, oid)` otherwise (heartbeat.py:93)
- pre: oid built once per process from `_hostname()`, `ROLE`, `_PROCESS_STARTED` (heartbeat.py:48-49)
- post: expired `control:primary` lease DELETEd before insert attempt (heartbeat.py:61-67); `control_owners` upserted with `last_seen_at = now()` (heartbeat.py:53-60)

**renew_lease** — heartbeat.py:96-108
- out: `True` iff UPDATE matched `lease_key = 'control:primary' AND owner_id = owner` (heartbeat.py:102-108)
- side: refreshes `control_owners.last_seen_at` first, unconditionally (heartbeat.py:97-99)

**record_heartbeat** — appends `(control_id, now(), tick_ok, census_size)` to `control_heartbeats`; returns None (heartbeat.py:111-118).

**corpus_state_hash** — digest over ordered parts: runs `(run_id, status, execution_contract::text)` (snapshots.py:20-24), stage_tickets `(stage, status, COUNT(*))` (snapshots.py:25-29), counts `docs/chunks/facts/mentions` (snapshots.py:30-37) -> `content_hash` (snapshots.py:38).

**acquire_snapshot** — snapshots.py:41-70
- pre (require_query_ready=True): `COUNT(runs.status != 'query_ready') == 0` AND `COUNT(stage_tickets.status != 'done') == 0`, else RuntimeError (snapshots.py:45-58)
- out: `"snap_" + content_hash({"c": corpus_id, "h": state})[:24]` (snapshots.py:60)
- post: upsert sets `valid = TRUE, invalidated_at = NULL, invalid_reason = NULL`, `generation = 1` (snapshots.py:63-68)

**validate_snapshot** — raises RuntimeError on: unknown snapshot_id (snapshots.py:81); invalidated snapshot with `invalid_reason` (snapshots.py:83-84); live hash != frozen hash (snapshots.py:86-99). Drift invalidation committed in its own transaction via `polymath_shared.db.tx` (snapshots.py:89-96).

**mark_stale_workers** — `status='healthy'` -> `'stale'` where `heartbeat_at < now() - make_interval(secs => STALE_AFTER_S)`; returns worker_ids (worker_supervisor.py:17-25).

**revoke_leases_for** — rows with `lease_owner=worker AND status='leased'` -> `status='ready', lease_owner=NULL, lease_expires_at=NULL, updated_at=now()`; returns rowcount or 0 (worker_supervisor.py:30-37).

**fleet_status** — returns `{"fleet": {"<worker_type>/<status>": count}, "summary": {"healthy", "stale", "quarantined"}}` (worker_supervisor.py:41-51).

**prune_dead_registrations** — DELETE `worker_registrations` where `heartbeat_at < now() - make_interval(secs => retention_s)`, default `24 * 3600`; returns rowcount or 0 (worker_supervisor.py:60-68).

**sweep** — one pass: mark stale -> revoke their leases (summed) -> prune dead; returns `{"stale": [...], "revoked_leases": n, "pruned_registrations": n}` (worker_supervisor.py:71-76).

## effect surface
- Postgres read: `runs` (snapshots.py:21), `stage_tickets` (snapshots.py:26, 51; worker_supervisor.py:31), `documents` (snapshots.py:31), `chunks` (snapshots.py:32), `facts`+`evidence` (snapshots.py:33), `mentions` (snapshots.py:34), `control_leases` (heartbeat.py:80), `corpus_snapshots` (snapshots.py:77), `worker_registrations` (worker_supervisor.py:19, 42, 61, 66)
- Postgres write: `control_owners` (heartbeat.py:55-59), `control_leases` (heartbeat.py:63-66, 70-75, 86-90, 102-105), `control_heartbeats` (heartbeat.py:113-117), `corpus_snapshots` (snapshots.py:63-68, 92-95), `stage_tickets` (worker_supervisor.py:31-33), `worker_registrations` (worker_supervisor.py:18-21, 64-66)
- Qdrant: none.
- Files: watches `sidecars/*.toml` per docstring — stub only (supervisor.py:19).
- Network: `GET /ready` per docstring, `httpx` imported — stub only (supervisor.py:12, 21).
- Subprocess: `systemctl restart <unit>` per docstring — stub only (supervisor.py:4-5, 24).
- Env flags: none read in SOURCE.

## invariants
INVARIANT: oid at acquire == stored `owner_id` of held lease — heartbeat.py:49, 82 [DERIVED]
  fails-if: recomputing owner id per call → controller can never re-acquire its own lease (documented regression, heartbeat.py:25-38)
INVARIANT: lease expiry = now + `lease_ttl_s` seconds on both paths — heartbeat.py:51 (Python) and heartbeat.py:103 (SQL interval) [DERIVED]
  fails-if: unit/clock mismatch between host and DB → premature expiry or immortal lease
INVARIANT: snapshot refused unless non-query_ready runs == 0 AND open tickets == 0 — snapshots.py:54-58 [DERIVED]
  fails-if: evaluation runs on a reconciling/degraded corpus ("retrieval 0/30" class, snapshots.py:3-5)
INVARIANT: live `corpus_state_hash` == frozen `state_hash` for the whole evaluation — snapshots.py:85-89 [DERIVED]
  fails-if: RuntimeError abort; snapshot marked invalid in a separate committed tx (snapshots.py:90-96)
INVARIANT: revoke_leases_for touches only `status='leased' AND lease_owner=%s` rows — worker_supervisor.py:32-33 [DERIVED]
  fails-if: resetting done/ready tickets re-executes completed stages
INVARIANT: `REGISTRATION_RETENTION_S = 24 * 3600` (86400 s forensics window) — worker_supervisor.py:55-60 [DERIVED]
  fails-if: too small deletes paused-but-live workers; too large repeats the 3,145-dead-registrations incident (worker_supervisor.py:55-59)
INVARIANT: sweep order = mark stale -> revoke -> prune — worker_supervisor.py:73-75 [DERIVED]
  fails-if: prune-first deletes registrations whose tickets are still `'leased'` → orphaned leases

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `dt.datetime.now` at heartbeat.py:39 and heartbeat.py:50; SQL `now()` throughout heartbeat.py:56, 66, 71, 87, 99, 103, 116, snapshots.py:47, 52, 93, worker_supervisor.py:20, 33, 65; digest depends on db state). `content_hash` labeled deterministic for fixed inputs — snapshots.py:16 [DERIVED].
idempotency: SAFE for acquire_lease (upsert + `ON CONFLICT DO NOTHING` + self-extend, heartbeat.py:53-92), acquire_snapshot (conflict re-validates, snapshots.py:65-66), sweep (mark/revoke converge on state predicates, prune bounded by 24h threshold). UNSAFE for record_heartbeat — append-only row per call (heartbeat.py:113-117).

## failure behaviour
No try/except in this unit; nothing is swallowed [DERIVED from SOURCE].
- RuntimeError: snapshot barrier refusal (snapshots.py:55-58); unknown snapshot (snapshots.py:81); invalidated snapshot (snapshots.py:84); state-drift abort (snapshots.py:97-99).
- NotImplementedError: `supervise_sidecars` (supervisor.py:26).
- acquire_lease does not raise on contention — returns `(False, oid)` (heartbeat.py:93).

## dumb-code flags
- `'control:primary'` literal repeated 5x with no named constant — heartbeat.py:64, 71, 81, 88, 104.
- Two expiry mechanisms: Python `now + dt.timedelta(seconds=lease_ttl_s)` (heartbeat.py:50-51) vs SQL `now() + (%s || ' seconds')::interval` (heartbeat.py:103) — host clock vs DB clock [INFERRED: skew risk].
- `generation` hardcoded `1` in snapshot INSERT — snapshots.py:64.
- `asyncio` (supervisor.py:9) and `httpx` (supervisor.py:12) imported but body is `raise NotImplementedError` — dead imports.
- `rows.rowcount or 0` — rowcount is already an int; `or 0` only fires on None — worker_supervisor.py:37, 68 [INFERRED: defensive].
- FACTS.tables_written lists `set` — no table named `set` appears in any SOURCE SQL [INFERRED: parser artifact from `SET` clauses].
- Comment-only values: `tick_interval_s=10`, `lease_ttl_s=30`, "two of every three ticks were no-ops" — heartbeat.py:34-38.

## refactor notes
- Owner-id stability is the fix for the documented regression; any change that recomputes the oid per call reverts it. Blast radius: `control/control/main.py` (sole importer, FACTS.importers) — heartbeat.py:25-49.
- The drift-invalidation UPDATE must stay in its own committed transaction; the caller's tx may roll back with the raise — snapshots.py:87-96.
- `'control:primary'` must change in all 5 sites together — heartbeat.py:64, 71, 81, 88, 104.
- `'leased' -> 'ready'` transition must match the stage-ticket state machine owned elsewhere — worker_supervisor.py:31-33.
- snapshot_id format `"snap_" + hash[:24]` and `generation` value are persisted; changing them orphans existing `corpus_snapshots` rows — snapshots.py:60-64.
- sweep ordering (mark -> revoke -> prune) must be preserved — worker_supervisor.py:73-75.
- Implementing `supervise_sidecars` must honor the docstring contract: `sidecars/*.toml`, `GET /ready`, `systemctl restart <unit>` after N consecutive failures — supervisor.py:18-25.

## VERIFY
```verify
grep -Fq 'control:primary' control/control/heartbeat.py
test "$(grep -c -F 'control:primary' control/control/heartbeat.py)" -ge 5
grep -Fq 'ROLE = "control"' control/control/heartbeat.py
grep -Fq 'ON CONFLICT (lease_key) DO NOTHING' control/control/heartbeat.py
grep -Fq 'raise NotImplementedError' control/control/supervisor.py
grep -Fq 'REGISTRATION_RETENTION_S = 24 * 3600' control/control/worker_supervisor.py
grep -Fq 'state drift during evaluation' control/control/snapshots.py
```
