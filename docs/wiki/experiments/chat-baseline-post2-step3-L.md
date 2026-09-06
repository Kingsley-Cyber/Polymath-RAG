---
title: "Chat baseline — post2-step3-L"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — post2-step3-L

Fixture `eval/fixtures/chat_lexical_L.json` (chat-lexical-L-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 1.0 |
| gold_in_union | 1.0 |
| gold_in_pre_rerank | 0.933 |
| hit@10_selected | 0.933 |
| mrr_selected | 0.843 |
| gold_cited | 0.4 |
| wall_p50_s | 7.44 |
| wall_p90_s | 14.31 |
| deaths | {'CITED': 12, 'IGNORED_BY_LLM': 16, 'LOST_AT_UNION_TRUNCATION': 2} |
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
| dominance_eligible_turns | 4 |
| doc_share_top_mean | 0.205 |
| phase_retrieve_p50_s | 5.64 |
| rerank_p50_s | 2.17 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 9 |
| answer_chars_p50 | 1053 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about "AU62"? | LOST_AT_UNION_TRUNCATION | None | 6.49 |
| cinema | What does the book say about "SO202"? | LOST_AT_UNION_TRUNCATION | None | 16.13 |
| cinema | What does the book say about "HD1"? | IGNORED_BY_LLM | 10 | 7.12 |
| cinema | What does the book say about "F850LP"? | CITED | 1 | 12.46 |
| cinema | What does the book say about "D16"? | IGNORED_BY_LLM | 1 | 14.31 |
| cinema | What does the book say about "W372"? | CITED | 1 | 9.99 |
| cinema | What does the book say about "A100"? | IGNORED_BY_LLM | 1 | 8.54 |
| cinema | What does the book say about "M4A1"? | IGNORED_BY_LLM | 1 | 9.66 |
| cinema | What does the book say about "XXXII"? | CITED | 1 | 7.93 |
| cinema | What does the book say about "MUA"? | IGNORED_BY_LLM | 1 | 7.01 |
| cinema | What does the book say about "UPA"? | IGNORED_BY_LLM | 1 | 7.57 |
| cinema | What does the book say about "ABLEGI"? | CITED | 1 | 15.4 |
| cinema | What does the book say about "NSCB"? | CITED | 5 | 14.11 |
| cinema | What does the book say about "VNSP"? | CITED | 1 | 10.42 |
| cinema | What does the book say about "UFO"? | IGNORED_BY_LLM | 1 | 5.52 |
| ecom-meta-v1 | What does the book say about "EC2"? | IGNORED_BY_LLM | 1 | 9.8 |
| ecom-meta-v1 | What does the book say about "S311"? | CITED | 1 | 7.31 |
| ecom-meta-v1 | What does the book say about "Z39"? | IGNORED_BY_LLM | 1 | 4.47 |
| ecom-meta-v1 | What does the book say about "M5H"? | IGNORED_BY_LLM | 2 | 7.8 |
| ecom-meta-v1 | What does the book say about "PCI"? | IGNORED_BY_LLM | 1 | 8.87 |
| ecom-meta-v1 | What does the book say about "FOMO"? | CITED | 1 | 5.57 |
| ecom-meta-v1 | What does the book say about "MWQ"? | IGNORED_BY_LLM | 1 | 5.49 |
| ecom-meta-v1 | What does the book say about "ASIC"? | CITED | 1 | 21.31 |
| ecom-meta-v1 | What does the book say about "ACC"? | IGNORED_BY_LLM | 2 | 3.04 |
| ecom-meta-v1 | What does the book say about "NIDA"? | CITED | 1 | 2.82 |
| ecom-meta-v1 | What does the book say about "RBV"? | IGNORED_BY_LLM | 1 | 3.45 |
| ecom-meta-v1 | What does the book say about "OECD"? | CITED | 1 | 3.19 |
| ecom-meta-v1 | What does the book say about "RBI"? | IGNORED_BY_LLM | 1 | 3.07 |
| ecom-meta-v1 | What does the book say about "NFI"? | IGNORED_BY_LLM | 1 | 3.07 |
| ecom-meta-v1 | What does the book say about "DBASSE"? | CITED | 1 | 5.09 |
