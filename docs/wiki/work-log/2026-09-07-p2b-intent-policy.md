---
title: "WORK LOG — P2b intent→budget policy (activates the additive depth lanes per intent)"
change_id: INTENT-POLICY-V1
date: 2026-09-07
owner: worker (live-reader budget change, reversible + default-off)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.158
package: shared/polymath_shared/query_intent.py, orchestrator/orchestrator/api/chat_retrieval.py, orchestrator/orchestrator/api/ui.py, tests/determinism/test_query_intent.py
architecture_impact: "P2b of FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1: the intent→budget policy (§33 matrix). `query_intent.INTENT_POLICY` is one `IntentPolicy` row per intent (dualread, micro_latent, breadth, resolution_lift, graph); `apply_intent_policy(intent, budget)` applies the ACTIVE, already-built knobs — the profile→map spine (`dualread_enabled`) + the latent micro-search (`latent_enabled`, §13 default) — per intent, leaving resolution_lift/graph/breadth forward-declared for P3/P6/P9. Wired at the ui.py budget seam behind `POLYMATH_CHAT_INTENT_POLICY` (default OFF ⇒ byte-identical); the explicit ✨ (req.latent) always wins the latent toggle. Duck-typed via dataclasses.replace so query_intent stays decoupled from CandidateBudget."
---

# WORK LOG — P2b intent→budget policy

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §4/§14/§33/§64: modes set the budget; the intent
selects which fields/techniques run within it. P2b maps the P2a intent to the budget knobs
that EXIST today (the two additive depth lanes), behind a reversible flag, and forward-
declares the rest of the §33 row for later phases.

Owner: `worker`. Verifier: `test_query_intent.py` (policy unit tests) +
`scripts/chat_regression.py --check` (flag-off byte-identical) + a live flag-on smoke.
Rollback: unset `POLYMATH_CHAT_INTENT_POLICY` (default off).

## Changes

- **`query_intent.py`:** `IntentPolicy` dataclass + `INTENT_POLICY` (one row per intent,
  the §33 matrix) + `policy_for()` + `apply_intent_policy(intent, budget)`. Applies
  `dualread_enabled` (profile→map spine, register 11.156) + `latent_enabled` (lane D
  micro-search) per intent; `breadth`/`resolution_lift`/`graph` are recorded for P9/P3/P6 to
  read but NOT applied here. Decoupled from `CandidateBudget` (uses `dataclasses.replace`).
- **`chat_retrieval.py`:** `intent_policy_enabled()` — reads `POLYMATH_CHAT_INTENT_POLICY`.
- **`ui.py`:** at the v2 budget seam, when the flag is on and the plan has an intent, build
  the budget via `apply_intent_policy(plan.intent, default_budget())`; the explicit ✨
  (`req.latent`) still forces latent on. Flag off ⇒ the pre-existing `_latent_kw` path is
  unchanged.

## Proof

- **Unit:** `test_query_intent.py` → `11/11` — policy covers every intent; MECHANISM → both
  lanes on, EXACT → spine on + latent OFF, DEFINITION → latent OFF; unknown intent is
  identity; `policy_for` case-insensitive.
- **Flag OFF byte-identical:** `scripts/chat_regression.py --check` → `131 rows, 0 failing`.
- **Flag ON live smoke (in-process over Qdrant, 10 cinema L+B queries):** apply the intent
  budget vs default, compare `gold_in_union`. **0 regressions** (gold never dropped); the
  additive lanes activate per intent (EXPLORATORY/COMPARISON → dualread 19–24 + latent 13–18
  children; EXACT → neither active-contributes, exact-lookup unchanged). Exact-lookup control
  preserved by construction (both lanes are additive, unioned last).

## Rejected claims

- **Not** a behavior change by default (flag off ⇒ byte-identical, proven).
- **Not** a hard gate: the intent policy only turns ON additive lanes; raw/exact/global-child
  survive (§53); `gold_in_union` cannot drop.

## Open contract gaps

- **P3 — Resolution Lift (next):** the `resolution_lift` policy field is declared but unused;
  P3 builds the source-derived vocabulary lift (TERM/exact IDs/entities/MAP hooks → bounded
  precision probes, §10–§12) and reads `policy_for(intent).resolution_lift`. Then P4 micro-
  latent tuning, P5 SEEALSO/BRIDGE, P6 graph auto-route (`policy_for(intent).graph`), P9
  breadth (`policy_for(intent).breadth`) — each consuming its forward-declared policy field.
