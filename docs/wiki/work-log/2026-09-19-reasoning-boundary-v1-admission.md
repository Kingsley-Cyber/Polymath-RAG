---
change_id: REASONING-BOUNDARY-V1-RB0
owner: "@king"
date: 2026-09-19
status: complete
status_note: "RB1-RB4 done and live: evidence boundary merged 99d12cc (11.343), reasoning policy switched on (11.344). (was: admitted)"
architecture_impact: "RB0 admission only (docs + register + worktree). No code. Admits REASONING-BOUNDARY-V1: (1) an EvidencePacket boundary — short-circuit the chat pipeline before synthesis so external agents (Claude Code/Hermes) get validated corpus evidence (roles/CA4/provenance/corpus_explore) with NO nested Polymath synthesis LLM; expose search/explore/answer on BOTH MCP servers, deprecate polymath_query. (2) A semantic role->reasoning-BUDGET policy translated by API-surface-aware provider adapters, applied to chat-synthesis + reviewer + chat-compiler; bridge (think:false) and document-extraction (contract-hash-locked) untouched. Reuses the retrieval spine; nothing rewrites retrieval."
last_reviewed: 2026-09-19
---

## Contract
Owner admitted REASONING-BOUNDARY-V1 (plan approved) after a 3-agent recon. Plan-of-record:
`docs/wiki/plans/REASONING-BOUNDARY-V1.md`. Base = `production` HEAD `3e88b06` (CORPUS-EXPLORER-V1 live).
LOCKED DECISIONS: (a) Evidence boundary = short-circuit `chat_events` before the synth branch to emit a
versioned, size-bounded `EvidencePacket`, reusing the pipeline in place (no `/retrieve` extension). `/retrieve`
stays the cheap q0-only search; `/chat/evidence` is the rich explore; `/chat` stays the human answer. (b) MCP:
canonical `polymath_search`/`polymath_explore`/`polymath_answer` on BOTH servers (A `mcp_server.py` + B
`polymath_mcp.py`), deprecate `polymath_query`, retrieval-authority/don't-pre-decompose descriptions, no server
unification. (c) Reasoning: semantic role->budget policy (reasoning ceiling SEPARATE from output floor; never
truncate JSON) via provider adapters aware of API surface (Qwen Chat-Completions `thinking_budget=300` not
`reasoning_effort`; Claude `effort=low`; Gemini `thinking_level=low`; DeepSeek disabled). Apply to
chat-synthesis + reviewer + chat-compiler; do NOT touch extraction (contract hash) or bridge (already off).

## Changes
RB0 (this slice) = admission + scaffolding only, no production code:
- Added `docs/wiki/plans/REASONING-BOUNDARY-V1.md` (plan-of-record, file:line seams + landmines).
- Added this work-log.
- Appended `PLAN-AUTHORITY-REGISTER.md` row 11.340 (admission).
- Declared both docs in `scripts/scaffold_polymath_v4.py` TREE.
- Verified base checkpoint: `production` HEAD `3e88b06`, tree clean; guards repo_guard/wiki_worm=0.
- Isolated in worktree `pmv4-reasoning` (branch `reasoning-boundary/agent-evidence`) off `3e88b06`.

## Proof
`ADMITTED` (docs). Base guards green at `3e88b06`. No code executed this slice; RB1+ carry the
UNIT_PROVEN / LIVE_PATH_PROVEN evidence.

## Rejected claims
- REJECTED extending `/retrieve` with bridges/CA4 (owner): keep it cheap q0-only; the rich packet comes from
  the chat pipeline short-circuit.
- REJECTED touching extraction or bridge reasoning: extraction is contract-hash-locked; bridge is already off.
- REJECTED `max_tokens` as the reasoning control, and unifying the two MCP servers.
- NOT claimed: any code proven this slice (RB0 is admission only).

## Open contract gaps
RB1 (EvidencePacket + evidence-only short-circuit), RB2 (reasoning_policy module + 3 callsites), RB3 (MCP
surface both servers + capabilities + docs), RB4 (verification + close-out). Contracts to touch:
`evidence_packet` (NEW), `reasoning_policy` (NEW), `chat_events`/`StreamChatRequest`/`ChatRequest`
(evidence_only + corpus_explorer), `_litellm_generate`/`_run_reviewer`/`client._chat` compiler lanes,
`capabilities.py`, both MCP servers. All additive + flag/param-gated; the human `/chat` path stays
byte-identical when `evidence_only` is unset.
