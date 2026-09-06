---
title: "CHAT-M-REPLAY p1e-B-modes: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY p1e-B-modes

run 2026-09-06T09:52:04+00:00 · fixture B · 30 questions · arms HYBRID, GRAPH, WILDCARD · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 35, 'sidecar_reranker': 25}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 30 | 0.9 | 0.833 | 0.667 | 0.582 | 0.815 | 5 | 1 / 13 | 9.94 | 17 | 8.42 | 5379.4 | 4854.4 | 24.0 | 14/7 |
| GRAPH | 30 | 0.9 | 0.833 | 0.633 | 0.581 | 0.815 | 5 | 1 / 15 | 10.47 | 19 | 8.84 | 7036.4 | 4909.6 | 24.0 | 8/8 |
| WILDCARD | 30 | 0.9 | 0.833 | 0.633 | 0.598 | 0.815 | 5 | 1 / 16 | 16.8 | 15 | 12.23 | 8001.2 | 4700.6 | 24.0 | 13/10 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]
- GRAPH: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]
- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 9.94 | 20.6 | 2574.8 | 5379.4 | 9886.3 | 24.0 | 14/7 | 17 | 8.42 | 4854.4 |
| GRAPH | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 10.47 | 30.45 | 3530.4 | 7036.4 | 9891.0 | 24.0 | 8/8 | 19 | 8.84 | 4909.6 |
| WILDCARD | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 16.8 | 32.91 | 5815.8 | 8001.2 | 14236.1 | 24.0 | 13/10 | 15 | 12.23 | 4700.6 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 30 | 9.94 | 0.0 | 8.42 | None / None | None | None | None / None | 0 | None | 0 | 0 |
| GRAPH | GRAPH | 30 | 10.47 | 0.53 | 8.84 | 20.0 / 20 | 8.0 | 549.8 | None / None | 0 | None | 0 | 0 |
| WILDCARD | WILDCARD | 30 | 16.8 | 6.86 | 12.23 | None / None | None | None | 0.0 / 0 | 0 | 2501.2 | 0 | 30 |

Residual (not system-honest OK):

- HYBRID: none
- GRAPH: none
- WILDCARD: none

Strict misses (silent):

- HYBRID: none
- GRAPH: none
- WILDCARD: none
