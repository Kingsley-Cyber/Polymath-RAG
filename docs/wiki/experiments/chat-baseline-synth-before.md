---
title: "Chat baseline — synth-before"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — synth-before

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer default; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.9 |
| gold_in_pre_rerank | 0.8 |
| hit@10_selected | 0.633 |
| mrr_selected | 0.539 |
| gold_cited | 0.6 |
| wall_p50_s | 39.61 |
| wall_p90_s | 52.63 |
| deaths | {'CITED': 18, 'IGNORED_BY_LLM': 3, 'LOST_AT_SELECTION': 3, 'LOST_AT_UNION_TRUNCATION': 3, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_baseline_B.json |
| fixture_version | chat-baseline-B-v3 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 28 |
| tags_total | 441 |
| tags_valid | 441 |
| abstain_markers | 3 |
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
| dominance_violations | 1 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 8 |
| doc_share_top_mean | 0.649 |
| phase_retrieve_p50_s | 8.08 |
| rerank_p50_s | 2.96 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 16 |
| answer_chars_p50 | 3133 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 39.12 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 27.28 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 21.84 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 3 | 43.15 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 30.84 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 19.12 |
| cinema | What does the book say about affect, fatigue, and injury are | LOST_AT_UNION_TRUNCATION | None | 55.41 |
| cinema | What does the book say about movement of an object with a ba | IGNORED_BY_LLM | 11 | 46.78 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 50.42 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 24.43 |
| cinema | What does the book say about rewards of good type developmen | CITED | 1 | 35.12 |
| cinema | What does the book say about multiple moments? | CITED | 1 | 40.1 |
| cinema | What does the book say about PREMISE AND THEME? | IGNORED_BY_LLM | 1 | 46.06 |
| cinema | What does the book say about battling overconfidence? | CITED | 1 | 29.26 |
| cinema | What does the book say about changing a level within a clip? | CITED | 3 | 29.68 |
| ecom-meta-v1 | What does the book say about why innovative leaders make a d | LOST_AT_UNION_TRUNCATION | None | 32.3 |
| ecom-meta-v1 | What does the book say about WHAT PROGRESS IS REALLY LIKE? | CITED | 11 | 53.44 |
| ecom-meta-v1 | What does the book say about the big idea? | LOST_AT_SELECTION | None | 37.9 |
| ecom-meta-v1 | What does the book say about automation aligned with busines | CITED | 2 | 43.11 |
| ecom-meta-v1 | What does the book say about cost innovations? | CITED | 3 | 28.53 |
| ecom-meta-v1 | What does the book say about the migration of capabilities? | IGNORED_BY_LLM | 1 | 52.63 |
| ecom-meta-v1 | What does the book say about the capabilities viewpoint? | LOST_AT_UNION_TRUNCATION | None | 50.46 |
| ecom-meta-v1 | What does the book say about getting the categories right? | CITED | 1 | 34.62 |
| ecom-meta-v1 | What does the book say about discovery skill #4: networking? | LOST_AT_SELECTION | None | 40.13 |
| ecom-meta-v1 | What does the book say about creating capabilities through a | CITED | 1 | 56.08 |
| ecom-meta-v1 | What does the book say about solar versus conventional elect | CITED | 1 | 36.31 |
| ecom-meta-v1 | What does the book say about cost structures and value netwo | CITED | 1 | 38.21 |
| ecom-meta-v1 | What does the book say about HOW DISK DRIVES WORK? | CITED | 1 | 43.91 |
| ecom-meta-v1 | What does the book say about innovations that will sustain t | LOST_AT_SELECTION | None | 42.04 |
| ecom-meta-v1 | What does the book say about make it platform-centric? | CITED | 1 | 46.03 |
