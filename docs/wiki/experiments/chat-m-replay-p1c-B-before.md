---
title: "CHAT-M-REPLAY p1c-B-before: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1c-B-before

run 2026-09-06T01:48:51+00:00 · fixture B · 30 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 1, 'sidecar_reranker': 5}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.9 | 0.767 | 0.7 | 0.519 | 0.815 | 5 | 0 / 0 | 9.91 | 24 | 9.1 | 4930.5 | 4786.8 | 20.0 | 1/5 |

Unseated golds that were in the union:

- single: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 9.91 | 26.29 | 3190.0 | 4930.5 | 9859.5 | 20.0 | 1/5 | 24 | 9.1 | 4786.8 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
