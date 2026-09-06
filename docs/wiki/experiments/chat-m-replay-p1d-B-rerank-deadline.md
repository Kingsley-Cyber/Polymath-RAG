---
title: "CHAT-M-REPLAY p1d-B-rerank-deadline: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1d-B-rerank-deadline

run 2026-09-06T04:26:37+00:00 · fixture B · 10 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 6}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.7 | 0.7 | 0.5 | 0.508 | 0.857 | 1 | 0 / 10 | 17.9 | 6 | 10.11 | 307.9 | 306.2 | 24.0 | 0/6 |

Unseated golds that were in the union:

- single: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 17.9 | 33.43 | 16222.8 | 307.9 | 17849.2 | 24.0 | 0/6 | 6 | 10.11 | 306.2 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
