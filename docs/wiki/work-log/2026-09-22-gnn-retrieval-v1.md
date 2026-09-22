---
change_id: GNN-RETRIEVAL-V1
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "Retrieval layer, additive: a fifth public mode GNN = graph-neural PARENT routing over the isolated experimental Qdrant collection → the existing routing_child search → the existing reranker; candidate engine lane I (GNN_ROUTE, default OFF ⇒ byte-identical union); mode registry, chat dispatch, chat receipt (meta.gnn), frontend PUBLIC_MODES. No ingestion / extraction / production-projection change; removable by dropping the polymath_gnn_parent_* collections."
last_reviewed: 2026-09-22
---

# GNN-RETRIEVAL-V1 — the experimental fifth retrieval mode, implemented, wired, tested, qualified

## Contract
Owner design 2026-09-22 (`polymath_gnn_retrieval_experiment.zip`, controlling context) executed on the repository as it is: **the GNN routes,
ORIGINAL children prove, the existing reranker judges**; smallest correct path at existing seams; no redesign, no new endpoint, no new
encoder, no ingestion or extraction change; the four existing modes untouched; an E2E comparison with causal controls decides A–E (plan §32).
Plan of record: `docs/wiki/plans/GNN-RETRIEVAL-V1.md`. Verdict: `docs/wiki/reports/2026-09-22/GNN-RETRIEVAL-V1-QUALIFICATION.md` (**D + C**:
projection helps, topology not causal; mostly duplicates existing routing — stays experimental).

## Changes
- `shared/polymath_shared/retrieval_modes.py` — `MODE_GNN`, fifth `EXPOSED_MODES` entry (the four existing and `DEFAULT_MODE` unchanged).
- `shared/polymath_shared/gnn_route.py` (new) — `GNN_ROUTE_CONTRACT`, `collection_name` (`polymath_gnn_parent_<embedding>_<gnn_contract>`), `verify_collection` (typed refusals: dim / embedding contract / missing / payload kind), `gnn_parent_search` (one corpus; routes only), `hydrate_original_children` (the caller's routing_child search, corpus + doc + parent filtered, deduped, capped), `route` + receipt.
- `shared/polymath_shared/candidate_engine.py` — `ARRIVAL_GNN_ROUTE`; budget `gnn_enabled / gnn_parent_k / gnn_children_per_parent / gnn_children / gnn_family / gnn_variant`; `retrieve_candidates(gnn_search=)`; lane I after lane H (same pattern), unioned last; `lane_sizes.gnn_route`, `funnel_lanes.gnn_route`, `trace.gnn` (typed `code` + `degraded` on failure); `synthesis_role(GNN_ROUTE) = RELATIONAL`.
- `orchestrator/orchestrator/api/chat_retrieval.py` — `MODE_LANES[GNN] = ()` and `_retrieve_gnn`: the GNN route ALONE (no A/B/C, every additive depth lane forced off — the chat path's intent policy would otherwise add latent / dual-read / lift), `meta.mode = GNN`, `meta.gnn` receipt, typed `meta.degraded`; the `gnn_search` closure beside `graph_dest_search`; `POLYMATH_CHAT_GNN_*` knobs (`_STR_KNOBS` for family / variant).
- `orchestrator/orchestrator/api/ui.py` — `GNN` accepted on the same `/chat` path; `gnn_requires_v2` refusal when the v1 engine is forced; `retrieval.gnn` in the chat receipt (None for other modes).
- `frontend-v2/src/lib/contracts.ts` — `PUBLIC_MODES = [HYBRID, GRAPH, WILDCARD, GNN]` (Chat selector + Compare screen); `components/LaneTable.tsx` alias `GNN_ROUTE → gnn_route`; `src/__tests__/retrieval-modes.test.ts`.
- `eval/gnn_route/` (new: `graph_snapshot.py`, `propagate.py`, `model.py`, `project.py`, `README.md`) + `scripts/gnn_route_build.py`, `scripts/gnn_route_qualify.py`; experiment records under `docs/wiki/experiments/gnn-route/cinema/`.
- Tests: `tests/determinism/test_gnn_route.py` (13), `tests/determinism/test_gnn_offline.py` (6); `test_candidate_engine.py` lane-set pin extended (`gnn_route` receipted, empty when off).
- No new runtime dependency: torch (already in the venv) is used only by the offline `model.py`; the deployed runtime imports nothing new.

## Proof
UNIT_PROVEN in the worktree (DB-free): route + engine + registry 13 / 13, offline half 6 / 6, engine 59, determinism + contracts suites green except the pre-existing live-compiler test (`test_chat_hygiene::…skips_retrieval…`, identical on `production`). Frontend: vitest 2 / 2, `tsc` clean, build ok. WORKTREE_INTEGRATION_PROVEN + REAL_INPUT_EXECUTED on a second orchestrator started from THIS worktree on :7201 (packages resolve to the worktree — verified by `__file__`): GNN and the four existing modes through `/chat/stream`, every cited chunk an original `chunks` row; frontend E2E in the built-in browser (selector shows GNN; `mode: "GNN"` sent; requested = executed = GNN; union 12 = `gnn_route`; 12 cited; HYBRID normal afterwards). Qualification: `scripts/gnn_route_qualify.py` over L + B (30 queries) for M1 and M2 with the no-graph / shuffled controls, Test A and Test B. Guards 0 / 0 / 0 / READY. Not merged into `production` by this work-log's commit; the live fleet (:7200) still serves the checkpoint until merged + bounced.

## Rejected claims
- "GNN adds unique retrieval value on cinema" — refused by the controls: unique gold 0 / 30 (both families), real ≤ shuffled (M1), real = nograph (M2).
- "Topology is what helps in Test B" — refused: B ≈ C ≈ D; the lift is the parent-route seat / projection.
- "FAST is in the v2 selector" — it is not (pre-existing; the backend accepts it); GNN was added beside the modes the selector actually has.
- "The first-message scratch-chat stream works" — it strands (the pre-existing scratch-key remount trap, memory 2026-09-17); "+ New chat" works; not touched here.

## Open contract gaps
- `CandidateBudget` / engine trace: UPDATED additively (new optional fields, new receipt keys; `lane_sizes` gains `gnn_route`) — TESTED_UNCHANGED for every other lane (byte-identical union when off).
- Chat receipt (`retrieval.gnn`): UPDATED additively; None for every other mode.
- `retrieval-mode-v1` (`EXPOSED_MODES`): UPDATED additively (fifth entry).
- Frontend contracts (`PUBLIC_MODES`): UPDATED additively.
- Ingestion / extraction / profile / parent-MAP / production Qdrant / Neo4j projections: NOT_AFFECTED (read-only; `project.assert_isolated`).
- Live proof on the production fleet (:7200): DEFERRED to the merge + one bounce (the checkpoint tag `restoration-integrated-2026-09-22` is the rollback).
