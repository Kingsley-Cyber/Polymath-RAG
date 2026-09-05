---
title: "Chat baseline — p1b-B-after"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1b-B-after

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.767 |
| hit@10_selected | 0.7 |
| mrr_selected | 0.516 |
| gold_cited | 0.667 |
| wall_p50_s | 13.11 |
| wall_p90_s | 30.92 |
| deaths | {'CITED': 20, 'IGNORED_BY_LLM': 2, 'LOST_AT_SELECTION': 1, 'LOST_AT_UNION_TRUNCATION': 4, 'NEVER_RETRIEVED': 3} |
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
| dims_unnamed | 0 |
| dims_in_union | 0 |
| dims_flagged | 0 |
| dims_ok | 0 |
| dims_ok_rate | 0.0 |
| dims_covered_rate | 0.0 |
| compiled_queries_mean | 0.0 |
| phase_retrieve_p50_s | 11.09 |
| rerank_p50_s | 5.2 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 4024 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 10.62 |
| cinema | What does the book say about nonsquare pixels? | CITED | 3 | 10.48 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 37.14 |
| cinema | What does the book say about miscellaneous drawing tips? | IGNORED_BY_LLM | 3 | 9.7 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 28.95 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 10.01 |
| cinema | What does the book say about affect, fatigue, and injury are | CITED | 4 | 30.92 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 46.91 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 29.56 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 13.17 |
| cinema | What does the book say about rewards of good type developmen | IGNORED_BY_LLM | 1 | 14.64 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 26.81 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 31.12 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 10.04 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 13.64 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 13.98 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 9 | 14.04 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 15.42 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 7 | 29.0 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 4 | 17.79 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 11.5 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 9.76 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 9.31 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_UNION_TRUNCATION | None | 13.05 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 9.5 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 11.26 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 2 | 8.96 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 9.54 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 15 | 8.43 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 9.98 |
