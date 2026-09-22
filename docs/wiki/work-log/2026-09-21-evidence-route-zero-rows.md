---
change_id: EVIDENCE-ROUTE-ZERO-ROWS-DA
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "QUERY_PLANNER gains one pure function, plan_for_evidence_route; EVIDENCE_BOUNDARY_API (POST /chat/evidence) applies it before the skip-retrieval decision, so an evidence-only request whose need compiles to a no-retrieval plan retrieves the need verbatim (q0 PRIMARY) instead of returning an empty packet. The chat route, the compiler, the EvidencePacket contract and retrieval itself are unchanged. Not merged, not deployed."
last_reviewed: 2026-09-21
---

# Restoration delta D-a — why the governed evidence boundary returned 0 rows (diagnosed + smallest fix)

## Contract
Owner instruction 2026-09-21: before the canonical benchmark, identify the exact deterministic cause of the first real ecommerce run's zero-row evidence boundary; do not redesign retrieval; if it is a software defect make the smallest correction with a targeted regression. Branch `restoration/evidence-route-retrieval` (worktree `../pmv4-evidence-route`) stacked on `restoration/reporting` `31273f7`.

## Changes
- DIAGNOSIS ($0, read-only, `query_receipts.meta.chat_plan` of run `adr_c994b32a…`): 13 of 13 `/chat/evidence` calls (WILDCARD and GRAPH, all three loop rounds) stored `task_type: GENERAL_CONVERSATION`, `evidence_policy: conversation`, `retrieval_required: false`, `queries: []`, `retrieval_skipped: true`; `phase_ms.retrieve` ≈ `phase_ms.compile` (retrieval took ~10 ms = it never ran). The adapter's need is a STATEMENT (the seed; a hypothesis statement); the chat intent compiler reads a statement as conversation; `orchestrator/orchestrator/api/ui.py` (`_skip_retrieval = (not _plan.retrieval_required) and ui_mode != "ASK"`) then skips retrieval, and the evidence-only branch emits a VALID, EMPTY EvidencePacket — reported by the boundary as `retrieval_completed: true`, `n_evidence: 0`, explorer `fired: false, cause: OTHER` (its real reason: no PRIMARY). `/retrieve/plan` has no intent gate and returned 121 / 107 rows for the same needs and corpus — that is why it carried the run. Not query compilation failure, not corpus binding (`corpus_ids: [cinema]`, `scope: corpus`), not boundary filtering, not hydration, not projection state. The provider 429 on the first compiler lane (2 of 13 calls) is unrelated: the third lane answered and classified the same way as the 11 calls without it.
- FIX: `shared/polymath_shared/chat_plan.py` `plan_for_evidence_route(plan)` — pure: a plan that would not retrieve (or has no compiled query) becomes grounded QA on the need verbatim with a q0 PRIMARY (what `fallback_plan` searches), everything else the compiler produced kept, the override recorded on the plan receipt (`compiler.evidence_route_override`); a plan that already retrieves is returned as the same object. `api/ui.py`: one guarded call (`if req.evidence_only`) before the skip decision.
- Test: NEW `tests/determinism/test_chat_evidence_route.py` (6), built from run 5's stored plan.

## Proof
EXECUTED in the worktree, no database, no network: new file 6 / 6 + `test_chat_compiler.py` green (20 tests together); the DB-free tests of the impacted contracts green EXCEPT one PRE-EXISTING red, identical on untouched `production`: `test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` (the recorded stale pin — the subquery tuple gained `origin`; it does not touch the evidence route). `shared/`: UNIT_PROVEN. `orchestrator/api/ui.py`: IMPLEMENTED only (one call site; under pytest in a worktree `orchestrator` resolves to MAIN) — a static test pins where the call sits; the live proof is owed. Guards 0 / 0 / 0 / READY.

## Rejected claims
- "Retrieval was broken." It was never invoked on that route; `/retrieve/plan` worked throughout.
- "The 429 caused it." 11 of 13 calls had no provider failure and the same classification.
- "The benchmark's corpus path is now proven." Only after the merge + bounce and one live `/chat/evidence` probe with a statement need (rows > 0, `evidence_route_override` on the receipt).

## Open contract gaps
- QUERY_PLANNER: UPDATED (additive pure function). EVIDENCE_BOUNDARY_API: UPDATED (behaviour on a no-retrieval plan only). EVIDENCE_PACKET, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE, PROFILE_SCOUT_WIRING, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, CANDIDATE_ENGINE, ACCEPTANCE: TESTED_UNCHANGED / NOT_AFFECTED (no shape change; the plan receipt gains one optional `compiler` key). ADAPTER_RUNTIME, MCP_SURFACE: NOT_AFFECTED (callers unchanged).
- Owed live (one $0-provider-free? NO — a `/chat/evidence` call runs the compiler lane: it is a small spend and needs the owner's word): L14 a statement need returns rows > 0 with the override on its receipt.
- The benchmark stays BLOCKED until L14 is observed after the bounce.
