---
title: "Chat baseline — p1a-B-v2"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1a-B-v2

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.767 |
| hit@10_selected | 0.7 |
| mrr_selected | 0.477 |
| gold_cited | 0.7 |
| wall_p50_s | 9.87 |
| wall_p90_s | 26.13 |
| deaths | {'CITED': 21, 'IGNORED_BY_LLM': 1, 'LOST_AT_SELECTION': 1, 'LOST_AT_UNION_TRUNCATION': 4, 'NEVER_RETRIEVED': 3} |
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
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 3895 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 4 | 10.51 |
| cinema | What does the book say about nonsquare pixels? | CITED | 3 | 11.13 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 35.23 |
| cinema | What does the book say about miscellaneous drawing tips? | IGNORED_BY_LLM | 3 | 14.06 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 29.1 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 26.13 |
| cinema | What does the book say about affect, fatigue, and injury are | CITED | 3 | 16.19 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 15.91 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 26.21 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 9.2 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 11.7 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 23.38 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 2 | 11.09 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 8.21 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 8.43 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 10.55 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 9 | 6.9 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 6.71 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 8 | 23.53 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 4 | 10.58 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 7.75 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 7.11 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 8.8 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_UNION_TRUNCATION | None | 8.69 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 8.7 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 7.69 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 2 | 6.98 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 9.23 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 15 | 6.47 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 6.23 |
