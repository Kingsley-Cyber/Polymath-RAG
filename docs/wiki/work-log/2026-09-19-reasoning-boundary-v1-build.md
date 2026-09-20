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

## Proof
- **RB1/RB2 shared UNIT_PROVEN** (executed path = worktree; import sources verified `pmv4-reasoning`).
  `test_evidence_packet.py` 8/8 (shape + no-synthesis flag; direct + CORPUS_EXPLORE rows; utility_role from
  C5 seat; c4_valid RELATED-only=false vs seated=true; size/receipt bounds; skip no-chunk-id; deterministic).
  `test_reasoning_policy.py` 11/11 (family detection; **Qwen Chat-Completions thinking_budget=300 not
  reasoning_effort**; Qwen Responses no-budget->disable; DeepSeek disabled; Claude effort=low no manual
  budget; Gemini thinking_level=low; output-separate-and-independent; **never both effort+budget** swept over
  roles×providers×surfaces; env override).

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
