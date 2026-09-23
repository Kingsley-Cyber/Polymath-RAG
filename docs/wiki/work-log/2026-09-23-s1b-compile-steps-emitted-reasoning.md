---
change_id: DOCUMENT-RAG-S1B-COMPILE-STEPS-EMITTED-REASONING
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "orchestrator + shared client code on branch fix/document-rag-s1-receipts (stacked on E7 + S1a; NOT merged, NOT live). The compile phase is timed step by step (`chat_plan.compiler.compile_ms`, plus a `scope` phase mark). Every model call on the chat path now receipts the reasoning settings it actually sent: the compiler (`chat_plan.compiler.reasoning`), the bridge / Corpus-Explore generator (`bridge_expansion.route`, `corpus_explore_expansion.route`) and synthesis (`generation.reasoning`). Receipt-only: no request, route, ranking or answer changes. `last_reasoning` is a runtime attribute on the compiler / bridge clients only; extraction clients never carry a reasoning role, so extraction and its contract hash are unchanged."
last_reviewed: 2026-09-23
---

# S1b: the compile phase is timed step by step; every chat model call receipts the reasoning it sent

## Contract
- Plan of record `docs/wiki/plans/DOCUMENT-RAG-COMPLETION-V1.md` Part F, "First (S1–S2)": compile sub-steps and the
  emitted reasoning settings. This is S1's second half (S1a, register 11.431, kept what was already measured).
- Owner rule (2026-09-23): thinking off where possible, otherwise ≤ 100; gpt-oss low. Nothing on the receipt proved what
  each call actually sent.
- The policy's JSONL wire receipt (`/private/tmp/polymath_fleet/reasoning_policy.jsonl`) is not joined to a turn.
- What was missing (READ, 2026-09-23):
  - `phase_ms.compile` is a cumulative mark that includes scope resolution.
  - Inside `_compile_chat_plan`, only the scout (`scout.ms`), the winning compiler attempt (`wall_ms`) and bridges
    (`bridge_expansion.latency_ms`) were timed. The last owner-style receipt had 14.5 s of compile with about 10 s
    unattributed.
  - The compiler client computed the applied reasoning params (`apply_chat_completions` returns them) and logged them, but
    never returned them to the plan.
  - Synthesis via LiteLLM computed `_rb_applied` and dropped it. The Ollama path yielded no `finish` at all.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - `_compile_chat_plan`: NEW `_timed(name, fn, …)` records the wall time of scout, endpoints, lanes (every compiler
    attempt), profile_expansion, bridges, provenance, constraints and explorer, plus a total.
    `plan.compiler["compile_ms"]` holds them on every path (fallbacks included).
  - `_compile_one`: `one.compiler["reasoning"]` = the winning attempt client's `last_reasoning`.
  - The stream generator: `_mark("scope")` after scope resolution, so the scope share of the compile mark can be
    subtracted.
  - `_bridge_llm(…, route=None)` fills `route` with the route that answered:
    - Ollama: `{"route": "ollama", "model": <bridge model>, "reasoning": {"surface": "ollama", "think": false}}`;
    - cloud: the lane's `endpoint_name` and `model`, and the client's `last_reasoning`.
  - `_add_bridge_expansion` and `_add_corpus_explore_expansion` store it as `route` on their receipts.
  - `_litellm_generate`: `finish.reasoning` = the policy's applied params. It is added only when the policy applied
    something, so with the policy off the finish dict is byte-identical (the generation-bound test proves it).
  - `_ollama_generate_inner`: `finish.reasoning` = `{"surface": "ollama", "think": <the value sent>}`.
  - `_ollama_stream_plain_inner`: `{"surface": "ollama", "think": null, "think_rejected": true}`.
- `shared/polymath_shared/llm_extraction/client.py`: `_chat` keeps `self.last_reasoning` = what `apply_chat_completions`
  put on the payload. It is set only for clients that carry a `reasoning_role` (compiler, bridge).
- Tests:
  - NEW `tests/determinism/test_compile_steps_and_emitted_reasoning.py` (8 tests). An autouse fixture sends the policy's
    JSONL wire receipt to `tmp_path`, so tests never write the fleet's file.
    - The compiler client's `last_reasoning` equals what went on the wire.
    - Every compile step is timed (stubbed slow scout / constraints show up).
    - The lanes are timed, and the winning attempt's plan carries the wire reasoning (a real client, a faked
      `httpx.post`).
    - The bridge route (Ollama, and the cloud fallback) with its reasoning.
    - The bridge-expansion receipt names the route.
    - LiteLLM synthesis `finish.reasoning` equals the sent `thinking`.
    - Ollama synthesis `finish.reasoning.think` equals the sent `think`.
    - A rejected `think` is receipted.
  - `test_chat_runtime.py` +1: `phase_ms` carries `scope` (≤ `retrieve`).

## Proof
- **Red first:** all 8 new tests failed on `629622e` (no `last_reasoning`; KeyError `compile_ms` / `route` / `reasoning`;
  TypeError: `_bridge_llm` had no `route`; no `finish` from Ollama).
- **The scope-mark test** was written after its one-line change. It was shown red on the S1a commit (throwaway worktree:
  `'scope' not in phase_ms`) and green here.
- **Neighbour suites** (the new file, test_chat_generation_bound, test_compiler_resilience, test_reasoning_policy,
  test_corpus_explore_firing, test_corpus_explore): 76 passed.
- **Lint:** no new ruff finding on the touched files versus `629622e`. An S110 on a try/except/pass became a total
  `isinstance` guard. The pre-existing I001 in client.py went away. The new test file is clean.
- **Broad run (EXECUTED):** 50 suites (contract_impact's list, the chat / compiler / bridge / reasoning suites, and every
  suite that touches `LLMExtractionClient`), with the worktree PYTHONPATH, no `.env` and `-k "not test_live_"`.
  - Branch: 611 passed, 4 failed, 1 skipped, 9 deselected.
  - Base = the S1a commit `629622e` (throwaway detached worktree): 602 passed, the SAME 4 failed.
  - The 4: the 3 known pre-existing failures, plus `test_synthesis_attempt_telemetry::test_the_bound_retry_records_BOTH_attempts`
    (`PoolTimeout`: a DB-backed ledger with no `.env`). That file passes alone on this branch, 21 / 21.
  - The +9 are the new tests (8 + the scope mark).

## Rejected claims
- "The reasoning policy's JSONL is enough proof": it is not joined to a turn, and it lives in `/private/tmp` (a reboot
  wipes it). The turn's own receipt now carries the settings.
- "`wall_ms` is the compiler's time": it is the winning attempt's time. `compile_ms.lanes` includes every attempt
  (failed / late lanes), which is part of what was unattributed.

## Open contract gaps
- Contract impact (`scripts/contract_impact.py --files …`, EXECUTED):
  - `EVIDENCE_BOUNDARY_API`: UPDATED (additive receipt fields `compile_ms`, `reasoning`, `route`, `generation.reasoning`,
    `phase_ms.scope`).
  - `QUERY_PLANNER`: UPDATED (`plan.compiler` gains `compile_ms` / `reasoning`; the plan fields are unchanged).
  - `PROFILE_SCOUT_WIRING` and the transitive `ACCEPTANCE`, `ADAPTER_RUNTIME`, `CANDIDATE_ENGINE`, `EVIDENCE_PACKET`,
    `MCP_SURFACE`, `PROFILE_YIELD_RECEIPT`, `RESOLUTION_STATE`, `RETRIEVAL_RECEIPT`, `SUBQUERY_PROVENANCE`:
    TESTED_UNCHANGED.
  - The extraction client (`client.py`): TESTED_UNCHANGED for extraction. `last_reasoning` is set only under a
    `reasoning_role`, which extraction clients never carry; the client suites are in the broad run.
  - DEFERRED: `tests/integration/test_cross_domain_routing.py` (not collectable under the worktree PYTHONPATH;
    skip-gated).
- Per-attempt reasoning for FAILED compiler attempts is not receipted, only the winning attempt's. `first_failure` still
  names the failure.
- S2 (E6): the two $0 traces use these receipts; D6 (latency budgets) is set from them.
- BLOCKED: merge + bounce, on the owner's word. LIVE proof = the next owner turn's receipt carries `compile_ms`,
  `reasoning`, `route` and `generation.reasoning` ($0).
