---
title: "Chat baseline — final-L-live"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# Chat baseline — final-L-live

Fixture `eval/fixtures/chat_lexical_L.json` (chat-lexical-L-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 1.0 |
| gold_in_union | 1.0 |
| gold_in_pre_rerank | 1.0 |
| hit@10_selected | 1.0 |
| mrr_selected | 0.8 |
| gold_cited | 0.367 |
| wall_p50_s | 9.25 |
| wall_p90_s | 15.23 |
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
| dominance_eligible_turns | 10 |
| doc_share_top_mean | 0.316 |
| phase_retrieve_p50_s | 7.76 |
| rerank_p50_s | 5.2 |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 12 |
| answer_chars_p50 | 925 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about "AU62"? | CITED | 6 | 8.88 |
| cinema | What does the book say about "SO202"? | IGNORED_BY_LLM | 6 | 11.58 |
| cinema | What does the book say about "HD1"? | IGNORED_BY_LLM | 7 | 14.92 |
| cinema | What does the book say about "F850LP"? | IGNORED_BY_LLM | 8 | 16.75 |
| cinema | What does the book say about "D16"? | IGNORED_BY_LLM | 1 | 11.01 |
| cinema | What does the book say about "W372"? | CITED | 1 | 7.54 |
| cinema | What does the book say about "A100"? | IGNORED_BY_LLM | 7 | 17.47 |
| cinema | What does the book say about "M4A1"? | IGNORED_BY_LLM | 4 | 15.23 |
| cinema | What does the book say about "XXXII"? | CITED | 2 | 9.08 |
| cinema | What does the book say about "MUA"? | IGNORED_BY_LLM | 1 | 7.65 |
| cinema | What does the book say about "UPA"? | IGNORED_BY_LLM | 1 | 10.47 |
| cinema | What does the book say about "ABLEGI"? | IGNORED_BY_LLM | 1 | 15.27 |
| cinema | What does the book say about "NSCB"? | CITED | 1 | 6.67 |
| cinema | What does the book say about "VNSP"? | CITED | 1 | 9.1 |
| cinema | What does the book say about "UFO"? | IGNORED_BY_LLM | 1 | 6.59 |
| ecom-meta-v1 | What does the book say about "EC2"? | IGNORED_BY_LLM | 1 | 11.6 |
| ecom-meta-v1 | What does the book say about "S311"? | CITED | 1 | 10.32 |
| ecom-meta-v1 | What does the book say about "Z39"? | IGNORED_BY_LLM | 1 | 14.51 |
| ecom-meta-v1 | What does the book say about "M5H"? | IGNORED_BY_LLM | 1 | 7.79 |
| ecom-meta-v1 | What does the book say about "PCI"? | IGNORED_BY_LLM | 1 | 10.76 |
| ecom-meta-v1 | What does the book say about "FOMO"? | CITED | 1 | 12.59 |
| ecom-meta-v1 | What does the book say about "MWQ"? | IGNORED_BY_LLM | 1 | 6.7 |
| ecom-meta-v1 | What does the book say about "ASIC"? | CITED | 1 | 6.19 |
| ecom-meta-v1 | What does the book say about "ACC"? | IGNORED_BY_LLM | 1 | 7.39 |
| ecom-meta-v1 | What does the book say about "NIDA"? | CITED | 1 | 6.4 |
| ecom-meta-v1 | What does the book say about "RBV"? | IGNORED_BY_LLM | 1 | 7.94 |
| ecom-meta-v1 | What does the book say about "OECD"? | CITED | 1 | 10.11 |
| ecom-meta-v1 | What does the book say about "RBI"? | IGNORED_BY_LLM | 2 | 9.4 |
| ecom-meta-v1 | What does the book say about "NFI"? | IGNORED_BY_LLM | 1 | 8.5 |
| ecom-meta-v1 | What does the book say about "DBASSE"? | CITED | 1 | 7.73 |
