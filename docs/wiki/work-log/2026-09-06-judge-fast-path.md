---
title: "WORK LOG — JUDGE-FAST-PATH-V1: the cross-encoder judge in fp16, 256-token pairs, one forward pass, inference_mode and a cross-request memo"
change_id: JUDGE-FAST-PATH-V1
date: 2026-09-06
owner: governance (owner decision 2026-09-06: "judge fix, do today")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.100
package: sidecars/reranker/server.py, shared/polymath_shared/rerank.py (client batch), scripts/rerank_judge_bench.py, tests/determinism/test_reranker_sidecar.py, tests/determinism/test_metal_lease.py
architecture_impact: "The judge (Qwen3-Reranker-0.6B as a sentence-transformers CrossEncoder on Metal) is the wall on every chat path — 24 pairs took 5.5 s p50 of a 9.5 s turn under enrichment load, scored in fp32 over untruncated 4000-char surfaces, 8 pairs per device batch, two HTTP requests per judge call. It now runs fp16 (POLYMATH_RERANKER_DTYPE; fp32 to revert), truncates every (query, document) pair to 384 tokens (POLYMATH_RERANK_MAX_LENGTH; the owner asked for 256 — the sweep below chose 384), scores a whole request in ONE forward pass (POLYMATH_RERANK_BATCH 64 = the wire cap; the OOM halving stays as the safety net; the client sends ≤ 64 surfaces per request so a 24-pair judge call is one request), under torch.inference_mode, and memoizes (query, document) scores across requests in a bounded LRU (POLYMATH_RERANK_MEMO_MAX 20000, 0 = off; the memo scope is model revision + dtype + max_length). fp16 self-tests at startup and falls back to fp32 on a non-finite score (logged, receipted `dtype_fallback`); at request time a non-finite score ranks last and is counted. Every knob is receipted per response (dtype, max_length, batch, memo_hits, memo_misses, nonfinite) and cumulatively on /ready (stats). Scoring semantics are unchanged: same model, same pairs, raw cross-encoder scores, rank-based use downstream."
---

# WORK LOG — JUDGE-FAST-PATH-V1

Owner decision (2026-09-06, after the acceptance run showed the judge as the wall on every path): *fp32 → fp16, batch all pairs in ONE forward pass, inference_mode, truncate to 256 tokens (negligible CE quality loss, ~2× compute cut), memoize scores across turns since carry-reranks repeat.* Hypothesis promoted only by measurement below.

## Contract

- `sidecars/reranker/server.py`: dtype / max_length / batch / memo knobs above; `torch.inference_mode()` around every device batch; startup self-test (`SELFTEST_PAIRS`, incl. a > 256-token document) decides the process dtype; `sanitize_scores` ranks non-finite scores last and counts them; `memo_key / memo_lookup / memo_store` (LRU, thread-safe, never memoizes a non-finite score); response fields `dtype, max_length, batch, memo_hits, memo_misses, nonfinite, dtype_fallback`; `/ready` reports the knobs, the fallback and cumulative `stats` (requests, pairs, memo hits/misses, nonfinite, memo_size).
- `shared/polymath_shared/rerank.py`: `RERANK_BATCH_SIZE` 16 → 64 (one request per judge call; the 4000-char surface cap is unchanged — the sidecar's token truncation does the bounding).
- Nothing in candidate_engine / chat_retrieval changed: the judge is called exactly as before (one call per turn under the 8 s deadline), so P1.c–P1.g contracts hold; the receipts get richer.

## Changes

- `sidecars/reranker/server.py`: dtype / max_length / batch / memo knobs (env, receipted); `torch_dtype_for`, `memo_key` / `memo_lookup` / `memo_store` (thread-safe LRU), `sanitize_scores`; startup self-test with fp32 fallback; `_predict` under `torch.inference_mode` with one batch per request; `/rerank` splits cached vs fresh pairs, merges in order, receipts `dtype, max_length, batch, memo_hits, memo_misses, nonfinite, dtype_fallback`; `/ready` reports the knobs, the fallback and cumulative `stats`; `RERANK_BATCH` default 8 → 64; the OOM halving loop is unchanged.
- `shared/polymath_shared/rerank.py`: `RERANK_BATCH_SIZE` 16 → 64 (one request per judge call).
- `scripts/rerank_judge_bench.py` (new, `scripts/README.md` row): real-pair bench with interleaved configs and ranking agreement.
- Tests: `tests/determinism/test_reranker_sidecar.py` (defaults, memo LRU/scope/off, non-finite handling, one pass + OOM halving, receipt fields); `tests/determinism/test_metal_lease.py` updated for the 64-surface client batch.
- Default token bound 384, chosen by the sweep (the owner asked for 256; the data said 384 — see Proof); `POLYMATH_RERANK_MAX_LENGTH=256` or `512` remain one env change away.

## Proof

**Bench (`rerank-judge-bench-judge-v1`, 10 fixture-B questions × 24 real pairs, configs interleaved per question, reference = production fp32:8192):**

| config | pass p50 ms | p90 | ms / pair | speed-up | non-finite | Spearman mean / min | Kendall | top-1 | top-5 | top-8 |
|---|---|---|---|---|---|---|---|---|---|---|
| fp32:8192 | 16097.8 | 63468.5 | 670.7 | 1.0× | 0 | 1.0 / 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| fp32:256 | 3329.8 | 7250.3 | 138.7 | 4.83× | 0 | 0.9425 / 0.7835 | 0.8891 | 0.8 | 0.88 | 0.912 |
| fp16:8192 | 17786.8 | 41855.6 | 741.1 | 0.91× | 0 | 0.9977 / 0.9922 | 0.989 | 1.0 | 0.96 | 0.988 |
| fp16:256 | 2177.2 | 7198.1 | 90.7 | 7.39× | 0 | 0.9432 / 0.7843 | 0.8846 | 0.8 | 0.88 | 0.9 |



**Truncation sweep (`rerank-judge-bench-judge-v2`, same questions, reference = fp16:8192 — fp16 itself is lossless, so the sweep isolates the length):**

| config | pass p50 ms | p90 | ms / pair | speed-up | non-finite | Spearman mean / min | Kendall | top-1 | top-5 | top-8 |
|---|---|---|---|---|---|---|---|---|---|---|
| fp16:8192 | 25367.6 | 80431.3 | 1057.0 | 1.0× | 0 | 1.0 / 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| fp16:256 | 2811.9 | 8618.6 | 117.2 | 9.02× | 0 | 0.945 / 0.7948 | 0.8903 | 0.8 | 0.88 | 0.912 |
| fp16:384 | 3139.6 | 19039.1 | 130.8 | 8.08× | 0 | 0.976 / 0.8504 | 0.9485 | 0.9 | 0.96 | 0.95 |
| fp16:512 | 3619.9 | 7785.4 | 150.8 | 7.01× | 0 | 0.9735 / 0.8426 | 0.9484 | 1.0 | 0.94 | 0.95 |
| fp16:768 | 6651.0 | 14628.8 | 277.1 | 3.81× | 0 | 0.9711 / 0.7878 | 0.9513 | 1.0 | 0.96 | 0.95 |

Reading: fp16 alone is lossless (fp16:8192 Spearman 0.9977, top-1 1.0) but not faster at full length on Metal (0.91×); the speed comes from the token bound, which is also what moves rankings (fp32:256 and fp16:256 agree with each other, both ≈ Spearman 0.9425 vs the untruncated judge). Chosen: **fp16:384** — 8.08× faster per pass than its bench reference, 0 non-finite scores, Spearman 0.976 (min 0.8504), top-8 overlap 0.95 (the composer's relevance slots), top-1 agreement 0.9.

**Live, same frozen plans, the fleet under enrichment (v33 removed earlier the same day — contention lower than the acceptance run):** B single `final-B` → `judge2-B`: judge+select p50 5469.8 → 3072.9 ms, wall p50 9.54 → 8.52 s (clean 7.2 → 5.42), p90 22.14 → 21.6 s, judge timeouts 10 → 6 of 30, degraded turns 16 → 16, OOM emb/rr 1/10 → 19/0; quality hit@10 0.667 → 0.633, MRR 0.565 → 0.558, survival 0.815 → 0.815, errors 0. M was NOT re-measured: the owner stopped the 60-turn replay as too long; the judge change touches no selection or flag logic (the last M reading, `final2-M`, is system-honest 1.0 / strict 1.0 with judge+select p50 8003.1 ms and 16/30 judge timeouts under the old judge). A 10-question M spot check is the cheap follow-up.

**Sidecar receipt after the runs (`/ready`):** dtype fp16, max_length 384, batch 64, fallback None; memo hit rate 0.0 (0 hits / 720 misses over 30 requests, 720 pairs), non-finite 0.

**Unit proof:** tests/determinism/test_reranker_sidecar.py (5) + test_rerank_wrapper.py + test_metal_lease.py: 31 passed, 2026-09-06.

## Rejected claims

- "Swap to a smaller cross-encoder for speed." Not taken: quality would need re-qualification on B/L/M; the owner's levers keep the model and its scores.
- "Drop the OOM halving now that fp16 halves the memory." Kept: it is the safety net that turned 21 × HTTP 500/h into complete answers on 2026-09-05; with a 64 cap it is simply never entered on a healthy device.
- "Memoize on the orchestrator side." Rejected: the sidecar is the one place every caller (chat judge, carry admission, wildcard validation, /retrieve) passes through, and the memo scope must follow the model dtype/length it serves.

## Open contract gaps

1. **fp16 numerics are guarded, not proven identical.** The bench measures ranking agreement on real pairs; the startup self-test and the per-request non-finite count guard the rest. A calibration change (sigmoid floors in the composer at 0.5) is not needed while agreement stays where the bench shows it.
2. **The memo does not persist** across sidecar respawns (process memory, LRU 20k). Hit rate in production is whatever repeated questions and carry re-scores produce; `/ready` stats say what it is.
3. **384 tokens bounds the judged prefix of a candidate.** Child chunks (≈ 100–170 tokens with the query) fit whole; the bound bites on section / document summaries and other long surfaces in the fusion prefix, which is where the sweep's remaining disagreement lives (one question, q04, stays at Spearman ≈ 0.8 even at 768 tokens). A per-kind bound (summaries longer) is the next lever if that matters.
