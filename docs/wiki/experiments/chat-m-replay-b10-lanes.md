---
title: "CHAT-M-REPLAY b10-lanes: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY b10-lanes

run 2026-09-07T00:17:54+00:00 · fixture B · 10 questions · arms ABC, BC · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ABC | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 3.8 | 10 | 3.8 | 917.7 | 917.7 | 32.0 | 0/0 |
| BC | 10 | 0.7 | 0.6 | 0.6 | 0.414 | 0.857 | 1 | 0 / 7 | 4.48 | 10 | 4.48 | 2487.7 | 2487.7 | 32.0 | 0/0 |

Unseated golds that were in the union:

- ABC: [{'idx': 7, 'union_rank': 20, 'pre_rerank': False}]
- BC: [{'idx': 7, 'union_rank': 16, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ABC | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 3.8 | 7.27 | 1678.5 | 917.7 | 3751.6 | 32.0 | 0/0 | 10 | 3.8 | 917.7 |
| BC | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 4.48 | 7.03 | 1785.2 | 2487.7 | 4427.2 | 32.0 | 0/0 | 10 | 4.48 | 2487.7 |

Residual (not system-honest OK):

- ABC: none
- BC: none

Strict misses (silent):

- ABC: none
- BC: none
