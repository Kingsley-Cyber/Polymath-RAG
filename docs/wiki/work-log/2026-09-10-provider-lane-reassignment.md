---
title: "WORK LOG — Provider lane reassignment: Google→graph, Groq split (1 doc-profile / 5 pMAP), Alibaba+Ollama compiler ring, OpenRouter fallbacks"
change_id: PROVIDER-LANE-REASSIGNMENT-V1
date: 2026-09-10
owner: governance (owner-directed API-env reconfiguration)
last_reviewed: 2026-09-10
status: complete (config written + validated; takes effect on next fleet bounce; NOT bounced)
register: 11.193
package: "config/cloud_providers.json + config/extraction_models/limiter.yaml (+ local .env OLLAMA_API_KEY, gitignored)"
architecture_impact: "Provider→function lane reassignment only (no code, no retrieval architecture change). Graph extraction = all Google (gemini*) + NVIDIA + SiliconFlow; doc_profile = 1 Groq key (compound) + OpenRouter fallback; pMAP = 5 Groq keys (compound-mini) + OpenRouter fallback; chat compiler = Alibaba-direct (compatible-mode) + Ollama gemma + OpenRouter backstop. De-shares the 6 Groq accounts (was doc_profile+pMAP shared). Inert until boot_polymath.sh; running fleet unchanged. Respects the cinema forensic hold (no backfill resumed)."
---

> **Ledger:** owner /goal API-env reconfiguration 2026-09-10. Register **11.193**. Config only; validated; not bounced.

## Contract

Requested outcome (owner): reassign which provider/account serves which function — all Google models to graph
extraction; 1 Groq key to document-level (doc_profile); the other 5 Groq keys to pMAP; an OpenRouter fallback for
each Groq function; the chat compiler off Google (any pool model with a fallback ring across chat models).

- **Acceptance:** every stage pin resolves to ACTIVE endpoints (no dark lane / `PinnedProviderUnavailable`); the
  graph unpinned ring = Google + NVIDIA + SiliconFlow; `bundle_integrity` READY; guards green.
- **Persistence:** two tracked config files; a local gitignored `.env` dummy key for the no-auth Ollama lane.
- **Rollback:** `git checkout` the two config files; the change is inert until a fleet bounce.

## Changes

`config/cloud_providers.json` (stage_pins + providers) and `config/extraction_models/limiter.yaml` (seeds):

- **Graph extraction** (unpinned ring) = `gemini1–6` + `gemini1b–6b` (all Google) + `nvidia`,`nvidia2` +
  `siliconflow1–3`. Achieved by removing `gemini5/5b/6/6b` from the legacy `parent_enrichment` pin and disabling
  the duplicate Gemini lanes (`compiler1–4`, `profile_fallback_gemini1/2`) that rode the same keys.
- **doc_profile** = `profile_groq1` (GROQ_KEY_1, `groq/compound`) + `profile_fallback_openrouter`
  (`mistral-small-2603`, OPENROUTER_API_KEY_2). Disabled `profile_groq2–6`.
- **pMAP** (`doc_parent_map`) = `map_groq2–6` (GROQ_KEY_2–6, `groq/compound-mini`) + **new**
  `map_fallback_openrouter` (`mistral-small-2603`, OPENROUTER_API_KEY_3, MAP DSL / json_mode off). Disabled
  `map_groq1`. This DE-SHARES the Groq accounts: KEY_1 = doc_profile only, KEY_2–6 = pMAP only.
- **Chat compiler** (`chat_compiler`) = **new** `compiler_alibaba_qwen` (Alibaba token-plan compatible-mode
  `qwen3.8-flash`) → `compiler_alibaba_deepseek` (`deepseek-v4-flash-0731`) → `compiler_ollama_gemma`
  (local Ollama `gemma4:31b-cloud`) → `compiler_alt` (OpenRouter backstop). Frees all Google for graph.
- **parent_enrichment** (legacy) = `openrouter1/2/3/5` only (Gemini removed).

## Proof

- **Endpoint reachability pre-verified** (raw + through the real `LLMExtractionClient`, `max_attempts=1`):
  Alibaba compatible-mode `qwen3.8-flash` + `deepseek-v4-flash-0731` → clean `{"ok":true}`; Ollama
  `gemma4:31b-cloud` → JSON (fenced); OpenRouter existing. **OpenCode is Cloudflare-blocked (403/1010) for the
  raw client** — usable only via the synthesizer's litellm — so it is NOT a compiler lane.
- **Config validation:** all 4 pins resolve to ACTIVE endpoints (0 dark); the graph ring is exactly
  Google + NVIDIA + SiliconFlow (+ the pre-existing `primary` default lane). `bundle_integrity` READY (the two
  config files are not part of the 8-file hashed semantic bundle). `repo_guard` ok.
- Alibaba key note: the OpenAI door is `…/compatible-mode/v1` (distinct from the `/apps/anthropic` litellm URL);
  standard dashscope hosts 401 the token-plan key.

## Rejected claims

- **"OpenCode can be a compiler/extraction lane."** REJECTED — Cloudflare 1010 blocks the raw client (owner
  agreed OpenCode can be used, but the direct client can't reach it; synthesizer path is unaffected).
- **"Alibaba can't do OpenAI format."** REJECTED — the token-plan's `compatible-mode/v1` works (I had only tried
  the standard dashscope host, which 401s the token-plan key).
- **"This resumes cinema pMAP."** REJECTED — lane topology only; the forensic hold + auto-mint gating are untouched.

## Open contract gaps

- **Takes effect only on `boot_polymath.sh`** (fleet bounce) — owner runs it; the running fleet still uses the old
  topology until then.
- **doc_profile is now 1 Groq key** (`compound` ≈ 1–2 profiles/min, no Groq redundancy) — fine for uploads, slow
  for a bulk re-profile; the OpenRouter fallback covers an outage, not throughput.
- **The pMAP OpenRouter fallback (`mistral-small-2603`) is unvalidated for actual MAP-DSL yield** — it's a
  last-resort lane (fires only if all 5 Groq lanes fail); a real MAP-DSL reliability check on it is a follow-up.
- The Ollama compiler lane depends on the local daemon (`127.0.0.1:11434`) being up; the ring fails over to
  Alibaba/OpenRouter if it is not.
