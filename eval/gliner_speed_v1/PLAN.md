# GLINER-SPEED-V1 — model × label-style benchmark

Speed AND entity quality. Direct sidecar benchmark — bypasses admission,
compiler, and projection so no downstream stage can confound the result.

## Design: 2x2 factorial

Two factors, so the label effect and the model effect are separable and
an interaction is detectable. A one-at-a-time design cannot tell whether
GLiNER2 "wins" because of the model or because it got better prompts.

| arm | model | labels |
|---|---|---|
| **A — CONTROL** | gliner_medium-v2.1 @ 40ec4193 (MPS) | identity (bare type names) |
| **B — VAR-LABEL** | gliner_medium-v2.1 @ 40ec4193 (MPS) | descriptive |
| **C — VAR-MODEL** | gliner2 base-mlx | identity |
| **D — BOTH** | gliner2 base-mlx | descriptive |

Arm A is today's production behaviour. Arm B is the "due diligence"
arm: GLiNER given its best shot before being compared to a successor.

## Controls (held constant in every arm)

- **Same 2 documents**: `01_northvale_health.md` (133 words, densest)
  and `05_corval_logistics.md` (94 words, sparsest) — the density
  extremes of the corpus.
- **Same input unit**: production per-sentence slices, identical slice
  list for all arms. Not whole-document — results must transfer to
  production behaviour.
- **Threshold 0.5** (the frozen production entity pin).
- **Label COUNT = 12 in every arm.** Critical: GLINER-QUERY-VOCAB-v2
  measured severe multi-label dilution (Kubernetes 0.929 single-label ->
  0.672 with two labels). Holding count fixed at 12 isolates label
  CONTENT from label COUNT. Varying both would be uninterpretable.
- **Worker fleet stopped** for the duration — no competing GPU load.
- **Round-robin arm execution**, not sequential blocks, so thermal drift
  cannot load onto whichever arm runs last.
- Same machine, same power state.

## Variables

1. `model` — gliner_medium-v2.1 vs gliner2 base-mlx
2. `label_style` — identity vs descriptive (`LABELS.json`)

## Measurement

**Speed** (the point of the test):
- 3 warm-up passes per arm, DISCARDED (model load + first-inference
  graph compile are one-off costs and would swamp a 5-slice document).
- 10 timed repetitions per document per arm.
- Report **median and p95** per slice and per document, plus min.
  Not mean — a single GC or thermal blip skews a 10-sample mean.
- Model load time reported separately as a one-off, never folded into
  per-slice latency.

**Quality** (against `eval/i4/gold/entity_gold.json`, those 2 docs only):
- span recall — of gold spans, how many proposed at all
- typing accuracy — of proposed gold spans, how many carry the gold type
- boundary exactness — proposed span offsets == gold offsets
- over-generation — proposed spans matching no gold span

## Pre-registered predictions (falsifiable)

1. **Descriptive labels change entity yield on gliner_medium** in some
   direction. Rationale: vocab-v2 proved label CONTENT matters (case
   sensitivity: `Technology` fires, `technology` does not) but only ever
   tested short aliases, never descriptions.
2. **Descriptive labels do NOT fix boundary contraction.** "Crestline"
   vs "Crestline Automation", "portside" vs "Portside warehouse" are
   span-scoring behaviour, not label-semantics. If this prediction is
   WRONG, descriptions become a direct precision lever and ledger row 8
   gets a cheap fix. This is the prediction most worth being wrong about.
3. **gliner2 base-mlx is faster per slice** than gliner_medium on MPS.
4. **The model swap moves WHICH entities are found more than the label
   swap does.**

## Honest comparison caveats

- Different runtimes (PyTorch/MPS vs MLX) on the same silicon. A speed
  delta is a *runtime + model* delta, not a model-architecture delta.
  It cannot be attributed to model quality.
- 2 documents, ~20 sentence slices. Adequate for latency (10 reps each),
  thin for quality — quality results are directional.
- gliner2 base-mlx is a DIFFERENT model with a different label
  vocabulary and training. A quality difference is not evidence that
  GLiNER2 "understands prompts better" unless arms C and D diverge from
  each other the same way A and B do.

## Status

- Arms **A and B: executable now.**
- Arms **C and D: BLOCKED** — neither `gliner2` nor `mlx` is installed.
  Adding them is a dependency change requiring declaration; the frozen
  GLiNER pin must not be disturbed, so gliner2 has to run as a SEPARATE
  sidecar/process, never by swapping the pinned runtime.

## What this test does NOT decide

Nothing about the ingestion pipeline, admission, or fact quality. It
measures entity proposal only. A faster or better entity proposer does
not address the current blocker (ledger rows 8, 21 — identity and
admission), and must not be promoted on speed alone.
