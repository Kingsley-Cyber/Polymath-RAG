---
title: "WORK LOG — P1.f runtime unification: one ChatRuntime — /chat, /chat/stream and MCP ask run the same generator; streaming is transport only"
change_id: CHAT-RUNTIME-V1
date: 2026-09-06
owner: governance (goal 2026-09-06; CHAT-QUERY-COMPILER-PLAN §4 P1.f / §3.7)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.98
package: orchestrator/orchestrator/api/{ui.py,chat.py}, shared/polymath_shared/query_receipts.py, tests/determinism/{test_chat_runtime.py,test_chat_hygiene.py}
architecture_impact: "`chat_events(req, *, route, receipt)` (ui.py) is the ONE chat runtime — eager request validation, scope, compiler off|shadow|on, MODE-COMPOSITION-V1 / v1 engines, bundle, CARRY-V2, SYNTHESIS-V2, receipts — yielding the SSE frames exactly as before; `chat_stream` streams it; `run_chat(req)` drains it and returns the `/chat` JSON (answer `result` + the same `retrieval` block + phases + `runtime: chat-runtime-v1`), raising the frame's HTTP status where the stream would have emitted an error frame. `/chat` builds a StreamChatRequest (CHAT-REQUEST-MAP-V1) and calls `run_chat`; its old dispatch is deleted; MCP `ask` inherits through `/chat`. Both routes write the same query receipt (route as a transport tag). Behaviour changes on `/chat`: LEGACY → 422 `unknown_mode`, multi-corpus FAST → 422 `mode_requires_single_corpus`, FAST reports `meta.mode: VECTOR`, `meta.funnel` is the compact funnel."
---

# WORK LOG — P1.f runtime unification

Plan gate (ledger row, read from disk before this phase): *same plan + same evidence ids for the same request on all routes (determinism test).* Goal: identical compiled plan, task type, resolved request, retrieval decision, evidence ids, carry admission, mode, degraded state and synthesis contract; streaming differs only in transport.

## Contract

- `chat_events(req: StreamChatRequest, *, route="chat/stream", receipt=None)`: validates message / mode / synthesizer eagerly (the same typed 422 on both transports, before any frame), then the generator emits `phase | token | reasoning | answer | done | error` frames unchanged (frame-name/order snapshots captured from the pre-refactor code through the same fakes match).
- `run_chat(req, *, route="chat", receipt=None)`: drains the generator to its end (the runtime's receipt is written first), returns answer `result` + `retrieval` + `phases` + `kind` + `latency_ms` + `runtime`; `meta.mode` = the executed mode; error frames → `HTTPException` with the frame's status (single-corpus 422; LLM / AssemblyError 502; else 500).
- Receipts: `_receipt_payload` builds one payload per turn inside the generator (`meta.route`); the transport's sink adds `kind` / `client` (stream: `chat_stream` / `ui-stream`; `/chat`: `chat` / user-agent; bare `run_chat`: `chat` / None). In-band error frames now receipt too.
- CHAT-REQUEST-MAP-V1 (`chat.stream_request`): message, corpus_id, corpus_ids, workspace, all_authorized, latent, retrieval, compiler, reasoning, reasoning_blend, history, carry_context → same names; `mode` None → `resolve_chat_mode(None)` = HYBRID; `synthesizer` None → `deterministic-template-v3` on `/chat` (the historical claims/citations contract for MCP/TRAIL readers; identical when given); `utility` added to StreamChatRequest (was `/chat`-only; a set value keeps the v1 engines like `latent`); `evidence` stays the post-answer `attach_evidence_rows` add-on. ChatRequest gained synthesizer, history, carry_context, compiler, reasoning, reasoning_blend.

## Changes

- `orchestrator/orchestrator/api/ui.py`: `chat_events`, `run_chat`, `_receipt_payload`, `_error_status`; `chat_stream` = `StreamingResponse(chat_events(req))`.
- `orchestrator/orchestrator/api/chat.py`: `stream_request`, `/chat` → `run_chat`; the old dispatch deleted. `shared/polymath_shared/query_receipts.py`: `route` in the meta whitelist.
- Tests: `tests/determinism/test_chat_runtime.py` (26 pure: plan / task / resolved request / retrieval decision / evidence ids / carry / mode / degraded / synthesis contract identical on both routes with the compiler off and in shadow; error status parity; frame snapshot; MCP `ask` posts to `/chat`) + 1 live parity test (skips when :7200 is unreachable); `test_chat_hygiene.py`: one assertion that counted the deleted dispatch's three return sites replaced by a runtime-shape assertion.
- Integrator fix (observable degradation, §3.16): the engine's deadline receipts (`<lane>_timeout`, `rerank_timeout`, `embed_deadline`, `graph_degraded`, `wildcard`) were visible only in the `retrieve_done` phase event; the answer event's `retrieval.degraded`, the `/chat` JSON and the query receipt carried `degradations()` alone, so a turn whose judge timed out was receipted `degraded: []`. `_merged_degraded(fast, stale)` (ui.py) now merges them, one entry per component; `test_engine_deadline_receipts_ride_the_degraded_list_on_both_routes_and_in_the_receipt` pins it on both transports and in the receipt.
- Implemented by a worktree agent (commit 03ce847 on agent/p1f-runtime, cherry-picked e3a2307) from the handoff draft as design input; re-verified by the integrator (93 tests across runtime/hygiene/modes/receipts + 45 contracts after the cherry-pick).

## Proof

**Offline parity suite:** 101 offline tests green — test_chat_runtime (27 pure parity tests, including the new degraded-receipt test) + test_chat_hygiene + test_chat_modes + 45 contract tests (-k 'not live', 2026-09-06 10:40Z); 93 + 45 right after the cherry-pick.

**Live parity test** (`tests/determinism/test_chat_runtime.py -k live`, real :7200 on the integrated code): PASSED 2026-09-06 10:42Z on the respawned orchestrator (pid 80880): identical runtime tag, mode, engine, chat_plan, legend chunk ids, chunk locators, used_evidence and citations on /chat and /chat/stream (the 10:29Z attempt skipped because /ready exceeded the test's 3 s probe right after a respawn; the 10:35Z rerun also passed).

**Route-parity probe (`chat-parity-p1f`, 10 fixture-B questions, the same request through `/chat` and `/chat/stream`, mode HYBRID, compiler off, `deterministic-template-v3`):** mode mismatches **0**, plan mismatches **0**; evidence-id mismatches 2 of 10 — on the **2 clean pairs** (no deadline receipt on either side, no sidecar OOM split inside the pair's window) **0**, on the other pairs 2 (explained: a judge deadline on one side keeps fusion order, an OOM-split rerank batch reorders near-ties — receipted components seen ['embed_deadline', 'rerank_timeout']); degraded-state mismatches 5; `runtime` reported by `/chat`: ['chat-runtime-v1']; modes seen ['HYBRID']; engines ['chat-retrieval-v2']; evidence rows per turn (chat vs stream) [(15, 15), (15, 15), (15, 15), (15, 15), (15, 15), (15, 15), (15, 15), (15, 15), (15, 15), (15, 15)]; wall p50 `/chat` 18.7 s vs `/chat/stream` 14.8 s (sequential, under enrichment contention — transport only; the second call of each pair benefits from warm caches).

**First probe (before the degraded-receipt fix, `chat-parity-p1f-first`):** evidence-id mismatches 2 of 10 with `retrieval.degraded` empty on every turn — the receipts could not say why (the /chat call of one pair ran 34 s with the judge past its 8 s deadline → fusion order; the reranker logged OOM splits at 8 → 4 pairs inside both mismatching windows). Fix: the engine's deadline receipts now ride `retrieval.degraded` on both routes and in the query receipt (`_merged_degraded`, one entry per component; parity test added).

Gate — *same plan + same evidence ids for the same request on all routes*: **MET** (clean pairs 2 / 10: 0 evidence mismatches; mode 0, plan 0; the offline suite pins plan, task type, resolved request, retrieval decision, evidence ids, carry, mode, degraded state and synthesis contract on both routes).

## Rejected claims

- "Keep `/chat`'s own dispatch as a compatibility path." Rejected: two paths is the defect the phase removes; behaviour differences are receipted as 422s or documented defaults, not preserved.
- "Make `/chat` default to the LLM synthesizer like the UI." Rejected: `/chat` is the machine route (MCP, TRAIL); its deterministic default is a documented contract; identical when the caller specifies the synthesizer.

## Open contract gaps

1. `mode: LEGACY` is no longer reachable from `/chat` (422 `unknown_mode`); `/retrieve` keeps LEGACY.
2. Multi-corpus FAST on `/chat` returns 422 `mode_requires_single_corpus` (the runtime is single-corpus, like the stream).
3. Pre-existing, not fixed: the runtime's ASK path calls `ask(AskRequest(...))` but `ask(req, request)` requires the Request → ASK mode errors on both routes (P1.g's absent-term case uses the stream's abstention, not ASK).
4. The frontend still reads the stream only; nothing changed there.
5. **Parity is asserted on clean pairs.** Two sequential calls of the SAME route are not identical under enrichment contention: a judge past its deadline keeps fusion order on one call (now receipted `rerank_timeout`), and an MLX OOM split (8 → 4 pairs) changes the batch composition and reorders near-tie scores — invisible to the engine (the sidecar retries silently and returns scores). The probe therefore reads the sidecar log for OOM lines inside each pair's window and reports evidence mismatches on clean pairs (the gate) separately from explained ones. A sidecar-side receipt for an OOM-halved batch (a header on the rerank response) would make the second cause visible in-band — one line in the sidecar, not done here.
