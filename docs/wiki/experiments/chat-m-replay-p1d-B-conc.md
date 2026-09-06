---
title: "CHAT-M-REPLAY p1d-B-conc: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1d-B-conc

run 2026-09-06T03:46:24+00:00 · fixture B · 30 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 8}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.9 | 0.833 | 0.767 | 0.562 | 0.852 | 4 | 2 / 24 | 8.75 | 22 | 8.03 | 3005.2 | 3006.1 | 24.0 | 0/8 |

Unseated golds that were in the union:

- single: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 8.75 | 14.65 | 4571.5 | 3005.2 | 8666.8 | 24.0 | 0/8 | 22 | 8.03 | 3006.1 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
