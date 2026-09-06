---
title: "CHAT-M-REPLAY final-B-modes: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY final-B-modes

run 2026-09-06T11:40:07+00:00 · fixture B · 30 questions · arms VECTOR, HYBRID, GRAPH, WILDCARD · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 1, 'sidecar_reranker': 24}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VECTOR | 30 | 0.767 | 0.667 | 0.633 | 0.521 | 0.826 | 4 | 0 / 10 | 8.16 | 28 | 7.15 | 4476.3 | 4476.3 | 24.0 | 1/1 |
| HYBRID | 30 | 0.9 | 0.833 | 0.633 | 0.558 | 0.815 | 5 | 0 / 11 | 7.46 | 27 | 7.05 | 4912.9 | 4694.5 | 24.0 | 0/4 |
| GRAPH | 30 | 0.9 | 0.833 | 0.7 | 0.573 | 0.852 | 4 | 0 / 12 | 10.88 | 25 | 9.51 | 6144.5 | 5339.5 | 24.0 | 0/10 |
| WILDCARD | 30 | 0.9 | 0.833 | 0.667 | 0.567 | 0.815 | 5 | 0 / 11 | 12.5 | 24 | 11.8 | 5040.8 | 4552.6 | 24.0 | 0/9 |

Unseated golds that were in the union:

- VECTOR: [{'idx': 6, 'union_rank': 30, 'pre_rerank': False}, {'idx': 16, 'union_rank': 26, 'pre_rerank': False}, {'idx': 17, 'union_rank': 18, 'pre_rerank': True}, {'idx': 23, 'union_rank': 45, 'pre_rerank': False}]
- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]
- GRAPH: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]
- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VECTOR | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 8.16 | 13.4 | 1778.0 | 4476.3 | 8106.9 | 24.0 | 1/1 | 28 | 7.15 | 4476.3 |
| HYBRID | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 7.46 | 13.94 | 1421.5 | 4912.9 | 7422.4 | 24.0 | 0/4 | 27 | 7.05 | 4694.5 |
| GRAPH | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 10.88 | 21.96 | 2007.1 | 6144.5 | 10306.9 | 24.0 | 0/10 | 25 | 9.51 | 5339.5 |
| WILDCARD | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 12.5 | 22.39 | 2397.9 | 5040.8 | 9492.8 | 24.0 | 0/9 | 24 | 11.8 | 4552.6 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VECTOR | VECTOR | 1.0 | 30 | 8.16 | 0.7 | 7.15 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |
| HYBRID | HYBRID | 1.0 | 30 | 7.46 | 0.0 | 7.05 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |
| GRAPH | GRAPH | 1.0 | 30 | 10.88 | 3.42 | 9.51 | 18.5 / 20 | 8.0 / 8 | 509.5 | None / None | 0 | None | 0 | 0 |
| WILDCARD | WILDCARD | 1.0 | 30 | 12.5 | 5.04 | 11.8 | None / None | None / None | None | 1.0 / 3 | 0 | 2971.2 | 0 | 12 |

Mode parity: VECTOR union ⊆ HYBRID union on 1.0 of 30 paired turns (clean turns 1.0 of 8); violations: none

Residual (not system-honest OK):

- VECTOR: none
- HYBRID: none
- GRAPH: none
- WILDCARD: none

Strict misses (silent):

- VECTOR: none
- HYBRID: none
- GRAPH: none
- WILDCARD: none
