---
title: "CHAT-M-REPLAY p1d-B-lane-deadline: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1d-B-lane-deadline

run 2026-09-06T04:23:28+00:00 · fixture B · 10 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 8}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.7 | 0.5 | 0.5 | 0.27 | 0.714 | 2 | 0 / 7 | 17.81 | 4 | 17.81 | 8008.4 | 6575.0 | 24.0 | 0/8 |

Unseated golds that were in the union:

- single: [{'idx': 7, 'union_rank': 38, 'pre_rerank': False}, {'idx': 9, 'union_rank': 32, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 17.81 | 31.39 | 11096.5 | 8008.4 | 17746.4 | 24.0 | 0/8 | 4 | 17.81 | 6575.0 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
