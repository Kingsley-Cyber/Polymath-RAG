---
title: "WORK LOG — diagnosing the 31 dark lanes: the detector was right to ask and wrong to shout"
change_id: DARK-LANE-DIAGNOSIS-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.242
architecture_impact: "narrows DARK_ENABLED_LANE to lanes skipped while their FUNCTION was working (idle functions are reported as context, never as a finding) and makes the finding carry its sample size. Corrects a stale docstring in conformance/assess.py that my own slices invalidated the same day. No schema change."
---

> 11.241 surfaced "31 enabled, credentialled lanes made no attempt in 24 hours" and
> explicitly did not diagnose it. This diagnoses it — and the answer changes the detector.

## Contract

§15's `DARK_ENABLED_LANE`, and §18's rule that a status must mean what it says.

## Changes

**The diagnosis.** All 31 dark lanes belong to functions that were not running:

| function | dark lanes |
|---|---|
| GRAPH_EXTRACTION | 18 |
| PMAP | 6 |
| parent_enrichment | 4 |
| DOCUMENT_PROFILE | 2 |
| CHAT | 1 |

The only lanes with traffic in 24h are the chat ones. No ingestion has run on this host
in that window — 265 stage tickets sit pending and unleased — so every extraction lane is
idle **because there is no work**, not because anything is misconfigured. A detector that
fires on "the pipeline is idle" trains its reader to ignore it, which is worse than not
having it.

**Refinement 1 — a lane is dark only if its FUNCTION was working.** Idle functions are
reported as context (`Idle functions, not counted: GRAPH_EXTRACTION(18), PMAP(6), …`),
never as a finding. Live output went from 31 lines of noise to **one specific claim**:

```
1 lane made no attempt in 24 hours WHILE THEIR FUNCTION WAS WORKING:
compiler_alibaba_deepseek [CHAT, 3 sibling(s) working]
```

**Then I chased that one, and it is not a defect either.** The lane is in the
`chat_compiler` stage pin, present in `cloud_endpoints()`, and reaches the roster — so I
tested the rotation directly rather than reasoning about it. Over 4000 distinct session
keys, `_compiler_attempt_order` is fair:

| lane | home | appears in the 3-attempt order |
|---|---|---|
| compiler_alibaba_deepseek | 25.5% | 74.9% |
| compiler_alt | 25.4% | 76.0% |
| compiler_alibaba_qwen | 25.1% | 74.5% |
| compiler_ollama_gemma | 24.0% | 74.5% |

The rotation is uniform. The window simply held **28 logical calls** from a handful of
session keys — the test suite reuses them — and a lane absent from 28 draws over 4 lanes
is unremarkable.

**Refinement 2 — the finding states its sample size.** `Sample: 28 logical call(s), 356
attempt(s) — with few calls, absence is expected, not evidence`. Without it the next
reader repeats the hour I just spent.

**And a stale note my own work invalidated.** `conformance/assess.py` documented, as of
today, that "the ledger is populated only for the CHAT-compiler lanes … a separate,
pre-existing ledger-population gap, not something this slice fixes". Registers
11.236–11.238 closed exactly that gap hours later, leaving a docstring that would tell a
future reader the ledger is still blind. Corrected in place, with what actually changed.

## Proof

- Live: the finding is now one lane, with its sample size, and the idle functions named
  as context.
- Rotation fairness measured over 4000 keys (pure function, no spend), table above.
- 35 tests green across the three attempt-telemetry files, including: an idle function's
  lanes are NOT dark but ARE reported as context; a lane skipped while a sibling worked
  IS dark; the finding carries `logical_calls` and `attempts`.

## Rejected claims

- **"31 dark lanes is a finding."** Withdrawn. It was one fact — the pipeline is idle —
  reported 31 times as though it were 31 problems.
- **"compiler_alibaba_deepseek is never selected; fix the rotation."** Rejected on
  measurement: the rotation is uniform to within 1.5 points over 4000 draws. The
  hypothesis was plausible and wrong, and testing it cost less than acting on it.
- **"Suppress the lane so the finding reads clean."** Rejected: the finding is true for
  the window. The fix is to make the window's size visible, not to hide the observation.

## Open contract gaps

- **Session-key diversity is low in the observed traffic** (28 logical calls, few keys),
  so lane-level conclusions from this window are weak by construction. Any real
  neglected-lane claim needs a window with real user traffic.
- `cost` is still never recorded (§15 lists it "if available").
