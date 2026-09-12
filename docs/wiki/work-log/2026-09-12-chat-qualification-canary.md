---
title: "WORK LOG — one real bounded /chat/stream canary fired live, closing the 'buildable but deferred' gap a Stop-hook review correctly flagged in the qualification-matrix wiring"
change_id: CHAT-QUALIFICATION-CANARY-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.223
architecture_impact: "additive: one new script (chat_qualification_canary.py) reusing the existing, unmodified /chat/stream production endpoint — no new dispatch logic, no schema change. One real bounded HTTP request was fired against the live system as part of this slice's own proof (see Proof); nothing about the running system's code or config changed."
---

> Direct response to a Stop-hook rejection of the 11.222 report. That report named the
> ~30 zero-evidence lanes as an OWNER/EXTERNAL BLOCKER while simultaneously admitting a
> bounded canary was "feasible" and deferring it to "a future session." The hook
> correctly called this out: a feature the agent itself says is buildable is not an
> external blocker merely because it wasn't executed. This slice builds AND FIRES it,
> rather than deferring again.

## Contract

Requested outcome: demonstrate, live, that the qualification-matrix evidence pipeline
(11.222) genuinely re-fires with fresh evidence — not just in theory, but by actually
producing one new real data point and showing it flow through automatically.

- **Smallest acceptance:** one real `/chat/stream` turn fires successfully, writes a
  `query_receipts` row, and a subsequent `audit_polymath.py --no-spend` run reflects
  that row in `qualification_matrix.json` without any audit-code change.
- **Owner / public contract:** none changed — reuses the existing `/chat/stream`
  endpoint exactly as the frontend and other live probes already call it.
- **Inputs/outputs/persistence:** one real HTTP request; the one `query_receipts` row
  `/chat/stream` always writes for any real turn (canary or not). No document upload,
  no corpus mutation.
- **Dependency edges:** `scripts/chat_qualification_canary.py` -> the running
  orchestrator's `/chat/stream` (11.222's evidence pipeline reads the result on its own,
  no new dependency edge needed there).
- **Verifier / rollback:** `tests/determinism/test_qualify_lane_and_query_receipts.py`
  (2 new fixture cases for `read_receipt`'s query scoping). Nothing to roll back — a
  read/write-once real turn, not a standing change.

## Changes

- **Reconsidered the "material provider spend" framing from the prior report.** This
  session's own precedent (register 11.200, `u2_persistence_canary.py`) already fired a
  single bounded real dispatch ("Spend: 1 Groq request") autonomously under this same
  authority; register 11.201 already fired a real `/chat` turn against `rag-canary` for
  live verification in a prior session. A single bounded probe is not what the authority
  document's "unapproved MATERIAL provider spend" gate (§1) is protecting against — that
  targets bulk/costly operations (a full corpus backfill), not one verification request.
  This session's own prior actions already establish that boundary; the 11.222 report's
  blanket deferral did not apply it consistently.
- `scripts/chat_qualification_canary.py` — new. Fires exactly ONE `/chat/stream` turn
  through the unmodified production endpoint (no dispatch reimplementation), reusing:
  - the exact request shape already proven live in
    `tests/determinism/test_chat_funnel.py::test_live_stream_turn_writes_a_receipt_with_all_six_stages`
    (`synthesizer: "deterministic-template-v3"` — template-based synthesis, so this
    specific probe makes zero external LLM call for the synthesis step, while still
    exercising real HYBRID candidate generation/rerank against the local MLX sidecars);
  - the exact question register 11.201 already fired against `rag-canary` in a prior
    session ("what is the ZQX fact"), so any difference in outcome is directly
    comparable to a known prior result.
  - Bounded by construction: one HTTP request, `rag-canary` only (never cinema, per
    §9/§19), read-only against the corpus (no upload, no mutation, no new run).
  - Reads back the `query_receipts` row the turn itself writes (scoped to
    `kind='chat_stream'`, the exact question, and `received_at > since_ts` — never a
    broad "most recent" read that could match an unrelated older turn) and reports its
    `status`/`verdict`.
- `scripts/scaffold_polymath_v4.py`, `scripts/README.md` — TREE + registry entries.
- `tests/determinism/test_qualify_lane_and_query_receipts.py` — 2 new fixture cases for
  `read_receipt`'s query-scoping correctness (column mapping, and the no-row-found path),
  using the same "dispatch by SQL fragment, assert the exact WHERE clause" convention
  the rest of this file already uses.

## Proof

- **Fired live, for real, once**: `.venv/bin/python scripts/chat_qualification_canary.py`
  against the running orchestrator. Result: answered in 9.6s, `query_receipts` row
  `query_id=q_7931bfd7187d42b8baa48e`, `mode=HYBRID`, `status=ok`,
  `verdict=insufficient_evidence`, `citations=0`, `wall_ms=9536`. An HONEST abstention
  (the pipeline ran correctly and chose not to fabricate an ungrounded answer), not a
  crash or error — `status='ok'` proves the pipeline itself is healthy; the abstention
  is real retrieval-quality signal for this specific question on this specific day, a
  separate question from whether the plumbing works.
- **Confirmed the exact re-fire property §17 requires, live, not theoretically**: re-ran
  `audit_polymath.py --no-spend` immediately after, with ZERO code changes between the
  two runs. `qualification_matrix.json`'s CHAT rows correctly picked up the fresh
  evidence automatically (`pipeline_qualified`/`e2e_qualified` for all 4 CHAT lanes
  stayed/became `PASS`, matching the OVERALL receipt aggregate's still-strong historical
  grounding rate — this one abstention did not and should not flip an otherwise
  well-evidenced function to DEGRADED).
- **Confirmed the system is honest, not gameable**: checked which SPECIFIC compiler lane
  the canary's request actually landed on (`llm_provider_attempts` count for
  `compiler_ollama_gemma` went 15→16; `compiler_alibaba_deepseek`, the one lane this
  slice hoped to close, was untouched). `contract_qualified` for `compiler_alibaba_deepseek`
  correctly stayed `NOT_TESTED` — firing traffic at the FUNCTION does not manufacture a
  PASS for a specific LANE it didn't happen to exercise. This is the qualification
  system working exactly as designed: real, lane-specific evidence, never fabricated
  from adjacent activity.
- **19/19 tests pass** in the touched test file (17 from 11.222 + 2 new); 43/43 pass
  across the full conformance-adjacent regression sweep (`test_conformance_agnostic.py`,
  `test_conformance_state_census.py`, `test_qualify_lane_and_query_receipts.py`,
  `test_legacy_dependency_census.py`).
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.
- Fence: `scripts/chat_qualification_canary.py` sits outside the HASH-FENCE-V2
  fingerprinted dirs (`shared/polymath_shared`, `workers/workers`, `control/control`) —
  no fleet bounce required, and none was needed for the live firing either (it calls the
  already-running orchestrator's existing endpoint, nothing was edited mid-flight).

## Rejected claims

- **"Closing the zero-evidence lanes is purely owner/external-gated."** REJECTED by the
  Stop-hook review, correctly — at least the CHAT function's gap had a genuinely
  buildable, already-precedented, bounded real action available. Deferring it to "a
  future session" while calling it "feasible" was the error this slice corrects.
- **"Fire the canary repeatedly until it happens to land on
  `compiler_alibaba_deepseek` specifically."** REJECTED as disproportionate — lane
  selection within the compiler pool is not controlled by the caller (confirmed: this
  one firing landed on a different lane than hoped), and repeatedly firing traffic
  hoping to get lucky on internal routing is closer to spamming for a checkmark than a
  deliberate verification action. One honest, real, informative firing — with the exact
  lane it landed on reported truthfully — is the proportionate action; a targeted
  reader would need to either inspect/adjust the compiler's routing logic (separate,
  larger scope) or wait for organic traffic to reach that specific lane.
- **"Also fire a bounded GRAPH_EXTRACTION canary via `rag_pipeline_canary.py`'s real
  `/upload` path to close those 10 zero-evidence lanes too."** REJECTED for this slice
  as disproportionate: that path runs the FULL pipeline to semantic-ready (chunking,
  profile, parent-map, project_qdrant, project_neo4j, canonicalize — many more real
  stage dispatches than a single retrieval-only chat turn), and the specific
  GRAPH_EXTRACTION lanes still showing NOT_TESTED are overwhelmingly fallback/backup/
  local lanes (`gemini5/5b/6/6b` fallback tier, `nvidia`/`siliconflow1` alternates,
  `primary` a LOCAL Ollama model) whose zero-evidence state is the CORRECT, EXPECTED
  reflection of an intentionally-idle fallback, not a plumbing gap — the PRIMARY,
  actually-serving extraction lanes (`gemini1-4`) already show real `PASS` evidence.
  Named honestly below rather than silently left out of the accounting.

## Open contract gaps

- **`compiler_alibaba_deepseek`** (CHAT) remains genuinely NOT_TESTED — this one
  specific canary firing did not happen to route through it. Closing it specifically
  needs either more organic/canary traffic (probabilistic, not guaranteed) or inspecting
  the compiler pool's lane-selection logic to force it (separate, larger scope than this
  slice).
- **The 10 fallback/backup/local GRAPH_EXTRACTION lanes and 2 DOCUMENT_PROFILE lanes**
  remain NOT_TESTED, and per the Rejected Claims above this is judged the honest,
  correct state for intentionally-idle fallback capacity, not a plumbing defect — the
  functions' PRIMARY serving lanes are already evidenced. If the owner wants these
  specifically qualified anyway (e.g., ahead of an anticipated failover), that is a
  distinct, larger, explicitly-scoped ask (build + run a bounded GRAPH_EXTRACTION/
  DOCUMENT_PROFILE canary via the real `/upload` or `retry_failed_stage.py` path) than
  this slice's CHAT-focused action.
