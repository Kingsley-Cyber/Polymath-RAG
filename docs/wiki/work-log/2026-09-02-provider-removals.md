---
change_id: PROVIDER-REMOVALS-0902
owner: governance
date: 2026-09-02
status: complete
architecture_impact: fleet inventory (config/cloud_providers.json, config/extraction_models/limiter.yaml); no live lane changed
last_reviewed: 2026-09-02
---

# WORK LOG — owner removals: Qwen2.5-7B, gemma-3-4b, the groq host

## Contract
Owner (2026-09-02), after the SiliconFlow decomposition and the 7B
weakness A/B: "remove it" (Qwen2.5-7B), then "GEMMA REMOVE IT AND GROQ
REMOVE IT". Remove = out of config, out of the limiter, keys out of .env,
persisted limiter state gone, scrub/continuity/register say so.

## Changes
1. Qwen2.5-7B: never wired; scrub rows OUT; SiliconFlow key removed from
   .env (no consumer) — done in the previous commit.
2. gemma-3-4b-it @ OpenRouter: never wired (was HOLD, "paced
   extraction-only lane if wanted"); scrub row OUT; owner gate closed.
3. groq host: providers `groq1..groq5` (qwen3.8-27b, dedicated, no pin)
   removed from config/cloud_providers.json (21 → 16 providers, `_doc`
   notes it); limiter.yaml `groq` family block + `groq1..5` blocks
   removed (other provider blocks byte-identical); `GROQ_API_KEY` and
   `GROQ_API_KEY_1..5` removed from .env; `llm_controller_state` rows
   `llm_cloud[groq1..4]` deleted (AIMD counters of the removed lanes).
   The gpt-oss-20b "escape rep" goes with the host — no groq key remains.

## Proof
- Structural asserts in the edit itself: provider set difference ==
  {groq1..5}; limiter key set difference == {groq, groq1..5}; exactly 6
  .env lines removed.
- Live pool load after the edit lists no groq lane (receipt in the
  commit's terminal output); pool tests, family-interleave and
  throughput tests green (their "groq" names are hermetic fakes).
- No pipeline behavior changed: groq lanes were parked/dedicated with no
  stage pin; gemma and Qwen2.5-7B were never wired. Pipeline idle
  throughout (0 open tickets).

## Rejected claims
- Keeping one groq key for the gpt-oss-20b escape rep — the owner chose
  the whole host; an escape lane nobody trusts is not an escape lane.
- Leaving the AIMD rows "in case" — state for lanes that cannot exist is
  debris the stall tracer and operators would have to read around.

## Open contract gaps
- None for these removals. The historical work-logs and older continuity
  checkpoints still describe the 5-groq fleet as it was; they are history,
  not state.
