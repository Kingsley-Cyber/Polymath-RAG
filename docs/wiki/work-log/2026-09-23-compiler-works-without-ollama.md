---
change_id: COMPILER-WORKS-WITHOUT-OLLAMA
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "orchestrator + shared code on branch fix/compiler-works-without-ollama (NOT merged, NOT live). The chat compiler and the bridge / Corpus-Explore generator keep working when any one provider, Ollama included, is down, slow or unusable. Gemma stays the go-to."
last_reviewed: 2026-09-23
---

# The chat compiler and bridges work without Ollama; gemma stays the go-to

## Contract
Owner, 2026-09-23: "I just want this stuff to work… Let's assume my Ollama subscription is complete now: the repo doesn't
work. I don't mind gemma being the go-to, but it should work regardless."

Before this change, if Ollama stopped:
- each session had a hashed home lane, so some started on a slow lane;
- a late answer (`budget_exceeded`) or an unusable plan never failed over and never cooled the lane, so those sessions got
  the weak fallback plan turn after turn;
- the bridge and Corpus-Explore generators called Ollama directly, with no backup.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - `_COMPILER_PREFERRED_LANE` (env `POLYMATH_CHAT_COMPILER_PREFERRED_LANE`, default `compiler_ollama_gemma`) is tried
    first by every session. While it is cooling (down or slow), the backups go first. An empty value restores the old
    hash ring.
  - NEW `_run_compiler_lanes`:
    - it returns the first real plan;
    - `transport:*` and `budget_exceeded:*` fail over AND cool the lane (for 120 s);
    - `invalid_json` / `invalid_plan:*` fail over without cooling, since another model may plan the question;
    - when every attempt fails, the fallback plan is returned with the FIRST failure recorded.
  - `_compile_chat_plan` uses it.
  - NEW `_bridge_llm` + `_bridge_cloud_clients`: Ollama first. When it is unreachable, errors or answers empty, the
    non-Ollama compiler lanes are tried in turn, with the owner's thinking rule (BRIDGE role) and plain-text output. Both the
    bridge compiler and Corpus Explore now call `_bridge_llm`.
  - `_COMPILER_HTTP_TIMEOUT_S` default 6.0 → 8.0 s.
- `shared/polymath_shared/chat_plan.py`: `COMPILER_HARD_BUDGET_S` default 6.0 → 8.0 s. The backup lanes plan in 3.5–5.3 s
  with thinking disabled (11.423), too close to 6 s.
- NEW `tests/determinism/test_compiler_resilience.py`, 7 tests:
  - gemma is first, and last while it is down;
  - late or unreachable → next lane + cool-down;
  - invalid plan → another model, no cool-down;
  - every lane failed → the fallback plan still runs;
  - bridges come from a cloud lane when Ollama is down;
  - bridges use Ollama first while it works;
  - the limits are 8 s.

## Proof
- **Red first:** all 7 new tests failed on `be37537`; all pass after the change.
- **Suites, in the worktree without `POLYMATH_PG_DSN`:** test_compiler_resilience, test_chat_hygiene, test_chat_runtime,
  test_bridge_integration, test_bridge_compiler, test_chat_evidence_route, test_latent_selection, test_reasoning_policy,
  test_chat_compiler, test_corpus_activation, test_corpus_explore and test_corpus_explore_firing: 152 passed, 1 failed. The
  failure is the known pre-existing `test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes`,
  which fails identically on production.
- **EXECUTED live simulation of the owner's case:** the real `_compile_chat_plan` in-process, branch code, `.env` flags on,
  the Ollama URL pointed at a dead port for BOTH the gemma compiler lane and the bridge generator.
  - Q1: gemma `ConnectError` → cooled → attempt 3 on qwen → a real plan with 7 queries (USER / PROFILE / BRIDGE) and bridges
    3 generated / 3 admitted through the cloud fallback; 26.5 s end to end (the first turn after the outage pays for the
    failed tries).
  - Q2: gemma cooling → deepseek on attempt 1 → a real plan (8 queries) and bridges 3 / 3; 11.9 s.
- Proof level: UNIT_PROVEN + a live simulation on the branch. Not merged, not deployed.

## Rejected claims
- "Raise the HTTP timeout alone": the 6 s hard budget would still discard a late plan. Both limits move together, to 8 s.
- "Retrying an invalid plan is pointless": that holds on the SAME lane. Another model often plans the question (DeepSeek
  returned `invalid_plan` once where Qwen planned the same question).
- "Without Ollama the repo stops working": EXECUTED otherwise, above.

## Open contract gaps
The contract-impact hook flagged EVIDENCE_BOUNDARY_API, PROFILE_SCOUT_WIRING, QUERY_PLANNER and SUBQUERY_PROVENANCE, plus
their downstream contracts. The impacted suites were run in the worktree without `POLYMATH_PG_DSN`:
- the compiler / bridge / evidence-route set above: 152 passed, 1 pre-existing failure;
- test_profile_scout, test_subquery_provenance, test_candidate_engine, test_evidence_packet, test_evidence_resolution,
  test_profile_yield, test_query_receipts, test_mcp_server_v2, test_chat_funnel, test_chat_retrieval_v2 and
  test_evidence_packet_contract: 138 passed, 1 failed. The failure is the known pre-existing
  `test_query_receipts::test_all_three_query_handlers_and_read_surfaces_are_wired`, which fails identically on production.

Dispositions:
- UPDATED: QUERY_PLANNER (the hard budget), the chat compiler lane policy, and the bridge / Corpus-Explore generator
  transport (tests added).
- TESTED_UNCHANGED: EVIDENCE_BOUNDARY_API (test_chat_evidence_route green), PROFILE_SCOUT_WIRING, SUBQUERY_PROVENANCE,
  CANDIDATE_ENGINE, EVIDENCE_PACKET, RETRIEVAL_RECEIPT, RESOLUTION_STATE, PROFILE_YIELD_RECEIPT, MCP_SURFACE.
- DEFERRED: ACCEPTANCE (the integration suite skips on production) and ADAPTER_RUNTIME (shares the fleet Postgres; the
  isolation rule).
- The chat compiler lane policy: UPDATED (tests added).
- The bridge / Corpus-Explore generator transport: UPDATED (tests added).
- QUERY_PLANNER (`chat_plan` hard budget): UPDATED. The compiler suites pass.
- Chat synthesis with an Ollama model the owner picks in the UI: NOT_AFFECTED. The default synthesizer is Alibaba DeepSeek.
- BLOCKED: merge + bounce, on the owner's word.
