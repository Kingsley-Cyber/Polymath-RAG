---
title: "CHAT-M-REPLAY r1-M: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# CHAT-M-REPLAY r1-M

run 2026-09-06T01:18:43+00:00 · 30 questions · arms single, multi · plans `eval/fixtures/chat_multi_M_plans.json` · OOM during run {'sidecar_embedder': 7, 'sidecar_reranker': 10}

| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.817 (49/60) | 0.9 (54/60) | 0.817 | 0.9 | 0 | 11 | 29 | 39 | 1 | 10.35 | 27.37 | 3252.5 | 5036.9 | 10284.7 | 20.0 | 4/6 | 20 | 9.29 | 4551.0 |
| multi | 30 | 0.917 (55/60) | 1.0 (60/60) | 0.917 | 1.0 | 5 | 5 | 29 | 50 | 0 | 10.76 | 28.15 | 3918.2 | 5694.7 | 10721.4 | 20.0 | 3/4 | 23 | 10.37 | 5542.2 |

Residual (not system-honest OK):

- single: [{'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': []}, {'idx': 7, 'term': 'Sound Editing', 'naming': []}, {'idx': 9, 'term': 'Rewards of Good Type Development', 'naming': []}, {'idx': 10, 'term': 'Multiple moments', 'naming': []}, {'idx': 17, 'term': 'Automation Aligned with Business Strategy', 'naming': []}, {'idx': 18, 'term': 'Cost Innovations', 'naming': []}]
- multi: none

Strict misses (silent):

- single: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 4, 'term': 'FACE OFF', 'naming': ['q0'], 'in_union': False}, {'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': [], 'in_union': False}, {'idx': 7, 'term': 'Sound Editing', 'naming': [], 'in_union': False}, {'idx': 9, 'term': 'Rewards of Good Type Development', 'naming': [], 'in_union': False}, {'idx': 10, 'term': 'Multiple moments', 'naming': [], 'in_union': False}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}, {'idx': 12, 'term': 'Battling Overconfidence', 'naming': ['q0'], 'in_union': True}, {'idx': 17, 'term': 'Automation Aligned with Business Strategy', 'naming': [], 'in_union': False}, {'idx': 18, 'term': 'Cost Innovations', 'naming': [], 'in_union': False}]
- multi: [{'idx': 1, 'term': 'Nonsquare Pixels', 'naming': ['q0'], 'in_union': True}, {'idx': 2, 'term': 'OEBPS/ritc 9781119685401 epub3 035 r1.xhtml', 'naming': ['q0'], 'in_union': False}, {'idx': 3, 'term': 'Miscellaneous Drawing Tips', 'naming': ['q0'], 'in_union': True}, {'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': ['q1', 'q2'], 'in_union': True}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}]
