# PROVIDER EQUIVALENCE RESULTS

corpus: ecom-meta-v1 · chunks: 40 · words: 4786

## Accepted density (post-gate)
| lane | model | facts/1K words | entities/1K words | quarantined | rejections | mean wall s |
|---|---|---|---|---|---|---|
| gemini1 | gemini-3.1-flash-lite | 12.1 | 29.3 | 5 | 22 | 3.9 |
| groq1 | qwen/qwen3.8-27b | 19.6 | 38.2 | 13 | 27 | 15.9 |
| nvidia | nvidia/nemotron-3.5-lightning-30b-a3b | 16.3 | 27.6 | 0 | 68 | 28.8 |
| primary | qwen3.5:397b-cloud | 28.6 | 64.1 | 0 | 103 | 5.2 |

## Pairwise FACT agreement (Jaccard over accepted (pred, subj, obj))
| A | B | agreement | A-only | B-only |
|---|---|---|---|---|
| gemini1 | groq1 | 0.10 | 44 | 80 |
| gemini1 | nvidia | 0.01 | 57 | 77 |
| gemini1 | primary | 0.04 | 51 | 130 |
| groq1 | nvidia | 0.02 | 91 | 75 |
| groq1 | primary | 0.04 | 85 | 128 |
| nvidia | primary | 0.02 | 73 | 132 |

## Owner gate
Tiering is the owner's call: a lane far below the top density, or pairwise agreement far under ~0.6, is a quality-tier candidate (overflow-only), and family-interleaved slices become worth wiring. Comparable lanes = the fleet is interchangeable as configured.