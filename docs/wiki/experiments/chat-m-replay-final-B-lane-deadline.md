---
title: "CHAT-M-REPLAY final-B-lane-deadline: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY final-B-lane-deadline

run 2026-09-06T11:42:57+00:00 · fixture B · 10 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 7}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.7 | 0.4 | 0.4 | 0.325 | 0.571 | 3 | 1 / 7 | 15.89 | 3 | 13.71 | 8009.2 | 8008.8 | 24.0 | 0/7 |

Unseated golds that were in the union:

- single: [{'idx': 6, 'union_rank': 30, 'pre_rerank': False}, {'idx': 7, 'union_rank': 38, 'pre_rerank': False}, {'idx': 9, 'union_rank': 34, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 15.89 | 22.74 | 8509.1 | 8009.2 | 15825.8 | 24.0 | 0/7 | 3 | 13.71 | 8008.8 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
