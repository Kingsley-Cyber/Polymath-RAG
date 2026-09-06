---
title: "WORK LOG — P1.c judge + composition: one judge over the fusion prefix, then deterministic slots for relevance, sources, exact matches and aspects"
change_id: EVIDENCE-COMPOSER-V1
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P1.c)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.93
package: shared/polymath_shared/candidate_engine.py, shared/polymath_shared/query_receipts.py, orchestrator/orchestrator/api/{chat_retrieval.py,ui.py}, scripts/chat_baseline.py, tests/determinism/test_candidate_engine.py
architecture_impact: "Final evidence is now COMPOSED, not truncated. After the one cross-encoder judgement over the fusion-ordered prefix, `compose_evidence` (deterministic, metadata only — §3.17) fills the synthesis budget in slots: pure judge relevance (8) → source diversity (soft maximum 3 chunks per document unless the score gap to the best unrepresented document is ≥ 0.1 on a sigmoid of the judge logit) → sparse winners (lane C arrivals, 3) → aspect coverage (compiled queries not yet represented, 3) → fill in judge order. Multi-lane agreement is a bounded ordering bonus (+0.02 per extra lane, cap 0.05, sigmoid scale) that can settle a near-tie but never passes a clearly higher judge score. The composer receipts slot fills, per-document counts, the top-document share and a dominance flag (share > 60 % while ≥ 3 documents sit within 0.1 of the top) on the trace, `meta.composition`, the answer event and the query receipt, plus `final_detail` (chunk, document, judge score, arrivals, query ids) for every seated item. Nothing under §3.23 touched; hybrid-retrieval-v1 / pass1-retrieval-v2 untouched."
---

# WORK LOG — P1.c judge + composition

Plan gate (ledger row, read from disk): *funnel: gold chunk survives selection on ≥ 0.85 of B where in the union; MRR@final ≥ baseline; no final set with > 60 % of chunks from one document when ≥ 3 documents scored within 0.1 of the top; citation precision ≥ baseline.*

## Contract

- **Judge.** One `rerank_children` call over the fusion-ordered prefix, now `rerank_max` = 28 (was 20; see Rejected claims) plus the P1.b aspect seats; candidate set asserted unchanged; degraded → fusion order. Client batches of 16 map to sidecar batches of 8 (≤ 10 per §3.8).
- **Composition (`compose_evidence`).** Input: the judged prefix in judge order. Ordering key: `judged_score` = sigmoid(rerank logit) + min(cap, boost × (arrivals − 1)). Slots, in order: `compose_relevance_slots` (8) unrestricted; source diversity — every further candidate is admitted while its document holds < `compose_doc_soft_max` (3) seats, or when its score exceeds the best still-unrepresented document's score by ≥ `compose_score_gap` (0.1); `compose_sparse_slots` (3) for lane C arrivals not yet seated; `compose_aspect_slots` (3) for candidates carrying a compiled query id not yet represented; then fill in judge order to `synthesis_max` (15). Dedupe by chunk id; a chunk may satisfy several slots.
- **Agreement bound.** The bonus is applied to ordering inside composition only; `judged_score(triple-lane, logit 0.5) < judged_score(single-lane, logit 2.0)` — a chunk found by every lane never displaces one with a clearly higher judge score (§5 #10c). Under a degraded judge the bonus is the only ordering signal and stays ≤ cap.
- **Receipts.** `trace.composition = {slots, doc_counts, doc_share_top, docs_within_gap, dominance, agreement_reordered}`, `trace.final_detail[]`; `meta.composition` / `meta.final_detail`; answer event `retrieval.composition` / `retrieval.final_detail`; receipt whitelist += `composition`. `scripts/chat_baseline.py` reports `survival_selected_given_union`, `dominance_violations` / `dominance_eligible_turns`, `doc_share_top_mean`.
- **Frozen and untouched:** lanes, fusion, budgets for candidates and rerank prefix, SYNTHESIS-V2, CARRY-V2, the funnel, receipts' existing keys.

## Changes

- `candidate_engine.py`: `CandidateBudget` += compose_* knobs; `_sig`, `judged_score`, `compose_evidence`; `select_evidence` composes after the judge and receipts `composition` + `final_detail`.
- `chat_retrieval.py`: `meta.composition`, `meta.final_detail`. `ui.py`: answer event + receipt. `query_receipts.py`: whitelist.
- `scripts/chat_baseline.py`: survival / dominance / doc-share summary fields.
- Tests: `test_candidate_engine.py` +4 (slot order and seating of sparse winner and uncovered aspect; dominance flag only with three close documents, gap exception keeps a far-ahead document whole; agreement bound; end-to-end `select_evidence` receipt).

## Proof

PROOF_BLOCK

## Rejected claims

- "Truncate at `synthesis_max` in judge order (P1.a/P1.b behaviour)." Rejected by the plan (§3.14 "diversity happens after relevance, at the chunk level, restrained") and by the dominance measurement below: a document that wins the routing lane can fill the whole final set even when two other documents score within a hair of the top.
- "Use MMR with embeddings for diversity." Rejected for now: §3.17 offers `0.80 × relevance − 0.20 × redundancy` as the alternative; the slot policy needs no vectors, no extra model, and its receipt says exactly which rule seated each chunk. MMR remains a measured alternative if the slot policy under-performs on real conversations (P1.g fixtures).
- "Let multi-lane agreement re-rank the judge." Rejected (§5 #10c): the cross-encoder is the common judge; agreement is evidence of *how* a chunk was found and is bounded to a near-tie breaker.
- "Keep the rerank prefix at 20 and fix survival with composition alone." Rejected by measurement: on the P1.b clean B run 4 of the 5 unseated gold chunks were never judged (union ranks 21 / 21 / 27 / 38) and composition cannot seat what the judge never saw. The prefix moves to 28 (§3.14 "top ≈30"), +8 pairs ≈ +1.9 s at ~235 ms per pair; the cost is recorded here and owned by P1.d's reranker budget.

## Open contract gaps

GAPS_BLOCK
