---
title: "Chat baseline — p0d-llm-before"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p0d-llm-before

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
| wall_p50_s | 11.33 |
| wall_p90_s | 13.69 |
| deaths | {'CITED': 19, 'LOST_AT_UNION_TRUNCATION': 6, 'NEVER_RETRIEVED': 5} |
| compiler | on |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 30 |
| tags_total | 369 |
| tags_valid | 369 |
| abstain_markers | 5 |
| answer_chars_p50 | 2396 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 10.39 |
| cinema | What does the book say about nonsquare pixels? | CITED | 2 | 14.2 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 13.46 |
| cinema | What does the book say about miscellaneous drawing tips? | LOST_AT_UNION_TRUNCATION | None | 12.83 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 11.1 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 19.43 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 13.69 |
| cinema | What does the book say about movement of an object with a ba | LOST_AT_UNION_TRUNCATION | None | 14.53 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 12.65 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 12.56 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 12.49 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 9.62 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 13.25 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 10.42 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 11.44 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | CITED | 7 | 10.37 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | LOST_AT_UNION_TRUNCATION | None | 8.39 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_UNION_TRUNCATION | None | 9.02 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 6 | 9.33 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 8.56 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 11.97 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 11.62 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 7 | 10.81 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | NEVER_RETRIEVED | None | 11.88 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 11.69 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 8.2 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 11.22 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 10.67 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | NEVER_RETRIEVED | None | 9.64 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 8.54 |
