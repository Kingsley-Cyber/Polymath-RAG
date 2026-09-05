---
title: "WORK LOG — P1.d concurrency + one rerank: every lane starts at T=0, one embedding, one judge, wall-clock budgets with degraded receipts"
change_id: CHAT-RETRIEVAL-V2-CONCURRENCY
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P1.d)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.94
package: shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/{chat_retrieval.py,fast.py,ui.py}, scripts/chat_baseline.py, tests/determinism/{test_candidate_engine.py,test_chat_retrieval_v2.py}
architecture_impact: "The candidate engine runs every independent lane of a turn concurrently (`_gather` on a per-turn ThreadPoolExecutor): document summaries ∥ section summaries ∥ entity cards ∥ global dense child ∥ global sparse child ∥ each subquery's B + C, then the section deepenings concurrently; each lane gets `lane_timeout_s` and a lane that misses it (or raises) is DEGRADED with a `<lane>_timeout` / error receipt while the turn proceeds. The route starts the ONE batched embedding and lane C (BM25 needs no vector) together at T=0, hands the sparse rows to the engine pre-fetched, and runs the ONE judge call under `rerank_budget_s` (past it: fusion order + `rerank_timeout`). Interactive turns wait at most POLYMATH_EMBED_WAKE_BUDGET_INTERACTIVE_S (20 s) for a parked embedder (§3.21 #18). Modes become lane compositions (`lanes` request override for evaluation: VECTOR = A+B, HYBRID = A+B+C) ahead of P1.e. Nothing under §3.23 touched; the immutable SearchContext (P1.a) is what makes the lanes shareable across threads (§3.21 #10)."
---

# WORK LOG — P1.d concurrency + one rerank

Plan gate (ledger row, read from disk): *on B: exactly 1 embedding per distinct query text and exactly 1 rerank call per turn (spy tests); HYBRID p50 ≤ VECTOR p50 + 0.5 s; a lane forced past its deadline yields a `degraded` receipt and a complete answer in ≤ core budget + rerank budget.*

## Contract

- **Stage plan (§3.16).** STAGE 1 ∥ lane C: `_embed_queries(distinct texts)` and `sparse_search` are submitted together; STAGE 2: `retrieve_candidates(executor=pool, prefetched_sparse=rows)` gathers doc/section/card/dense/sparse/subquery lanes under `lane_timeout_s` (6 s), then the section deepenings; STAGE 3–4: union → dedupe → one `rerank_children` call under `rerank_budget_s` (20 s); STAGE 5: composition (P1.c); the pool is shut down without waiting (a late lane cannot hang the turn).
- **Degradation is receipted, never silent.** `trace.degraded` / `meta.degraded` carry `{component, effect, reason}` with reasons `global_sparse_child_timeout`, `document_summary_timeout`, `hierarchical_children_timeout`, `rerank_timeout`, `sub_<qid>_dense_timeout`, or the exception name; `trace.concurrent`, `trace.lane_timeout_s`, `timings_ms.lanes_wall`, `meta.budgets` state the budgets that applied.
- **One embedding, one judge.** Exactly one embedder call per turn carrying every distinct query text; exactly one `rerank_children` call per turn (the client still chunks the sidecar HTTP into batches of 16 → sidecar batches of 8, per §3.8).
- **Thread-safety (§3.21 #10).** Lanes share the immutable `SearchContext`; the FastSearcher's generation cache is warmed before threads share it; per-lane timings come from the engine's gather, not from mutable searcher counters.
- **Interactive wake budget (§3.21 #18).** `EMBED_WAKE_BUDGET_INTERACTIVE_S` (20 s) for chat; ingest keeps `POLYMATH_EMBED_WAKE_BUDGET_S` (150 s).
- **Modes as lane compositions.** `lanes` (request, evaluation) / `--lanes AB|ABC` select the lane set on the same engine; VECTOR = HIERARCHICAL_ROUTE + GLOBAL_DENSE_CHILD, HYBRID = + GLOBAL_SPARSE_CHILD. P1.e maps the UI modes onto this.
- **Frozen and untouched:** budgets K, fusion, aspect seats, composer, SYNTHESIS-V2, CARRY-V2, the funnel, receipts' existing keys.

## Changes

- `candidate_engine.py`: `CandidateBudget` += lane_timeout_s / rerank_budget_s / max_workers; `_LaneOutcome`, `_gather`; `retrieve_candidates(executor=, prefetched_sparse=)` rewritten to submit every lane at T=0, deepen concurrently, receipt per-lane outcomes.
- `chat_retrieval.py`: per-turn pool; embedding ∥ lane C; `_rerank_with_deadline`; `lanes=`; `meta.budgets`; `extra_degraded` merged into `meta.degraded`.
- `fast.py`: `EMBED_WAKE_BUDGET_INTERACTIVE_S`, `_await_embedder(client, budget_s)`, `_embed_queries(texts, wake_budget_s)`.
- `ui.py`: `StreamChatRequest.lanes` → `chat_retrieve_v2(lanes=)`. `scripts/chat_baseline.py`: `--lanes`.
- Tests: `test_candidate_engine.py` +1 (lanes overlap, slow lane degraded not awaited, pre-fetched sparse, inline path unchanged), `test_chat_retrieval_v2.py` +1 (route spies: one embedding for the distinct texts with the interactive wake budget, one judge call, lane C starts before the vector exists, budgets receipted).

## Proof

PROOF_BLOCK

## Rejected claims

- "Use asyncio for the lanes." Rejected: every store client on this path (qdrant_client REST, psycopg via `tx()`, the sidecar HTTP clients) is synchronous; a thread pool per turn gives the overlap without rewriting the clients, and the pool is disposed with `wait=False` so a late lane cannot hold the turn.
- "Cancel the judge on timeout." Not possible over HTTP without a sidecar change; the turn proceeds in fusion order and the receipt says so — the plan's degradation rule, not a silent wait.
- "Run the subquery lanes after the primary." Rejected: they are independent of the primary's results (they need only their own vectors and tokens), so they belong at T=0.
- "Measure HYBRID vs VECTOR against the v1 FAST route." Rejected: two engines with different prefixes and rerank sizes measure the engines, not the lane cost. Both arms run on the v2 engine (`--lanes AB` vs `ABC`) back-to-back.

## Open contract gaps

GAPS_BLOCK
