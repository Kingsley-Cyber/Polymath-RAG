---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 05 — Unfinished Work

Priority order. Each: problem · why · FILE:SYMBOL · dependency · acceptance · next step.

## P0 — Groq quota topology unverified (gates cinema resume)
- **Problem:** whether `groq/compound` and `groq/compound-mini` share one account RPD, and the real per-account RPD, is UNVERIFIED. Config "RPD 250" (local cap 230) is an assumption never reconciled to a Groq header.
- **Why:** local RPD is per-lane (2×230=460/account) vs one real account quota → over-admission; blocks a trustworthy resume.
- **FILE:** `limiter.py:_observe_provider_rpd_locked` (now records provider RPD once headers are observed).
- **Dependency:** owner-authorized bounded live probe (spend).
- **Acceptance:** captured `x-ratelimit-*-requests` on 2xx for compound + compound-mini on ≥2 accounts; sharing question answered; account isolation confirmed.
- **Next:** `07_NEXT_ACTION.md`.

## P0 — MAP-batch efficiency benchmark (15/20/30/40/60)
- **Problem:** `MAP_RELIABILITY_CAP=15` is a measured compound-mini envelope; the valid-maps-per-request curve at 20/30/40/60 is unmeasured.
- **FILE:** `map_batches.py:MAP_RELIABILITY_CAP`, `map_batches.py:mapping_only_capacity`.
- **Dependency:** live spend (after topology probe).
- **Acceptance:** per-batch-size complete-response rate + persisted-maps/request; pick the efficiency-optimal cap.

## P1 — No full-pipeline `/upload`→semantic-ready timed canary exists (0/3)
- **Problem:** only STAGE canaries exist (`parent_map_canary`, `profile_vnext_canary`, `profile_atom_canary`, `chat_compiler_canary`, `siliconflow_extraction_canary`, `shadow_route_canary`). The directive's end-to-end 3–5 KB `/upload`→semantic-ready(<4min)×3 canary is **unbuilt**.
- **Why:** can't prove pipeline stability or locate where minutes go.
- **Acceptance:** a script that uploads a unique ~4 KB structured file via the canonical `/upload`, times to VNEXT semantic-ready, emits run-scoped diagnostics, FAILs at 4 min; 3 consecutive unique passes.
- **Next:** build after P0 (needs the pipeline actually draining, which needs Groq resume).

## P1 — Run-scoped diagnostics gap
- **Problem:** can't currently attribute where a 4-minute pipeline run's time went (per-stage timeline, lane, HTTP dispatch, refusal-by-reason). The limiter now emits reasons; the pipeline doesn't aggregate a run timeline.
- **Acceptance:** a run_id-scoped timeline (stage → queue/ticket transitions → lane → dispatch/refusal counts → blocker). Never log secrets.

## P2 — Deterministic pMAP grounding (`DocumentGroundingContextV1`) not built
- **Problem:** pMAP maps each section blind to the document; the `is_combined` combined-profile+MAP path is a no-op.
- **FILE:** `map_prompt.py:build_map_prompt` (is_combined), `map_batches.py:combined_capacity`.
- **Acceptance:** CPU-only, ~50–100 tok, versioned, no-LLM grounding header fed into the MAP prompt; measurably better signature discriminativeness; re-map gated by owner.

## P2 — Functional-pool drain invariant unverified for graph extraction
- **Problem:** confirm a rate-limited/circuit-open lane's work is re-claimable by a healthy lane (pool-owned, not lane-owned). `worker_runtime._is_provider_capacity` treats 429/LIMITER_REFUSED as capacity (no attempt burn), but end-to-end requeue-across-lanes isn't proven by a test.
- **Acceptance:** a test where lane A fails transiently and lane B drains the same job.

## P3 — Housekeeping
- 4 local commits (control-plane repair) are **unpushed** to origin.
- graphify doc-semantic layer stale (2026-09-01); `limiter.yaml` change not in graph (YAML=doc-category).
- `test_fact_endpoint_eligibility::test_no_active_fact_has_a_pronoun_endpoint` fails on live data (pronoun-endpoint facts exist) — separate data-hygiene task.
- Gemini extract lanes don't explicitly disable thinking (token-efficiency; verify).
- legacy `parent_enrichment` retirement gated on proven vNext replacement readers (S13–S18).
