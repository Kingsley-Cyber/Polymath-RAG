# unit: shared/polymath_shared/control_plane_status.py
anchor: shared/polymath_shared/control_plane_status.py:1-184

## purpose
Read-only, corpus-scoped aggregate of functional-pool health for the operational UI: document summary (documents / semantic-ready / processing / blocked) plus per-pool (GRAPH_EXTRACTION, DOCUMENT_PROFILE, PMAP, CHAT) queue depth, lane health, and provider-request accounting — distinguishing local `limiter_refused` (0 HTTP) from real `http_429` — shared/polymath_shared/control_plane_status.py:1-13 [DERIVED]. Single backend authority; the UI renders it, never recomputes it — shared/polymath_shared/control_plane_status.py:11-12 [DERIVED]. Sole known importer: `orchestrator/orchestrator/api/ui.py` (module-level, from FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `control_plane_status` | def | (conn, *, corpus_id: str, sidecars: dict[str, bool] \| None = None) -> dict[str, Any] | shared/polymath_shared/control_plane_status.py:123-183 | orchestrator/orchestrator/api/ui.py (module import) |
| `pool_lanes_detail` | def | (conn, *, function: str) -> dict[str, Any] | shared/polymath_shared/control_plane_status.py:89-120 | orchestrator/orchestrator/api/ui.py (module import) |

Module-private helpers, internal only: `_queue_by_pool` :30-49, `_pmap_provider` :52-63, `_graph_provider` :66-86.

## contracts

**control_plane_status** — shared/polymath_shared/control_plane_status.py:123-183
- in: `conn` (DB `.execute`), keyword-only `corpus_id: str`, keyword-only `sidecars: dict[str, bool] | None = None` (:123-124).
- out: dict keys `contract` (= `"control-plane-status-v1"` :19, :174), `corpus_id` (:175), `control_ready` (:178), `summary` {documents, semantic_ready, basic_profile, processing, processing_active, processing_stalled, blocked} (:179-181), `pools` {GRAPH_EXTRACTION, DOCUMENT_PROFILE, PMAP, CHAT} (:166-171); CHAT carries `"latency_pool": True` (:171).
- pre: readable schema — `stage_tickets(corpus_id, stage, status, attempt)` (:33-34), `artifacts(run_id, stage, payload, extract_*) + extract_stats_present` (:58-59, :77-82), `runs(run_id, corpus_id, status, updated_at, superseded_by_run_id)` (:58, :81, :140-145).
- post: the one control-ready verdict composed here via `pipeline_health.control_ready(conn, sidecars=sidecars)`; callers render `control_ready.state`, never derive it (:126, :177-178).

**pool_lanes_detail** — shared/polymath_shared/control_plane_status.py:89-120
- in: `conn`, keyword-only `function: str` (pool name, e.g. matched against `l.function`) (:89, :97).
- out: `{"function": function, "models": [{"model": m, "lanes": [...]}]}`, models sorted (:110-120); each lane: `lane`, `account_env`, `configured`, `reachability`, `role`, `family`, `capacity` {rpm, tpm, rpd, concurrency, map_batch_cap}, `live` {day_count, effective, ceiling, decreases, increases, last_updated} (:113-118).
- pre: `polymath_shared.llm_extraction.lane_registry` importable (:95); `llm_controller_state(key, state, updated_at)` readable (:101-102).
- post: contains credential ENV **names** only, never values (:91-92, :114).

Helper one-liners: `_queue_by_pool` buckets stage_tickets per pool (pending|ready→queued, leased→processing, failed→failed, retry = attempt>0) (:37-48); `_pmap_provider` sums `payload->'doc_parent_map'` JSON counters (:54-63); `_graph_provider` sums `extract_*` scalar columns WHERE `extract_stats_present` (:77-86).

## effect surface
- Postgres read: `stage_tickets` (:33-34); `artifacts` JOIN `runs` — doc_parent_map payload (:58-59) and extract_* columns (:81-82); `runs` (:140-145); `llm_controller_state` (:101-102, `pool_lanes_detail` only).
- Postgres written: none — FACTS.tables_written empty; every statement is SELECT. [DERIVED]
- Network / Qdrant / files / subprocess: none — "no provider call, no secrets" (:11). [DERIVED]
- Config/env: lane registry exposes credential ENV names + `credential_present` (:95-97, :113-115); `sidecars` argument feeds `control_ready` (:124, :178).

## invariants
INVARIANT: blocked == documents − searchable — shared/polymath_shared/control_plane_status.py:135 [DERIVED]
  fails-if: red-file count diverges from the searchable rule at :133.
INVARIANT: basic_profile == searchable − semantic_ready — shared/polymath_shared/control_plane_status.py:134 [DERIVED]
  fails-if: double-counts searchable files lacking the vNext profile.
INVARIANT: processing == processing_active + processing_stalled — shared/polymath_shared/control_plane_status.py:146 [DERIVED]
  fails-if: summary shows fewer in-flight runs than the runs table query returned.
INVARIANT: searchable counts summaries where `vnext_ready` OR (`map_unresolved` == 0 AND `profile_present`) — shared/polymath_shared/control_plane_status.py:133 [DERIVED]
  fails-if: frontend `docSearchable` rule and backend blocked count disagree (LIBRARY-READY-LABEL :130-132).
INVARIANT: maps_per_request == None whenever http_dispatches == 0; else round(mapped/disp, 2) — shared/polymath_shared/control_plane_status.py:63 [DERIVED]
  fails-if: zero-division on an idle corpus.
INVARIANT: stage_tickets statuses outside {pending, ready, leased, failed} contribute only to `retry`, never to queued/processing/failed — shared/polymath_shared/control_plane_status.py:41-47 [DERIVED]
  fails-if: a newly introduced ticket status silently disappears from queue accounting.
INVARIANT: queue keys exist only for pools in _POOL_STAGES (GRAPH_EXTRACTION, DOCUMENT_PROFILE, PMAP); CHAT has no queued/processing/retry/failed keys — shared/polymath_shared/control_plane_status.py:22-26, :37, :161 [DERIVED]
  fails-if: a consumer assuming uniform pool shape reads missing keys on CHAT.
INVARIANT: _graph_provider sums only artifacts rows with `extract_stats_present` — shared/polymath_shared/control_plane_status.py:82 [DERIVED]
  fails-if: rows without extract stats inflate/deflate GRAPH_EXTRACTION accounting vs the old JSONB derivation (:73-76).
INVARIANT: active/stalled split uses DORMANT_RUN_AGE_SECONDS, the same window pipeline_health uses — shared/polymath_shared/control_plane_status.py:126, :140-145 [DERIVED]
  fails-if: frozen runs counted as processing again (GAP-4: 64 runs frozen since 2026-09-07, :138-139).

## determinism & idempotency
determinism: NONDETERMINISTIC (db contents: :33-34, :58-59, :81-82, :101-102, :140-145; SQL clock `now()` :141-142; lane-registry config/env :95-97, :113-115)
idempotency: SAFE (read-only; all statements SELECT, no tables written)

## failure behaviour
- `except Exception` around `build_registry()` / `pool_lane_health()` — shared/polymath_shared/control_plane_status.py:149-154 (FACTS.fallbacks line 153). Any config-read failure is swallowed; `health = {}`, `LR = None`. Downstream `pool()` then defaults lanes to `active 0 / total 0 / credential_absent 0 / disabled 0 / active_lanes []` (:156-160), so callers receive a zeroed-lane payload, not an error. `# noqa: BLE001` on :153.
- No other handlers; SQL/DB errors propagate to the caller.

## dumb-code flags
- Literal `"llm_cloud["` duplicated: key construction :99 and manual strip :104 — prefix change must touch both. [DERIVED]
- Dead assignment: `LR = None` in the except arm (:154); neither `LR` nor `reg` is used after the try block. [DERIVED]
- `round(mapped / disp, 2)` — magic precision for maps_per_request (:63). [DERIVED]
- CHAT omits queue counters while :170 (FRONTEND-BACKEND-CONTRACT-V1) claims the same lane shape as every pool — queue shape still differs (:171 vs :37). [INFERRED: keys absent because CHAT is not in _POOL_STAGES]
- runs in-flight filter is the literal status set `('intake','reconciling','degraded')` plus `superseded_by_run_id IS NULL` (:143-144) — any other non-terminal status name is invisible here. [DERIVED]

## refactor notes
- Payload shape is a UI contract: `contract` string (:19, :174), summary keys (:179-181), pools keys incl. CHAT `latency_pool` (:166-171) — sole known importer is orchestrator/orchestrator/api/ui.py (FACTS.importers).
- `control_ready` must stay composed here once; callers render `control_ready.state` (:11-12, :177-178).
- `_graph_provider` depends on migration 0057 scalar columns (`extract_llm_calls`, `extract_neighborhoods_sent`, `extract_neighborhoods_unaccounted`, `extract_neighborhoods_dropped`, `extract_entity_count`, `extract_relation_count`, `extract_stats_present`) — schema drift breaks it and reintroduces the ~45,000-buffer TOAST detoast (490-605 ms) of the old JSONB path (:67-76, :77-82).
- DORMANT_RUN_AGE_SECONDS must remain imported from pipeline_health (:126) or the stalled/active split diverges from control_ready's dormancy window (:140-145).

## VERIFY
```verify
grep -Fq 'CONTROL_PLANE_STATUS_VERSION = "control-plane-status-v1"' shared/polymath_shared/control_plane_status.py
grep -Fq 'searchable = sum(1 for v in summaries.values() if v["vnext_ready"] or (v["map_unresolved"] == 0 and v["profile_present"]))' shared/polymath_shared/control_plane_status.py
grep -Fq 'processing = processing_active + processing_stalled' shared/polymath_shared/control_plane_status.py
grep -Fq 'round(mapped / disp, 2) if disp else None' shared/polymath_shared/control_plane_status.py
grep -Fq 'AND a.extract_stats_present' shared/polymath_shared/control_plane_status.py
grep -Eq 'status IN \(.intake.,.reconciling.,.degraded.\)' shared/polymath_shared/control_plane_status.py
test "$(grep -c -F 'COALESCE(SUM(' shared/polymath_shared/control_plane_status.py)" -ge 7
```
