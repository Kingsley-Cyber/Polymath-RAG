---
title: "Chat baseline — post2-step3-B"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — post2-step3-B

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.767 |
| hit@10_selected | 0.633 |
| mrr_selected | 0.566 |
| gold_cited | 0.667 |
| wall_p50_s | 6.0 |
| wall_p90_s | 8.95 |
| deaths | {'CITED': 20, 'IGNORED_BY_LLM': 1, 'LOST_AT_SELECTION': 2, 'LOST_AT_UNION_TRUNCATION': 4, 'NEVER_RETRIEVED': 3} |
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
| doc_share_top_mean | 0.573 |
| phase_retrieve_p50_s | 3.99 |
| rerank_p50_s | 1.77 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 6 |
| answer_chars_p50 | 3922 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 15.04 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 5.63 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 8.95 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 2 | 7.86 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 8.11 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 7.18 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 6.06 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 5.26 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 4.63 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 6.09 |
| cinema | What does the book say about rewards of good type developmen | IGNORED_BY_LLM | 1 | 5.94 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 6.75 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 5.94 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 7.02 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 10.12 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 8.76 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 11 | 5.8 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 4.23 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 2 | 5.41 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 4.84 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 6.31 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 5.24 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 6.1 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 5.27 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 4.71 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 5.59 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 5.81 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 9.52 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 15 | 5.2 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 6.42 |
