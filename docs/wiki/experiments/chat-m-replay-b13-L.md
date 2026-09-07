---
title: "CHAT-M-REPLAY b13-L: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY b13-L

run 2026-09-07T01:40:53+00:00 · fixture L · 10 questions · arms HYBRID, HYBRID+DOCS · plans `eval/fixtures/chat_lexical_L_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 3}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 1.0 | 1.0 | 0.9 | 0.775 | 1.0 | 0 | 0 / 2 | 6.79 | 9 | 6.52 | 2811.4 | 1841.8 | 32.0 | 0/1 |
| HYBRID+DOCS | 10 | 1.0 | 1.0 | 0.9 | 0.742 | 1.0 | 0 | 0 / 3 | 6.37 | 9 | 5.91 | 3920.3 | 3803.0 | 32.0 | 0/2 |

Unseated golds that were in the union:

- HYBRID: none
- HYBRID+DOCS: none

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 0 | 6.79 | 10.36 | 1677.6 | 2811.4 | 6741.0 | 32.0 | 0/1 | 9 | 6.52 | 1841.8 |
| HYBRID+DOCS | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 6.37 | 7.98 | 1543.1 | 3920.3 | 6311.3 | 32.0 | 0/2 | 9 | 5.91 | 3803.0 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 1.0 | 10 | 6.79 | 0.0 | 6.52 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |

Residual (not system-honest OK):

- HYBRID: none
- HYBRID+DOCS: none

Strict misses (silent):

- HYBRID: none
- HYBRID+DOCS: none
