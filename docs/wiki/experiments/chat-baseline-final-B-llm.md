---
title: "Chat baseline — final-B-llm"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — final-B-llm

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer default; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.833 |
| hit@10_selected | 0.667 |
| mrr_selected | 0.574 |
| gold_cited | 0.7 |
| wall_p50_s | 16.68 |
| wall_p90_s | 22.94 |
| deaths | {'CITED': 21, 'IGNORED_BY_LLM': 1, 'LOST_AT_SELECTION': 3, 'LOST_AT_UNION_TRUNCATION': 2, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_baseline_B.json |
| fixture_version | chat-baseline-B-v3 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 29 |
| tags_total | 511 |
| tags_valid | 511 |
| abstain_markers | 7 |
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
| dominance_eligible_turns | 12 |
| doc_share_top_mean | 0.638 |
| phase_retrieve_p50_s | 9.01 |
| rerank_p50_s | 5.27 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 14 |
| answer_chars_p50 | 3655 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 16.85 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 14.86 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 17.36 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 3 | 36.03 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 16.61 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 20.77 |
| cinema | What does the book say about affect, fatigue, and injury are | CITED | 13 | 35.52 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_SELECTION | None | 24.58 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 19.08 |
| cinema | What does the book say about write radio sparely? | CITED | 1 | 15.37 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 16.15 |
| cinema | What does the book say about multiple moments? | IGNORED_BY_LLM | 8 | 18.06 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 14.99 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 11.15 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 13.93 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 18.34 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 11 | 12.4 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 16.75 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 1 | 17.27 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 2 | 22.94 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 12.57 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 13.9 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 13.95 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 16.23 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 15.23 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 14.9 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 16.99 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 15.09 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 10 | 17.83 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 17.1 |
