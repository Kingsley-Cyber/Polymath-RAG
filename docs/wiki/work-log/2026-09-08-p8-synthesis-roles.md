---
title: "WORK LOG — P8 synthesis evidence-role bundle (DIRECT/PRECISION/RELATIONAL/LATENT)"
change_id: SYNTHESIS-ROLES-V1
date: 2026-09-08
owner: worker (additive receipt field; no ranking/selection change)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.165
package: shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/chat_retrieval.py, tests/determinism/test_candidate_engine.py
architecture_impact: "P8 (§44–§47): every selected evidence chunk is tagged with its synthesis ROLE derived from its lane arrivals — DIRECT (a direct answer lane A/B/C), PRECISION (resolution lift, lane F only), RELATIONAL (a graph-destination child, P7), LATENT (latent rescue / dual-read, lanes D/E only). `candidate_engine.synthesis_role(arrivals)` is pure; `chat_retrieve_v2` stamps `role` on each evidence row and a `meta.evidence_roles` count bundle. Additive — no ranking or selection changes; a chunk that arrived via any direct lane is DIRECT (§47: LATENT never substitutes for DIRECT). This gives synthesis the role structure to present DIRECT answers first, PRECISION to sharpen, LATENT to extend."
---

# WORK LOG — P8 synthesis evidence-role bundle

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §44–§47: preserve four evidence roles so synthesis
answers the DIRECT obligation first, sharpens with PRECISION, connects with RELATIONAL, and
extends with LATENT — and never lets LATENT substitute for missing DIRECT evidence.

Owner: `worker`. Verifier: `test_candidate_engine.py` + `chat_regression --check` + a live
probe. Rollback: n/a — the `role` field is additive; nothing keys behavior on it.

## Changes

- **`candidate_engine.py`:** `synthesis_role(arrivals)` (pure, §46) + `SYNTHESIS_ROLES` +
  `ARRIVAL_GRAPH_DEST` (the P7 graph-destination child tag). Direct arrival wins; else
  RELATIONAL > PRECISION > LATENT.
- **`chat_retrieval.py`:** each evidence row gets `role = synthesis_role(c.arrivals)`;
  `meta.evidence_roles` = the DIRECT/PRECISION/RELATIONAL/LATENT counts.

## Proof

- **Unit:** `test_candidate_engine.py` — `synthesis_role` maps arrivals correctly (direct
  wins over lift; F→PRECISION; D/E→LATENT; GRAPH_DEST→RELATIONAL). 37/37.
- **Additive (no behavior change):** `chat_regression --check` → `131 rows, 0 failing`.
- **LIVE (cinema, intent policy on):** every evidence row carries a valid role;
  `meta.evidence_roles` present. On the mapped cohort the final selection is DIRECT-dominated
  (the additive lanes' candidates rarely win selection here) — the role structure is correct
  and diversifies as those lanes contribute winning candidates on the full corpus.

## Rejected claims

- **Not** a ranking/selection change: `role` is a derived label on the already-selected
  evidence; the judge/fusion are untouched.
- **Not** role-inflation: a chunk that answers directly is DIRECT even if it is also precise
  (§47) — PRECISION/LATENT/RELATIONAL are for chunks whose ONLY contribution is that role.

## Open contract gaps

- **Next (P8b):** have the synthesizer CONSUME the roles — present DIRECT first, label
  PRECISION terminology, add LATENT after the direct answer (§46 law), cite graph provenance
  for RELATIONAL — a synthesis-prompt/bundle change (§44). The role structure is now available.
- Role DIVERSITY (non-DIRECT roles appearing) is gated on the additive lanes contributing
  winning candidates — i.e. on parent-MAP backfill + richer atoms (marked GATED elsewhere).
