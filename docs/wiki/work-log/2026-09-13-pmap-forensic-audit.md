---
title: "WORK LOG — PMAP-FORENSIC-AUDIT-V1: the 15-cap is not a model ceiling; parents disappear at the provider (TPD 100k/org + EMPTY 200s), not at truncation/compiler/persistence"
change_id: PMAP-FORENSIC-AUDIT-V1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.253
architecture_impact: "No production change. Read-only forensic audit of the Parent-MAP request path with byte-identical production requests and full raw provider capture. Locates the failure boundary (provider stage: daily-token exhaustion + intermittent EMPTY 200s, amplified by ~5× hidden completion and a ~5× local token undercount). Specifies the deterministic fix; does not apply it. Supersedes the causal reading of 11.251 (the 35/50 collapse was budget-state-dependent, not an inherent ceiling)."
---

> Owner: take over the Parent-MAP forensic audit. Treat code, commits, receipts, provider responses and
> actual outbound requests as authoritative. Do not speculate when it can be proven. Establish the
> conservation chain requested → admitted → dispatched → tokens → content → MAP lines → compiled →
> persisted → credited, and find exactly where parents disappear. Only then change the system.

## Contract
The 15-parent cap (`MAP_RELIABILITY_CAP`, commit `20b54083`, 2026-09-08) was disputed as unproven. The
leading hypothesis was an artificial output-token limit (~1200–2400) masquerading as a model ceiling. The
audit had to trace the real request, prove every outbound field from provider truth, and classify every
loss into one evidence-backed category — without touching the frozen DSL/compiler or the production request.

## Changes
- **None to production.** Requests were captured by intercepting `httpx.post` in the client module to
  *record* payload + full response; nothing sent was altered. Diagnostic arms (tools-off, `reasoning_effort`)
  injected a single extra key each and are labelled as such.
- **Evidence preserved** in `docs/wiki/experiments/pmap-forensic-audit-2026-09-13/` — the 15-section
  report (`README.md`) plus `run1-*.json` and `run2-*.json` holding raw bodies, usage, headers, and
  per-request compiler re-runs (credential scan clean).

## Proof
- **Exact outbound request:** `{model, messages, temperature 0.0, max_tokens 2400, stream false}` — nothing
  else (`request_keys` captured every call). `max_tokens=2400` originates from `doc_parent_map_stage_worker.py:54
  MAX_MAP_TOKENS` and the literal at `parent_map_backfill.py:89`; the planner's 6500 never reaches HTTP.
- **Truncation disproven:** `finish_reason=stop` on every 2xx; `completion_tokens` exceeded 2400 with
  `stop` at N=20/30/40/50 (2723/3033/3628/4010). Corroborates the 09-08 record (EMPTY even at `max_tokens=8000`).
- **Batch 40 works:** production request, fresh-budget lane → **40/40 MAP lines, 0 rejections, 40 persisted**.
- **Provider substrate + ceiling:** 429 bodies name `llama-3.3-70b-versatile`; `Limit 100000, Used 99497` →
  **TPD 100k/org** is binding (RPD 250, TPM 70k slack). ~6.1k tokens per 15-parent request → ~16 req/day/org.
- **EMPTY captured live:** N=50 repair (21 aliases) → `200, stop, 3420 completion tokens, 0 content` on a lane at
  98,114/100,000 TPD. `executed_tools` absent; `reasoning` present but empty → hidden orchestration, not tools.
- **Model cliff (real, partial not truncation):** N=50 primary emitted P0001–P0030 then stopped (`stop`).
- **Compiler/persistence lossless:** one `empty_signature` in the whole audit; compiled == readback == credited.
- **Limiter invariant holds:** 24h, all lanes: LIMITER_REFUSED 0, refused-but-dispatched 0.
- **Six keys = six budgets:** per-key probes show distinct `remaining-requests` and reset clocks.
- **Accounting defects measured:** admission uses `len(user)/4` (no system prompt, no completion) → ~5×
  undercount (est ~1181 vs actual 6092); chars/token is ~1.56 not 4; input density ~250–270/parent vs 135.7.
- **Compound-mini rejects `reasoning_effort`:** HTTP 400 "not supported with this model" — explains the
  lane spec's `reasoning_effort: null`; reasoning control is unavailable by that parameter.
- **Second cap location:** lane-level `map_batch_cap: 15` is live (`lane_registry.py:86-95`, pool cap = MIN
  over lanes) — raising the planner alone would not raise the pool.

## Rejected claims
- **"An artificial output ceiling caused the 15-limit"** — DISPROVEN (no `finish=length`; completion > cap with `stop`).
- **"Compound-mini's tool router fires and empties the output"** — DISPROVEN (`executed_tools` never present, including on the EMPTY response).
- **"json_mode is wrongly on"** — DISPROVEN (`json_mode:false`, `structured:text`; `response_format` omitted).
- **"The compiler / persistence lose parents"** — DISPROVEN (G≈0, H=I=0).
- **"The six keys share one org budget"** — DISPROVEN (distinct per-key remaining/reset).
- **"≥25 aliases is inherently unreliable" (the 11.178 / 11.251 reading)** — DISPROVEN as stated: 40/40 under
  fresh budget. The 35/50 collapse in 11.251 ran under heavy TPD burn and is re-read as budget-state-dependent
  EMPTY/partial, not a fixed ceiling. A real cliff exists between 40 and 50 (single sample).
- **Run1 sizes 30–60 and arm B** — REJECTED as evidence: a harness defect (fresh round-robin closure per size)
  routed every request to the TPD-exhausted `map_groq2`. Corrected in run2; recorded, not hidden.

## Open contract gaps
- **Repeats are required before promotion.** All size results are single samples; today's active lanes' TPD is
  spent. Re-run ≥5 samples/size across fresh-budget lanes (EMPTY ≤5%, missing ≤2%) before raising the cap.
- **The deterministic fix is specified, not applied** (report §13): real-token admission + declared `tpd` per
  lane with pacing; cap → 40 in **both** `MAP_RELIABILITY_CAP` and each lane's `map_batch_cap` (+ planner
  version bump); persist `finish_reason`/`content_empty`/`usage` on the §15 Attempt and treat EMPTY 200 as a
  provider fault with backoff; source `max_tokens` from the planner; enforce `request_char_budget` on the map
  path (pre-empt the 413 at ~60). Touches `shared/` + `workers/` + config → fence + bounce; owner gate.
- **Reasoning-overhead control** for compound-mini remains unexplored beyond `reasoning_effort` (rejected);
  `reasoning_format`/`include_reasoning` untested (budget). The only proven throughput lever is provider capacity.
