---
title: "WORK LOG — PROVIDER-ATTEMPT-LEDGER-V3: the batched fix covered ONE of four seams; a gate now enumerates them"
change_id: PROVIDER-ATTEMPT-LEDGER-V3
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.237
architecture_impact: "additive telemetry + one new verifier gate pair. Recording added to the two remaining provider-dispatch seams (`_extract_prompt`, `complete_batched.run`); `provider` populated at every seam; `started_at` now written as the attempt's start instead of defaulting to its insert time. No schema change, no production data mutated, no dispatch semantics changed. Touches shared/, so it requires a fleet bounce."
---

> Register 11.236 closed "the batched seam" and called it the last unmeasured clause.
> That was one seam of four. This log corrects that claim and finishes the job.

## Contract

REQUIRED FINAL STATE, DURABLE ATTEMPT TELEMETRY (§15): every provider attempt is durable
per attempt, not per logical call — and, in §15's own vocabulary, `UNACCOUNTED_ATTEMPT`
must be detectable rather than discovered by accident.

## Changes

**The audit that should have come first.** After committing 11.236 I asked the obvious
follow-up question — how many provider-dispatch seams are there? — with an AST walk over
`LLMExtractionClient` instead of a reading of the diff:

| seam | dispatches | recorded before this change |
|---|---|---|
| `complete_one` → `_chat` | 1 | ✅ (the original ledger) |
| `_infer_batch_call` | 1 | ✅ (register 11.236) |
| `_extract_prompt` → `_chat` | 1 | ❌ |
| `complete_batched.run` | 1 | ❌ |
| `probe` | 1 | ❌ (excluded by design, below) |

`_extract_prompt` is the worse of the two misses. It is the single-neighborhood
extraction path AND the documented 404 fallback from the batched path — and it contains
a **retry loop**. A 429 on attempt 1, a retry, a 200 on attempt 2, and the function
returns a successful result carrying `attempts=2` as an integer. That is §15's example
reproduced inside one function, and the 429 was durable nowhere.

`complete_batched.run` is the second batched seam — same four branches, same 500-halving
recursion, serving the non-extraction compilers.

**Four fixes.**

1. **Recording at both missed seams**, per branch, mirroring `complete_one`. In
   `_extract_prompt` the rows are written INSIDE the retry loop with a per-iteration
   clock, so a retried call writes one row per attempt rather than one per call.
2. **Vocabulary normalised.** 11.236 wrote `limiter_refused` / `http_429`;
   `complete_one` has always written `LIMITER_REFUSED` / `HTTP_429`. One table must not
   carry two spellings of one condition — that is the same class of split as recording
   `self.lane` instead of `self.limiter_key`, which 11.236 avoided and then reintroduced
   one field over. Fixed to the existing uppercase convention, and the tests that
   asserted the lowercase spelling failed loudly, which is how it was caught.
3. **`provider` populated.** §15 lists it; it was NULL on all 226 rows because no call
   site set it. It is now the netloc of the live base URL — where the request actually
   WENT, which is stronger evidence than config and carries no credential.
4. **`started_at` made honest.** The column is `DEFAULT now()` and the row is inserted
   AFTER the attempt finishes, so a column named `started_at` held the FINISH time.
   Anything measuring attempt overlap or lane pressure from it was silently inverted.
   `record` now writes `now() - latency`, which also yields §15's `finished_at` as
   `started_at + latency_ms`.

**And the durable part — a gate, not just a fix.** Two seams went unrecorded for months
because nothing enumerated them. `verify_final_state.py` gains:

- **`attempt_ledger_covers_every_provider_seam`** — AST over the client: every function
  that dispatches to a provider (directly, or through the `_chat` transport helper) must
  record. FAIL names the offenders and uses §15's own term, `UNACCOUNTED_ATTEMPT`.
  Exclusions are a printed dict with reasons, never a silent skip list:
  - `_chat` — pure transport helper; both callers record around it, so recording here
    too would double-count every attempt.
  - `probe` — liveness, not workload. It bypasses the limiter by design, so recording it
    as `limiter_admitted` would corrupt the `LIMITER_BYPASS` signal this same ledger is
    meant to detect.
- **`attempt_ledger_shape_matches_s15`** — the table carries §15's field list
  (`finished_at` derived, `cost` "if available" in the authority's own words), and the
  live row/lane/ordinal/provider-population counts are printed on PASS as well as FAIL.

## Proof

**1 — the gate FAILS on the bug it exists for.**
`tests/determinism/test_attempt_seam_coverage_gate.py` feeds the gate a doctored client
module whose new `extract_batched` dispatches without recording, and requires FAIL plus
the seam's NAME; the same module with the record added must PASS, so the gate cannot be
satisfied by always failing. 4 tests, green.

**2 — the retry loop keeps both attempts.** `test_the_retry_loop_keeps_BOTH_attempts`:
`_chat` raises 429 (Retry-After: 3) then succeeds; exactly 2 rows are recorded —
`HTTP_429 / retry_after_s=3.0 / success=False`, then `success=True / http_status=200 /
tokens (11, 7)`. Plus the compiler-seam and `provider` tests. 9 tests in the file, green.

**3 — live gate output, read-only:**

```
PASS  attempt_ledger_covers_every_provider_seam
      seams recording: 5 [complete_one(L440), _infer_batch_call(L596),
      complete_batched(L768), _extract_prompt(L867), run(L788)];
      excluded by design: _chat (...), probe (...)
PASS  attempt_ledger_shape_matches_s15
      all §15 fields present (finished_at = started_at + latency_ms; cost is
      'if available' per the authority). rows=226 lanes=4 max_ordinal=1
      provider_set=0/226 (history written before a seam/field fix keeps its
      NULLs — reported, not windowed away)
```

## Rejected claims

- **"11.236 closed DURABLE ATTEMPT TELEMETRY."** Withdrawn. It closed one seam of four.
  The register row is corrected by this one rather than edited, and the correction is
  stated in the row itself.
- **"`provider_set=0/226` is a failure."** Rejected: those rows were written before the
  field was populated. Backfilling them would be inventing data, and narrowing the gate's
  window until the number looks good is the anti-pattern this session already rejected
  once. The count is printed on PASS so the improvement is visible as new rows arrive.
- **"Record `probe` too — §15 says every external model attempt."** Rejected with a
  reason, not by omission: a probe bypasses the limiter deliberately, so a row claiming
  `limiter_admitted=True` would be false and a row claiming `False` would look like a
  refusal. Recording it needs a third state the ledger does not have. Listed as an open
  gap and printed by the gate every run.
- **"Scan the whole repo for provider dispatch."** Rejected as currently unfalsifiable:
  `httpx` calls to the embedder, reranker and graph sidecars are not provider-account
  attempts, and a gate that has to guess which is which would be noise. Scope is stated
  in the gate: the LLM provider client, where lanes, limiters and accounts live.

## Open contract gaps

- **`probe` records nothing** — deliberate, reasoned, and printed every run, but §15's
  text does cover it. Closing it properly needs a `limiter_bypassed` state on the
  Attempt, which is a schema change and therefore owner-gated.
- **Non-client provider calls are out of scope** — chat synthesis via litellm dispatches
  outside `LLMExtractionClient` and is not covered by the seam gate. Named here rather
  than implied by the gate's silence.
- **`response_hash` is never set** (NULL on all rows); §15 lists it. Not claimed closed.
- **Coverage is wiring-proven, not traffic-proven** — `max_ordinal=1` because no failover
  has run since the fix. The next real batched run populates it.
