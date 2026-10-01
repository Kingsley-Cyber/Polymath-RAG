# unit: shared/polymath_shared/control_plane_status.py
anchor: shared/polymath_shared/control_plane_status.py:1-191

## purpose

One bounded, read-only aggregate of the FUNCTIONAL POOLS' health for the operational UI: the corpus document summary (documents / semantic-ready / processing / blocked) plus per-pool queue depth, lane health, and provider-request accounting — distinguishing a LOCAL `limiter_refused` (0 HTTP) from an ACTUAL HTTP 429 (GROQ-MAP-CONTROL-PLANE-REPAIR-V1). shared/polymath_shared/control_plane_status.py:1-8 [DERIVED]
Every counter is ONE corpus-scoped aggregate query (never per-document scans); this module is the single backend authority — the UI renders it, never recomputes it. shared/polymath_shared/control_plane_status.py:10-13 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `control_plane_status` | def | (conn, *, corpus_id: str, sidecars: dict[str, bool] \| None = None, served: dict[str, dict] \| None = None) -> dict[str, Any] | shared/polymath_shared/control_plane_status.py:123-191 | orchestrator/orchestrator/api/ui.py (module-level import; per-symbol use not in FACTS) |
| `pool_lanes_detail` | def | (conn, *, function: str) -> dict[str, Any] | shared/polymath_shared/control_plane_status.py:89-120 | orchestrator/orchestrator/api/ui.py (module-level import; per-symbol use not in FACTS) |

Private helpers: `_queue_by_pool` :30-49, `_pmap_provider` :52-63, `_graph_provider` :66-86.

## contracts

**control_plane_status** — shared/polymath_shared/control_plane_status.py:123-191
- in: `conn` (DB-API conn executing `%s`-param SQL incl. `ANY(%s)` arrays), keyword-only `corpus_id` required, `sidecars=None`, `served=None` :123-125, :34, :147-152
- out: keys `contract` (= `"control-plane-status-v1"`), `corpus_id`, `control_ready`, `summary` {`documents`, `semantic_ready`, `vnext_served`, `basic_profile`, `processing`, `processing_active`, `processing_stalled`, `blocked`}, `pools` {`GRAPH_EXTRACTION`, `DOCUMENT_PROFILE`, `PMAP`, `CHAT`} :180-190, :19
- pre: `stage_tickets`, `artifacts` (with migration-0057 scalar columns + `extract_stats_present`), `runs`, `llm_controller_state` queryable :32-35, :78-83, :101-103, :147-152
- post: no rows written (FACTS `tables_written` empty); `control_ready` verdict composed exactly once here — callers render `control_ready.state`, they do not derive it :183-184

**pool_lanes_detail** — shared/polymath_shared/control_plane_status.py:89-120
- in: keyword-only `function` (pool name)
- out: `{"function": function, "models": [{"model": m, "lanes": [...]}]}` sorted by model; each lane has `lane`, `account_env`, `configured`, `reachability`, `role`, `family`, `capacity` {`rpm`,`tpm`,`rpd`,`concurrency`,`map_batch_cap`}, `live` {`day_count`,`effective`,`ceiling`,`decreases`,`increases`,`last_updated`} :113-120
- pre: `LR.build_registry()` must succeed — no handler in this function :95-96 [INFERRED]
- post: contains credential ENV NAMES only, never values :92-93

**_queue_by_pool** — shared/polymath_shared/control_plane_status.py:30-49
- out: per pool `{queued, processing, retry, failed}`; status `pending`/`ready`→queued, `leased`→processing, `failed`→failed; `retry` += tickets with `attempt>0` :37-48

**_pmap_provider** — shared/polymath_shared/control_plane_status.py:52-63
- out: `{provider_requests, limiter_refused, http_429, transport_errors, empty_completions, valid_maps_persisted, maps_per_request}`; `maps_per_request = round(mapped / disp, 2) if disp else None` :61-63

**_graph_provider** — shared/polymath_shared/control_plane_status.py:66-86
- out: `{provider_requests, neighborhoods_sent, neighborhoods_unaccounted, neighborhoods_dropped, entities, relations}` summed from columns `extract_llm_calls`, `extract_neighborhoods_sent`, `extract_neighborhoods_unaccounted`, `extract_neighborhoods_dropped`, `extract_entity_count`, `extract_relation_count`, gated by `a.extract_stats_present`, all `COALESCE(...,0)` :78-86

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `stage_tickets` (corpus-scoped GROUP BY stage,status) | shared/polymath_shared/control_plane_status.py:32-35 |
| Postgres read | `artifacts` JOIN `runs` (PMAP JSONB payload sums; extract scalar columns) | shared/polymath_shared/control_plane_status.py:55-59, :78-83 |
| Postgres read | `runs` (processing active/stalled split) | shared/polymath_shared/control_plane_status.py:147-152 |
| Postgres read | `llm_controller_state` (`key = ANY(...)`) | shared/polymath_shared/control_plane_status.py:101-103 |
| Postgres write | none (FACTS `tables_written: []`; read-only aggregate) | shared/polymath_shared/control_plane_status.py:3 |
| Network | none — "no provider call, no secrets" from LANE-REGISTRY | shared/polymath_shared/control_plane_status.py:11 |
| Lazy imports | `polymath_shared.document_status.corpus_document_summaries`; `polymath_shared.pipeline_health.{DORMANT_RUN_AGE_SECONDS, control_ready}`; `polymath_shared.llm_extraction.lane_registry`; `polymath_shared.document_profile.served.served_vnext_count` | shared/polymath_shared/control_plane_status.py:126-127, :95, :157, :139 |
| Env | none read directly; env NAMES surfaced via `l.api_key_env` | shared/polymath_shared/control_plane_status.py:114 |

## invariants

INVARIANT: `processing` = `processing_active` + `processing_stalled` — shared/polymath_shared/control_plane_status.py:153 [DERIVED]
  fails-if: summary undercounts in-flight work if one FILTER arm is dropped
INVARIANT: `blocked` = `documents` − `searchable` — shared/polymath_shared/control_plane_status.py:142 [DERIVED]
  fails-if: red-file count misreports the corpus
INVARIANT: `basic_profile` = `searchable` − (`semantic_ready` if `vnext_served is None` else `vnext_served`) — shared/polymath_shared/control_plane_status.py:141 [DERIVED]
  fails-if: ready/basic split double-counts or drops served vNext cards
INVARIANT: `semantic_ready` ≤ `searchable` — shared/polymath_shared/control_plane_status.py:130 vs :134 [INFERRED] (`vnext_ready` is the first disjunct of the searchable predicate, so every counted doc is searchable)
  fails-if: negative `basic_profile`
INVARIANT: `pools` keys exactly {"GRAPH_EXTRACTION","DOCUMENT_PROFILE","PMAP","CHAT"} — shared/polymath_shared/control_plane_status.py:173-179 [DERIVED]
INVARIANT: `provider` sub-dict present only on GRAPH_EXTRACTION and PMAP; DOCUMENT_PROFILE and CHAT have none — shared/polymath_shared/control_plane_status.py:174-178 [DERIVED]
INVARIANT: `_ALL_STAGES` = union of `_POOL_STAGES` values = {`extract`,`profile_document`,`doc_profile`,`doc_parent_map`} — shared/polymath_shared/control_plane_status.py:22-27 [DERIVED]

## determinism & idempotency

determinism: NONDETERMINISTIC (db — four tables read :32-35, :55-59, :78-83, :101-103, :147-152; clock — `now()` in the runs dormancy split :148-149; env/config — `lane_registry` build :95-96, :157-158)
idempotency: SAFE (read-only; no writes anywhere in the module — shared/polymath_shared/control_plane_status.py:3, FACTS `tables_written: []`)

## failure behaviour

- `except Exception` at shared/polymath_shared/control_plane_status.py:160 (FACTS.fallbacks: "handled: assign") swallows any lane-registry/config failure: `health, LR = {}, None` (:161). The endpoint still returns; every pool's `lanes` silently renders zero/empty defaults (:164-167). [DERIVED]
- `served=None` / unread profile index → `served_vnext_count` yields `None` → `basic_profile` falls back to `semantic_ready` — "None = the index was unread" (:140-141, :138). [DERIVED]
- `pool_lanes_detail` has no try/except — a config-read error propagates to its caller (:89-120). [INFERRED]
- No error codes are raised by this module.

## dumb-code flags

- `CHAT` is absent from `_POOL_STAGES` (:22-26), so `pool("CHAT")` merges `queue.get("CHAT", {})` → the CHAT pool has no `queued`/`processing`/`retry`/`failed` keys — shape differs from ingestion pools (:168, :178). [DERIVED]
- Key round-trip surgery: builds `f"llm_cloud[{l.name}]"` (:99) then parses back via slicing `key[len("llm_cloud["):-1]` (:104) — breaks if a lane name contains `]`. [DERIVED]
- `DORMANT_RUN_AGE_SECONDS` passed twice, once per FILTER arm (:152) — the two arms must stay in sync. [DERIVED]
- Two provider-accounting mechanisms: PMAP sums JSONB payload keys (`p->>'http_dispatches'` etc., :55-57) while GRAPH_EXTRACTION sums migration-0057 scalar columns (:78-82); the old JSONB path measured 490-605 ms from ~45,000-buffer TOAST detoasts (:69-73). [DERIVED]
- Ticket-status literals `'pending'`,`'ready'`,`'leased'`,`'failed'` inline in SQL string and branches, no shared enum (:34, :42-47). [DERIVED]
- Near-duplicate counters with different semantics: `semantic_ready` counts written vNext cards (scripts read it) vs `vnext_served` counts served cards (:130 vs :140, :138). [DERIVED]

## refactor notes

- `"contract": CONTROL_PLANE_STATUS_VERSION` (`"control-plane-status-v1"`, :19, :181) is a versioned shape; the sole importer orchestrator/orchestrator/api/ui.py (FACTS.importers) must move with any key change. [DERIVED]
- CHAT must keep the same lane shape as every pool — FRONTEND-BACKEND-CONTRACT-V1 notes it previously omitted `credential_absent` / `disabled` (:177). [DERIVED]
- `control_ready` is composed here once; callers render `control_ready.state` and must not re-derive it (:183-184). [DERIVED]
- `_graph_provider` depends on migration 0057 columns + `extract_stats_present`; aggregate semantics were proven by 100% shadow parity against the old JSONB derivation (:67-76) — any re-derivation needs equivalent re-proof. [DERIVED]
- The `searchable` rule mirrors the frontend rule (frontend lib/readiness.ts `docSearchable`): every eligible parent mapped AND any profile = searchable (:131-134); renaming `vnext_ready` / `map_unresolved` / `profile_present` summary fields breaks both sides. [DERIVED]

## VERIFY

```verify
grep -Fq 'control-plane-status-v1' shared/polymath_shared/control_plane_status.py
grep -Fq 'llm_cloud[' shared/polymath_shared/control_plane_status.py
grep -Fq 'superseded_by_run_id IS NULL' shared/polymath_shared/control_plane_status.py
grep -Fq 'make_interval(secs => %s)' shared/polymath_shared/control_plane_status.py
! grep -Fq 'INSERT INTO' shared/polymath_shared/control_plane_status.py
test "$(grep -c -F 'DORMANT_RUN_AGE_SECONDS' shared/polymath_shared/control_plane_status.py)" -ge 2
```
