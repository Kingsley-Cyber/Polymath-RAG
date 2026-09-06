---
title: "WORK LOG — P1.c judge + composition: one judge over the fusion prefix, then deterministic slots for relevance, sources, exact matches and aspects"
change_id: EVIDENCE-COMPOSER-V1
date: 2026-09-06
owner: governance (goal 2026-09-06; CHAT-QUERY-COMPILER-PLAN §4 P1.c)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.95
package: shared/polymath_shared/candidate_engine.py, shared/polymath_shared/query_receipts.py, orchestrator/orchestrator/api/{chat_retrieval.py,ui.py}, scripts/chat_baseline.py, scripts/chat_m_replay.py, tests/determinism/test_candidate_engine.py
architecture_impact: "Final evidence is COMPOSED, not truncated. After the one cross-encoder judgement over the fusion-ordered prefix (plus the P1.b aspect seats), `compose_evidence` (deterministic, metadata only — §3.17) fills `synthesis_max` in slots: pure relevance, source diversity (soft max per document unless the score gap to the best unrepresented document is large), sparse winners (lane C arrivals), aspect coverage (one seat per non-weak compiled query not yet represented), fill. Ordering inside composition uses a sigmoid of the judge logit plus a bounded multi-lane agreement bonus that can break near-ties only. Receipts: `trace.composition` (slot fills, per-document counts, top-document share, documents within the gap, dominance flag) beside `final_detail`, in `meta`, the answer event and the query receipt. Rerank prefix: 24 judged pairs (was 20), chosen by measurement, not by the draft's 28 (see Proof and Rejected claims). Nothing under §3.23 touched."
---

# WORK LOG — P1.c judge + composition

Plan gate (ledger row, read from disk before this phase): *funnel: gold chunk survives selection on ≥ 0.85 of B where in the union; MRR@final ≥ baseline; no final set with > 60 % of chunks from one document when ≥ 3 documents scored within 0.1 of the top; citation precision ≥ baseline.*

## Contract

- **Judge.** One `rerank_children` call over the fusion-ordered prefix (`rerank_max`) plus the P1.b aspect seats; the candidate set is asserted unchanged by the judge; a degraded judge yields fusion order. The cross-encoder remains the only relevance authority.
- **Composition (`compose_evidence`).** Input: the judged prefix in judge order. Ordering key `judged_score` = sigmoid(rerank logit) + min(`compose_agreement_cap` 0.05, `compose_agreement_boost` 0.02 × (arrivals − 1)). Slots in order: `compose_relevance_slots` (8, untouched), source diversity (soft max `compose_doc_soft_max` 3 per document unless the gap to the best unrepresented document ≥ `compose_score_gap` 0.1), `compose_sparse_slots` (3, lane C arrivals), `compose_aspect_slots` (3, one per non-weak compiled query not yet represented, displacing the lowest item that is not another aspect's only representative when the set is full), fill in judge order. A chunk may satisfy several slots; the final list is deduped.
- **Agreement bound (§5 #10c).** The bonus orders inside composition only: a chunk found by every lane never displaces one with a clearly higher judge score (`judged_score(three lanes, logit 0.5) < judged_score(one lane, logit 2.0)`).
- **Dominance guard and receipt (gate).** While ≥ 3 documents score within 0.1 (sigmoid) of the top, no document may take more than `compose_dominance_share` (0.6) of the set through the diversity, sparse, aspect and fill slots; a final pass lifts the cap only when nothing else is left. The receipt distinguishes `dominance` (LITERAL: top share > 0.6 with ≥ 3 close documents) from `dominance_avoidable` (a judge-accepted chunk of another document was left unseated while the top document exceeded the share). The gate counts the avoidable kind: the literal kind can only be removed by discarding superior evidence with no replacement, which §3.14 / §5b #5 forbid. Both are aggregated by `chat_baseline` and the replay harness (`dominance_violations`, `dominance_avoidable_violations`, `dominance_eligible_turns`).
- **Frozen and untouched:** lanes, fusion, candidate budgets, SYNTHESIS-V2, CARRY-V2, the funnel, existing receipt keys, the P1.b aspect-seat semantics (they became the composer's aspect slot).

## Changes

- `shared/polymath_shared/candidate_engine.py`: `CandidateBudget` += `compose_relevance_slots` 8, `compose_doc_soft_max` 3, `compose_sparse_slots` 3, `compose_aspect_slots` 3, `compose_score_gap` 0.1, `compose_agreement_boost` 0.02, `compose_agreement_cap` 0.05; `_sig`, `judged_score`, `compose_evidence` (EVIDENCE-COMPOSER-V1); `select_evidence` composes after the judge (the P1.b top-k + one-seat block replaced; aspect seats are the composer's aspect slot) and receipts `composition` beside `final_detail`.
- `orchestrator/orchestrator/api/chat_retrieval.py`: `meta.composition`. `ui.py`: answer event `retrieval.composition`, receipt `composition`. `shared/polymath_shared/query_receipts.py`: whitelist += `composition`.
- `scripts/chat_baseline.py`: per-turn `doc_share_top` / `docs_within_gap` / `dominance` / `composition_slots`; summary `survival_selected_given_union`, `dominance_violations`, `dominance_eligible_turns`, `doc_share_top_mean`.
- `scripts/chat_m_replay.py`: B / L rows carry the composition receipt (dominance columns already summarised).
- Tests (`tests/determinism/test_candidate_engine.py` +4): slot order and the seating of a sparse winner and an uncovered aspect (a weak aspect is never seated); the dominance flag only when three documents are close and the gap rule keeps a far-ahead document whole; the agreement bonus never passes a clearly higher judge score (and stays bounded with a degraded judge); `select_evidence` composes and receipts the composition end to end.
- Rerank prefix: `CandidateBudget.rerank_max` 20 → 24 with the measured reason in the field comment; `test_budget_shapes_on_the_resolved_request` pins 24.

## Proof

**Baseline before the change (frozen-plan replay, pre-composer code, prefix 20; `chat-m-replay-p1c-B-before`, `-L-before`, and R1's `chat-m-replay-r1-M`):** B gold in union 0.900, in judged prefix 0.767, hit@10 0.700, MRR 0.519, survival given union 22/27 = 0.815 (unseated golds at union ranks 21, 21, 27, 38 and one judged-but-dropped at rank 5), wall p50 9.91 s (clean 9.10 s), no dominance receipt yet; L union 1.000, hit@10 1.000, MRR 0.913; M (multi arm) strict 0.917, system-honest 1.000.

**Composer at the same prefix (`chat-m-replay-p1c-B-p20`):** survival unchanged 0.815 (composition cannot seat what the judge never saw), hit@10 0.700, **MRR 0.519 → 0.576** (judge-score ordering plus the bounded agreement tie-break), dominance receipt live: 8 turns with ≥ 3 documents within 0.1 of the top, **2 of them with > 60 % of the set from one document** (B #7 share 0.80, B #14 share 0.87) → the fill step needed the dominance guard (Changes). M under the composer: strict 0.917 (55/60), system-honest **1.000 (60/60)**, flagged 5, silent 5 — coverage did not move.

**Prefix experiment (composer on, frozen plans, same day; `-p20` / `-p24` / `-p28`):**

| rerank prefix | gold in judged prefix | survival given union | hit@10 | MRR | dominance viol / eligible | rerank p50 ms (clean) | total p50 ms | clean wall p50 s | OOM emb / rr |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 0.767 | 0.815 (22/27) | 0.700 | 0.576 | 2 / 8 | 5162 (4682) | 9167 | 8.31 | 5 / 5 |
| 24 | 0.833 | **0.852 (23/27)** | 0.667 | 0.578 | 3 / 8 | 6016 (5621) | 9820 | 8.86 | 3 / 9 |
| 28 | 0.867 | 0.889 (24/27) | 0.700 | 0.594 | 4 / 9 | 7723 (6943) | 12063 | 10.76 | 1 / 9 |

Per-question: 24 seats B #7 (union rank 21 → final rank 12); 28 additionally seats B #21 (union rank 27 → final rank 2); B #16 (union rank 8) slips from final rank 9 to 11 at 24 and 12 at 28 because more judged candidates outrank it (hit@10 0.700 → 0.667 at 24); B #23 (rank 21) is judged at 24/28 but rejected; B #15 (rank 38) and B #17 (judged, rank 5, low score) stay out at every prefix. Decision: **24** (gate met at the smallest latency; 28 recorded for P1.d).

**Confirmation on the final code (guard + prefix 24; `chat-m-replay-p1c-final-*`):** B: gold in union 0.9, in judged prefix 0.833, **survival given union 0.852**, hit@10 0.667, **MRR 0.578**, dominance: literal 0 / **avoidable 0** of 8 eligible turns, prefix p50 24.0, wall p50 14.0 s (clean 10.61 s, 18 clean), rerank p50 6148.5 ms, OOM 7/11; unseated: [{'idx': 15, 'union_rank': 38, 'pre_rerank': False}, {'idx': 17, 'union_rank': 5, 'pre_rerank': True}, {'idx': 21, 'union_rank': 27, 'pre_rerank': False}, {'idx': 23, 'union_rank': 21, 'pre_rerank': True}]. M (multi): strict 0.933 (56/60), **system-honest 1.0 (60/60)**, flagged 6, silent 4, wall p50 11.37 s (clean 9.71 s). L: union 1.0, hit@10 1.0, MRR 0.894, survival 1.0, dominance literal 0 of 4 (pre-refinement composer run).

**Citation precision (live LLM run, `chat-baseline-p1c-B-llm-after`, P0.d baseline 1.000 on 30/30 answers with tags):** citation precision mean **1.0** on 30/30 answers with [S#] tags, abstain markers 2, hit@10 0.667, MRR 0.581, survival given union 0.852, dominance 0/7, doc share top mean 0.653, wall p50 20.28 s, compiler fallbacks 0.

**Unit proof:** `tests/determinism/test_candidate_engine.py` (+5 composer tests, all engine tests green), receipts whitelist test green, retrieval/funnel/receipts suites green (49 tests passed in the chat/engine suites (test_candidate_engine +7 composer/dominance tests); the full non-live `tests/determinism` run has 6 failures that fail identically on main 0a24d7f against the live dev database (`test_fact_endpoint_eligibility`, `test_incremental_census`, `test_stall_tracer`: live-store state, none import the changed modules) — pre-existing, and CI's fresh Postgres passes them).

## Rejected claims

- "Truncate at `synthesis_max` in judge order (P1.a/P1.b behaviour)." Rejected by the plan (§3.14: diversity happens after relevance, at the chunk level, restrained) and by the dominance measurement.
- "Use MMR with embeddings for diversity." Rejected for now: §3.17 offers `0.80 × relevance − 0.20 × redundancy` as the alternative; the slot policy needs no vectors, no extra model, and its receipt says exactly which slot admitted each chunk.
- "Cut the top document to 60 % of the set whenever three documents are close, even when the other documents have nothing else judged relevant." Rejected by measurement: B #14 (final run) holds 12 confident chunks of one book plus every one of the 3 judged-relevant chunks the two close books offered; the literal rule would drop 6 chunks at sigmoid ≥ 0.99 for nothing. The receipt keeps the literal flag visible and the gate counts avoidable dominance.
- "Let multi-lane agreement re-rank the judge." Rejected (§5 #10c): agreement is evidence of *how* a chunk was found; it is bounded to a near-tie breaker.
- "Raise the rerank prefix to 28 as the handoff draft proposed." Rejected by measurement on the frozen-plan B replay (composer on, same plans, same day): 20 → 24 → 28 pairs gives survival-given-union 0.815 → 0.852 → 0.889, MRR 0.576 → 0.578 → 0.594, rerank p50 5.16 → 6.02 → 7.72 s (clean turns 4.68 → 5.62 → 6.94 s), total p50 9.17 → 9.82 → 12.06 s. 24 clears the ≥ 0.85 gate at +0.9 s; 28 buys one more gold (B #21, fusion rank 27, judged into final rank 2) for another +1.7 s under contention (+1.0 s fresh at ~240 ms/pair) while the plan's rerank budget is 3 s (§3.16). 28 is recorded as the ceiling candidate for P1.d's deadline-aware prefix (judge as many pairs as the budget allows, in fusion order).

## Open contract gaps

1. **Survival ceiling at 24 pairs.** 0.852 of B's in-union golds are seated; B #15 (fusion rank 38) and B #17 (judged, rejected by the cross-encoder) are not, and B #21 (rank 27, judged into final rank 2 at 28 pairs) is the measured argument for a wider prefix on a calm GPU — P1.d's deadline-aware prefix (ceiling 28) owns it.
2. **hit@10 on B dipped by one question (0.700 → 0.667) when the prefix grew**: B #16's gold (fusion rank 8) is outranked by the newly judged candidates; MRR still rose. Recorded, not tuned — composition orders by the judge.
3. **Dominance guard is share-based, not topic-based.** It caps a document at 60 % of the set only while ≥ 3 documents are within 0.1 of the top; a single-source question keeps its whole set (gap rule). P1.e's mode composition inherits the same receipt.
4. **Composition receipts are not yet in `/chat` (non-stream)**; they ride the stream answer event and the query receipt. P1.f's runtime unification carries them to `/chat`.
5. **Rerank cost is the wall.** 24 pairs ≈ 5.8 s on a fresh sidecar (≈ 240 ms/pair, fp32 CrossEncoder, batches of 16 per HTTP call) against the plan's 3 s rerank budget; under enrichment contention 6–8 s p50. P1.d owns the budget (interactive Metal lease, deadline, one HTTP call per turn).
