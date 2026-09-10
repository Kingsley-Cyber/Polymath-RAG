---
owner: "@king"
last_reviewed: 2026-09-09
status: FORENSIC HOLD — principal task for the next session
architecture_impact: none yet (audit produces evidence, not a patch)
---

# GROQ PARENT-MAP BACKFILL — FORENSIC AUDIT (principal next-session task)

Your principal task is a **forensic audit of the Groq Parent-MAP request/accounting path**, not a
backfill, not a generic "investigate Groq", and **not a code patch first**. Reconstruct the
conservation chain from evidence, then — only after the acceptance gate passes — a bounded canary.

## Why this exists (the disputed conclusion)

The prior session ran cinema parent-MAP backfill. After advancing coverage 551→1254/11,993, a
subsequent pass reported **+0 new parents / 0 errored_docs**. That was recorded as **proof** that the
six Groq accounts had exhausted their **daily RPD**, and the run was "capacity-paused".

That inference is **DISPUTED**. A `+0 / 0-errors` pass is equally consistent with:
- a **local limiter refusal** (no HTTP request ever left the process — zero provider consumption);
- **hidden compiler / mapping failures** that never surface as `errored_docs`;
- **lane accounting** that counts endpoint *selections* rather than actual HTTP *dispatches*;
- a **systematic retry loop** burning requests on bad/partial batches.

None of these were ruled out. Provider quota exhaustion was never reconciled end-to-end against Groq's
own rate-limit headers, the limiter's admission decisions, actual HTTP dispatch counts,
`MappingOutcome.errors`, retry behavior, compiler yield, and persisted maps.

## The conservation chain you must reconstruct

Every unit of intended work must be conserved and accounted for across this chain. A discrepancy at any
hop is a finding:

```text
backfill cohort (docs × parents to map)
  → batch plan (map_batches: how many batches, what sizes)
    → limiter admission (ADMITTED vs LIMITER_REFUSED)      [refused ⇒ 0 HTTP]
      → HTTP dispatch to Groq (actual requests sent)
        → Groq response (status, rate-limit headers, body)
          → map_compiler yield (valid parents compiled per response)
            → persistence (rows written to document_parent_maps)
              → backfill accounting (mapped / complete / errored_docs / lane_counter)
```

Conservation identities to prove or falsify (build a table):

```text
intended parents  ==  admitted + limiter_refused
admitted          ==  http_dispatched                    (no silent drops)
http_dispatched   ==  http_200 + http_429 + http_other
compiled_parents  <=  http_200 responses × parents/response
persisted_parents ==  compiled_parents (minus dedupe)     (no persistence loss)
provider_rpd_used ==  http_dispatched counted by Groq     (NOT admitted, NOT selections)
```

## Investigation targets (record as questions, not confirmed root causes)

### A. Groq request-limit headers
Verify against the implementation whether `x-ratelimit-limit-requests` /
`x-ratelimit-remaining-requests` / `x-ratelimit-reset-requests` are interpreted correctly. Determine
whether **request**-header truth is being fed into an **RPM** bucket (a per-minute vs per-day category
error). Groq exposes daily request budgets in these headers; the limiter must not conflate them.

### B. Successful-response headers
Determine whether a successful `complete_one()` preserves provider response headers far enough up the
stack for the limiter to reconcile (`use_headers` path). If headers are dropped on the success path, the
limiter is flying blind and RPD truth is unobservable.

### C. Local RPD charging point
Establish exactly WHEN local `day_count` increments relative to: limiter acquisition, HTTP dispatch, HTTP
response. Charging at acquisition (before dispatch) over-counts; charging only on 200 under-counts 429s.
The correct charge point is the actual provider-counted request.

### D. `LIMITER_REFUSED` ≠ provider consumption
Prove that a local limiter refusal produces **zero** HTTP request to Groq and is **never** recorded as
provider quota consumption anywhere in accounting. This is the single most important invariant behind the
disputed conclusion.

### E. Hidden `MappingOutcome` failures
Determine whether `MappingOutcome.errors` can accumulate while `parent_map_backfill.py` still reports
`errored_docs=0`. If so, "0 errors" is not "0 failures". (Incidental observation, NOT audit evidence:
this session's stopped re-run showed several docs `mapped=N/N` yet `complete=False`, e.g. Anatomy for
Sculptors 71/71 — examine that discrepancy.)

### F. Retry waste
Audit `run_document_mapping(max_attempts=3)`: quantify how many actual HTTP requests a single doc can
consume through repeated bad/partial batches. A retry storm on unreliable batches can burn RPD while
producing +0 parents — which would masquerade as "exhaustion".

### G. Lane accounting
Determine whether `lane_counter` records **endpoint selections** or **actual HTTP dispatches**. The
BACKFILL-SPREAD-V1 round-robin (`7f74777`) spreads *selections* across six accounts; that is not proof of
six dispatched+counted requests.

### H. Account / family capacity topology
Determine whether runtime behavior matches the accepted six-separate-Groq-accounts architecture. Do NOT
assume `6 × 250` or `6 × 500` daily requests. Establish the real per-account quota from **provider
truth** (headers), and whether a shared FAMILY circuit is (incorrectly) correlating independent accounts.

### I. MAP batch reliability
`MAP_RELIABILITY_CAP=15` (`20b5408`, map-batches-v2) is NOT permanently proven. Benchmark batch sizes
**15 / 20 / 30 / 40 / 60** under the existing plaintext MAP DSL + deterministic compiler, measuring
valid-map yield and requests consumed per valid parent. **JSON object mode / schema / function-calling is
explicitly OUT OF SCOPE** — the plaintext DSL + compiler is the frozen design.

## Acceptance gate (all must pass before ANY bounded canary)

```text
[ ] provider RPD truth is OBSERVABLE (Groq rate-limit headers captured on success AND 429)
[ ] local RPD (day_count) RECONCILES with provider-counted requests
[ ] failure/refusal accounting is correct (errored_docs reflects MappingOutcome.errors)
[ ] LIMITER_REFUSED proven to be ZERO provider consumption
[ ] actual HTTP dispatch counts are separated from local attempts / endpoint selections
[ ] retry waste quantified (requests per doc under max_attempts=3)
[ ] request → valid-map efficiency measured (requests per persisted parent)
[ ] MAP batch sizes 15/20/30/40/60 benchmarked under the DSL + compiler
[ ] no systematic quota-burning retry loop exists
[ ] plaintext MAP DSL + deterministic compiler remain mandatory (no JSON mode introduced)
```

## Only after the gate passes

```text
bounded canary (small, owner-authorized)
  → compute expected API calls to finish cinema (from measured requests/valid-parent)
    → owner review
      → full backfill (resumable, idempotent)
```

**Do NOT** move automatically from audit → corpus backfill. The bounded canary and the full backfill are
separate owner-gated steps. Do NOT resume backfill because a quota window reset.

## Hard prohibitions (see BE_AWARE.md)

```text
- do not resume cinema backfill
- do not wait for / rely on a Groq quota reset
- do not spend provider quota merely to gather evidence
- do not start with a code patch (evidence table first)
- do not introduce Groq JSON object mode / schema / function-calling for MAPs
- do not bypass map_compiler
- do not modify the chunker or parent boundaries
- do not weaken strict parent identity
- do not autonomously flip QUERY_READY, disable legacy producers/readers, delete legacy state, or cut over
```

## PROBE RESULT (2026-09-10, owner-authorized bounded probe — register 11.192)

Executed the LIVE portion of this gate CINEMA-FREE via `scripts/groq_map_forensic_probe.py` (synthetic parents,
production `complete_one`, `max_attempts=1`, 17 requests, ~3 RPD/account). Evidence:
`docs/wiki/experiments/u2-groq-map-forensic-probe-2026-09-10/`.

- **Provider RPD OBSERVABLE + NOT exhausted:** all 6 accounts ~246–248 remaining of ~250 (`x-ratelimit-remaining-requests`
  captured on success). The "six accounts exhausted daily RPD" inference is CONTRADICTED.
- **Local ↔ provider RPD reconcile:** `day_count` +1 per HTTP dispatch; dispatched==requests; RPD tracks dispatch.
- **LIMITER_REFUSED = 0 HTTP** confirmed (11.185 census: 926 historical refusals, zero dispatch) ⇒ the historical
  `+0/0-errors` pass was a LOCAL refusal cascade.
- **Batch 15/20/30/40/60 = yield 1.0 on SYNTHETIC parents** (best case) — a REAL-parent (non-cinema) benchmark is
  still needed before raising `MAP_RELIABILITY_CAP` above 15.
- **Cinema-finish estimate:** ~10,739 unresolved → ~716 requests at cap-15 (or ~179 at batch 60), vs ~1,500 req/day
  capacity ⇒ finishes in well under a day.

**Gate substantially MET** (only the real-parent batch benchmark remains). **Next = OWNER REVIEW** of these
findings + estimate → (bounded cinema canary → owner review → full backfill). Resumption remains owner-gated; do
NOT resume on a quota reset.
