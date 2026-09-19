---
change_id: LATENT-QUERY-FUSION-V2-CAUSAL
owner: wildcard-investigation
date: 2026-09-19
status: complete
architecture_impact: "LATENT-QUERY-FUSION-V2 LEVEL-3 CAUSAL experiment (no code change; eval artifacts only). Fixed-upstream V1-flatten vs V2-fusion replay isolates the fusion/truncation policy by deriving BOTH cap-sets from ONE real retrieval per query (identical fused list / RankedLane[] / arrivals / local rankings). RESULT = NULL: given identical inputs, V2 fusion reshuffles the cap heavily (68/78 chunks swapped each way) but does NOT net-improve deep-family admission (exactly 1 gain / 1 loss per mode, both modes). The mechanism WORKS (it does admit a deep winner the flatten truncates — wc05 Timing HYBRID, wc10 Laban WILDCARD→final) but its NET causal effect is zero. Therefore the end-to-end A/B gain (deep_final_reach 0.667 vs 0.467) is CONFOUNDED (upstream variance / mode / C5 seating), NOT causally isolated to fusion. V2 stays SAFE (sentinel) + LIVE per owner; its specific fusion benefit is causally UNPROVEN."
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
`LIVE_PATH_PROVEN` (real retrievals, live sidecars) — the experiment itself; the RESULT is a NULL.

(A) ADMISSION effect (identical upstream):
| mode | swap each way | deep-admission gain / loss | net | v2-only→final |
|---|---|---|---|---|
| HYBRID | 68 / 68 | 1 (wc05 Timing) / 1 (wc03 Ekman) | **0** | 1 |
| WILDCARD | 78 / 78 | 1 (wc10 Laban→final) / 1 (wc03 Ekman) | **0** | 4 (1 deep) |

Fusion changes WHO survives the cap substantially and symmetrically, but deep-family admission is a
wash — one clean win and one clean loss in EACH mode (different queries by margin non-determinism;
wc03 loses Ekman in both). 9/10 queries have a cap-set delta; the deep family sits in the intersection
(safely in) or outside (safely out) for most — the policy only bites at the truncation margin, where
it nets zero. `merged_candidate_max` binds (fused_total 171–200 > 120), so this is not a "cap didn't
bind" artifact.

(B) DOWNSTREAM utility of the differential: the mechanism WORKS where it fires — wc10 (WILDCARD) V2
admitted a Laban chunk the flatten truncated and it reached final evidence; wc05 (HYBRID) V2 admitted
Timing (v1_pos None → v2_pos 27/108) though those chunks did not reach final. But these are offset by
the wc03 Ekman loss, so no NET downstream deep-family gain.

## The evidence stack (honest)
```
LEVEL 1 MECHANISM (synthetic seam, unit)          PASS  — fusion preserves a synthetic bridge winner
LEVEL 2 LIVE EXEMPLAR (wc01/05/07 receipts)       PASS  — origin flows; ranked lanes; wc01 chain fires
LEVEL 3 CAUSAL (fixed-upstream, HYBRID+WILDCARD)   NULL  — net-neutral deep admission (1 gain/1 loss each)
LEVEL 4 END-TO-END A/B (3 repeats, WILDCARD)       V2>V1 but CONFOUNDED (upstream varies; not isolated)
LEVEL 5 SAFETY (CA5-SENTINEL-18, 18×4)             PASS  — halluc 0 / q0 1.0 / provenance 1.0 / 0 flags
LEVEL 6 PRODUCTION (fleet)                          HEALTHY — flags on, one bundle, /ready
```

## Rejected claims
- REJECTED: "V2 fusion causally improves deep-family reach." The controlled experiment is a NULL.
- REJECTED: the A/B gain as causal proof of the fusion mechanism — it is end-to-end and confounded.
- NOT claimed harm: the swaps are balanced, the wc03 Ekman drop never reached final, and the sentinel
  shows no safety regression. Net effect = neutral + safe.
- No tuning of weights / preserve_top_n / K on these 10 probes (owner rule).

## Open contract gaps
Decision for the owner: V2 is SAFE and its mechanism WORKS occasionally, but its NET causal benefit on
these probes is a NULL. Keeping a safe-but-net-neutral mechanism as the live default is the owner's
call. Current state: LEFT LIVE per prior owner instruction ("leave V2 live"); the honest null is
recorded so it is not sold as a proven improvement. REVERT is one step (3 `.env` flags → 0 + bounce) if
the owner decides an unproven-benefit mechanism should not be the default. A larger benchmark would NOT
change the causal conclusion (it is a control problem, not a sample-size problem).
