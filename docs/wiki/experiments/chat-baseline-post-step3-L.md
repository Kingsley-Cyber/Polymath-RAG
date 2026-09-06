---
title: "Chat baseline — post-step3-L"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — post-step3-L

Fixture `eval/fixtures/chat_lexical_L.json` (chat-lexical-L-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 1.0 |
| gold_in_union | 1.0 |
| gold_in_pre_rerank | 0.933 |
| hit@10_selected | 0.9 |
| mrr_selected | 0.886 |
| gold_cited | 0.433 |
| wall_p50_s | 6.15 |
| wall_p90_s | 8.84 |
| deaths | {'CITED': 13, 'IGNORED_BY_LLM': 15, 'LOST_AT_UNION_TRUNCATION': 2} |
| compiler | on |
| retrieval | v2 |
| fixture | eval/fixtures/chat_lexical_L.json |
| fixture_version | chat-lexical-L-v1 |
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
| dims_system_ok | 0 |
| dims_system_ok_rate | 0.0 |
| dims_unnamed | 0 |
| dims_in_union | 0 |
| dims_flagged | 0 |
| dims_ok | 0 |
| dims_ok_rate | 0.0 |
| dims_covered_rate | 0.0 |
| compiled_queries_mean | 0.0 |
| survival_selected_given_union | 0.933 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 3 |
| doc_share_top_mean | 0.202 |
| phase_retrieve_p50_s | 4.44 |
| rerank_p50_s | 2.34 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 4 |
| answer_chars_p50 | 1289 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about "AU62"? | LOST_AT_UNION_TRUNCATION | None | 7.05 |
| cinema | What does the book say about "SO202"? | LOST_AT_UNION_TRUNCATION | None | 7.05 |
| cinema | What does the book say about "HD1"? | IGNORED_BY_LLM | 13 | 6.02 |
| cinema | What does the book say about "F850LP"? | IGNORED_BY_LLM | 1 | 7.19 |
| cinema | What does the book say about "D16"? | IGNORED_BY_LLM | 1 | 5.73 |
| cinema | What does the book say about "W372"? | CITED | 1 | 5.45 |
| cinema | What does the book say about "A100"? | CITED | 1 | 6.69 |
| cinema | What does the book say about "M4A1"? | CITED | 1 | 8.84 |
| cinema | What does the book say about "XXXII"? | CITED | 1 | 11.61 |
| cinema | What does the book say about "MUA"? | IGNORED_BY_LLM | 1 | 5.66 |
| cinema | What does the book say about "UPA"? | IGNORED_BY_LLM | 1 | 7.63 |
| cinema | What does the book say about "ABLEGI"? | CITED | 1 | 7.25 |
| cinema | What does the book say about "NSCB"? | CITED | 1 | 6.41 |
| cinema | What does the book say about "VNSP"? | CITED | 1 | 6.19 |
| cinema | What does the book say about "UFO"? | IGNORED_BY_LLM | 1 | 6.11 |
| ecom-meta-v1 | What does the book say about "EC2"? | IGNORED_BY_LLM | 1 | 4.63 |
| ecom-meta-v1 | What does the book say about "S311"? | CITED | 1 | 6.61 |
| ecom-meta-v1 | What does the book say about "Z39"? | IGNORED_BY_LLM | 1 | 5.33 |
| ecom-meta-v1 | What does the book say about "M5H"? | IGNORED_BY_LLM | 2 | 4.51 |
| ecom-meta-v1 | What does the book say about "PCI"? | IGNORED_BY_LLM | 1 | 4.48 |
| ecom-meta-v1 | What does the book say about "FOMO"? | CITED | 1 | 5.53 |
| ecom-meta-v1 | What does the book say about "MWQ"? | IGNORED_BY_LLM | 1 | 5.6 |
| ecom-meta-v1 | What does the book say about "ASIC"? | CITED | 1 | 4.51 |
| ecom-meta-v1 | What does the book say about "ACC"? | IGNORED_BY_LLM | 1 | 3.63 |
| ecom-meta-v1 | What does the book say about "NIDA"? | CITED | 1 | 8.68 |
| ecom-meta-v1 | What does the book say about "RBV"? | IGNORED_BY_LLM | 1 | 5.88 |
| ecom-meta-v1 | What does the book say about "OECD"? | CITED | 1 | 6.7 |
| ecom-meta-v1 | What does the book say about "RBI"? | IGNORED_BY_LLM | 1 | 11.87 |
| ecom-meta-v1 | What does the book say about "NFI"? | IGNORED_BY_LLM | 1 | 3.9 |
| ecom-meta-v1 | What does the book say about "DBASSE"? | CITED | 1 | 13.58 |
