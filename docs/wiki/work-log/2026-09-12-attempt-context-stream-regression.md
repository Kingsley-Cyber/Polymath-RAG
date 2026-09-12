---
title: "WORK LOG — the attempt ledger broke chat, and the live test reported it as green"
change_id: PROVIDER-ATTEMPT-LEDGER-V4-FIX
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.239
architecture_impact: "fixes a production break introduced by 11.238: attempt contexts no longer span a streaming generator's yields, and `attempt_context.__exit__` tolerates being resumed in a different Context. Also narrows the live chat test's skip-on-stream-error so it can no longer hide an exception from our own code."
---

> The diagnostics I added to make provider failures visible made every chat answer fail,
> and the test written to catch chat failures classified it as someone else's problem.

## Contract

§15 telemetry must never affect the path it observes. `record` was already fail-soft; the
CONTEXT around it was not.

## Changes

**The break.** 11.238 wrapped the streaming synthesis generators in an
`attempt_context`, held open across their `yield`s. A contextvar token is only valid in
the `Context` that created it, and Starlette resumes a sync streaming generator in a
different one, so `__exit__` raised:

```
ValueError: <Token var=<ContextVar name='attempt_ctx' ...>> was created in a different Context
```

Every `/chat` answer ended as a stream error. Live, in production, for the ~14 minutes
between that commit and this one.

**How it stayed invisible.** `tests/determinism/test_chat_synthesis.py` ends its stream
reader with:

```python
if err:
    pytest.skip(f"stream error (LLM lane, not the contract under test): {err[:160]}")
```

which is right for a provider fault and wrong for ours. The suite reported **10 passed,
3 skipped, exit 0** while chat was broken — and I read that as "the restructured
generators work live". It only surfaced because I re-ran with `-rs` to see WHY three
tests skipped, and the skip reason was my own ValueError.

**Two fixes, structural before defensive:**

1. **No attempt context spans a yield.** `_AttemptOutcome` captures the ambient
   correlation id on entry and opens a context only around the `record()` call, which
   cannot yield. `_litellm_generate` does the same through a small `_rec_attempt` helper.
   Grouping is preserved — the captured id is reused — without holding contextvar state
   across a suspension point.
2. **`attempt_context.__exit__` cannot raise.** If the token is foreign, it restores the
   previous mapping by value instead. Diagnostics wrapped around a user-visible stream
   must degrade, never throw.

**And the masking itself, which is the more valuable fix.** The live test now skips only
on error codes that NAME a provider condition (`ollama_unavailable`, `ollama_error`,
`litellm_error`, rate/timeout/upstream) and **fails** on anything else:

```python
if not any(code in err for code in _LANE_FAULTS):
    pytest.fail(f"stream error from OUR OWN code, not the LLM lane: {err[:300]}")
```

## Proof

- **Before the fix:** 10 passed, **3 skipped** — the three live synthesis tests, each
  skipping on the ValueError.
- **After the fix and a fleet bounce:** **13 passed, 0 skipped.**
- **Real traffic in the ledger**, which is also the first traffic proof for 11.238's
  chat seam — six genuine synthesis attempts recorded, previously invisible:

```
lane=chat_synth:anthropic  model=anthropic/deepseek-v4-flash-0731  ok=True  14340ms
lane=chat_synth:anthropic  model=anthropic/deepseek-v4-flash-0731  ok=True  37858ms
lane=chat_synth:anthropic  model=anthropic/deepseek-v4-flash-0731  ok=True   7094ms
lane=chat_synth:anthropic  model=anthropic/deepseek-v4-flash-0731  ok=True  15401ms
lane=chat_synth:anthropic  model=anthropic/deepseek-v4-flash-0731  ok=True  59043ms
lane=chat_synth:anthropic  model=anthropic/deepseek-v4-flash-0731  ok=True   7981ms
```

- **Three new tests** pin it: exiting a context from a different `Context` must not
  raise; `_AttemptOutcome` holds no context object across the stream; and a streamed
  attempt still groups with its caller's correlation id.

## Rejected claims

- **"The live chat tests pass, so the restructuring is safe."** Withdrawn — that was the
  claim I made from a green run, and it was false. A skip is not a pass.
- **"Catch the ValueError and move on."** Rejected as the only fix: it would have left a
  context open across yields, which is the actual defect. The tolerant `__exit__` stays
  as a second line of defence, not the first.
- **"Tighten the skip list later."** Rejected: the masking is what turned a 14-minute
  outage into one I had already declared verified. It ships in the same commit.

## Open contract gaps

- Other live tests may carry similar skip-on-error branches; only this one was audited.
