---
change_id: DEEP-RESEARCH-DR6
owner: "@king"
date: 2026-09-26
status: complete
status_note: "DR6a-c built: research moves in the engine (MOVE grammar, controller, signals, gap nodes, relevance gate, receipts), the route per move with /retrieve's optional intent and the reranker gate, and the UI's move labels and counter-evidence line. Moves off = DR1's engine, byte for byte. DR6d (the live A/B) waits for the deploy."
architecture_impact: "shared/polymath_shared/deep_research/moves.py (new), engine.py, prompts.py, __init__.py; shared/polymath_shared/probe_gate.py (gated_origins); orchestrator/orchestrator/api/retrieve.py (intent); orchestrator/orchestrator/api/deep_research.py (moves, move_request, _gate_port); frontend-v2 ProcessRail.tsx, AnswerBody.tsx, app.css; tests/contracts/test_deep_research_moves.py (new), test_retrieve_intent.py (new), test_deep_research_route.py (+9 tests); frontend-v2/src/__tests__/chat-deep.test.tsx (+4 tests)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR6a-c: research moves

## Contract
- DEEP-RESEARCH-MODE-V1 §10 and the §5 rows DR6a, DR6b, DR6c (register 11.524). The owner approved the design: "go for the
  deep research moves design".
- The orchestrating session added, for DR7 (§11, approved later the same day): keep the report change to the grouping and
  the counter-evidence line; expose each learning's goal id, move and cited documents, and the run's goals in plan order;
  keep the UI change to the rail labels and the counter-evidence line.

## Changes
- Commits on `feat/deep-research-moves`: DR6a `72612350`, DR6b `1d39aa62`, DR6c the commit that adds this log.
- **DR6a, the engine** (`shared/polymath_shared/deep_research/`):
  - `moves.py` (new, pure): the four MOVES, the §10.3 intent weights, `allocate` (largest remainder, ties in move order, exact
    fractions), the evaluative cues, the child mixes, and the repeat / concentration / one-sided checks.
  - `prompts.py`: the MOVE field (optional; an unknown value is a repair), the plan prompt's quota ("MOVES: write 1 broad,
    1 deep and 1 inverse query." plus one line per move), the gap line, and the report's three sections with the "no
    counter-evidence" line. Without moves every prompt and parse is DR1's.
  - `engine.py`: `Config.moves / gate_floor / spawn_floor`; `Row.doc_id`; `Learning.move`; an optional `gate` port. With moves:
    - acceptance fills each move's quota in plan order, then fills empty slots from the leftovers;
    - one gate call per level, before its searches;
    - `retrieve(query, scope, move=, anchor_docs=)`;
    - `_merge_moves` runs the signals, dry moves and gap nodes;
    - the receipt's `summary()["moves"]` block.
  - For DR7: `Learning.goal_id` and `doc_ids`, `QueryRecord.move` and `goal_id`, `ResearchOutcome.goals` (the level-1 searches
    in plan order). These are data only, filled with moves on or off.
- **DR6b, the route**:
  - `/retrieve` gains `intent`. On the v2 path of HYBRID / GRAPH / WILDCARD it applies
    `apply_intent_policy(intent, default_budget())`, lets ✨ latent still win, and sets `graph_assist = policy.graph`
    (`_engine_kwargs`, replacing three copies of the old latent block). Absent = the old kwargs. Unknown = 422
    `unknown_intent`. Any other path = 422 `intent_unsupported`.
  - `probe_gate.gate_probes(..., gated_origins=None)`: None keeps chat's origins.
  - `/research/deep`:
    - `DeepResearchRequest.moves = True`, and `POLYMATH_DEEP_RESEARCH_MOVES=0` forces moves off;
    - `move_request` builds each move's search (§10.1): broad = the base mode, with rows built under the EXPLORE cap; deep
      with anchors = the default lane with `document_ids`; adjacent / inverse = the base mode with `intent` RELATIONSHIP /
      COMPARISON;
    - rows carry `doc_id`;
    - `_gate_port` wraps `chat_retrieval._rerank_children` through `gate_probes`, with origin DEEP_RESEARCH and floor 0.2;
    - phase frames carry `moves` (plan) and `move` + `query` (search); a `deep_gate` frame reports each gate call.
- **DR6c, the UI**:
  - `ProcessRail` labels a deep research search "Broad · / Deep · / Adjacent · / Inverse · <query>".
  - `AnswerBody` shows "Counter-evidence: N findings" or "Counter-evidence: none found in the libraries" under the report,
    read from `meta.deep_research.moves.inverse`. It appears only when inverse searches ran.

## Proof
- Every §10.8 item has a test:
  - `test_deep_research_moves.py`, 37 tests: grammar, quotas and leftovers, `allocate`, each intent's mix, the evaluative
    reserve, repeat, concentration (only deep queries anchored), one-sided, dry, gap nodes inside the budget, the gate (floor,
    fail-open, deadline, spawn floor), the receipt and the report sections, the same outcome with 1 or 3 workers, DR7's
    fields, and moves off.
  - `test_deep_research_route.py`, +9 tests: each move's request, the EXPLORE cap for broad, the receipt's moves block, the
    frames, a gated search never runs, moves off by request and by the switch, the gate port, `gated_origins`.
  - `test_retrieve_intent.py`, 28 tests: absent intent = the exact old `chat_retrieve_mode` kwargs (with and without latent,
    in 3 modes); present = chat's budget and graph assist; unknown = 422; unsupported paths = 422.
  - The existing 42 deep research tests pass. The route defaults moves on, so the `rec` fixture now fakes the gate port (it
    would reach the live reranker) and the 3-argument `_build_rows` fake takes `**kw`. No assertion changed.
- Moves off against DR1: a scratch harness ran the pre-DR6 engine (`HEAD` 7051bf0c) and the new engine with moves off on 20
  scripted scenarios. The prompts, port calls, event streams, summaries, queries, learnings, evidence and report prompts
  were identical in all 20.
- Mutation checks (scratch). All 19 engine mutations and all 11 route mutations were caught, among them: the reserve off,
  repeat judged in completion order, anchors on every move, the gate asked about the thread, the switch ignored.
- `tests/contracts -k "not test_live_"`: 471 passed (397 before).
- The determinism tests that touch retrieval, intents and the gate: 195 passed. One fails, and it fails the same way at
  `HEAD`: `test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` (stale expected kwargs).
- Frontend: `tsc --noEmit` 0. vitest: 93 passed (4 new); each UI change fails its test when reverted.
- `agent_preflight.py`, `repo_guard.py` and `wiki_worm.py --check`: 0. Ruff: no new findings in the changed files
  (`retrieve.py` went from 41 to 39).

## Rejected claims
- "§10.1 says HYBRID, so every move searches HYBRID." The request's `mode` stays the base mode, and HYBRID is its default.
  A FAST or GNN run keeps its mode. There, adjacent and inverse search without the intent: `/retrieve` refuses an intent it
  cannot honour, and the route does not send one. The receipt's mode shows this rule.
- "An intent on an unsupported path can be ignored." §10.1 names only absent and unknown. Like `document_ids`, an intent a
  path cannot honour is a 422 (`intent_unsupported`), never a silent no-op.
- "An inverse query is anchored by its own GOAL line." No: restating the query there would pass anything. It must share a
  content term with its thread (the question itself at level 1), the thread's goal, or the parent's findings.
- Other readings, recorded here:
  - The evaluative reserve guarantees at least one inverse slot per level. The slot comes from deep first. Below level 1 it
    goes to the richest child, and gap nodes are left out.
  - "Deep-heavy" is all deep, today's meaning below level 1.
  - A gap node's line without MOVE defaults to broad, since it asks for one broad query.
  - A drifting thread's follow-ups are not listed as open questions.
  - `moves.inverse` sits in `meta.deep_research.moves`, the run's counts, with no second copy.
- `receipt.signals` (repeat / concentration / one_sided counts) is an addition, so DR6d can see which signals fired.

## Open contract gaps
- DR6d (live A/B, §10.9) waits for the deploy. It must watch:
  - the gate: one reranker call per level, bounded at 3 s, fail-open (`gate.failed_open`, `gate:*` in errors);
  - anchored deep searches on the default lane (its own lanes, Neo4j hop, reranker when `POLYMATH_G3_RERANKER=1`);
  - intent-policy lanes on adjacent / inverse searches: dual-read, latent, SEEALSO fan-out, graph destinations, and graph
    assist `auto` for RELATIONSHIP;
  - fewer rows per document on broad searches (EXPLORE cap);
  - LLM calls: gap nodes add up to 2 each, inside the budget.
- Found and left alone:
  - HYBRID still searches one library per call, so a multi-library run fails every HYBRID search. This predates DR6;
    anchored deep searches (default lane) do work across libraries.
  - A failed run's receipt has no `deep_research` block, because only the answer carries it.
  - The `stopped` phase label reads `reason`, but the engine emits `stop_reason`.
  - On thorough runs, the report's top-30 cap can drop inverse learnings. The counter-evidence line still counts them.
