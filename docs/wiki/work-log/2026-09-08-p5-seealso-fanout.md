---
title: "WORK LOG — P5 SEEALSO/BRIDGE/ANCHOR fan-out (lane G, TERM branch)"
change_id: SEEALSO-FANOUT-V1
date: 2026-09-08
owner: worker (additive retrieval lane, default-off)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.172
package: shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/query_intent.py, tests/determinism/test_candidate_engine.py, scripts/scaffold_polymath_v4.py
architecture_impact: "FINAL-PLAN P5 (§20–§23). The relational Profile Atoms regenerated in 11.169 are now USED beyond doc-nomination: a new additive engine lane (G, SEEALSO_FANOUT) takes the intent's RELATIONAL atom texts (SEEALSO/BRIDGE/ANCHOR/TENSION/INVERSION — routing-inferred 'look over here' pointers) and probes ORIGINAL children via GLOBAL dense child search (the §21 TERM/vocab-probe branch). The atom only ROUTES (never evidence, §63/§64); the source children PROVE; the cross-encoder still judges. Role = LATENT (§46/§47 — it EXTENDS via adjacency; RELATIONAL stays reserved for Neo4j source-attested relationships). Additive, unioned LAST, default-off (flag-off byte-identical), enabled per-intent for RELATIONSHIP + EXPLORATORY. Coverage-INDEPENDENT (global child search, not parent-MAP)."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P5** (SEEALSO/BRIDGE fan-out — the §21 TERM branch is now built; ENTITY branch → P7, DOC/parent-MAP branch → coverage). The MD phase table is the control point; this work-log is the evidence.

# WORK LOG — P5 SEEALSO/BRIDGE fan-out (lane G)

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §20–§23: a relational atom is a routing pointer; resolve its
target and fan out to adjacent knowledge the user did not know to ask for (§0 goal 3). The §21
resolver has three branches — ENTITY (canonical graph seed), DOCUMENT (profile → parent-MAP →
children), TERM (vocab probe → children). This slice builds the **TERM branch**: it is graph-free
and parent-MAP-coverage-free, so it is implementable + qualifiable now. Invariants held: atoms
never become evidence (§63/§64); children prove; the cross-encoder is the sole judge; raw query +
exact terms + global child recall are untouched (additive, unioned last).

Owner: `worker`. Verifier: `test_candidate_engine.py` (lane-G + off-by-default) + `chat_regression
--check` + a live fan-out probe. Rollback: `seealso_fanout_enabled=False` (default) ⇒ lane G empty
⇒ union byte-identical.

## Changes

- **`candidate_engine.py`:** lane `LANE_G = "SEEALSO_FANOUT"` (in `_LATENT_LANES` ⇒ `synthesis_role`
  = LATENT); budget knobs `seealso_fanout_enabled` (False) / `seealso_fanout_atoms` (6) /
  `seealso_fanout_children` (4); `fanout_search` callback threaded through `retrieve_candidates` →
  `_retrieve_on`; the lane-G block (mirrors lane F) unioned last; `seealso_fanout` receipt in
  `trace` + `lane_sizes` + `funnel_lanes`.
- **`chat_retrieval.py`:** `fanout_search(qv)` — filter `budget.atom_kinds` to `RELATIONAL_KINDS`,
  `search_atoms` → top atoms → embed their texts → GLOBAL `routing_child` dense search → rows
  tagged `fanout_atom`. Wired into `retrieve_candidates`; knobs added to `_INT_KNOBS`.
- **`query_intent.py`:** `IntentPolicy.seealso_fanout`; enabled for **RELATIONSHIP + EXPLORATORY**
  (the connect/explore intents); `apply_intent_policy` sets `seealso_fanout_enabled`.

## Proof

- **Unit/regression:** `test_candidate_engine.py` (39, incl. `test_seealso_fanout_lane_g_adds_…`
  — lane-G children enter the union as LATENT and a fused DIRECT winner is NOT demoted, §47 — and
  `test_seealso_fanout_is_off_by_default_…` — the probe is never invoked when off); `test_query_intent`
  13/13; retrieval determinism subset 220 pass. **Flag-off byte-identical:** `chat_regression --check`
  = **131 rows, 0 failing**.
- **Live functional qualification** (`POLYMATH_CHAT_INTENT_POLICY=1`, RELATIONSHIP query, cinema):
  lane G produced **24 fan-out children from 6 real relational atoms** — "Connecting theater acting
  pedagogy to computer animation education", "applying animation timing concepts to video game
  character movement", "balancing realistic timing with stylized visual effects", "timing importance
  in animation", … — judged by the cross-encoder; **2 survived into the final evidence as LATENT**
  (lane 398 ms). The relational atoms route to adjacent source children end-to-end.

## Rejected claims

- **Not the ENTITY branch** (SEEALSO/BRIDGE target → canonical graph seed → traversal) — that needs
  the graph-destination machinery = **P7**. **Not the DOCUMENT/parent-MAP branch** (target → profile
  → MAP → children) — that is parent-MAP-coverage-gated.
- **Not a corpus-scale uplift claim.** Whether fan-out children IMPROVE answers is the D-10 uplift
  measurement, GATED on parent-MAP coverage; here 2/15 final slots came from the lane on the current
  substrate (functional, not yet an uplift number).
- **Atoms are never evidence** and the role is **LATENT, not RELATIONAL** (RELATIONAL is reserved for
  Neo4j source-attested relationships, §64).

## Open contract gaps

- **P5 ENTITY branch** (graph seed) folds into **P7** (graph destination → parent-MAP → child).
- **P5 DOCUMENT branch** (target → profile → parent-MAP → children) unblocks with parent-MAP coverage.
- **TENSION paired-probe fan-out (§24)** and **BRIDGE endpoint fan-out (§22)** beyond the generic TERM
  probe are follow-ups (the generic lane already probes TENSION/BRIDGE atom texts).
- **Corpus-scale uplift** (does the lane add winning candidates) = re-run `production_routing_qualify`
  + a recall-delta variant once the parent-MAP backfill fills the corpus (D-10).
