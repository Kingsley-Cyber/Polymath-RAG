---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# DEPENDENCY MAP — unfinished work (2026-09-07)

> **Next-phase plan admitted 2026-09-07 (S0, register 11.129):**
> `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` extends the profile
> critical path with a parent-map scale and a vocabulary bridge. Slice order
> S1 ParentSkeleton → S2 map compiler → S3 packer → S4 SQL → S5 profile vNext →
> S6 one-call canary → S7 shared budget → S8 `doc_profile` refactor → S9
> `doc_parent_map` worker → S10 projection → S11 verifier → **S12 (= old U1)**
> runtime lane → S13 vocabulary bridge → S14 backfill → **S15 (= old U2)**
> QUERY_READY (owner go) → S16 ablation. `ParentSkeleton` (S1) has no blockers.
> The graph below is the chat-side/profile reliability context around that path.

## Human-readable

The document profile chain is the architecture's critical path. Its first five steps are done: the compiler produces the representation (`compiler.py` → `representations`), the worker projects it into the profile collection with `doc_id` in the payload, and the backfill populated cinema. **Step 6 (U1)** consumes exactly that payload: the lane resolves documents by `doc_id` and reads the same named vectors the gate script reads. Therefore a compiler or projection change (a new surface, a renamed vector) breaks the lane even when lane code is untouched — bump `COMPILER_VERSION` / `PROJECTION_VERSION` and re-backfill instead of editing in place. **Phase B (U2)** must wait for U1 because gating readiness on a representation that retrieval does not yet use would only make documents un-serveable; it also needs every corpus backfilled and the pacing (U5) proven at that scale.

The chat-side items form a second, loosely coupled chain: the relief after-measurement (U3) tells us whether the judge is healthy; only then does the lean prompt (U8) make sense to measure, and pure-rank composition (U7) should be measured on a candidate set that already includes the profile lane (U1), otherwise the measurement is repeated. B16 (U4) is a measurement task that U1 later supersedes for ranking.

Parallel-safe: U5 (limiter), U6 (requeue script), U11 (test hygiene) touch nothing on the critical path. Owner-gated: U2 flip, U7 rule, U9 go, U10 deletions and key rotation.

## Compact graph

```text
DONE: DP1 compiler ─▶ DP2 context ─▶ DP3 stage+pool ─▶ DP4 projection ─▶ DP5 backfill (cinema)
                                                                              │
                                        ┌─────────────────────────────────────┘
                                        ▼
U1  DOCUMENT_PROFILE retrieval lane  (no blockers)
 │        ▲
 │        └── U4 B16 titles measurement (independent; U1 later feeds the same ranking)
 ▼
U2  phase B readiness gate  ◀── needs: U1 evidence + backfill of non-cinema corpora + owner go
 ▲
 └── U5 durable shared limiter (needed before large-corpus backfills; parallel-safe otherwise)

U3  relief after-measurement (owner UI turns) ─▶ deadline 12 → 8 ─▶ U8 lean prompt
U7  pure-rank composition (owner rule) — measure AFTER U1 (candidate set changes)
U9  ladder L3 (owner go) — prefer AFTER U1
U6  requeue-below + RAPO re-profile — parallel-safe
U11 test hygiene — parallel-safe
U10 data hygiene + key rotation — owner only
```

## Coupling table

| Item | Prerequisites | Downstream | Parallel-safe with | Mutually coupled with | Blocker type |
|---|---|---|---|---|---|
| U1 lane | none (DP5 done) | U2, U7, U9, U4 re-measure | U3, U5, U6, U11 | compiler/projection versions | none |
| U2 gate | U1 evidence, corpus backfills, U5 at scale | serving semantics of every corpus | U6, U11 | census/verify | owner go |
| U3 relief measure | owner UI turns, backlog drain | U8 | everything | — | external |
| U4 B16 measure | none | U1 ranking reuse | everything | — | owner verdict |
| U5 limiter | none | U2 at scale | U1, U3, U6 | limiter.yaml rows | design call |
| U6 requeue | none | — | all | compiler unknown-tag rule | none |
| U7 pure rank | owner rule; U1 for a fair measurement | answer composition | U3 | U1 | owner |
| U8 lean prompt | U3 | — | U1 | presentation probe | owner scope |
| U9 ladder L3 | owner go; U1 preferred | compiler tokens (U8) | U5, U6 | U1 | owner |
| U10 hygiene | owner | profile quality of two docs | all | — | owner |
| U11 tests | none | CI stability | all | — | none |
