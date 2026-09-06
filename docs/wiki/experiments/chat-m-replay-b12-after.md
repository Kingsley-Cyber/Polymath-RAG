---
title: "CHAT-M-REPLAY b12-after: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY b12-after

run 2026-09-06T22:49:51+00:00 · fixture B · 10 questions · arms HYBRID, WILDCARD, HYBRID+LATENT · plans `eval/fixtures/chat_baseline_B_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 20, 'sidecar_reranker': 0}

| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 8.53 | 7 | 7.88 | 2939.6 | 4309.1 | 32.0 | 3/0 |
| WILDCARD | 10 | 0.7 | 0.6 | 0.6 | 0.417 | 0.857 | 1 | 0 / 6 | 13.11 | 5 | 8.3 | 731.5 | 197.6 | 32.0 | 8/0 |
| HYBRID+LATENT | 10 | 0.7 | 0.6 | 0.6 | 0.467 | 0.857 | 1 | 0 / 8 | 11.43 | 5 | 4.89 | 1850.1 | 1164.4 | 32.0 | 8/0 |

Unseated golds that were in the union:

- HYBRID: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]
- WILDCARD: [{'idx': 7, 'union_rank': 21, 'pre_rerank': False}]
- HYBRID+LATENT: [{'idx': 7, 'union_rank': 35, 'pre_rerank': False}]

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 8.53 | 13.97 | 1611.3 | 2939.6 | 8471.8 | 32.0 | 3/0 | 7 | 7.88 | 4309.1 |
| WILDCARD | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 13.11 | 21.27 | 1991.5 | 731.5 | 7190.7 | 32.0 | 8/0 | 5 | 8.3 | 197.6 |
| HYBRID+LATENT | 10 | 0.0 (0/0) | 0.0 (0/0) | 0.0 | 0.0 | 0 | 0 | 0 | 0 | 1 | 11.43 | 21.25 | 3421.2 | 1850.1 | 11375.5 | 32.0 | 8/0 | 5 | 4.89 | 1164.4 |

P1.e mode compositions (gates: GRAPH p50 ≤ HYBRID + 1.5 s with ≤ 8 seeds / ≤ 20 facts; WILDCARD p50 ≤ HYBRID + 2.0 s with ≤ 3 bridges, `bridges in evidence` = 0):

| arm | mode | mode truthful | n | wall p50 s | Δ vs HYBRID s | clean wall p50 s | graph facts p50 / max | graph seeds p50 / max | graph ms p50 | wildcard bridges p50 / max | bridges in evidence | wildcard ms p50 | graph degraded | wildcard degraded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HYBRID | HYBRID | 1.0 | 10 | 8.53 | 0.0 | 7.88 | None / None | None / None | None | None / None | 0 | None | 0 | 0 |
| WILDCARD | WILDCARD | 1.0 | 10 | 13.11 | 4.58 | 8.3 | None / None | None / None | None | 3.0 / 3 | 0 | 5934.4 | 0 | 6 |

Residual (not system-honest OK):

- HYBRID: none
- WILDCARD: none
- HYBRID+LATENT: none

Strict misses (silent):

- HYBRID: none
- WILDCARD: none
- HYBRID+LATENT: none
