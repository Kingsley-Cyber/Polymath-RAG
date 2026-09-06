---
title: "CHAT-M-REPLAY p1c-final2-M: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1c-final2-M

run 2026-09-06T03:25:35+00:00 · fixture M · 30 questions · arms multi · plans `eval/fixtures/chat_multi_M_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 9}


| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| multi | 30 | 0.933 (56/60) | 1.0 (60/60) | 0.933 | 1.0 | 6 | 4 | 30 | 50 | 0 | 11.37 | 32.37 | 2509.0 | 7187.5 | 11274.6 | 24.0 | 0/9 | 22 | 9.71 | 5950.1 |

Residual (not system-honest OK):

- multi: none

Strict misses (silent):

- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': ['q1', 'q2'], 'in_union': True}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}]
