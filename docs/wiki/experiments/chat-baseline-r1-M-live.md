---
title: "Chat baseline — r1-M-live"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — r1-M-live

Fixture `eval/fixtures/chat_multi_M.json` (chat-multi-M-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.867 |
| gold_in_union | 0.933 |
| gold_in_pre_rerank | 0.9 |
| hit@10_selected | 0.767 |
| mrr_selected | 0.554 |
| gold_cited | 0.6 |
| wall_p50_s | 18.38 |
| wall_p90_s | 34.34 |
| deaths | {'CITED': 18, 'IGNORED_BY_LLM': 7, 'LOST_AT_SELECTION': 2, 'LOST_AT_UNION_TRUNCATION': 1, 'NEVER_RETRIEVED': 2} |
| compiler | on |
| retrieval | v2 |
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
| dims_covered | 49 |
| dims_covered_gold | 30 |
| dims_silent | 6 |
| dims_system_ok | 60 |
| dims_system_ok_rate | 1.0 |
| dims_unnamed | 0 |
| dims_in_union | 48 |
| dims_flagged | 5 |
| dims_ok | 54 |
| dims_ok_rate | 0.9 |
| dims_covered_rate | 0.817 |
| compiled_queries_mean | 2.37 |
| phase_retrieve_p50_s | 17.8 |
| rerank_p50_s | 6.1 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 4053 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | Compare what the book says about making your own chroma keye | CITED | 1 | 11.0 |
| cinema | Compare what the book says about nonsquare pixels with what  | LOST_AT_UNION_TRUNCATION | None | 49.63 |
| cinema | Compare what the book says about oebps/ritc 9781119685401 ep | IGNORED_BY_LLM | 4 | 12.22 |
| cinema | Compare what the book says about miscellaneous drawing tips  | IGNORED_BY_LLM | 3 | 11.18 |
| cinema | Compare what the book says about transcoding versus color re | CITED | 1 | 32.8 |
| cinema | Compare what the book says about FACE OFF with what it says  | NEVER_RETRIEVED | None | 28.57 |
| cinema | Compare what the book says about affect, fatigue, and injury | CITED | 11 | 20.37 |
| cinema | Compare what the book says about movement of an object with  | NEVER_RETRIEVED | None | 14.98 |
| cinema | Compare what the book says about sound editing with what it  | CITED | 1 | 10.73 |
| cinema | Compare what the book says about write radio sparely with wh | IGNORED_BY_LLM | 2 | 15.22 |
| cinema | Compare what the book says about rewards of good type develo | CITED | 1 | 10.92 |
| cinema | Compare what the book says about multiple moments with what  | CITED | 1 | 9.64 |
| cinema | Compare what the book says about PREMISE AND THEME with what | IGNORED_BY_LLM | 3 | 10.73 |
| cinema | Compare what the book says about battling overconfidence wit | IGNORED_BY_LLM | 1 | 14.02 |
| cinema | Compare what the book says about changing a level within a c | IGNORED_BY_LLM | 1 | 9.07 |
| ecom-meta-v1 | Compare what the book says about why innovative leaders make | LOST_AT_SELECTION | None | 8.05 |
| ecom-meta-v1 | Compare what the book says about WHAT PROGRESS IS REALLY LIK | CITED | 11 | 9.87 |
| ecom-meta-v1 | Compare what the book says about the big idea with what it s | CITED | 7 | 30.56 |
| ecom-meta-v1 | Compare what the book says about automation aligned with bus | CITED | 2 | 26.57 |
| ecom-meta-v1 | Compare what the book says about cost innovations with what  | CITED | 1 | 40.6 |
| ecom-meta-v1 | Compare what the book says about the migration of capabiliti | IGNORED_BY_LLM | 1 | 73.01 |
| ecom-meta-v1 | Compare what the book says about the capabilities viewpoint  | LOST_AT_SELECTION | None | 32.35 |
| ecom-meta-v1 | Compare what the book says about getting the categories righ | CITED | 1 | 16.73 |
| ecom-meta-v1 | Compare what the book says about discovery skill #4: network | CITED | 4 | 34.34 |
| ecom-meta-v1 | Compare what the book says about creating capabilities throu | CITED | 1 | 24.53 |
| ecom-meta-v1 | Compare what the book says about solar versus conventional e | CITED | 1 | 33.99 |
| ecom-meta-v1 | Compare what the book says about cost structures and value n | CITED | 2 | 34.15 |
| ecom-meta-v1 | Compare what the book says about HOW DISK DRIVES WORK with w | CITED | 1 | 20.03 |
| ecom-meta-v1 | Compare what the book says about innovations that will susta | CITED | 7 | 16.28 |
| ecom-meta-v1 | Compare what the book says about make it platform-centric wi | CITED | 2 | 22.54 |
