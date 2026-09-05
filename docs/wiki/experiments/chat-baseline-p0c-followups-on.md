---
title: "Chat baseline — p0c-followups-on"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p0c-followups-on

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; follow-ups True; HYBRID via /chat/stream.

Recovery vs `p0c-B-on`: paired 30, both 18, only reference 1, only this 0, neither 11; reference hit@10 0.633; **hit@10 on the reference-retrievable subset 0.947**.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.733 |
| gold_in_union | 0.7 |
| gold_in_pre_rerank | 0.6 |
| hit@10_selected | 0.6 |
| mrr_selected | 0.443 |
| gold_cited | 0.167 |
| wall_p50_s | 9.52 |
| wall_p90_s | 14.36 |
| deaths | {'CITED': 5, 'IGNORED_BY_LLM': 13, 'LOST_AT_UNION_TRUNCATION': 4, 'NEVER_RETRIEVED': 8} |
| compiler | on |
| followups | True |
| recovery | {'reference': 'p0c-B-on', 'paired': 30, 'both': 18, 'only_reference': 1, 'only_this': 0, 'neither': 11, 'reference_hit@10': 0.633, 'subset_hit@10': 0.947} |
| compiler_fallbacks | 0 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | How does that work in practice? | IGNORED_BY_LLM | 1 | 9.66 |
| cinema | Can you say more about that? | IGNORED_BY_LLM | 2 | 9.7 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 8.45 |
| cinema | How does that work in practice? | LOST_AT_UNION_TRUNCATION | None | 10.85 |
| cinema | Can you say more about that? | IGNORED_BY_LLM | 1 | 14.79 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 14.36 |
| cinema | How does that work in practice? | LOST_AT_UNION_TRUNCATION | None | 11.61 |
| cinema | Can you say more about that? | NEVER_RETRIEVED | None | 2.08 |
| cinema | Why does that matter? | NEVER_RETRIEVED | None | 10.57 |
| cinema | How does that work in practice? | IGNORED_BY_LLM | 2 | 8.32 |
| cinema | Can you say more about that? | IGNORED_BY_LLM | 1 | 9.62 |
| cinema | Why does that matter? | IGNORED_BY_LLM | 1 | 10.93 |
| cinema | How does that work in practice? | IGNORED_BY_LLM | 1 | 18.39 |
| cinema | Can you say more about that? | CITED | 1 | 22.79 |
| cinema | Why does that matter? | IGNORED_BY_LLM | 1 | 8.24 |
| ecom-meta-v1 | How does that work in practice? | CITED | 8 | 8.33 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 3.44 |
| ecom-meta-v1 | Why does that matter? | LOST_AT_UNION_TRUNCATION | None | 8.33 |
| ecom-meta-v1 | How does that work in practice? | IGNORED_BY_LLM | 6 | 7.56 |
| ecom-meta-v1 | Can you say more about that? | IGNORED_BY_LLM | 3 | 7.19 |
| ecom-meta-v1 | Why does that matter? | CITED | 1 | 7.99 |
| ecom-meta-v1 | How does that work in practice? | LOST_AT_UNION_TRUNCATION | None | 10.51 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 2.54 |
| ecom-meta-v1 | Why does that matter? | NEVER_RETRIEVED | None | 12.85 |
| ecom-meta-v1 | How does that work in practice? | CITED | 1 | 9.55 |
| ecom-meta-v1 | Can you say more about that? | CITED | 1 | 7.58 |
| ecom-meta-v1 | Why does that matter? | IGNORED_BY_LLM | 1 | 8.57 |
| ecom-meta-v1 | How does that work in practice? | IGNORED_BY_LLM | 2 | 7.84 |
| ecom-meta-v1 | Can you say more about that? | NEVER_RETRIEVED | None | 9.48 |
| ecom-meta-v1 | Why does that matter? | IGNORED_BY_LLM | 6 | 11.09 |
