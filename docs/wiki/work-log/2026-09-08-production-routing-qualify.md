---
title: "WORK LOG — production routing qualification (intent-aware stack, non-regression)"
change_id: PRODUCTION-ROUTING-QUALIFY-V1
date: 2026-09-08
owner: worker (read-only qualification)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.167
package: scripts/production_routing_qualify.py, docs/wiki/experiments/production-routing-qualify-2026-09-08.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "The 'production routing qualification' the plan names: with the intent policy ON, the whole routing stack (intent → budget → the additive lanes dual-read / profile-atom / resolution-lift + micro-latent + intent breadth + graph assist) must not regress the frozen gold. `scripts/production_routing_qualify.py` runs the exact live function (`chat_retrieve_v2`) over the frozen L (exact identifiers) + B (grounded QA) cinema fixtures, policy OFF vs ON, comparing `gold_in_union`; every lane is additive + unioned last, so gold can only stay or rise. Read-only. LIVE: L 15/15→15/15, B 13/15→13/15, 0 regressions — PASS."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P10** — this work-log is the EVIDENCE for that ledger row (the MD phase table is the control point; this does not duplicate it).

# WORK LOG — production routing qualification

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 "production routing qualification" + §53 laws: the
intent-aware stack, fully ON, must preserve exact-lookup and grounded gold (raw query +
exact terms + global raw child always survive; every added lane is additive). This is the
non-regression capstone over the frozen fixtures; corpus-scale UPLIFT is a separate,
backfill-gated measurement.

Owner: `worker`. Verifier: `scripts/production_routing_qualify.py`. Rollback: n/a (read-only).

## Changes

- **`production_routing_qualify.py`** (new): per frozen query, compute the intent
  (`classify_intent`), build the intent budget (`apply_intent_policy`), call `chat_retrieve_v2`
  policy OFF vs ON over live Qdrant, compare `gold_in_union`; exit non-zero on ANY gold lost.

## Proof

- **LIVE (cinema, L + B fixtures):**
  - **L (exact identifiers): `gold_in_union` off 15/15 → on 15/15, 0 regressions** — exact
    lookup fully preserved with the whole stack on.
  - **B (grounded QA): off 13/15 → on 13/15, 0 regressions** — grounded gold preserved (the 2
    misses are present with the policy OFF too — pre-existing union gaps, not a routing
    regression).
  - **PASS.** Evidence: `production-routing-qualify-2026-09-07.json` [2026-09-08].

## Rejected claims

- **Not** an uplift claim: this proves NON-REGRESSION (safety), not that the additive lanes
  improve recall — that is gated on parent-MAP backfill + richer atom generation and measured
  separately (P10–P13). On the tiny mapped cohort the ON union equals or slightly exceeds OFF.
- **Not** a rank/answer change: `gold_in_union` is a union-level (pre-judge) measurement; the
  cross-encoder still judges.

## Open contract gaps

- **P10–P13 uplift measurement** (does the intent-aware stack IMPROVE recall/precision) is
  GATED on the parent-MAP backfill reaching corpus coverage + vNext atom regeneration — the
  additive lanes only add unique winning candidates once the substrate is filled. Re-run this
  qualifier (and a recall-delta variant) as the backfill completes.
