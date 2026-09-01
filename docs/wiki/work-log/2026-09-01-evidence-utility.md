---
change_id: EVIDENCE-UTILITY-V1
owner: governance
date: 2026-09-01
status: complete (flag-gated; default-on is a separate owner GO)
architecture_impact: final evidence-set composition for HYBRID/GRAPH (flagged); latent seat semantics
last_reviewed: 2026-09-01
---

# WORK LOG — EVIDENCE-UTILITY-V1 (marginal-utility evidence selection)

## Contract
Owner 2026-09-01, from an outside-model design ("codebase-blind"),
reconciled here: final evidence should maximize marginal utility —
"latent gets guaranteed access to the competition for final seats,
not guaranteed final seats"; set composition rewards requirement
coverage and breadth, penalizes saturation and redundancy. Owner
directive: "create a good diagnostic test for it being well
implemented and identify bugs and issues. and then build it."

SOLE-SCORING-AUTHORITY (production-redesign law) explicitly
addressed: the cross-encoder remains the only RELEVANCE authority.
This module never re-scores relevance and never reorders by a score
of its own — it composes the SET (bounded promotion within a
lookahead window over the existing order) and filters latent against
G3's OWN numbers. Register row records this as set composition, not
score fusion.

## Grounding discoveries (the value of reconciling before building)
- The pipeline is CUT-THEN-RERANK, not rerank-then-cut (both the
  outside design and the first reconciliation assumed the reverse):
  `_truncate_reserving_rescue` fires before G3, and G3 asserts it
  never changes membership — the cross-encoder had NO say in final-
  set membership. The module therefore intervenes twice: set
  composition at the pre-rerank cut; latent competition after G3,
  the only point where cross-lane comparable scores exist.
- The PRE-REGISTERED baseline probe (20 P6 cases) REFUTED the
  design's redundancy premise on this corpus: mean pairwise token
  J=0.072, ZERO duplicate-fact incidences — so fact/entity novelty is
  DEFERRED (the `annotations` seam stays in the signature) and no
  redundancy win is claimed. The probe CONFIRMED parent saturation:
  mean max-from-one-parent 3.6, worst 8/10.
- The worst saturation case is the DEPTH PROFILE working as designed
  (enumeration query → query_shape raises caps/neighbors → 32
  evidence items, deep same-parent coverage intended). T1 is scored
  on standard-profile cases; depth queries keep their depth.

## Changes
- `shared/polymath_shared/evidence_utility.py`: `derive_requirements`
  (conservative connective split; <2 requirements → no-op),
  `utility_cut` (seat floors for rescue+latent preserved; non-
  reserved seats filled by bounded-lookahead greedy — lexicographic
  key: covers-uncovered-requirement, parent below saturation, non-
  redundant (token J), original index; promotion bounded to the
  lookahead window so tail junk can never leapfrog), and
  `latent_competition` (post-G3: keep a latent survivor iff score ≥
  weakest non-latent − margin OR novel parent; fail-open without
  scores). Deterministic throughout; no models, no RNG.
- `hybrid.py`: plan fields (`evidence_utility_enabled=False` frozen
  default + eu_* knobs); flagged cut replacement; post-G3 latent
  competition; `evidence_utility` trace block. GRAPH inherits.
- Plumbing mirrors `latent`: `apply_utility` in retrieval_modes,
  worker setting `evidence_utility_enabled=False`, `utility` flag on
  RetrieveRequest/ChatRequest → hybrid/graph.

## Proof
- Diagnostic suite `test_evidence_utility.py` — 13 green: degeneration
  to the plain cut under no pressure; breadth vs genuine depth;
  requirement promotion within the window; relevance floor (tail junk
  never leapfrogs); redundancy veto; rescue seat floors; latent
  competition drop/keep/novel/fail-open; single-clause no-op;
  determinism; engine flag-off BYTE-IDENTICAL; engine diagnostics.
- Live A/B, 20 P6 cases, ALL pre-registered targets met:
  T1 saturation (standard-profile 17 cases): 3.00 mean/3 max →
  **2.00/2** (targets ≤2.5/≤4); T2 survival **70% (0pt delta)**,
  gain 2.7/case (≥2.5), children admitted 49 (unchanged),
  latent_dropped=0 live (nothing on this corpus deserves dropping —
  displacement is now CONDITIONAL; the drop path is unit-proven);
  T3 latency **−27 ms** (≤+10); T4 byte-identical pin.

## Rejected claims
- "Fact novelty / entity novelty now" — refuted by the baseline
  probe (zero duplicate-fact incidences); deferred behind the
  annotations seam until a corpus shows the disease.
- "Weighted utility soup (0.4/0.3/0.3)" — not shipped; lexicographic
  tiers per the design's own fallback and the determinism law.
- "Dynamic K" — not shipped; interacts with the answerability/
  abstention gates and needs its own qualification.
- "Rerank the whole pool then utility-cut" — rejected: 3-5× reranker
  load on the shared Metal GPU (contention law; death-spiral
  history).

## Open contract gaps
- Default OFF. Promotion to default-on for HYBRID/GRAPH awaits the
  owner GO (flip `evidence_utility_enabled`; the ✨-style per-request
  `utility` flag already works).
- STATE-DRIFT TEST DEBT (found while qualifying, stash-bisected to
  clean HEAD): 7 determinism tests now fail against live state
  because the tier_v3 re-ingest rewrote facts/graph/evidence rows
  under state-pinned expectations (embed_batching, fact_endpoint ×2,
  graph_lifecycle ×2, evidence_truncation, killchain). Pre-existing
  relative to this change; needs a state-refresh pass of its own.
- `latent_dropped` = 0 on this corpus; the competition's live drop
  behavior first becomes observable on a corpus with weaker latent
  nominations.
