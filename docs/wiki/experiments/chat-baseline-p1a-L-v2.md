---
title: "Chat baseline — p1a-L-v2"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1a-L-v2

Fixture `eval/fixtures/chat_lexical_L.json` (chat-lexical-L-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v2; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 1.0 |
| gold_in_union | 1.0 |
| gold_in_pre_rerank | 1.0 |
| hit@10_selected | 1.0 |
| mrr_selected | 0.913 |
| gold_cited | 0.4 |
| wall_p50_s | 13.46 |
| wall_p90_s | 26.52 |
| deaths | {'CITED': 12, 'IGNORED_BY_LLM': 18} |
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
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 924 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about "AU62"? | CITED | 4 | 18.59 |
| cinema | What does the book say about "SO202"? | IGNORED_BY_LLM | 1 | 31.18 |
| cinema | What does the book say about "HD1"? | IGNORED_BY_LLM | 7 | 13.3 |
| cinema | What does the book say about "F850LP"? | IGNORED_BY_LLM | 1 | 14.56 |
| cinema | What does the book say about "D16"? | IGNORED_BY_LLM | 1 | 11.99 |
| cinema | What does the book say about "W372"? | CITED | 1 | 12.04 |
| cinema | What does the book say about "A100"? | IGNORED_BY_LLM | 1 | 11.7 |
| cinema | What does the book say about "M4A1"? | IGNORED_BY_LLM | 1 | 13.51 |
| cinema | What does the book say about "XXXII"? | CITED | 2 | 12.88 |
| cinema | What does the book say about "MUA"? | IGNORED_BY_LLM | 1 | 13.41 |
| cinema | What does the book say about "UPA"? | IGNORED_BY_LLM | 1 | 12.69 |
| cinema | What does the book say about "ABLEGI"? | CITED | 1 | 20.98 |
| cinema | What does the book say about "NSCB"? | CITED | 1 | 14.91 |
| cinema | What does the book say about "VNSP"? | CITED | 1 | 15.24 |
| cinema | What does the book say about "UFO"? | IGNORED_BY_LLM | 1 | 14.3 |
| ecom-meta-v1 | What does the book say about "EC2"? | IGNORED_BY_LLM | 1 | 34.9 |
| ecom-meta-v1 | What does the book say about "S311"? | CITED | 1 | 15.3 |
| ecom-meta-v1 | What does the book say about "Z39"? | IGNORED_BY_LLM | 1 | 10.79 |
| ecom-meta-v1 | What does the book say about "M5H"? | IGNORED_BY_LLM | 1 | 26.52 |
| ecom-meta-v1 | What does the book say about "PCI"? | IGNORED_BY_LLM | 1 | 21.59 |
| ecom-meta-v1 | What does the book say about "FOMO"? | CITED | 1 | 8.53 |
| ecom-meta-v1 | What does the book say about "MWQ"? | IGNORED_BY_LLM | 1 | 7.44 |
| ecom-meta-v1 | What does the book say about "ASIC"? | CITED | 1 | 8.73 |
| ecom-meta-v1 | What does the book say about "ACC"? | IGNORED_BY_LLM | 1 | 8.58 |
| ecom-meta-v1 | What does the book say about "NIDA"? | CITED | 1 | 7.19 |
| ecom-meta-v1 | What does the book say about "RBV"? | IGNORED_BY_LLM | 1 | 9.19 |
| ecom-meta-v1 | What does the book say about "OECD"? | CITED | 1 | 14.34 |
| ecom-meta-v1 | What does the book say about "RBI"? | IGNORED_BY_LLM | 2 | 23.79 |
| ecom-meta-v1 | What does the book say about "NFI"? | IGNORED_BY_LLM | 1 | 55.36 |
| ecom-meta-v1 | What does the book say about "DBASSE"? | CITED | 1 | 8.49 |
