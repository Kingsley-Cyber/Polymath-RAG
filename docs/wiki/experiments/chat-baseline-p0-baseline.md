---
title: "Chat baseline — p0-baseline"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p0-baseline

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer deterministic-template-v3; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.733 |
| gold_in_union | 0.6 |
| gold_in_pre_rerank | 0.433 |
| hit@10_selected | 0.433 |
| mrr_selected | 0.371 |
| gold_cited | 0.433 |
| wall_p50_s | 6.29 |
| wall_p90_s | 8.45 |
| deaths | {'CITED': 13, 'LOST_AT_UNION_TRUNCATION': 9, 'NEVER_RETRIEVED': 8} |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 6.92 |
| cinema | What does the book say about nonsquare pixels? | CITED | 2 | 7.75 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 7.87 |
| cinema | What does the book say about miscellaneous drawing tips? | NEVER_RETRIEVED | None | 8.81 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 7.02 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 15.07 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 8.45 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 6.77 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 9.35 |
| cinema | What does the book say about write radio sparely? | CITED | 1 | 6.31 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 5.6 |
| cinema | What does the book say about multiple moments? | LOST_AT_UNION_TRUNCATION | None | 7.43 |
| cinema | What does the book say about PREMISE AND THEME? | LOST_AT_UNION_TRUNCATION | None | 7.04 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 7.41 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 6.3 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | CITED | 8 | 3.78 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | NEVER_RETRIEVED | None | 3.06 |
| ecom-meta-v1 | What does the book say about the big idea? | NEVER_RETRIEVED | None | 3.61 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | LOST_AT_UNION_TRUNCATION | None | 2.76 |
| ecom-meta-v1 | What does the book say about cost innovations? | LOST_AT_UNION_TRUNCATION | None | 3.95 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 2.98 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | NEVER_RETRIEVED | None | 3.17 |
| ecom-meta-v1 | What does the book say about getting the categories right? | LOST_AT_UNION_TRUNCATION | None | 6.28 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_UNION_TRUNCATION | None | 3.66 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 5.27 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 2.9 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 2 | 3.86 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 7.34 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | NEVER_RETRIEVED | None | 2.55 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | LOST_AT_UNION_TRUNCATION | None | 3.37 |
