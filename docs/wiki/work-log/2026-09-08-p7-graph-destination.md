---
title: "WORK LOG — P7 graph destination as JUDGED evidence (lane H)"
change_id: GRAPH-DEST-V1
date: 2026-09-08
owner: worker (additive judged graph lane, default-off)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.173
package: shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/query_intent.py, tests/determinism/test_candidate_engine.py, scripts/scaffold_polymath_v4.py
architecture_impact: "FINAL-PLAN P7 (§39) / DEFERRED D-7. The graph now supplies JUDGED RELATIONAL evidence, not just a post-answer fact side-channel. New additive engine lane H (`graph_dest`): query entity-card seeds → Neo4j hop-1 (the SAME `graph_expand` P6 uses) → destination entities → their DOCUMENTS (`mentions`) → ORIGINAL children, unioned BEFORE the cross-encoder and tagged `ARRIVAL_GRAPH_DEST` ⇒ RELATIONAL role (§46). This clears D-7's 'graph-before-judge' requirement WITHOUT the risky pipeline reorder: `_attach_graph` (P6, post-judge fact display) is untouched; the lane is the pre-judge judged path. Neo4j supplies the source-attested relationship ROUTE; source children PROVE; the cross-encoder judges; the graph route is never evidence itself. Default-off, unioned last, flag-off byte-identical; enabled per-intent where the intent's graph budget is auto/strong (RELATIONSHIP)."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P7** + DEFERRED **D-7** (BLOCKED-arch → cleared via the additive judged lane). The MD phase table is the control point; this work-log is the evidence.

# WORK LOG — P7 graph destination (lane H)

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §39 + D-7: graph destinations must become JUDGED source
children (RELATIONAL evidence), not the post-answer fact side-channel. D-7 named this "BLOCKED —
needs the graph-before-judge flow reorder." This slice reaches the same end additively: a new lane
runs the graph hop BEFORE the cross-encoder and contributes its destination children to the union,
so they are judged like any other candidate — no reorder of the existing post-judge `_attach_graph`.
Invariants: Neo4j supplies the source-attested route; children prove; the cross-encoder is the sole
judge; the graph route (entities/facts) is routing-inferred and never evidence (§63/§64); raw query
+ exact terms + global child recall untouched (additive, unioned last).

Owner: `worker`. Verifier: `test_candidate_engine.py` (lane-H + off-by-default) + `chat_regression
--check` + a live graph-dest probe. Rollback: `graph_dest_enabled=False` (default) ⇒ lane H empty ⇒
union byte-identical.

## Changes

- **`candidate_engine.py`:** lane H (tag `ARRIVAL_GRAPH_DEST` ⇒ `synthesis_role` = RELATIONAL, the
  role that was always empty); budget knobs `graph_dest_enabled` (False) / `graph_dest_children` (8);
  `graph_dest_search` callback threaded through the engine; the lane-H block (fail-open, mirrors lane
  G) unioned last; `graph_dest` receipt in `trace` + `lane_sizes` + `funnel_lanes`.
- **`chat_retrieval.py`:** `graph_dest_search(qv)` — `entity_card_probe` (seeds on the primary
  vector) → `graph_expand_or_502` (Neo4j hop-1, reused from P6) → destination entity ids (fact
  subject/object minus the seeds) → `SELECT DISTINCT doc_id FROM mentions WHERE entity_id = ANY(…)
  AND corpus_id=…` → per destination doc, a `routing_child` dense search on the primary vector.
  Fail-open at every store boundary. Wired into `retrieve_candidates`; knobs added to `_INT_KNOBS`.
- **`query_intent.py`:** `apply_intent_policy` sets `graph_dest_enabled` when the intent's `graph`
  budget is auto/strong (RELATIONSHIP) — reuses the existing §37/§38 graph field.

## Proof

- **Unit/regression:** `test_candidate_engine.py` (`test_graph_dest_lane_h_adds_relational_children_
  and_is_off_by_default` — destination children enter the union as RELATIONAL; off ⇒ the probe is
  never invoked, byte-identical) + the lane-set pin updated to 8 lanes. **Flag-off byte-identical:**
  `chat_regression --check` = **131 rows, 0 failing**.
- **Live functional qualification** (`POLYMATH_CHAT_INTENT_POLICY=1`, RELATIONSHIP query, cinema):
  entity seeds → Neo4j hop → **8 destination documents** → children, judged; **evidence_roles now
  `DIRECT 12 · PRECISION 0 · RELATIONAL 1 · LATENT 2`** — the RELATIONAL bucket, always 0 before P7,
  carries a source-attested graph-destination child in the final evidence. `degraded=None` (Neo4j
  reached), lane 2.4 s.

## Rejected claims

- **Not a reorder of `_attach_graph`.** P6's post-judge fact side-channel is untouched; P7 is a
  separate PRE-judge lane, so both coexist (facts for display, judged children for evidence).
- **Not the §39 parent-MAP localization refinement.** This lane localizes to the destination
  DOCUMENT (global child search filtered by doc), not yet to the destination PARENT via the
  parent-MAP — that refinement is parent-MAP-coverage-gated (a follow-up).
- **Not a corpus-scale GRAPH uplift claim.** Whether graph-destination children IMPROVE answers is
  P11 (GRAPH measurement), gated on Neo4j graph density + the parent-MAP coverage; here 1/15 final
  slots came from the lane on the current graph (functional, not yet an uplift number).
- **The graph route is never evidence.** Only the source children it localizes to are; the entities
  and facts route only (§64).

## Open contract gaps

- **Latency:** the lane is 2.4 s (entity probe + Neo4j hop + 8 per-doc child searches); it runs under
  `lane_deadline_s` (dropped + receipted past it). Parallelizing the per-doc searches and/or a tighter
  `graph_dest_children` is a tuning follow-up.
- **§39 parent-MAP localization** (destination doc → parent-MAP → parent → child) unblocks with
  parent-MAP coverage — it will sharpen the destination children from doc-level to parent-level.
- **P11 GRAPH measurement** (does the lane add winning RELATIONAL candidates corpus-wide) = re-run the
  routing qualifier with a GRAPH arm once graph density + coverage support it (D-11).
