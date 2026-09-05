---
title: "Chat baseline — p1a-B-v1"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1a-B-v1

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v1; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.8 |
| gold_in_union | 0.667 |
| gold_in_pre_rerank | 0.6 |
| hit@10_selected | 0.6 |
| mrr_selected | 0.433 |
| gold_cited | 0.6 |
| wall_p50_s | 11.25 |
| wall_p90_s | 19.58 |
| deaths | {'CITED': 18, 'LOST_AT_UNION_TRUNCATION': 6, 'NEVER_RETRIEVED': 6} |
| compiler | on |
| retrieval | v1 |
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
| answer_chars_p50 | 2998 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 17.88 |
| cinema | What does the book say about nonsquare pixels? | CITED | 2 | 15.98 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 15.96 |
| cinema | What does the book say about miscellaneous drawing tips? | LOST_AT_UNION_TRUNCATION | None | 15.87 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 11.94 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 22.38 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 19.58 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 12.88 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 31.53 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 11.57 |
| cinema | What does the book say about rewards of good type developmen | NEVER_RETRIEVED | None | 11.35 |
| cinema | What does the book say about multiple moments? | CITED | 5 | 11.04 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 11.75 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 11.14 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 8.18 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | CITED | 7 | 7.01 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | LOST_AT_UNION_TRUNCATION | None | 9.42 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_UNION_TRUNCATION | None | 6.85 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 6 | 31.65 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 8.23 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 12.53 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 7.72 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 7 | 6.9 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | NEVER_RETRIEVED | None | 7.78 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 7.06 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 8.06 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 5.27 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 15.3 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | NEVER_RETRIEVED | None | 8.21 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 5.91 |
