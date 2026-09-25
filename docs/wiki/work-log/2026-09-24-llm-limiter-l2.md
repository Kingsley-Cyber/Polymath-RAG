---
change_id: LLM-BACKEND-L2-LIMITER
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "shared/ limiter + client + registry check + config budgets. Every complete_one call (profiles, pMAP, parent enrichment, the chat compiler and bridges) now reserves prompt + output before dispatch and settles to the provider's usage; Groq lanes gain a rolling 24 h token budget, groq_5 qwen an output-per-minute budget. Fence + one bounce."
last_reviewed: 2026-09-24
---

# LLM-BACKEND L2: limiter correctness

## Contract
- The owner, 2026-09-24: "go L2". Roadmap `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §1.2 / §3 row 3; gaps L-04 (admission
  counted `len(user_prompt) / 4`), L-05 (no daily-token budget), L-16 remainder (no output-per-minute budget).

## Changes
- `limiter.py`:
  - `ProviderLimit.tpd` (tokens per ROLLING 24 h: Groq refills continuously, so a UTC-midnight reset would be wrong) and
    `ProviderLimit.otpm` (output tokens per minute);
  - `_RollingTokens`: the 24 h window, one entry per call, persisted as hour buckets (`state()["tpd_hours"]`) and
    restored only under the same limits fingerprint (which now includes tpd / otpm);
  - `admit(est_tokens, block, *, reserved_output=0)`: TPM takes prompt + reserved output, OTPM the reserved output, the
    daily window the reservation; new refusals `REFUSE_TPD`, `REFUSE_OTPM`; every refusal refunds what it took;
  - `settle(decision, tokens_in, tokens_out, *, failed)`: unused reservation goes back to TPM / OTPM, overuse is
    charged (`_TokenBucket.debit`), the daily window records the real total, a failed call releases its daily
    reservation; the dirty state persists through the existing coalesced writer.
- `client.py`: `admission_tokens(*texts)` (ceil(chars / 3): conservative, trued up by settle); `complete_one` admits
  `system + user + max_tokens` with `reserved_output=max_tokens` and settles on success / failure.
- Config (both the registry and `limiter.yaml`, drift 0): Groq lanes `tpd` = 95 % of the pair's 200K divided by the worker
  slots that share the lane (profile 31,666 × 6; pMAP 47,500 × 4), the rule the existing rpd values follow;
  `map_groq5q` `otpm: 1000`.
- `accounts.py`: warning `BUDGET_EXCEEDS_QUOTA` (per-process budget × slots vs the pair's quota).
- Test doubles widened to the new interface (assertions unchanged): `test_offline_conservation_replay._FakeLimiter`
  (`reserved_output`, a no-op `settle`), `test_limiter_control_plane` (`admit` lambda accepts `**_kw`).

## Proof
- `tests/determinism/test_llm_limiter_l2.py`: 12 tests pass (reservation + true-up, overuse charge, failed release,
  no-usage keeps the estimate, TPD refusal with refunds, OTPM refusal, window expiry, restore under the same / other
  limits, lanes without budgets unchanged, `admission_tokens`, `complete_one` wiring, registry budgets).
- Impacted suites (29 files), worktree without `.env`, dead `POLYMATH_TEST_DSN`, `-k "not test_live_"`: branch 283
  tests = 1 failure, 4 skipped; production 271 = the same 1 failure
  (`test_synthesis_attempt_telemetry::test_the_bound_retry_records_BOTH_attempts`, order-dependent, needs a database).
- `scripts/llm_accounts.py diff`: no drift. `validate`: 0 errors; `BUDGET_EXCEEDS_QUOTA` reports only per-MINUTE
  overshoot on shared pairs (tpm × slots; groq_5 qwen otpm 1,000 × 4) — every daily budget fits its quota.
- Lint: limiter.py 8 / client.py 15 findings, identical to production; the new test is clean. Contract impact: none.

## Rejected claims
- "Divide TPM / OTPM by the slots too": a per-process bucket smaller than one request's reservation waits for a full
  bucket and still lets every process send, so it cannot enforce a shared per-minute limit; single ownership (L3) or a
  shared budget (L5) can.
- "Count tokens with a tokenizer at admission": the only cached encoding is cl100k and a missing cache would download
  at run time inside a worker; a conservative character estimate trued up by the provider's usage is exact where it
  matters (the daily window).

## Open contract gaps
- L-21: the batched extraction paths (`extract_batched`, `complete_batched`, `_extract_prompt`) still admit `len / 4` of
  the user prompts; they run on lanes without Groq daily budgets.
- L-06: budgets are per process; L3 gives each dedicated pair one owner, L5 shares budgets across processes.
