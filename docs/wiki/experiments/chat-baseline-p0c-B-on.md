---
title: "Chat baseline — p0c-B-on"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p0c-B-on

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; compiler on; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.833 |
| gold_in_union | 0.733 |
| gold_in_pre_rerank | 0.633 |
| hit@10_selected | 0.633 |
| mrr_selected | 0.465 |
| gold_cited | 0.633 |
| wall_p50_s | 9.18 |
| wall_p90_s | 14.45 |
| deaths | {'CITED': 19, 'LOST_AT_UNION_TRUNCATION': 6, 'NEVER_RETRIEVED': 5} |
| compiler | on |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 14.45 |
| cinema | What does the book say about nonsquare pixels? | CITED | 2 | 8.0 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 12.72 |
| cinema | What does the book say about miscellaneous drawing tips? | LOST_AT_UNION_TRUNCATION | None | 14.57 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 11.56 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 19.62 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 12.32 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 8.77 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 23.33 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 10.13 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 9.03 |
| cinema | What does the book say about multiple moments? | CITED | 6 | 7.82 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 7.91 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 10.6 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 7.61 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | CITED | 7 | 12.75 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | LOST_AT_UNION_TRUNCATION | None | 12.93 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_UNION_TRUNCATION | None | 5.39 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 6 | 9.72 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 5.46 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 7.64 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 9.59 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 7 | 9.34 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | NEVER_RETRIEVED | None | 8.83 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 7.79 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 8.41 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 7.14 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 11.03 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | NEVER_RETRIEVED | None | 7.26 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 6.65 |
