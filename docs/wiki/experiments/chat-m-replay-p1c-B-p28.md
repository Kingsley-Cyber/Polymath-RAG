---
title: "CHAT-M-REPLAY p1c-B-p28: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1c-B-p28

run 2026-09-06T02:23:21+00:00 · fixture B · 30 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override 28 · OOM during run {'sidecar_embedder': 1, 'sidecar_reranker': 9}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.9 | 0.867 | 0.7 | 0.594 | 0.889 | 3 | 4 / 9 | 12.13 | 23 | 10.76 | 7723.1 | 6942.7 | 28.0 | 1/9 |

Unseated golds that were in the union:

- single: [{'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 12.13 | 31.49 | 2632.6 | 7723.1 | 12063.1 | 28.0 | 1/9 | 23 | 10.76 | 6942.7 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
