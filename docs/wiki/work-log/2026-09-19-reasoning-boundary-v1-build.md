---
change_id: REASONING-BOUNDARY-V1-BUILD
owner: "@king"
date: 2026-09-19
status: in-progress
architecture_impact: "Living build log for REASONING-BOUNDARY-V1 RB1->RB4. NEW pure shared modules (evidence_packet, reasoning_policy) + live wiring (chat_events short-circuit + /chat/evidence; reasoning policy on _litellm_generate/_run_reviewer/compiler; MCP search/explore/answer on both servers). Additive; the human /chat path stays byte-identical when evidence_only is unset; bridge + extraction reasoning untouched."
last_reviewed: 2026-09-19
---

## Contract
Execute REASONING-BOUNDARY-V1 per `docs/wiki/plans/REASONING-BOUNDARY-V1.md` (admitted, register 11.340).
LOCKED: evidence boundary = short-circuit chat before synthesis -> versioned bounded EvidencePacket (NO
synthesis LLM, NO reviewer); reasoning = semantic role->budget policy (reasoning ceiling SEPARATE from output
floor) via API-surface-aware provider adapters, applied to chat-synthesis + reviewer + chat-compiler; bridge
(think:false) + document-extraction (contract-hash-locked) untouched. shared/ is worktree-unit-provable;
ui.py/mcp_server/compare_review/client are live-only (editable-.pth).

## Changes
- **RB1 shared (evidence contract, pure).** NEW `shared/polymath_shared/evidence_packet.py`: `EvidencePacket`
  + `EvidenceItem` + `build_evidence_packet(*, q0, retrieval_mode, plan_queries, evidence_rows, ca4_grades,
  receipts, corpus_explorer_requested/used, max_rows, max_text)` — tolerant pure mapper (internal chat bundle
  -> bounded packet: utility_role DIRECT/COMPLEMENTARY/DIVERGENT [C5 seat > synthesis_role], ca4_grade
  DIRECT/PARTIAL/RELATED, c4_valid, provenance{origin/inspired_by/derived_from}, receipts bounded to the 4
  known keys). `synthesis_performed=false` first-class. Row/text/receipt bounded.
- **RB2 shared (reasoning policy, pure).** NEW `shared/polymath_shared/reasoning_policy.py`: `RolePolicy` +
  `ROLE_POLICIES` (BRIDGE/STRUCTURED_COMPILER/REVIEWER/CHAT_SYNTHESIS) + `reasoning_params(role, model,
  api_surface) -> {top_level, extra_body, max_output_tokens}`. Provider adapter: Qwen Chat-Completions
  `thinking_budget=300`+`preserve_thinking=false` (Responses -> disable; NEVER `reasoning_effort`+budget),
  Claude `effort=low`, Gemini `thinking_level=low`, DeepSeek `thinking:disabled`, OpenAI `reasoning_effort=low`.
  Output budget SEPARATE from the reasoning ceiling. Env overrides `POLYMATH_REASONING_MAX_<ROLE>` /
  `POLYMATH_OUTPUT_MAX_<ROLE>`.

- **RB1-live (ui.py + chat.py; live-only).** `chat_events` short-circuit BEFORE the synth branch
  (`ui.py`): when `req.evidence_only`, build the packet from the already-computed bundle (`fast['evidence']`,
  `_grades_by_chunk` CA4, `_plan`, compiler receipts) and emit `kind:"evidence"` (`synthesis_performed=false`)
  + return — NO synthesis LLM, NO reviewer. `StreamChatRequest.evidence_only` + `ChatRequest.{corpus_explorer,
  evidence_only}` + the `stream_request()` mapping. NEW `POST /chat/evidence` (forces evidence_only; drains
  via `run_chat`).
- **RB2-live (3 callsites; ALL behind `POLYMATH_REASONING_POLICY`, default 0 -> no-op/byte-identical).**
  Appliers `apply_litellm`/`apply_chat_completions` overlay reasoning params at runtime (never config ->
  extraction contract hash UNTOUCHED). Wired: `_litellm_generate` (CHAT_SYNTHESIS), `_run_reviewer`
  (REVIEWER; the deepseek `thinking:disabled` stays as an UNGATED correctness baseline, policy overlays on
  top), and the chat-compiler via `client.reasoning_role="STRUCTURED_COMPILER"` read by `client._chat`
  (extraction clients never set it). Each logs a sanitized `reasoning_policy {...}` line (Slice-2 wire proof).
- **RB3 (MCP surface + docs; live-only/docs).** Canonical `polymath_search` (→`/retrieve` evidence=true) /
  `polymath_explore` (→`/chat/evidence`, corpus_explorer) / `polymath_answer` (→`/chat`) added to BOTH
  servers (`mcp_server/polymath_mcp.py` stdio + `orchestrator/mcp_server.py` streamable-http); `polymath_query`
  + `polymath_retrieve` DEPRECATED in description (kept working). Server instructions carry the
  retrieval-authority / don't-pre-decompose contract. `capabilities.py`: `evidence-packet:v1` + `/chat/evidence`
  + the 3 tool names. `CONNECTORS.md` refreshed (two servers, canonical surface). `.env.example`:
  `POLYMATH_REASONING_POLICY=0`.

## Proof
- **RB1/RB2 shared UNIT_PROVEN** (executed path = worktree; import sources verified `pmv4-reasoning`).
  `test_evidence_packet.py` 8/8 (shape + no-synthesis flag; direct + CORPUS_EXPLORE rows; utility_role from
  C5 seat; c4_valid RELATED-only=false vs seated=true; size/receipt bounds; skip no-chunk-id; deterministic).
  `test_reasoning_policy.py` 11/11 (family detection; **Qwen Chat-Completions thinking_budget=300 not
  reasoning_effort**; Qwen Responses no-budget->disable; DeepSeek disabled; Claude effort=low no manual
  budget; Gemini thinking_level=low; output-separate-and-independent; **never both effort+budget** swept over
  roles×providers×surfaces; env override).
- **RB1-live/RB2-live IMPLEMENTED, live-only** (editable-.pth: ui.py/chat.py/compare_review/client resolve
  to MAIN under pytest). py_compile all OK; preflight=0; appliers no-op when the flag is off (verified). +2
  applier tests (off=no-op byte-identical; on=deepseek disabled + qwen thinking_budget=300 no reasoning_effort).
  Real proof = the live boundary checks (Slice 1) + the reasoning wire-param log (Slice 2) after merge+bounce.
- **SLICE 1 CUTOVER — LIVE_PATH_PROVEN (merge `99d12cc` -> production; bounce; `POLYMATH_REASONING_POLICY=0`).**
  Fleet one bundle, /ready, orchestrator env `POLYMATH_REASONING_POLICY=0` + `POLYMATH_CORPUS_EXPLORER=1`.
  Deployed shared re-proven on MAIN (113 tests). ALL 8 boundary checks PASS: (1) `/chat` normal =
  answer, unchanged; (2) `/chat/evidence` = `kind:evidence` EvidencePacket v1, `synthesis_performed=false`,
  21 rows w/ utility_role+ca4_grade (CA4 ran), corpus_explorer_used=true, all 4 receipts, NO answer field;
  (3) evidence_only receipt `verdict=evidence_only` + NO synthesis_version (0 synthesis) & reviewer not in
  path (0 reviewer); (4) polymath_search -> 38 evidence rows; (5) polymath_explore -> rich packet, no
  synthesis; (6) polymath_answer -> answer; (7) `/capabilities` advertises `evidence-packet:v1` +
  `/chat/evidence` + the 3 canonical tools, both servers carry the don't-pre-decompose contract; (8) bridge
  `think:false` intact (2x) + extraction contract inputs (GENERATION_CONFIG/cloud_providers.json/pool.py)
  UNCHANGED -> no re-key/re-extraction. Checkpoint tag `v4-reasoning-boundary-slice1`.

## Rejected claims
- NOT claimed: any live behavior (RB1/RB2 live wiring + RB3 MCP are live-only; proof = post-merge live).
- NOT claimed: exact provider wire-param placement is final — encoded per owner intents; the live
  request-capture test (RB2-live) validates each reaches the wire correctly.

## Open contract gaps
RB1 live (chat_events short-circuit + `/chat/evidence` + `evidence_only`/`corpus_explorer` on both request
models), RB2 live (apply `reasoning_params` at `_litellm_generate` CHAT_SYNTHESIS + `_run_reviewer` REVIEWER +
chat-compiler STRUCTURED_COMPILER, VERIFYING no extract-contract re-key), RB3 (MCP search/explore/answer on
both servers + deprecate polymath_query + capabilities + CONNECTORS.md), RB4 (live verification + close-out).
All live-only + gated; `/chat` byte-identical when `evidence_only` unset.
