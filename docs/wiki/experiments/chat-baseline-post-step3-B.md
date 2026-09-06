---
title: "Chat baseline — post-step3-B"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — post-step3-B

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.733 |
| hit@10_selected | 0.6 |
| mrr_selected | 0.505 |
| gold_cited | 0.7 |
| wall_p50_s | 7.93 |
| wall_p90_s | 14.53 |
| deaths | {'CITED': 21, 'LOST_AT_SELECTION': 1, 'LOST_AT_UNION_TRUNCATION': 5, 'NEVER_RETRIEVED': 3} |
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
| survival_selected_given_union | 0.778 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 9 |
| doc_share_top_mean | 0.491 |
| phase_retrieve_p50_s | 5.63 |
| rerank_p50_s | 2.12 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 10 |
| answer_chars_p50 | 3893 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 7.69 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 4.35 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 6.94 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 2 | 5.68 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 9.89 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 7.93 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 14.53 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 7.97 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 13.66 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 11.23 |
| cinema | What does the book say about rewards of good type developmen | LOST_AT_UNION_TRUNCATION | None | 6.49 |
| cinema | What does the book say about multiple moments? | CITED | 12 | 7.17 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 15.92 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 20.48 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 23.94 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 10.57 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 10 | 12.93 |
| ecom-meta-v1 | What does the book say about the big idea? | CITED | 15 | 5.06 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 2 | 6.4 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 4.86 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 8.89 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 5.27 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 5.46 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 5.2 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 13.42 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 7.93 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 8.64 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 5.59 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 14 | 8.16 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 4.54 |
