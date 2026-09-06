---
title: "CHAT-M-REPLAY final-L: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY final-L

run 2026-09-06T11:02:00+00:00 · fixture L · 30 questions · arms single · plans `eval/fixtures/chat_lexical_L_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 6, 'sidecar_reranker': 2}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 1.0 | 1.0 | 1.0 | 0.824 | 1.0 | 0 | 0 / 10 | 7.47 | 25 | 6.87 | 4622.2 | 4255.5 | 24.0 | 6/2 |

Unseated golds that were in the union:

- single: none

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 7.47 | 17.46 | 968.6 | 4622.2 | 7416.7 | 24.0 | 6/2 | 25 | 6.87 | 4255.5 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
