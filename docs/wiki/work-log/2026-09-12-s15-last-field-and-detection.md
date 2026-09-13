---
title: "WORK LOG — §15's last unset field and last unimplemented detection"
change_id: PROVIDER-ATTEMPT-LEDGER-V5
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.241
architecture_impact: "additive: `response_hash` is now set at all seven success seams (streamed answers hashed incrementally, nothing buffered), and `CONFIG/LIVE_MISMATCH` is implemented in reconcile(). No schema change. Touches shared/ and orchestrator/, so it needs a fleet bounce."
---

> The two gaps 11.238 and 11.239 named as explicitly NOT closed.

## Contract

§15's field list — `response_hash` among them — and its five named detections:
`UNACCOUNTED_ATTEMPT`, `HIDDEN_429`, `LIMITER_BYPASS`, `CONFIG/LIVE_MISMATCH`,
`DARK_ENABLED_LANE`.

## Changes

**`response_hash`, NULL on every row since the ledger landed.** It is what makes two
attempts comparable without keeping the response: a lane returning the SAME body for
different prompts — a stuck model, a cached edge, a provider serving an error page with
HTTP 200 — is invisible in status codes and obvious in a repeated hash. Now set at every
success seam:

| seam | hashed |
|---|---|
| `complete_one` | the completion text |
| `_extract_prompt` | the raw completion |
| `_infer_batch_call` | the batch body |
| `complete_batched.run` | the batch body |
| `probe` | the served model |
| `_AttemptOutcome` (Ollama synthesis) | the stream, hashed INCREMENTALLY |
| `_litellm_generate` | the stream, hashed incrementally per attempt |

Streamed answers update a `sha256` as pieces arrive, so nothing is buffered to hash it.
An EMPTY answer records `NULL`, not `sha256("")` — recording the empty digest would make
every empty answer look identical to every other, a match that means nothing.

**`CONFIG/LIVE_MISMATCH`, the fifth detection.** Config is a claim about what the system
will do; the ledger records what it did. Two divergences, neither visible from either
side alone:

- a lane that DISPATCHED but the registry does not contain (live > config);
- a lane whose configured model is not the model its attempts carried — a stage pin that
  never took effect, or a provider substituting silently.

`chat_synth:*` is excluded by construction: those are synthesis seams, not registry
lanes.

## Proof

**All five §15 detections now produce real findings against the live ledger:**

```
FAILOVER_ATTEMPTS     2 extra attempt(s) beyond the 19 logical calls
LIMITER_BYPASS        24 attempt(s) reached a provider without limiter admission,
                      on: chat_synth:anthropic×18, chat_synth:ollama×5, dbg×1
DARK_ENABLED_LANE     31 enabled, credentialled lane(s) made no attempt in 24 hours:
                      compiler_alibaba_deepseek, gemini1, gemini1b, gemini2, …
CONFIG/LIVE_MISMATCH  dispatched but absent from the registry: dbg×1,
                      selftest-batch-seam×1, selftest-v3×2
```

The `CONFIG/LIVE_MISMATCH` finding is **my own probe lanes**, caught by the detection the
first time it ran — which is the detection working, not noise to curate away. Those
lanes really did dispatch and really are not configured.

**19 tests green** in the synthesis telemetry file, including: a streamed answer hashes
in stream order and matches `sha256("hello world")`; an empty answer hashes to `None`;
identical bodies hash identically and different ones do not; a ghost lane on the wire is
reported; a model substitution is reported with both sides named.

## Rejected claims

- **"Exclude the selftest lanes so CONFIG/LIVE_MISMATCH reads clean."** Rejected: the
  finding is true. Suppressing the first real thing a new detector finds, because I
  caused it, is how detectors become decoration.
- **"Buffer the answer and hash it at the end."** Rejected: the synthesis path streams
  precisely so it does not hold the answer, and a diagnostic must not change that.
- **"`DARK_ENABLED_LANE`: 31 lanes is a bug in the detection."** Not rejected — not
  investigated. Reported as an observation for the owner; 31 credentialled lanes with
  zero attempts in 24h is either a correctly parked rotation or dead weight, and the
  detection's job was to make the question askable.

## Open contract gaps

- **31 dark lanes are unexplained.** Surfaced, not diagnosed.
- `cost` is still never recorded; §15 lists it as "if available".
