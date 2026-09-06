---
title: "Chat baseline — synth-after"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — synth-after

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer default; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.8 |
| hit@10_selected | 0.633 |
| mrr_selected | 0.564 |
| gold_cited | 0.733 |
| wall_p50_s | 37.05 |
| wall_p90_s | 52.22 |
| deaths | {'CITED': 22, 'LOST_AT_SELECTION': 2, 'LOST_AT_UNION_TRUNCATION': 3, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_baseline_B.json |
| fixture_version | chat-baseline-B-v3 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 29 |
| tags_total | 412 |
| tags_valid | 412 |
| abstain_markers | 2 |
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
| survival_selected_given_union | 0.815 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 7 |
| doc_share_top_mean | 0.651 |
| phase_retrieve_p50_s | 3.19 |
| rerank_p50_s | 1.32 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 4 |
| answer_chars_p50 | 2770 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 39.45 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 27.13 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 36.62 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 3 | 21.87 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 26.76 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 48.23 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 51.76 |
| cinema | What does the book say about movement of an object with a ba | CITED | 11 | 52.22 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 40.95 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 24.18 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 53.08 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 22.13 |
| cinema | What does the book say about PREMISE AND THEME? | CITED | 1 | 27.6 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 37.48 |
| cinema | What does the book say about changing a level within a clip? | CITED | 1 | 15.46 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 26.24 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 11 | 59.65 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 32.57 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 2 | 38.97 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 45.58 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | CITED | 1 | 44.18 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 49.54 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 61.09 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 33.77 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 27.8 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 34.28 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 38.17 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 27.65 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | CITED | 14 | 28.68 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 44.94 |
