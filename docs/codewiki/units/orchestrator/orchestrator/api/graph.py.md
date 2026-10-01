# unit: orchestrator/orchestrator/api/graph.py
anchor: orchestrator/orchestrator/api/graph.py:1-277

## purpose
Production GRAPH retrieval route: one promoted HYBRID Pass-1 (hybrid-retrieval-v1, lexical on, MMR off) plus an evidence-authorized, corpus-authorized canonical bidirectional hop1 graph expansion — orchestrator/orchestrator/api/graph.py:1-18 [DERIVED]. Returns hierarchical synthesis context (document summary → section summaries → exact child evidence) with graph facts as a separate lane, never conflated — orchestrator/orchestrator/api/graph.py:11-15, 168-169 [DERIVED]. Consumed by the orchestrator API layer (chat_retrieval, evidence, retrieve, ui per FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `graph_retrieve` | def | (query: str, corpus_id: str, latent: "bool \| None" = None, utility: "bool \| None" = None, scope=None) -> dict | orchestrator/orchestrator/api/graph.py:72-276 | orchestrator/orchestrator/api/chat_retrieval.py, evidence.py, retrieve.py, ui.py (FACTS.importers) |
| `_selected_surfaces` | def | (query: str, evidence: list[dict]) -> list[str] | orchestrator/orchestrator/api/graph.py:56-69 | internal only (called at :161, :236, :269) |

## contracts

### graph_retrieve
- in: `corpus_id` required — `None` → 422 `corpus_required` — orchestrator/orchestrator/api/graph.py:77-81 [DERIVED]
- in: `latent`/`utility` flags applied to the shaped plan via `apply_latent` / `apply_utility` — orchestrator/orchestrator/api/graph.py:107, 109 [DERIVED]
- in: `scope` forwarded through `scope_kwargs(scope)` into `FastSearcher`, `_lexical_search`, `entity_card_probe` — orchestrator/orchestrator/api/graph.py:97, 124, 152 [DERIVED]
- pre: `_begin_retrieval()` and `_ensure_fast_ready(corpus_id)` must pass — orchestrator/orchestrator/api/graph.py:76, 83 [DERIVED]
- pre: Qdrant client constructible, else 502 `qdrant_unavailable` — orchestrator/orchestrator/api/graph.py:89-95 [DERIVED]
- out: dict with keys `query`, `meta`, `documents`, `unassigned_rescue_evidence`, `graph_relationships`, `trace` — orchestrator/orchestrator/api/graph.py:222-275 [DERIVED]
- out: `graph_relationships` items carry exactly `fact_id`, `predicate`, `subject_id`, `subject`, `object_id`, `object` — orchestrator/orchestrator/api/graph.py:253-258 [DERIVED]
- out: `meta.graph_bounds = {"max_seeds": 8, "max_facts": GRAPH_MAX_FACTS}` — orchestrator/orchestrator/api/graph.py:229 [DERIVED]
- post: graph facts sliced `[:GRAPH_MAX_FACTS]` — orchestrator/orchestrator/api/graph.py:165 [DERIVED]
- post: both Qdrant clients closed on all paths via `finally` — orchestrator/orchestrator/api/graph.py:131-132, 153-154 [DERIVED]

### _selected_surfaces
- in: query terms kept when `len(term) > 3`; evidence terms (first `evidence[:10]` chunks) when `len(term) > 5` — orchestrator/orchestrator/api/graph.py:63, 65, 67 [DERIVED]
- out: order-preserving dedup, capped `[:12]` — orchestrator/orchestrator/api/graph.py:69 [DERIVED]

## effect surface
- Postgres read: `SELECT chunk_id, summary FROM chunks WHERE chunk_id = ANY(%s)` inside `tx()` — orchestrator/orchestrator/api/graph.py:170-174 [DERIVED]
- Postgres write: none (FACTS.tables_written empty)
- Qdrant: two clients to `get_settings().stores.qdrant_url` — timeout=60 main — orchestrator/orchestrator/api/graph.py:90 [DERIVED]; timeout=30 entity-card probe — orchestrator/orchestrator/api/graph.py:148-149 [DERIVED]; searches via `FastSearcher` (:97) and `entity_card_probe` over collections from `_corpus_collections([corpus_id])` (:88, :151-152); card lane documented as "dense+sparse over routing_entity" — orchestrator/orchestrator/api/graph.py:143 [DERIVED]
- Graph store: expansion delegated to `graph_expand_or_502`; comment states "a Neo4j failure is a typed 502" — orchestrator/orchestrator/api/graph.py:136-138 [INFERRED: the Neo4j call happens inside orchestrator.api.retrieve, not in this file]
- Env/settings: `get_settings()` (qdrant URL) — orchestrator/orchestrator/api/graph.py:90, 148 [DERIVED]
- Clock: `time.time()` ×4 — orchestrator/orchestrator/api/graph.py:98, 130, 159, 166 (FACTS.nondeterminism) [DERIVED]

## invariants
INVARIANT: len(graph_facts) ≤ GRAPH_MAX_FACTS — slice at orchestrator/orchestrator/api/graph.py:165 [DERIVED]; docstring says "20-fact caps" (:8) so GRAPH_MAX_FACTS == 20 [INFERRED: docstring is the only place 20 appears]
  fails-if: `graph_relationships` and `meta.graph_fact_count` exceed the documented cap.
INVARIANT: len(seed surfaces) ≤ 12 — orchestrator/orchestrator/api/graph.py:69 [DERIVED]
  fails-if: unbounded seed-surface input into `graph_expand_or_502` (:161).
INVARIANT: `meta.graph_bounds.max_seeds` == 8 == docstring "8-seed" cap — orchestrator/orchestrator/api/graph.py:229 vs :8 [DERIVED]
  fails-if: reported bounds disagree with the expansion actually performed.
INVARIANT: evidence partition — every `final_evidence` chunk lands in section evidence, its document's `rescue_evidence`, or `unassigned_rescue_evidence` (tracked via `used_chunks`) — orchestrator/orchestrator/api/graph.py:178-220 [DERIVED]
  fails-if: silent evidence loss, violating the recall-safety HYBRID invariant at :216-217.
INVARIANT: trace `graph_seed_surfaces` ≤ 8 while the surfaces passed to expansion can be 12 — orchestrator/orchestrator/api/graph.py:269 vs :69, :161 [DERIVED]
  fails-if: trace no longer reflects the full seed-surface input.
INVARIANT: `rerank_children` wired only when `shaped.rerank_enabled`; `latent_rescue` only when `shaped.latent_enabled` — orchestrator/orchestrator/api/graph.py:125, 128 [DERIVED]
  fails-if: rerank/rescue lanes run against a plan that disabled them.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.time()` at orchestrator/orchestrator/api/graph.py:98, 130, 159, 166 → `latency_ms.pass1/graph/total` at :270-273)
idempotency: SAFE (read-only: no table writes, single chunks SELECT — orchestrator/orchestrator/api/graph.py:170-174; FACTS.tables_written empty)

## failure behaviour
- `corpus_id is None` → `HTTPException` 422, `error_code: "corpus_required"` — orchestrator/orchestrator/api/graph.py:77-81 [DERIVED]
- `QdrantClient(...)` raises → re-raised as `HTTPException` 502, `error_code: "qdrant_unavailable"`, chained `from exc` (FACTS.fallbacks "handled: raise" :91) — orchestrator/orchestrator/api/graph.py:89-95 [DERIVED]
- Entity-card lane: bare `except Exception` → `card_seed_ids = []` (FACTS.fallbacks "handled: assign" :156) — fail-open to surface seeding; caller sees a normal GRAPH response with card seeds silently absent — orchestrator/orchestrator/api/graph.py:156-157 [DERIVED]
- Neo4j failure → typed 502 from `graph_expand_or_502`, "never an empty 'no graph knowledge' result" (FAILURE-TRANSPARENCY-V1) — orchestrator/orchestrator/api/graph.py:136-138 [DERIVED]

## dumb-code flags
- Magic literal `8` duplicated (`max_seeds` :229, trace `[:8]` :269, docstring :8) while the actual expansion input is capped at 12 (:69) — three different bounds for "seeds" in one request.
- `_selected_surfaces(query, evidence)` recomputed three times per call (:161, :236, :269); the `meta.liveness` copy (:236) is untruncated while the trace copy (:269) is `[:8]`.
- Unused import `Optional` — orchestrator/orchestrator/api/graph.py:23 [DERIVED: no `Optional` use anywhere in the file]
- Redundant string annotations `"bool | None"` (:73-74) despite `from __future__ import annotations` (:20).
- Plan forked via `HybridRetrievalPlan(**{**plan.__dict__, "corpus_ids": (corpus_id,)})` — reaches into plan internals, couples to `HybridRetrievalPlan` field names — orchestrator/orchestrator/api/graph.py:102 [DERIVED]
- `t0` reused for two separate timings — orchestrator/orchestrator/api/graph.py:98, 159 [DERIVED]
- Same Qdrant URL, two different timeouts: 60 (:90) vs 30 (:148), unexplained.
- Unexplained token thresholds: `> 3` query vs `> 5` evidence, `evidence[:10]` — orchestrator/orchestrator/api/graph.py:63, 65, 67 [DERIVED]

## refactor notes
- Four importers (chat_retrieval.py, evidence.py, retrieve.py, ui.py — FACTS.importers) consume the response; renaming `meta` / `documents` / `unassigned_rescue_evidence` / `graph_relationships` / `trace` keys breaks all four.
- Private cross-module contract on `orchestrator.api.fast`: `_begin_retrieval`, `_embed_query`, `_ensure_fast_ready`, `_neighbor_lookup`, `_region_lookup`, `_liveness`, `_rerank_children`, `_corpus_collections`, `degradations`, `FastSearcher`, `entity_card_probe` — orchestrator/orchestrator/api/graph.py:40-51, 147 [DERIVED]; plus `orchestrator.api.hybrid._lexical_search` (:52). Renaming any breaks this file.
- `graph_expand_or_502` called positionally `(surfaces, [corpus_id], [chunk_ids], seed_entity_ids=...)` — orchestrator/orchestrator/api/graph.py:160-164 [DERIVED]; parameter reorder in retrieve.py breaks this call.
- `apply_latent` wiring is the §1.5/B5 repair ("an earlier wiring accepted the flag but silently dropped it") — removing :107 silently regresses latent — orchestrator/orchestrator/api/graph.py:104-107 [DERIVED]
- `scope_kwargs` contract: "K1: pass a role scope only when it narrows" — must stay a no-op when `scope` is None — orchestrator/orchestrator/api/graph.py:53 [DERIVED]
- Audited-behaviour comments (FAILURE-TRANSPARENCY-V1 :136-138, CARD-SEEDS-V1 audit F1 :141-144) document checked invariants; do not delete without re-running those audits.

## VERIFY
```verify
grep -Fq 'corpus_required' orchestrator/orchestrator/api/graph.py
grep -Fq 'qdrant_unavailable' orchestrator/orchestrator/api/graph.py
grep -Fq '[:GRAPH_MAX_FACTS]' orchestrator/orchestrator/api/graph.py
grep -Fq 'return list(dict.fromkeys(surfaces))[:12]' orchestrator/orchestrator/api/graph.py
grep -Fq 'card_seed_ids = []' orchestrator/orchestrator/api/graph.py
grep -Fq 'SELECT chunk_id, summary FROM chunks WHERE chunk_id = ANY(%s)' orchestrator/orchestrator/api/graph.py
grep -Eq 'time\.time\(\)' orchestrator/orchestrator/api/graph.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/graph.py
```
