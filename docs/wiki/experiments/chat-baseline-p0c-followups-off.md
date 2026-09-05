---
title: "Chat baseline — p0c-followups-off"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p0c-followups-off

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler off; follow-ups True; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.0 |
| gold_in_union | 0.0 |
| gold_in_pre_rerank | 0.0 |
| hit@10_selected | 0.0 |
| mrr_selected | 0.0 |
| gold_cited | 0.0 |
| wall_p50_s | 6.61 |
| wall_p90_s | 9.84 |
| deaths | {'NEVER_RETRIEVED': 30} |
| compiler | off |
| followups | True |
| compiler_fallbacks | 0 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | How does that work in practice? | NEVER_RETRIEVED | None | 9.84 |
| cinema | Can you say more about that? | NEVER_RETRIEVED | None | 7.76 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 7.78 |
| cinema | How does that work in practice? | NEVER_RETRIEVED | None | 9.99 |
| cinema | Can you say more about that? | NEVER_RETRIEVED | None | 9.63 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 8.92 |
| cinema | How does that work in practice? | NEVER_RETRIEVED | None | 9.55 |
| cinema | Can you say more about that? | NEVER_RETRIEVED | None | 7.98 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 6.86 |
| cinema | How does that work in practice? | NEVER_RETRIEVED | None | 10.15 |
| cinema | Can you say more about that? | NEVER_RETRIEVED | None | 8.27 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 7.16 |
| cinema | How does that work in practice? | NEVER_RETRIEVED | None | 10.73 |
| cinema | Can you say more about that? | NEVER_RETRIEVED | None | 7.05 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 6.12 |
| ecom-meta-v1 | How does that work in practice? | NEVER_RETRIEVED | None | 5.88 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 5.03 |
| ecom-meta-v1 | Why does that matter? | NEVER_RETRIEVED | None | 6.35 |
| ecom-meta-v1 | How does that work in practice? | NEVER_RETRIEVED | None | 3.92 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 5.44 |
| ecom-meta-v1 | Why does that matter? | NEVER_RETRIEVED | None | 2.62 |
| ecom-meta-v1 | How does that work in practice? | NEVER_RETRIEVED | None | 9.47 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 4.65 |
| ecom-meta-v1 | Why does that matter? | NEVER_RETRIEVED | None | 5.77 |
| ecom-meta-v1 | How does that work in practice? | NEVER_RETRIEVED | None | 4.58 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 5.05 |
| ecom-meta-v1 | Why does that matter? | NEVER_RETRIEVED | None | 5.38 |
| ecom-meta-v1 | How does that work in practice? | NEVER_RETRIEVED | None | 6.15 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 4.72 |
| ecom-meta-v1 | Why does that matter? | NEVER_RETRIEVED | None | 5.27 |
