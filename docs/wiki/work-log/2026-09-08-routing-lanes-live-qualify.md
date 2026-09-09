---
title: "WORK LOG — Routing lanes qualified LIVE on cinema (P5/P7/F/E fire + contribute)"
change_id: ROUTING-LANES-LIVE-QUALIFY-V1
date: 2026-09-08
owner: governance (routing qualification; read-only)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.179
package: docs/wiki/experiments/routing-lanes-qualify-cinema-2026-09-08.json, scripts/scaffold_polymath_v4.py, docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md
architecture_impact: "FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 P10 (Measure HYBRID) + P5/P7. The additive routing lanes — previously landed default-off and only single-query-smoke-tested — are now SYSTEMATICALLY QUALIFIED LIVE on the cinema corpus through the real `chat_retrieve_v2`: with the intent policy ON, every RELATIONSHIP query fires all four additive lanes and each contributes SOURCE-CHILD candidates (P5 seealso_fanout 24, P7 graph_dest 8, F resolution_lift 6, E dual-read 22-24), expanding the candidate union +60-75% while preserving the frozen gold (0 regressions). This moves P5/P7/F/E past 'default-off wiring' to 'live-contributing on a real corpus, invariant-preserved'. KEY correction: P5 fan-out / P7 graph-dest / F lift are parent-MAP-coverage-INDEPENDENT (atom/graph → GLOBAL child search), so they qualify on cinema NOW regardless of the parent-MAP backfill wall — only the E dual-read reach scales with coverage. Read-only qualification; no code or contract changed."
---

> **Ledger rows:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` **P10** (+ **P5 / P7** systematic-qualification pointers). The MD ledger's status table is the control point; this work-log + the experiment JSON are the evidence.

# WORK LOG — routing lanes qualified live on cinema

## Contract

The plan direction "rerun P10 for measurable uplift → unlock P5 fan-out → qualify Wildcard …". Do NOT
stop at default-off wiring — require live value qualification. Preserve the invariant chain (atoms
expand, Parent MAP localizes, Graph supplies attested relationships, children PROVE, cross-encoder
judges; routing-inferred artifacts NEVER become factual evidence, §63/§64).

## Changes (steps — exact commands + evidence)

- **P10 rerun (read-only):** `production_routing_qualify.py --corpus cinema` (L + B fixtures) — the exact
  live `chat_retrieve_v2`, intent policy OFF vs ON. Result below.
- **Per-lane attribution (read-only):** three cinema RELATIONSHIP queries through `chat_retrieve_v2` with
  `apply_intent_policy(intent, default_budget())`, capturing the `trace` per-lane fields →
  `docs/wiki/experiments/routing-lanes-qualify-cinema-2026-09-08.json` (declared in scaffold).

## Proof

- **Non-regression (P10):** L exact 15/15 → 15/15; B grounded 13/15 → 13/15; **0 regressions** (§53).
- **Union expansion (breadth the lanes add):** L avg 69.5 → 109.5 (+58 %), B 90.9 → 147.8 (+63 %) —
  EVERY query's `union_on > union_off`.
- **Per-lane, cinema RELATIONSHIP queries (consistent across 3):** `seealso_fanout` **24** candidates
  (6 relational atom routers), `graph_dest` **8** Neo4j-attested destination docs (2.4 s), `resolution_lift`
  **6** (lifted terms B1/C3/C500), `dualread` **22-24** (cinema's 838 parent-maps). Union +60-75 %.
- **Invariant held:** all contributed candidates are `routing_child` (source children). The atoms and
  graph entities only ROUTE; the cross-encoder still judges. No routing artifact entered as evidence.
- **Coverage independence (correction):** P5/P7/F use atom/graph → GLOBAL child search, so they fired
  fully on cinema despite parent-MAP coverage being partial (838/11,993). Only E dual-read's reach
  scales with coverage.
- **All three compositions qualified live** (`chat_retrieve_mode`, cinema): **HYBRID** (the four lanes
  above); **WILDCARD** (P13) — divergent sweep 45/42 latent_candidates → obvious-excluded → two-hop
  validated → **3 bridges** on the separate `wildcard` lane (never evidence, §3.19); **GRAPH** (P11) —
  **15–20 source-attested Neo4j facts** (predicates PRODUCES/REQUIRES) via 8 entity-card seeds
  (card_probe ok), bounded hop-1, `graph_degraded` null, on the `graph_relationships` side channel
  (relationships route, children prove). Recorded in the evidence JSON's `wildcard`/`graph` sections.
- **P8b synthesis presentation operationalized on REAL evidence** (`_grounded_messages`): the bridge
  query's 10 DIRECT + 5 LATENT rows, roles ON → regrouped DIRECT-first (measured **0 DIRECT-after-LATENT**),
  every [S#] role-labelled, §47 guidance prepended ("never let LATENT/RELATIONAL substitute for a DIRECT
  answer"); roles OFF byte-identical; the [S#]→locator mapping is unchanged so citations are stable.
  This presents grounded evidence by role on live multi-role retrieval (not just the synthetic unit test).

## Rejected claims

- **Not a gold-recall uplift.** `gold_in_union` did NOT rise (L at ceiling 15/15; B's 2 misses are
  unrecovered by any lane — likely parent-MAP-localization-gated). The lanes' value here is RELATIONAL
  BREADTH (see-also / graph / lift discovery), which `gold_in_union` does not measure.
- **Not an answer-quality number.** This qualifies that the lanes fire + contribute invariant-preserving
  breadth; whether the +60-75 % breadth improves FINAL answers needs a downstream answer-quality eval.

## Judge-survival finding (the honest value limit)

On the exact/QA L/B fixtures the relational candidates expand the UNION (+60-75 %) but do NOT survive
the cross-encoder into final evidence — the final top-15 is **all `DIRECT`** (`meta.evidence_roles`
{DIRECT:15, RELATIONAL:0}), even on RELATIONSHIP-classified queries: the judge correctly prefers direct
dense hits when cinema HAS them.

**VALUE DEMONSTRATED (the other half):** on cross-document / exploratory queries where direct hits are
SPARSE, the relational/latent candidates DO survive into final evidence — measured live:
editing↔fermentation **5 LATENT**, hydrology↔composition **3 LATENT**, maintenance↔cinematography
**2 RELATIONAL (graph_dest)** survivors per query. So the lanes provide real evidence exactly where
direct is insufficient AND yield to direct otherwise — the designed behaviour, invariant-preserved
(children prove, cross-encoder judges). The retrieval-side value is shown; a FORMAL answer-quality
number still needs a chat model + rubric.

## Open contract gaps

- **D-10 downstream uplift (NARROWED):** union-recall + cross-encoder SURVIVAL are now shown live
  (2-5 non-DIRECT survivors on cross-doc/exploratory queries). What remains is a FORMAL ANSWER-QUALITY
  number — an LLM-judge or human rubric comparing final answers with the lanes on vs off on a
  relational-query fixture. Needs a chat model (Groq capacity) + a rubric; `gold_in_union` on exact/QA
  L/B is the wrong instrument (base ceilings it AND direct out-competes relational candidates there).
- **E dual-read reach** scales with parent-MAP coverage (cinema 838/11,993) — capacity-gated
  multi-session (batch-size unblocked in 11.178).
- **Wildcard (P12)** still unimplemented (divergent atom frontier); lowest-value slice.
