---
title: "Chat baseline — r1-M-live-single"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — r1-M-live-single

Fixture `eval/fixtures/chat_multi_M.json` (chat-multi-M-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2-single; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.867 |
| hit@10_selected | 0.833 |
| mrr_selected | 0.581 |
| gold_cited | 0.667 |
| wall_p50_s | 12.07 |
| wall_p90_s | 29.9 |
| deaths | {'CITED': 20, 'IGNORED_BY_LLM': 5, 'LOST_AT_SELECTION': 1, 'LOST_AT_UNION_TRUNCATION': 1, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2-single |
| fixture | eval/fixtures/chat_multi_M.json |
| fixture_version | chat-multi-M-v1 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 1 |
| tags_total | 3 |
| tags_valid | 3 |
| abstain_markers | 0 |
| engines | {'chat-retrieval-v2': 30} |
| dims_total | 60 |
| dims_covered | 47 |
| dims_covered_gold | 32 |
| dims_silent | 13 |
| dims_system_ok | 56 |
| dims_system_ok_rate | 0.933 |
| dims_unnamed | 5 |
| dims_in_union | 44 |
| dims_flagged | 0 |
| dims_ok | 47 |
| dims_ok_rate | 0.783 |
| dims_covered_rate | 0.783 |
| compiled_queries_mean | 1.0 |
| phase_retrieve_p50_s | 9.68 |
| rerank_p50_s | 7.53 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 4077 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | Compare what the book says about making your own chroma keye | CITED | 1 | 12.94 |
| cinema | Compare what the book says about nonsquare pixels with what  | LOST_AT_UNION_TRUNCATION | None | 52.67 |
| cinema | Compare what the book says about oebps/ritc 9781119685401 ep | NEVER_RETRIEVED | None | 37.95 |
| cinema | Compare what the book says about miscellaneous drawing tips  | IGNORED_BY_LLM | 1 | 29.23 |
| cinema | Compare what the book says about transcoding versus color re | CITED | 1 | 70.19 |
| cinema | Compare what the book says about FACE OFF with what it says  | NEVER_RETRIEVED | None | 29.9 |
| cinema | Compare what the book says about affect, fatigue, and injury | CITED | 6 | 14.06 |
| cinema | Compare what the book says about movement of an object with  | NEVER_RETRIEVED | None | 8.88 |
| cinema | Compare what the book says about sound editing with what it  | CITED | 1 | 27.42 |
| cinema | Compare what the book says about write radio sparely with wh | IGNORED_BY_LLM | 2 | 10.1 |
| cinema | Compare what the book says about rewards of good type develo | IGNORED_BY_LLM | 1 | 11.91 |
| cinema | Compare what the book says about multiple moments with what  | CITED | 1 | 11.7 |
| cinema | Compare what the book says about PREMISE AND THEME with what | IGNORED_BY_LLM | 4 | 9.86 |
| cinema | Compare what the book says about battling overconfidence wit | IGNORED_BY_LLM | 1 | 10.98 |
| cinema | Compare what the book says about changing a level within a c | CITED | 1 | 9.06 |
| ecom-meta-v1 | Compare what the book says about why innovative leaders make | LOST_AT_SELECTION | None | 9.87 |
| ecom-meta-v1 | Compare what the book says about WHAT PROGRESS IS REALLY LIK | CITED | 10 | 11.47 |
| ecom-meta-v1 | Compare what the book says about the big idea with what it s | CITED | 7 | 25.59 |
| ecom-meta-v1 | Compare what the book says about automation aligned with bus | CITED | 4 | 24.88 |
| ecom-meta-v1 | Compare what the book says about cost innovations with what  | CITED | 1 | 10.28 |
| ecom-meta-v1 | Compare what the book says about the migration of capabiliti | CITED | 1 | 12.53 |
| ecom-meta-v1 | Compare what the book says about the capabilities viewpoint  | CITED | 7 | 7.68 |
| ecom-meta-v1 | Compare what the book says about getting the categories righ | CITED | 1 | 10.49 |
| ecom-meta-v1 | Compare what the book says about discovery skill #4: network | CITED | 4 | 7.66 |
| ecom-meta-v1 | Compare what the book says about creating capabilities throu | CITED | 1 | 11.41 |
| ecom-meta-v1 | Compare what the book says about solar versus conventional e | CITED | 1 | 13.84 |
| ecom-meta-v1 | Compare what the book says about cost structures and value n | CITED | 1 | 17.01 |
| ecom-meta-v1 | Compare what the book says about HOW DISK DRIVES WORK with w | CITED | 1 | 8.54 |
| ecom-meta-v1 | Compare what the book says about innovations that will susta | CITED | 8 | 12.22 |
| ecom-meta-v1 | Compare what the book says about make it platform-centric wi | CITED | 2 | 13.59 |
