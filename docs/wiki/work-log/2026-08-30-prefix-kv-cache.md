---
change_id: PREFIX-KV-CACHE-V1
owner: worker
date: 2026-08-30
status: complete
architecture_impact: local extraction sidecar only (sidecars/local_extractor); no contract, store, or fleet-code change
last_reviewed: 2026-08-30
---

# WORK LOG — PREFIX-KV-CACHE-V1 (local lane throughput)

## Contract
Local lane must finish a ≤300 KB book in under 7 minutes. Production
receipts measured 8 tok/s effective through the sidecar while in-process
decode reaches 80–90 tok/s — the gap must be closed in the sidecar, not
by reverting the owner's LEAN/mask/memory work.

## Changes
`sidecars/local_extractor/batched_server.py` — three changes inside
`_generate`, everything else untouched:
1. PREFIX-KV-CACHE-V1: the batch's longest common TOKEN prefix (the
   rendered system prompt, ~0.5–1K of every ~2.2K prompt) is prefilled
   ONCE into a KV cache, kept across calls (LRU 4, keyed by the prefix
   token tuple), and every sequence decodes from a suffix-only prompt.
   Single-prompt calls only REUSE a stored prefix, never build one
   (building would churn the LRU with unique content). Fail-open to full
   prefill; kill-switch `POLYMATH_PREFIX_CACHE=off`.
2. Per-sequence budgets: `max_tokens=budgets` (mlx_lm 0.31.3 accepts a
   list) instead of `max(budgets)` uniform.
3. `completion_batch_size=MAX_BATCH` so decode rows match the server cap.

## Proof
- Prefill measured at 536 tok/s — the bottleneck (decode is 80–90).
- Probe (batch 4, 518-token LCP): 17.3 s → 13.0 s (+1.0 s one-time
  build); cache reuse across calls byte-identical (B==C).
- HTTP production shape (batch 20, 45K in / 3.9K out):
  **46 tok/s effective vs 8 in production receipts**; batch 8: 37 tok/s.
  All stops `stop`, outputs gate-clean on real text.
- Nondeterminism control: full-prefill greedy output ALREADY differs
  across batch compositions (batch4 != batch2 != batch1; reruns stable),
  and production batch packing varies run to run — the cache adds no new
  nondeterminism class.
- 300 KB book math at measured rates: ~75 s prefill (system prefix
  cached) + ~150 s decode ≈ ~4 min single-book extract — under the
  7-minute target with margin.

## Rejected claims
- "The rep-penalty processor is the slowdown" — REJECTED, measured: 90.7
  tok/s WITH processors vs 80.7 without (the penalty self-terminates
  output sooner; it SAVES wall).
- "Uniform max(budgets) burns straggler steps" — REJECTED for wall
  (BatchGenerator retires sequences at EOS; per-seq list kept anyway as
  correctness hygiene).
- "The sidecar HTTP path itself is the gap" — REJECTED: warm HTTP now
  within ~10% of in-process at the same shape. The residual production
  gap vs bench is GEN-LOCK wait (two books time-sharing one window) +
  Metal contention with the embedder — scheduling, owned by lane-aware
  routing (next item), not the server.

## Open contract gaps
1. Lane-aware routing (overflow the second small book to cloud when the
   local window is busy) — queued, other session's item.
2. `local_extractor` supervisor slot — queued for the next bounce (other
   session's item; agreed).
3. Real-corpus LEAN prefix share is system-prompt-only (~45% of prefill);
   the bench's shared user text overstates in-call savings — expect
   ~35–40 tok/s effective on real books, still ≥4× production baseline.
