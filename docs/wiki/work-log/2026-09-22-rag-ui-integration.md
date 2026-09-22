---
change_id: RAG-UI-INTEGRATION
owner: orchestrator
date: 2026-09-22
status: complete
architecture_impact: "Existing HTTP and frontend integration only; no engine or storage redesign."
last_reviewed: 2026-09-22
---

# RAG UI integration repair

## Contract

Owner approved the diagnosis and explicitly authorized updating the exact selector assertion to FAST, HYBRID, GRAPH, WILDCARD, GNN. These modes must be selectable and comparable, the first chat stream must remain attached to its visible session, and corpus chat must request retrieval rather than silently accept a conversation-only compiler decision. GNN candidate routing stays isolated.

Smallest acceptance: actual frontend selection agrees with Compare validation; no requested mode is silently truncated; first-turn answer and receipt survive session creation; corpus-chat requests override a no-retrieval plan with a receipted decision while existing clients retain automatic routing.

## Changes

Admitted slices, in dependency order:
1. Orchestrator owner, existing compare-retrieval-v1 HTTP contract: mode list input, per-arm receipts output, no new persistence; reject unknown modes. Frontend mirrors the same public list. Rollback: mode-list/Compare edits.
2. Frontend session owner: initialize a session before Chat mounts; preserve the component while a stream runs. Existing localStorage persistence only. Rollback: App navigation edits.
3. Orchestrator chat boundary: additive explicit require_retrieval request flag, default false; reuse the deterministic evidence-route plan normalization with a truthful override rule. Frontend opts in. No new engine, provider or durable schema. Rollback: request flag and call-site edits.

Dependency reads: AGENTS.md, continuity current block and bootstrap, register 11.401/11.402, two newest work logs, architecture/dependencies.json, contract-dependencies.yaml, FRONTEND-V2-PLAN, current stream schema and mode dispatcher. GNN work log independently records the scratch remount defect and absent FAST selector.

## Proof

Baseline production HEAD 34c9d56 clean. Preflight, repo guard, wiki check and bundle integrity pass. Fleet read-only census reports healthy workers. Browser verification is blocked by an unavailable admin security check; no bypass attempted. All changes occur in isolated branch codex/rag-ui-integration.

Verification plan: run existing relevant deterministic suites unchanged; add focused frontend session and backend boundary regression coverage. Test doubles only control external responses in new unit tests; they do not establish live retrieval or quality. Verify build and repository guards. Stop once these implementation claims are proven; production merge/restart and browser proof must be separately reported.

## Rejected claims

- Engine rewrite, Settings completion and corpus reindexing do not repair the demonstrated integration defects.
- Successful mocked tests do not establish live corpus retrieval quality.

## Open contract gaps

Implementation and verification pending. Existing tests other than the owner-authorized exact selector assertion remain immutable. No merge, restart or remote push performed.

## Verification checkpoint

Implementation finished in this worktree. Changed: five-mode selector and authorized exact-list assertion; Compare accepts every requested distinct public mode without truncation and renders typed degradation as strings; session exists before Chat mounts; explicit require_retrieval flag on corpus-chat requests; existing plan normalization records corpus_chat:retrieval_required; FAST's VECTOR alias is explained in QueryTrace. The candidate engine and mode compositions are unchanged.

Added jsdom as a development dependency to exercise React session lifecycle with a delayed stream. No production dependency added. New test paths and this record are declared in the scaffold TREE; no repository guard weakened. Graft had no graph in this checkout, so callers were inspected with targeted source searches instead.

- Frontend focused tests: 5 passed, including both Chat navigation and New chat, first answer, receipt and saved session. Initial new-test setup failures were Node/jsdom storage wiring; corrected to use the document's actual jsdom storage. Build then caught a missing required engine field in the new alias fixture; fixture completed without weakening assertions. Final TypeScript and Vite build pass.
- Focused backend run: 22 passed (new boundary checks, existing evidence-route normalization, existing GNN isolation).
- Broader selected offline regression: 157 passed, 2 failed, 1 live test deselected because live browser inspection is blocked. Failures: test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes expects the old four-field subquery tuple and omits latent_bridge_ids; actual code passes the USER origin and latent_bridge_ids. test_query_receipts.py::test_all_three_query_handlers_and_read_surfaces_are_wired expects two literal chat receipt calls, but unchanged chat.py contains four. Neither original test was changed. These failures block a claim of a clean suite; no fix or test rewrite attempted.
- Real-store proof, one question across the five requested modes: registered Compare router invoked in-process from this worktree, using real cinema stores, embedding and reranking, no mocked retrieval. HTTP 200; FAST/HYBRID/GRAPH/WILDCARD each returned 15 evidence passages; GNN returned 12. GNN had 12 gnn_route candidates and zero other candidate lanes; every other mode had gnn_route=0. GRAPH returned evidence with a reported embedding delay (12214 ms against the existing engine deadline of 2.5 s). This is implementation smoke, not retrieval-quality qualification. Receipt summary: /private/tmp/rag-ui-real-compare.json. No request to the blocked production browser URL was used.
- Preflight and repo guard pass after declaring new files. Wiki check, bundle integrity and git diff --check pass. Production is still at 34c9d56; no production files, processes or corpus content changed.

Impact dispositions: QUERY_PLANNER and EVIDENCE_BOUNDARY_API UPDATED additively; PROFILE_SCOUT_WIRING and SUBQUERY_PROVENANCE NOT_AFFECTED (their logic is unchanged). CANDIDATE_ENGINE, PROFILE_YIELD_RECEIPT and RESOLUTION_STATE TESTED_UNCHANGED by the selected suites. RETRIEVAL_RECEIPT BLOCKED for a clean suite by the existing literal-call assertion; no receipt writer changed. ADAPTER_RUNTIME, EVIDENCE_PACKET and MCP_SURFACE NOT_AFFECTED because require_retrieval defaults false and the evidence-only normalization default remains identical. ACCEPTANCE DEFERRED: no production merge, fleet restart, fresh browser check or quality benchmark.

The user test-protection instruction requires stopping and reporting the original-test conflicts. Work stops here. Deployment also requires the repository's per-action production merge/restart approval; no remote push is proposed.

## Integration addendum (2026-09-22, Claude — branch ui/chat-restore)
Imported verbatim as commit `9823bbc` (this worktree had left it uncommitted). The block is lifted by attribution: both failing tests —
`test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` and
`test_query_receipts::test_all_three_query_handlers_and_read_surfaces_are_wired` — fail identically on untouched production `34c9d56`
(pre-existing; recorded in the GNN-RETRIEVAL-V1 attribution). Verified in the importing worktree with imports resolving there: 92 backend
tests passed; frontend 12 / 12 (incl. `chat-session.test.tsx`), `tsc` clean, build ok. One defect in the session fix was found and fixed in
the follow-up commit (CHAT-UI-RESTORE): blank sessions were persisted, so each reload of Chat minted another and, at the history cap, blanks
would evict real conversations — blanks are no longer persisted and "+ New chat" reuses an open blank.

