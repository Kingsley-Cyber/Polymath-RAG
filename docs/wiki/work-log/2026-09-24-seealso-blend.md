---
change_id: SEEALSO-BLEND-V1
owner: "@king"
date: 2026-09-24
status: complete
status_note: "Replaces the 11.472 book-finding hop on the owner's word. Merged 95d7832a; the live .env carries POLYMATH_CHAT_SEEALSO_BLEND=1 (question weight 0.7) and no longer the hop flag. LIVE AT THE NEXT FLEET BOUNCE: the agent's bounce was denied as Production Deploy (2026-09-24 22:5x MDT) and handed to the owner. Until then the running orchestrator (started 22:15:46) still holds the retired hop code, whose module file the merge removed: a GRAPH / WILDCARD turn that reaches the hop would lose lane G for that turn (receipted as degraded, never silent). Rollback = 0 + a bounce. Live confirmation: the next HYBRID / GRAPH / WILDCARD chat whose lane G runs (receipt: trace.seealso_fanout.blends)."
architecture_impact: "shared (new seealso_blend.py replacing seealso_hop.py; candidate_engine lane G blend fields, cap + receipt; skeleton_routes switch; search_atoms doc_ids filter) + orchestrator (chat_retrieval fanout_search; the alpha knob). Lane G is byte-identical with the flag off. Fence + one bounce."
last_reviewed: 2026-09-24
---

# SEEALSO-BLEND-V1: SEE ALSO as a semantic search for similar ideas

## Contract
- The owner, 2026-09-24, after the hop (11.472) went live: "well i dont think see also should be used to find books i
  think semantic search for similar ideas, maybe a system that takes see also in a document level supplemnent it with a
  search simialr to semantci and relevant of the query and search for whats in their … because see also is doc levle".
- So: SEE ALSO lines are document-level; they widen the IDEA, they never pick books. Blend them with the question and
  search the content.

## Changes
- `shared/polymath_shared/seealso_blend.py` (new; replaces `seealso_hop.py`):
  - `blend(q, item, alpha)` = unit(alpha · q̂ + (1 − alpha) · î);
  - `blend_rows(items, vectors, *, question_vector, search_children, alpha, children_per_item)`: one blended probe per
    line, passages from anywhere in the corpus, deduplicated across lines, tagged `fanout_atom` + `seealso_blend`,
    fail-open per line.
- `chat_retrieval.fanout_search`:
  - the question's documents = the scout's own profile nomination (`profile_nominate`, answer surfaces, k = 4);
  - their SEE ALSO lines ranked by the question (`search_atoms(…, doc_ids=…)`, k = 4);
  - one batch embed; each line blended with the question and searched over the corpus (4 passages each).
- `profile_atom_projection.search_atoms`: an optional `doc_ids` filter (an empty list → nothing).
- `candidate_engine.CandidateBudget`: `seealso_blend_enabled / _docs 4 / _items 4 / _children 4 / _alpha 0.7`; the hop
  fields are removed. Lane G's cap makes room for the blend rows; the receipt gains `blends` (line, document) and
  `blend_candidates`.
- `skeleton_routes`: `seealso_blend_enabled` = `POLYMATH_CHAT_SEEALSO_BLEND=1`, in every mode that opens lane G (HYBRID
  when the plan nominated documents, GRAPH, WILDCARD; never FAST / GNN). `POLYMATH_CHAT_SEEALSO_HOP` is retired.
- Knobs: `POLYMATH_CHAT_SEEALSO_BLEND_DOCS / _ITEMS / _CHILDREN / _ALPHA`.
- Tests:
  - `test_seealso_blend.py` (5): the blend math and weighting; one corpus-wide probe per line; fail-open; the mode +
    flag switch; the atom doc filter;
  - `test_candidate_engine.py`: the hop test is replaced by the blend's cap + receipt test;
  - `test_seealso_hop.py` is removed with its module.
- Live `.env`: `POLYMATH_CHAT_SEEALSO_HOP=1` → `POLYMATH_CHAT_SEEALSO_BLEND=1` (after the merge, at the bounce).

## Proof
- Unit (worktree, PYTHONPATH origins inside it, safe recipe): 88 tests on the blend / engine / routes / atom files, 0
  failures. The wide impacted list gave 306 tests with the same 2 known pre-existing failures as production.
- Replay ($0, `docs/wiki/experiments/seealso-blend-2026-09-24/replay.py` → `replay.json`): the five stored questions in
  their own mode and in GRAPH (7 runs), base vs blend 0.5 vs blend 0.7.
  - Blend 0.5: new evidence in 4 of 7 runs.
  - Blend 0.7: new evidence in 7 of 7 runs (1–3 passages each); direct (q0) evidence unchanged in every run; lane G
    +0.2–1.0 s (lanes run in parallel).
  - Blend 0.7 swaps:
    - "weighty movement" gained "a live actor … deals with gravity automatically" and "timing … the feeling of size and
      scale", and dropped an off-topic author bio;
    - "lighting and color" gained "We 'feel' color … people look green when sick";
    - "suspense" gained "cutting back and forth at an increasing pace creates suspense";
    - one sideways swap (two relevant editing passages); no clearly worse swap (the hop had one).
  - The blended passages are also reachable by the dense lane; the blend lifts the most on-point ones into the evidence.
- The 11.472 hop replay stays as evidence (`docs/wiki/experiments/seealso-hop-2026-09-24/`).

## Rejected claims
- "Use SEE ALSO to find books" (11.472): the owner rejected it; SEE ALSO is a document-level pointer to ideas.
- "Weight the line and the question equally": 0.5 lifted evidence in 4 of 7 runs, 0.7 in 7 of 7.

## Open contract gaps
- `contract_impact.py --range c36ac730..HEAD`: 2 changed + 14 transitive. The TESTS TO RUN, safe recipe, branch vs a
  production baseline:
  - the contracts + adapter / MCP / evidence / scout / provenance files: 170 tests, 0 failures on both;
  - `test_profile_atom*.py` (3 files): 14 tests, 0 failures on both;
  - engine / chat retrieval / chat runtime / resolution / yield / manifest writer: 132 tests, 1 failure on both (the known
    `test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_…`).
- CANDIDATE_ENGINE: UPDATED (the blend fields replace the hop fields; byte-identical off).
- PROFILE_ATOM: UPDATED (`search_atoms` gains an optional `doc_ids` filter; the default `None` keeps every existing call
  unchanged).
- ACCEPTANCE, ADAPTER_RUNTIME, EVIDENCE_BOUNDARY_API, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_SCOUT_FUSION,
  PROFILE_SCOUT_INPUT, PROFILE_SCOUT_OUTPUT, PROFILE_SCOUT_WIRING, PROFILE_YIELD_RECEIPT, QUERY_PLANNER,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE: TESTED_UNCHANGED (the runs above).
- DEFERRED, not run:
  - `tests/determinism/test_adapter_product_discovery_loop.py` (writes the fleet database);
  - `tests/determinism/test_query_receipts.py` (hard-coded fleet connection);
  - `tests/integration/test_cross_domain_routing.py` (not collectable under the worktree PYTHONPATH; skip-gated).
