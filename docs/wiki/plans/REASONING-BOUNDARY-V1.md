---
title: "REASONING-BOUNDARY-V1 — evidence-only agent tool boundary + centralized model-role reasoning-budget policy"
date: 2026-09-19
last_reviewed: 2026-09-19
status: "DONE — RB1-RB4 live: evidence boundary merged 99d12cc (11.343), reasoning policy switched on (11.344). Status refreshed 2026-09-24 (11.463)."
owner: "@king"
scope: "Stop compounding/nested LLM reasoning. Expose Polymath to Claude Code/Hermes as an evidence-only retrieval service (search + explore) plus a human answer tool, on BOTH MCP servers, with retrieval-authority tool descriptions. Centralize reasoning as a semantic role-budget policy translated by API-surface-aware provider adapters, applied to the chat synthesis + reviewer + chat-compiler; leave bridge (off) and document-extraction (off, contract-hash-locked) untouched."
---

# REASONING-BOUNDARY-V1 — Implementation Plan (repo-grounded)

## Context

**Problem — reasoning compounds.** Today an external agent asking Polymath a question triggers a *stack* of
LLM reasoning: caller reasons → Polymath chat compiler → bridge model → **Polymath chat synthesis model** →
caller reasons again over the answer. Two facts make this worse than it looks:
1. **The local agent path uses the wrong tool.** There are **two MCP servers**. The public streamable-http
   Server A (`orchestrator/orchestrator/mcp_server.py`) has evidence-only tools (`retrieve_evidence`,
   `compile_plan`, EXPLORE). But **this project's Claude Code / local Hermes is wired to the stdio Server B**
   (`mcp_server/polymath_mcp.py`, `~/.claude.json:1409-1420`), whose `polymath_query` → `/chat` runs the full
   answer LLM. So the default local tool triggers nested synthesis and doesn't even expose evidence-only tools.
2. **The chat synthesis reasoning is uncontrolled.** The default answer model (`deepseek-v4-flash`) is invoked
   via `_litellm_generate` (`ui.py:2764`) with **no** thinking/effort param — only `max_tokens=6000`. That
   same model "spends most of its tokens on reasoning" and even "returns EMPTY unless thinking is disabled"
   (per `compare_review.py:204-214`, which hardcodes the disable for the reviewer only).

**Decisions (owner):**
- **Boundary:** factor the chat path as `prepare_evidence(req) -> EvidencePacket` reused by both a new
  evidence endpoint (return the packet, **skip synthesis + reviewer**) and `/chat/stream`
  (`prepare_evidence → synthesize → review → stream`). Keep the cheap `/retrieve` (q0-only) as a separate
  lightweight "search". So: **`search` (cheap q0 evidence) + `explore` (full pipeline, evidence-only) +
  `answer` (human synthesis)**.
- **MCP:** give BOTH servers the same canonical surface (`polymath_search` / `polymath_explore` /
  `polymath_answer`), **deprecate the ambiguous `polymath_query`** (don't silently change it — check
  consumers, re-describe/hide), add retrieval-authority / don't-pre-decompose language, fix `CONNECTORS.md`.
  Do NOT unify the two servers.
- **Reasoning:** a **semantic role → reasoning-BUDGET policy** (not just on/off), translated by
  **API-surface-aware provider adapters**. Apply to chat-compiler + chat-synthesis + reviewer now. Bridge is
  already `think:false`; document-extraction is already off and **contract-hash-locked — do not touch**.

**Governing principle:** Polymath owns retrieval intelligence (planning + grounded expansion + validation);
the caller (or the human synthesis model) owns final reasoning; **no hidden nested synthesis** and **no stage
lets reasoning consume the budget its structured output needs**.

---

## Architecture

### A. The evidence boundary (short-circuit, not a rewrite)

```text
                 CLAUDE CODE / HERMES  (original q0; no pre-decomposition)
                         │
        ┌────────────────┴─────────────────┐
   polymath_search                    polymath_explore
        │                                   │
  /retrieve (q0-only, cheap)          /chat/evidence  (NEW; evidence_only)
   evidence rows, no plan                   │  prepare_evidence():
   no Corpus Explore, no synth              │   compiler → Corpus Explore(if requested)
        │                                   │   → retrieval/RankedLane/V2 → C4 → C5 → CA4
        │                                   │   → assemble EvidencePacket → STOP
        └───────────── EvidencePacket ◄─────┘   (NO synthesis LLM, NO reviewer)
                         │
                 caller reasons + writes the answer

   polymath_answer → /chat/stream → prepare_evidence() → synthesize() → review() → answer  (humans/UI)
```

The `retrieval` object the chat path already emits (legend / used_evidence / epistemic=CA4 / chat_plan +
`corpus_activation`/`corpus_explore_expansion` receipts — verified live in CORPUS-EXPLORER-V1) already holds
the packet's data. The work is: **short-circuit `chat_events` at the evidence-bundle seam (before the
synthesizer branch, `ui.py:3621`) to emit an EvidencePacket and return** — reusing the pipeline in place
(no duplication). Optional later cleanup: extract a non-streaming `prepare_evidence()` for structure.

### B. EvidencePacket — a versioned, size-bounded contract (NEW, `shared/`)

```text
EvidencePacket
  schema_version: "evidence-packet-v1"
  q0 · retrieval_mode · synthesis_performed=false
  plan { compiled_queries[], corpus_explorer_requested, corpus_explorer_used }
  evidence[] {
    chunk_id · document_id · source · text(bounded)
    origin · query_ids[] · lineage[]
    utility_role  # DIRECT / COMPLEMENTARY / DIVERGENT   (C5 seat_role, else synthesis_role)
    ca4_grade     # DIRECT / PARTIAL / RELATED           (grade_evidence per-chunk)
    c4_valid · provenance
  }
  receipts { activation, bridges, corpus_explore, fusion }   # bounded
```
Assembled by a pure `build_evidence_packet(bundle, plan, receipts)` mapper. Size-bounded (cap evidence rows +
text length + receipt depth). External agents don't need every internal score.

### C. Reasoning as a semantic role → BUDGET policy (NEW, `shared/`)

The rule (owner): *For bounded RAG planning stages, prioritize completion of the structured contract over
hidden reasoning. Target ≤300 reasoning tokens where the provider supports an explicit reasoning budget;
otherwise disable reasoning or use the lowest available effort. Reserve ≥250–350 output tokens for
bridge/compiler JSON. **Never let reasoning consumption truncate the structured response.***

Semantic policy per role (reasoning ceiling is a CEILING, not a target — simple calls use ~0):

| Role | reasoning (ceiling) | structured output cap |
|---|---|---|
| `BRIDGE` (Corpus Explore / bridge gen) | 0–200 | ~250–350 |
| `STRUCTURED_COMPILER` (chat query compiler) | 0–300 | ~350–500 |
| `REVIEWER` / validator | 0–200 | ~100–200 |
| `CHAT_SYNTHESIS` | low / adaptive | large (separate budget) |
| `EXTRACTION` | **LOCKED — do not touch** | locked |
| caller (Claude/Hermes) | caller-controlled | caller-controlled |

Encode it semantically; a **provider adapter** translates per API surface (the rest of Polymath stays
provider-agnostic):
```text
RolePolicy{ preferred_max_reasoning_tokens, fallback_effort, allow_reasoning_disable,
            min_output_tokens, target_output_tokens, hard_output_tokens }
```
| Provider (surface) | translate reasoning | notes |
|---|---|---|
| **Qwen 3.8 — Chat Completions** | `thinking_budget=300` + `preserve_thinking=false` | do NOT also send `reasoning_effort` (invalid combo); `reasoning_effort=low`≈4096 = too big |
| **Qwen 3.8 — Responses API** | `thinking_budget` NOT supported → disable / lowest effort | adapter MUST know the surface, not blindly normalize |
| **Claude** | `effort=low` (or thinking disabled where supported) | no 300-token manual budget; manual min 1024; newer = adaptive effort |
| **Gemini 3.8 Flash** | `thinking_level=low` | defaults medium; low/medium/high; cannot fully disable |
| **DeepSeek v4** | `extra_body={"thinking":{"type":"disabled"}}` (or `reasoning.effort=none`) | REQUIRED — returns empty otherwise |
| **Ollama (bridge)** | `think:false` (already) | leave as-is |

Output budget is set **independently** of reasoning (never share one ceiling). Apply the compiler's cap as
`hard_output_tokens` (~350–500) AFTER the reasoning ceiling, replacing the "600 total" single ceiling.

---

## New / changed files

| File | Change | Provable |
|---|---|---|
| `shared/polymath_shared/evidence_packet.py` | **NEW, pure.** `EvidencePacket` dataclass + `build_evidence_packet(bundle, plan, receipts, *, max_rows, max_text)` mapper (bundle→packet; utility_role/ca4_grade/c4_valid/provenance from existing fields). Size-bounded. | `shared/` UNIT |
| `orchestrator/orchestrator/api/ui.py` (`chat_events` ~`:3044`, before synth branch `:3621`) | Add `evidence_only` request path: after the evidence bundle + CA4 are assembled, emit `build_evidence_packet(...)` as the terminal event and **return before synthesis + reviewer**. Additive; `evidence_only` defaults false → `/chat/stream` byte-identical. | `ui.py` LIVE |
| `orchestrator/orchestrator/api/ui.py` + `chat.py` | New `/chat/evidence` endpoint (thin: run the evidence-only path, return the packet as JSON). Add `evidence_only` + `corpus_explorer` to the request models where missing (`ChatRequest` lacks both). | LIVE |
| `shared/polymath_shared/reasoning_policy.py` | **NEW, pure.** `RolePolicy` + `ROLE_POLICIES` (BRIDGE/STRUCTURED_COMPILER/REVIEWER/CHAT_SYNTHESIS) + `provider_params(role, model, api_surface) -> dict` adapter (the table above). Config-overridable via env. | `shared/` UNIT |
| `orchestrator/orchestrator/api/ui.py` `_litellm_generate` (`:2708-2764`) | Inject `provider_params("CHAT_SYNTHESIS", model, "litellm")` into the litellm kwargs/`extra_body`; keep the large answer budget separate. | LIVE |
| `orchestrator/orchestrator/api/compare_review.py` `_run_reviewer` (`:185-215`) | Replace the hardcoded deepseek `thinking:disabled` with `provider_params("REVIEWER", model, "litellm")`. | LIVE |
| `shared/polymath_shared/llm_extraction/client.py` `_chat` (`:357-414`) + `config/cloud_providers.json` compiler lanes | Apply the `STRUCTURED_COMPILER` policy to the chat-compiler endpoints (Qwen `thinking_budget=300`+`preserve_thinking=false` on Chat Completions; output cap ~350–500). **Verify this does NOT re-key the extract-stage contract** (`pool_fingerprint`/`GENERATION_CONFIG`, `pool.py:330`, `client.py:42`) — if it would, apply the compiler budget via a chat-compiler-only path, NOT the shared extraction contract. | `shared/` UNIT + LIVE |
| `orchestrator/orchestrator/mcp_server.py` (Server A) + `mcp_server/polymath_mcp.py` (Server B) | Add `polymath_search` (→ `/retrieve` evidence-only), `polymath_explore` (→ `/chat/evidence`, `corpus_explorer` supported), `polymath_answer` (→ `/chat`). **Deprecate `polymath_query`** (Server B): keep working but re-describe as human-answer/deprecated; check `~/.claude.json` + consumers first. Rewrite descriptions with the retrieval-authority / don't-pre-decompose / synthesize-yourself contract. | LIVE / manual |
| `orchestrator/orchestrator/api/capabilities.py` | Add `evidence-packet: "v1"` + endpoints (`/chat/evidence`) + the new MCP tool names to `CONTRACTS`/`ENDPOINTS`/`MCP_TOOLS`. | LIVE |
| `mcp_server/CONNECTORS.md` + `README.md` | Update the stale "one server / 9 tools" doc to the canonical 3-tool surface + both servers. | docs |

**Reused unchanged:** the whole retrieval spine (compiler, Corpus Explore, RankedLane, V2 fusion, C4/C5/CA4,
`grade_evidence`, `evidence_rows.build_evidence_rows`); the extraction `cloud_opts`/`stage_pins` reasoning
machinery (`client._chat`); the bridge `think:false`. `/retrieve` stays q0-only and cheap (NOT extended).

---

## Implementation phases

**RB0 — recon + checkpoint (done).** Recon complete (two-server discovery; evidence-path gap; reasoning gap
localized). Base = `production` HEAD `3e88b06` (CORPUS-EXPLORER-V1 live). Isolate in a worktree; author
plan-of-record `docs/wiki/plans/REASONING-BOUNDARY-V1.md` + register row + work-log.

**RB1 — EvidencePacket + evidence-only short-circuit (shared + ui.py).** `evidence_packet.py` (pure) + the
`chat_events` short-circuit + `/chat/evidence`. **Acceptance:** a live `/chat/evidence` call returns a valid
EvidencePacket (roles, CA4 grade, provenance, corpus_explore receipts) and makes **zero** synthesis/reviewer
LLM calls (assert via the ledger / no `chat_synth` attempt); `/chat/stream` unchanged (evidence_only=false).

**RB2 — reasoning-budget policy (shared + 3 callsites).** `reasoning_policy.py` (pure, provider-adapter) +
apply to `_litellm_generate` (CHAT_SYNTHESIS), `_run_reviewer` (REVIEWER), and the chat-compiler lanes
(STRUCTURED_COMPILER). **Acceptance:** unit — the adapter emits the right params per (role, provider,
surface) incl. Qwen Chat-Completions `thinking_budget=300`/no `reasoning_effort` combo, Claude `effort=low`,
DeepSeek disabled; live — the params reach the wire (capture the outgoing request), the compiler emits
complete JSON (no truncation) with reasoning bounded, and **extraction contract hash is unchanged** (no
re-extraction triggered).

**RB3 — MCP surface (both servers) + docs.** Add the 3 canonical tools to A + B; deprecate `polymath_query`;
rewrite descriptions; update `capabilities.py` + `CONNECTORS.md` + `README.md`. **Acceptance:** the local
Claude Code (Server B) sees `polymath_search`/`polymath_explore`/`polymath_answer`; `polymath_explore`
returns an EvidencePacket with no Polymath answer; descriptions carry the don't-pre-decompose contract.

**RB4 — verification + close-out.** End-to-end nesting check (an agent calling `polymath_explore` gets
evidence + synthesizes itself; no nested Polymath synthesis fired); register/work-log/CONTINUITY; checkpoint
tag. Bounce only if an env/settings-frozen value changed (the JSON catalog + DB are live; env is `lru_cache`d).

---

## Landmines

1. **Extraction contract hash.** `reasoning_effort` is hashed into `pool_fingerprint` + the extract-stage
   contract → changing extraction reasoning forces **re-extraction**. Do NOT touch extraction lanes. For the
   chat-compiler lanes, VERIFY the new param (`thinking_budget`/`enable_thinking`) isn't in the extract
   contract hash before setting it; if it is, route the compiler budget outside the shared contract.
2. **Qwen API surface.** `thinking_budget` is **Chat Completions only** (not the Responses API); never send
   `reasoning_effort` + `thinking_budget` together; `reasoning_effort=low`≈4096 tokens (too large). The
   adapter must branch on surface. The compiler uses the httpx Chat-Completions client (`client._chat`) → OK.
3. **Claude has no 300 budget.** Use `effort=low`/disable, not a manual small budget (min 1024).
4. **Never let reasoning starve output.** Set the output cap independently of the reasoning ceiling (replace
   the compiler's single "600 total"); ≥250–350 output for bridge/compiler JSON.
5. **Preserve the human path exactly.** `evidence_only` + `/chat/evidence` are additive; `/chat` and
   `/chat/stream` must be byte-identical when `evidence_only` is unset.
6. **Deprecate `polymath_query` safely.** Check `~/.claude.json` + any consumers; keep it functional but
   unambiguous/deprecated — don't silently change its behavior.
7. **Two request models.** `/chat` uses `ChatRequest` (no `corpus_explorer`, no `evidence_only`) mapped to
   `StreamChatRequest` by `stream_request()` — add fields in BOTH + the mapping or they drop on `/chat`/MCP.
8. **Bound the packet.** Cap rows + text + receipt depth; don't leak every internal score.
9. **Editable-.pth.** `ui.py`/`mcp_server.py` are live-only-provable; `shared/` (evidence_packet,
   reasoning_policy) is worktree-unit-provable.

---

## Verification

- **Unit (shared/):** `evidence_packet` mapping (roles/CA4/provenance/size-bound); `reasoning_policy`
  adapter per (role, provider, surface) — assert the exact params + the invalid-combo guard.
- **Live:** `/chat/evidence` returns a valid packet with **0 synthesis/reviewer attempts** (ledger); the
  reasoning params reach the wire (capture request) and the compiler returns complete JSON under bound;
  `/chat/stream` unchanged; MCP `polymath_explore` returns the packet on both servers.
- **Nesting check:** an agent flow using `polymath_explore` produces evidence only (no Polymath answer),
  proving the reasoning boundary — one Polymath planning layer, caller does the final reasoning.
- **Guards** 0; extraction contract hash unchanged (no re-extraction); new files in scaffold TREE.

## Do-not
Do not: extend `/retrieve` with bridges/CA4; touch extraction/bridge reasoning; use `max_tokens` as the
reasoning control; send Qwen `reasoning_effort`+`thinking_budget` together; force a 300-token budget on
Claude; unify the two MCP servers; change `polymath_query` behavior silently; `git push` to main.
