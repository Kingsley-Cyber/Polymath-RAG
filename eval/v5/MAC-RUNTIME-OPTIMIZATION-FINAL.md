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

## Phase 11 — conditional reranking (MEASURED, sealed 10-kind panel)

release-books-v1, HYBRID, identical orchestrators (G3 on = 7200 vs
G3 off = 7201):

- top-1 citation agreement: 4/10 · identical final answers: 3/10
  (all three = abstentions, which agree 10/10 both ways)
- rerank latency cost: ~1.5 s warm (0.8-0.9 s → 2.2-2.5 s)
- the earlier "reranker kept the same top passages" observation was a
  2-query anecdote; the panel shows reranking CHANGES the outcome on
  most queries.

DECISION: CONDITIONAL_RERANK = REJECTED. No deterministic skip signal
can preserve the qualified quality bar when 60% of orderings move; the
~1.5 s cost is the price of the G3-qualified ranking. Abstention
honesty is rerank-independent (10/10 verdict agreement). Revisit only
with a much larger labeled panel.

## Phase 0 — CLOSED. Full drain record (cysa-study-v1, 12 books, 8,351 chunks)

Upload 08-26 11:06 → last ticket settled 08-27 00:58 (~13h52m wall,
including the 4h drift-guard wedge, quadratic chunk-lane waste, and
restart amplification — all since fixed). Per-stage last settlements:
extract 18:57 · project_qdrant 00:26→00:31 (all 12 within 5 min of the
checkpoint patch) · neo4j 00:37 · parent summaries 00:50 · document
00:53 · corpus 00:56 · vocabulary 00:58. Final: 12/12 query_ready,
corpus flipped production/query_enabled. Layers: 2,959 parent / 22 doc
/ 3 corpus summary rows; 10,168 Qdrant points.

Stranded-run note: one run sat 'reconciling' with all tickets done
(post-verify lanes overwrite verify's verdict; nothing re-verifies
promptly). The control plane's slow pass converged it in ~10 min.
OPERATOR-STATE-V1 (ff30948) removes the false-DEGRADED half of this;
the re-verify latency is acceptable and left unchanged.

## Phase 8 — extract checkpointing: DEFERRED (analysis, not hypothesis)

- Replay exposure bounded: 12-25 min per book at the measured 33
  children/min; all extraction writes are content-addressed ON CONFLICT
  — replay costs time, never correctness.
- Both observed mid-extract losses were VOLUNTARY restarts, now
  eliminated (autopilot parks GLiNER only at zero extract backlog;
  code changes land in inter-ticket gaps).
- No clean seam: pass 1 batches GLiNER calls by label composition
  across the whole document, syntax evidence is one whole-doc call, and
  the compiler passes are doc-global. A checkpoint boundary would
  restructure the frozen semantic stage (DO_NOT_REDESIGN).
Revisit only if unattended crash loss is actually observed.

## Phase 15 — DRAIN-state actual memory (measured 00:54)

Docker actual: qdrant 1.81 GB · neo4j 1.0 GB · postgres 0.25 GB ·
redis 0.01 GB = ~3.1 GB used of 4.8 GB VM reservation. Sidecar RSS
135-430 MB each (Metal buffers not fully visible in RSS — budget caps
remain the honest GPU number). Workers 25-90 MB; control 92 MB.
Whole system: 15.1 GB of 32 GB in use.

## Query availability during ingest (measured constraint)

ALL retrieval modes route through the reranker gate — with the pipeline
fleet loaded (no reranker in budget), every query fails typed
(rerank_unavailable), not just HYBRID. GLiNER + reranker cannot coexist
under the 18.5 GB ceiling (19.6 committed). Autopilot therefore gives
extraction priority while extract backlog exists; queries during heavy
ingest fail loudly. OWNER OPTION: Docker VM 5.0→4.0 GB (+ spaCy parked)
would fit reranker alongside the pipeline = queryable-while-ingesting.

## Phase B — FRESH projection telemetry (bench-fresh-v1, PROJECTION-TELEMETRY-V1)

Recovery-attempt ticket (post-crash), measured by the stage itself:
total 120.1 s = embed 117.7 s (98.0%) · qdrant 0.43 s (0.36%, 8 batches)
· receipts 0.24 s + lookup 8 ms (0.2%) · control ~1.4%.
47 embed calls · 726 texts = 6.2 texts/s live (concurrent GLiNER load;
idle optimum 6.9). 'project_qdrant' is formally an embedding stage.

## Phase C — checkpoint crash qualification: PASS

Kill after 4 durable slices (256/485 chunk receipts). On supervisor
recovery: representations_already_current = 256 — every checkpointed
slice SKIPPED; 229 remaining chunks + routing embedded fresh; max
replay ≤ 1 in-flight slice. Integrity: 485/485 Qdrant points, ZERO
duplicate active receipts per (projection, kind, entity) — the 2x row
count is the designed qdrant+neo4j projection pair — and no early
query_ready (run stayed reconciling under OPERATOR-STATE-V1 with open
lanes).
  OLD_MAX_REPLAY: whole corpus pass · NEW_MAX_REPLAY: 64 reps (~10 s)

## Phase D — EMBED-BATCH-16: KEEP (measured end-to-end)

Live fresh projection ran 6.2 texts/s under mixed load vs 3.5 texts/s
at the old batch-32 config = 1.77x measured, no OOM, no memory delta
(same 3.5 GB cap). Batch 16 is the qualified transport value.
