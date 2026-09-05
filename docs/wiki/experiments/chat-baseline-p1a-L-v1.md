---
title: "Chat baseline — p1a-L-v1"
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: measured
---

# Chat baseline — p1a-L-v1

Fixture `eval/fixtures/chat_lexical_L.json` (chat-lexical-L-v1, seed 20260905); synthesizer deterministic-template-v3; compiler on; retrieval v1; follow-ups False; HYBRID via /chat/stream.

| metric | value |
|---|---|
| n | 30 |
| errors | 0 |
| gold_in_retrieved | 0.9 |
| gold_in_union | 0.833 |
| gold_in_pre_rerank | 0.2 |
| hit@10_selected | 0.2 |
| mrr_selected | 0.2 |
| gold_cited | 0.1 |
| wall_p50_s | 6.25 |
| wall_p90_s | 11.8 |
| deaths | {'CITED': 3, 'IGNORED_BY_LLM': 3, 'LOST_AT_UNION_TRUNCATION': 21, 'NEVER_RETRIEVED': 3} |
| compiler | on |
| retrieval | v1 |
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
| engines | {'hybrid-retrieval-v1': 30} |
| arrivals_missing_total | 0 |
| turns_with_arrivals | 30 |
| degraded_turns | 0 |
| answer_chars_p50 | 62 |

| corpus | question | death | selected rank | wall s |
|---|---|---|---|---|
| cinema | What does the book say about "AU62"? | LOST_AT_UNION_TRUNCATION | None | 7.24 |
| cinema | What does the book say about "SO202"? | LOST_AT_UNION_TRUNCATION | None | 8.64 |
| cinema | What does the book say about "HD1"? | LOST_AT_UNION_TRUNCATION | None | 8.4 |
| cinema | What does the book say about "F850LP"? | LOST_AT_UNION_TRUNCATION | None | 8.7 |
| cinema | What does the book say about "D16"? | LOST_AT_UNION_TRUNCATION | None | 12.92 |
| cinema | What does the book say about "W372"? | LOST_AT_UNION_TRUNCATION | None | 11.8 |
| cinema | What does the book say about "A100"? | LOST_AT_UNION_TRUNCATION | None | 13.5 |
| cinema | What does the book say about "M4A1"? | LOST_AT_UNION_TRUNCATION | None | 13.13 |
| cinema | What does the book say about "XXXII"? | LOST_AT_UNION_TRUNCATION | None | 10.19 |
| cinema | What does the book say about "MUA"? | LOST_AT_UNION_TRUNCATION | None | 8.29 |
| cinema | What does the book say about "UPA"? | NEVER_RETRIEVED | None | 6.55 |
| cinema | What does the book say about "ABLEGI"? | LOST_AT_UNION_TRUNCATION | None | 9.55 |
| cinema | What does the book say about "NSCB"? | LOST_AT_UNION_TRUNCATION | None | 5.96 |
| cinema | What does the book say about "VNSP"? | LOST_AT_UNION_TRUNCATION | None | 7.83 |
| cinema | What does the book say about "UFO"? | IGNORED_BY_LLM | 1 | 9.2 |
| ecom-meta-v1 | What does the book say about "EC2"? | IGNORED_BY_LLM | 1 | 6.64 |
| ecom-meta-v1 | What does the book say about "S311"? | LOST_AT_UNION_TRUNCATION | None | 4.62 |
| ecom-meta-v1 | What does the book say about "Z39"? | IGNORED_BY_LLM | 1 | 4.9 |
| ecom-meta-v1 | What does the book say about "M5H"? | LOST_AT_UNION_TRUNCATION | None | 4.3 |
| ecom-meta-v1 | What does the book say about "PCI"? | LOST_AT_UNION_TRUNCATION | None | 3.99 |
| ecom-meta-v1 | What does the book say about "FOMO"? | LOST_AT_UNION_TRUNCATION | None | 5.13 |
| ecom-meta-v1 | What does the book say about "MWQ"? | LOST_AT_UNION_TRUNCATION | None | 4.81 |
| ecom-meta-v1 | What does the book say about "ASIC"? | CITED | 1 | 4.4 |
| ecom-meta-v1 | What does the book say about "ACC"? | NEVER_RETRIEVED | None | 4.5 |
| ecom-meta-v1 | What does the book say about "NIDA"? | CITED | 1 | 5.47 |
| ecom-meta-v1 | What does the book say about "RBV"? | LOST_AT_UNION_TRUNCATION | None | 4.56 |
| ecom-meta-v1 | What does the book say about "OECD"? | CITED | 1 | 5.82 |
| ecom-meta-v1 | What does the book say about "RBI"? | NEVER_RETRIEVED | None | 5.12 |
| ecom-meta-v1 | What does the book say about "NFI"? | LOST_AT_UNION_TRUNCATION | None | 4.59 |
| ecom-meta-v1 | What does the book say about "DBASSE"? | LOST_AT_UNION_TRUNCATION | None | 4.24 |
