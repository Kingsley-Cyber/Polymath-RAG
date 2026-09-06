---
title: "WORK LOG — B8 GRAPH-EVIDENCE-HYGIENE-V1: fact provenance is not evidence, one tag per passage, index pages out of the lanes"
change_id: GRAPH-EVIDENCE-HYGIENE-V1
date: 2026-09-06
owner: governance (owner backlog B8, released 2026-09-06; found on the owner's GRAPH control turn)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.115
package: orchestrator/orchestrator/api/ui.py (_evidence_legend: claim rows excluded, one tag per chunk), shared/polymath_shared/candidate_engine.py (structural_noise_reason, union noise filter + receipts), tests/determinism/test_chat_synthesis.py, tests/determinism/test_candidate_engine.py, docs/wiki/experiments/chat-presentation-b8-graph-{before,after}.json, chat-m-replay-b8-graph.json
architecture_impact: "GRAPH mode's prompt no longer carries unjudged passages. The assembler turns each graph fact into a `claim` item with its provenance passage and sorts claims first; the legend builder now skips claim items (the fact still reaches the prompt in the tagless `[fact:…]` block) and gives each chunk one [S#] tag however many bundle items carry it. Separately, the candidate engine drops back-of-book index pages and page-number lists from the fused union before truncation by a conservative lexical test (page-link density ≥ 6 and ≥ 1 per 120 chars, or ≥ 45 % bare-number tokens over ≥ 40 tokens), receipted as `noise_dropped` / `noise_reasons` / `noise_sample`; the materializer's region roles are the long-term source of that label and are not available at lane time. Facts, seeds, hop bounds and the GRAPH composition are unchanged."
---

# WORK LOG — B8 GRAPH-EVIDENCE-HYGIENE-V1

## Contract

Every [S#] row was judged; a chunk has one tag; a fact rides as a fact; a page of index entries never competes with prose.

## Changes

- `ui._evidence_legend`: `kind == "claim"` items skipped; `seen_chunks` dedup; both projections of the legend on the answer event keep `breadcrumb`.
- `candidate_engine.structural_noise_reason(text)` (pure) + the union filter before `merged_candidate_max`, with trace receipts.
- Tests: `test_graph_hygiene_claims_are_not_evidence_rows_and_tags_are_unique_per_chunk`; `test_structural_noise_filter_drops_index_pages_and_number_lists_but_never_prose`.

## Proof

GRAPH probe, the same 10 fixture-B questions in GRAPH mode (before = the code before this change, after = with it):

| metric (10 GRAPH turns) | before | after | target |
|---|---|---|---|
| answered | 10 / 10 | 10 / 10 | 10 / 10 |
| legend rows p50 (range) | 21.5 (17–38) | 15 (15–15) | the composer's judged set only |
| duplicate rows (total) | 41 | 0 | 0 |
| unjudged rows beyond the judged set (total, est.) | 61 | 0 | 0 |
| index-page rows in the legend (total) | 5 | 0 | 0 |
| citation tags p50 | 10.5 | 12 | held |
| prompt chars p50 | 33,748 | 27,269 | down |
| wall s p50 | 32.0 | 38.3 | — (model variance) |

Every row the model saw in the after-run was one of the composer's judged passages, once; the facts still reached the prompt as the tagless facts block.

Frozen-plan modes replay (GRAPH bounds): `chat_m_replay.py --fixture B --arms HYBRID,GRAPH --limit 10 --tag b8-graph`: GRAPH graph_facts_max 20 (≤ 20), graph_seeds_max 8 (≤ 8), graph_degraded_turns 0, errors 0, wall p50 HYBRID 3.55 s → GRAPH 4.01 s (Δ +0.46 s, gate ≤ 1.5 s); gold-in-union 0.7 on both arms for this 10-turn subset (identical: the hygiene changes what the prompt shows, not what retrieval finds). The 30-turn manifest recordings for case 11 stand unchanged.

Owner's control turn (2026-09-06 19:19, before): 35 chunk rows in the legend for 15 judged passages, 3 duplicate rows, 2 index-page chunks, S1 / S2 / S5 unjudged and cited. After (same prompt, GRAPH, 22:21): 15 legend rows, 0 duplicates, 14 facts in the tagless block, 30 citation tags in a 3,941-character answer, prompt 37,638 chars (was 63,965); the first rows are the judged Screen Combat Handbook and Fight Choreography passages with breadcrumbs ("The Screen Combat Handbook … › Bounce", "Fight Choreography … › …"). That turn also carried `embed_deadline` and `rerank_timeout` degradations (enrichment contention), unrelated to the change.

## Rejected claims

- "Judge the provenance passages and admit the ones above the floor" — not taken: it adds a judge call per fact per turn on the contended judge; the facts block already carries the claim, and a passage the judge liked is in the evidence anyway. Recorded as the alternative the backlog row allowed.
- "Filter by the materializer's region role" — not available at lane time (roles live in the document's source map, not on the chunk); the lexical test is the bridge until roles ride the chunk payload.

## Open contract gaps

- The lexical noise test is conservative by design; a table of contents rendered as prose lines passes it.
- The probe cannot count facts from the answer event (they ride the `graph_done` phase event and the prompt, not `retrieval`); the replay reports them.
- The graph lane's value with its passages gone is the facts block alone; whether those 20 `subject —predicate→ object` lines earn citations is a question for the B10-style ablation, not settled here.
