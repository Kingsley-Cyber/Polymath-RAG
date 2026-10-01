# unit: shared/polymath_shared/receipts.py
anchor: shared/polymath_shared/receipts.py:1-464

## purpose
Single Postgres transaction boundary for durable stage writes: a stage's writes + receipt + `runs` status transition + outbox event commit in ONE transaction (AGENTS.md rule 5, cited in module docstring). Also owns projection claim lifecycle (attempts immutable, claims active/inactive) and outbox claiming for delivery. Consumers re-run the same content-hashed keys, so replays are no-ops. — receipts.py:1-9 [DERIVED]

## public surface

Importers (file-level, from FACTS): `shared/polymath_shared/worker_runtime.py`, `workers/workers/_small-modules`, `canonicalize_worker.py`, `doc_parent_map_stage_worker.py`, `doc_profile_worker.py`, `extract_worker.py`, `intake_worker.py`, `profile_worker.py`, `project_canonical_worker.py`, `project_neo4j_worker.py`, `project_qdrant_worker.py`, `verify_worker.py` — receipts.py (FACTS.importers) [DERIVED]

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `stage_contract_hash` | def | (stage: str, frozen: dict) -> str | receipts.py:27-28 | importers above |
| `StageFailed` | class(RuntimeError) | (run_id: str, stage: str); attrs `.run_id`, `.stage` | receipts.py:31-37 | importers above |
| `stage_transaction` | @contextmanager def | (conn, *, run_id, stage, contract_hash) -> Iterator[_StageWrite] | receipts.py:41-70 | importers above |
| `_StageWrite.artifact` | method | (payload: dict) -> str | receipts.py:153-198 | importers above |
| `_StageWrite.outbox` | method | (event_type: str, payload: dict) -> None | receipts.py:200-210 | importers above |
| `_StageWrite.run_status` | method | (status: str) -> None | receipts.py:222-233 | importers above |
| `record_projection_attempt` | def | (conn, *, projection, entity_kind, entity_id, receipt_hash, contract="", state=None, artifact_hash=None, observed_ref=None, projection_version=None) -> None | receipts.py:241-299 | importers above |
| `supersede_projection_claims` | def | (conn, *, projection, entity_kind=None, entity_ids: list[str]) -> None | receipts.py:302-331 | self (385-439) + importers |
| `mark_projection_failed` | def | (conn, *, projection, entity_kind, entity_id, error, projection_version=None) -> None | receipts.py:334-356 | importers above |
| `projection_manifest_row` | def | (conn, *, projection, entity_kind, entity_id) -> dict \| None | receipts.py:359-377 | importers above |
| `invalidate_corpus_projections` | def | (conn, corpus_id: str) -> int | receipts.py:385-439 | — |
| `claim_events` | def | (conn, event_types: list[str], limit: int) -> list[dict] | receipts.py:442-464 | — |
| `_now` | def | () -> str | receipts.py:23-24 | internal |

## contracts

**stage_transaction** — receipts.py:41-70
- pre: caller supplies open `psycopg` `Connection`, plus `run_id`, `stage`, `contract_hash`.
- out: yields `_StageWrite`; success path RELEASEs savepoint, writes committed receipt, `conn.commit()` (68-70).
- failure: any `BaseException` in the body → `ROLLBACK TO SAVEPOINT stage_work`, RELEASE, `_record_failure(exc)`, `conn.commit()`, then `raise StageFailed(run_id, stage) from exc` (61-66). Caller sees `StageFailed`, never the original exception.
- post: no dangling attempt — attempt row outcome is durably `'failed'` or `'ok'` with a matching `receipts` row.

**_StageWrite.artifact(payload)** — receipts.py:153-198
- in: `payload: dict`.
- out: returns `artifact_id = content_hash({"run": run_id, "stage": stage, "contract": contract_hash, "payload": payload})` (172-177).
- post: row keyed `(run_id, stage, contract_hash)`; repeated calls MERGE via `payload = artifacts.payload || EXCLUDED.payload` (193-194); operational projection columns (migration 0057) derived only from payloads mentioning `llm_extraction`, never from the merge (165-171, 178-188).

**_StageWrite.outbox(event_type, payload)** — receipts.py:200-210
- post: `outbox_events` row with `idempotency_key = content_hash({"run", "type": event_type, "payload"})`, `ON CONFLICT (idempotency_key) DO NOTHING` (202-207).

**_StageWrite.run_status(status)** — receipts.py:220-233
- pre/post: if `status in _PROGRESS_STATUSES` (`{"reconciling"}`), UPDATE only `WHERE ... status IN ('intake', 'reconciling')` (223-229); any other status (verdicts `degraded`, `query_ready`, `failed` per comment 217-218) updates unconditionally (230-233).

**record_projection_attempt** — receipts.py:241-299
- pre: `contract` defaults `""`; lifecycle fields all optional.
- post: immutable row appended to `projection_attempts` (266-272). If `state is None and artifact_hash is None and observed_ref is None and projection_version is None` → LEGACY claim (`active = TRUE`, no migration-0065 columns) (273-283); else extended claim with `active = (st == "PROJECTED")` where `st = state or "PROJECTED"` (284-299).

**invalidate_corpus_projections(conn, corpus_id)** — receipts.py:385-439
- in: corpus whose runs are terminal (`query_ready`).
- out: returns count of re-entered runs; `0` if no documents (398-399).
- post: supersedes claims for projections `("qdrant", "neo4j")` over chunk+summary+canonical+fact ids (413-416); affected runs set `status = 'degraded'` (428-430); `stage_attempts` for `("project_qdrant", "project_neo4j", "project_canonical", "verify_projections")` updated IN PLACE to `outcome = 'skipped'` (425, 431-437) — no synthetic rows, per comment 420-424.

**claim_events** — receipts.py:442-464
- post: returns rows with `delivered_at IS NULL`, `event_type = ANY(%s)`, `ORDER BY event_id LIMIT %s FOR UPDATE SKIP LOCKED`, and marks them `delivered_at = now()` in the same transaction (447-462).

## effect surface

| effect | detail | anchor |
|---|---|---|
| PG read | `documents`, `chunks`, `retrieval_summaries`, `canonical_entities`, `evidence`, `runs`, `outbox_events`, `projection_receipts` (+ FACTS.tables_read) | receipts.py:396-418, 448-454 |
| PG write | `stage_attempts`, `receipts`, `artifacts`, `outbox_events`, `runs`, `projection_attempts`, `projection_receipts` | receipts.py:84, 114-128, 140-148, 191-196, 205-209, 224-232, 268, 276-298, 319-330, 347-354, 428-437, 461 |
| clock | `dt.datetime.now(dt.timezone.utc).isoformat()` in `_now` | receipts.py:24 |
| imports | `polymath_shared.identity` (`attempt_id`, `content_hash`, `receipt_id`); deferred `polymath_shared.extract_projection.extract_projection_columns_for` inside `artifact` | receipts.py:20, 178 |

Note: FACTS.tables_written also lists `"set"` and `"skip"` — SQL keyword artifacts of the analyzer (`SET`, `SKIP LOCKED`), not tables. [INFERRED]

## invariants

INVARIANT: stage durable writes + receipt + status transition + outbox event commit in one transaction — receipts.py:48-55, 60-70 [DERIVED]
  fails-if: partial commits leave dangling attempts / undeliverable events.
INVARIANT: `stage_attempts` key = `(run_id, stage, contract_hash)`; insert uses `ON CONFLICT ... DO NOTHING` — receipts.py:84-86 [DERIVED]
  fails-if: retry of the same contract would error or duplicate attempt rows.
INVARIANT: `_describe` output length ≤ 2000 (`[:2000]`) and is cycle-safe (`seen` set of `id(cur)`) — receipts.py:100-106 [DERIVED]
  fails-if: unbounded error strings or infinite loop on exception cycles.
INVARIANT: outbox `idempotency_key` = `content_hash({"run", "type", "payload"})`, conflict → `DO NOTHING` — receipts.py:202-207 [DERIVED]
  fails-if: redelivery would duplicate events.
INVARIANT: `_PROGRESS_STATUSES == frozenset({"reconciling"})`; progress writes only over `'intake'`/`'reconciling'` — receipts.py:220-229 [DERIVED]
  fails-if: a late stage could overwrite a verdict (`degraded`/`query_ready`/`failed`) — the STATUS-MONOTONE-V1 bug (comment 212-218).
INVARIANT: legacy claim path requires `state`, `artifact_hash`, `observed_ref`, `projection_version` ALL `None` — receipts.py:273 [DERIVED]
  fails-if: mixed callers write extended columns before migration 0065 exists.
INVARIANT: extended claim `active` is TRUE iff `state == "PROJECTED"` — receipts.py:284, 297 [DERIVED]
  fails-if: non-PROJECTED states (e.g. FAILED) would be believed present in the store.
INVARIANT: `mark_projection_failed` truncates error to 500 chars (`str(error)[:500]`), writes `receipt_hash = ''`, preserves prior `projection_version` via COALESCE — receipts.py:349-355 [DERIVED]
  fails-if: long errors overflow column; version history lost.
INVARIANT: `invalidate_corpus_projections` supersedes exactly projections `("qdrant", "neo4j")` and re-drives stages `("project_qdrant", "project_neo4j", "project_canonical", "verify_projections")` — receipts.py:414, 425-426 [DERIVED]
  fails-if: a new projection store added without editing both tuples is silently not reconstructed.
INVARIANT: `claim_events` only returns rows with `delivered_at IS NULL` under `FOR UPDATE SKIP LOCKED` — receipts.py:450-454 [DERIVED]
  fails-if: concurrent consumers deliver the same event twice.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `dt.datetime.now` at receipts.py:24; DB-dependent reads and `FOR UPDATE SKIP LOCKED` batch contents depend on concurrency at receipts.py:447-458) [DERIVED]
idempotency: SAFE — content-hash keys everywhere: `stage_attempts` DO NOTHING (86), `receipts` DO UPDATE (124-125, 143-144), `artifacts` jsonb merge (193-194), `outbox_events` idempotency-key DO NOTHING (207), projection claims upsert on `(projection, entity_kind, entity_id)` (278-279, 291-295) [DERIVED]

## failure behaviour
- `except BaseException` at receipts.py:61 (FACTS.fallbacks: "handled: expr, expr, expr, expr, raise"): body writes rolled back to savepoint, failure receipt + attempt committed, then re-raised as `StageFailed(run_id, stage) from exc` — nothing is swallowed; caller sees `StageFailed` (a `RuntimeError`) with `.run_id`/`.stage`. [DERIVED]
- `_record_failure` runs after rollback-to-savepoint so its transaction is clean and committable (108-110).
- `StageFailed` is the only custom exception; no error codes, no retries here. [DERIVED]

## dumb-code flags
- Optimistic `'ok'`: `_begin_attempt` inserts `outcome = 'ok'` before any work is done (85); a crash between insert and `_record_failure` leaves a false `'ok'` attempt unless the transaction aborts. [INFERRED — depends on the outer transaction also rolling back]
- Two different error-truncation limits: `[:2000]` in `_describe` (106) vs `[:500]` in `mark_projection_failed` (355). [DERIVED]
- Stage-name tuple duplicated in `invalidate_corpus_projections` (425-426) — duplicates knowledge of the worker stage names also embedded in importers' filenames. [DERIVED]
- Deferred import `from polymath_shared.extract_projection import extract_projection_columns_for` executed on every `artifact()` call (178). [DERIVED]
- Ordering coupling in `artifact()`: narrow operational columns are set only when the payload mentions `llm_extraction`, because `extract_worker.py` writes that key in a later call than its first `{"manifest": ...}` write (165-171). [DERIVED]
- FACTS `tables_written` entries `"set"` and `"skip"` are analyzer noise, not tables. [INFERRED — parsed from SQL keywords `SET`/`SKIP`]

## refactor notes
- Blast radius: 13 importer modules (FACTS.importers) — any signature change to `stage_transaction`, `_StageWrite` methods, or the projection functions touches every chain worker.
- `record_projection_attempt`'s legacy/extended branch keys on the all-`None` check at receipts.py:273; adding a lifecycle field must extend that check or legacy callers start touching migration-0065 columns. [DERIVED]
- `run_status` progress gate: the guard list `('intake', 'reconciling')` (226) must grow if `_PROGRESS_STATUSES` grows. [DERIVED]
- `invalidate_corpus_projections` updates `stage_attempts` in place (`outcome = 'skipped'`, 433-436) because the census reads the latest-started attempt per stage (420-424); switching to synthetic rows re-introduces endless re-drive. [DERIVED]
- `artifact()` merge semantics (`||`, last-write-wins per key, 193-194) is the fix for I4R-A provenance loss (159-163); changing to DO NOTHING drops audit/syntax/rescue evidence. [DERIVED]

## VERIFY
```verify
grep -Fq 'SAVEPOINT stage_work' shared/polymath_shared/receipts.py
grep -Fq 'raise StageFailed(run_id, stage) from exc' shared/polymath_shared/receipts.py
grep -Fq '_PROGRESS_STATUSES = frozenset({"reconciling"})' shared/polymath_shared/receipts.py
grep -Fq 'payload = artifacts.payload || EXCLUDED.payload' shared/polymath_shared/receipts.py
grep -Fq 'FOR UPDATE SKIP LOCKED' shared/polymath_shared/receipts.py
test "$(grep -c -F 'DO NOTHING' shared/polymath_shared/receipts.py)" -ge 2
```
