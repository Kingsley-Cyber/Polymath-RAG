---
change_id: PMAP-WITHIN-DOC-CONCURRENCY-V1
date: 2026-09-13
last_reviewed: 2026-09-13
status: evidence (frozen)
architecture_impact: none (read-only measurement; concurrency is a driver choice, not committed to production — finding is "bound within-doc concurrency at 2 and make it 429-adaptive")
---

# pMAP within-document concurrency — 2026-09-13 (PMAP-WITHIN-DOC-CONCURRENCY-V1)

Phase 3 of the owner pMAP directive (separate experiment, run only after the batch-size
qualification was committed). Batch size held at the qualified cap=15; the ONE variable is
within-document concurrency (disjoint parallel slices of one doc, sharing the thread-safe
routed infer). Disjoint slices => distinct batch hashes => structurally no duplicate work and
no lease conflict (verified: `duplicate_parent_maps=0` in both runs).

## Files
- `arm-c1-vs-c2-facs.json` — doc Paul Ekman FACS, same-doc halves, run when the Groq pool had
  headroom. c=1: 141 maps/min, 0% 429, 100% single-pass. c=2: **245 maps/min (1.74×)**, 23%
  429, 77.5% single-pass (resumable). 0 duplicate maps, 0 lease conflicts, 0 local refusals.
- `curve-c1-c2-c3-c4.json` — doc Directing the Story, 4 disjoint slices at c=1/2/3/4, run when
  the pool was ALREADY throttled (43% 429 at 01:45). Concurrency **amplifies** the 429 storm:

  | c | 429 % | maps/min |
  | - | ----: | -------: |
  | 1 | 33 | 114 |
  | 2 | 67 | 79 |
  | 3 | 83 | 6 |
  | 4 | 100 | **0** |

## Verdict
- **Duplicate-work = 0, lease conflicts = 0, local refusals = 0** at every concurrency (the
  disjoint-slice design is safe by construction).
- **The bottleneck is the Groq RPM pool** (~4 RPM/account × 5 map accounts ≈ 20 RPM), NOT batch
  size, NOT the local limiter. RPD was not exhausted (208 remaining); the 429s are instant
  (~0.3s) RPM/burst rejections.
- **Within-doc concurrency helps ONLY with RPM headroom.** With headroom, c=2 ≈ 1.74×. Under
  throttle, even c=1 struggles and c≥2 collapses throughput (c=4 → 0 maps). Higher concurrency
  is a footgun.
- **Recommendation:** bound within-document concurrency at **2**, and make it **429-adaptive**
  (drop to 1 when the live 429 rate rises). Do NOT hard-set c≥3. The real lever for more pMAP
  throughput is provider capacity (more Groq accounts / higher-RPM tier / a higher-RPM map
  model), not concurrency or batch size. Adaptive-concurrency implementation in
  `run_document_mapping` is a separate future change, deliberately not made here.
