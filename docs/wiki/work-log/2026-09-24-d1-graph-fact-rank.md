---
change_id: D1-GRAPH-FACT-RANK
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "orchestrator only: retrieve.py (the hop-1 fact order behind POLYMATH_GRAPH_FACT_RANK, card seeds best-first under the same flag, the selected-facts read), chat_retrieval.py (graph_bounds.fact_order receipt), mcp_server.py (truncation marker). Flag OFF = the legacy query and order. Fence-safe (no shared/workers/control change); the orchestrator and the MCP slot pick it up at a bounce."
last_reviewed: 2026-09-24
---

# D1: GRAPH hop-1 facts ranked; MCP rows say when their text was cut

## Contract
- `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 6 (D1): "GRAPH hop-1 facts ranked by seed rank × predicate tier ×
  evidence in the selected set (replay on saved GRAPH plans shows the change); MCP rows say `truncated` + full length";
  slice note: "the fact order must stay deterministic (ties broken by `fact_id`)".
- Gaps D-01 (`ORDER BY fact_id LIMIT 20`: `fact_id` is a hash, so the 20 facts are an arbitrary pick) and D-02 (MCP
  trims text with no marker).
- The owner, 2026-09-24: "Then D1 (roadmap row 6): GRAPH hop-1 facts ranked + the MCP truncation marker."

## Changes
- `orchestrator/orchestrator/api/retrieve.py`:
  - `POLYMATH_GRAPH_FACT_RANK` (default off) and `fact_rank_enabled()`;
  - `rank_graph_facts(rows, seed_ids, selected_fact_ids)`: a lexicographic, weight-free order —
    1. a fact with an evidence row among the selected chunks (the answer can cite it this turn);
    2. a specific predicate before the ontology's last resort (`RELATED_TO`, "keep rare": `ontology.LAST_RESORT`);
    3. the seeds take turns: each seed's first fact, then each seed's second, … (inside a turn, the resolver's seed
       order);
    4. `fact_id` for ties;
  - `_selected_fact_ids(conn, chunk_ids)`: one read of `evidence` for the selected chunks;
  - `_neo4j_expand`, flag on: the same Cypher (authorization still inside the query) reads the authorized pool up to 500
    facts (`LIMIT $pool`), then ranks and keeps 20. Flag off: the legacy query string and order, unchanged;
  - `_corpus_seed_ids`, flag on: entity cards keep the probe's best-first order. Sorting them by id discarded that
    order, and a definitional turn (2 seeds) kept the two alphabetically-first cards instead of the two best.
- `orchestrator/orchestrator/api/chat_retrieval.py`: `meta.graph_bounds.fact_order = "ranked"` when the flag is on (absent
  = the legacy window).
- `orchestrator/orchestrator/mcp_server.py` (D-02, no flag): `_trim_rows` (1,200 characters) and `_trim_hit`
  (1,400 / 600) add `truncated: true` + `full_length` (characters before the cut) to a row whose text was cut; a row that
  fits keeps exactly its old keys. `retrieve`'s inline trim now calls `_trim_rows`.
- Tests: `tests/determinism/test_graph_fact_rank.py` (12).
- Receipts: `/retrieve` answers `graph_fact_order: "ranked"` when the flag is on (a $0 live check).
- Replay: `docs/wiki/experiments/graph-fact-rank-2026-09-24/replay.py` → `replay.json` (final order) and
  `replay_strict_seed.json` (the rejected first design).

## Proof
- Unit (worktree `pmv4-d1-facts`, PYTHONPATH origins inside it, safe recipe): `test_graph_fact_rank.py` 12 / 12. The
  impacted list (tests/contracts whole + 17 determinism files) matches a production baseline: the same 2 known failures
  (`test_chat_modes::test_wildcard_sweep_overlaps…`, `test_chat_runtime::test_compiler_on_drives…`).
- Replay ($0, EXECUTED 2026-09-24, worktree code, live stores + local sidecars): 8 GRAPH questions (the 3 stored
  RETRIEVAL-PATHWAYS-5Q plans + the 5 most recent distinct GRAPH receipts with a saved plan), each flag off / on / off
  again:

  | question | citable facts (proving chunk in the evidence) off → on | RELATED_TO off → on | pool |
  |---|---|---|---|
  | weighty animated movement | 0 → 1 | 2 → 1 | 50 |
  | suspense without dialogue | 2 → 2 | 0 → 0 | 21 |
  | lighting and color | 0 → 0 | 4 → 0 | 66 |
  | UGC image prompt | 0 → 0 | 0 → 0 | 13 |
  | lone photographer's batteries | 0 → 9 | 2 → 0 | 105 |
  | camera equipment and batteries | 0 → 0 | 0 → 0 | 63 |
  | "shape" in Laban terms | 9 → 17 | 1 → 0 | 37 |
  | memorable ideas | 1 → 1 | 1 → 1 | 12 |

  - 12 → 30 citable facts in total; 10 → 2 last-resort facts. Pools 12–105, far below the 500 read cap.
  - Direct (q0) evidence unchanged in every run. The evidence set: 6 of 8 identical; "weighty" differs by one passage,
    and so did the second OFF pass (run noise); "batteries" swapped one off-topic "Lighting for Cinema" newsmagazine
    passage for another (cross-encoder −9.5 → −8.4).
  - Graph time: 661–724 ms off, 677–733 ms on.
- The facts, read: "suspense" keeps its own facts ("shorter and shorter shots CAUSES suspense", "anxiety CAUSES
  suspense") after the two citable ones; "lighting" spreads across its seeds (three-point lighting, natural realism,
  "lighting ACTS_ON eyes of the viewer", "softlight CAUSES illusion of reality"); "batteries" leads with nine citable
  facts ("led lights USES batteries", "camera prep ACTS_ON batteries", the LED makers).

- Post-merge fix (register 11.479, EXECUTED 2026-09-25). The agent's bounce after the merge was denied (Production
  Deploy). A $0 baseline of `live_check.py` then showed `/retrieve` GRAPH answering HTTP 500: `ImportError: cannot import
  name 'fact_rank_enabled' from 'orchestrator.api.retrieve'` (orchestrator.log). The running orchestrator (started
  23:21 MDT) keeps its pre-D1 `retrieve` module in memory, while `chat_retrieval.py` is loaded from disk on first use
  (`retrieve.py:256-315`; every chat turn through `ui.py:3784`). So every chat turn would have failed until the bounce.
  - Fix: `chat_retrieval.py` imports `fact_rank_enabled` behind `except ImportError`. The fallback reports the legacy
    order, which is what the old process serves.
  - Test: `test_chat_retrieval_loads_beside_a_retrieve_module_from_before_d1` (loads the file next to a stub pre-D1
    module).
  - After the fix, `/retrieve` GRAPH answered 200 on the same old process: 20 graph facts, no `fact_order` (legacy).
- The live check (`live_check.py`, $0: `/retrieve` GRAPH `meta.graph_bounds.fact_order` + MCP `polymath_search`
  markers) runs after the owner's bounce. Its pre-bounce baseline (`live_check_before_bounce.json`) recorded the MCP
  defect live: 116 rows, 2 cut at exactly 1,200 characters with no marker.

- **LIVE_PATH_PROVEN** (EXECUTED 2026-09-25 00:10 MDT, register 11.480). The owner's bounce at 00:09 started the
  orchestrator and MCP Server A at 00:09:08, with `POLYMATH_GRAPH_FACT_RANK=1` in the orchestrator environment
  (`ps eww`); the fleet came back as 26 / 13 / one bundle `c6687ef2365a`. `live_check.py` exited 0
  (`live_check.json`):
  - `/retrieve` GRAPH on :7200: HTTP 200, `meta.graph_bounds.fact_order: "ranked"`, 20 facts, for all three questions;
  - MCP `polymath_search` on :8930: 114 rows. The 1 cut row says `truncated` (exactly 1,200 characters, a longer
    `full_length`), and no unmarked row is at or over 1,200. Before the bounce: 2 of 116 rows cut with no marker.

## Rejected claims
- "Rank strictly by seed" (the first design, `replay_strict_seed.json`): the entity-card probe ranked "ADR" top for
  "suspense WITHOUT dialogue" (it matched "dialogue"), so its facts filled the list and "shorter and shorter shots CAUSES
  suspense" fell out of the 20. Lane H (which expands the same facts to find destination documents) also lost on-topic
  passages: the batteries question lost "the lights could run on AC or DC … operated off batteries in the field", and
  the equipment question lost an on-set equipment checklist. Seeds taking turns fixed all three.
- "RELATED_TO facts are always noise": some carry content ("illusion of reality RELATED_TO lighting"). They are ranked
  last, not removed; a pool with fewer than 20 specific facts still shows them.
- "Score the facts with fixed weights (seed rank × tier × evidence)": a lexicographic order gives the same priorities
  with no weights to tune and stays deterministic.

## Open contract gaps
- CANDIDATE_ENGINE (`chat_retrieval.py`): UPDATED (a receipt key under `meta.graph_bounds`, flag on only; the graph
  order reaches lane H through `graph_expand_or_502`, replayed above).
- MCP_SURFACE (`mcp_server.py`): UPDATED (additive `truncated` / `full_length` on cut rows only; the evidence-row schema
  allows extra keys).
- ACCEPTANCE, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, RETRIEVAL_RECEIPT: TESTED_UNCHANGED (the impacted list above).
- DEFERRED: `tests/determinism/test_query_receipts.py` (hard-coded fleet connection);
  `tests/integration/test_cross_domain_routing.py`, `test_corpus_scoped_graph.py` (skip-gated; not collectable under the
  worktree PYTHONPATH).
- Gap D-02's full-unit reader stays with C9.
