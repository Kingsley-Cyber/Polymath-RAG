---
title: "WORK LOG — PMAP-WITHIN-DOC-CONCURRENCY-V1: c=2 helps only with RPM headroom; bottleneck is the Groq RPM pool"
change_id: PMAP-WITHIN-DOC-CONCURRENCY-V1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.252
architecture_impact: "No production change. Phase 3 measurement: within-document pMAP concurrency. Finding — bound concurrency at 2 and make it 429-adaptive; the throughput ceiling is aggregate Groq RPM (~20 RPM across 5 map accounts), not batch size or the local limiter. Adaptive-concurrency implementation deferred."
---

> Owner (Phase 3, separate experiment, only after the batch-size winner was committed):
> investigate bounded within-document parallelism — one large doc, independent batches,
> independent lanes, results persist independently, unresolved aliases alone re-enter work.
> Begin at concurrency=2; qualify higher only through measurement. Never repurchase maps.

## Contract
`run_document_mapping` processes a doc's batches sequentially. Would running one doc's batches
across multiple Groq lanes in parallel raise throughput without repurchasing maps or causing
lease conflicts — and how far does it scale?

## Changes
- **No production code change.** Measurement only. Within-doc concurrency was realised as N
  disjoint parallel slices of one doc, each its own `run_document_mapping` sharing the
  thread-safe routed infer (distinct batch hashes ⇒ no duplicate work, no lease conflict).
  Batch size held at the qualified cap=15; provider/prompt/compiler/model/retry unchanged.
- Evidence preserved under `docs/wiki/experiments/pmap-within-doc-concurrency-2026-09-13/`.

## Proof
- **c=1 vs c=2 (doc FACS, RPM headroom):** c=1 = 141 maps/min, 0% 429, 100% single-pass; c=2 =
  **245 maps/min (1.74×)**, 23% 429, 77.5% single-pass (resumable). `duplicate_parent_maps=0`,
  0 lease conflicts, 0 local refusals.
- **Curve c=1..4 (doc Directing the Story, pool ALREADY throttled — 43% 429 at 01:45):**
  429% 33→67→83→**100**; maps/min 114→79→6→**0**. Concurrency AMPLIFIES the 429 storm; c=4
  produced zero maps. `duplicate_parent_maps=0` throughout.
- **Root cause (measured):** RPD not exhausted (208 remaining); 429s are instant (~0.3s)
  RPM/burst rejections. The ceiling is aggregate Groq RPM (~4 RPM/account × 5 map accounts ≈
  20 RPM), NOT batch size and NOT the local limiter (0 refusals at every level).

## Rejected claims
- **"More within-doc concurrency = more throughput"** — REJECTED beyond ~2: helps only with
  RPM headroom (c=2 = 1.74× on FACS); under throttle it collapses throughput (c=4 → 0 maps).
- **"Concurrency risks duplicate work / lease conflicts"** — REJECTED for the disjoint-slice
  design: 0 duplicates, 0 conflicts, 0 refusals across both runs.
- **"The bottleneck is the local limiter / batch size"** — REJECTED across all three phases:
  it is provider RPM capacity.

## Open contract gaps
- **Adaptive-concurrency in `run_document_mapping`** (bound at 2, back off to 1 as the live
  429 rate rises) is the natural production change — deliberately NOT made here; it is a
  separate slice requiring a `workers/` edit + fleet bounce.
- **The real throughput lever is provider capacity** — more Groq map accounts / a higher-RPM
  tier / a higher-RPM map model. Batch size (15) and concurrency (≤2) are already at their
  useful limits.
- Cinema still has ~4,600 unresolved parents; finishing them is the owner-authorized backfill
  at cap 15, concurrency ≤2, paced against 429 (not launched here). Session Groq RPM is
  currently depleted (43% 429) — a backfill now would be 429-paced; better after a quota window.
