# unit: orchestrator/orchestrator/api/graph.py
anchor: orchestrator/orchestrator/api/graph.py:1-286

## purpose
Production GRAPH route: one promoted HYBRID Pass-1 (`hybrid-retrieval-v1`) plus a qualified hop-1 graph expansion — orchestrator/orchestrator/api/graph.py:1-18 [DERIVED]. Returns a hierarchical synthesis context (documents → sections with summaries → exact child evidence) with graph facts as a separate `graph_relationships` lane — graph.py:11-15 [DERIVED]. Serves the api layer; the module is imported by `chat_retrieval.py`, `evidence.py`, `retrieve.py`, `ui.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `graph_retrieve` | def | `(query: str, corpus_id: str, latent: "bool \| None" = None, utility: "bool \| None" = None, scope=None) -> dict` | graph.py:81-285 | module imported by chat_retrieval.py, evidence.py, retrieve.py, ui.py (FACTS.importers; symbol per importer unknown) |
| `_selected_surfaces` | def | `(query: str, evidence: list[dict]) -> list[str]` | graph.py:56-78 | — (internal to graph.py; called at :170, :245, :278) |

## contracts

### `graph_retrieve` — graph.py:81-285
- in: `query: str`; `corpus_id: str` mandatory — `None` raises HTTP 422 `corpus_required` — graph.py:86-90 [DERIVED].
- in: `latent`, `utility` optional booleans; applied to the plan via `apply_latent(shaped, latent)` and `apply_utility(shaped, utility)` — graph.py:116-118 [DERIVED]. Comment: "GRAPH INHERITS LATENT (plan §1.5)"; an earlier wiring accepted the flag but silently dropped it — graph.py:113-115 [DERIVED].
- pre: `_begin_retrieval()` runs first, then `_ensure_fast_ready(corpus_id)` — graph.py:85, 92 [DERIVED].
- pre: pass-1 plan = `hybrid_mode_plan(MODE_GRAPH)` reshaped by `plan_for_query` with `corpus_ids: (corpus_id,)` (exactly one corpus) — graph.py:96, 109-112 [DERIVED].
- out: dict with keys `query`, `meta`, `documents`, `unassigned_rescue_evidence`, `graph_relationships`, `trace` — graph.py:231-284 [DERIVED].
- post: `meta.graph_fact_count == len(graph_relationships)` — both derive from the same `graph_facts` list — graph.py:241 vs 260-269 [INFERRED: same variable feeds both].
- post: graph lane result sliced `[:GRAPH_MAX_FACTS]` — graph.py:300 [DERIVED].

### `_selected_surfaces` — graph.py:56-78
- in: reads at most the first 10 evidence items (`evidence[:10]`) and only their `"text"` field — graph.py:67, 74-75 [DERIVED].
- out: delegates to `retrieve.seed_surfaces(query, ...)` when importable — graph.py:61-67 [DERIVED].
- out (fallback when `ImportError`): query tokens with `len(term) > 3`, evidence tokens with `len(term) > 5`, order-preserving dedup via `dict.fromkeys`, cut at 12 — graph.py:72-78 [DERIVED].

## effect surface
- Postgres read: `SELECT chunk_id, summary FROM chunks WHERE chunk_id = ANY(%s)` for section parent ids — graph.py:179-184 [DERIVED]. Tables written: none (FACTS.tables_written).
- Qdrant: client `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` for pass-1 — graph.py:99 [DERIVED]; second client `timeout=30` for the entity-card probe — graph.py:157-158 [DERIVED]. Collections from `_corpus_collections([corpus_id])` — graph.py:97 [DERIVED].
- Graph store: `graph_expand_or_502(...)` from `orchestrator.api.retrieve` — graph.py:148, 169-174 [DERIVED]; docstring names the machinery `_neo4j_expand`, so Neo4j is the backing store — graph.py:18 [INFERRED].
- Settings read: `get_settings().stores.qdrant_url` — graph.py:99, 157 [DERIVED].
- No files, no subprocesses visible.

## invariants
- INVARIANT: `len(graph_relationships)` ≤ `GRAPH_MAX_FACTS` — graph.py:300 [DERIVED]
  fails-if: response carries more facts than `meta.graph_bounds.max_facts` reports.
- INVARIANT: `trace.graph_seed_surfaces` length ≤ 8 — graph.py:278 [DERIVED]
  fails-if: trace reports more seeds than `graph_bounds.max_seeds = 8` — graph.py:238.
- INVARIANT: fallback surface count ≤ 12, matching the `retrieve.seed_surfaces` cut convention — graph.py:78 and 58-59 [DERIVED]
  fails-if: fallback and shared implementation disagree on seed input during the merge bounce window.
- INVARIANT: pass-1 Qdrant client is closed on every path (`finally: client.close()`) — graph.py:140-141 [DERIVED]
  fails-if: leaked connections per request.
- INVARIANT: every chunk in `result.final_evidence` appears exactly once across `documents[*].sections[*].evidence`, `documents[*].rescue_evidence`, or `unassigned_rescue_evidence` (tracking via `used_chunks`) — graph.py:187, 212-213, 227-229 [INFERRED: set-difference structure guarantees it]
  fails-if: evidence silently dropped, breaking the "recall safety" comment — graph.py:226-227.
- INVARIANT: pass-1 plan carries exactly one corpus (`corpus_ids: (corpus_id,)`) — graph.py:111 [DERIVED]
  fails-if: cross-corpus leak in GRAPH mode.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.time()` at graph.py:107, 139, 168, 175; network Qdrant graph.py:99, 157-160; graph store call graph.py:169; db read graph.py:179-183) [DERIVED]
idempotency: SAFE (no table writes, FACTS.tables_written empty; the only SQL is a SELECT — graph.py:180-183) [INFERRED]

## failure behaviour
- `corpus_id is None` → `HTTPException(status_code=422, detail={"error_code": "corpus_required", ...})` — graph.py:87-90 [DERIVED].
- `QdrantClient(...)` constructor `Exception` → `HTTPException(status_code=502, detail={"error_code": "qdrant_unavailable", ...})`, re-raised (`handled: raise`, FACTS.fallbacks) — graph.py:100-104 [DERIVED].
- Entity-card probe: any `Exception` swallowed, `card_seed_ids = []` — "fail-open to surface seeding" (`handled: assign`, FACTS.fallbacks) — graph.py:165-166 [DERIVED]. Caller still gets a response, seeded from surfaces only.
- `from orchestrator.api.retrieve import seed_surfaces` `ImportError` → legacy token-surface fallback kept (merge → bounce window, "D1 lesson, 2026-09-25") — graph.py:62-65, 68-78 [DERIVED].
- Graph lane failure is a typed 502 from `graph_expand_or_502`, "never an empty 'no graph knowledge' result" — graph.py:146-148, 169 [DERIVED].

## dumb-code flags
- `_selected_surfaces(query, evidence)` recomputed 3× per request (graph seeds :170, liveness :245, trace :278); only the trace copy is cut `[:8]` — graph.py:170, 245, 278 [DERIVED].
- `max_seeds` hardcoded as `8` in `graph_bounds` while `max_facts` uses the shared constant `GRAPH_MAX_FACTS` — graph.py:238 [DERIVED].
- Magic numbers: Qdrant `timeout=60` (:99) vs card-probe `timeout=30` (:158); `evidence[:10]` (:67, :74); token length thresholds `> 3` / `> 5` (:72, :76); dedup cut `[:12]` (:78); `round(v, 6)` for rrf (:221); `round(..., 1)` for latency (:280-282) [DERIVED].
- In-function imports duplicate the module-level import source: `hybrid_retrieve` (:94) although `HybridRetrievalPlan` already comes from `polymath_shared.hybrid` at :55; `apply_latent` (:108) and `apply_utility` (:117) although `polymath_shared.retrieval_modes` is imported at :30-35 [DERIVED].
- Two Qdrant clients opened per request (pass-1 :99, card probe :157) instead of reuse [DERIVED].
- Circular import with `orchestrator.api.retrieve`: graph.py imports from it (:61, :148) while FACTS.importers lists `retrieve.py` as an importer of graph.py [INFERRED: both directions visible; the :62-65 ImportError fallback exists to survive it].

## refactor notes
- `graph_retrieve` signature and response shape (`meta`, `documents`, `unassigned_rescue_evidence`, `graph_relationships`, `trace`) are consumed by 4 modules (FACTS.importers: chat_retrieval.py, evidence.py, retrieve.py, ui.py) — renaming keys breaks them — graph.py:81-285 [DERIVED].
- Depends on private helpers of `orchestrator.api.fast`: `_begin_retrieval`, `_embed_query`, `_ensure_fast_ready`, `_neighbor_lookup`, `_region_lookup`, `_liveness`, `_rerank_children`, `_corpus_collections`, `degradations`, `FastSearcher`, `entity_card_probe` (FACTS.imports) — renaming in fast.py breaks this file — graph.py:40-51, 156 [DERIVED].
- `retrieve.seed_surfaces` and `retrieve.graph_expand_or_502` are load-bearing cross-module contracts; the ImportError fallback at :62-65 only covers `seed_surfaces`, not `graph_expand_or_502` (:148 raises on missing) [INFERRED].
- `GRAPH_MAX_FACTS`, `MODE_GRAPH`, `GRAPH_PLAN_VERSION`, `hybrid_mode_plan` come from `polymath_shared.retrieval_modes`; changing the constant changes both the slice (:300) and `meta.graph_bounds` (:238) — graph.py:30-35 [DERIVED].
- `latent`/`utility` must keep flowing into `apply_latent`/`apply_utility` (:116-118); a past wiring dropped them silently (B5 diagnostics) — graph.py:113-115 [DERIVED].

## VERIFY
```verify
grep -Fq 'def graph_retrieve(query: str, corpus_id: str,' orchestrator/orchestrator/api/graph.py
grep -Fq 'error_code": "corpus_required' orchestrator/orchestrator/api/graph.py
grep -Fq 'timeout=60' orchestrator/orchestrator/api/graph.py
grep -Fq 'card_seed_ids = []' orchestrator/orchestrator/api/graph.py
grep -Fq 'graph_bounds": {"max_seeds": 8, "max_facts": GRAPH_MAX_FACTS}' orchestrator/orchestrator/api/graph.py
grep -Fq '[:GRAPH_MAX_FACTS]' orchestrator/orchestrator/api/graph.py
grep -Fq 'return list(dict.fromkeys(surfaces))[:12]' orchestrator/orchestrator/api/graph.py
```
