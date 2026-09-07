---
title: "CHAT-M-REPLAY region-excl-L: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY region-excl-L

run 2026-09-07T05:15:52+00:00 · fixture L · 10 questions · arms HYBRID · plans `eval/fixtures/chat_lexical_L_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 1.0 | 0.9 | 0.9 | 0.825 | 0.9 | 1 | 0 / 2 | 6.66 | 10 | 6.66 | 3481.8 | 3481.8 | 32.0 | 0/0 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 0, 'union_rank': 7, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 6.66 | 8.88 | 1841.9 | 3481.8 | 6593.9 | 32.0 | 0/0 | 10 | 6.66 | 3481.8 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 1.0 | 10 | 6.66 | 0.0 | 6.66 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |

Residual (not system-honest OK):

- HYBRID: none

Strict misses (silent):

- HYBRID: none
