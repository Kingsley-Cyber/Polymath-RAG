---
title: "Chat baseline — b11-steps12"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — b11-steps12

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer default; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 10 |
| errors | 0 |
| gold_in_retrieved | 0.7 |
| gold_in_union | 0.7 |
| gold_in_pre_rerank | 0.6 |
| hit@10_selected | 0.5 |
| mrr_selected | 0.408 |
| gold_cited | 0.6 |
| wall_p50_s | 28.42 |
| wall_p90_s | 42.45 |
| deaths | {'CITED': 6, 'LOST_AT_UNION_TRUNCATION': 1, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_baseline_B.json |
| fixture_version | chat-baseline-B-v3 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 9 |
| tags_total | 120 |
| tags_valid | 120 |
| abstain_markers | 1 |
| engines | {'chat-retrieval-v2': 10} |
| dims_total | 0 |
| dims_covered | 0 |
| dims_covered_gold | 0 |
| dims_silent | 0 |
| dims_system_ok | 0 |
| dims_system_ok_rate | 0.0 |
| dims_unnamed | 0 |
| dims_in_union | 0 |
| dims_flagged | 0 |
| dims_ok | 0 |
| dims_ok_rate | 0.0 |
| dims_covered_rate | 0.0 |
| compiled_queries_mean | 0.0 |
| survival_selected_given_union | 0.857 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 5 |
| doc_share_top_mean | 0.473 |
| phase_retrieve_p50_s | 3.33 |
| rerank_p50_s | 0.59 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 10 |
| degraded_turns | 3 |
| answer_chars_p50 | 2212 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 30.37 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 27.55 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 27.9 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 2 | 22.35 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 28.94 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 11.22 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 55.89 |
| cinema | What does the book say about movement of an object with a ba | CITED | 12 | 18.82 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 42.45 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 40.5 |
