---
change_id: LANE-G-RECEIPT
owner: "@king"
date: 2026-09-25
status: complete
architecture_impact: "orchestrator only: ui._turn_receipt_extras keeps lane G's steering lines (seealso_fanout without its clock readings) on the chat receipt. Receipt-only; nothing reads it back. One bounce."
last_reviewed: 2026-09-25
---

# The chat receipt keeps lane G's steering lines

## Contract
- The live proof of the SEE ALSO blend (11.475) and DOC-STEER (11.482) needs a stored record of which document lines
  steered lane G. The owner's standing word (2026-09-24): "i decide for all your deficiencies found to be resolved".

## Changes
- `orchestrator/orchestrator/api/ui.py`, `_turn_receipt_extras`: when lane G ran (`seealso_fanout.enabled`), the receipt's
  `retrieval_trace.seealso_fanout` keeps the lane's record without its clock readings. That record holds the relational
  atoms, `blends` (line, document, and `kind` with the steer on), `blend_candidates`, `steer_kinds`, `steer_candidates`,
  `candidates` and `degraded`. `lane_ms` stays under `trace_ms.lanes`, as before.
- Test: `tests/determinism/test_turn_receipt_extras.py` (1 new).

## Proof
- Found READ (2026-09-25): `_TRACE_RECEIPT_KEYS` kept only the aspect keys, and `_LANE_TRACE_KEYS` only the lane times.
  So the 11.475 work-log's "Live confirmation … receipt: trace.seealso_fanout.blends" pointed at a field that was never
  stored. The stored field from now on is `query_receipts.meta.retrieval_trace.seealso_fanout`.
- Unit (worktree `pmv4-lane-g-receipt`, PYTHONPATH origins inside it, safe recipe): the impacted list (tests/contracts whole +
  14 determinism files) 377 tests vs production 376, the same 1 known failure
  (`test_chat_runtime::test_compiler_on_drives…`).

## Rejected claims
- "Add seealso_fanout to _TRACE_RECEIPT_KEYS": that would store `lane_ms` twice. The S1a rule keeps clock readings under
  `trace_ms` only, so the record is filtered with `_is_clock`.

## Open contract gaps
- EVIDENCE_BOUNDARY_API, PROFILE_SCOUT_WIRING (the paths of `ui.py`): UPDATED (a receipt key only).
- ACCEPTANCE, ADAPTER_RUNTIME, CANDIDATE_ENGINE, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE: TESTED_UNCHANGED (the list above).
- DEFERRED: `test_query_receipts.py` (hard-coded fleet connection), `test_adapter_product_discovery_loop.py` (writes the
  fleet database), `tests/integration/test_cross_domain_routing.py` (skip-gated).
