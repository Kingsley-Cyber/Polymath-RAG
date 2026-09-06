---
title: "CHAT-M-REPLAY final2-M: fixture M replayed in-process with frozen plans"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# CHAT-M-REPLAY final2-M

run 2026-09-06T12:42:38+00:00 · fixture M · 30 questions · arms single, multi · plans `eval/fixtures/chat_multi_M_plans.json` · rerank_max override None · OOM during run {'sidecar_embedder': 20, 'sidecar_reranker': 19}


| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | 30 | 0.9 (54/60) | 0.933 (56/60) | 0.9 | 0.933 | 5 | 6 | 29 | 39 | 0 | 16.21 | 38.13 | 9202.0 | 4996.6 | 16169.2 | 24.0 | 9/9 | 16 | 7.44 | 3834.4 |
| multi | 30 | 1.0 (60/60) | 1.0 (60/60) | 1.0 | 1.0 | 6 | 0 | 33 | 50 | 0 | 11.32 | 28.12 | 3402.7 | 8003.1 | 11240.4 | 24.0 | 11/10 | 17 | 8.97 | 4930.9 |

Residual (not system-honest OK):

- single: [{'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': []}, {'idx': 9, 'term': 'Rewards of Good Type Development', 'naming': []}, {'idx': 10, 'term': 'Multiple moments', 'naming': []}, {'idx': 17, 'term': 'Automation Aligned with Business Strategy', 'naming': []}]
- multi: none

Strict misses (silent):

- single: [{'idx': 6, 'term': 'Movement of an Object with a Background', 'naming': [], 'in_union': False}, {'idx': 9, 'term': 'Rewards of Good Type Development', 'naming': [], 'in_union': False}, {'idx': 10, 'term': 'Multiple moments', 'naming': [], 'in_union': False}, {'idx': 11, 'term': 'Multiple moments', 'naming': ['q0'], 'in_union': False}, {'idx': 12, 'term': 'Battling Overconfidence', 'naming': ['q0'], 'in_union': True}, {'idx': 17, 'term': 'Automation Aligned with Business Strategy', 'naming': [], 'in_union': False}]
- multi: none
