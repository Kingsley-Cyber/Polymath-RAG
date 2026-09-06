---
title: "Chat baseline — pre-step3-B"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — pre-step3-B

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.833 |
| hit@10_selected | 0.667 |
| mrr_selected | 0.581 |
| gold_cited | 0.767 |
| wall_p50_s | 5.05 |
| wall_p90_s | 7.02 |
| deaths | {'CITED': 23, 'LOST_AT_SELECTION': 2, 'LOST_AT_UNION_TRUNCATION': 2, 'NEVER_RETRIEVED': 3} |
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
| survival_selected_given_union | 0.852 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 7 |
| doc_share_top_mean | 0.658 |
| phase_retrieve_p50_s | 3.08 |
| rerank_p50_s | 1.02 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 1 |
| answer_chars_p50 | 4024 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 4.76 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 5.08 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 5.55 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 2 | 8.44 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 6.71 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 4.13 |
| cinema | What does the book say about affect, fatigue, and injury are | CITED | 3 | 6.42 |
| cinema | What does the book say about movement of an object with a ba | CITED | 11 | 4.59 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 5.74 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 5.79 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 4.35 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 5.03 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 7.02 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 5.11 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 4.8 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 5.51 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 11 | 3.66 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 3.77 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 2 | 6.34 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 4.58 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 8.15 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 4.85 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 4.95 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 4.55 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 4.71 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 5.65 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 11.17 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 5.58 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 14 | 4.29 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 3.88 |
