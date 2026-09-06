---
title: "CHAT-M-REPLAY b8-graph: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY b8-graph

run 2026-09-06T22:19:57+00:00 · fixture B · 10 questions · arms HYBRID, GRAPH · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 3.55 | 10 | 3.55 | 1314.8 | 1314.8 | 32.0 | 0/0 |
| GRAPH | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 4.01 | 10 | 4.01 | 623.7 | 623.7 | 32.0 | 0/0 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]
- GRAPH: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 3.55 | 6.28 | 1017.0 | 1314.8 | 3489.6 | 32.0 | 0/0 | 10 | 3.55 | 1314.8 |
| GRAPH | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 4.01 | 5.66 | 1205.7 | 623.7 | 3153.4 | 32.0 | 0/0 | 10 | 4.01 | 623.7 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 1.0 | 10 | 3.55 | 0.0 | 3.55 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |
| GRAPH | GRAPH | 1.0 | 10 | 4.01 | 0.46 | 4.01 | 19.5 / 20 | 8.0 / 8 | 705.7 | None / None | 0 | None | 0 | 0 |

Residual (not system-honest OK):

- HYBRID: none
- GRAPH: none

Strict misses (silent):

- HYBRID: none
- GRAPH: none
