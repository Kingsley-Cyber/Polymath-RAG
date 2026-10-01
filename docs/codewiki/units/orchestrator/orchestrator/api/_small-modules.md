# unit: orchestrator/orchestrator/api/_small-modules
anchor: orchestrator/orchestrator/api/capabilities.py:1-86

## purpose
Four small API modules: `/capabilities` advertises what this Polymath is (contracts, endpoints, MCP tools) so agents "switch on CONTRACTS (never on the name)" — orchestrator/orchestrator/api/capabilities.py:1-6 [DERIVED]. `/fleet` is a read-only control-plane board (lanes, workers, queue, enrichment) — orchestrator/orchestrator/api/fleet.py:1-8 [DERIVED]. `/queries` is the QUERY-RECEIPTS-V1 read surface over `query_receipts` — orchestrator/orchestrator/api/queries.py:1-4 [DERIVED]. `wildcard_retrieve` wires live stores + cross-encoder into the DIVERGENT-RETRIEVAL-V1 wildcard lane — orchestrator/orchestrator/api/wildcard.py:1-6 [DERIVED].

## public surface
Unit-level importers (FACTS.importers): orchestrator/orchestrator/api/retrieve.py, orchestrator/orchestrator/api/ui.py, orchestrator/orchestrator/main.py.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| capabilities_payload | def | () -> dict | orchestrator/orchestrator/api/capabilities.py:78-80 | — (unit importers above) |
| capabilities | route GET /capabilities | () -> dict | orchestrator/orchestrator/api/capabilities.py:83-85 | — |
| fleet | route GET /fleet | () -> dict | orchestrator/orchestrator/api/fleet.py:39-79 | — |
| queries | route GET /queries | (corpus_id, kind, limit, since_h) -> dict | orchestrator/orchestrator/api/queries.py:17-32 | — |
| wildcard_retrieve | def | (query: str, corpus_id: str, scope=None) -> dict | orchestrator/orchestrator/api/wildcard.py:18-100 | retrieve.py [INFERRED: retrieval helper, retrieve.py is a unit importer] |
| _version, _live_contracts, _lane_rows | def (private) | — | capabilities.py:47-52, 55-75; fleet.py:20-36 | internal only |

## contracts
**capabilities_payload** — capabilities.py:78-80
- in: none. pre: none.
- out: `{"backend": "polymath", "version": _version(), "api": API_DATE, "contracts": _live_contracts(), "endpoints": list(ENDPOINTS), "mcp_tools": list(MCP_TOOLS)}` — capabilities.py:79-80, with `API_DATE = "2026-09-04"` at capabilities.py:19 [DERIVED].
- post: `_live_contracts` "Best effort; never raises" — capabilities.py:57-58; `_version` returns `"unknown"` on any exception — capabilities.py:51-52.

**queries** — queries.py:17-32
- in: `corpus_id: Optional[str] = None`, `kind: Optional[str] = None`, `limit: int = Query(20, ge=1, le=200)`, `since_h: float = Query(24.0, gt=0, le=24 * 30)` — queries.py:18-20 [DERIVED].
- pre: `corpus_id` given → `require_corpus(corpus_id)` (FRIENDS-ACCESS-V1 D5) — queries.py:24-25; no corpus_id and `allowed_corpora() is not None` → HTTPException 422 `CORPUS_ID_REQUIRED` — queries.py:26-27 [DERIVED].
- out: `{"corpus_id", "kind", "since_h", "count": len(rows), "summary", "queries": rows}` — queries.py:31-32 [DERIVED].

**fleet** — fleet.py:39-79
- in: none. pre: none.
- out: `{"lanes": [...], "workers": [...], "queue": [{"stage","status","count"}...], "enrichment": {"parents": parents_total, **status_counts}}` — fleet.py:78-79 [DERIVED]; a lane gets a `"limiter"` key only when `f"[{lane['name']}]" in key` matches a controller key — fleet.py:73-76 [DERIVED].

**wildcard_retrieve** — wildcard.py:18-100
- in: `query: str, corpus_id: str, scope=None`. pre: `corpus_id is None` → HTTPException 422 `{"error_code": "corpus_required", ...}` — wildcard.py:29-32 [DERIVED].
- out: `{**fast, "meta": {**fast.meta, "mode": "WILDCARD", "wildcard": diagnostics, "wildcard_plan": plan}, "wildcard": out["wildcard"]}` — wildcard.py:96-100 [DERIVED].
- post: rerank logits squashed via `1.0 / (1.0 + math.exp(-float(s)))` — wildcard.py:79-83; Qdrant client closed in `finally` — wildcard.py:93-94 [DERIVED].

## effect surface
| effect | detail | anchor |
|---|---|---|
| Postgres read | `runs` (latest `field-evidence%` corpus with `status = 'query_ready'`) | capabilities.py:63-67 |
| Postgres read | `llm_controller_state`, `worker_registrations` (LIMIT 40), `stage_tickets` (statuses `pending/ready/leased/failed`), `parent_enrichments` JOIN `chunks`, `chunks` (`tier='parent'`) | fleet.py:46, 56-59, 62-65, 66-69, 70-72 |
| Postgres read | `query_receipts` via `recent_queries`/`query_summary` (polymath_shared.query_receipts) | queries.py:4, 29-30 |
| Postgres write | none (FACTS tables_written: []) | — |
| Qdrant | `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)`, filters on `representation_kind`/`corpus_id`/`parent_id` | wildcard.py:48, 52-61 |
| subprocess | `git rev-parse --short HEAD`, `timeout=5`, cwd = `Path(__file__).resolve().parents[3]` | capabilities.py:49-50 |
| env read | `POLYMATH_CORPUS_EXPLORER` default `'0'`; `"1"` → contracts `"corpus-explorer": "v1"` else `False` | capabilities.py:74 |
| network | cross-encoder rerank sidecar via `_rerank_children` [INFERRED: comment names "the sidecar"] | wildcard.py:69-73, 79 |

## invariants
INVARIANT: len(MCP_TOOLS) == 17 (10 base names + 7 ADAPTER_MCP_TOOLS) — capabilities.py:41-43 [DERIVED]
  fails-if: advertised MCP tool list drifts from the two MCP servers pinned by tests/contracts/test_mcp_adapter_parity.py — capabilities.py:37-40.
INVARIANT: len(ENDPOINTS) == 13 — capabilities.py:34-36 [DERIVED]
  fails-if: consumers probing ENDPOINTS hit missing routes.
INVARIANT: `_live_contracts()` returns `dict(CONTRACTS)` plus at most overrides of `"field-evidence-corpus"` and `"corpus-explorer"` — capabilities.py:59, 67-68, 74 [DERIVED]
  fails-if: removing/renaming a key breaks additive-only contract consumers — capabilities.py:6.
INVARIANT: `"field-evidence-corpus"` is `None` or a `query_ready` corpus_id matching `field-evidence%` — capabilities.py:31, 63-68 [DERIVED]
  fails-if: clients route to a corpus that is not query-ready.
INVARIANT: queries `limit` ∈ [1, 200] default 20; `since_h` ∈ (0, 720] default 24.0 — queries.py:19-20 [DERIVED]
  fails-if: FastAPI 422 validation error before any DB work.
INVARIANT: response `"count"` == len(response `"queries"`) — queries.py:31-32 [DERIVED]
  fails-if: UI paging math breaks.
INVARIANT: fleet workers list length ≤ 40 (`LIMIT 40`) — fleet.py:59 [DERIVED]
  fails-if: board silently hides active workers.
INVARIANT: `heartbeat_age_s` == `int(time.time() - heartbeat_at)` or `None` — fleet.py:53-54 [DERIVED]
  fails-if: clock skew yields negative ages.
INVARIANT: `_version()` cached per process (`@lru_cache(maxsize=1)`) — capabilities.py:46 [DERIVED]
  fails-if: long-lived process reports a stale commit after deploy.
INVARIANT: wildcard return is the FAST payload untouched, plus meta/wildcard keys — wildcard.py:2-3, 100 [DERIVED]
  fails-if: mutating FAST keys breaks "wildcard NEVER displaces it" consumers.

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess git rev-parse — capabilities.py:50; clock `time.time` — fleet.py:53; db reads of runs/llm_controller_state/worker_registrations/stage_tickets/parent_enrichments/chunks/query_receipts — capabilities.py:63-67, fleet.py:46-72, queries.py:29-30; env `POLYMATH_CORPUS_EXPLORER` — capabilities.py:74; Qdrant network — wildcard.py:48)
idempotency: SAFE — all four modules are read-only against Postgres (FACTS tables_written: []) and wildcard closes its own Qdrant client — wildcard.py:93-94.

## failure behaviour
- `_version`: `except Exception` → `return "unknown"` (SWALLOWED) — capabilities.py:51-52; caller sees `version: "unknown"` [DERIVED].
- `_live_contracts`: `except Exception` → `pass` (SWALLOWED) — capabilities.py:69-70; caller sees static CONTRACTS with `"field-evidence-corpus": None`. The `corpus-explorer` env line sits outside the try, so it is always set — capabilities.py:74 [DERIVED].
- queries: 422 `{"error_code": "CORPUS_ID_REQUIRED", "message": "name one of your libraries"}` — queries.py:27; `require_corpus` may raise (behaviour lives in orchestrator.web_scope, not visible here) — queries.py:25 [DERIVED].
- wildcard: 422 `{"error_code": "corpus_required", "message": "WILDCARD requires an explicit corpus_id"}` — wildcard.py:30-32 [DERIVED].
- `_rerank_pairs` returns `None` when any rerank score is missing — wildcard.py:76-78; handling belongs to `divergent_retrieve` in polymath_shared.divergent — wildcard.py:85-92 [DERIVED].
- wildcard frontier exceptions still close the Qdrant client (`finally`) — wildcard.py:93-94 [DERIVED].

## dumb-code flags
- Date drift: module docstring "CAPABILITIES-V1 (2026-09-03)" vs `API_DATE = "2026-09-04"` — capabilities.py:1 vs 19 [DERIVED].
- None-check on a `str`-annotated param: `if corpus_id is None` under `corpus_id: str` — wildcard.py:18, 29 [DERIVED].
- Hidden coupling via function attribute: `_embed` writes `_children_of._qvec`; `_children_of` reads it — wildcard.py:57-66. If `divergent_retrieve` calls `_children_of` before `_embed`, AttributeError [INFERRED: no default value is ever set].
- Lane↔limiter join by substring `f"[{lane['name']}]" in key` — fleet.py:75; a lane name that is a substring of another lane's key would steal its limiter state [INFERRED: pure substring match].
- SQL literal `LIKE 'field-evidence%%'` with doubled `%%` in a non-parameterized execute — capabilities.py:65 [INFERRED: only meaningful if the driver escapes `%`].
- Magic numbers: `timeout=5` — capabilities.py:50; `timeout=60` — wildcard.py:48; `LIMIT 40` — fleet.py:59; hardcoded ticket statuses `('pending','ready','leased','failed')` — fleet.py:63-64 [DERIVED].
- Lazy imports inside function bodies: capabilities.py:61, fleet.py:21-24, queries.py:21-23, wildcard.py:19-27, plus `import math` mid-function — wildcard.py:82 [DERIVED].

## refactor notes
- CONTRACTS/ENDPOINTS/MCP_TOOLS are an external contract: consumers "switch on CONTRACTS (never on the name)" and "a key is only ever added or versioned up" — capabilities.py:3-6. Key renames/version bumps break unknown external consumers.
- ADAPTER_MCP_TOOLS names are pinned by tests/contracts/test_mcp_adapter_parity.py across two MCP surfaces (orchestrator/orchestrator/mcp_server.py :8930 bearer, mcp_server/polymath_mcp.py stdio) — capabilities.py:37-40. Renames break parity test GOVERNED-CONVERGENCE-V1 TG1.
- wildcard imports private hybrid helpers `_corpus_collections`, `_embed_query`, `_rerank_children` — wildcard.py:23-27; any refactor of orchestrator/api/hybrid.py internals breaks wildcard.
- wildcard output shape merges the FAST payload with meta overrides `"mode": "WILDCARD"`, `"wildcard"`, `"wildcard_plan"` — wildcard.py:96-100; WILDCARD callers depend on both key sets.
- queries depends on `require_corpus`/`allowed_corpora` semantics (FRIENDS-ACCESS-V1 D5) from orchestrator.web_scope — queries.py:23-27.
- `_lane_rows` depends on pool introspection: `stage_pin("parent_enrichment")`, `cloud_endpoints()`, attrs `dedicated`/`structured` — fleet.py:21-36.
- Route paths `/capabilities`, `/fleet`, `/queries` are consumed by the unit importers retrieve.py, ui.py, main.py (FACTS.importers); renaming any path touches all three.

## VERIFY
```verify
grep -Fq 'API_DATE = "2026-09-04"' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'POLYMATH_CORPUS_EXPLORER' orchestrator/orchestrator/api/capabilities.py
grep -Fq 'LIMIT 40' orchestrator/orchestrator/api/fleet.py
grep -Fq 'CORPUS_ID_REQUIRED' orchestrator/orchestrator/api/queries.py
grep -Fq 'WILDCARD requires an explicit corpus_id' orchestrator/orchestrator/api/wildcard.py
! grep -Fq 'INSERT' orchestrator/orchestrator/api/fleet.py
test "$(grep -c -F 'v1' orchestrator/orchestrator/api/capabilities.py)" -ge 5
```
