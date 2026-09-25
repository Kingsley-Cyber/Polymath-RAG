---
change_id: K1-KNOWLEDGE-SCOPE
owner: "@king"
date: 2026-09-25
status: complete
status_note: "Retrieval side done. The Postgres column (migration 0067) and the importer's implementation role land with C1 (gap K-03)."
architecture_impact: "shared (new polymath_shared/code/ package with scope.py; the profile / atom / pMAP / GNN searches take a scope; the receipt keeps knowledge_scope; Trail's evidence body) + orchestrator (every route and search site: FAST / HYBRID / GRAPH / WILDCARD / GNN, the profile scout, Corpus Explore, /retrieve, /retrieve/plan, /chat, /chat/evidence, /evidence, /ask, /compare) + workers (the adapter's legacy and plan bodies). A request without a scope is unchanged. Fence + one bounce."
last_reviewed: 2026-09-25
---

# K1: knowledge roles and retrieval scope

## Contract
- `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 6b; `CODE-RAG-IMPLEMENTATION-V1.md` R8 and §4 K1, with the 11.471
  amendment ("a rollback never widens a reference-only request"). Gaps K-01, K-02.
- The external Trail audit (11.484, REQ-10): K1 must hold on every planning / retrieval / fallback / graph path before any
  code is ingested.
- The owner, 2026-09-25: "go K1".

## Changes
- `shared/polymath_shared/code/scope.py` (new; the `code/` package starts here). It holds `RetrievalScope`, `ALL`,
  `REFERENCE_ONLY` and `parse_scope`, which refuses a malformed scope (`ScopeError`) and never reads it as "both roles".
  - `apply(filter)`: reference-only adds `must_not knowledge_role == "implementation"`, and existing conditions are never
    removed. A point without the field is reference (the column default), so no backfill is needed to stay correct.
  - Implementation-only adds `must knowledge_role == "implementation"`.
  - `sql_predicate` is ready for migration 0067.
  - `scope_kwargs`: the scope is passed only when it narrows the roles, so a request without one keeps its exact
    pre-K1 calls.
- The searches take `scope`:
  - `FastSearcher` (its one filter builder, `_filter_for`);
  - `entity_card_probe`, `profile_nominate`, `search_atoms`, `count_atoms`, `search_parent_maps`;
  - `gnn_parent_search` / `gnn_route.route`;
  - `retrieve._qdrant_search`, `hybrid._sparse_lexical_search` / `_lexical_search`, `ask._vector_object_ranks`.
- The routes parse the scope once and hand it to every search of the request:
  - `chat_retrieve_v2` / `chat_retrieve_mode` (every mode, the graph attach, the WILDCARD sweep, the GNN route);
  - `fast_retrieve`, `hybrid_fast_retrieve`, `wildcard_retrieve`, `graph_retrieve`;
  - the chat runtime, which parses the scope eagerly (422 before the first frame): the profile scout, Corpus Explore
    and the compiler call;
  - `/retrieve`, `/retrieve/plan`, `/chat` + `/chat/evidence` (`ChatRequest.scope` mapped by `stream_request`), `/evidence`,
    `/ask`, `/compare`.
- Trail: `evidence_boundary.TRAIL_SCOPE = {"roles": ["reference"]}`. It goes on the evidence-route body (now five fields),
  the legacy `/retrieve` call, the plan lane and the graph fallback, so a rollback of the surface never widens it.
- Receipts: the recorder (`query_receipts.record_query_receipt`, the one writer behind /retrieve, /ask, /chat,
  /chat/evidence and the chat stream) keeps the request's scope as `meta.knowledge_scope`, on ok and error receipts alike;
  a malformed one is kept as `{"invalid": true}`. It is read from the request only: a response cannot set or widen it
  (it is not on the response whitelist). Without a scope, receipts are unchanged.
- Tests: `tests/determinism/test_knowledge_scope.py` (20):
  - the contract, and the refusals;
  - every search applies the scope;
  - a caller pin: every runtime call of a scoped search in orchestrator / shared / workers / control / mcp_server
    passes the request scope, so a forgotten caller fails CI;
  - Trail bodies, request models, receipts;
  - the turn reads its scope from the request only, never from the plan.
- Four contract pins updated to the new exact Trail bodies (with `scope`), still exact:
  `test_adapter_evidence_boundary::test_request_body_is_exactly_five_fields` and three in
  `tests/contracts/test_adapter_worker_evidence_surface.py`. The pin on the rollback path now includes the scope on
  purpose: that is the fail-closed rule.

## Proof
- Unit (worktree `pmv4-k1`, PYTHONPATH origins inside it, safe recipe): `test_knowledge_scope.py` 20 / 20. The impacted
  list is tests/contracts whole + 33 determinism files (the contract map's TESTS TO RUN plus every test touching a changed
  function). The branch ran 572 tests against production's 552; the only failure is the known one on both
  (`test_chat_runtime::test_compiler_on…`).
- Cost (EXECUTED, read-only, live Qdrant): the role clause on the 163k-point children collection is 19–21 ms → 25 ms
  median per search. The collection has no payload index at all; only reference-only requests (Trail) pay it.
- End-to-end replay (EXECUTED, $0, `experiments/k1-knowledge-scope-2026-09-25/replay.py` → `replay.json`): in-process
  from the worktree against the live stores and the local embedder / reranker. The 3 stored RETRIEVAL-PATHWAYS-5Q
  questions × FAST / HYBRID / GRAPH / WILDCARD, each run without a scope and with Trail's reference-only scope. A recorder
  on the Qdrant client kept the filter of every search and count that reached Qdrant.
  - Scoping: in all 12 reference-only runs every search carried the role clause (FAST 22 of 23, HYBRID 65–69 of 66–70,
    GRAPH 79–83 of 80–84, WILDCARD 93–95 of 94–96). The one left out in each run is the corpus readiness check
    (`fast.py:290`, a whole-collection count that returns a number, never passages; readiness does not depend on the
    roles asked for). In all 12 runs without a scope, no search carried the clause. The profile scout: 6 of 6 scoped
    with the scope, 0 of 6 without.
  - Evidence: identical in 10 of 12 (all FAST and HYBRID; GRAPH and WILDCARD on 2 of the 3 questions). Graph facts:
    identical in all 12.
  - The 2 differences (GRAPH 2 of 15 passages, WILDCARD 1 of 15, both on the "weighty" question, with the same number of
    searches, 84 / 84 and 94 / 94) did not come back: `noise_check.py` → `noise_check.json` ran both modes twice without
    and twice with the scope, and all 8 runs matched the first no-scope run (0 of 15 changed). With the raw check (the
    clause changed 0 of 30 result lists), they were a one-off in that run, not the scope.
  - Time: the reference run always ran second (warmer caches), so the per-run wall times are not a cost comparison; the
    cost is the per-search figure above.
  - $0: `llm_provider_attempts` held 9,639 rows before and after both scripts (no model call).
- Live check (`live_check.py`, $0: four /retrieve GRAPH calls, their receipts and orchestrator.log) — control run on the
  pre-K1 fleet (2026-09-25 02:57 MDT): exit 1 as it must be. The reference-only, malformed and implementation-only calls
  all answered 200 with the same 15 unscoped passages and no `knowledge_scope` on their receipts (the old request models
  drop the unknown field), so the check cannot pass without K1 live. That run also found gap K-04 (below). The run after
  the merge + bounce is the LIVE_PATH proof.
- The receipt change (tests in the same worktree): `test_knowledge_scope.py`, `test_query_receipts.py` (its one fleet
  database test deselected), `test_qualify_lane_and_query_receipts.py`, `test_chat_runtime.py`, `test_chat_funnel.py`,
  `test_chat_evidence_route.py`, `test_adapter_evidence_boundary.py`: all pass except `test_compiler_on…` (known) and
  `test_query_receipts::test_all_three_query_handlers_and_read_surfaces_are_wired`, which fails on production too: it pins
  2 chat receipt writers, and production has had 4 since /chat/evidence (that file is normally excluded, so the stale pin
  went unseen). tests/contracts whole: 145 / 145.

## Rejected claims
- "Gate enforcement behind `POLYMATH_KNOWLEDGE_SCOPE`": a switch that turns enforcement off is a rollback that widens a
  reference-only request, which the 11.471 amendment forbids. Enforcement of an explicit scope is unconditional; the
  no-scope default is today's behaviour.
- "Backfill `knowledge_role=reference` on every existing point first": with `must_not implementation`, a missing field
  already means reference; the backfill buys only explicitness.
- "Thread the scope through a context variable": the lanes run on thread pools that do not inherit context variables, so
  the scope would be silently lost (fail open). The scope is an explicit argument, and the caller pin keeps it that way.
- "Update every test double to accept `scope`": passing the scope only when it narrows keeps the no-scope calls exactly as
  they were. A narrowing scope reaching a callee that cannot take it fails loudly (TypeError), never silently.

## Open contract gaps
- ADAPTER_RUNTIME, EVIDENCE_BOUNDARY_API, PROFILE_ATOM, PROFILE_PROJECTION, PROFILE_SCOUT_WIRING, CANDIDATE_ENGINE:
  UPDATED (an optional scope; unchanged without one; the Trail body gains `scope`).
- ACCEPTANCE, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_SCOUT_FUSION / INPUT / OUTPUT, PROFILE_YIELD_RECEIPT, QUERY_PLANNER,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE: TESTED_UNCHANGED (the impacted list above).
- DEFERRED: `test_query_receipts.py` (hard-coded fleet connection), `test_adapter_product_discovery_loop.py` (writes the
  fleet database), the integration files (skip-gated / not collectable under the worktree PYTHONPATH).
- K-03 (OPEN, C1): Postgres-side reads cannot filter by role until migration 0067. Safe until then, because no
  implementation document can exist without that column.
- K-04 (OPEN, K1b before C1's importer): pre-K1 code ignores `scope` without an error and Trail does not check that its
  scope was applied, so a rollback of the orchestrator to a pre-K1 commit would widen Trail's requests once implementation
  material exists. Fix: echo the applied scope on every scoped response; Trail refuses a response without the exact echo.
