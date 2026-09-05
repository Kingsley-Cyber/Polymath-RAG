---
title: "Chat baseline — p0d-llm-after"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p0d-llm-after

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer default; compiler on; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.833 |
| gold_in_union | 0.7 |
| gold_in_pre_rerank | 0.633 |
| hit@10_selected | 0.633 |
| mrr_selected | 0.493 |
| gold_cited | 0.633 |
| wall_p50_s | 14.7 |
| wall_p90_s | 33.27 |
| deaths | {'CITED': 19, 'LOST_AT_UNION_TRUNCATION': 6, 'NEVER_RETRIEVED': 5} |
| compiler | on |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 30 |
| tags_total | 445 |
| tags_valid | 445 |
| abstain_markers | 3 |
| answer_chars_p50 | 3003 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 11.23 |
| cinema | What does the book say about nonsquare pixels? | CITED | 2 | 12.74 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 10.39 |
| cinema | What does the book say about miscellaneous drawing tips? | LOST_AT_UNION_TRUNCATION | None | 15.6 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 22.41 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 33.27 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 13.83 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 33.76 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 42.16 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 38.11 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 17.82 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 15.0 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 21.28 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 15.98 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 33.26 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | CITED | 7 | 20.67 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | LOST_AT_UNION_TRUNCATION | None | 23.93 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_UNION_TRUNCATION | None | 8.57 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 6 | 22.82 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 20.17 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 11.75 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 8.87 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 7 | 9.9 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | NEVER_RETRIEVED | None | 11.88 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 14.39 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 10.14 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 10.03 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 11.5 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | NEVER_RETRIEVED | None | 13.92 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 9.17 |
