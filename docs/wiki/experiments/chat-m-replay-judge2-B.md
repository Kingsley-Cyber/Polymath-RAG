---
title: "CHAT-M-REPLAY judge2-B: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY judge2-B

run 2026-09-06T14:47:01+00:00 · fixture B · 30 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 19, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.9 | 0.8 | 0.633 | 0.558 | 0.815 | 5 | 0 / 10 | 8.52 | 15 | 5.42 | 3072.9 | 2832.5 | 24.0 | 19/0 |

Unseated golds that were in the union:

- single: [{'idx': 6, 'union_rank': 79, 'pre_rerank': False}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 8.52 | 21.6 | 1721.1 | 3072.9 | 8480.2 | 24.0 | 19/0 | 15 | 5.42 | 2832.5 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
