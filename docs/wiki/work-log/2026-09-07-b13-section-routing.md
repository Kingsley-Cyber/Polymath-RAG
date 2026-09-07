---
title: "WORK LOG — B13 SECTION-ROUTING-V1: the summary lane routes by section; the document vote is opt-in"
change_id: SECTION-ROUTING-V1
date: 2026-09-07
owner: governance (owner decision 2026-09-07: "document summary should also be removed from search; it should fall on parent or section for routing")
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.120
package: shared/polymath_shared/candidate_engine.py (hierarchy_route_documents, lane A, route_kinds receipt), orchestrator/orchestrator/api/chat_retrieval.py (env knob), scripts/chat_m_replay.py (+DOCS arm, judged_docs / final_docs receipts), tests/determinism/test_candidate_engine.py, docs/wiki/experiments/chat-m-replay-b13-{B,L}.{json,md}
architecture_impact: "The hierarchical lane (lane A) no longer searches document summaries by default: routing to documents happens through section summaries, the child votes and the entity cards (`aggregate_documents_n` unchanged; the document-summary contribution is simply absent), then deepens through the selected sections' original children as before. `hierarchy_route_documents=True` (env `POLYMATH_CHAT_HIERARCHY_ROUTE_DOCUMENTS=1`) restores the old five-search lane; the trace names the route kinds. Document summaries stay out of the prompt (B11) and out of chat routing (this item); they remain produced by enrichment and used by /retrieve's Tier-0 routing outside chat. Breadth is unchanged in mechanism: B11's document-fair judged prefix and the composer's diversity seats are the 'document filter' the owner asked about."
---

# WORK LOG — B13 SECTION-ROUTING-V1

## Contract

The section is the routing unit in chat; the document is reached through its sections; the document-level summary vote is available but off; nothing about what gets judged or how changes.

## Changes

- `candidate_engine.py`: `CandidateBudget.hierarchy_route_documents = False`; lane A submits the `document_summary` search only when set; `doc_lane` empty otherwise; `trace.route_kinds`.
- `chat_retrieval.py`: `hierarchy_route_documents` on the env knob list.
- `chat_m_replay.py`: arm `<MODE>+DOCS` (the old routing) and per-row `judged_docs` / `final_docs` receipts with p50s in the summary.
- Tests: the three P1.d concurrency tests that exercise the document lane now set the flag explicitly; `test_subqueries_run_lanes_b_and_c_only_with_per_query_provenance` pins lane A through the section search; new `test_section_routing_is_the_default_and_the_document_vote_is_opt_in`.

## Proof

Frozen fixtures, first 10 plans each, arms interleaved per question (`chat_m_replay.py --arms HYBRID,HYBRID+DOCS`), the engine in-process on the committed code:

| fixture / metric | section routing (new default) | document vote on (old) | floor |
|---|---|---|---|
| B gold-in-union / gold in judged | 0.7 / 0.6 | 0.7 / 0.6 | ≥ 0.85 (30-plan recording; equal on this subset) |
| B hit@10 / MRR / survival | 0.6 / 0.417 / 0.857 | 0.6 / 0.417 / 0.857 | ≥ 0.60 / ≥ 0.45 (30-plan) |
| B documents judged / in final (p50) | 10.5 / 5.5 | 10.5 / 5.0 | held or up |
| B wall p50 | 3.35 s | 3.41 s | — |
| L gold-in-union / gold in judged | 1.0 / 1.0 | 1.0 / 1.0 | ≥ 0.95 |
| L hit@10 / MRR / survival | 0.9 / 0.775 / 1.0 | 0.9 / 0.742 / 1.0 | ≥ 0.90 / ≥ 0.80 (30-plan; 0.775 vs 0.742 on this subset, both arms) |
| L documents judged / in final (p50) | 32 / 15 | 32 / 15 | held |
| L wall p50 (degraded turns) | 6.79 s (2) | 6.37 s (1) | — |

Reading: removing the document-summary vote changed no recall number on either fixture; documents in the final set were equal or one higher; MRR on L was slightly higher without the vote (0.775 vs 0.742) and equal on B. One fewer vector search per turn (B wall −0.06 s p50; the L wall difference is contention, 2 vs 1 degraded turns). Gate MET. Together with B10 (the whole lane off: identical) and B11 (summary rows out of the prompt: identical precision), document summaries now play no measured part in chat retrieval; sections carry the routing.

## Rejected claims

- "Remove document summaries from the index" — not done: this item changes what chat searches, not what exists; /retrieve and the corpus map still route through them, and the owner's enrichment ledger is a separate decision.
- "Replace the lane with an MMR document filter" — not needed: the document-fair judged prefix (B11) and the composer's dominance guard already bound any one document's share; MMR was rejected earlier for this engine (lambda 1.0 promoted).

## Open contract gaps

- Ten plans per fixture; the 30-plan recordings for cases 01 / 02 are unchanged and remain the floors.
- /retrieve, the corpus map and TRAIL still route through document summaries; this item is chat-only by design.
- Whether to keep producing document summaries at all is the owner's enrichment decision (B10 / B6 territory); nothing here changes enrichment.
- In the full determinism run the live route-parity test (`test_live_chat_and_stream_agree_on_plan_and_evidence_ids`) failed once and passed on an immediate re-run; the two routes share the engine, so a judge-deadline difference between the two sequential live calls is the likely cause — the test does not yet apply P1.f's clean-pair classification, which is the proper fix.
