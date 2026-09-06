---
title: "WORK LOG — R2 hybrid-retrieval-v1 sparse lane: the collection dict's keys were queried as collections (404) and every turn fell back, silently, to the Postgres scan"
change_id: HYBRID-V1-SPARSE-LANE-FIX
date: 2026-09-06
owner: governance (goal 2026-09-06 R2)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.94
package: orchestrator/orchestrator/api/hybrid.py, orchestrator/orchestrator/api/fast.py, tests/determinism/test_hybrid_sparse_lane.py
architecture_impact: "`_sparse_lexical_search` now iterates `_corpus_collections(...).values()` (collection names), so the SPARSE-BM25 child lexical lane of hybrid-retrieval-v1 (/retrieve HYBRID, /ask consumers, TRAIL, chat `retrieval: v1`) queries the projected BM25 index as §11.6 specifies. The in-memory Postgres `lexical_score` scan remains the degradation path — but it is no longer silent: `note_sparse_fallback(reason)` records `sparse_empty` / `sparse_error:<Exception>` per request and `degradations()` surfaces it as component `sparse_lexical` in `meta.degraded`, next to the reranker's. No retrieval semantics changed beyond the bug: an empty sparse result still falls through to the scan (counted). Versioned contracts (`hybrid-retrieval-v1`, `/retrieve`, `/ask`) unchanged."
---

# WORK LOG — R2 hybrid-retrieval-v1 sparse lane

## Contract

- §11.6 SPARSE-BM25 child lexical lane: query the routing collection's named `bm25` sparse vector with the shared tokenizer; the in-memory scan is the fallback for legacy dense-only collections.
- Silent-fallback accounting (standing rule): every fallback counts and surfaces its rate. A fallback that fires on 100 % of turns without a receipt is a defect twice.
- Versioned authority: the fix lives in `hybrid-retrieval-v1`'s own module; chat v2 (`chat_retrieve_v2`) never used this path (its lane C is `FastSearcher.sparse_search` with the mapped collection) and is untouched.

## Changes

- `orchestrator/orchestrator/api/hybrid.py`: `for collection in collections.values()`; `_lexical_search` calls `note_sparse_fallback("sparse_empty")` when BM25 returns nothing and `note_sparse_fallback(f"sparse_error:{type}")` when it raises, then scans as before.
- `orchestrator/orchestrator/api/fast.py`: `_SPARSE_FALLBACK` ContextVar (reset in `_begin_retrieval`), `note_sparse_fallback(reason)` (warning with `error_code=sparse_fallback`), `degradations()` returns both the reranker and the sparse notes.
- `tests/determinism/test_hybrid_sparse_lane.py` (3 tests, fake Qdrant + fake tx): the mapped collection is queried and no `FROM chunks` scan runs when BM25 answers; an outage degrades to the scan and is receipted `sparse_error:RuntimeError`; an empty result is receipted `sparse_empty`; state resets per request.

## Proof

- **Before (structural, reproduced live 2026-09-06 01:05 UTC):** `_corpus_collections(["cinema"])` = `{'cinema': 'polymath_b815843425f6_embed_e794ec4cab197a3f'}`; `query_points(collection_name='cinema', …)` → `UnexpectedResponse: 404 (Not Found)`; the mapped name → 3 sparse hits, top score 82.09 for "chroma keyer". Every v1 HYBRID turn therefore raised inside `_sparse_lexical_search`, was swallowed by `except Exception: pass`, and scanned Postgres — with `meta.degraded == []`.
- **Unit:** the three tests above + `test_hybrid.py` (5) + chat v2 unit (4) + engine (13) green.
- **After (live, orchestrator restarted on this code):** three `/retrieve` HYBRID calls on `cinema` ("chroma keyer", "nonsquare pixels", "FACE OFF") at 01:2x UTC: `meta.degraded == []`, lane liveness `live` includes `lexical` and `reranker`, plan `hybrid-retrieval-v1`, 10 evidence rows each, and **0** `sparse_fallback` warnings in the orchestrator log since the restart (before the fix every such call raised a 404 inside the sparse lane and scanned Postgres silently). A stop-word probe ("the and of to a in") still found BM25 hits (the shared tokenizer keeps some of those tokens), so the `sparse_empty` path was exercised by the unit test, not live.

## Rejected claims

- "Drop the empty-result fallback to the scan; BM25 is the authority." Rejected for R2: that changes retrieval semantics beyond the bug (a query of pure stop-words still gets the legacy scan); it is counted now and retired when P1.e recomposes the modes on the shared primitives.
- "Route v1 HYBRID onto `chat_retrieve_v2`." Rejected here: mode recomposition is P1.e; R2 fixes the versioned authority in place.

## Open contract gaps

1. `hybrid-retrieval-v1` still has two lexical paths by design (BM25 + scan). The scan's share is now visible in `meta.degraded` and the `sparse_fallback` warnings; P1.e decides its retirement.
2. Consumers that compare v1 HYBRID results against pre-fix expectations (TRAIL / research fixtures pinned on the scan's ordering) may see a different lexical lane; none exist in this repo's tests (`grep -rn _lexical_search tests/` → only the new file).
