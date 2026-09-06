---
title: "Chat baseline — final-B-live"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — final-B-live

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.833 |
| hit@10_selected | 0.667 |
| mrr_selected | 0.595 |
| gold_cited | 0.667 |
| wall_p50_s | 10.11 |
| wall_p90_s | 17.24 |
| deaths | {'CITED': 20, 'IGNORED_BY_LLM': 2, 'LOST_AT_SELECTION': 3, 'LOST_AT_UNION_TRUNCATION': 2, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_baseline_B.json |
| fixture_version | chat-baseline-B-v3 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 0.0 |
| answers_with_tags | 0 |
| tags_total | 0 |
| tags_valid | 0 |
| abstain_markers | 0 |
| engines | {'chat-retrieval-v2': 30} |
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
| survival_selected_given_union | 0.815 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 10 |
| doc_share_top_mean | 0.644 |
| phase_retrieve_p50_s | 8.15 |
| rerank_p50_s | 5.02 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 15 |
| answer_chars_p50 | 4038 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 11.52 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 12.01 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 13.15 |
| cinema | What does the book say about miscellaneous drawing tips? | IGNORED_BY_LLM | 5 | 37.77 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 13.2 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 16.75 |
| cinema | What does the book say about affect, fatigue, and injury are | IGNORED_BY_LLM | 2 | 15.77 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_SELECTION | None | 12.4 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 11.68 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 27.98 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 11.54 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 17.24 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 10.12 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 7.75 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 8.36 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 8.39 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 11 | 6.33 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 6.68 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 1 | 10.59 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 2 | 19.24 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 7.21 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 7.79 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 6.71 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 8.06 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 8.81 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 8.23 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 10.09 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 7.35 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 14 | 8.31 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 7.39 |
