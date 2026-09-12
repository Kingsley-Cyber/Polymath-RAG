---
title: "WORK LOG — PROVIDER-ATTEMPT-LEDGER-V2: the batched seam was never recorded, so the one call site that TAGS attempts wrote nothing"
change_id: PROVIDER-ATTEMPT-LEDGER-V2
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.236
architecture_impact: "additive telemetry on an existing seam: four `record(Attempt(...))` calls inside `LLMExtractionClient._infer_batch_call`, matching the four already in `complete_one`. No schema change, no production data mutated, no dispatch semantics changed — `record` is fail-soft by construction. Touches shared/, so it requires a fleet bounce to become live."
---

> §15 states the ledger's purpose as a single example:
>
>     lane A -> HTTP 429 · lane B -> HTTP 429 · lane C -> HTTP 200 · PMAP batch -> SUCCESS
>
> "Batch success is correct. But the first two attempts must not disappear."
> The batch in that sentence is a pMAP batch — and the pMAP batch path recorded nothing.

## Contract

REQUIRED FINAL STATE, DURABLE ATTEMPT TELEMETRY: every provider attempt is durable per
attempt, not per logical call, so failover and throttling survive a successful outcome.

## Changes

**Measured first, on the live database, before touching code:**

| measurement | value |
|---|---|
| `llm_provider_attempts` rows | 209 |
| distinct lanes in the ledger | **3** (`compiler_alt`, `compiler_ollama_gemma`, `compiler_alibaba_qwen`) |
| lanes with real dispatch activity in durable limiter state | **13** |
| rows carrying `function` / `stage` / `run_id` | **0** — every row untagged |

Those three numbers are one fact, not three. `record(Attempt(...))` existed only inside
`LLMExtractionClient.complete_one` — the SINGLE-completion path, which in practice only
the chat query-compiler lanes take. Every batched extraction and every pMAP dispatch goes
through `_infer_batch_call`, which recorded nothing.

The structural consequence is sharper than "some lanes are missing". `grep -rn
attempt_context` finds exactly **one** caller in the entire repository:

```
workers/workers/doc_parent_map_stage_worker.py:232:  with attempt_context(function="PMAP", stage="doc_parent_map", run_id=run_id):
```

The only code that TAGS attempts wraps the only path that RECORDED none. The tagging
context and the recording call site were on disjoint code paths, which is why 209 out of
209 rows are untagged — not a configuration oversight, a wiring gap.

**Fix.** Four `record` calls in `_infer_batch_call`, one per branch, mirroring
`complete_one`:

| branch | `limiter_admitted` | `http_dispatched` | recorded |
|---|---|---|---|
| limiter refuses | `False` | `False` | `error_class="limiter_refused"` — a LOCAL refusal, never a provider request |
| `HTTPStatusError` | `True` | `True` | `http_status`, `retry_after_s`, `error_class=http_<status>`, `latency_ms` — **the 429 case** |
| transport / JSON error | `True` | `True` | `error_class=<exception type>`, `latency_ms` |
| success | `True` | `True` | `success=True`, `http_status=200`, `latency_ms` |

`lane=self.limiter_key`, not `self.lane`. `self.lane` is the TRANSPORT kind
(`"local"`/`"cloud"`); the lane NAME is `limiter_key`, and that is what `complete_one`
has always recorded. Recording `self.lane` would have produced a ledger whose two halves
disagreed on what "lane" means — 13 real lanes collapsing into 2 rows.

A 500 halves the sub-batch and re-enters `_infer_batch_call`, so each half takes its own
`t0` and writes its own row: a halved batch records one attempt per sub-call, which is
the per-attempt semantics the contract asks for rather than one row per logical call.

## Proof

**1 — unit, no provider spend.** `tests/determinism/test_batch_attempt_telemetry.py`,
5 tests, all four branches pinned with a mocked transport plus one test that documents
the fail-soft contract (`record`'s own try/except is what makes it safe; the client does
not add a second swallow that would hide a broken ledger).

```
.venv/bin/python -m pytest tests/determinism/test_batch_attempt_telemetry.py -q
5 passed
```

**2 — end to end, against the REAL ledger, still no provider spend.** The real client,
inside the real `attempt_context` the pMAP worker uses, dispatched at `127.0.0.1:9`
(nothing listening, so it fails at connect — no provider is contacted and nothing is
billed), then the row was read back out of Postgres:

```
correlation_id: aaa0403c76034f2b93ffc18f
('selftest-batch-seam', 'SELFTEST', 'batch_seam_proof', 1, True, True, False, 'ConnectError', 55, 'selftest/none')
 lane                  function    stage              ord  adm  disp  ok    error_class     ms   model
```

That row is the whole claim: the batched seam reaches the ledger, and the context tags
join — the two halves that had never met. It is deliberately tagged `function=SELFTEST`
so it is filterable and can never be mistaken for production traffic, and it is left in
place rather than deleted (deleting production rows is an owner gate, and the attempt it
records genuinely happened).

**3 — guards.** `agent_preflight` ok, `repo_guard` ok. Targeted determinism suite green.

## Rejected claims

- **"The ledger works, 209 rows prove it."** Rejected: row count measures that the writer
  works on one path, not that the paths that matter write. 3 lanes of 13, zero tagged.
- **"Record `self.lane`."** Rejected after reading `complete_one`: it records
  `self.limiter_key`. Consistency between the two halves of one table outranks the
  attribute name being the tidier read.
- **"Prove it with a real batched extraction."** Rejected: that spends provider quota
  under a standing forensic hold. The connect-refused probe exercises the identical code
  path through to the INSERT at zero cost, and the mocked tests cover the branches a
  failed connect cannot reach.
- **"`record` can't raise, so no test is needed for that."** Rejected: that is true of
  `record` TODAY. The test pins it, so removing the swallow fails a test instead of
  failing production extraction.

## Open contract gaps

- **Coverage is now wired, not yet demonstrated across all 13 lanes with live traffic.**
  The next real batched run will populate them; until then the gate reads the wiring,
  not a lane census. Stated as wiring-proven, not traffic-proven.
- **`complete_one` remains untagged in practice** — no caller wraps the chat-compiler
  lanes in an `attempt_context`, so those rows still carry null `function`/`stage`. The
  batched path (the one §15's example is about) is now tagged; the compiler path is a
  separate, smaller gap and is not claimed as closed.
