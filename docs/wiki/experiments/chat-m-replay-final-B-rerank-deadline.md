---
title: "CHAT-M-REPLAY final-B-rerank-deadline: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY final-B-rerank-deadline

run 2026-09-06T11:45:28+00:00 · fixture B · 10 questions · arms single · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 5}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.7 | 0.7 | 0.5 | 0.428 | 0.857 | 1 | 0 / 10 | 13.19 | 7 | 10.34 | 306.4 | 307.0 | 24.0 | 0/5 |

Unseated golds that were in the union:

- single: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 13.19 | 23.26 | 11595.4 | 306.4 | 13140.3 | 24.0 | 0/5 | 7 | 10.34 | 307.0 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
