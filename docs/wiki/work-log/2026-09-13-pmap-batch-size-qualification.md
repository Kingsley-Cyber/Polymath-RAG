---
title: "WORK LOG — PMAP-BATCH-SIZE-QUALIFICATION-V1: 15 vs 35 vs 50 parents/request on real docs; cap CONFIRMED at 15"
change_id: PMAP-BATCH-SIZE-QUALIFICATION-V1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.251
architecture_impact: "No behavior change. Reaffirms map_batches.MAP_RELIABILITY_CAP=15 with fresh real-doc evidence (comment-only edit; map_batches.py is NOT an execution-bundle member (8-member lock), so no bounce/re-freeze). Establishes that pMAP throughput is provider-latency/concurrency-bound, not batch-size- or limiter-bound."
---

> Owner: prove/falsify pMAP is provider-capacity-bound; finish the 15-parent 2-doc canary
> with authoritative accounting; then qualify 15 (control) / 35 / 50 (owner-preferred)
> changing ONE variable only (parents/request). Promote the largest RELIABLY superior size.
> Do not launch the corpus backfill until the winner is selected, evidenced, the cap
> deliberately set, and the production path re-verified.

## Contract
`groq/compound-mini` pMAP calls are capped at `MAP_RELIABILITY_CAP=15` parents/request. The
owner believed 50 might be viable and that the historical 925 `LIMITER_REFUSED` implied local
admission starvation. Both had to be tested against live measurement, changing only
parents/request (`reliability_cap`), with per-attempt/per-batch evidence and conservation.

## Changes
- **No production behavior change.** `shared/polymath_shared/document_profile/map_batches.py`:
  appended the 2026-09-13 real-doc re-qualification result to the `MAP_RELIABILITY_CAP=15`
  provenance comment (value unchanged; "no unexplained global constant"). Comment-only.
- **Evidence preserved** under `docs/wiki/experiments/pmap-batch-size-qualification-2026-09-13/`
  (Phase 1 baseline JSON, synthetic-probe counter-example, Phase 2 real-doc qualification JSON,
  README with the full table + conservation).
- Diagnostic harnesses ran from the scratchpad (not committed): they drive the UNCHANGED
  production `run_document_mapping` path, swapping only the doc cohort and `reliability_cap`.

## Proof
- **Phase 1 (15-parent, VES + Dancyger):** ledger 94 attempts = 94 admitted = 94 dispatched =
  87×200 + 7×429; **0 LIMITER_REFUSED, 0×413**; alias conservation exact (1749 eligible = 557
  already + 1092 newly + 100 unresolved). 140 maps/min. The historical 925 `LIMITER_REFUSED`
  (worker path, shared-limiter blind-capacity pin) did NOT reproduce on the dedicated
  per-endpoint-limiter path → historical vs current vs root-cause distinguished, not rewritten.
- **Phase 2 (15/35/50, 506 equivalent parents each, one variable):** 15 → 98.8% durably
  mapped, 0 unresolved, 0 empty, 0×413, 130 maps/min, retires the work in 38 dispatches; 35 →
  50.8% (31% of 2xx EMPTY), 245 unretired; 50 → 36.8%, 13% HTTP 413, 20% 429, 313 unretired.
  Conservation reconciled per cohort (ledger dispatched = 200+429+413+other; eligible =
  mapped+unresolved+excluded; refusals=0). **WINNER: 15.**
- **Production path re-verified:** the cap=15 cohort IS the production configuration running
  live (98.8% yield, 0 failures). No bounce needed — `map_batches.py` is not an
  execution-bundle member and the edit is comment-only (value unchanged at 15); fleet stayed
  healthy (23 workers, one bundle hash), `bundle_integrity` READY `7e97368d`, `/ready` true.
- Side effect (real progress): cinema unresolved 6,693 → 4,658 (~2,035 parents mapped, never
  re-purchased — idempotent).

## Rejected claims
- **"50 parents/request is viable" (owner hypothesis)** — REJECTED by real-doc measurement:
  36.8% yield, 13% HTTP 413, 62% missing. Falsified.
- **"35 is a safe speed-up"** — REJECTED: 50.8% yield, 31% of successful calls return EMPTY.
- **"The synthetic probe (35=1.0) qualifies 35"** — REJECTED: synthetic skeletons are trivial;
  real parents collapse at ≥25 aliases. The probe is kept only as the counter-example.
- **"pMAP is local-limiter/admission bound"** — REJECTED: 0 local refusals at every size; the
  only throttle is real provider (429/413) and the structured-output reliability ceiling.

## Open contract gaps
- **Throughput** is now provider-latency/concurrency-bound at 15 (p50 4.8s/dispatch,
  sequential). Bounded within-document concurrency (start=2) is the next experiment (Phase 3),
  deliberately separate and not yet run.
- The cap is `Canaryable`: if a future `groq/compound-mini` (or a different map model) improves
  big-batch structured-output reliability, re-run PMAP-BATCH-SIZE-QUALIFICATION-V1 before raising.
- Cinema still has 4,658 unresolved parents; finishing them is the owner-authorized backfill at
  the confirmed 15-cap (not launched here — this slice is the qualification only).
