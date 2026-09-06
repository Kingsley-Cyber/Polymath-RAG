---
title: "Chat baseline — final-M-live"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — final-M-live

Fixture `eval/fixtures/chat_multi_M.json` (chat-multi-M-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.933 |
| gold_in_pre_rerank | 0.933 |
| hit@10_selected | 0.8 |
| mrr_selected | 0.625 |
| gold_cited | 0.733 |
| wall_p50_s | 12.79 |
| wall_p90_s | 19.52 |
| deaths | {'CITED': 22, 'IGNORED_BY_LLM': 5, 'LOST_AT_SELECTION': 1, 'NEVER_RETRIEVED': 2} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_multi_M.json |
| fixture_version | chat-multi-M-v1 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 1 |
| tags_total | 2 |
| tags_valid | 2 |
| abstain_markers | 0 |
| engines | {'chat-retrieval-v2': 30} |
| dims_total | 60 |
| dims_covered | 53 |
| dims_covered_gold | 37 |
| dims_silent | 5 |
| dims_system_ok | 57 |
| dims_system_ok_rate | 0.95 |
| dims_unnamed | 0 |
| dims_in_union | 48 |
| dims_flagged | 2 |
| dims_ok | 55 |
| dims_ok_rate | 0.917 |
| dims_covered_rate | 0.883 |
| compiled_queries_mean | 2.37 |
| survival_selected_given_union | 0.964 |
| dominance_violations | 1 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 17 |
| doc_share_top_mean | 0.582 |
| phase_retrieve_p50_s | 10.81 |
| rerank_p50_s | 6.58 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 20 |
| answer_chars_p50 | 3974 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | Compare what the book says about making your own chroma keye | CITED | 1 | 8.07 |
| cinema | Compare what the book says about nonsquare pixels with what  | CITED | 1 | 13.29 |
| cinema | Compare what the book says about oebps/ritc 9781119685401 ep | IGNORED_BY_LLM | 9 | 19.4 |
| cinema | Compare what the book says about miscellaneous drawing tips  | IGNORED_BY_LLM | 3 | 12.72 |
| cinema | Compare what the book says about transcoding versus color re | CITED | 1 | 12.87 |
| cinema | Compare what the book says about FACE OFF with what it says  | NEVER_RETRIEVED | None | 17.15 |
| cinema | Compare what the book says about affect, fatigue, and injury | CITED | 13 | 10.77 |
| cinema | Compare what the book says about movement of an object with  | NEVER_RETRIEVED | None | 12.93 |
| cinema | Compare what the book says about sound editing with what it  | CITED | 1 | 17.38 |
| cinema | Compare what the book says about write radio sparely with wh | IGNORED_BY_LLM | 2 | 9.81 |
| cinema | Compare what the book says about rewards of good type develo | CITED | 1 | 11.93 |
| cinema | Compare what the book says about multiple moments with what  | CITED | 1 | 17.95 |
| cinema | Compare what the book says about PREMISE AND THEME with what | IGNORED_BY_LLM | 3 | 9.77 |
| cinema | Compare what the book says about battling overconfidence wit | CITED | 1 | 19.52 |
| cinema | Compare what the book says about changing a level within a c | CITED | 1 | 21.09 |
| ecom-meta-v1 | Compare what the book says about why innovative leaders make | CITED | 14 | 8.1 |
| ecom-meta-v1 | Compare what the book says about WHAT PROGRESS IS REALLY LIK | CITED | 12 | 10.1 |
| ecom-meta-v1 | Compare what the book says about the big idea with what it s | CITED | 2 | 14.72 |
| ecom-meta-v1 | Compare what the book says about automation aligned with bus | CITED | 2 | 24.49 |
| ecom-meta-v1 | Compare what the book says about cost innovations with what  | IGNORED_BY_LLM | 2 | 9.06 |
| ecom-meta-v1 | Compare what the book says about the migration of capabiliti | CITED | 1 | 8.5 |
| ecom-meta-v1 | Compare what the book says about the capabilities viewpoint  | LOST_AT_SELECTION | None | 24.27 |
| ecom-meta-v1 | Compare what the book says about getting the categories righ | CITED | 1 | 7.37 |
| ecom-meta-v1 | Compare what the book says about discovery skill #4: network | CITED | 1 | 11.57 |
| ecom-meta-v1 | Compare what the book says about creating capabilities throu | CITED | 1 | 14.61 |
| ecom-meta-v1 | Compare what the book says about solar versus conventional e | CITED | 1 | 9.98 |
| ecom-meta-v1 | Compare what the book says about cost structures and value n | CITED | 1 | 16.03 |
| ecom-meta-v1 | Compare what the book says about HOW DISK DRIVES WORK with w | CITED | 2 | 11.94 |
| ecom-meta-v1 | Compare what the book says about innovations that will susta | CITED | 4 | 19.04 |
| ecom-meta-v1 | Compare what the book says about make it platform-centric wi | CITED | 1 | 12.08 |
