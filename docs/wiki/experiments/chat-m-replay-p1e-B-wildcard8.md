---
title: "CHAT-M-REPLAY p1e-B-wildcard8: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY p1e-B-wildcard8

run 2026-09-06T10:08:43+00:00 · fixture B · 30 questions · arms HYBRID, WILDCARD · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 1, 'sidecar_reranker': 21}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 30 | 0.9 | 0.833 | 0.633 | 0.586 | 0.815 | 5 | 0 / 14 | 10.4 | 24 | 9.56 | 5261.0 | 4668.0 | 24.0 | 0/7 |
| WILDCARD | 30 | 0.9 | 0.833 | 0.667 | 0.599 | 0.815 | 5 | 2 / 15 | 18.42 | 19 | 16.53 | 6836.2 | 4590.1 | 24.0 | 1/14 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]
- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': True}, {'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 10.4 | 18.67 | 3702.2 | 5261.0 | 10352.5 | 24.0 | 0/7 | 24 | 9.56 | 4668.0 |
| WILDCARD | 30 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 18.42 | 31.62 | 2071.9 | 6836.2 | 10348.0 | 24.0 | 1/14 | 19 | 16.53 | 4590.1 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 30 | 10.4 | 0.0 | 9.56 | None / None | None | None | None / None | 0 | None | 0 | 0 |
| WILDCARD | WILDCARD | 30 | 18.42 | 8.02 | 16.53 | None / None | None | None | 0.0 / 0 | 0 | 8002.7 | 0 | 30 |

Residual (not system-honest OK):

- HYBRID: none
- WILDCARD: none

Strict misses (silent):

- HYBRID: none
- WILDCARD: none
