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
