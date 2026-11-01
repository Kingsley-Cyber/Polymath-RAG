# unit: orchestrator/orchestrator/api/_small-modules
anchor: orchestrator/orchestrator/api/capabilities.py:1-97

## purpose
Four small API modules: `capabilities.py` publishes what this Polymath instance is (contracts, endpoints, MCP tool lists) at `GET /capabilities` for agents/skills; `fleet.py` serves read-only fleet state at `GET /fleet`; `queries.py` serves the query-receipts read surface at `GET /queries`; `wildcard.py` implements the WILDCARD retrieval mode on top of FAST evidence plus frontier bridges. — capabilities.py:1-6 [DERIVED], fleet.py:1-7 [DERIVED], queries.py:1-4 [DERIVED], wildcard.py:1-6 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `capabilities` | route handler | GET `/capabilities` () -> dict | capabilities.py:94-96 | unit importers: retrieve.py, ui.py, main.py (FACTS.importers) [DERIVED] |
| `capabilities_payload` | def | () -> dict | capabilities.py:86-91 | retrieve.py / ui.py / main.py (unit importers; exact per-module split unknown) [DERIVED] |
| `fleet` | route handler | GET `/fleet` () -> dict | fleet.py:39-40 | ui.py / main.py (unit importers) [DERIVED] |
| `queries` | route handler | GET `/queries` (corpus_id, kind, limit, since_h) -> dict | queries.py:17-20 | main.py (router mount, unit importers) [DERIVED] |
| `wildcard_retrieve` | def | (query: str, corpus_id: str, scope=None) -> dict | wildcard.py:18 | retrieve.py — wildcard.py registers no route, so a sibling module must call it [INFERRED: no router in this file, and retrieve.py imports the unit] |
| `_version` | def (private) | () -> str | capabilities.py:54-55 | — |
| `_live_contracts` | def (private) | () -> dict | capabilities.py:63 | — |
| `_lane_rows` | def (private) | () -> list[dict] | fleet.py:20 | — |

## contracts

**capabilities_payload** (capabilities.py:86-91)
- in: no args.
- out: dict with keys exactly `"backend": "polymath"`, `"version"`, `"api"`, `"contracts"`, `"endpoints"`, `"mcp_tools"`, `"mcp_hidden_tools"`, `"retrieval_modes"` — capabilities.py:88-91 [DERIVED]
- post: `retrieval_modes = {m: MODE_GUIDE[m] for m in RETRIEVAL_MODES}` — capabilities.py:91 [DERIVED]
- post: `contracts["corpus-explorer"] == "v1"` iff `POLYMATH_CORPUS_EXPLORER == "1"`, else `False` — capabilities.py:82 [DERIVED]
- post: `contracts["field-evidence-corpus"]` = latest `runs.corpus_id` matching `LIKE 'field-evidence%'` with `status = 'query_ready'`, else stays `None` — capabilities.py:72-76, 31 [DERIVED]

**fleet** (fleet.py:40-79)
- in: no args.
- out: keys `"lanes"`, `"workers"`, `"queue"`, `"enrichment"` — fleet.py:78-79 [DERIVED]
- out: each lane has `role` = `"enrichment"` if name in `stage_pin("parent_enrichment")`, else `"extraction"` if not `dedicated`, else `"dedicated"` — fleet.py:31-33 [DERIVED]
- out: `workers` ≤ 40 rows, ordered `heartbeat_at DESC NULLS LAST` — fleet.py:59 [DERIVED]
- out: `enrichment = {"parents": <count of chunks tier='parent'>, **<status:count from parent_enrichments JOIN chunks ON chunk_id = parent_id>}` — fleet.py:66-71, 79 [DERIVED]

**queries** (queries.py:18-32)
- in: `corpus_id: Optional[str] = None`, `kind: Optional[str] = None`, `limit: int = Query(20, ge=1, le=200)`, `since_h: float = Query(24.0, gt=0, le=24 * 30)` — queries.py:18-20 [DERIVED]
- pre: if `corpus_id` given → `require_corpus(corpus_id)` — queries.py:24-25 [DERIVED]
- pre: if `corpus_id` absent and `allowed_corpora() is not None` → HTTP 422 `{"error_code": "CORPUS_ID_REQUIRED", ...}` — queries.py:26-27 [DERIVED]
- out: keys `corpus_id`, `kind`, `since_h`, `count = len(rows)`, `summary`, `queries` — queries.py:31-32 [DERIVED]

**wildcard_retrieve** (wildcard.py:18-100)
- pre: `corpus_id is None` → HTTP 422 `{"error_code": "corpus_required", "message": "WILDCARD requires an explicit corpus_id"}` — wildcard.py:29-32 [DERIVED]
- post: answer evidence is plain FAST output (`fast_retrieve`), wildcard never displaces it — wildcard.py:34-35, 4-5 [DERIVED]
- post: result = `{**fast, "meta": meta, "wildcard": out["wildcard"]}` with `meta["mode"] == "WILDCARD"`, `meta["wildcard"]` = diagnostics, `meta["wildcard_plan"]` = plan — wildcard.py:96-100 [DERIVED]
- post: rerank scores squashed via sigmoid `1.0 / (1.0 + math.exp(-s))` — wildcard.py:83 [DERIVED]

## effect surface

| kind | item | anchor |
|---|---|---|
| Postgres read | `runs` (field-evidence corpus lookup) | capabilities.py:72-74 [DERIVED] |
| Postgres read | `llm_controller_state` | fleet.py:45-46 [DERIVED] |
| Postgres read | `worker_registrations` | fleet.py:55-59 [DERIVED] |
| Postgres read | `stage_tickets` (statuses pending/ready/leased/failed) | fleet.py:60-64 [DERIVED] |
| Postgres read | `parent_enrichments` JOIN `chunks` | fleet.py:66-68 [DERIVED] |
| Postgres read | `chunks` (tier='parent' count) | fleet.py:70-71 [DERIVED] |
| Postgres read | `query_receipts` via shared `recent_queries`/`query_summary` | queries.py:3, 29-30 [DERIVED] |
| Postgres write | none (FACTS tables_written: []) | FACTS.tables_written [DERIVED] |
| Qdrant | `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)`, closed in `finally`; filtered searches on `representation_kind` incl. `"routing_child"` | wildcard.py:48, 53-61, 93-94 [DERIVED] |
| subprocess | `git rev-parse --short HEAD`, `timeout=5`, `cwd=Path(__file__).resolve().parents[3]` | capabilities.py:57-58 [DERIVED] |
| env flag | `POLYMATH_CORPUS_EXPLORER = '0'` (default) | capabilities.py:82 [DERIVED] |
| clock | `time.time()` for `heartbeat_age_s` | fleet.py:53 [DERIVED] |

## invariants
INVARIANT: `len(MCP_HIDDEN_TOOLS) == 4` (`compile_plan`, `retrieve_evidence`, `retrieve`, `ask`) — capabilities.py:51 [DERIVED]
  fails-if: hidden-but-still-answering tools silently vanish from the capabilities payload agents switch on.
INVARIANT: `len(ADAPTER_MCP_TOOLS) == 7` and all seven appear in `MCP_TOOLS` — capabilities.py:43, 50 [DERIVED]
  fails-if: adapter parity between the two MCP surfaces breaks (comment cites tests/contracts/test_mcp_adapter_parity.py, capabilities.py:41).
INVARIANT: `len(ENDPOINTS) == 22` — capabilities.py:34-38 [DERIVED]
  fails-if: advertised endpoint list disagrees with actually mounted routes.
INVARIANT: `workers` row count ≤ 40 — fleet.py:59 [DERIVED]
  fails-if: UI board pagination assumptions change.
INVARIANT: `1 <= limit <= 200` and `0 < since_h <= 720` — queries.py:19-20 [DERIVED]
  fails-if: receipt window queries return unbounded results.
INVARIANT: `_version()` is constant per process (`@lru_cache(maxsize=1)`) — capabilities.py:54 [DERIVED]
  fails-if: long-running server keeps reporting a stale git sha after deploy.
INVARIANT: wildcard output `meta["mode"] == "WILDCARD"` and FAST evidence keys survive the merge `{**fast, ...}` — wildcard.py:97, 100 [DERIVED]
  fails-if: consumers keying on FAST evidence fields lose them.

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess git call capabilities.py:58; env `POLYMATH_CORPUS_EXPLORER` capabilities.py:82; `time.time` fleet.py:53; Postgres reads capabilities.py:70-74, fleet.py:42-71, queries.py:29-30; Qdrant network wildcard.py:48)
idempotency: SAFE (all four modules are read-only; FACTS tables_written is empty)

## failure behaviour
- capabilities.py:59 — any `Exception` in the git subprocess → swallowed, `_version()` returns `"unknown"`; `/capabilities` still serves with `version: "unknown"` — capabilities.py:59-60 [DERIVED]
- capabilities.py:77 — any `Exception` in the field-evidence DB lookup → swallowed (`pass`); `contracts["field-evidence-corpus"]` stays `None` — capabilities.py:77-78, 31 [DERIVED]
- queries.py:27 — raises HTTP 422 `error_code "CORPUS_ID_REQUIRED"` when corpus_id omitted under a restricted scope — queries.py:26-27 [DERIVED]
- wildcard.py:30-32 — raises HTTP 422 `error_code "corpus_required"` when `corpus_id is None` — wildcard.py:29-32 [DERIVED]
- wildcard.py:93-94 — Qdrant client is closed in `finally`; rerank returning missing scores yields `None` from `_rerank_pairs` (no exception) — wildcard.py:75-78, 93 [DERIVED]

## dumb-code flags
- Date mismatch: module docstring says `CAPABILITIES-V1 (2026-09-03)` but `API_DATE = "2026-09-04"` — capabilities.py:1 vs 19 [DERIVED]
- Hidden side-channel: `_embed` stashes the query vector on `_children_of._qvec`; `_children_of` reads it, and the attribute is never initialized in this file — calling `_children_of` before `_embed` raises `AttributeError` — wildcard.py:57-66 [DERIVED]
- Substring limiter matching: `f"[{lane['name']}]" in key` — a lane name that is a substring of another lane's key suffix can bind the wrong limiter state — fleet.py:73-77 [DERIVED, collision risk INFERRED]
- Function-level `import math` inside `_rerank_pairs` — wildcard.py:82 [DERIVED]
- Inconsistent error-code casing across sibling modules: `"CORPUS_ID_REQUIRED"` (queries.py:27) vs `"corpus_required"` (wildcard.py:31) [DERIVED]
- Analyzer artifact: FACTS.collections lists `polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare`, `polymath_deep_research`, `polymath_models` anchored at capabilities.py:48-49 — those lines are the `MCP_TOOLS` literal, not Qdrant collection reads — capabilities.py:48-49 [DERIVED]

## refactor notes
- `CONTRACTS`, `ENDPOINTS`, `MCP_TOOLS`, `MCP_HIDDEN_TOOLS`, `ADAPTER_MCP_TOOLS` are agent-facing literals served by `GET /capabilities`; consumers switch on keys, never names — any rename/change breaks external agents and the parity tests named at capabilities.py:41, 47 [DERIVED]
- wildcard.py imports private helpers `_corpus_collections`, `_embed_query`, `_rerank_children` from `orchestrator.api.hybrid` — renaming those in hybrid.py breaks wildcard at import time — wildcard.py:23-27 [DERIVED]
- wildcard.py also depends on `FastSearcher`, `fast_retrieve` from `orchestrator.api.fast` and on `scope_kwargs` semantics ("pass a role scope only when it narrows") — wildcard.py:22, 15 [DERIVED]
- fleet response keys (`lanes`, `workers`, `queue`, `enrichment`, `heartbeat_age_s`) are consumed by the UI importer ui.py — key renames break the board — fleet.py:49-53, 78-79 [DERIVED]
- The error strings `"CORPUS_ID_REQUIRED"` and `"corpus_required"` are API-visible literals; unify only together with client updates — queries.py:27, wildcard.py:31 [DERIVED]
- `_version` is `lru_cache`d per process; a deploy strategy that expects fresh shas from a running server must account for that — capabilities.py:54 [DERIVED]

## VERIFY
```verify
grep -Fq 'API_DATE = "2026-09-04"' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'POLYMATH_CORPUS_EXPLORER' orchestrator/orchestrator/api/capabilities.py
grep -Fq '["adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status", "adapter_result", "adapter_cancel"]' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'heartbeat_at DESC NULLS LAST LIMIT 40' orchestrator/orchestrator/api/fleet.py
grep -Fq 'CORPUS_ID_REQUIRED' orchestrator/orchestrator/api/queries.py
grep -Fq 'WILDCARD requires an explicit corpus_id' orchestrator/orchestrator/api/wildcard.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/queries.py
```
