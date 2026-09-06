---
title: "CHAT-M-REPLAY b12-wildcard-before: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY b12-wildcard-before

run 2026-09-06T22:36:33+00:00 · fixture B · 10 questions · arms HYBRID, WILDCARD · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 7.46 | 10 | 7.46 | 664.8 | 664.8 | 32.0 | 0/0 |
| WILDCARD | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 5.95 | 10 | 5.95 | 677.7 | 677.7 | 32.0 | 0/0 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]
- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 7.46 | 10.63 | 4501.9 | 664.8 | 7398.6 | 32.0 | 0/0 | 10 | 7.46 | 664.8 |
| WILDCARD | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 5.95 | 15.85 | 1888.8 | 677.7 | 3936.2 | 32.0 | 0/0 | 10 | 5.95 | 677.7 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 1.0 | 10 | 7.46 | 0.0 | 7.46 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |
| WILDCARD | WILDCARD | 1.0 | 10 | 5.95 | -1.51 | 5.95 | None / None | None / None | None | 1.0 / 1 | 0 | 1867.8 | 0 | 0 |

Residual (not system-honest OK):

- HYBRID: none
- WILDCARD: none

Strict misses (silent):

- HYBRID: none
- WILDCARD: none
