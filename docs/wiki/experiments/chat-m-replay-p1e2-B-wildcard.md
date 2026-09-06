---
title: "CHAT-M-REPLAY p1e2-B-wildcard: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY p1e2-B-wildcard

run 2026-09-06T10:21:15+00:00 · fixture B · 30 questions · arms HYBRID, WILDCARD · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 17}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 30 | 0.9 | 0.833 | 0.633 | 0.586 | 0.815 | 5 | 0 / 11 | 7.53 | 24 | 6.96 | 4699.4 | 4464.1 | 24.0 | 0/6 |
| WILDCARD | 30 | 0.9 | 0.833 | 0.633 | 0.559 | 0.815 | 5 | 0 / 12 | 13.42 | 22 | 11.78 | 5782.6 | 4735.6 | 24.0 | 0/11 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]
- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 7.53 | 14.72 | 1668.8 | 4699.4 | 7491.0 | 24.0 | 0/6 | 24 | 6.96 | 4464.1 |
| WILDCARD | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 13.42 | 20.38 | 3618.3 | 5782.6 | 10215.4 | 24.0 | 0/11 | 22 | 11.78 | 4735.6 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 30 | 7.53 | 0.0 | 6.96 | None / None | None | None | None / None | 0 | None | 0 | 0 |
| WILDCARD | WILDCARD | 30 | 13.42 | 5.89 | 11.78 | None / None | None | None | 1.0 / 2 | 0 | 3045.4 | 0 | 13 |

Residual (not system-honest OK):

- HYBRID: none
- WILDCARD: none

Strict misses (silent):

- HYBRID: none
- WILDCARD: none
