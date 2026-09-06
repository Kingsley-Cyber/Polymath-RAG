---
title: "CHAT-M-REPLAY p1c-L-before: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1c-L-before

run 2026-09-06T01:54:39+00:00 · fixture L · 30 questions · arms single · plans `eval/fixtures/chat_lexical_L_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 1, 'sidecar_reranker': 2}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 1.0 | 1.0 | 1.0 | 0.913 | 1.0 | 0 | 0 / 0 | 9.71 | 27 | 9.39 | 5521.3 | 5159.8 | 20.0 | 1/2 |

Unseated golds that were in the union:

- single: none

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 9.71 | 17.59 | 2836.4 | 5521.3 | 9652.5 | 20.0 | 1/2 | 27 | 9.39 | 5159.8 |

Residual (not system-honest OK):

- single: none

Strict misses (silent):

- single: none
