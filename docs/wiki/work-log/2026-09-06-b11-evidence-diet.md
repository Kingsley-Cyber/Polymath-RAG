---
title: "WORK LOG — B11 EVIDENCE-DIET-V1: passages only in the prompt, breadcrumbs for context, document-fair judging"
change_id: EVIDENCE-DIET-V1
date: 2026-09-06
owner: governance (owner backlog B11, released 2026-09-06; owner: "document summary is a waste of final chunks … keep section or parent summary … increase breadth at the document level in a fair manner")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.113
package: orchestrator/orchestrator/api/ui.py (_evidence_legend, _breadcrumb, prompt legend lines), shared/polymath_shared/candidate_engine.py (judged_prefix, CandidateBudget.rerank_round_robin / rerank_doc_cap, trace receipts), tests/determinism/test_chat_synthesis.py, tests/determinism/test_candidate_engine.py, docs/wiki/experiments/chat-presentation-b11-steps12.json, chat-baseline-b11-steps12.{json,md}, chat-baseline-pre-step3-{B,L}.{json,md}, chat-baseline-post-step3-{B,L}.{json,md}, chat-baseline-post2-step3-{B,L}.{json,md}
architecture_impact: "Three changes on the shared evidence path. (1) Document- and section-summary rows no longer reach the prompt, the [S#] legend, the Sources count or the funnel's `selected` — the legend builder skips the assembler's summary kinds; the bundle itself is unchanged (the deterministic synthesizer and /retrieve keep their summaries). (2) Each passage's legend line carries a breadcrumb — the assembler's `presentation.human_locator` ('book › section' from heading_path; every cinema child has one), with source › title and the bare source name as fallbacks — on the evidence block header and in the tag legend; the raw locator stays on the answer event and the receipt. (3) The judged prefix (`rerank_max`, 24) is filled document-fairly by `judged_prefix`: round 1 seats every surfaced document's best fused candidate (first-appearance order), then the fusion order continues under a per-document cap (`rerank_doc_cap`, 8), then leftover seats fill in fusion order; relevance (the judge) still decides survival; the trace receipts `prefix_policy`, `judged_docs`, `capped_out`, `prefix_docs`. `rerank_round_robin=False` restores the old top-k slice."
---

# WORK LOG — B11 EVIDENCE-DIET-V1

## Contract

The prompt carries passages, each labelled with where it comes from; nothing is offered to the model that the model has never used; and a passage's chance to be judged depends on its rank inside its own document and on relevance, not on how many candidates its document put into the union.

## Changes

- Steps 1–2 (`ui.py`): `_SUMMARY_TEXT_KINDS`, `_breadcrumb(item)`, `_evidence_legend` skips summary rows and adds `breadcrumb`; `_grounded_messages` writes `[S#] book › section` on the passage header and `[S#] = book › section` in the legend.
- Step 3 (`candidate_engine.py`): `judged_prefix(union, budget)` (pure), two budget knobs, four trace receipts; `select_evidence` uses it in place of `union[:rerank_max]`; aspect seat reservation unchanged.
- Tests: `test_evidence_diet_prompt_carries_passages_only_with_breadcrumbs` (summaries skipped, tags contiguous, breadcrumb fallbacks, prompt lines, raw locator kept); `test_judged_prefix_seats_every_document_once_then_fusion_order_under_a_cap_then_fills` (round 1 / cap / fill / off = old slice / invariants).

## Proof

Steps 1–2 — same 10 fixture-B questions, deepseek-v4-flash (before = the bold-retired probe turns of 18:35–18:50):

| metric | before | after | target |
|---|---|---|---|
| prompt chars p50 | 41,613 | 28,899 (−31 %) | down |
| legend rows p50 (chunk / section / doc totals over 10 turns) | 31 (150 / 100 / 52) | 15 (150 / 0 / 0) | passages only |
| breadcrumbs on passage rows | 0 | 15 / 15 rows on a live LLM turn after the respawn | all |
| answers tagged | 10 / 10 | 10 / 10 on the probe; on the LLM citation check 9 / 10 tagged + 1 correct abstention ("The retrieved evidence contains no mention of FACE OFF", no corpus claims, no tags — correct) | 10 / 10 |
| citation precision (10-question LLM check) | 1.0 (synth-after2) | 1.0 (120 / 120 tags valid) | ≥ 0.95 |
| answer chars p50 | 2,674 | 2,293 (probe) / 2,212 (citation check) | held |
| wall s p50 | 37.4 | 30.3 (probe) / 28.4 (check) | — |

Step 3 — frozen fixture B (30 questions, retrieval-only, the recorded acceptance instrument) and L:

| fixture / metric | before (fusion top-24) | fair, 24 seats (first attempt) | fair, 32 seats (shipped) | manifest floor |
|---|---|---|---|---|
| B gold-in-union | 0.900 | 0.900 | 0.900 | ≥ 0.85 |
| B hit@10 (selected) | 0.667 | 0.600 | 0.633 | ≥ 0.60 |
| B MRR (selected) | 0.581 | 0.505 | 0.566 | ≥ 0.45 |
| B survival given union | 0.852 | 0.778 | 0.778 | (P1.c value 0.852; no manifest floor) |
| B degraded turns / rerank p50 | 1 / 1.02 s | 10 / 2.12 s | 6 / 1.77 s | — |
| L gold-in-union | 1.000 | 1.000 | 1.000 | ≥ 0.95 |
| L hit@10 (selected) | 1.000 | 0.900 | 0.933 | ≥ 0.90 |
| L MRR (selected) | 0.902 | 0.886 | 0.843 | ≥ 0.80 |
| L survival given union | 1.000 | 0.933 | 0.933 | — |
| documents judged per turn (p50 / mean, B + L receipts) | 5 / 5.2 | 9 / 13.0 | 9 / 15.0 | up |
| documents in the final set (p50) | 4 | 6.5 | 6 | — |

Reading: every manifest floor holds at 32 seats and the breadth goal is met (documents judged per turn 5 → 9 at the median, documents in the final set 4 → 6). The cost is recall inside the judged set: survival given union 0.852 → 0.778 on B and 1.000 → 0.933 on L, hit@10 0.667 → 0.633 (one question) and 1.000 → 0.933 (two). The first attempt at 24 seats was worse (B hit@10 0.600, MRR 0.505); 32 seats recovered most of it, not all. Contention differed between runs (B degraded turns 1 → 6), which moves survival too, but L lost recall with fewer degraded turns than its pre-run on the first attempt, so the policy itself costs some tail recall: a gold chunk sitting 5th–8th in the dominant document now competes for its seat with other documents' best candidates. Shipped: fair policy ON at 32 seats (`rerank_round_robin`, `rerank_max_fair`, `rerank_doc_cap` = 8; `POLYMATH_CHAT_RERANK_ROUND_ROBIN=0` restores the fusion slice), status IMPLEMENTED with the survival miss recorded.

## Rejected claims

- "Drop the summary rows in the assembler" — rejected: the assembler also feeds the deterministic synthesizer and /retrieve; the prompt is where the rows were useless, so the legend builder is where they are removed.
- "Pure round-robin for all 24 seats" — rejected: it would give a ten-candidate book two judged passages; round 1 seats each document once and the fusion order, capped, decides the rest.
- "Ship the fair policy off by default because survival dropped" — rejected for now: the owner's stated goal was breadth, every recorded floor holds, and the knob is one environment line; the miss is written, not hidden.
- "Raise the seats to 40" — not attempted: one corrective attempt (24 → 32) is the rule; 40 costs another ~25 % of judge time and is the next experiment if the owner wants the tail recall back.

## Open contract gaps

- Breadcrumbs depend on heading_path (all cinema children have it); a legacy corpus without it falls back to "source › title" or the bare source name.
- The per-document cap and the round-robin first pass are knobs, not laws; the recorded floors are the guard when they change.
- Survival given union is below its P1.c value on both fixtures (B 0.852 → 0.778, L 1.000 → 0.933). Candidates for the next attempt: 40 seats; round 1 limited to documents whose best candidate sits inside the fusion top-32 (protects the head of the order); a corpus-size-aware cap. Each is a frozen-fixture measurement, not a guess.
- The step-1 P_CRUMBS placeholder above was verified on a live LLM turn after the respawn: 15 of 15 legend rows carried a breadcrumb (e.g. "David Landau - Lighting for Cinematography › Pages 366–368").
