---
title: "Chat baseline — p1b-M-after"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1b-M-after

Fixture `eval/fixtures/chat_multi_M.json` (chat-multi-M-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.933 |
| gold_in_pre_rerank | 0.9 |
| hit@10_selected | 0.7 |
| mrr_selected | 0.548 |
| gold_cited | 0.567 |
| wall_p50_s | 14.57 |
| wall_p90_s | 34.96 |
| deaths | {'CITED': 17, 'IGNORED_BY_LLM': 7, 'LOST_AT_SELECTION': 3, 'LOST_AT_UNION_TRUNCATION': 1, 'NEVER_RETRIEVED': 2} |
| compiler | on |
| retrieval | v2 |
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
| dims_covered | 46 |
| dims_covered_gold | 29 |
| dims_silent | 7 |
| dims_system_ok | 59 |
| dims_system_ok_rate | 0.983 |
| dims_unnamed | 0 |
| dims_in_union | 48 |
| dims_flagged | 7 |
| dims_ok | 53 |
| dims_ok_rate | 0.883 |
| dims_covered_rate | 0.767 |
| compiled_queries_mean | 2.37 |
| phase_retrieve_p50_s | 12.38 |
| rerank_p50_s | 6.35 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 4053 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | Compare what the book says about making your own chroma keye | CITED | 1 | 11.51 |
| cinema | Compare what the book says about nonsquare pixels with what  | LOST_AT_UNION_TRUNCATION | None | 49.85 |
| cinema | Compare what the book says about oebps/ritc 9781119685401 ep | IGNORED_BY_LLM | 4 | 13.83 |
| cinema | Compare what the book says about miscellaneous drawing tips  | IGNORED_BY_LLM | 1 | 27.37 |
| cinema | Compare what the book says about transcoding versus color re | CITED | 1 | 34.71 |
| cinema | Compare what the book says about FACE OFF with what it says  | NEVER_RETRIEVED | None | 24.68 |
| cinema | Compare what the book says about affect, fatigue, and injury | CITED | 11 | 19.82 |
| cinema | Compare what the book says about movement of an object with  | NEVER_RETRIEVED | None | 15.24 |
| cinema | Compare what the book says about sound editing with what it  | CITED | 1 | 24.38 |
| cinema | Compare what the book says about write radio sparely with wh | IGNORED_BY_LLM | 2 | 14.66 |
| cinema | Compare what the book says about rewards of good type develo | IGNORED_BY_LLM | 1 | 8.31 |
| cinema | Compare what the book says about multiple moments with what  | CITED | 1 | 23.46 |
| cinema | Compare what the book says about PREMISE AND THEME with what | IGNORED_BY_LLM | 3 | 12.07 |
| cinema | Compare what the book says about battling overconfidence wit | IGNORED_BY_LLM | 1 | 17.94 |
| cinema | Compare what the book says about changing a level within a c | CITED | 1 | 11.13 |
| ecom-meta-v1 | Compare what the book says about why innovative leaders make | LOST_AT_SELECTION | None | 10.4 |
| ecom-meta-v1 | Compare what the book says about WHAT PROGRESS IS REALLY LIK | CITED | 11 | 14.48 |
| ecom-meta-v1 | Compare what the book says about the big idea with what it s | LOST_AT_SELECTION | None | 14.32 |
| ecom-meta-v1 | Compare what the book says about automation aligned with bus | CITED | 6 | 10.1 |
| ecom-meta-v1 | Compare what the book says about cost innovations with what  | IGNORED_BY_LLM | 4 | 11.07 |
| ecom-meta-v1 | Compare what the book says about the migration of capabiliti | CITED | 1 | 10.12 |
| ecom-meta-v1 | Compare what the book says about the capabilities viewpoint  | LOST_AT_SELECTION | None | 11.3 |
| ecom-meta-v1 | Compare what the book says about getting the categories righ | CITED | 1 | 13.7 |
| ecom-meta-v1 | Compare what the book says about discovery skill #4: network | CITED | 5 | 12.31 |
| ecom-meta-v1 | Compare what the book says about creating capabilities throu | CITED | 1 | 15.16 |
| ecom-meta-v1 | Compare what the book says about solar versus conventional e | CITED | 1 | 15.77 |
| ecom-meta-v1 | Compare what the book says about cost structures and value n | CITED | 2 | 10.13 |
| ecom-meta-v1 | Compare what the book says about HOW DISK DRIVES WORK with w | CITED | 1 | 57.35 |
| ecom-meta-v1 | Compare what the book says about innovations that will susta | CITED | 14 | 81.01 |
| ecom-meta-v1 | Compare what the book says about make it platform-centric wi | CITED | 1 | 34.96 |
