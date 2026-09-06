---
title: "CHAT-M-REPLAY p1d-M-lease: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY p1d-M-lease

run 2026-09-06T04:09:51+00:00 · fixture M · 30 questions · arms multi · plans `eval/fixtures/chat_multi_M_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 0, 'sidecar_reranker': 10}


| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| multi | 30 | 0.9 (54/60) | 0.917 (55/60) | 0.9 | 0.917 | 2 | 6 | 32 | 50 | 0 | 12.13 | 22.75 | 4406.7 | 7634.8 | 12075.3 | 24.0 | 0/10 | 22 | 10.28 | 5158.4 |

Residual (not system-honest OK):

- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0']}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0']}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0', 'q2']}, {'idx': 5, 'term': 'FACE OFF', 'naming': ['q0']}, {'idx': 7, 'term': 'Sound Editing', 'naming': ['q1', 'q2']}]

Strict misses (silent):

- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0', 'q2'], 'in_union': False}, {'idx': 5, 'term': 'FACE OFF', 'naming': ['q0'], 'in_union': False}, {'idx': 7, 'term': 'Sound Editing', 'naming': ['q1', 'q2'], 'in_union': False}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}]
