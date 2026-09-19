---
change_id: WLK2C-C1-BRIDGE-ADMISSIBILITY
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C1 (shared, UNIT_PROVEN, worktree `wlk2c/retrieval-lineage` UNMERGED). NEW pure `shared/polymath_shared/bridge_admission.py`: STRUCTURAL bridge admissibility — can a DiscoveryPath legitimately be a bridge CANDIDATE? Deterministic, no model, and crucially NO relevance judgment (that is the C4 semantic gate). A path is a structural bridge candidate iff: non-primary (the q0 path is DIRECT, never a bridge); non-empty origin_query; grounded derivation (recognized origin + a real bridge id); materially distinct from q0 (introduces content beyond q0); not a q0 duplicate/paraphrase (token-Jaccard < 0.8 ceiling); not boilerplate (≥2 distinct content tokens). Consequence (intended, per owner): a grounded-but-misdirected bridge PASSES this gate and is rejected only at C4 (bridge↔q0 semantics). Lineage existence ≠ bridge validity: a failing path keeps provenance but can never earn COMPLEMENTARY/DIVERGENT admission. No caller yet (C3–C6 wiring, live at C7)."
last_reviewed: 2026-09-18
---

## Contract
WLK2C C1 (plan-of-record `docs/wiki/plans/WLK2C-RETRIEVAL-LINEAGE-V1.md`, tiers 1–2 gate). The owner
scoped C1 to STRUCTURAL admissibility only — "can this path legitimately be considered a bridge
candidate?" — with NO relevance judgment ("is this actually relevant enough to q0?" is deferred to C4).
Checks: provenance exists; origin_query non-empty; differs materially from q0; grounded derivation
(existing subquery / profile-concept / graph / wildcard); not merely duplicated q0; not malformed /
generic boilerplate.

## Changes
- NEW `shared/polymath_shared/bridge_admission.py` (pure): `AdmissionVerdict{admissible, reasons}` (a
  structural verdict, NOT a relevance/validity claim); `structural_bridge_admissibility(path, root_query)`
  → the six structural checks, reasons ∈ {not_a_bridge_path, empty_origin_query, ungrounded_origin,
  boilerplate_or_too_short, duplicate_of_q0, no_distinct_content}; `admissible_bridge_paths(lineage)` →
  the lineage's structurally-admissible bridge paths (order preserved); `annotate_admissibility(lineage)`
  → a receipt-friendly per-candidate structural view. Constants `DUPLICATE_Q0_CEILING=0.8`,
  `MIN_CONTENT_TOKENS=2`; local stopword content-tokenizer (no coupling to a private symbol). Imports
  only `retrieval_lineage` (C0).
- NEW `tests/determinism/test_bridge_admission.py` (11 tests).
- Register row 11.317; this work-log; scaffold TREE declarations (module + test).

## Proof
`UNIT_PROVEN` — executed path verified = the worktree copy (`import polymath_shared.bridge_admission` →
`/…/pmv4-wlk2c/shared/…/bridge_admission.py`). 11/11 green: q0/primary path → not_a_bridge_path;
a distinct grounded subquery → admissible; a q0 paraphrase (≥0.8 overlap) → duplicate_of_q0; a strict
q0 subset → no_distinct_content; empty → empty_origin_query; <2 content tokens → boilerplate; a
non-primary path with no query id → ungrounded_origin; **a grounded-but-misdirected bridge → admissible
(the no-relevance-judgment contract)**; admissibility keys on STRUCTURE not relevance (off-topic-distinct
admissible, on-topic-paraphrase rejected); `admissible_bridge_paths` filters a mixed lineage; receipt
shape; deterministic.

## Rejected claims
- REJECTED an earlier C1 draft that required "relates-to-q0 by shared content" — that leaked a RELEVANCE
  judgment into C1. Corrected per owner: C1 is structural-only; the misdirected-bridge rejection is C4.
- No behavior change claimed (no caller yet). A misdirected bridge passing C1 is INTENDED, not a defect.

## Open contract gaps
`contract_impact` = no impacted production contract (new isolated `shared/` module; only imports C0).
Deferred: tier-2 GRAPH-path bridge CONSTRUCTION (deriving a bridge string from a graph relation — needs
the relation text exposed on the candidate); C2 bounded compiler (runs only when no admissible existing
bridge + task permits latent expansion); C4 SEMANTIC gate (bridge↔q0 + chunk↔origin_query via the
cross-encoder) — the relevance judgment C1 defers. Live wiring + proof at C7 (merge + bounce + qual).
