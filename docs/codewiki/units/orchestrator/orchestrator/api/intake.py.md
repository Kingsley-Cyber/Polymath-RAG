# unit: orchestrator/orchestrator/api/intake.py
anchor: orchestrator/orchestrator/api/intake.py:1-162

## purpose
FastAPI router with three endpoints: `POST /intake` (transactional intake boundary — one Postgres transaction writes a run row plus an `intake.v1` outbox event and returns `run_id` immediately), `GET /runs/{run_id}` (run + stage attempts), `GET /status` (DOCUMENT-STATUS-V1 one-read aggregate for agents). — orchestrator/orchestrator/api/intake.py:1-12 [DERIVED], orchestrator/orchestrator/api/intake.py:83-88 [DERIVED]
All writes are delegated to `polymath_shared.intake_submission` (shared with the I1 manifest producer); this module only reads. — orchestrator/orchestrator/api/intake.py:8-9 [DERIVED]
Router mounted by `orchestrator/orchestrator/main.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `intake` | route handler, `POST /intake` | `async def intake(req: IntakeRequest) -> IntakeResponse` | orchestrator/orchestrator/api/intake.py:33-47 | orchestrator/orchestrator/main.py |
| `run_status` | route handler, `GET /runs/{run_id}` | `async def run_status(run_id: str) -> dict` | orchestrator/orchestrator/api/intake.py:50-77 | orchestrator/orchestrator/main.py |
| `pipeline_status` | route handler, `GET /status` | `async def pipeline_status(corpus_id: str, source_name: str \| None = None, run_id: str \| None = None) -> dict` | orchestrator/orchestrator/api/intake.py:80-162 | orchestrator/orchestrator/main.py |
| `IntakeResponse` | pydantic model | `run_id: str; accepted: bool; already_exists: bool = False` | orchestrator/orchestrator/api/intake.py:27-30 | `response_model` of `intake` (:33) |

Routes (FACTS.routes): `POST /intake` :33, `GET /runs/{run_id}` :50, `GET /status` :80.

## contracts

**`intake`** (orchestrator/orchestrator/api/intake.py:34-47)
- in: `IntakeRequest` fields used: `corpus_id, source_name, media_type, content_b64, config` — orchestrator/orchestrator/api/intake.py:36 [DERIVED]; type from `polymath_shared.contracts` (:20)
- pre: canonical payload built via `canonical_intake_payload(...)` — orchestrator/orchestrator/api/intake.py:35-37 [DERIVED]
- effect: single `tx()` transaction calling `submit_intake(conn, canonical_payload)` — orchestrator/orchestrator/api/intake.py:39-40 [DERIVED]
- out: `IntakeResponse(**result)` — result keys must be exactly `run_id, accepted, already_exists` — orchestrator/orchestrator/api/intake.py:41 [DERIVED]
- error: `ValueError` → HTTP 422 with `detail=str(exc)` — orchestrator/orchestrator/api/intake.py:42-43 [DERIVED]
- error: `psycopg.errors.UniqueViolation` → HTTP 200 with `accepted=True, already_exists=True` — orchestrator/orchestrator/api/intake.py:44-47 [DERIVED]

**`run_status`** (orchestrator/orchestrator/api/intake.py:51-77)
- in: path param `run_id`
- out: dict keys `run_id, corpus_id, status, created_at, updated_at, stages[]`; each stage = `{stage, contract_hash, outcome, completed_at, error}`; `created_at/updated_at` via `.isoformat()` — orchestrator/orchestrator/api/intake.py:66-77 [DERIVED]
- error: 404 `detail="run not found"` if no `runs` row — orchestrator/orchestrator/api/intake.py:57-58 [DERIVED]

**`pipeline_status`** (orchestrator/orchestrator/api/intake.py:81-162)
- in: `corpus_id` required; `source_name=None`, `run_id=None` — orchestrator/orchestrator/api/intake.py:81-82 [DERIVED]
- pre: `run_id or source_name` must be given, else HTTP 422 `"pass run_id or source_name"` — orchestrator/orchestrator/api/intake.py:89-90 [DERIVED]
- lookup: by `run_id` requires corpus match (`WHERE run_id = %s AND corpus_id = %s`); by `(corpus_id, source_name)` takes latest run with `superseded_by_run_id IS NULL` — orchestrator/orchestrator/api/intake.py:92-106 [DERIVED]
- out: keys `run_id, corpus_id, source_name, status, query_ready, created_at, updated_at, doc_id, bytes, chunks, enrichment, stages, open_stages, degraded_reasons, last_error, stalls, hint` — orchestrator/orchestrator/api/intake.py:146-162 [DERIVED]
- error: 404 `detail={"error_code": "RUN_NOT_FOUND", "message": "no run for that document in that corpus"}` — orchestrator/orchestrator/api/intake.py:107-109 [DERIVED]

## effect surface
- Postgres reads (FACTS.tables_read): `runs` (:54, :96, :102-105), `stage_attempts` (:61-62), `stage_tickets` (:112-113, :142-143), `documents` (:116-117), `parent_enrichments` (:123-124), `chunks` (:127-128), `stall_traces` (:135-137)
- Postgres writes: none in this file (FACTS.tables_written = `[]`); the run-row/outbox write happens inside `submit_intake` — orchestrator/orchestrator/api/intake.py:40 [DERIVED]
- Qdrant / files / network / subprocess: none visible in SOURCE
- Env flags / constants: none (FACTS.constants = `[]`)

## invariants
INVARIANT: `query_ready` == (`status` == `"query_ready"`) — orchestrator/orchestrator/api/intake.py:148 [DERIVED]
  fails-if: agent calls `ask()` on a run that is not queryable; hint at :159 would also lie.
INVARIANT: `open_stages` ⊆ tickets with status in `("pending", "ready", "leased")` — orchestrator/orchestrator/api/intake.py:145 [DERIVED]
  fails-if: settled runs reported as "in progress" in the hint (:160).
INVARIANT: `(corpus_id, source_name)` lookup rows have `superseded_by_run_id IS NULL` and max `created_at` (`ORDER BY created_at DESC LIMIT 1`) — orchestrator/orchestrator/api/intake.py:103-105 [DERIVED]
  fails-if: status reported for a superseded run.
INVARIANT: `enrichment.parents_total` == `COUNT(DISTINCT parent_id) FILTER (WHERE tier = 'child')` over `chunks` — orchestrator/orchestrator/api/intake.py:128,131 [DERIVED]
  fails-if: enrichment progress denominator disagrees with chunk tree.
INVARIANT: replay of identical canonical input creates no second run (docstring claim; enforcement in shared `submit_intake` + `UniqueViolation` handler) — orchestrator/orchestrator/api/intake.py:3-6,44-47 [DERIVED]
  fails-if: duplicate runs per document; see unbound-`result` flag below.
INVARIANT: stage ordering differs per endpoint — `run_status` sorts `ORDER BY stage`, `pipeline_status` sorts `ORDER BY seq` — orchestrator/orchestrator/api/intake.py:62,113 [DERIVED]
  fails-if: consumers assume one canonical stage order.

## determinism & idempotency
determinism: NONDETERMINISTIC (db — every response reflects live `runs`/`stage_tickets`/`stall_traces` state; no clock/uuid/random calls inside this file) — orchestrator/orchestrator/api/intake.py:53-56,111-114,134-138 [DERIVED]
idempotency: SAFE — `POST /intake` replay returns the existing `run_id` with `already_exists=True` (:5-6, :44-47); GET endpoints are read-only. Caveat: the replay path can crash on unbound `result` (:46) — orchestrator/orchestrator/api/intake.py:44-47 [INFERRED, see dumb-code flags]

## failure behaviour
- Swallowed: any `Exception` in the `stall_traces` read → `stalls = []` (FACTS.fallbacks; comment: table absent on an older store) — orchestrator/orchestrator/api/intake.py:139-140 [DERIVED]. Caller sees HTTP 200 with empty `stalls`, no signal that the read failed for other reasons.
- HTTP 422: `ValueError` from intake path, `detail=str(exc)` (:42-43); missing both `run_id` and `source_name`, `detail="pass run_id or source_name"` (:89-90).
- HTTP 404: `"run not found"` (:57-58); `{"error_code": "RUN_NOT_FOUND", ...}` (:107-109).
- `UniqueViolation` → HTTP 200 `already_exists=True` (:44-47), not an error.

## dumb-code flags
- Unbound `result` in the `UniqueViolation` handler: `result` is assigned only at :40 inside the `with`; if the violation escapes `submit_intake` before assignment, `result.get("run_id", "")` at :46 raises `NameError` → client gets 500 on the very replay path meant to be idempotent — orchestrator/orchestrator/api/intake.py:40,44-47 [INFERRED — assignment and use sit on disjoint paths]
- 404 detail shape mismatch: `run_status` returns a plain string, `pipeline_status` a structured dict — orchestrator/orchestrator/api/intake.py:58 vs :108-109 [DERIVED]
- Positional tuple indexing throughout `pipeline_status` (`run[0]`, `t[0..4]`, `s[0..5]`, `e[0]`, `c[0]`, `c[1]`, `doc[0]`, `doc[1]`) — fragile to column reorder — orchestrator/orchestrator/api/intake.py:110,115-119,130-132,152-153,157-158 [DERIVED]
- Bare `except Exception` around only the `stall_traces` query hides all failures, not just missing table — orchestrator/orchestrator/api/intake.py:139 [DERIVED]
- Duplicated 6-column SELECT list between the two run lookups — orchestrator/orchestrator/api/intake.py:94-95 vs :100-101 [DERIVED]

## refactor notes
- Route paths `/intake`, `/runs/{run_id}`, `/status` are the external contract (mounted via `orchestrator/orchestrator/main.py`, FACTS.importers; decorators at :33, :50, :80) — renaming breaks MCP clients.
- `POST /intake` response field names `run_id, accepted, already_exists` (:27-30) and the DOCUMENT-STATUS-V1 key set (:146-161) are consumed by agents; renames are breaking.
- `submit_intake`'s returned dict is splatted into `IntakeResponse(**result)` — its keys must stay exactly the three model fields — orchestrator/orchestrator/api/intake.py:40-41 [DERIVED]
- The write path is shared with the I1 manifest producer in `polymath_shared/intake_submission.py`; changing it here means changing it there — orchestrator/orchestrator/api/intake.py:8-9 [DERIVED]
- The `stall_traces` try/except must survive while older stores without the table exist — orchestrator/orchestrator/api/intake.py:139 [DERIVED]

## VERIFY
```verify
grep -Fq 'already_exists: bool = False' orchestrator/orchestrator/api/intake.py
grep -Fq 'except psycopg.errors.UniqueViolation' orchestrator/orchestrator/api/intake.py
grep -Fq 'pass run_id or source_name' orchestrator/orchestrator/api/intake.py
grep -Fq 'RUN_NOT_FOUND' orchestrator/orchestrator/api/intake.py
grep -Fq 'superseded_by_run_id IS NULL' orchestrator/orchestrator/api/intake.py
grep -Fq 'table absent on an older store' orchestrator/orchestrator/api/intake.py
test "$(grep -c -F 'query_ready' orchestrator/orchestrator/api/intake.py)" -ge 2
```
