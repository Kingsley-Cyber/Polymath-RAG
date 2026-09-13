---
change_id: PMAP-BATCH-SIZE-QUALIFICATION-V1
date: 2026-09-13
last_reviewed: 2026-09-13
status: evidence (frozen)
architecture_impact: none (read-only measurement qualifying map_batches.MAP_RELIABILITY_CAP; value CONFIRMED at 15)
---

# pMAP batch-size qualification — 2026-09-13 (PMAP-BATCH-SIZE-QUALIFICATION-V1)

Owner-directed: prove/falsify that pMAP is provider-capacity-bound, then qualify larger
parents/request (15 control / 35 / 50 owner-preferred). One variable only:
`map_batches.MAP_RELIABILITY_CAP` (parents/request). Provider, prompt, compiler, model
(`groq/compound-mini`), grounding, retry semantics, concurrency (sequential) all held fixed.

## Files
- `phase1-baseline-15-canary.json` — Phase 1: 15-parent baseline on VES Handbook + Ken
  Dancyger (1749 eligible; 1092 newly mapped). Ledger: 94 attempts = 94 admitted = 94
  dispatched = 87×200 + 7×429, **0 LIMITER_REFUSED**, 0×413. Alias conservation exact
  (1749 = 557 already + 1092 new + 100 unresolved).
- `synthetic-probe-15-35.json` — `groq_map_forensic_probe --live` on SYNTHETIC skeletons;
  both 15 and 35 returned yield 1.0. **Misleading** — synthetic skeletons are trivial; see
  the real-doc result below. Kept as the counter-example.
- `phase2-qualification-15-35-50.json` — the authoritative real-doc qualification: 4 cinema
  docs, each doc's unresolved parents shuffled (seed 1337) into 3 disjoint thirds → one
  third per cohort, so every cohort sees the same doc-difficulty mix. 506 equivalent
  parents per size.

## Result (real docs, 506 equivalent parents each)

| Metric | 15 | 35 | 50 |
| --- | --: | --: | --: |
| HTTP dispatches | 38 | 17 | 15 |
| Local refusals | 0 | 0 | 0 |
| 429 % | 0 | 5.9 | 20.0 |
| 413 % | 0 | 0 | 13.3 |
| Complete % (submitted durably mapped) | 98.8 | 50.8 | 36.8 |
| Empty/invalid % (of 2xx) | 0 | 31.3 | 20.0 |
| Maps/dispatch | 13.2 | 15.1 | 12.4 |
| Maps/min | 130 | 85 | 80 |
| Missing-parent % | 0 | 48 | 62 |
| Repair calls | 0 | 0 | 0 |
| Requests to retire 506 | 38 (DONE) | ≥17 (245 left) | ≥15 (313 left) |
| p50 / p95 latency (s) | 4.8 / 7.8 | 8.5 / 10.4 | 7.9 / 10.4 |

Conservation reconciled per cohort: ledger dispatched = 200 + 429 + 413 + other; eligible =
mapped + unresolved + excluded; refusals = 0.

## Verdict
**WINNER: 15.** 35 collapses to 50.8% (31% of successful calls return EMPTY); 50 to 36.8%
(adds 13% HTTP 413 payload + 20% 429), both leaving 48–62% unmapped and running *slower* in
maps/min. The ceiling is `groq/compound-mini` structured-output reliability — not tokens, not
the limiter (0 local refusals at every size). The owner's 50-parent hypothesis is falsified
on real docs. `MAP_RELIABILITY_CAP` stays **15**, reaffirmed with this evidence.

**Remaining bottleneck (measured):** at 15, provider latency (p50 4.8s/dispatch, sequential)
— throughput scales with lane concurrency, not batch size. Next experiment: bounded
within-document concurrency (Phase 3).
