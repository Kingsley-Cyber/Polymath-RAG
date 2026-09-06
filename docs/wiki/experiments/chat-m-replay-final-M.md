---
title: "CHAT-M-REPLAY final-M: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY final-M

run 2026-09-06T11:17:51+00:00 · fixture M · 30 questions · arms single, multi · plans `eval/fixtures/chat_multi_M_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 33, 'sidecar_reranker': 18}


| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.817 (49/60) | 0.817 (49/60) | 0.817 | 0.817 | 0 | 11 | 29 | 39 | 0 | 13.48 | 33.42 | 5239.2 | 7027.8 | 13434.0 | 24.0 | 15/9 | 18 | 8.16 | 5221.8 |
| multi | 30 | 0.9 (54/60) | 0.917 (55/60) | 0.9 | 0.917 | 2 | 6 | 34 | 50 | 0 | 11.82 | 29.99 | 3383.2 | 8000.4 | 11777.7 | 24.0 | 18/9 | 16 | 9.91 | 7120.3 |

Residual (not system-honest OK):

- single: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0']}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0']}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0']}, {'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': []}, {'idx': 7, 'term': 'Sound Editing', 'naming': []}, {'idx': 9, 'term': 'Rewards of Good Type Development', 'naming': []}, {'idx': 10, 'term': 'Multiple moments', 'naming': []}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0']}, {'idx': 12, 'term': 'Battling Overconfidence', 'naming': ['q0']}, {'idx': 17, 'term': 'Automation Aligned with Business Strategy', 'naming': []}, {'idx': 18, 'term': 'Cost Innovations', 'naming': []}]
- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0']}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0']}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0', 'q2']}, {'idx': 7, 'term': 'Sound Editing', 'naming': ['q1', 'q2']}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0']}]

Strict misses (silent):

- single: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0'], 'in_union': False}, {'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': [], 'in_union': False}, {'idx': 7, 'term': 'Sound Editing', 'naming': [], 'in_union': False}, {'idx': 9, 'term': 'Rewards of Good Type Development', 'naming': [], 'in_union': False}, {'idx': 10, 'term': 'Multiple moments', 'naming': [], 'in_union': False}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}, {'idx': 12, 'term': 'Battling Overconfidence', 'naming': ['q0'], 'in_union': True}, {'idx': 17, 'term': 'Automation Aligned with Business Strategy', 'naming': [], 'in_union': False}, {'idx': 18, 'term': 'Cost Innovations', 'naming': [], 'in_union': False}]
- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0', 'q2'], 'in_union': False}, {'idx': 7, 'term': 'Sound Editing', 'naming': ['q1', 'q2'], 'in_union': False}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}, {'idx': 13, 'term': 'Battling Overconfidence', 'naming': ['q0'], 'in_union': True}]
