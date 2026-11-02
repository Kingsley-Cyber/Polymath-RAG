# unit: orchestrator/orchestrator/api/_small-modules
anchor: orchestrator/orchestrator/api/capabilities.py:1-102

Files: `orchestrator/orchestrator/api/capabilities.py` (:1-101), `orchestrator/orchestrator/api/fleet.py` (:1-79), `orchestrator/orchestrator/api/queries.py` (:1-32), `orchestrator/orchestrator/api/wildcard.py` (:1-100).

## purpose
- capabilities.py serves `GET /capabilities`: a self-describing payload (backend, version, CONTRACTS, ENDPOINTS, MCP tools, retrieval modes) that agents probe once and then switch on CONTRACTS keys, never on the name — orchestrator/orchestrator/api/capabilities.py:1-7, :99-101 [DERIVED]
- fleet.py serves `GET /fleet`: read-only "who is doing what, how many jobs" over the provider roster, AIMD limiter state, worker heartbeats, ticket queue, enrichment coverage — no new state, no scheduling authority — orchestrator/orchestrator/api/fleet.py:1-8, :39-40 [DERIVED]
- queries.py serves `GET /queries`: the last N served queries plus per-mode p50/p95 and abstention/error counts, backed by the `query_receipts` table — orchestrator/orchestrator/api/queries.py:1-4, :17-18 [DERIVED]
- wildcard.py implements the WILDCARD retrieval mode: answer evidence comes untouched from FAST, plus at most three source-grounded frontier bridges from the latent surfaces — orchestrator/orchestrator/api/wildcard.py:1-6 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `capabilities_payload` | def | () -> dict | orchestrator/orchestrator/api/capabilities.py:91-96 | `capabilities` route (same file) |
| `capabilities` | route GET /capabilities | () -> dict | orchestrator/orchestrator/api/capabilities.py:99-101 | router mount |
| `fleet` | route GET /fleet | () -> dict | orchestrator/orchestrator/api/fleet.py:39-79 | router mount |
| `queries` | route GET /queries | (corpus_id=None, kind=None, limit=Query(20, ge=1, le=200), since_h=Query(24.0, gt=0, le=24 * 30)) -> dict | orchestrator/orchestrator/api/queries.py:17-32 | router mount |
| `wildcard_retrieve` | def | (query: str, corpus_id: str, scope=None) -> dict | orchestrator/orchestrator/api/wildcard.py:18-100 | unit importers |
| `router` (×3) | APIRouter | — | orchestrator/orchestrator/api/capabilities.py:17, orchestrator/orchestrator/api/fleet.py:17, orchestrator/orchestrator/api/queries.py:15 | unit importers |

Unit imported by: `orchestrator/orchestrator/api/retrieve.py`, `orchestrator/orchestrator/api/ui.py`, `orchestrator/orchestrator/main.py` [DERIVED — FACTS.importers]; per-symbol attribution not in FACTS.
Private helpers: `_version` orchestrator/orchestrator/api/capabilities.py:60-65, `_live_contracts` :68-88, `_lane_rows` orchestrator/orchestrator/api/fleet.py:20-36.

## contracts

**capabilities_payload** — orchestrator/orchestrator/api/capabilities.py:91-96
- out: keys `"backend": "polymath"`, `"version"` (`_version()`), `"api"` (= `API_DATE`), `"contracts"` (`_live_contracts()`), `"endpoints"`, `"mcp_tools"`, `"mcp_hidden_tools"`, `"retrieval_modes"` — :93-96 [DERIVED]
- post: `"version"` resolved once per process (`@lru_cache(maxsize=1)` on `_version`, :59) — :59-63 [DERIVED]
- post: `retrieval_modes` = `{m: MODE_GUIDE[m] for m in RETRIEVAL_MODES}` — :96 [DERIVED]

**_live_contracts** — orchestrator/orchestrator/api/capabilities.py:68-88
- out: copy of `CONTRACTS` (defaults incl. `"field-evidence-corpus": None` :31) with `field-evidence-corpus` set to newest `runs.corpus_id` where `corpus_id LIKE 'field-evidence%%'` and `status = 'query_ready'` (`ORDER BY r.updated_at DESC LIMIT 1`) — :72-81 [DERIVED]
- out: `"corpus-explorer"` = `"v1"` iff `POLYMATH_CORPUS_EXPLORER == "1"`, else `False` — :87 [DERIVED]
- post: "Best effort; never raises" — :69-71 [DERIVED]

**fleet** — orchestrator/orchestrator/api/fleet.py:39-79
- out: `{"lanes", "workers", "queue", "enrichment"}`; `enrichment` = `{"parents": <count(chunks tier='parent')>, **<parent_enrichments status counts>}` — :78-79, :66-72 [DERIVED]
- lane rows: `name`, `model`, `role` ∈ {"enrichment" (name in `stage_pin("parent_enrichment")` :25), "extraction", "dedicated"}, `structured`; `lane["limiter"]` attached when `f"[{lane['name']}]"` occurs in an `llm_controller_state.key` (key shape `'llm_cloud[groq1]'`, comment :43) — :28-35, :73-77 [DERIVED]
- worker rows: `worker_id`, `worker_type`, `status`, `processed`, `current_ticket`, `last_error`, `heartbeat_age_s` = `int(time.time() - heartbeat_at.timestamp())`; capped by SQL `LIMIT 40`, `ORDER BY heartbeat_at DESC NULLS LAST` — :49-59 [DERIVED]
- queue rows: stage/status/count for `status IN ('pending','ready','leased','failed')` — :60-65 [DERIVED]

**queries** — orchestrator/orchestrator/api/queries.py:17-32
- in: `corpus_id: Optional[str] = None`, `kind: Optional[str] = None`, `limit: int = Query(20, ge=1, le=200)`, `since_h: float = Query(24.0, gt=0, le=24 * 30)` — :18-20 [DERIVED]
- pre: corpus_id given → `require_corpus(corpus_id)` (FRIENDS-ACCESS-V1 D5) — :24-25; omitted while `allowed_corpora() is not None` → HTTP 422 — :26-27 [DERIVED]
- out: `{"corpus_id", "kind", "since_h", "count": len(rows), "summary", "queries"}` from `recent_queries` + `query_summary` — :28-32 [DERIVED]

**wildcard_retrieve** — orchestrator/orchestrator/api/wildcard.py:18-100
- pre: `corpus_id is None` → HTTPException 422 `{"error_code": "corpus_required", "message": "WILDCARD requires an explicit corpus_id"}` — :29-32 [DERIVED]
- in: FAST baseline via `fast_retrieve(query, [corpus_id], **scope_kwargs(scope))`; baseline `doc_ids`/`parent_ids`/`chunk_ids` sets built from `fast["evidence"]` — :34-43 [DERIVED]
- effect: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)`; latent search filters on `representation_kind` + `corpus_id`; child search adds `representation_kind: "routing_child"` + `parent_id` — :48, :52-61 [DERIVED]
- post: rerank logits squashed via `1.0 / (1.0 + math.exp(-float(s)))`; any missing score → `_rerank_pairs` returns `None` — :76-83 [DERIVED]
- out: `{**fast, "meta": meta, "wildcard": out["wildcard"]}` with `meta["mode"] = "WILDCARD"`, `meta["wildcard"] = out["diagnostics"]`, `meta["wildcard_plan"] = out["plan"]`; engine called with `DIVERGENT_DEFAULT_PLAN` — :85-100 [DERIVED]
- post: `finally: client.close()` — :93-94 [DERIVED]

## effect surface

Postgres — read-only; FACTS.tables_written = `[]`.

| table | use | anchor |
|---|---|---|
| `runs` | field-evidence corpus lookup | orchestrator/orchestrator/api/capabilities.py:75-81 |
| `llm_controller_state` | per-lane AIMD limiter | orchestrator/orchestrator/api/fleet.py:45-48 |
| `worker_registrations` | worker heartbeat rows | orchestrator/orchestrator/api/fleet.py:55-59 |
| `stage_tickets` | queue counts | orchestrator/orchestrator/api/fleet.py:60-65 |
| `parent_enrichments` ⋈ `chunks` | enrichment coverage | orchestrator/orchestrator/api/fleet.py:66-69 |
| `chunks` (tier='parent') | parents_total | orchestrator/orchestrator/api/fleet.py:70-72 |
| `query_receipts` (via `recent_queries`/`query_summary`) | /queries; written by /chat, /ask, /retrieve per docstring | orchestrator/orchestrator/api/queries.py:4, :28-30 |

- Qdrant: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` — orchestrator/orchestrator/api/wildcard.py:48; collections resolved via `_corpus_collections` imported from `orchestrator.api.hybrid` — :46 [DERIVED]. FACTS.collections names `polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare`, `polymath_deep_research`, `polymath_models`; in SOURCE those literals are members of `MCP_TOOLS` — orchestrator/orchestrator/api/capabilities.py:53-54 [DERIVED — FACTS/SOURCE classification mismatch].
- Subprocess: `git rev-parse --short HEAD`, `cwd=Path(__file__).resolve().parents[3]`, `timeout=5` — orchestrator/orchestrator/api/capabilities.py:62-63 [DERIVED]
- Env: `POLYMATH_CORPUS_EXPLORER` = `'0'` — orchestrator/orchestrator/api/capabilities.py:87 [DERIVED]
- Clock: `time.time()` — orchestrator/orchestrator/api/fleet.py:53 [DERIVED]
- Network: Qdrant client — orchestrator/orchestrator/api/wildcard.py:48; cross-encoder reached through `_rerank_children`, comment calls it "the sidecar" — :69-79 [INFERRED: "sidecar" implies a separate service]

## invariants
INVARIANT: len(ADAPTER_MCP_TOOLS) == 7 == comment "The seven adapter_* tools" — orchestrator/orchestrator/api/capabilities.py:46, :42-45 [DERIVED]
  fails-if: the two MCP surfaces (:42-45) stop mirroring tool names/parameters.
INVARIANT: "/capabilities" ∈ ENDPOINTS but "/fleet" ∉ ENDPOINTS and "/queries" ∉ ENDPOINTS — orchestrator/orchestrator/api/capabilities.py:34-41 vs orchestrator/orchestrator/api/fleet.py:39, orchestrator/orchestrator/api/queries.py:17 [DERIVED]
  fails-if: runtime still works, but CONTRACTS-driven agents never discover the fleet board or receipts surface.
INVARIANT: 1 ≤ queries limit ≤ 200 (default 20); 0 < since_h ≤ 24 * 30 — orchestrator/orchestrator/api/queries.py:19-20 [DERIVED]
  fails-if: unbounded scans of query_receipts.
INVARIANT: fleet workers list length ≤ 40 — orchestrator/orchestrator/api/fleet.py:59 [DERIVED]
  fails-if: board silently hides every worker beyond the 40 freshest heartbeats.
INVARIANT: wildcard bridges ≤ 3 and FAST evidence never displaced — orchestrator/orchestrator/api/wildcard.py:3-4, :35, :100 [DERIVED]
  fails-if: WILDCARD mode alters answer evidence, violating DIVERGENT-RETRIEVAL-V1.
INVARIANT: rerank scores ∈ (0,1) after `1.0 / (1.0 + math.exp(-float(s)))` — orchestrator/orchestrator/api/wildcard.py:79-83 [DERIVED]
  fails-if: raw logits compared against the support floor / multiplicative WildcardValue scale (:79-81).
INVARIANT: `_version()` constant per process (`lru_cache(maxsize=1)`) — orchestrator/orchestrator/api/capabilities.py:59 [DERIVED]
  fails-if: long-lived process reports a stale commit after a redeploy.

## determinism & idempotency
determinism: NONDETERMINISTIC (subprocess git orchestrator/orchestrator/api/capabilities.py:63; env POLYMATH_CORPUS_EXPLORER :87; db reads :75-81, orchestrator/orchestrator/api/fleet.py:42-72, orchestrator/orchestrator/api/queries.py:28-30; clock time.time orchestrator/orchestrator/api/fleet.py:53; Qdrant network + cross-encoder orchestrator/orchestrator/api/wildcard.py:48, :73)
idempotency: SAFE (all handlers read-only, FACTS.tables_written = `[]`; wildcard opens and closes its own Qdrant client per call — orchestrator/orchestrator/api/wildcard.py:48, :93-94)

## failure behaviour
- `except Exception: return "unknown"` in `_version` — git failure swallowed; payload reports `version: "unknown"` — orchestrator/orchestrator/api/capabilities.py:64-65 [DERIVED]
- `except Exception: pass` in `_live_contracts` — DB failure swallowed; `field-evidence-corpus` stays `None` — orchestrator/orchestrator/api/capabilities.py:82-83 [DERIVED]
- HTTPException 422, `error_code` `"corpus_required"` — orchestrator/orchestrator/api/wildcard.py:30-32 [DERIVED]
- HTTPException 422, `{"error_code": "CORPUS_ID_REQUIRED", "message": "name one of your libraries"}` — orchestrator/orchestrator/api/queries.py:26-27 [DERIVED]
- `_rerank_pairs` returns `None` when any candidate lacks a `rerank_score` — orchestrator/orchestrator/api/wildcard.py:76-78 [DERIVED]
- `finally: client.close()` releases Qdrant even if `divergent_retrieve` raises — orchestrator/orchestrator/api/wildcard.py:93-94 [DERIVED]

## dumb-code flags
- Module docstring dated "2026-09-03" but `API_DATE = "2026-09-04"` — orchestrator/orchestrator/api/capabilities.py:1 vs :19 [DERIVED]
- `LIKE 'field-evidence%%'` in a no-params `conn.execute` — doubled `%%` redundant — orchestrator/orchestrator/api/capabilities.py:76-79 [INFERRED: LIKE folds `%%` to `%`; looks pasted from a parametrized query]
- `corpus-explorer` value mixes types: `"v1"` (str) or `False` (bool) — orchestrator/orchestrator/api/capabilities.py:87 [DERIVED]
- Error-code casing inconsistent: `"corpus_required"` vs `"CORPUS_ID_REQUIRED"` — orchestrator/orchestrator/api/wildcard.py:31, orchestrator/orchestrator/api/queries.py:27 [DERIVED]
- `corpus_id: str` annotation yet `if corpus_id is None` guard — orchestrator/orchestrator/api/wildcard.py:18 vs :29 [DERIVED]
- `_children_of._qvec` function attribute assigned only inside `_embed`; calling `_children_of` before `_embed` reads an unset attribute — orchestrator/orchestrator/api/wildcard.py:58, :63-66 [INFERRED: sole assignment visible at :65]
- `import math` inside `_rerank_pairs` body — orchestrator/orchestrator/api/wildcard.py:82 [DERIVED]

## refactor notes
- wildcard imports three private helpers from `orchestrator.api.hybrid` (`_corpus_collections`, `_embed_query`, `_rerank_children`); renaming/moving any of them breaks wildcard — orchestrator/orchestrator/api/wildcard.py:22-27 [DERIVED]
- CONTRACTS is additive-by-design ("a key is only ever added or versioned up") and consumers switch on keys, never the backend name — removing/renaming a key breaks external agents — orchestrator/orchestrator/api/capabilities.py:4-6, :20-33 [DERIVED]
- `/capabilities` payload keys are the agent-facing contract (backend/version/api/contracts/endpoints/mcp_tools/mcp_hidden_tools/retrieval_modes) — orchestrator/orchestrator/api/capabilities.py:93-96 [DERIVED]
- Unit imported by `orchestrator/orchestrator/api/retrieve.py`, `orchestrator/orchestrator/api/ui.py`, `orchestrator/orchestrator/main.py` — router mounting and WILDCARD dispatch live outside this unit [DERIVED — FACTS.importers]
- Ticket status literal set `('pending','ready','leased','failed')` embedded in fleet SQL; must track the ticket state machine — orchestrator/orchestrator/api/fleet.py:62-64 [DERIVED]
- `_version` is lru_cached: reporting a new commit requires a process restart — orchestrator/orchestrator/api/capabilities.py:59-60 [DERIVED]

## VERIFY
```verify
grep -Fq 'API_DATE = "2026-09-04"' orchestrator/orchestrator/api/capabilities.py
test "$(grep -c -F 'capabilities_payload' orchestrator/orchestrator/api/capabilities.py)" -ge 2
grep -Fq 'ORDER BY heartbeat_at DESC NULLS LAST LIMIT 40' orchestrator/orchestrator/api/fleet.py
grep -Eq 'Query\(20, ge=1, le=200\)' orchestrator/orchestrator/api/queries.py
grep -Fq 'meta["mode"] = "WILDCARD"' orchestrator/orchestrator/api/wildcard.py
grep -Eq 'math\.exp\(-float\(s\)\)' orchestrator/orchestrator/api/wildcard.py
! grep -Fq '/fleet' orchestrator/orchestrator/api/capabilities.py
```
