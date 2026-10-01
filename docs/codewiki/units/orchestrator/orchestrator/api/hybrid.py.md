# unit: orchestrator/orchestrator/api/hybrid.py
anchor: orchestrator/orchestrator/api/hybrid.py:1-290

## purpose
Production HYBRID retrieval route for orchestrator-owned HTTP reads: FAST service primitives plus a lexical lane, executed as one qualified hybrid result that feeds `/retrieve`, `/evidence`, and `/chat`. — orchestrator/orchestrator/api/hybrid.py:1-6 [DERIVED]
MMR was rejected by R1D qualification; the promoted plan is `lambda 1.0`, relevance-only. Lexical failure fails loudly — the in-memory Postgres scan is the only fallback, never a silent degrade of HYBRID to FAST. — orchestrator/orchestrator/api/hybrid.py:3-10 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `hybrid_fast_retrieve` | def | (`query: str`, `corpus_id: str`, `plan: Optional[HybridRetrievalPlan] = None`, `latent: "bool \| None" = None`, `utility: "bool \| None" = None`, `scope=None`) -> `dict` | orchestrator/orchestrator/api/hybrid.py:143-289 | module imported by `api/evidence.py`, `api/graph.py`, `api/retrieve.py`, `api/ui.py`, `api/_small-modules` (FACTS.importers; specific symbol not shown) [DERIVED] |
| `_lexical_search` | def | (`query: str`, `corpus_id: str`, `top_k: int`, `scope=None`) -> `list[LaneHit]` | orchestrator/orchestrator/api/hybrid.py:103-140 | `hybrid_fast_retrieve` via `hybrid_retrieve` at :195 [DERIVED] |
| `_sparse_lexical_search` | def | (`query: str`, `corpus_id: str`, `top_k: int`, `scope=None`) -> `list[LaneHit]` | orchestrator/orchestrator/api/hybrid.py:46-100 | `_lexical_search` at :109 [DERIVED] |

## contracts

**hybrid_fast_retrieve** — orchestrator/orchestrator/api/hybrid.py:143-289
- in: `corpus_id` is required; `None` raises 422 `corpus_required` (:158-162). Defaults: `plan = None`, `latent = None`, `utility = None`, `scope = None` (:146-149). [DERIVED]
- pre: `_begin_retrieval()` first (:154); plan normalized via `apply_utility(apply_latent(plan or hybrid_mode_plan(MODE_HYBRID), latent), utility)` (:155-157); `_ensure_fast_ready(corpus_id)` (:164); corpus pinned by `HybridRetrievalPlan(**{**plan.__dict__, "corpus_ids": (corpus_id,)})` (:177-180). [DERIVED]
- out: dict with top-level keys `query`, `meta`, `selected_documents`, `selected_sections`, `evidence`, `trace` (:212-289); `meta.mode = MODE_HYBRID` (:215); `meta.mmr = "REJECTED_BY_R1D"` when `not result.plan.mmr_enabled`, else `result.plan.mmr_lambda` (:220); `meta.degraded = degradations()` (:224). [DERIVED]
- post: Qdrant client closed in `finally` (:203-204); `latency_ms` = `searcher.latency` rounded to 1 decimal plus `"total"` (:206-207); each evidence `text` truncated `[:240]` (:276). [DERIVED]

**_lexical_search** — orchestrator/orchestrator/api/hybrid.py:103-140
- in: `query: str, corpus_id: str, top_k: int, scope=None` (:103). [DERIVED]
- out: `list[LaneHit]` with `representation_kind="child_lexical"`, only scores `s > 0`, sorted `(-s, chunk_id)`, cut to `top_k` (:128-140). [DERIVED]
- pre: sparse lane attempted first; empty → `note_sparse_fallback("sparse_empty")`; any `Exception` → `note_sparse_fallback(f"sparse_error:{type(exc).__name__}")` (:108-114). [DERIVED]
- post: fallback SQL reads `chunks ch JOIN documents d` with `ch.tier = 'child'` and `_chunk_visible_sql("ch", "d")` visibility (:115-125). [DERIVED]

**_sparse_lexical_search** — orchestrator/orchestrator/api/hybrid.py:46-100
- in: `query: str, corpus_id: str, top_k: int, scope=None` (:46). [DERIVED]
- out: `list[LaneHit]` sorted `(-raw_similarity, chunk_id)`, sliced to `top_k` (:95-98); `[]` when `sparse_vector(query)` yields no indices (:58-60). [DERIVED]
- pre/post: raises on any shortfall so the caller falls back (:50-52); client closed (:99-100). [DERIVED]

## effect surface
- Postgres read: `chunks` JOIN `documents` (:118-121); `hidden_generations(_conn, corpus_id)` (:66-67). FACTS `tables_read = ["chunks", "documents"]`; `tables_written = []`. [DERIVED]
- Qdrant: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=30)` (:62) and `timeout=60` (:168); sparse `query_points` with `SparseVector`, `using=SPARSE_VECTOR_NAME`, `limit=top_k`, `with_payload=True` (:76-83); dense/neighbor/region/latent lanes delegated to `FastSearcher` + `hybrid_retrieve` on the same client (:175, :190-201). [DERIVED]
- Settings: `get_settings().stores.qdrant_url` (:62, :168); default not shown. [DERIVED]
- Raises `HTTPException` 422 and 502 (:159, :170). [DERIVED]

## invariants
INVARIANT: sparse filter `representation_kind == "routing_child"` AND `corpus_id` match — orchestrator/orchestrator/api/hybrid.py:69-72 [DERIVED]
  fails-if: hits from other corpora or non-child representations enter the lexical lane.
INVARIANT: `chunk_contract_version` values in `hidden_generations(corpus_id)` excluded via `must_not` — orchestrator/orchestrator/api/hybrid.py:66-74 [DERIVED]
  fails-if: hidden generations surface as lexical evidence.
INVARIANT: both lexical lanes emit `representation_kind == "child_lexical"` — orchestrator/orchestrator/api/hybrid.py:87 and :134 [DERIVED]
  fails-if: lane accounting / RRF contributions misattribute the lexical lane.
INVARIANT: tie-break sort keys identical: `(-raw_similarity, chunk_id)` sparse vs `(-s, chunk_id)` fallback — orchestrator/orchestrator/api/hybrid.py:95 and :131 [DERIVED]
  fails-if: ordering flaps between sparse and fallback paths on equal scores.
INVARIANT: fallback SQL selects only `ch.tier = 'child'` — orchestrator/orchestrator/api/hybrid.py:121 [DERIVED]
  fails-if: parent/document rows get scored in the child lexical lane.
INVARIANT: `summary_vectors == None` and `meta.mmr == "REJECTED_BY_R1D"` when `not plan.mmr_enabled` — orchestrator/orchestrator/api/hybrid.py:197, :220 [DERIVED]
  fails-if: reintroduced MMR changes ranking without a new qualification run.
INVARIANT: `evidence[].text` length ≤ `240` — orchestrator/orchestrator/api/hybrid.py:276 [DERIVED]
  fails-if: response payload grows unbounded on large chunks.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.time` at :176 and :202 — feeds `latency_ms` only; network Qdrant calls :62/:168; db Postgres rows :115-125; Qdrant scores drive ranking) — orchestrator/orchestrator/api/hybrid.py:176,202 [DERIVED]
idempotency: SAFE (read-only: `tables_written = []` per FACTS; both clients closed in `finally` :99-100, :203-204; only in-process degradation counters mutated via `note_sparse_fallback` :112,:114) — orchestrator/orchestrator/api/hybrid.py:112-114 [DERIVED]

## failure behaviour
- `except Exception` (noqa: BLE001) around the sparse lane swallows the error, records degradation `f"sparse_error:{type(exc).__name__}"`, then the in-memory Postgres scan runs — caller still gets a full HYBRID result — orchestrator/orchestrator/api/hybrid.py:113-125 [DERIVED]
- Empty sparse hits → degradation `"sparse_empty"`, scan runs — orchestrator/orchestrator/api/hybrid.py:110-112 [DERIVED]; a no-token query returns `[]` from sparse (:58-60) and surfaces the same way.
- `corpus_id is None` → `HTTPException` 422, `error_code: "corpus_required"` — orchestrator/orchestrator/api/hybrid.py:158-162 [DERIVED]
- QdrantClient construction failure → `HTTPException` 502, `error_code: "qdrant_unavailable"`, message `f"qdrant unavailable: {type(exc).__name__}"` — orchestrator/orchestrator/api/hybrid.py:168-173 [DERIVED]
- The 502 handler wraps only the constructor; exceptions raised inside `hybrid_retrieve`/`query_points` propagate uncaught (inner `try` has `finally` only) — orchestrator/orchestrator/api/hybrid.py:167-204 [DERIVED]
- Module contract: if Postgres rows are unavailable the request fails loudly — never silently degrades HYBRID to FAST — orchestrator/orchestrator/api/hybrid.py:8-10 [DERIVED]

## dumb-code flags
- Duplicate `QdrantClient` construction with disagreeing timeouts: `timeout=30` (:62) vs `timeout=60` (:168) — orchestrator/orchestrator/api/hybrid.py:62,168 [DERIVED]
- Literal pair for one lane stage: filter matches `"routing_child"` (:70-71) but output kind is `"child_lexical"` (:87, :134) — orchestrator/orchestrator/api/hybrid.py:70-71 [DERIVED]
- Magic number `240` for evidence text truncation — orchestrator/orchestrator/api/hybrid.py:276 [DERIVED]
- Plan rehydrated via `{**plan.__dict__, "corpus_ids": (corpus_id,)}` — orchestrator/orchestrator/api/hybrid.py:179 [DERIVED]
- `Callable` imported from `typing` but never used in the file — orchestrator/orchestrator/api/hybrid.py:15 [DERIVED]
- Sparse lane fetches `limit=top_k` per collection, then merges/sorts/truncates to `top_k` — with N collections up to `N * top_k` points fetched — orchestrator/orchestrator/api/hybrid.py:75-98 [DERIVED]

## refactor notes
- Return-dict shape (`meta`/`selected_documents`/`selected_sections`/`evidence`/`trace` keys) is the cross-route contract; `api/evidence.py`, `api/graph.py`, `api/retrieve.py`, `api/ui.py`, `api/_small-modules` import this module (FACTS.importers) and the docstring pins one result feeding `/retrieve`, `/evidence`, `/chat` — orchestrator/orchestrator/api/hybrid.py:5-6, :212-289 [DERIVED]
- `lexical_search=lambda q, k: ...` arity is fixed by the `hybrid_retrieve` call — orchestrator/orchestrator/api/hybrid.py:195 [DERIVED]
- `summary_vectors=None` is pinned by R1D qualification (`lambda 1.0` promoted); changing it requires re-qualification — orchestrator/orchestrator/api/hybrid.py:3-4, :197, :220 [DERIVED]
- `collections` maps corpus_id → collection NAME; must iterate `.values()`, not keys (comment records a past 404 → silent Postgres scan bug) — orchestrator/orchestrator/api/hybrid.py:75-76 [DERIVED]
- K1 role scope must reach both lanes: `scope_kwargs(scope)` applied at :109, :175, :195 — orchestrator/orchestrator/api/hybrid.py:43, :109, :175, :195 [DERIVED]
- The `plan.__dict__` splat assumes `HybridRetrievalPlan` is a plain attribute object; adding computed/non-init members changes the copy — orchestrator/orchestrator/api/hybrid.py:179 [INFERRED: dict splat copies `__dict__` verbatim]

## VERIFY
```verify
grep -Fq 'def hybrid_fast_retrieve(' orchestrator/orchestrator/api/hybrid.py
grep -Fq 'summary_vectors=None,  # MMR rejected; lambda 1.0 promoted' orchestrator/orchestrator/api/hybrid.py
grep -Fq 'corpus_required' orchestrator/orchestrator/api/hybrid.py
grep -Fq 'qdrant_unavailable' orchestrator/orchestrator/api/hybrid.py
grep -Fq '"REJECTED_BY_R1D"' orchestrator/orchestrator/api/hybrid.py
grep -Fq '[:240]' orchestrator/orchestrator/api/hybrid.py
test "$(grep -c -F 'note_sparse_fallback' orchestrator/orchestrator/api/hybrid.py)" -ge 2
```
