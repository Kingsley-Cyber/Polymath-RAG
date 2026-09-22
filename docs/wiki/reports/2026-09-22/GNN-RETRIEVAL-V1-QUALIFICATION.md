---
title: "GNN-RETRIEVAL-V1 — E2E qualification: the five modes, the causal controls, the verdict"
date: 2026-09-22
last_reviewed: 2026-09-22
status: complete
owner: "@king"
---

# GNN-RETRIEVAL-V1 — qualification (corpus `cinema`, 2026-09-22)

Retrieval-level, no LLM (plan §20): the frozen fixtures `eval/fixtures/chat_lexical_L.json` (15 exact-identifier queries) +
`chat_baseline_B.json` (15 grounded-QA queries), the exact live functions (`chat_retrieve_mode`; the SAME `_rerank_children` judge for
the fixed-budget arms), gold parents read from `chunks`. Raw rows: `docs/wiki/experiments/gnn-route/cinema/qualify-{m1,m2}-2026-09-22.json`.
Build manifests: `build-2026-09-22.json` (snapshot + M0 + M1 arms), `build-m2-2026-09-22.json` (M2 arms).

## Graph (snapshot `gs_3673c34e9b06f569c46a9782`, contract `embed_e794ec4cab197a3f`, dim 1024)
| ENTITY | CHILD | PARENT | E→E (Neo4j accepted) | E→C (mentions) | C→P (hierarchy) | missing vectors | orphans |
|---:|---:|---:|---:|---:|---:|---|---|
| 43,707 | 71,791 | 12,361 | 21,776 | 78,096 | 71,791 | parents without a map vector 368 (take their children's message); 0 entities / children without a vector | entities without a relation, children without a mention, parents without a child — in the manifest |

## Models
| family | contract | λ / residual | architecture | objective | seed | digest (real) | anchor cos (real / nograph / shuffled) |
|---|---|---|---|---|---|---|---|
| M0 | `m0-identity-v1` | identity | — | — | — | `m0_…` | 1.0 |
| **M1** | `m1-smooth-v1` | λ = 0.7, `h' = λh + (1−λ)Σ w h_u`, unit output | two deterministic hops (entity ← relations; child ← entities; parent ← children), relation priors 1.0 / 1.0 / 0.5 / `similar_to` 0.25 | none (no parameter) | 0 | `m1_2f14df897d8f8e36` | 0.979 / 1.000 / 0.970 |
| **M2** | `m2-hsage-v1` | residual `z = norm(h + 0.5·tanh(m))` | shallow HeteroSAGE, 2 layers, near-identity relation transforms (W_rel, W_mention, W_child) | InfoNCE link prediction over E–E / E–C / C–P with in-batch type-compatible negatives + η = 1 anchor `1 − cos(z, h)`; 30 epochs, Adam 1e-3, MPS, 29 s/arm; frozen gold never a label | 0 | `m2_746dfd1944b7cc3a` | 0.896 / 1.000 / 0.904 |

## E2E — the five modes (n = 30)
| Metric | FAST | HYBRID | GRAPH | WILDCARD | GNN (M1) | GNN (M2) |
|---|---:|---:|---:|---:|---:|---:|
| Recall@K (K = the mode's evidence rows) | 0.281 | 0.784 | 0.784 | 0.784 | 0.280 | 0.267 |
| Gold in union | 0.467 | 0.933 | 0.933 | 0.933 | 0.433 | 0.400 |
| Gold after rerank | 0.367 | 0.867 | 0.867 | 0.867 | 0.433 | 0.400 |
| MRR | 0.297 | 0.692 | 0.692 | 0.692 | 0.388 | 0.367 |
| Selected gold | 0.367 | 0.867 | 0.867 | 0.867 | 0.433 | 0.400 |
| Candidates (mean = unique) | 66.3 | 81.0 | 81.0 | 81.0 | 11.5 | 11.6 |
| p50 latency (ms) | 5,606 | 2,412 | 2,508 | 5,575 | 2,367 | 1,904 |
| p95 latency (ms) | 12,604 | 3,774 | 2,991 | 6,478 | 2,862 | 2,540 |

Per fixture, gold after rerank — L (exact identifiers): FAST 1 · HYBRID 15 · GNN 1 (no sparse lane in GNN or FAST; the identifiers need
lane C). B (grounded QA): FAST 10 · HYBRID 11 · **GNN-M1 12** · GNN-M2 11 — with 11.5 candidates against 81.

## GNN-specific
| | M1 | M2 |
|---|---:|---:|
| GNN unique-gold count / rate (gold the GNN route found AND the HYBRID union did not) | **0 / 0.000** | **0 / 0.000** |
| Overlap of the GNN union with HYBRID's | 0.37 | 0.42 |
| Gold parent nominated among the 8 route parents | 0.433 | 0.400 |
| real − no-graph (gold after rerank / MRR) | +0.033 / +0.027 | 0.000 / +0.006 |
| real − shuffled (gold after rerank / MRR) | **0.000** / +0.017 | +0.033 / +0.034 |
| topology_supported (real > nograph AND real > shuffled) | false | false |
| reranker survival (judged prefix / union, GNN alone) | 12 / 12 per query (every routed child judged) | 12 / 12 |

Controls, gold after rerank: M1 real 0.433 · nograph 0.400 · shuffled 0.433; M2 real 0.400 · nograph 0.400 · shuffled 0.367.

## TEST A — recall ceiling (HYBRID union vs HYBRID ∪ the additive GNN lane)
M1: baseline 0.933 → 0.933 (union 81 → 88; 1 query gained gold, none lost, rate unchanged at 28/30 because the gain fell on a query already covered by a
degraded baseline turn). M2: 0.933 → 0.933. **The GNN route adds no gold the existing union lacks on these fixtures.**

## TEST B — fixed budget K = 24 (same judge, same selected budget), gold after rerank / selected gold / MRR
| arm | M1 | M2 |
|---|---|---|
| A HYBRID prefix 24 | 0.867 / 0.867 / 0.484 | 0.867 / 0.833 / 0.500 |
| B 18 HYBRID + 6 GNN-real | 0.933 / 0.833 / 0.531 | 0.900 / 0.833 / 0.529 |
| C 18 HYBRID + 6 no-graph | 0.900 / 0.833 / 0.527 | 0.900 / 0.833 / 0.527 |
| D 18 HYBRID + 6 shuffled | 0.900 / 0.833 / 0.528 | 0.867 / 0.767 / 0.495 |

Six routed parent-children seats raise gold-after-rerank and MRR over the HYBRID prefix — but B ≈ C ≈ D (M1) and B = C (M2): the lift is
the PROJECTION / parent-route seat, not the topology. Selected gold does not improve (−0.034 M1; 0 M2).

## Regression
Determinism + contracts suites in the worktree: green except `test_chat_hygiene::test_live_transform_turn_skips_retrieval_when_the_compiler_is_on`,
which fails identically on untouched `production` (a live-compiler test). New tests: `test_gnn_route.py` 13, `test_gnn_offline.py` 6, engine suite
59 (one pin extended for the receipted lane set); frontend `retrieval-modes.test.ts` 2/2, `tsc` clean. Existing modes: byte-identical union when the
GNN lane is off (test), `gnn_route = 0` on every non-GNN turn (HTTP + UI), FAST / HYBRID / GRAPH / WILDCARD answer normally through the same
`/chat/stream`. Cross-corpus: the parent search is corpus-filtered and re-checks the payload (test). Frontend E2E (built-in browser, experiment
server on :7201 from this worktree): the selector shows `HYBRID / GRAPH / WILDCARD / GNN`; selecting GNN sends `mode: "GNN"` on `/chat/stream`;
the turn's query trace shows requested = executed = GNN, union 12 = `gnn_route` only, 12 selected, 12 cited, a grounded answer; switching to HYBRID
in the same UI gives a normal HYBRID turn (union 209, `gnn_route 0`). Two pre-existing UI facts, not caused by this change: FAST is not in the v2
public selector (backend accepts it), and a first message on a scratch chat still strands its stream (the scratch-key remount trap) — "+ New chat"
works.

## Conclusion (plan §32 — from the measured controls)
- **A. GNN adds unique graph-derived retrieval value — NOT supported.** Unique gold 0 / 30 for both families; Test A adds no gold.
- **B. GNN improves recall only by increasing candidate budget — partly.** With the budget fixed (Test B) six routed seats do raise gold-after-rerank / MRR over the HYBRID prefix, but the controls raise it just as much.
- **C. GNN mostly duplicates existing Polymath routing — SUPPORTED.** Overlap 0.37–0.42 with HYBRID; every gold it reaches, HYBRID already reaches; on grounded QA the GNN route alone matches HYBRID (12 / 11 of 15) with one-seventh of the candidates.
- **D. GNN projection helps, but actual graph topology is not causal — SUPPORTED.** real ≤ shuffled (M1) / real = nograph (M2) on gold-after-rerank; `topology_supported: false` for both families.
- **E. Excessive noise — NOT supported.** 12 / 12 routed children survive the judge; latency is the lowest of the five modes.

**Verdict: D + C.** A cheap, well-behaved parent route whose value on this corpus comes from the parent-MAP projection, not from the
propagated topology. Keep `GNN` selectable and experimental (default off in every other mode); do not promote. Substrate limitation to report,
not to fix here (plan §3 / §33): the accepted relation graph is thin and typed by predicate only (21,776 relations for 43,707 entities, no
confidence), and the exact-identifier fixture needs the sparse lane the GNN route deliberately lacks.
