# unit: shared/polymath_shared/control_plane_status.py
anchor: shared/polymath_shared/control_plane_status.py:1-179

## purpose
Read-only, corpus-scoped aggregate of functional-pool ingestion health for the operational UI: document summary, per-pool queue depth, lane health, and provider-request accounting — explicitly separating local `limiter_refused` (0 HTTP) from real `http_429` (GROQ-MAP-CONTROL-PLANE-REPAIR-V1) — shared/polymath_shared/control_plane_status.py:1-13 [DERIVED]. Every counter is one corpus-scoped aggregate query, never per-document scans; this module is the single backend authority the UI renders, never recomputes — shared/polymath_shared/control_plane_status.py:10-13 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `control_plane_status` | def | `(conn, *, corpus_id: str, sidecars: dict[str, bool] \| None = None) -> dict[str, Any]` | shared/polymath_shared/control_plane_status.py:123-179 | orchestrator/orchestrator/api/ui.py |
| `pool_lanes_detail` | def | `(conn, *, function: str) -> dict[str, Any]` | shared/polymath_shared/control_plane_status.py:89-120 | orchestrator/orchestrator/api/ui.py [INFERRED: module-level importer per FACTS; exact symbol not in FACTS] |

Internal: `_queue_by_pool` (30-49), `_pmap_provider` (52-63), `_graph_provider` (66-86); constants `CONTROL_PLANE_STATUS_VERSION` (19), `_POOL_STAGES` (22-26), `_ALL_STAGES` (27).

## contracts

### `control_plane_status`
- in: keyword-only `corpus_id: str`; optional `sidecars: dict[str, bool] | None = None` — shared/polymath_shared/control_plane_status.py:123-124 [DERIVED]
- out: keys `"contract"` (= `CONTROL_PLANE_STATUS_VERSION`), `"corpus_id"`, `"control_ready"`, `"summary"` (`documents`, `semantic_ready`, `processing`, `processing_active`, `processing_stalled`, `blocked`), `"pools"` (`GRAPH_EXTRACTION`, `DOCUMENT_PROFILE`, `PMAP`, `CHAT`) — shared/polymath_shared/control_plane_status.py:169-179 [DERIVED]
- pre: `conn` executes `%s`-placeholder SQL with tuple params (psycopg-style) — shared/polymath_shared/control_plane_status.py:33-35 [INFERRED: every query uses `%s` + `ANY(%s)`]
- post: CHAT pool carries `"latency_pool": True`; GRAPH_EXTRACTION and PMAP pools carry a `"provider"` dict, DOCUMENT_PROFILE does not — shared/polymath_shared/control_plane_status.py:162-168 [DERIVED]
- post: control-ready verdict is composed exactly once via `control_ready(conn, sidecars=sidecars)`; callers render `control_ready.state` and never derive it — shared/polymath_shared/control_plane_status.py:172-174 [DERIVED]

### `pool_lanes_detail`
- in: keyword-only `function: str` — shared/polymath_shared/control_plane_status.py:89 [DERIVED]
- out: `{"function": function, "models": [{"model": m, "lanes": [...]}]}` with models `sorted()` — shared/polymath_shared/control_plane_status.py:120 [DERIVED]
- post: each lane exposes `lane`, `account_env`, `configured`, `reachability`, `role`, `family`, `capacity` (`rpm`, `tpm`, `rpd`, `concurrency`, `map_batch_cap`), `live` (`day_count`, `effective`, `ceiling`, `decreases`, `increases`, `last_updated`) — shared/polymath_shared/control_plane_status.py:113-118 [DERIVED]
- post: credential is the ENV NAME only (`l.api_key_env`), never the value — shared/polymath_shared/control_plane_status.py:90-92, 114 [DERIVED]

### `_queue_by_pool`
- Maps ticket status: `("pending", "ready")` → `queued`; `"leased"` → `processing`; `"failed"` → `failed`; `retry` += rows with `attempt>0` — shared/polymath_shared/control_plane_status.py:33, 42-48 [DERIVED]

### `_pmap_provider`
- Sums `doc_parent_map` payload fields `http_dispatches`, `limiter_refusals`, `http_429`, `http_failures`, `parents_mapped`, `empty_completions`; `maps_per_request = round(mapped / disp, 2) if disp else None` — shared/polymath_shared/control_plane_status.py:55-63 [DERIVED]

### `_graph_provider`
- Sums scalar columns `extract_llm_calls`, `extract_neighborhoods_sent`, `extract_neighborhoods_unaccounted`, `extract_neighborhoods_dropped`, `extract_entity_count`, `extract_relation_count` filtered by `a.extract_stats_present` (migration 0057 projection); never reads `artifacts.payload` — shared/polymath_shared/control_plane_status.py:67-83 [DERIVED]

## effect surface
- Postgres read: `stage_tickets` (33-35), `artifacts` (58, 80-81), `runs` (58-59, 81-82, 136-141), `llm_controller_state` (101-103) [DERIVED]
- Postgres write: none — FACTS `tables_written: []`; no write SQL in source [DERIVED]
- Network/provider calls: none — "no provider call, no secrets" — shared/polymath_shared/control_plane_status.py:11 [DERIVED]
- Env: none read directly; lane credential ENV names surfaced as strings via `l.api_key_env` (114), values excluded [DERIVED]
- Deferred imports: `polymath_shared.llm_extraction.lane_registry` (95, 146), `polymath_shared.document_status.corpus_document_summaries` (125), `polymath_shared.pipeline_health.{DORMANT_RUN_AGE_SECONDS, control_ready}` (126) [DERIVED]

## invariants
INVARIANT: `processing == processing_active + processing_stalled` — shared/polymath_shared/control_plane_status.py:142 [DERIVED]
  fails-if: summary double-counts or drops in-flight runs.
INVARIANT: a run counts as stalled iff `updated_at <= now() - make_interval(secs => DORMANT_RUN_AGE_SECONDS)` among statuses `('intake','reconciling','degraded')` with `superseded_by_run_id IS NULL` — shared/polymath_shared/control_plane_status.py:137-140 [DERIVED]
  fails-if: dormant runs reported as actively processing (GAP-4 comment: 64 frozen runs since 2026-09-07 were previously shown as processing) — shared/polymath_shared/control_plane_status.py:132-135 [DERIVED]
INVARIANT: `_ALL_STAGES` == flatten of `_POOL_STAGES` (`extract`, `profile_document`, `doc_profile`, `doc_parent_map`) — shared/polymath_shared/control_plane_status.py:22-27 [DERIVED]
  fails-if: a pool's queue counters silently miss its stage.
INVARIANT: `maps_per_request` is None iff summed `http_dispatches` == 0 — shared/polymath_shared/control_plane_status.py:63 [DERIVED]
  fails-if: division by zero on an empty corpus.
INVARIANT: response `"contract"` == `"control-plane-status-v1"` — shared/polymath_shared/control_plane_status.py:19, 170 [DERIVED]
  fails-if: UI contract check fails.
INVARIANT: every pool's `lanes` block defaults to `{active: 0, total: 0, credential_absent: 0, disabled: 0, active_lanes: []}` when registry health is unavailable — shared/polymath_shared/control_plane_status.py:153-156 [DERIVED]
  fails-if: config failure crashes the polled endpoint instead of degrading to zeros.

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads of `stage_tickets`/`artifacts`/`runs`/`llm_controller_state` at 33-35, 54-59, 77-83, 101-103, 136-141; SQL `now()` at 137-138; lane-registry config at 96 and 146-147) [DERIVED]
idempotency: SAFE (read-only; no table writes, no state mutation — FACTS `tables_written: []`) [DERIVED]

## failure behaviour
- `except Exception` at shared/polymath_shared/control_plane_status.py:149 (`# noqa: BLE001 — never crash on a config read`): registry/config failures are swallowed; `health, LR = {}, None`; all pools then report zeroed lane blocks (153-156) and the caller still receives the full response [DERIVED]
- SQL failures from `conn.execute` are not guarded (only the registry read is inside `try`) and propagate to the caller — shared/polymath_shared/control_plane_status.py:145-150 [DERIVED]
- Empty/absent corpus result sets yield 0, not errors, via `COALESCE(SUM(...),0)` — shared/polymath_shared/control_plane_status.py:55-57, 78-80 [DERIVED]

## dumb-code flags
- CHAT is absent from `_POOL_STAGES` (22-26), so `queue.get("CHAT", {})` (157) returns `{}` and the CHAT pool dict has **no** `queued`/`processing`/`retry`/`failed` keys, unlike the other three pools which are zero-initialized (37) — shared/polymath_shared/control_plane_status.py:37, 157, 167 [DERIVED]
- Dead assignment `LR = None` in the except branch; `LR` is never referenced after line 147 — shared/polymath_shared/control_plane_status.py:150 [DERIVED]
- `retry` counts `attempt>0` rows independently of status (33, 48): a failed retrying ticket is counted in both `failed` and `retry` — shared/polymath_shared/control_plane_status.py:46-48 [DERIVED]
- Duplicated literals: `doc_parent_map` in `_POOL_STAGES` (25) and again in `_pmap_provider` SQL (58); `extract` in `_POOL_STAGES` (23) and `_graph_provider` SQL (82) [DERIVED]
- Inline status lists, no shared constant: `("pending", "ready")` / `"leased"` / `"failed"` (42-46) and `('intake','reconciling','degraded')` (139) [DERIVED]
- Magic rounding `round(mapped / disp, 2)` and model sentinel `"(unset)"` — shared/polymath_shared/control_plane_status.py:63, 113 [DERIVED]

## refactor notes
- orchestrator/orchestrator/api/ui.py imports this module (FACTS.importers); it renders the output and "never recomputes it" (12-13) — renaming output keys, pools, or `latency_pool` breaks the UI without a UI change — shared/polymath_shared/control_plane_status.py:166-179 [DERIVED]
- `_graph_provider` depends on migration-0057 scalar columns and `extract_stats_present`; reverting to a `payload` JSONB filter reintroduces the ~45,000-buffer TOAST detoast measured at 490-605 ms per call — shared/polymath_shared/control_plane_status.py:67-76 [DERIVED]
- `DORMANT_RUN_AGE_SECONDS` is imported from `pipeline_health` (126) and used twice in one query (141); changing the shared constant shifts the active/stalled split here and there simultaneously — shared/polymath_shared/control_plane_status.py:126, 137-141 [DERIVED]
- `control_ready` verdict composed once here (GAP-1); moving that composition to callers violates the stated contract — shared/polymath_shared/control_plane_status.py:172-174 [DERIVED]
- `pool_lanes_detail` must keep `account_env` as ENV name only; leaking credential values violates the "NEVER a secret" contract — shared/polymath_shared/control_plane_status.py:90-92, 114 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTROL_PLANE_STATUS_VERSION = "control-plane-status-v1"' shared/polymath_shared/control_plane_status.py
grep -Fq 'DORMANT_RUN_AGE_SECONDS' shared/polymath_shared/control_plane_status.py
grep -Fq 'extract_stats_present' shared/polymath_shared/control_plane_status.py
grep -Fq 'llm_controller_state' shared/polymath_shared/control_plane_status.py
grep -Fq 'latency_pool' shared/polymath_shared/control_plane_status.py
! grep -Fq 'INSERT INTO' shared/polymath_shared/control_plane_status.py
test "$(grep -c -F 'COALESCE' shared/polymath_shared/control_plane_status.py)" -ge 6
```
