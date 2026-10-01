---
change_id: MCP-RETRIEVAL-MODES-V1
owner: "@king"
date: 2026-10-01
status: complete
status_note: "Both MCP servers offer the app's own retrieval: the five public modes (FAST, HYBRID, GRAPH, WILDCARD, GNN) on search / explore / answer, plus compare, deep research and models, from ONE shared module; polymath_search no longer reaches /retrieve's frozen LEGACY lane path; the four legacy tools are callable but no longer listed. Live after the owner's deploy."
architecture_impact: "shared/polymath_shared/mcp_retrieval.py (new: modes, request bodies, answer shaping); orchestrator/orchestrator/mcp_server.py + mcp_server/polymath_mcp.py (tools, hidden legacy tools, instructions); orchestrator/orchestrator/api/chat.py (attach_packet_rows: /chat/evidence evidence=true); orchestrator/orchestrator/api/ui.py (the evidence frame carries graph_facts); orchestrator/orchestrator/mcp_principals.py (knowledge.research scope + 3 policies); orchestrator/orchestrator/api/capabilities.py; orchestrator/orchestrator/api/web_settings.py (agent prompt line 2); mcp_server/CONNECTORS.md; tests."
last_reviewed: 2026-10-01
---

# MCP-RETRIEVAL-MODES-V1: the MCP tools offer the app's own retrieval

## Contract
- The owner, 2026-10-01, pasting how Claude (through the new connector) described Polymath's tools: "tools are stale and
  outdated. polymath has different types of retrieval". Then "go" on this plan: search / explore / answer take the app's
  modes, compare and deep research become tools, the legacy tools leave the list, the same on the local server.
- What was stale (read from the code): `polymath_search` sent NO mode, so `/retrieve` served it from
  `retrieval_modes.DEFAULT_MODE` = LEGACY, the frozen pre-R1A lane route the app no longer uses (Claude's "three lanes
  merged: reranked chunks, document summaries and graph facts" is that route). The server instructions named three modes
  ("FAST (cheap baseline), HYBRID, GRAPH"); WILDCARD and GNN were absent; there was no deep research and no compare tool;
  Server B's descriptions had drifted (VECTOR / ASK). `retrieve` still advertised `EXPLORE`.

## Changes
- **One module, both servers** (`shared/polymath_shared/mcp_retrieval.py`, pure): `RETRIEVAL_MODES` = the app's public modes
  with one line each (`MODE_GUIDE`), the curated reasoning styles, the deep research depths, the request body of every tool and
  how each answer is cut down for an agent. Server A (`orchestrator/orchestrator/mcp_server.py`) and Server B
  (`mcp_server/polymath_mcp.py`) build their tools and descriptions from it.
- **`polymath_search(query, corpus_id, mode, max_evidence)`**: the app's evidence route (`/chat/evidence`) with the query
  compiler OFF and Corpus Explore off — one query on the chosen mode's real engine — and `evidence: true`, so it still returns
  RETRIEVE-EVIDENCE-ROWS-V1 rows (chunk rows now carry the packet's `utility_role` / `ca4_grade`; GRAPH adds attested graph-fact
  rows), the WILDCARD lane when the mode has one, the executed mode and `degraded`. Never `/retrieve` (asserted).
- **`polymath_explore`**: the five modes described; the answer keeps the EvidencePacket, the executed mode, graph facts and the
  WILDCARD lane, and drops the runtime's full retrieval inventory and phase list (diagnostics, tens of KB).
- **`polymath_answer`**: + `reasoning` (the app's 13 curated styles) and `model` (a `/synthesizers` id); defaults send nothing new.
- **New**: `polymath_compare` (`/compare`: per mode latency, counts, documents, top rows; the chunks every mode found; how many
  only one mode found), `polymath_deep_research` (`/research/deep`'s event stream consumed to the end: the report, its
  citations, counts, stop reason, coverage; typed errors, `DEEP_RESEARCH_BUSY` = 409), `polymath_models`.
- **The orchestrator side**: the evidence frame's `result` carries the turn's `graph_facts` (≤ 40); `/chat/evidence` with
  `evidence: true` attaches rows built from the packet's own chunk ids and those facts (`chat.attach_packet_rows`, no second
  retrieval).
- **Legacy tools hidden, not removed**: `retrieve`, `retrieve_evidence`, `compile_plan`, `ask` (A) and `polymath_query`,
  `polymath_retrieve` (B) stay registered (an old caller's `tools/call` works) but `list_tools` leaves them out.
- **Permissions**: `polymath_compare` = `knowledge.search` on the friend's libraries; `polymath_deep_research` = a new scope
  `knowledge.research`, NOT in the friend profile (minutes of model calls on the owner's accounts; granted per friend);
  `polymath_models` = answer or research. `capabilities` lists the new tools, the hidden ones and the modes.
- Server instructions, the agent prompt (Settings, line 2) and `mcp_server/CONNECTORS.md` describe the modes and the new tools.
- Corrected in the plan before building: the app's chat retrieves over exactly ONE library in every mode
  (`mode_requires_single_corpus`), so the tools stay one library per call (the plan had said "one or more").

## Proof
- `tests/contracts/test_mcp_retrieval_modes.py` (12): the five modes = the UI's `PUBLIC_MODES` = `EXPOSED_MODES` minus LEGACY =
  `/compare`'s modes; styles = `CURATED_MODES`; depths = the engine's `PRESETS`; search sends exactly the evidence route with
  the compiler off for each of the five modes and never `/retrieve`; an unknown mode / style / depth is refused before any call;
  explore / answer / compare / models / deep research bodies and shapes; the event-stream parser; legacy tools callable over
  HTTP but never listed; every query tool and both servers' instructions describe the five modes; Server B sends the same
  requests.
- `tests/determinism/test_chat_runtime.py::test_the_evidence_route_gives_an_agent_graph_facts_and_contract_rows`: a real
  runtime GRAPH turn (stores faked) returns its graph facts, and the rows are built from the packet's chunk ids in order plus
  those facts; without `evidence` no rows.
- `tests/determinism/test_mcp_principals_gate.py` +1: a friend compares only its libraries; deep research is refused without
  `knowledge.research` and, once granted, streams through the gate (the real `_orch_events`) for its libraries only.
- Updated to the new contract: the parity test (legacy = registered, not listed), `test_mcp_server_v2` (the listed set), the
  gate test (the friend's listed set, the trusted context's path), the hosted acceptance fakes (`/chat/evidence`).
- **A sealed reproduction of CI on this tree** (both workflows' steps; throwaway Postgres with every migration; git and curl
  present as on a CI checkout; nothing else reachable): contracts **861 passed**, 5 skipped, 1 failed = the code-wiki check, stale
  until this slice's refresh (2,229 / 2,229 after it); determinism **3,285 passed**, 35 skipped, 2 failed:
  `test_knowledge_scope_echo` (a structural check that read `return run_chat(` in `_evidence_impl`; it now checks both handlers
  return run_chat's own scope-confirming reply and drop nothing — `_evidence_impl` has `_chat_impl`'s `out = run_chat(...)` /
  `return out` shape) and `test_wrong_credentials_fail_at_startup_with_a_code` (the container's own artifact: a database reached
  on its own 127.0.0.1 trusts the login; it passes on GitHub).
- In process (fakes, dead addresses): the MCP + web suites and the runtime test, 93 passed.
- Fail first on the deployed code (`3aa82e01`): `polymath_search` posts `/retrieve` there (the gate test's old expectation
  `{"path": "/retrieve", …}` passed against it), the shared module does not exist, and no compare / deep research / models tool
  is registered.
- The code wiki refreshed (257 units: the new module has its page; 6 flows regenerated); `verify.py --strict-anchors` 2,229 /
  2,229 on 342 pages.

## Contract impact (pre-commit)
- MCP_SURFACE [live] (`mcp_server.py`): UPDATED — the tools above; the legacy tools stay callable.
- EVIDENCE_BOUNDARY_API [live] (`api/chat.py`): UPDATED — `/chat/evidence` gains `graph_facts` and, only with `evidence: true`,
  `evidence_rows` / `evidence_contract`; every existing field and the packet are unchanged (additive).
- PROFILE_SCOUT_WIRING [live] (its spec names `api/ui.py`): NOT_AFFECTED — the one ui.py change adds `graph_facts` to the
  evidence frame's result; the profile scout's wiring is untouched.
- Transitive (ACCEPTANCE, ADAPTER_RUNTIME, CANDIDATE_ENGINE, EVIDENCE_PACKET, PROFILE_YIELD_RECEIPT, QUERY_PLANNER,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE): TESTED_UNCHANGED — every listed contracts / determinism file ran in
  the sealed reproduction above and passed. `tests/integration/test_cross_domain_routing.py`: DEFERRED — an integration test
  against the live stack, not part of CI; the change on its path is additive (one key, one opt-in add-on).

## Rejected claims
- "Search several libraries at once": the app's chat refuses it in every mode (`mode_requires_single_corpus`).

## Open contract gaps
- Deep research over MCP waits for the whole run (quick = minutes). A client with a shorter tool timeout loses the answer
  while the run finishes and is receipted; a start / status pair would remove that limit.
- `polymath_explore` and `polymath_answer` run the query compiler (one model call) as the app does; only search is model-free.
