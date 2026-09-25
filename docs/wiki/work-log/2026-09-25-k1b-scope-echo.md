---
change_id: K1B-SCOPE-ECHO
owner: "@king"
date: 2026-09-25
status: complete
status_note: "Every scoped JSON reply confirms its scope; Trail refuses an unconfirmed reply on every path (gap K-04 closed)."
architecture_impact: "shared (code/scope.py: echo_scope / echo_matches; adapter/evidence_boundary.py: scope_violation) + orchestrator (every route whose request takes a scope confirms it: /retrieve, /retrieve/plan, run_chat behind /chat and /chat/evidence, /evidence, /ask, /compare) + workers (adapter_step_worker._orch_post refuses an unconfirmed reply with ScopeNotConfirmed). A request without a scope is unchanged. One bounce: the orchestrator and adapter_step restart together (the fence restarts neither)."
last_reviewed: 2026-09-25
---

# K1b: the scope confirmation and Trail's check (gap K-04)

## Contract
- Gap K-04, found by the K1 live check's control run (11.485–11.486): pre-K1 code drops `scope` silently (200, unscoped
  evidence), and Trail never checked that its scope was applied. Once implementation material exists, a rollback of the
  orchestrator to a pre-K1 commit (the recovery tags are pre-K1) would widen Trail's reference-only requests: the 11.471
  fail-closed rule, broken by a code rollback instead of a switch.
- `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 6c (K1b), before C1's importer.
- The owner, 2026-09-25: "go K1b".

## Changes
- `shared/polymath_shared/code/scope.py`:
  - `ECHO_KEY = "knowledge_scope"`;
  - `echo_scope(out, requested)` (server): the reply confirms the parsed scope; a request without a scope gets its reply
    unchanged;
  - `echo_matches(sent, response)` (consumer): exact; a missing, malformed or different confirmation (a widened one
    included) is False.
- `shared/polymath_shared/adapter/evidence_boundary.py`: `scope_violation(body, resp)`, which returns None for an
  unscoped call or an exact confirmation, and the reason otherwise.
- `workers/workers/adapter_step_worker.py`: `_orch_post` is Trail's one outbound function (already the allow-list gate).
  It now raises `ScopeNotConfirmed` (a subclass of `OrchRejected`) when a scoped call comes back unconfirmed.
  - Like any contract defect this is never a fallback. The step fails (`STEP_EXECUTOR_ERROR`) instead of reasoning over
    possibly unscoped evidence.
  - One place covers every path: the evidence route, its unavailable-fallback, the kill-switch legacy lane, the plan
    lane and the graph union.
- The orchestrator: every route whose request model takes a `scope` returns through `echo_scope(…, req.scope)`:
  - /retrieve (the receipt wrapper) and /retrieve/plan;
  - `run_chat`, the one reply builder behind /chat and /chat/evidence;
  - /evidence (three returns), /ask (the receipt wrapper) and /compare.
  - The key sits at the top level, beside any EvidencePacket, never inside it: the packet schema is unchanged.
- Not confirmed: the SSE stream (`chat_stream`). It is not a JSON reply, no stream client sends a scope (the UI never
  does), and its receipt keeps the scope (K1). A future scoped stream client needs the confirmation on the answer frame,
  which `chat_events` builds in four places.
- Tests: `tests/determinism/test_knowledge_scope_echo.py` (17):
  - the helpers and `scope_violation`;
  - an AST pin: every route whose request model has `scope` returns `echo_scope(…, req.scope)`. The chat routes pass
    through `run_chat`, which is pinned too; the stream is exempt by name. A new scoped route that forgets the
    confirmation fails CI;
  - behaviour of /retrieve, /retrieve/plan (the scope also reaches every reformulation) and `run_chat`;
  - on the wire: a real local HTTP stand-in plays a pre-K1 orchestrator (200, no confirmation), a K1b one and a widening
    one. Every Trail path runs through the REAL `_orch_post`, and an unconfirmed reply is refused on each.

## Proof
- Unit: `test_knowledge_scope_echo.py` 17 / 17. Mutation check: with the worker's refusal switched off and
  /retrieve/plan's confirmation dropped, 10 of the 17 fail (the route pin, the plan behaviour and all 8 refusal tests);
  restored, 17 / 17.
- Impacted list (worktree `pmv4-k1b`, its PYTHONPATH origins verified, the safe recipe): tests/contracts whole + 36
  determinism files (the contract map's TESTS TO RUN, plus every test touching the edited routes or the worker). The
  branch ran 579 tests against production's 562 (the 17 new ones). Both runs had the same 2 failures, known and
  pre-existing (`test_chat_runtime::test_compiler_on…`, `test_query_receipts::test_all_three_query_handlers…`); the
  branch added none.
- CI on the pushed K1 commit `63816479`: contracts, agent-preflight and repo-governance green; determinism 13 failures,
  all 13 also in the previous run's 14.
- Live control (EXECUTED, $0, 2026-09-25 04:48 MDT, `live_check.py --control` → `live_check_control.json`): the branch's
  Trail code against the live K1 fleet, which does not confirm. /retrieve and /retrieve/plan answered 200 with no
  confirmation, and `_orch_post` refused both of Trail's lanes (`ScopeNotConfirmed`). No scope: unchanged (15 passages).
  This is what a rollback looks like from Trail's side, and it fails closed. It is also why the merge and the bounce must
  run back to back.
- LIVE (EXECUTED 2026-09-25 04:57 MDT, register 11.488): the owner's Run button merged `63816479..6c52bc1c` and bounced
  (READY after ~55 s: 26 workers / 13 types / ONE bundle `acc8f3e1c16f`; the three chat / graph flags unchanged).
  `live_check.py` exit 0 (`live_check.json`), with the deployed worker file loaded from production:
  - /retrieve without a scope → 200, 15 passages, no confirmation (unchanged);
  - /retrieve with Trail's scope → 200, 15 passages, confirmed `{"roles": ["reference"]}`;
  - /retrieve/plan with Trail's scope → 200, 119 rows, confirmed;
  - Trail's `_orch_post` accepted the legacy lane (48 rows) and the plan lane (110 rows);
  - no Traceback in orchestrator.log while the calls ran.
  Guards 0 on production after the merge; bundle_integrity READY. Seen in passing: two identical /retrieve/plan calls a
  few seconds apart returned 119 and 110 rows (123 in the control run). That is the EXPLORE lanes' run-to-run variance,
  already present before K1b, and not a scope effect.

## Rejected claims
- "Check the confirmation in `check_response`": that covers only the evidence route and leaves the legacy, plan and graph
  lanes open. The one outbound function covers every path, present and future.
- "Put the confirmation inside the EvidencePacket": the packet is a versioned contract with its own schema. The
  confirmation is about the call, so it sits beside the packet, like `synthesis_performed`.
- "Fall back to the legacy lane when the evidence route does not confirm": a server that ignores scope ignores it on every
  route. The refusal is final (the `OrchRejected` rule).
- "Confirm from inside each search": the scope comes from the request only, is parsed once, and reaches every search
  (the K1 caller pin). Confirming the parsed request scope is what a K1-aware server can truthfully say, and the purpose
  is to detect a server that ignores the field.
- "Confirm on the SSE stream now": no consumer needs it, and it would mean four frame builders for no reader.

## Open contract gaps
- ADAPTER_RUNTIME: UPDATED (the worker refuses an unconfirmed reply). EVIDENCE_BOUNDARY_API: UPDATED (/chat/evidence
  confirms a scoped request at the top level; `scope_violation`). PROFILE_SCOUT_WIRING: NOT_AFFECTED (it is listed because
  `ui.py` changed; only `run_chat`'s return changed).
- ACCEPTANCE, CANDIDATE_ENGINE, EVIDENCE_PACKET (the packet and its schema are unchanged), MCP_SURFACE,
  PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE: TESTED_UNCHANGED (the
  impacted list below).
- DEFERRED: `test_adapter_product_discovery_loop.py` and `test_adapter_worker_registration.py` (both write the fleet
  database), `test_query_receipts.py`'s one fleet-database test, `tests/integration/test_cross_domain_routing.py`.
- K-03 (OPEN, C1): Postgres-side role filtering, unchanged by this slice.
