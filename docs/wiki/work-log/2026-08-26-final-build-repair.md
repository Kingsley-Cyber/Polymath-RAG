---
change_id: FINAL-BUILD-P0-REPAIRS
owner: governance
date: 2026-08-26
status: implemented
architecture_impact: none (repair/measurement log)
last_reviewed: 2026-08-29
---

# 2026-08-26 — Final build: P0 repairs + transcript qualification

Mission POLYMATH_FINAL_BUILD_REPAIR_AND_QUALIFICATION, from the SMART
verification baseline at f33a0ff. Full evidence:
`eval/v5/FINAL-PRODUCTION-READINESS-REVIEW.md`.

## Shipped (each with regressions)

1. **Query plane restored** — ask_router import; app import/route
   registration test class added (938b852).
2. **Scope fail-closed everywhere** — one resolver on all four routes;
   implicit-all branches deleted; adversarial two-corpus proof
   (44e4c6e).
3. **Router = priority, never authorization** — local trigger evidence
   reaches the compiler under any document classification; compilers
   self-gate; A–F matrix (706baaa).
4. **Answer admission** — query-relevance gate + full-coverage verdict;
   nonce/neighbor abstain live (7ad9418).
5. **Failure transparency** — typed graph 502; SEMANTIC_COMPLETE/
   INCOMPLETE/FAILED view + /semantic_readiness; cross-corpus content
   collision typed refusal; artifact-lane verify coverage; receipt-gap
   ticket reopen (456a52c, dd6427c, 957c1e4, f283ecb).
6. **Corpus map active** — scoped planner + vocabulary alias bridge in
   /ask with traced neighborhoods; procedures feed the builder
   (4b8027e).
7. **Transcript register** — conversational-lead imperative stripping;
   guarded copula-definition patterns; latent IndexError fixed
   (8f55055, 6e9976b).
8. **Rerank robustness** — 16-pair batching + 4,000-char scoring
   surface bound after a measured MPS OOM on release-books
   (df30415, dcdce71).
9. **Gates** — verify_product_readiness.py (10/10 live) +
   final_product_panel.py (13/13 live, latencies recorded).

## Measured qualification

- Fresh real transcript corpus `transcript-qual-v1`: PROCEDURE 1,
  CONCEPT 2, summaries + corpus map + neural + graph substrate +
  query_ready + SEMANTIC_COMPLETE; VECTOR/HYBRID/GRAPH + /ask + /chat
  + abstention all live-verified.
- FACT lane: 34 candidates discovered under a deprioritizing router;
  0 admitted — every rejection typed (F3 endpoint durability; type
  signatures). Outcome D, boundary traced; precision gates upheld.
- Transcript FACT → public GRAPH → exact evidence span proven on
  core-3-v1 through HTTP.
- Isolated acceptance: 240 tests × 2 identical green runs on fresh
  schema-clone databases.

## Verdict

NO-GO on exactly one owner-gated item (spoken-register relations vs
frozen predicate signatures — see review §21); all other final gates
GO.

## Closeout — spoken-relation adapter (owner Option A)

Four historically-incomplete adaptation seams closed (binding,
created signature, F7 orientation vocabulary, F8 object-side relcl
mirror), each measured live, each shadow-qualified with zero
false accepts on 13 hard negatives. Result, fully live on the
unaltered transcript: created(facebook, andromeda) — F1–F8 PASS
(policy v1.1) → Neo4j → public GRAPH → exact span
chunk_161c2c49…@2402:3508 → grounded cited answer. Acceptance
252×2; panel 13/13; product gate 10/10; extraction 16.7→14.3 s.
Verdict revised: PRODUCTION GO.

## Contract

(Historical entry — the contract it worked under is stated in the entry body above.)

## Changes

(Historical entry — the changes are recorded in the entry body above.)

## Proof

(Historical entry — the proof and measured evidence are in the entry body above.)

## Rejected claims

(Historical entry — none recorded beyond the entry body above.)

## Open contract gaps

(Historical entry — see the entry body and the CURRENT_STATE chain above.)
