---
title: "Chat baseline — pre-step3-L"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — pre-step3-L

Fixture `eval/fixtures/chat_lexical_L.json` (chat-lexical-L-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 1.0 |
| gold_in_union | 1.0 |
| gold_in_pre_rerank | 1.0 |
| hit@10_selected | 1.0 |
| mrr_selected | 0.902 |
| gold_cited | 0.367 |
| wall_p50_s | 7.78 |
| wall_p90_s | 11.87 |
| deaths | {'CITED': 11, 'IGNORED_BY_LLM': 19} |
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
| survival_selected_given_union | 1.0 |
| dominance_violations | 0 |
| dominance_avoidable_violations | 0 |
| dominance_eligible_turns | 5 |
| doc_share_top_mean | 0.342 |
| phase_retrieve_p50_s | 6.07 |
| rerank_p50_s | 3.58 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 8 |
| answer_chars_p50 | 924 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about "AU62"? | CITED | 6 | 5.71 |
| cinema | What does the book say about "SO202"? | IGNORED_BY_LLM | 1 | 12.3 |
| cinema | What does the book say about "HD1"? | IGNORED_BY_LLM | 5 | 8.64 |
| cinema | What does the book say about "F850LP"? | IGNORED_BY_LLM | 1 | 8.87 |
| cinema | What does the book say about "D16"? | IGNORED_BY_LLM | 1 | 7.12 |
| cinema | What does the book say about "W372"? | CITED | 1 | 9.9 |
| cinema | What does the book say about "A100"? | IGNORED_BY_LLM | 1 | 11.87 |
| cinema | What does the book say about "M4A1"? | IGNORED_BY_LLM | 5 | 20.82 |
| cinema | What does the book say about "XXXII"? | CITED | 2 | 11.39 |
| cinema | What does the book say about "MUA"? | IGNORED_BY_LLM | 1 | 9.09 |
| cinema | What does the book say about "UPA"? | IGNORED_BY_LLM | 1 | 5.87 |
| cinema | What does the book say about "ABLEGI"? | IGNORED_BY_LLM | 1 | 7.94 |
| cinema | What does the book say about "NSCB"? | CITED | 1 | 7.74 |
| cinema | What does the book say about "VNSP"? | CITED | 1 | 6.21 |
| cinema | What does the book say about "UFO"? | IGNORED_BY_LLM | 1 | 9.18 |
| ecom-meta-v1 | What does the book say about "EC2"? | IGNORED_BY_LLM | 1 | 8.36 |
| ecom-meta-v1 | What does the book say about "S311"? | CITED | 1 | 7.43 |
| ecom-meta-v1 | What does the book say about "Z39"? | IGNORED_BY_LLM | 1 | 11.52 |
| ecom-meta-v1 | What does the book say about "M5H"? | IGNORED_BY_LLM | 1 | 11.73 |
| ecom-meta-v1 | What does the book say about "PCI"? | IGNORED_BY_LLM | 1 | 6.3 |
| ecom-meta-v1 | What does the book say about "FOMO"? | CITED | 1 | 16.0 |
| ecom-meta-v1 | What does the book say about "MWQ"? | IGNORED_BY_LLM | 1 | 7.37 |
| ecom-meta-v1 | What does the book say about "ASIC"? | CITED | 1 | 7.15 |
| ecom-meta-v1 | What does the book say about "ACC"? | IGNORED_BY_LLM | 1 | 6.34 |
| ecom-meta-v1 | What does the book say about "NIDA"? | CITED | 1 | 6.73 |
| ecom-meta-v1 | What does the book say about "RBV"? | IGNORED_BY_LLM | 1 | 7.42 |
| ecom-meta-v1 | What does the book say about "OECD"? | CITED | 1 | 7.22 |
| ecom-meta-v1 | What does the book say about "RBI"? | IGNORED_BY_LLM | 1 | 7.74 |
| ecom-meta-v1 | What does the book say about "NFI"? | IGNORED_BY_LLM | 1 | 7.19 |
| ecom-meta-v1 | What does the book say about "DBASSE"? | CITED | 1 | 7.81 |
