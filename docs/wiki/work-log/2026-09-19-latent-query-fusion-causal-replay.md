---
change_id: LATENT-QUERY-FUSION-V2-CAUSAL
owner: wildcard-investigation
date: 2026-09-19
status: complete
architecture_impact: "LATENT-QUERY-FUSION-V2 LEVEL-3 CAUSAL experiment + differential-quality analysis (no code change; eval artifacts only). Fixed-upstream V1-flatten vs V2-fusion, both cap-sets from ONE real retrieval per query (identical fused list / RankedLane[] / arrivals / local rankings). TWO-LEVEL result: (1) DEEP-FAMILY ADMISSION (document count) = NULL on WLK-10 (1 V2 gain / 1 V2 loss per mode) — a narrow metric; equal-sized V1-only/V2-only swaps are a fixed-cap artifact (composition churn), NOT evidence of neutrality. (2) ARCHITECTURAL UTILITY (differential-quality, offline over the captured artifacts) = POSITIVE + asymmetric: V2 preserved 11–12 lane-winners/mode (local_rank 0) that the flatten truncates and displaced ZERO lane-winners V1 kept; per-query V2-better 1 (HYBRID)/4 (WILDCARD), V1-better 0 (both); WILDCARD 5 V2-only useful downstream evidence (3 C5-seated latent). Tradeoff = only the weakest q0-cap tail displaced (v1_pos 105–119 of 120, 0 lane-winners), answer-level q0_preserved 1.0. So V2 DELIVERS its designed behavior (preserve locally-important lane candidates for downstream judgment) safely; it does NOT raise deep-family doc count. The end-to-end A/B favored V2 but, upstream having varied, cannot causally attribute that gain to fusion. V2 SAFE + LIVE."
last_reviewed: 2026-09-19
---

## Contract
Owner correction (2026-09-19): the mission named the fixed-upstream V1/V2 replay as the clean causal
experiment; it had NOT been run (the 3-repeat A/B varied upstream; the synthetic seam test used hand-
built lanes). This slice runs it — smallest controlled experiment that isolates the fusion policy —
per the tightened spec (prove the counterfactual first; one real upstream per query; deterministic
discriminator; complete differential records; separate admission from downstream; 10 WLK probes; honest
paired reporting; a null is valid; no tuning).

## Changes
No production code. Method + eval artifacts:
- **Counterfactual proven first** (POINT 1): on a deterministic fixture (FakeMulti + subqueries, cap 5),
  flag-off V1 `union` IDs == flag-on `union_ids_uncapped[:merged_candidate_max]` EXACTLY. So the F3
  adapter's own `fallback` arg (`fused[:cap]`) IS the historical V1 cap-set.
- **One real retrieval per query**, both policies from it: monkeypatch `_latent_fused_union(fused,
  ranked_lanes, budget, fallback)` — `fallback` = V1 cap-set, return = V2 cap-set, identical inputs.
- **Deterministic discriminator**: HYBRID and (verified) WILDCARD both call the adapter EXACTLY ONCE
  per query (the sweep uses a different path); assert exactly one capture else AMBIGUOUS. 0 ambiguous
  in both runs (n=10 each). NOT "largest union".
- **Complete differential records** per changed candidate: chunk_id / doc / query_ids / lineage
  (query_id·origin·lane·local_rank, many-to-one) / v1_pos / v2_pos / downstream (final/seat/CA4).
- Artifacts: `eval/wildcard_latent_knowledge/CAUSAL-REPLAY-HYBRID-2026-09-19.json` +
  `CAUSAL-REPLAY-WILDCARD-2026-09-19.json`.

## Proof
`LIVE_PATH_PROVEN` (real retrievals, live sidecars) — the experiment; interpreted at TWO levels.
`CAUSAL-DIFFQUALITY-2026-09-19.json` is the offline differential-quality analysis (no new retrieval).

**(A) DEEP-FAMILY ADMISSION (document count) — NULL on WLK-10.** deep-family gain/loss = 1/1 in each mode
(HYBRID wc05 Timing / wc03 Ekman; WILDCARD wc10 Laban→final / wc03 Ekman). NOTE: the equal-sized
V1-only/V2-only swaps (HYBRID 68/68, WILDCARD 78/78) are a FIXED-CAP artifact — both policies pick
exactly N, so `|V1_only| == |V2_only|` by construction. Those counts are COMPOSITION CHURN, not utility;
they are NOT evidence of neutrality. The narrow, valid finding is only: no net deep-family document-count
gain on WLK-10.

**(B) ARCHITECTURAL UTILITY (differential-quality) — POSITIVE + asymmetric.** For every V1-only / V2-only
candidate, derived from the captured artifacts: lane-winner status (local_rank 0), origin, C5 seat,
CA4 grade, final membership, q0/DIRECT status.
| metric (fixed upstream) | HYBRID | WILDCARD |
|---|---|---|
| lane-winners V2 preserved (flatten truncated) | 12 | 11 |
| lane-winners V2 displaced (V1 kept) | **0** | **0** |
| V2-only useful downstream (final/seat/grade) | 1 | 5 |
| V2-only C5-seated latent (COMPLEMENTARY/DIVERGENT) | 0 | 3 |
| per-query: V2 better / V1 better / churn+equiv | 1 / **0** / 9 | 4 / **0** / 6 |
| DIRECT/q0 displaced — all marginal tail (v1_pos 105–119/120, 0 winners) | 19 | 24 |

V2 does what it was DESIGNED to do: it preserves locally-important lane-winners (subquery/bridge #1s the
q0-dominated flatten truncates) so they reach downstream C4/C5 judgment — preserving 11–12/mode and
displacing ZERO lane-winners V1 kept. It costs only the weakest q0-cap tail (positions 105–119, never a
lane-winner), and the answer keeps q0 (sentinel answer-level q0_preserved 1.0). Those preserved winners
get a fair trial; occasionally it pays off (WILDCARD: 5 V2-only useful, 3 C5-seated, across 4 queries).
**No query was made worse (V1-better = 0 in both modes).** The magnitude is modest (mostly churn), but
the direction is one-sided in V2's favor and matches the architecture's intent.

## The evidence stack (honest)
```
LEVEL 1 MECHANISM (synthetic seam, unit)          PASS   — fusion preserves a synthetic bridge winner
LEVEL 2 LIVE EXEMPLAR (wc01/05/07 receipts)       PASS   — origin flows; ranked lanes; wc01 chain fires
LEVEL 3a CAUSAL deep-family ADMISSION (fixed-up)  NULL   — no net deep-family doc-count gain on WLK-10
LEVEL 3b CAUSAL architectural UTILITY (fixed-up)  POSITIVE (asymmetric, modest) — lane-winners +11/+12,
                                                          displaced 0; V2-better 1–4, V1-better 0
LEVEL 4 END-TO-END A/B (3 repeats, WILDCARD)      V2>V1, but cannot be causally attributed to fusion
                                                          (upstream state varied between conditions)
LEVEL 5 SAFETY (CA5-SENTINEL-18, 18×4)            PASS   — halluc 0 / answer-level q0 1.0 / prov 1.0 / 0 flags
LEVEL 6 PRODUCTION (fleet)                         HEALTHY — flags on, one bundle, /ready
```

## Rejected claims
- REJECTED (my own earlier overclaim): "fusion causal benefit = zero." FALSE — that generalized a narrow
  deep-family DOC-COUNT null. The fixed-upstream utility analysis shows a real, asymmetric benefit
  (lane-winner preservation for downstream judgment; V1-better = 0).
- REJECTED: reading equal V1-only/V2-only swap counts as neutrality — they are a fixed-cap artifact.
- REJECTED: "the A/B gain was caused by upstream variance." The correct statement is weaker: the A/B
  favored V2 but, because upstream state varied, that experiment CANNOT causally attribute the gain to
  fusion (neither confirms nor denies causation).
- NOT claimed: a large deep-family reach win — deep-family doc-count admission is a NULL on WLK-10.
- No tuning of weights / preserve_top_n / K on these 10 probes (owner rule).

## Open contract gaps
Decision for the owner: V2 is SAFE and, at fixed upstream, DELIVERS its designed behavior (preserves
lane-winners for downstream judgment, never displaces one V1 kept, never makes a query worse, occasional
useful complementary evidence) — while NOT increasing deep-family document count. Magnitude is modest.
Current state: LEFT LIVE per prior owner instruction; the honest two-level result is recorded. REVERT
remains one step (3 `.env` flags → 0 + bounce) if the owner prefers to wait for a larger-magnitude
signal. A bigger benchmark would sharpen magnitude but not the direction (a control question, already
answered by the fixed-upstream design).
