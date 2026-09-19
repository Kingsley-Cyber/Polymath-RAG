---
change_id: WLK2C-C3-LIVE-WIRING
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C3-live (orchestrator, IMPLEMENTED — live proof deferred to C7; flag `POLYMATH_CHAT_BRIDGE_COMPILER` default-off ⇒ byte-identical when off). `ui.py`: `_add_bridge_expansion(plan, scout_result)` wired into `_compile_chat_plan._finish` after `_add_profile_expansion` (so tier-1 reuse sees existing subqueries) and before provenance annotation. Builds ONE bounded low-temperature cloud-Gemma JSON call (the WILDCARD path — httpx POST OLLAMA_URL/api/chat, temperature 0.1, num_predict 700, timeout 12 s, non-streaming) as the injected `generate` for `plan_bridge_expansion`. Owner failure-mode locks: FAIL-OPEN (any timeout/provider-error/malformed/empty/zero-bridge leaves the pre-WLK2C plan untouched — double-guarded by compile_bridges' try/except + the outer wrapper); hard budget (one call, ≤4 bridges, bounded timeout/tokens, only grounded nominated concepts); no duplicate expansion (tier-1 covered + compiler self-dedup + append-dedup vs q0/existing). Records the C6 metrics attempted/succeeded/generated/admitted/rejected/fallback_reason/latency_ms on plan.compiler['bridge_expansion']."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C3-live (plan-of-record C3). Wire the bounded compiler into the live compile path, after Scout
(it needs the nominations — after-Scout is correct; no artificial parallelism). Flag-gated, default-off.
The desired flow: Scout completes → eligible intent? → concepts lacking a reusable bridge? → ONE bounded
Gemma call → activation-only validation → 0 valid bridges ⇒ existing retrieval unchanged, else BRIDGE
subqueries added with lineage. C3 does NOT prove semantic goodness — a well-formed but weak bridge enters
as a BRIDGE_CANDIDATE; C4 owns the decisive bridge↔q0 rejection.

## Changes
- `orchestrator/orchestrator/api/ui.py`: `_add_bridge_expansion(plan, scout_result)` + module constants
  `_BRIDGE_MODEL` (default `gemma4:31b-cloud`, strips an `ollama:` prefix), `_BRIDGE_TIMEOUT_S` (12),
  `_BRIDGE_NUM_PREDICT` (700). The `_bridge_generate` closure = ONE `httpx.post(OLLAMA_URL/api/chat,
  stream=False, think=False, temperature=0.1, num_predict=…, timeout=…)` returning the message content.
  Calls `plan_bridge_expansion` (C3 pure); records the C6 diag; fail-open on any exception. Wired into
  `_finish` after `_add_profile_expansion`, before `annotate_subquery_provenance`.
- Register row 11.320; this work-log. No new files (no scaffold change).

## Proof
`IMPLEMENTED` — orchestrator code is NOT worktree-unit-testable (editable `.pth` resolves `orchestrator`
to MAIN under pytest); honest proof is py_compile + preflight clean now, and the C7 LIVE qualification.
`ui.py` py_compile OK; `agent_preflight`=0. Flag `POLYMATH_CHAT_BRIDGE_COMPILER` default-off ⇒ the live
`/chat` path is byte-identical (the function returns immediately). The pure logic it drives is already
UNIT_PROVEN (C0–C3, 44 tests). Verified read-side safety: `annotate_subquery_provenance` leaves
`origin=BRIDGE` intact (only promotes USER→PROFILE) and keeps scout-produced `inspired_by_profile`
links; `OLLAMA_URL` is the existing synthesizer daemon constant.

## Rejected claims
- NOT proven live yet (deferred to C7). No latency/quality numbers claimed. The Gemma call correctness
  (endpoint, JSON shape, gemma structured-output behavior) is verified only at C7 under the live fleet.
- The bridge layer is OPTIONAL and never a dependency: fail-open is double-guarded; default-off.

## Open contract gaps
`contract_impact` (ui.py) — `_add_bridge_expansion` is additive + flag-gated; no contract signature
changes (a new private helper + three env-configurable constants). The live `/chat` behavior when the
flag is OFF is unchanged (proven by the early return). Dispositions for any ui.py-mapped contract:
**TESTED_UNCHANGED** off-flag (byte-identical), **DEFERRED** on-flag to the C7 live qualification.
Deferred next: C4 (rerank latent candidates against q0 + origin_query — the semantic bridge↔q0 gate)
→ C5 (bounded DIRECT/COMPLEMENTARY/DIVERGENT roles) → C6 (surface the bridge_expansion diag in the
receipt) → C7 (merge + port-gated bounce + WLK2C qual + full CA5 64×4).
