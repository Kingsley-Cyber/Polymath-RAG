---
title: "WORK LOG — PROVIDER-ATTEMPT-LEDGER-V4: chat synthesis was an unrecorded provider seam, and the ledger could not express why"
change_id: PROVIDER-ATTEMPT-LEDGER-V4
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
architecture_impact: "additive: migration 0059 adds one nullable-by-default column (limiter_bypassed); recording added to four chat/probe seams; attempt_ordinal is now derived in SQL instead of counted in a contextvar; attempt_context inherits its correlation id; attempt_summary stops inflating failover with uncorrelated rows; two of §15's five named detections implemented. No data rewritten, nothing dropped. Touches shared/ and orchestrator/, so it needs a fleet bounce."
register: 11.238
---

> §15 says "each external model attempt". The ledger covered extraction and the query
> compiler. Every answer the product produces is an external model attempt too.

## Contract

§15 DURABLE ATTEMPT TELEMETRY across every external-model seam, plus the detections §15
names by name: `UNACCOUNTED_ATTEMPT`, `HIDDEN_429`, `LIMITER_BYPASS`,
`CONFIG/LIVE_MISMATCH`, `DARK_ENABLED_LANE`.

## Changes

**What the V3 seam gate could not see.** V3's gate scanned `LLMExtractionClient` only,
and said so. Widening the question to "what else dispatches to an external model?" found
three modules with HTTP dispatch in the whole repository, and the interesting one was the
chat path:

| seam | what it dispatches | recorded before |
|---|---|---|
| `ui.py:_litellm_generate` | answer synthesis on **paid** models (`anthropic/deepseek-v4-flash-0731`, …) | ❌ |
| `ui.py:llm_test` | one-shot credential/connectivity test | ❌ |
| `ui.py:_ollama_generate` | answer synthesis via the local daemon | ❌ |
| `ui.py:_ollama_stream_plain` | the `think`-rejected retry of the above | ❌ |
| `client.py:probe` | lane liveness/auth | ❌ (V3 excluded it, with a reason) |

The Ollama pair looked excludable as "local, no quota". It is not: **every model in this
host's Ollama catalog is `*-cloud`** — `gemma4:31b-cloud`, `deepseek-v4-flash:cloud`,
`qwen3.5:397b-cloud`, twelve of twelve. The daemon is local; the inference is not.
Excluding that seam would have been true of the hop and false of the spend.

**Why they were unrecordable, not merely unrecorded.** Migration 0056 documents
`limiter_admitted = false => zero HTTP, zero quota`. None of these seams passes a lane
limiter, so `false` would assert "no quota spent" about a paid call and `true` would
assert an admission that never happened. **Migration 0059** adds `limiter_bypassed`
(additive, `DEFAULT false`, every existing row correctly false) so the ledger can say
"not applicable" instead of guessing — and `attempt_summary` now reads refusals as
`NOT limiter_admitted AND NOT limiter_bypassed`.

**One row per dispatch, from a generator with four exits.** A stream ends at `done`, at
an error chunk, at a non-200, or at an exception. Recording at each exit duplicates or
drops the row, so `_AttemptOutcome` marks outcomes and writes exactly once on the way
out, in a `with` block — including when the client disconnects mid-stream, which is
recorded honestly as `INCOMPLETE_STREAM` rather than as a success.

**Two counting bugs the live probe then exposed**, neither visible from unit tests:

1. **Every attempt of one logical call was `attempt_ordinal = 1`.** `attempt_context`
   minted a fresh correlation id per context and counted the ordinal in a contextvar; a
   nested or sibling context (the `think` retry opens a second `_AttemptOutcome` inside
   the first) reset the token on exit and discarded the increment. Fixed twice over: the
   correlation id is **inherited** — only the outermost context mints one — and the
   ordinal is **derived in SQL** (`MAX(attempt_ordinal)+1` for that correlation), which
   also survives attempts that span threads or processes.
2. **`failover_attempts` was inflated by untagged rows.** It is `attempts - logical
   calls`, and `COUNT(DISTINCT correlation_id)` ignores NULLs — so a seam that merely
   forgot its `attempt_context` looked exactly like heavy provider failover. Measured
   live: `attempts=22, logical_calls=6, uncorrelated=14` read as **failover=16**; the
   true figure was **2**. Now computed over correlated rows only, with
   `uncorrelated_attempts` reported as its own number.

**Two of §15's five named detections implemented** in `reconcile()`, which previously had
`HIDDEN_429` and two of its own:

- `LIMITER_BYPASS` — now that the state is expressible, reported as an observation with
  its lanes, not as a fault: probe and synthesis bypass by design. A lane appearing here
  that is supposed to be limiter-mediated is the fault, and naming lanes is what makes
  that visible.
- `DARK_ENABLED_LANE` — enabled and credentialled in the registry, yet no attempt in the
  window. Dead weight in the rotation, or nothing upstream is selecting it; invisible
  from outcome counters either way.

**The gate follows the code.** `attempt_ledger_covers_every_provider_seam` now iterates a
list of modules, each with the call shapes that count as a dispatch there, and reports
NOT_TESTED (never a vacuous PASS) if any named module cannot be parsed.

## Proof

**1 — live, zero spend.** Two `_AttemptOutcome` blocks inside one `attempt_context`,
dispatching nowhere:

```
ordinal=1 success=False error=ConnectError bypassed=True
ordinal=2 success=True  error=None         bypassed=True
summary: refused=0 bypassed=6 failover=2 logical_calls=6 attempts=22 uncorrelated=14
```

Ordinals sequence across sibling contexts, bypass rows persist, refusals are untouched,
and failover reads 2 rather than the 16 the old arithmetic gave on the same rows.

**2 — 25 tests green** across three files, including: a stream that never finished is not
a success; exactly one row per dispatch however many markers are set; the bound-retry
loop records **both** attempts (§15's example, in chat); a probe 429 keeps its
`Retry-After`; nested contexts share one correlation id; and failover arithmetic with and
without uncorrelated rows.

**3 — the gate still fails on the bug it exists for**, and now also reports NOT_TESTED
when a module it names is missing — the way a static gate usually dies is by having its
target renamed and passing forever.

**4 — live gate output:** both attempt gates PASS, 8 recording seams across 2 modules,
3 exclusions printed with reasons.

## Rejected claims

- **"Ollama is local, so it is out of §15's scope."** Rejected on measurement: the
  catalog is 12 cloud models and 0 local ones.
- **"Record synthesis as `limiter_admitted=false`."** Rejected: 0056 documents that as
  "zero HTTP, zero quota", which is false of a paid call. Adding a column beat writing a
  false row.
- **"failover=16 is real provider pressure."** Rejected after tracing it: 14 of those
  were rows with no correlation id at all.
- **"The live synthesis test failure is mine."** Rejected on evidence: it passed twice in
  isolation, and the orchestrator was still running the pre-change module, so the new
  code had not executed when it failed. Re-run live after the bounce.

## Open contract gaps

- **`CONFIG/LIVE_MISMATCH`** — the third of §15's five detections, still unimplemented.
- **`response_hash`** is still never set.
- **Chat synthesis rows are wiring-proven, not traffic-proven** — a real synthesis
  attempt costs provider spend, so the live evidence here is the connect-refused path and
  the unit tests; the first real chat answer after the bounce populates the rest.
