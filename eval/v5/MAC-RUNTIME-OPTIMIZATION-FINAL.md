# MAC-RUNTIME-OPTIMIZATION — mission log

MISSION: POLYMATH_PROJECTION_AND_EMBEDDER_CRITICAL_PATH_OVERRIDE
START_HEAD: 6a66e4f
STARTED: 2026-08-27T00:30 local

## Phase 0 — baseline (drain in progress)

Measured before any change:

- project_qdrant anatomy: ~95% embedding. One embedder call per ~7.0s,
  8 texts/call (max_batch_texts=8) = ~1.1 texts/sec effective,
  ~314 tokens/sec.
- **P0 ROOT CAUSE (bigger than restart amplification): the chunk lane
  in project_qdrant_worker has NO `_already_current` receipt filter and
  NO slice checkpointing, and `_chunks_for_run` joins runs by CORPUS —
  every ticket embeds every chunk in the corpus.** 12 tickets x 8,351
  chunks ≈ 100k embeddings scheduled where ~8.4k are needed. The routing
  lane received precisely this fix after a documented incident
  (`_already_current` docstring: "each ticket re-embedded all 19,016
  chunks... the real reason projections never converged"); the chunk
  lane did not.
- Restart amplification (secondary): chunk receipts commit only at
  ticket settlement, so worker death mid-ticket forfeits all credit.
  Observed: 0/12 project_qdrant tickets done at 00:09 despite points
  existing since ~19:30; fleet restarts (converge swap ~20:5x, reranker
  cap fix ~23:5x) each restarted the in-flight quadratic ticket.
- Extraction (measured, corrects an earlier overclaim): 1 worker ≈ 33
  children/min; 4 workers ≈ 32 children/min aggregate. Worker scaling
  gave ZERO throughput; GLiNER sidecar serially saturated. CPU% of the
  sidecar process (16%) was misleading — Metal work is invisible to it.
- Qdrant exonerated pending Phase 5: upsert is one batched wait=True
  call per slice; UPSERT_BATCH=128; QDRANT_TIMEOUT_S=300.

## Archaeology (Phase 3/4 pre-work, read-only)

- max_batch_texts=8: introduced in 8ca4523 (2026-08-22, the 13 GB-era
  budget commit) alongside max_batch_tokens=16384 with the quadratic-
  attention rationale. Conservative-historical candidate; benchmark
  before changing.
- MLX embedder exists: ~/PolymathRuntime/apple_ml_services/embedder_mlx/
  main.py — mlx-community/Qwen3-Embedding-0.6B-mxfp8 via mlx-embeddings,
  dim 1024, pooled sentence embeddings, warmup probes, /info endpoint.
  SAME model family as production neural-embed-v1 but mxfp8-quantized;
  parity panel required before any contract decision.
- Production contract has query/document prefix machinery
  (embedding_contracts.py) — MLX parity must include prefix behavior.

## Phase 0 execution plan (within CURRENT_RUN constraints)

1. Let the leased ticket (Practice Tests) settle untouched — its wall
   time is the OLD baseline; its settlement writes the first chunk
   receipts.
2. In the inter-ticket gap: apply the chunk-lane fix (receipt filter +
   sliced out-of-band checkpoints, mirroring _write_routing_points),
   restart workers. Forced replay: at most minutes of the next ticket.
3. Remaining 11 tickets become incremental. Record NEW ticket wall
   times as the immediate before/after.

(fill in as phases complete)

## Phase 4 — embedder saturation (MEASURED 2026-08-27, live sidecar, idle window)

Representative ~1,100-char (~280-token) production chunks:

| batch | p50 ms | texts/s |
|---|---|---|
| 1 | 291 | 3.4 |
| 4 | 742 | 5.4 |
| 8 | 1,397 | 5.7 |
| **16** | **2,321** | **6.9 ← optimum** |
| 32 | 9,051 | 3.5 ← production config (worst measured) |

Caller matrix at batch 8: 1/2/3 concurrent callers = 5.8/5.7/5.8 texts/s —
FLAT. The sidecar serializes; caller concurrency adds nothing (same
lesson as GLiNER, now proven for the embedder).

Consequences: worker EMBED_BATCH 32→16 is a ~2x in-contract fresh-embed
win; caller-based scaling is rejected by measurement. Mac ceiling on
the current backend: ~6.9 texts/s ≈ 1,900 tokens/s.
max_batch_texts=8 origin: 8ca4523 (13 GB-era memory guard) — sidecar-
internal split; the 32-text client call pays 4 sequential internal
batches plus overhead.

## Phase 5 — MLX qualification (MEASURED)

mlx-community/Qwen3-Embedding-0.6B-mxfp8 via mlx-embeddings (mlx 0.31.2),
forced-eval timings, same 32 chunks:

| batch | p50 ms | texts/s |
|---|---|---|
| 1 | 101 | 9.9 |
| 8 | 736 | **10.9** |
| 16 | 1,489 | 10.7 |
| 32 | 4,337 | 7.4 |

Peak MLX memory 2.59 GiB; l2-normalized, dim 1024; cold load 27.8 s
(with download). Speed vs PyTorch best: 1.6x (10.9 vs 6.9).

Parity vs production vectors: doc cross-impl cosine mean 0.972 /
min 0.925; query mean 0.975. Retrieval: top-1 SAME 4/4 queries,
overlap@5 ≥ 4/5. Faithful bf16 MLX variant does NOT exist upstream
(only 4bit-DWQ / 8bit / mxfp8).

DECISION: PYTORCH_MPS_KEEP for neural-embed-v1 (0.925 min-cosine
forbids silent in-contract swap; mixing backends corrupts existing
collection geometry). MLX-mxfp8 = qualified CANDIDATE for a future
neural-embed-v2 contract (owner choice: new corpora only, or re-embed).

## Phase 6 — Qdrant pure write benchmark (MEASURED)

Isolated 1024-dim cosine collection, precomputed vectors, prod payloads:
100 pts = 34 ms · 500 = 158 ms · 1,000 = 321 ms (≈3,000 points/s single
request); 5,000 pts in production-shape 128-batches: 3.3 s wall = 1,527
points/s. (Single 5,000-point request exceeds Qdrant's 32 MB JSON body
limit — transport artifact, production batches at 128.)

VERDICT: QDRANT_BOTTLENECK = NO. The whole 8,351-point corpus is ~3-5 s
of Qdrant time. Qdrant optimization is closed.

## Phase 7 — summary lane (observed during drain)

Generation is deterministic CPU assembly (build_parent_summary — no
model calls), content-addressed (input_hash dedup, ON CONFLICT DO
NOTHING). Ticket cadence ~2.5-3 min per document (~140 parents/book,
per-parent child/fact/entity assembly through PG). Bottleneck class:
per-ticket orchestration + DB roundtrips, NOT inference. Full profile
after drain.
