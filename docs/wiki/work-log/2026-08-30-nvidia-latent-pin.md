---
change_id: NVIDIA-LATENT-PIN-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: config (cloud_providers.json, limiter.yaml) + client per-provider limiter seeds; NVIDIA live in the pool, dedicated to parent_enrichment
last_reviewed: 2026-08-30
---

# WORK LOG — NVIDIA-LATENT-PIN-V1 (dedicated enrichment provider, live)

## Contract
Owner 2026-08-30: NVIDIA is the dedicated provider endpoint for
enrichment; then the explicit spec: model
`nvidia/nemotron-3.5-lightning-30b-a3b`, thinking OFF, temperature 0,
JSON mode ON, tightly bounded output, worker-controlled concurrency,
~35–38 RPM initially, 429 exponential backoff.

## Changes
- NVIDIA_API_KEY (owner-provided) in the gitignored `.env` — auto-gate
  activated the provider with no restart; roster groq+nvidia+primary.
- First pin `meta/llama-3.3-70b-instruct` was 410 GONE (same stale-pin
  class as Groq's llama-3.3); account model list fetched live.
- Thinking-knob probe on NIM nemotron (measured, one-token JSON task):
  baseline → finish:length, pure thinking; `reasoning_effort:"low"` →
  503; **`reasoning_effort:"none"` → finish:stop clean JSON**;
  `chat_template_kwargs thinking:false` also works; `/no_think` system
  prompt does NOT. Config carries `"reasoning_effort": "none"`.
- Owner overrode the interim super-120b pick mid-verification →
  `nemotron-3.5-lightning-30b-a3b` pinned per spec.
- Per-provider limiter seeds: `_lane_limit(lane, provider)` reads a
  limiter.yaml block matching the endpoint name — `nvidia:` rpm 36,
  conc_cap 4 (worker-controlled), `groq:` rpm 30 (free-tier reality);
  unmatched endpoints inherit ollama_cloud. 429 exponential backoff =
  the existing AIMD (x0.5 on 429/503, Retry-After honored, header
  sync) — no new retry machinery.

## Proof
- Probe: groq 397 ms / nvidia 2080 ms / primary 1186 ms — all OK.
- Canary through `select_endpoint_for_stage("parent_enrichment", …)`:
  pinned endpoint returned, sanitize ok=True, 4 ontology-conform
  relations, 358 output tokens (no thinking burn), limiter live-seeded
  rpm 36 / conc_cap 4.
- test_extraction_pool.py 13/13; determinism suite at the 8-failure
  pre-existing baseline.

## Rejected claims
- "reasoning_effort low is enough" — 503'd on NIM during the probe and
  is semantically wrong anyway: the owner spec is thinking OFF; "none"
  is the verified knob.

## Open contract gaps
- Lightning yielded 0 ENTITIES on the extraction-schema canary
  (relations fine). Its dedicated role is the enrichment schema, so no
  action now — but Phase B qualification MUST canary
  parent-enrichment-v1 on this exact model before corpus-wide spend.
- RPM 36 is a seed; watch the AIMD lane on the first real enrichment
  batch and re-seed limiter.yaml if NIM headers disagree.
