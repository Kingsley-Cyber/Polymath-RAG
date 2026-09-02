---
change_id: SILICONFLOW-DECOMPOSITION + CANARY-LIMITER-ISOLATION + CANARY-CALL-DECOMP
owner: governance
date: 2026-09-02
status: complete (measurements below)
architecture_impact: provider_canary.py (own limiter row per canary host; per-call decomposition output); PROVIDER-SCRUB verdict for Qwen2.5-7B split into endpoint vs model
last_reviewed: 2026-09-02
---

# WORK LOG — "150 s per call" decomposed: SiliconFlow's endpoint, not Qwen2.5-7B

## Contract
Owner (2026-09-02): the SiliconFlow Qwen2.5-7B verdict ("150–158 s per
call, FAIL") is suspect — the Mac only sends HTTP, SiliconFlow does the
inference, and the canary runs behind our own rate limiter, so the wall
time must be split into limiter wait / queue+TTFT / generation / retries
before anything is dropped. Distinguish the MODEL (7.6B dense, JSON-capable)
from the ENDPOINT (SiliconFlow serverless, FP8, JSON mode only, no
schema-constrained output).

## What the original number actually contained
The canary timed `client.extract(...)` end to end. Inside that call the
production client does: limiter `acquire` (blocking; the shared
`llm_cloud[default]` AIMD row) → HTTP POST, `stream: False`, timeout
180 s, `max_tokens` = the locked 2,500 output budget (decision 18) even
for a 61-token chunk → `sanitize`; on a malformed packet ONE retry with a
nudge (`max_attempts=2`). So a single "call" wall could be two HTTP
calls, plus limiter wait, plus retry sleep. None of that was reported.

## Changes
1. CANARY-CALL-DECOMP (`eval/v5/fleet/provider_canary.py`): every
   extraction call now prints `CALL {chunk, wall_s, limiter_wait_s,
   attempts, tokens_in, tokens_out, out_tok_per_s, finish_reason,
   result}` (limiter wait measured by wrapping the lane limiter's
   `acquire`; tok/s over wall minus limiter wait) and a `DECOMP` summary
   line; the enrichment phase prints per-call wall min/mean/max. A
   verdict now carries its own decomposition.
2. CANARY-LIMITER-ISOLATION: the canary used `limiter_key="default"`,
   which is the PRODUCTION PRIMARY lane's persisted AIMD row (pool.py:
   primary → "default"). Canary timeouts/429s against SiliconFlow, groq,
   etc. halved production's concurrency on that row (`llm_controller_
   state` shows 23 decreases on `llm_cloud[default]`). Each canary host
   now keys `canary:<netloc>` — its own row, production untouched.

## Proof
- STREAMING BASELINE (same prompt, same 7.6B model, temp 0.7, 900
  max_tokens, measured with a raw streaming client — no limiter, no
  client, no retry):

  | endpoint | TTFT | generation | output tok/s | total |
  |---|---|---|---|---|
  | SiliconFlow serverless `Qwen/Qwen2.5-7B-Instruct` | **37.25 s** | 56.2 s for 900 tok | **16.0** | 93.4 s |
  | OpenRouter `qwen/qwen-2.5-7b-instruct` (same model) | **0.38 s** | 12.2 s for 900 tok | **73.9** | 12.6 s |

  Arithmetic for the original canary: 37 s queue + 2,500 tokens ÷ 16 tok/s
  = ~193 s per HTTP call when the model runs to the output cap — beyond
  the client's 180 s timeout; a retry doubles it. The "150–158 s" was
  the endpoint's queue plus slow decode, not a Mac problem and not the
  model's size.
- PROBE B2 — STREAMING REPLAY OF THE CLIENT'S EXACT EXTRACTION PAYLOAD
  (captured from the production client: system prompt + chunk, temp 0,
  max_tokens 2,500; schema and json modes; the canary's 61-token and
  221-token chunks; 8 calls concurrently):

  | endpoint / mode / chunk | TTFT | gen | out tok | tok/s | finish | JSON | total |
  |---|---|---|---|---|---|---|---|
  | SiliconFlow schema 61 tok | 29.6 s | 24.8 s | 433 | 17.5 | stop | valid, text corrupted ("ThisD was designedD toD") | 54.4 s |
  | SiliconFlow schema 221 tok | 29.0 s | 136.0 s | 2,500 | 18.4 | **length** | invalid ("pololmamDh-extraction-v1t") | 165.0 s |
  | SiliconFlow json 61 tok | 29.5 s | 135.9 s | 2,500 | 18.4 | **length** | invalid | 165.4 s |
  | SiliconFlow json 221 tok | 29.5 s | 135.9 s | 2,500 | 18.4 | **length** | invalid ("polology-extraction-vttract") | 165.3 s |
  | OpenRouter schema 61 tok | 0.47 s | 3.3 s | 177 | 53.9 | stop | valid, sane | 3.8 s |
  | OpenRouter schema 221 tok | 0.48 s | 9.1 s | 502 | 54.9 | stop | valid, sane | 9.6 s |
  | OpenRouter json 61 tok | 0.48 s | 3.6 s | 189 | 52.3 | stop | valid, sane | 4.1 s |
  | OpenRouter json 221 tok | 0.46 s | 7.9 s | 433 | 55.0 | stop | valid, sane | 8.3 s |

  Reading: the original 150–158 s = ~30 s provider queue (TTFT is
  identical on every call, so it is a queue, not prefill) + 2,500
  tokens at ~18 tok/s (136 s) because the endpoint's output DEGENERATES
  (token corruption — "D" insertions, misspelled contract ids — a
  serving/quantization fault, not a 7B capability limit) and runs to
  the cap. The same weights via OpenRouter answer the same packet
  cleanly in 4–10 s. No limiter, no Mac, no retry in this measurement.
- PROBE A (real client path, limiter waits timed) and the OpenRouter
  production canary of the same model: appended below when they land.

## Rejected claims
- "The Mac is slow" — the Mac sends one HTTP request; every second is
  spent at the provider or in our own limiter/retry.
- "Qwen2.5-7B cannot do extraction" — untested by the SiliconFlow run;
  the same weights answer at 74 tok/s elsewhere. The model stays in
  evaluation; the SiliconFlow serverless endpoint is what is dropped.
- Resetting `llm_cloud[default]` by hand — AIMD climbs back +1 per 8
  clean successes; the fix is isolation, not a state edit.

## Open contract gaps
- The client's non-streaming POST cannot separate TTFT from generation
  in production receipts; only the canary's streaming probe can. A
  `stream_options`-based TTFT receipt in the client is a later change.
