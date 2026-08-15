> HISTORICAL / FROZEN / NOT PRODUCTION — the models below were evaluated and REJECTED in EM1; the sole production GLiNER is urchade/gliner_medium-v2.1 @ 40ec4193.
# EM1 Entity Model Qualification Report

Status: FROZEN
Date: 2026-08-14
Outcome: **FAIL — no challenger clears the full promotion bar; held-out preserved; escalate architecture/provider**

## Phase 0 — pins (frozen before scoring)

| Model | Repo @ revision | License |
|---|---|---|
| baseline-medium | urchade/gliner_medium-v2.1 @ `40ec4193…` | apache-2.0 |
| A-large-v21 | urchade/gliner_large-v2.1 @ `abd49a1f…` | apache-2.0 |
| B-large-v25 | gliner-community/gliner_large-v2.5 @ `3d6d1760…` | apache-2.0 |
| C-nuner-zero | numind/NuNER_Zero @ `c9018767…` | mit |

Library: gliner 0.2.28 · torch 2.13.0 · transformers 5.13.1 · device
mps · dtype fp32. Per-model file SHA256 snapshots recorded in the
artifact files. Fair contract: identical normalized chunks, production
label inventory, production mapping, EP1 dev gold, EP1 scoring harness.
Threshold grid 0.30–0.60 chosen on DEV only. Determinism re-checked on
every run (all deterministic).

## Measurement-integrity finding (recorded, EP1 artifacts NOT rewritten)

The EP1 baseline was scored on spans recovered through the sidecar HTTP
path, whose offsets were misaligned with the harness's chunk-space
arithmetic — EP1 span texts are visibly corrupted (" attentio",
" studen"). EM1 runs models through the direct GLiNER API on the exact
chunk text, producing clean spans. The EM1 clean-contract baseline
therefore SUPERSEDES the EP1 baseline as the delta reference. All
comparisons below use the clean baseline.

## Phase 2 — dev entity metrics (best row per model; full grids frozen)

| Model @ thr | overlap R | mw R | type acc | bare-head | false | exact P |
|---|---|---|---|---|---|---|
| baseline @0.45 | 0.356 | 0.449 | 0.824 | 0.000 | 0.296 | 0.120 |
| baseline @0.30 | 0.452 | 0.551 | 0.734 | 0.000 | 0.367 | 0.102 |
| A @0.35 | 0.519 | 0.619 | 0.759 | 0.000 | 0.402 | 0.098 |
| A @0.30 | 0.534 | 0.644 | 0.766 | 0.000 | 0.422 | 0.094 |
| B @0.45 | 0.587 | 0.669 | 0.713 | 0.016 | 0.460 | 0.079 |
| B @0.40 | 0.606 | 0.695 | 0.698 | 0.015 | 0.480 | 0.072 |
| C @0.35 | 0.538 | 0.593 | 0.741 | 0.043 | 0.459 | 0.025 |

## Phase 3 — promotion floors (dev)

Required: overlap R ≥ 0.55 AND multiword R ≥ 0.55, substantial gain
over baseline, false-span not materially worse, type accuracy in a
precision-safe range, bare-head down, deterministic.

- **A-large-v21**: multiword floor met (0.62–0.64); overlap 0.519–0.534
  — below the 0.55 floor; type accuracy 0.76–0.77 (−8 pts vs baseline);
  false-span 0.40–0.42 (+11–13 pts). FAIL (floors).
- **B-large-v25**: the ONLY model clearing both recall floors
  (overlap 0.59–0.61, mw 0.67–0.70), but false-span 0.46–0.48 (+16–18
  pts vs baseline) materially worsens and type accuracy falls to
  0.70–0.71 (−12 to −15 pts). FAIL (precision-first safety).
- **C-nuner-zero**: overlap 0.538 at best — below the floor; exact
  precision ~0.02 (near-zero exact spans, label noise). FAIL.

Selection priority is precision/false-span safety first: no challenger
clears all required floors. Per the EM1 brief — **STOP. Do not consume
held-out.**

## Phase 6 — held-out

`heldout_ep1_v1` was NOT run. It remains untouched for the escalated
architecture experiment.

## Phase 7 — operational (recorded per artifact)

| Model | cold load | warm load | peak MPS |
|---|---|---|---|
| baseline-medium | 5.3s | 5.3s | 744MB |
| A-large-v21 | 68.9s | 10.5s | 1699MB |
| B-large-v25 | 114.4s | 8.0s | 1752MB |
| C-nuner-zero | 132.1s | 9.4s | 1712MB |

All models run comfortably within 32GB host memory; no OOM. (Load
times and per-chunk latency will be re-qualified on the promoted
configuration only — no promotion occurred.)

## Final verdict

**EM1 FAIL.** No candidate recovers realistic multiword coverage at a
precision-safe operating point. The next escalation per the brief: a
different entity architecture/provider (supervised span-expansion or
decoder-based proposal) under a new explicit gate, reusing the frozen
EP1/EM1 dev + gold protocol and the preserved one-shot held-out set.

Downstream status unchanged: production remains gliner_medium-v2.1 @
40ec4193 with rule pack 1.0.1; I1 remains BLOCKED.
