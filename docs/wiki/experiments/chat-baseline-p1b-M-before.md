---
title: "Chat baseline — p1b-M-before"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1b-M-before

Fixture `eval/fixtures/chat_multi_M.json` (chat-multi-M-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2-single; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.933 |
| gold_in_pre_rerank | 0.867 |
| hit@10_selected | 0.733 |
| mrr_selected | 0.551 |
| gold_cited | 0.6 |
| wall_p50_s | 9.92 |
| wall_p90_s | 36.89 |
| deaths | {'CITED': 18, 'IGNORED_BY_LLM': 6, 'LOST_AT_SELECTION': 2, 'LOST_AT_UNION_TRUNCATION': 2, 'NEVER_RETRIEVED': 2} |
| compiler | on |
| retrieval | v2-single |
| fixture | eval/fixtures/chat_multi_M.json |
| fixture_version | chat-multi-M-v1 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 1 |
| tags_total | 1 |
| tags_valid | 1 |
| abstain_markers | 0 |
| engines | {'chat-retrieval-v2': 30} |
| dims_total | 60 |
| dims_covered | 47 |
| dims_covered_gold | 29 |
| dims_silent | 13 |
| dims_system_ok | 51 |
| dims_system_ok_rate | 0.85 |
| dims_unnamed | 10 |
| dims_in_union | 39 |
| dims_flagged | 0 |
| dims_ok | 47 |
| dims_ok_rate | 0.783 |
| dims_covered_rate | 0.783 |
| compiled_queries_mean | 1.0 |
| phase_retrieve_p50_s | 7.55 |
| rerank_p50_s | 4.92 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 4076 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | Compare what the book says about making your own chroma keye | CITED | 1 | 11.59 |
| cinema | Compare what the book says about nonsquare pixels with what  | LOST_AT_UNION_TRUNCATION | None | 36.89 |
| cinema | Compare what the book says about oebps/ritc 9781119685401 ep | LOST_AT_UNION_TRUNCATION | None | 36.36 |
| cinema | Compare what the book says about miscellaneous drawing tips  | IGNORED_BY_LLM | 1 | 38.31 |
| cinema | Compare what the book says about transcoding versus color re | CITED | 1 | 96.46 |
| cinema | Compare what the book says about FACE OFF with what it says  | NEVER_RETRIEVED | None | 38.87 |
| cinema | Compare what the book says about affect, fatigue, and injury | CITED | 11 | 8.28 |
| cinema | Compare what the book says about movement of an object with  | NEVER_RETRIEVED | None | 8.6 |
| cinema | Compare what the book says about sound editing with what it  | CITED | 1 | 27.76 |
| cinema | Compare what the book says about write radio sparely with wh | IGNORED_BY_LLM | 2 | 9.53 |
| cinema | Compare what the book says about rewards of good type develo | IGNORED_BY_LLM | 1 | 9.69 |
| cinema | Compare what the book says about multiple moments with what  | CITED | 1 | 9.33 |
| cinema | Compare what the book says about PREMISE AND THEME with what | IGNORED_BY_LLM | 4 | 11.55 |
| cinema | Compare what the book says about battling overconfidence wit | CITED | 1 | 11.08 |
| cinema | Compare what the book says about changing a level within a c | IGNORED_BY_LLM | 1 | 11.9 |
| ecom-meta-v1 | Compare what the book says about why innovative leaders make | LOST_AT_SELECTION | None | 8.48 |
| ecom-meta-v1 | Compare what the book says about WHAT PROGRESS IS REALLY LIK | CITED | 10 | 11.23 |
| ecom-meta-v1 | Compare what the book says about the big idea with what it s | LOST_AT_SELECTION | None | 8.1 |
| ecom-meta-v1 | Compare what the book says about automation aligned with bus | CITED | 8 | 19.83 |
| ecom-meta-v1 | Compare what the book says about cost innovations with what  | CITED | 1 | 7.99 |
| ecom-meta-v1 | Compare what the book says about the migration of capabiliti | IGNORED_BY_LLM | 1 | 8.1 |
| ecom-meta-v1 | Compare what the book says about the capabilities viewpoint  | CITED | 7 | 8.13 |
| ecom-meta-v1 | Compare what the book says about getting the categories righ | CITED | 1 | 10.15 |
| ecom-meta-v1 | Compare what the book says about discovery skill #4: network | CITED | 4 | 9.54 |
| ecom-meta-v1 | Compare what the book says about creating capabilities throu | CITED | 1 | 7.75 |
| ecom-meta-v1 | Compare what the book says about solar versus conventional e | CITED | 1 | 10.51 |
| ecom-meta-v1 | Compare what the book says about cost structures and value n | CITED | 2 | 7.45 |
| ecom-meta-v1 | Compare what the book says about HOW DISK DRIVES WORK with w | CITED | 1 | 13.86 |
| ecom-meta-v1 | Compare what the book says about innovations that will susta | CITED | 13 | 9.33 |
| ecom-meta-v1 | Compare what the book says about make it platform-centric wi | CITED | 2 | 9.02 |
