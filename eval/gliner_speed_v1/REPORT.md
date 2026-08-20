# GLINER-SPEED-V1 — results

Design and predictions fixed in `PLAN.md` before execution. Arms run one
at a time; arm A re-run last as A2 to test thermal drift.

## Deviations from plan

- **`fastino/gliner2-base-mlx` does not exist** (HTTP 404). No MLX build
  of gliner2 is published — only base/large/multi plus community ONNX
  and int8 forks. Ran `fastino/gliner2-base-v1` on MPS instead.
- GLiNER medium was ALREADY on MPS, not CPU. Both arms therefore share
  the PyTorch/MPS backend, so the speed delta is a genuine model delta
  rather than a runtime delta — cleaner than the planned comparison.
- gliner2 installed into an isolated `.venv-gliner2` (Python 3.11) so it
  could not upgrade torch and disturb the frozen GLiNER pin.

## Results

| arm | model | labels | ms/slice | proposed | exact (of 20 gold) | partial | missed | type ok | extra |
|---|---|---|---|---|---|---|---|---|---|---|
| A | medium | identity | 33.8 | 58 | 15 | 5 | 0 | 13/15 | 29 |
| B | medium | descriptive | 59.4 | 21 | 8 | 1 | 11 | 8/8 | 6 |
| C | gliner2 | identity | 34.2 | 78 | 16 | 4 | 0 | 16/16 | 36 |
| D | gliner2 | descriptive | 55.8 | 66 | 12 | 4 | 4 | 12/12 | 33 |

Drift check: A2 re-run after all arms gave 34.96 / 33.31 ms vs A's
34.18 / 33.40, entity counts identical (34, 24). No thermal drift.

## Prediction results

| # | Prediction | Result |
|---|---|---|
| 1 | Descriptive labels change yield on gliner_medium | **CONFIRMED** — 58 -> 21 proposals |
| 2 | Descriptive labels do NOT fix boundary contraction | **CONFIRMED** — gliner2 partials unchanged 4 -> 4; medium's 5 -> 1 is explained by 11 outright misses, not better boundaries |
| 3 | gliner2 base is faster per slice | **FAILED** — 34.2 vs 33.8 ms, no difference |
| 4 | Model swap moves WHICH entities more than label swap | **FAILED** — label swap moved yield far more (58->21) than model swap (58->78) |

## Findings

**1. Latency is driven by label length, not model choice.** Identical
34 ms/slice for both models at identity labels; +63-76% for descriptive
labels in both. GLiNER2 buys no speed.

**2. Descriptions are a precision instrument, not a quality fix.** On
medium they cut over-generation 29 -> 6 (-80%) with perfect typing
(8/8), but lose 11 of 20 gold entities. Too blunt to ship as-is.

**3. Descriptions do NOT solve multiword/boundary contraction** — the
hypothesis that motivated the test. Ledger row 8 keeps its owner
(admission/identity), not the label vocabulary.

**4. gliner2-base-v1 + plain identity labels is the only arm that
improves on production for free**: exact 16 vs 15, missed 0, and
**typing 16/16 vs 13/15** at identical latency. It over-generates more
(36 vs 29 extra), which is admission-gate work, not model work.

GLiNER typing drift was a named I4 FP driver ("Kubernetes->Product,
Nimbus platform->Organization"). Arm C typed every matched gold span
correctly.

## What this does NOT decide

Entity proposal only. No fact, admission, or retrieval claim. Two
documents, 20 gold spans, 23 sentence slices — adequate for latency
(10 timed reps, drift-checked), directional for quality. No arm is
qualified for promotion on this evidence; a model swap would need the
full frozen I4 gate under the entity-admission and canonicalization
contracts.

## CORRECTION (post-publication)

Finding 4 called gliner2-base-v1 a free improvement candidate. That
reading does not survive inspection of its raw proposals.

Its confidence saturates — `delays` 1.000, `regional` (Location) 0.966,
`Corval` typed **Person** 0.998, `Corval Freight` typed **Product**
0.990, `FreightNet` emitted as both Product 0.997 and Technology 0.975.
Threshold 0.5 is therefore inert for this model, and core organizations
are mistyped.

The 16/16 typing figure scored **matched gold spans only**; it was blind
to typing quality inside the 36 over-generated spans. gliner2 is NOT
qualified as an improvement. See ledger row 34.
