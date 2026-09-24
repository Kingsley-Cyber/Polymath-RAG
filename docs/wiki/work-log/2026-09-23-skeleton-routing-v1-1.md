---
change_id: SKELETON-ROUTING-V1.1
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "shared + orchestrator code on branch feat/skeleton-probe-routes. With the doors open, skeleton lanes D–H run concurrently, merged in the fixed lane order (union unchanged). Every skeleton path carries a readable need: latent text, pMAP signature, atom, graph fact. The path-aware judge checks connection first and is path-fair (WILDCARD 6 needs). Receipts keep WLK2C's latent seat calibration plus the judge's and probe routes' records. Probe doors built behind POLYMATH_CHAT_SKELETON_PROBES and left OFF on evidence."
last_reviewed: 2026-09-23
---

# SKELETON-ROUTING-V1.1: faster doors, readable needs, a path-fair judge — and probe doors measured, not shipped

## Contract
- The owner, 2026-09-23 (leaving):
  - "fix the issues you've found based on your understanding of my intent";
  - "no more than 10 queries tests" (this slice spent none; the V1 live check spent 5);
  - "the skeleton works with my subqueries";
  - "i have questions, latent summaries which can all influence ranking and retrieval against a query".
- The two pasted design notes: every chunk keeps its discovery path; judge indirect chunks with context; a vague bridge
  earns nothing; no LLM judge.
- Design of record: `docs/wiki/plans/SKELETON-ROUTING-V1.md` §9, a new section.
- The V1 live check (register 11.441) found the defects this slice fixes.

## Changes
- `shared/polymath_shared/candidate_engine.py`:
  - **Lanes D, E, F, G and H are now self-contained functions** returning (candidates, receipt, needs).
    - `_run_route_lanes` runs them in order, or concurrently when `parallel_route_lanes` (a pool of their own).
    - Results merge in the fixed lane order.
    - A lane that raises becomes an empty, receipted lane.
  - **Lane D** records the latent text of each rescued parent as the route need.
  - **Lane H** takes the route need from `dest_need` (the fact phrase), never the doc id.
  - **`_contextual_judge`:**
    - it runs the connection check over every skeleton need (bounded to 3 × `contextual_max_needs`) before selecting;
    - vague needs are dropped and counted;
    - it picks needs path-fairly (each path's strongest usable need first).
  - **Probe doors** (`skeleton_probe_routes` > 0; default 0):
    - `_probe_order` picks BRIDGE / CORPUS_EXPLORE first, then PROFILE, then USER by weight;
    - `_probe_route` drives the door with the probe;
    - `_doc_fair_parents` takes one section per book first;
    - `_blend` reads children through the unit mean of the question and probe vectors;
    - candidates are tagged `[probe, rt:probe]` and keep the probe as their need;
    - the aspect counts `rt:probe`;
    - `trace.probe_routes`, `lane_sizes.probe_routes` and `funnel_lanes.probe_routes` exist only when probes ran.
  - **New fields:** `ROUTE_PROBE`; budget `skeleton_probe_routes` / `skeleton_probe_parents` / `skeleton_probe_children` /
    `parallel_route_lanes`; `SubQuery.derived_from`.
- `shared/polymath_shared/latent/rescue.py`: `LatentParent.need` holds the best hit's text.
- `shared/polymath_shared/skeleton_routes.py`:
  - opened doors set `parallel_route_lanes`;
  - WILDCARD reads 6 needs;
  - `POLYMATH_CHAT_SKELETON_PROBES=1` sets 7 (WILDCARD) or 4 probe routes.
- `orchestrator/orchestrator/api/chat_retrieval.py`:
  - `dualread_search(qv, *, docs=None, nominate=True, signatures=True)`. The defaults are the q0 door, unchanged.
  - The subquery spec carries `derived_from` (6th field).
  - `graph_dest_search` attaches `dest_need`, the hop's "subject predicate object" per destination book (a separate
    mentions read, only when paths are on).
- `orchestrator/orchestrator/api/ui.py`:
  - The plan's `derived_from` rides the subquery tuple.
  - `_turn_receipt_extras(trace, latent_selection, wildcard)` receives WLK2C's `_latent_receipt` at both call sites (S1a wired
    `latent_meta`, so every live receipt read null).
  - It keeps `retrieval_trace.contextual` and `retrieval_trace.probe_routes`, with their timings under `trace_ms`.
- `docs/wiki/experiments/skeleton-routing-2026-09-23/`:
  - `replay.py` gains the `deployed` / `probes` configs and passes `derived_from`, with `REPLAY_RESULTS` / `REPLAY_OUT`;
  - evidence files: `live_results.json`, `live_compare.json` (V1 live check), `replay_probes.json`,
    `replay_v1_deployed.json`, `replay_v11_deployed.json`.

## Proof
- **Unit tests (18 new, all green).** Three behaviour fixes were verified red by swapping the fix back out: path-fair
  needs, vague need, and the WLK2C receipt. The other tests cover new code.
  - `test_candidate_engine.py` (+12):
    - each probe drives the door its origin calls for;
    - probe path + need, never posing as q0;
    - blended read;
    - probe order;
    - doc-fair sections;
    - probes off by default;
    - parallel = sequential union;
    - a raising lane becomes an empty lane;
    - latent need;
    - graph fact need;
    - path-fair needs;
    - a vague need never spends its path's turn.
  - `test_skeleton_routes.py` (+2), `test_turn_receipt_extras.py` (+2).
  - `test_chat_runtime.py` (+1): the receipt keeps WLK2C's calibration.
- **Replay ($0; live stores + local embedder / reranker; tonight's five stored plans):**
  - production V1 against V1.1, deployed config:
    - the final evidence set is identical in 5 of 5 turns;
    - engine core time is 1.2–2.3 s lower;
    - wall time is 1.3–2.3 s lower per turn.
  - Probe doors: chunks at union ranks 65–110, final-set change in 1 of 5 turns. In WILDCARD they displaced *Force Dynamic
    Life Drawing* and *The Laban Workbook* (8 books → 6).
- **Lint:** 131 findings before and after across the five touched files (zero new).
- **Full determinism suite** (worktree PYTHONPATH, `-k "not test_live_"`): 5 failures, and every one fails identically on
  production in the same environment:
  - `test_query_receipts::test_all_three_query_handlers_and_read_surfaces_are_wired`: a source count, 4 ≠ 2;
  - `test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`;
  - `test_document_profile_stage::test_worker_writes_the_profile_and_projection_artifacts_with_the_receipt_chain`;
  - `test_fact_endpoint_eligibility::test_no_active_fact_has_a_pronoun_endpoint` and
    `test_killchain_pass2::test_punctuated_identifiers_survive_extraction_intact`: ledger reads.
  - `test_chat_modes::test_wildcard_sweep_overlaps_the_core…` (a race on `sweep_done_before_core`) failed in a targeted run
    on both trees and passed in the full run.

- **Contract dispositions** (`contract_impact` at commit):
  - CANDIDATE_ENGINE: UPDATED. Lanes concurrent, path needs, path-fair judge, probe doors behind a flag; engine tests +12
    and the full determinism suite.
  - EVIDENCE_BOUNDARY_API: UPDATED. Receipt-only fields (`latent_selection` wiring, `contextual`, `probe_routes`); the
    response shape is unchanged. Covered by `test_turn_receipt_extras` +2 and `test_chat_runtime` +1.
  - PROFILE_SCOUT_WIRING: UPDATED. The plan's `derived_from` rides the subquery tuple; scout behaviour is unchanged.
  - TESTED_UNCHANGED:
    - ACCEPTANCE, ADAPTER_RUNTIME, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE,
      RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE.
    - `tests/contracts/*` (the six impacted files): 63 passed.
    - The impacted determinism suites passed in the full run (`test_query_receipts` keeps its pre-existing source-count
      failure).
    - `tests/integration/test_cross_domain_routing.py` cannot be collected under the worktree PYTHONPATH (known trap;
      skip-gated).

## Rejected claims
- **"Routing each probe through the skeleton finds better evidence":** rejected on the replay (§9.2). The door works, but the
  probes the scout and bridge compiler emit are often off-target, so the door fetches off-target sections.
- **"Latent needs alone explain the WILDCARD swap":** the swap came from the need budget. Path-fair selection plus the
  connection check first restored V1's set.

## Open contract gaps
- Probe quality gate (plan §9.4): a plan-time connection check before probes spend slots and seats.
- Atom repair (plan §8): waits for the owner.
- The LIVE path of V1.1 needs its own check after the bounce (`LIVE_PATH_PROVEN`), within the owner's remaining 5 queries.
