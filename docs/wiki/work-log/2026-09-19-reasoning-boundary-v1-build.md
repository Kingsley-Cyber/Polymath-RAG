---
change_id: REASONING-BOUNDARY-V1-BUILD
owner: "@king"
date: 2026-09-19
status: complete
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
- **SLICE 2 REASONING QUAL — PASS (`POLYMATH_REASONING_POLICY=1` + bounce; separate reversible slice).**
  INFO logs were suppressed, so the appliers append the sanitized applied params to a JSONL receipt
  (`54094a4`; `POLYMATH_REASONING_RECEIPT`). Small live matrix (2 chats + 1 reviewer; the compiler fires on
  each) captured the ACTUAL outgoing params (`eval/reasoning_boundary/SLICE2-WIRE-PARAMS-2026-09-19.json`):
  STRUCTURED_COMPILER/qwen/chat_completions = **`thinking_budget=300, preserve_thinking=false` (NO
  reasoning_effort)** out=500; CHAT_SYNTHESIS/deepseek/litellm = `extra_body.thinking:disabled` out=6000;
  CHAT_SYNTHESIS/qwen/litellm = `enable_thinking:false, preserve_thinking:false` out=6000; REVIEWER/deepseek
  = `thinking:disabled` out=200; a non-reasoning compiler lane ("other") = `{}` (safe). Output budget
  INDEPENDENT of the reasoning ceiling; **reasoning never truncated the structured output** — all qual turns
  finished `stop` (deepseek 1765 / qwen 1492 chars), reviewer parse_error=None, **0 compiler fallbacks**.
  Claude(effort=low)/Gemini(thinking_level=low) not in the live config -> proven deterministically (unit).
  End state: policy stays ON (qualified). REVERSIBLE: `POLYMATH_REASONING_POLICY=0` + bounce (evidence
  boundary + MCP unaffected).

## Rejected claims
- NOT claimed: any live behavior (RB1/RB2 live wiring + RB3 MCP are live-only; proof = post-merge live).
- NOT claimed: exact provider wire-param placement is final — encoded per owner intents; the live
  request-capture test (RB2-live) validates each reaches the wire correctly.

## Open contract gaps
RB0-RB4 COMPLETE + LIVE. Slice 1 (evidence boundary, policy OFF) 8/8 proven; Slice 2 (reasoning policy ON)
wire-params proven. Contract dispositions (additive, live-verified): `evidence_packet`/`reasoning_policy`
NEW; `StreamChatRequest`/`ChatRequest`/`chat_events` UPDATED (`evidence_only`, byte-identical when unset);
`_litellm_generate`/`_run_reviewer`/`client._chat` UPDATED (gated runtime overlay; extraction contract hash
UNCHANGED, no re-extraction); both MCP servers + `capabilities.py` UPDATED (canonical surface). Consumers
TESTED_UNCHANGED (102 impacted determinism + 69 extraction-client). END STATE: `POLYMATH_REASONING_POLICY=1`
(qualified) + `POLYMATH_CORPUS_EXPLORER=1`, evidence boundary LIVE. FOLLOW-UPS (not blockers): Server A/B
unification (deferred, owner said no); the suppressed INFO logger (superseded by the JSONL receipt).
REVERSIBLE: `POLYMATH_REASONING_POLICY=0` + bounce restores pre-RB reasoning; evidence boundary + MCP stay.
