---
title: "RERANK-JUDGE-BENCH judge-v1: fp32 vs fp16 vs 256-token truncation on real judge pairs"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# RERANK-JUDGE-BENCH judge-v1

run 2026-09-06T14:28:23+00:00 · Qwen/Qwen3-Reranker-0.6B on mps · 10 fixture-B questions × 24 real pairs (fusion prefix of the acceptance modes replay, texts from Postgres, client cap 4000 chars) · configs interleaved per question · reference = fp32:8192

| config | pass p50 ms | pass p90 ms | ms / pair | speed-up vs reference | non-finite | Spearman mean / min | Kendall | top-1 | top-5 overlap | top-8 overlap |
|---|---|---|---|---|---|---|---|---|---|---|
| fp32:8192 | 16097.8 | 63468.5 | 670.7 | 1.0× | 0 | 1.0 / 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| fp32:256 | 3329.8 | 7250.3 | 138.7 | 4.83× | 0 | 0.9425 / 0.7835 | 0.8891 | 0.8 | 0.88 | 0.912 |
| fp16:8192 | 17786.8 | 41855.6 | 741.1 | 0.91× | 0 | 0.9977 / 0.9922 | 0.989 | 1.0 | 0.96 | 0.988 |
| fp16:256 | 2177.2 | 7198.1 | 90.7 | 7.39× | 0 | 0.9432 / 0.7843 | 0.8846 | 0.8 | 0.88 | 0.9 |

Per question (ms · Spearman · top-8 overlap vs reference):

- q00 (24 pairs, doc p50 492.5 chars): fp32:8192 3818 ms ρ 1.0 top8 1.0; fp32:256 2387 ms ρ 0.9757 top8 0.875; fp16:8192 2768 ms ρ 0.9948 top8 1.0; fp16:256 1750 ms ρ 0.9757 top8 0.875
- q01 (24 pairs, doc p50 542.0 chars): fp32:8192 3612 ms ρ 1.0 top8 1.0; fp32:256 2394 ms ρ 0.927 top8 0.875; fp16:8192 2636 ms ρ 0.9991 top8 1.0; fp16:256 1745 ms ρ 0.9261 top8 0.875
- q02 (24 pairs, doc p50 414.5 chars): fp32:8192 115542 ms ρ 1.0 top8 1.0; fp32:256 2623 ms ρ 0.9174 top8 0.875; fp16:8192 28195 ms ρ 0.9991 top8 1.0; fp16:256 2972 ms ρ 0.92 top8 0.875
- q03 (24 pairs, doc p50 272.0 chars): fp32:8192 4972 ms ρ 1.0 top8 1.0; fp32:256 2382 ms ρ 0.9974 top8 1.0; fp16:8192 3360 ms ρ 1.0 top8 1.0; fp16:256 5963 ms ρ 0.9922 top8 1.0
- q04 (24 pairs, doc p50 801.0 chars): fp32:8192 63468 ms ρ 1.0 top8 1.0; fp32:256 7401 ms ρ 0.7835 top8 0.625; fp16:8192 58187 ms ρ 0.9983 top8 1.0; fp16:256 15078 ms ρ 0.7843 top8 0.625
- q05 (24 pairs, doc p50 561.0 chars): fp32:8192 26558 ms ρ 1.0 top8 1.0; fp32:256 6260 ms ρ 0.9661 top8 1.0; fp16:8192 37453 ms ρ 0.9922 top8 1.0; fp16:256 2216 ms ρ 0.9704 top8 1.0
- q06 (24 pairs, doc p50 697.0 chars): fp32:8192 10416 ms ρ 1.0 top8 1.0; fp32:256 3472 ms ρ 0.9148 top8 0.875; fp16:8192 7379 ms ρ 0.9983 top8 1.0; fp16:256 2139 ms ρ 0.9174 top8 0.875
- q07 (24 pairs, doc p50 353.5 chars): fp32:8192 21780 ms ρ 1.0 top8 1.0; fp32:256 3188 ms ρ 0.9835 top8 1.0; fp16:8192 41856 ms ρ 0.9974 top8 0.875; fp16:256 2109 ms ρ 0.9826 top8 0.875
- q08 (24 pairs, doc p50 732.0 chars): fp32:8192 28960 ms ρ 1.0 top8 1.0; fp32:256 3809 ms ρ 0.9661 top8 1.0; fp16:8192 33762 ms ρ 0.9991 top8 1.0; fp16:256 7198 ms ρ 0.9678 top8 1.0
- q09 (24 pairs, doc p50 407.5 chars): fp32:8192 2876 ms ρ 1.0 top8 1.0; fp32:256 7250 ms ρ 0.9939 top8 1.0; fp16:8192 2202 ms ρ 0.9983 top8 1.0; fp16:256 1764 ms ρ 0.9957 top8 1.0
