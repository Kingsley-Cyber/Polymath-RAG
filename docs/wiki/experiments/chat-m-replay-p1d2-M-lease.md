---
title: "CHAT-M-REPLAY p1d2-M-lease: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1d2-M-lease

run 2026-09-06T04:52:29+00:00 · fixture M · 30 questions · arms multi · plans `eval/fixtures/chat_multi_M_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 9}


| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| multi | 30 | 0.917 (55/60) | 0.933 (56/60) | 0.917 | 0.933 | 2 | 5 | 32 | 50 | 0 | 10.03 | 23.28 | 2114.5 | 6350.3 | 9985.5 | 24.0 | 0/9 | 23 | 7.29 | 5824.3 |

Residual (not system-honest OK):

- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0']}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0']}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0', 'q2']}, {'idx': 7, 'term': 'Sound Editing', 'naming': ['q1', 'q2']}]

Strict misses (silent):

- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0', 'q2'], 'in_union': False}, {'idx': 7, 'term': 'Sound Editing', 'naming': ['q1', 'q2'], 'in_union': False}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}]
