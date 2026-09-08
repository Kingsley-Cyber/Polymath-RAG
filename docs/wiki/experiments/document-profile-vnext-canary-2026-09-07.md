---
title: "EXPERIMENT — profile vNext fingerprint-budget canary (S5)"
change_id: PROFILE-VNEXT-CANARY-V1
date: 2026-09-07
owner: governance
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
---

# Profile vNext fingerprint-budget canary (S5)

**Question (plan §18 / S5):** which adaptive `DocumentFingerprint` budget is the
smallest that still profiles well and shows no late-structure (first-400) bias?

**Method:** `scripts/profile_vnext_canary.py` — 5-doc cinema cohort × budgets
{500, 1000, 1500, 2000}; each (doc, budget) builds the fingerprint, renders
`profile_prompt_vnext`, and calls the EXISTING isolated `doc_profile` Groq pool
(`groq/compound`) once. 20 calls, 0 errors, fleet idle on profiles (no shared-budget
collision). Raw evidence: `document-profile-vnext-canary-2026-09-07.json`.

**Metrics:** `input_tokens` (deterministic, the cost driver); `latency_s` (compound is
agentic, 3-37 s, noisy); `fields`/`items`/`research_tags` (coverage — the profile has
16 field types incl. the 7 research-index tags); `late_structure` = fraction of the
profile's SEARCH/Q/TOPIC/TERM terms landing in the document's SECOND half (≈0.5 is
balanced full-document coverage; near 0 is first-400 bias).

| budget | ok/n | mean input_tok | mean latency_s | mean items | mean fields | mean tags | mean late_structure |
|--:|--:|--:|--:|--:|--:|--:|--:|
| **500** | 5/5 | **969** | 10.0 | 24.0 | 16.0 | 7.0 | 0.824 |
| 1000 | 5/5 | 1350 | 17.0 | 26.6 | 15.0 | 6.2 | 0.768 |
| 1500 | 5/5 | 1633 | 15.6 | 28.4 | 15.8 | 6.8 | 0.783 |
| 2000 | 5/5 | 1748 | 16.2 | 23.0 | 14.4 | 5.6 | 0.933 |

**Finding — the plateau is the floor.** Field and research-tag coverage are saturated
at 500 (all 16 field types, all 7 tags); the no-first-400-bias gate is already met at
500 (late-structure 0.82) because the fingerprint's coverage surface samples the WHOLE
document at every budget — the win is the coverage DISTRIBUTION, not the token count.
Budgets 1000-2000 nearly double the input cost (969 → 1748 tokens) for no quality gain,
with a slight coverage regression at 2000 (14.4 fields / 5.6 tags — more input, more
for the model to drop). Latency is dominated by compound's agentic variance, not the
budget.

**Decision:** `DEFAULT_BUDGET_TOKENS = 500` (the min). The adaptive 500-2000 machinery
stays available, but the selected production budget is the floor. Pinned by
`tests/determinism/test_document_fingerprint.py::test_default_budget_is_canary_selected_floor`.

**Not measured here (gated to projection):** profile self-retrieval rank vs the current
gate (top-1 85.8%) — that needs the vNext profile projected to Qdrant and queried; it
is the S8/projection qualification, not the budget canary. This canary answers only the
budget question, and answers it decisively.
