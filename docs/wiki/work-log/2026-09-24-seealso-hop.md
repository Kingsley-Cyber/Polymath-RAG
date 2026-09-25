---
change_id: SEEALSO-HOP-V1
owner: "@king"
date: 2026-09-24
status: complete
status_note: "The one-hop SEE ALSO door (owner decision D8) is built and replay-measured. It is switched ON in the live .env for GRAPH and WILDCARD on the owner's 'man fix the see also'; rollback = POLYMATH_CHAT_SEEALSO_HOP=0 + a bounce. Live confirmation comes from the owner's next GRAPH / WILDCARD chats (receipt: trace.seealso_fanout.hops)."
architecture_impact: "shared (new seealso_hop.py; candidate_engine lane G cap + receipt; skeleton_routes switch) + orchestrator (chat_retrieval fanout_search; fast.py list filters → MatchAny). Lane G is byte-identical with the flag off. Fence + one bounce."
last_reviewed: 2026-09-24
---

# SEEALSO-HOP-V1: the one-hop SEE ALSO door

## Contract
- The owner, 2026-09-24: "man fix the see also". Owner decision D8 (DOCUMENT-RAG-COMPLETION-V1 §1): "GRAPH traversal: one hop
  only (SEEALSO / concept neighbour)"; §5's "neighbour door": the item vector searches other documents' items → their maps →
  children.
- Correction to the agent's own earlier report (same day). It had described SEE ALSO from the 09-23 enrichment audit,
  which predates two later slices:
  - the atom repair (11.445) made all of each book's SEE ALSO items searchable: 696 cinema items in 67 books, 100 in
    commerce-v1 (EXECUTED count);
  - the skeleton routes (11.441–11.444) run the SEE ALSO lane (G) on every GRAPH and WILDCARD turn, and in HYBRID when
    the plan nominated documents.
  - Receipts since then (14 UI turns): lane G ran in 9, brought 190 candidates; 21 reached the evidence (10 found by no
    other lane) and 15 were cited.
- The bridge compiler's "kind name instead of text" bug (audit defect 2) was already fixed
  (`bridge_integration.concepts_from_nominations`).
- What was genuinely missing is the one-hop door. This slice builds it.

## Changes
- `shared/polymath_shared/seealso_hop.py` (new), `hop_rows(items, vectors, *, question_vector, nominate, search_maps,
  search_children, docs_per_item, children_per_item, parallel)`:
  - each SEE ALSO item's vector nominates documents on what they are ABOUT (identity / theme / title / concepts /
    theories, `HOP_SURFACES`, never their own see-also pointers), excluding the pointing document;
  - the QUESTION vector picks the parent maps and the original children inside them (ONE child search per item);
  - items run concurrently and merge in item order; rows carry `fanout_atom` (the need for the path judge) and
    `seealso_hop`;
  - every lookup fails open.
- `candidate_engine.py`:
  - `CandidateBudget.seealso_hop_enabled / _items (3) / _docs (2) / _children (4)`;
  - lane G's cap grows by items × children when the hop is on (lane rows are taken in order, so appended hop rows were
    cut);
  - the receipt gains `seealso_fanout.hops` (item, from_doc, to_doc) and `hop_candidates`.
- `skeleton_routes.py`: `seealso_hop_enabled` = GRAPH or WILDCARD and `POLYMATH_CHAT_SEEALSO_HOP=1`.
- `chat_retrieval.fanout_search`:
  - a dedicated SEEALSO atom search for the hop (the relational top-k may hold only BRIDGE / ANCHOR atoms);
  - ONE batch embed for the global door and the hop;
  - the hop wired with the profile collection, the parent-map collection and the searcher.

  `_INT_KNOBS` gains the three sizes (`POLYMATH_CHAT_SEEALSO_HOP_ITEMS / _DOCS / _CHILDREN`).
- `fast.py` `FastSearcher._filter_for`: a list / tuple / set value is `MatchAny` (one search across several parents); a
  string keeps `MatchValue`, so existing callers are unchanged.
- Tests:
  - `tests/determinism/test_seealso_hop.py`, 6 tests: the pointer chooses the documents and the question the passages;
    one child search; caps and cross-item dedup; deterministic parallel merge; fail-open; the mode + flag switch; the
    list filter;
  - `test_candidate_engine.py` +1: hop rows get room in lane G and are receipted.
- Live `.env`: `POLYMATH_CHAT_SEEALSO_HOP=1`, set after the merge; applies at the bounce.

## Proof
- Unit (worktree, PYTHONPATH origins inside the worktree, safe recipe):
  - the hop / engine / skeleton-route files: 81 tests, 0 failures;
  - the wider impacted list (27 files incl. the contract-impact TESTS TO RUN): branch 307 tests with 2 failures,
    production 300 tests with the same 2 known pre-existing failures (`test_chat_modes::test_wildcard_sweep_overlaps…`,
    `test_chat_runtime::test_compiler_on_drives…`).
- Replay ($0, `docs/wiki/experiments/seealso-hop-2026-09-24/replay.py` → `replay.json`): the five stored questions, live
  config vs live + hop; 3 in GRAPH, 2 in WILDCARD; real stores, local embedder / reranker, no model call.
  - The first version ranked the destination passages by the SEE ALSO item and did one search per section. Result: 12 hop
    candidates per turn, 0 reached the evidence, lane G +3 s.
  - The final version lets the question pick the passages, with one search per item and items in parallel:
    - new evidence in 4 of 5 runs (2, 3, 0, 2, 1 passages), each swapped for one existing passage;
    - direct (q0) evidence unchanged (15→15, 14→14);
    - lane G 1.0–1.2 s → 1.8–2.3 s, but wall time only +0.04 to +0.83 s (lanes run in parallel).
  - Read of the swaps:
    - "weighty movement" (GRAPH): gained the library's most direct passage ("Weight is perceived when movement has
      consequences…"), lost an equally good Don Graham passage;
    - same question (WILDCARD): gained 3 relevant passages, dropped an off-topic author bio;
    - "lighting and color" (GRAPH): a sideways swap;
    - "suspense without dialogue" (WILDCARD): slightly worse (lost "suspense by not revealing the audio source").
  - The new passages were also found by the global dense lane. On these questions the hop PROMOTES question-relevant
    passages in the books the pointers lead to; it did not discover passages no other lane found.

## Rejected claims
- The agent's earlier "SEE ALSO lines are never searched / about 1 per document / only for relationship questions": stale
  (see Contract).
- "Rank the destination passages by the SEE ALSO item": measured, it reaches no evidence (the reranker judges against
  the question).
- "Lane H already hops through SEE ALSO": lane H follows Neo4j entity facts, not SEE ALSO.

## Open contract gaps
- CANDIDATE_ENGINE: UPDATED (lane G cap + receipt; byte-identical with the flag off, `test_candidate_engine` green).
- ACCEPTANCE, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, RETRIEVAL_RECEIPT: TESTED_UNCHANGED (their TESTS TO RUN are green;
  the same 2 pre-existing failures as production).
- `tests/integration/test_cross_domain_routing.py`: DEFERRED. It cannot be collected under the worktree PYTHONPATH and is
  skip-gated behind `POLYMATH_INTEGRATION=1`.
- Live: the owner's next GRAPH / WILDCARD chats show `trace.seealso_fanout.hops` in their receipts. S6's other doors
  (profile-multivector select, home door) stay in DOCUMENT-RAG-COMPLETION-V1; the atom store already serves item-level
  select + the global door.
