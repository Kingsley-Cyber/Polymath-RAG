---
title: "CHAT-M-REPLAY b12-forced: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY b12-forced

run 2026-09-06T22:52:33+00:00 · fixture B · 10 questions · arms WILDCARD · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 15, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WILDCARD | 10 | 0.7 | 0.6 | 0.6 | 0.467 | 0.857 | 1 | 0 / 8 | 14.14 | 2 | 9.17 | 5509.4 | 3309.6 | 32.0 | 15/0 |

Unseated golds that were in the union:

- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WILDCARD | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 14.14 | 22.96 | 5783.5 | 5509.4 | 13633.1 | 32.0 | 15/0 | 2 | 9.17 | 3309.6 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WILDCARD | WILDCARD | 1.0 | 10 | 14.14 | None | 9.17 | None / None | None / None | None | 3.0 / 3 | 0 | 450.9 | 0 | 0 |

Residual (not system-honest OK):

- WILDCARD: none

Strict misses (silent):

- WILDCARD: none
