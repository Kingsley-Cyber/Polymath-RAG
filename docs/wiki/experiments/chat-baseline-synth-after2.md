---
title: "Chat baseline — synth-after2"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — synth-after2

Fixture `eval/fixtures/chat_baseline_B.json` (chat-baseline-B-v3, seed 20260905); synthesizer default; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 10 |
| errors | 0 |
| gold_in_retrieved | 0.7 |
| gold_in_union | 0.7 |
| gold_in_pre_rerank | 0.7 |
| hit@10_selected | 0.6 |
| mrr_selected | 0.412 |
| gold_cited | 0.7 |
| wall_p50_s | 42.02 |
| wall_p90_s | 77.72 |
| deaths | {'CITED': 7, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_baseline_B.json |
| fixture_version | chat-baseline-B-v3 |
| followups | False |
| recovery | None |
| compiler_fallbacks | 0 |
| citation_precision_mean | 1.0 |
| answers_with_tags | 10 |
| tags_total | 158 |
| tags_valid | 158 |
| abstain_markers | 1 |
| engines | {'chat-retrieval-v2': 10} |
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
| survival_selected_given_union | 1.0 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 4 |
| doc_share_top_mean | 0.487 |
| phase_retrieve_p50_s | 11.01 |
| rerank_p50_s | 1.58 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 10 |
| degraded_turns | 8 |
| answer_chars_p50 | 2488 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about making your own chroma keyer? | CITED | 1 | 38.23 |
| cinema | What does the book say about nonsquare pixels? | CITED | 1 | 44.22 |
| cinema | What does the book say about oebps/ritc 9781119685401 epub3  | NEVER_RETRIEVED | None | 40.34 |
| cinema | What does the book say about miscellaneous drawing tips? | CITED | 5 | 42.79 |
| cinema | What does the book say about transcoding versus color rerend | CITED | 1 | 25.42 |
| cinema | What does the book say about FACE OFF? | NEVER_RETRIEVED | None | 26.13 |
| cinema | What does the book say about affect, fatigue, and injury are | CITED | 3 | 107.44 |
| cinema | What does the book say about movement of an object with a ba | CITED | 11 | 77.72 |
| cinema | What does the book say about sound editing? | NEVER_RETRIEVED | None | 53.68 |
| cinema | What does the book say about write radio sparely? | CITED | 2 | 41.24 |
