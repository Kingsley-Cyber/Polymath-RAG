---
title: "CHAT-M-REPLAY p1d-B-modes: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1d-B-modes

run 2026-09-06T04:20:04+00:00 · fixture B · 30 questions · arms AB, ABC · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 1, 'sidecar_reranker': 9}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AB | 30 | 0.767 | 0.667 | 0.633 | 0.474 | 0.826 | 4 | 0 / 11 | 8.69 | 27 | 8.1 | 4178.5 | 4198.9 | 24.0 | 0/3 |
| ABC | 30 | 0.9 | 0.833 | 0.667 | 0.564 | 0.815 | 5 | 0 / 11 | 10.1 | 23 | 10.09 | 5240.4 | 4785.0 | 24.0 | 1/6 |

Unseated golds that were in the union:

- AB: [{'idx': 6, 'union_rank': 28, 'pre_rerank': False}, {'idx': 16, 'union_rank': 26, 'pre_rerank': False}, {'idx': 17, 'union_rank': 18, 'pre_rerank': True}, {'idx': 23, 'union_rank': 45, 'pre_rerank': False}]
- ABC: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AB | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 2 | 8.69 | 19.74 | 3036.3 | 4178.5 | 8594.0 | 24.0 | 0/3 | 27 | 8.1 | 4198.9 |
| ABC | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 10.1 | 13.1 | 3503.6 | 5240.4 | 10057.8 | 24.0 | 1/6 | 23 | 10.09 | 4785.0 |

Residual (not system-honest OK):

- AB: none
- ABC: none

Strict misses (silent):

- AB: none
- ABC: none
