---
title: "RERANK-JUDGE-BENCH judge-v2: fp32 vs fp16 vs 256-token truncation on real judge pairs"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: measured
---

# RERANK-JUDGE-BENCH judge-v2

run 2026-09-06T14:39:47+00:00 · Qwen/Qwen3-Reranker-0.6B on mps · 10 fixture-B questions × 24 real pairs (fusion prefix of the acceptance modes replay, texts from Postgres, client cap 4000 chars) · configs interleaved per question · reference = fp16:8192

| config | pass p50 ms | pass p90 ms | ms / pair | speed-up vs reference | non-finite | Spearman mean / min | Kendall | top-1 | top-5 overlap | top-8 overlap |
|---|---|---|---|---|---|---|---|---|---|---|
| fp16:8192 | 25367.6 | 80431.3 | 1057.0 | 1.0× | 0 | 1.0 / 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| fp16:256 | 2811.9 | 8618.6 | 117.2 | 9.02× | 0 | 0.945 / 0.7948 | 0.8903 | 0.8 | 0.88 | 0.912 |
| fp16:384 | 3139.6 | 19039.1 | 130.8 | 8.08× | 0 | 0.976 / 0.8504 | 0.9485 | 0.9 | 0.96 | 0.95 |
| fp16:512 | 3619.9 | 7785.4 | 150.8 | 7.01× | 0 | 0.9735 / 0.8426 | 0.9484 | 1.0 | 0.94 | 0.95 |
| fp16:768 | 6651.0 | 14628.8 | 277.1 | 3.81× | 0 | 0.9711 / 0.7878 | 0.9513 | 1.0 | 0.96 | 0.95 |

Per question (ms · Spearman · top-8 overlap vs reference):

- q00 (24 pairs, doc p50 492.5 chars): fp16:8192 2490 ms ρ 1.0 top8 1.0; fp16:256 1757 ms ρ 0.9817 top8 0.875; fp16:384 2320 ms ρ 1.0 top8 1.0; fp16:512 2316 ms ρ 1.0 top8 1.0; fp16:768 2316 ms ρ 1.0 top8 1.0
- q01 (24 pairs, doc p50 542.0 chars): fp16:8192 2543 ms ρ 1.0 top8 1.0; fp16:256 1743 ms ρ 0.927 top8 0.875; fp16:384 2554 ms ρ 1.0 top8 1.0; fp16:512 2571 ms ρ 1.0 top8 1.0; fp16:768 2543 ms ρ 1.0 top8 1.0
- q02 (24 pairs, doc p50 414.5 chars): fp16:8192 26753 ms ρ 1.0 top8 1.0; fp16:256 10640 ms ρ 0.9165 top8 0.875; fp16:384 2671 ms ρ 0.9565 top8 0.875; fp16:512 3616 ms ρ 0.9452 top8 0.875; fp16:768 6571 ms ρ 0.9583 top8 0.875
- q03 (24 pairs, doc p50 272.0 chars): fp16:8192 2838 ms ρ 1.0 top8 1.0; fp16:256 1743 ms ρ 0.9922 top8 1.0; fp16:384 2692 ms ρ 1.0 top8 1.0; fp16:512 7785 ms ρ 1.0 top8 1.0; fp16:768 2843 ms ρ 1.0 top8 1.0
- q04 (24 pairs, doc p50 801.0 chars): fp16:8192 80431 ms ρ 1.0 top8 1.0; fp16:256 8619 ms ρ 0.7948 top8 0.625; fp16:384 23980 ms ρ 0.8504 top8 0.625; fp16:512 4780 ms ρ 0.8426 top8 0.625; fp16:768 6877 ms ρ 0.7878 top8 0.625
- q05 (24 pairs, doc p50 561.0 chars): fp16:8192 23982 ms ρ 1.0 top8 1.0; fp16:256 3463 ms ρ 0.9704 top8 1.0; fp16:384 4938 ms ρ 0.9791 top8 1.0; fp16:512 3648 ms ρ 0.9704 top8 1.0; fp16:768 21210 ms ρ 0.9809 top8 1.0
- q06 (24 pairs, doc p50 697.0 chars): fp16:8192 101050 ms ρ 1.0 top8 1.0; fp16:256 2161 ms ρ 0.9174 top8 0.875; fp16:384 3218 ms ρ 0.993 top8 1.0; fp16:512 3611 ms ρ 0.993 top8 1.0; fp16:768 6731 ms ρ 0.9991 top8 1.0
- q07 (24 pairs, doc p50 353.5 chars): fp16:8192 66587 ms ρ 1.0 top8 1.0; fp16:256 7114 ms ρ 0.9835 top8 1.0; fp16:384 15014 ms ρ 0.9835 top8 1.0; fp16:512 3623 ms ρ 0.9861 top8 1.0; fp16:768 6891 ms ρ 0.9861 top8 1.0
- q08 (24 pairs, doc p50 732.0 chars): fp16:8192 53092 ms ρ 1.0 top8 1.0; fp16:256 5554 ms ρ 0.9687 top8 1.0; fp16:384 19039 ms ρ 0.9974 top8 1.0; fp16:512 12904 ms ρ 0.9974 top8 1.0; fp16:768 14629 ms ρ 0.9991 top8 1.0
- q09 (24 pairs, doc p50 407.5 chars): fp16:8192 2092 ms ρ 1.0 top8 1.0; fp16:256 1743 ms ρ 0.9974 top8 1.0; fp16:384 3061 ms ρ 1.0 top8 1.0; fp16:512 2087 ms ρ 1.0 top8 1.0; fp16:768 2121 ms ρ 1.0 top8 1.0
