# unit: orchestrator/orchestrator/api/_small-modules
anchor: orchestrator/orchestrator/api/capabilities.py:1-93

## purpose
Four small read-only API modules: `capabilities.py` serves a self-describing capability card (`GET /capabilities`) for agents/skills to probe contracts; `fleet.py` serves `GET /fleet`, a live visibility board over lanes/workers/queue/enrichment; `queries.py` serves `GET /queries`, the query-receipts read surface; `wildcard.py` implements the WILDCARD retrieval mode service (DIVERGENT-RETRIEVAL-V1). [DERIVED] capabilities.py:1-7, fleet.py:1-8, queries.py:1-4, wildcard.py:1-8

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `capabilities_payload` | function | () -> dict | capabilities.py:82-87 | one or more of retrieve.py, ui.py, main.py (FACTS.importers) [INFERRED] |
| `capabilities` | route handler | GET /capabilities () -> dict | capabilities.py:90-92 | — |
| `fleet` | route handler | GET /fleet () -> dict | fleet.py:39-79 | — |
| `queries` | route handler | GET /queries (corpus_id=None, kind=None, limit=20, since_h=24.0) -> dict | queries.py:17-32 | — |
| `wildcard_retrieve` | function | (query: str, corpus_id: str, scope=None) -> dict | wildcard.py:18-100 | — |
| `_version` | function (lru_cache maxsize=1) | () -> str | capabilities.py:50-56 | internal |
| `_live_contracts` | function | () -> dict | capabilities.py:59-79 | internal |
| `_lane_rows` | function | () -> list[dict] | fleet.py:20-36 | internal |

## contracts

**capabilities_payload()** — capabilities.py:82-87
- in: no arguments.
- out: dict with keys `backend="polymath"`, `version`, `api` (= `API_DATE`), `contracts`, `endpoints`, `mcp_tools`, `mcp_hidden_tools`, `retrieval_modes`. [DERIVED] capabilities.py:84-87
- pre: every name in `RETRIEVAL_MODES` must be a key of `MODE_GUIDE`, else the comprehension `{m: MODE_GUIDE[m] ...}` raises `KeyError`. [INFERRED — direct dict indexing] capabilities.py:87
- post: `contracts` comes from `_live_contracts()`, which is best-effort and never raises. [DERIVED] capabilities.py:62, 74

**fleet()** — fleet.py:39-79
- in: no arguments.
- out: `{"lanes": [...], "workers": [...], "queue": [...], "enrichment": {"parents": <int>, <status>: <count>}}`. [DERIVED] fleet.py:78-79
- pre: DB reachable; `cloud_endpoints()` / `stage_pin("parent_enrichment")` importable. [DERIVED] fleet.py:21-25
- post: each lane dict may gain a `"limiter"` key matched by substring `f"[{lane['name']}]"` in the controller key. [DERIVED] fleet.py:73-77

**queries(...) — GET /queries** — queries.py:17-32
- in: `corpus_id: Optional[str]`, `kind: Optional[str]`, `limit: int = Query(20, ge=1, le=200)`, `since_h: float = Query(24.0, gt=0, le=24 * 30)`. [DERIVED] queries.py:18-20
- pre: if `corpus_id` given, it must pass `require_corpus(corpus_id)` (FRIENDS-ACCESS-V1 D5); if `allowed_corpora() is not None` and no `corpus_id`, raises `HTTPException(422, {"error_code": "CORPUS_ID_REQUIRED", ...})`. [DERIVED] queries.py:24-27
- out: `{"corpus_id", "kind", "since_h", "count", "summary", "queries"}` where rows/summary come from `recent_queries` / `query_summary`. [DERIVED] queries.py:28-32

**wildcard_retrieve(query, corpus_id, scope=None)** — wildcard.py:18-100
- pre: `corpus_id` must not be `None`, else `HTTPException(422, {"error_code": "corpus_required", "message": "WILDCARD requires an explicit corpus_id"})`. [DERIVED] wildcard.py:29-32
- in/out: answer evidence = plain `fast_retrieve(query, [corpus_id], **scope_kwargs(scope))`; frontier via `divergent_retrieve(..., plan=DIVERGENT_DEFAULT_PLAN)`. [DERIVED] wildcard.py:35, 85-92
- post: returns `{**fast, "meta": meta, "wildcard": out["wildcard"]}` with `meta["mode"] = "WILDCARD"`, `meta["wildcard"] = out["diagnostics"]`, `meta["wildcard_plan"] = out["plan"]`. [DERIVED] wildcard.py:96-100

## effect surface
- Postgres read (via `polymath_shared.db.tx`): `runs` (capabilities.py:66-70); `llm_controller_state`, `worker_registrations`, `stage_tickets`, `parent_enrichments` JOIN `chunks`, `chunks` (fleet.py:44-72); query receipts via `recent_queries`/`query_summary`, docstring: "Backed by the `query_receipts` table" (queries.py:3-4, 28-30). [DERIVED]
- Postgres written: none — `tables_written: []` across the unit. [DERIVED] FACTS tables_written
- Qdrant: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` opened and closed in `finally` (wildcard.py:48-49, 93-94); searches filter on `representation_kind` in {latent kinds, `"routing_child"`} + `corpus_id` (+ `parent_id`). [DERIVED] wildcard.py:52-61
- Network (sidecar): cross-encoder rerank via `_rerank_children`; comment: "the sidecar returns raw cross-encoder logits". [INFERRED — rerank goes to a sidecar] wildcard.py:73, 79-81
- Subprocess: `git rev-parse --short HEAD`, `cwd=repo root (parents[3])`, `timeout=5` (capabilities.py:53-54).
- Env flags read: `POLYMATH_CORPUS_EXPLORER` default `'0'`; `"v1"` advertised only when value is `"1"`, else `False` (capabilities.py:78).
- Files: none written by this unit. [DERIVED]

## invariants
INVARIANT: Postgres writes = 0 for all four modules (read-only surfaces) — FACTS tables_written [DERIVED]
  fails-if: any INSERT/UPDATE here would break the "visibility only / no new state" contract of the fleet board (fleet.py:6-7)
INVARIANT: workers list length ≤ 40 — fleet.py:59 (`LIMIT 40`) [DERIVED]
  fails-if: more than 40 live workers silently drop rows from the board
INVARIANT: `limit` ∈ [1, 200] default 20; `since_h` ∈ (0, 720] default 24.0 — queries.py:18-20 [DERIVED]
  fails-if: FastAPI 422 validation error before handler code runs
INVARIANT: `len(ENDPOINTS)` = 16 — capabilities.py:34-37 [DERIVED]
  fails-if: consumers iterating ENDPOINTS see a changed surface without a CONTRACTS version bump
INVARIANT: `len(MCP_TOOLS)` = 9 + 7 `ADAPTER_MCP_TOOLS` = 16 — capabilities.py:42, 45-46 [DERIVED]
  fails-if: adapter parity between MCP Server A and Server B (pinned by tests/contracts/test_mcp_adapter_parity.py) drifts — capabilities.py:38-41
INVARIANT: `field-evidence-corpus` is non-null only when a `runs` row with `corpus_id LIKE 'field-evidence%'` has `status = 'query_ready'` — capabilities.py:68-72 [DERIVED]
  fails-if: a non-ready corpus is advertised to consumers as ingestable field evidence
INVARIANT: lane role precedence = `name in pins` → `"enrichment"`, else `not dedicated` → `"extraction"`, else `"dedicated"` — fleet.py:31-34 [DERIVED]
  fails-if: a pinned endpoint that is also dedicated is reported as enrichment, hiding its dedicated role
INVARIANT: `_version` computed once per process (`lru_cache(maxsize=1)`) — capabilities.py:50 [DERIVED]
  fails-if: a deploy without restart keeps reporting the old git sha in the payload
INVARIANT: cross-encoder logits squashed to 0-1 via `1.0 / (1.0 + math.exp(-float(s)))` so they share a scale with the support floor — wildcard.py:82-83 [DERIVED]
  fails-if: raw logits would make the engine's support floor and multiplicative WildcardValue incomparable

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess `git rev-parse` capabilities.py:54; clock `time.time` for `heartbeat_age_s` fleet.py:53; DB reads fleet.py:44-72, queries.py:28-30, capabilities.py:66-70; env `POLYMATH_CORPUS_EXPLORER` capabilities.py:78; network Qdrant + rerank sidecar wildcard.py:48, 73) [DERIVED]
idempotency: SAFE (all endpoints read-only; `wildcard_retrieve` opens its Qdrant client and closes it in `finally`, wildcard.py:93-94; no table writes) [DERIVED]

## failure behaviour
- `capabilities.py:54-56`: any `Exception` from the git subprocess is swallowed → `_version()` returns `"unknown"`; `/capabilities` still serves with `version: "unknown"`. [DERIVED]
- `capabilities.py:72-74`: any `Exception` from the `runs` lookup is swallowed (`pass`) → `field-evidence-corpus` stays `None` in the payload. [DERIVED]
- `queries.py:27`: `HTTPException(422)` with `error_code: "CORPUS_ID_REQUIRED"` when the caller is corpus-scoped but named no corpus. [DERIVED]
- `wildcard.py:30-32`: `HTTPException(422)` with `error_code: "corpus_required"` when `corpus_id is None`. [DERIVED]
- `wildcard.py:77-78`: `_rerank_pairs` returns `None` when any candidate is missing a `rerank_score` in the cross-encoder result. [DERIVED]

## dumb-code flags
- Date mismatch: module docstring says `CAPABILITIES-V1 (2026-09-03)` but `API_DATE = "2026-09-04"` — capabilities.py:1, 19. [DERIVED]
- Function-attribute smuggling: `_embed` stashes the query vector on `_children_of._qvec`, consumed later by `_children_of` — order-dependent, never initialized at def time; calling `_children_of` before `_embed` raises `AttributeError`. [INFERRED — attribute only set inside `_embed`] wildcard.py:57-66
- `import math` performed inside `_rerank_pairs` on every call — wildcard.py:82. [DERIVED]
- `'field-evidence'` prefix duplicated: in the SQL `LIKE 'field-evidence%%'` and in the CONTRACTS comment/key `field-evidence-corpus` — capabilities.py:31, 69. [DERIVED]
- Literal `"v1"` vs `False` mixed types for the `corpus-explorer` contract value (`"v1"` when enabled, `False` when off) — capabilities.py:78. [DERIVED]
- Docstring promises "at most three source-grounded frontier bridges" but the count is controlled by `DIVERGENT_DEFAULT_PLAN` in another module — wildcard.py:4-5, 92. [DERIVED]

## refactor notes
- CONTRACTS keys are the consumer switch: docstring mandates "a key is only ever added or versioned up" and consumers switch on CONTRACTS, "never on the name" — renaming/removing a key breaks external agents. capabilities.py:3-6, 20-33
- `ENDPOINTS`, `MCP_TOOLS`, `MCP_HIDDEN_TOOLS` are copied verbatim into the payload — any edit changes the advertised surface in one place but every consumer of `/capabilities`. capabilities.py:84-86
- Modules are imported by `orchestrator/orchestrator/api/retrieve.py`, `orchestrator/orchestrator/api/ui.py`, `orchestrator/orchestrator/main.py` — route/payload changes ripple into main app wiring. FACTS.importers
- `queries` bounds (`limit` ≤ 200, `since_h` ≤ 720) are part of the API contract; tightening them 422s existing callers. queries.py:18-20
- `wildcard_retrieve` spreads `{**fast, ...}` — renaming keys in the FAST payload (e.g. `meta`) changes the WILDCARD response shape. wildcard.py:96-100
- `fleet`'s limiter matching is substring-based (`f"[{lane['name']}]" in key`); renaming an endpoint lane breaks its limiter display. fleet.py:74-77

## VERIFY
```verify
grep -Fq 'API_DATE = "2026-09-04"' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'CAPABILITIES-V1 (2026-09-03)' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'POLYMATH_CORPUS_EXPLORER' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'ORDER BY heartbeat_at DESC NULLS LAST LIMIT 40' orchestrator/orchestrator/api/fleet.py
grep -Fq 'CORPUS_ID_REQUIRED' orchestrator/orchestrator/api/queries.py
grep -Fq 'DIVERGENT_DEFAULT_PLAN' orchestrator/orchestrator/api/wildcard.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/fleet.py
```
