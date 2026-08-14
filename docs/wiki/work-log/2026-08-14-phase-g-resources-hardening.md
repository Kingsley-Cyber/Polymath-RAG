---
change_id: phase-g-resources-hardening
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none
---

# Phase G hardening: immutable revision pinning, coverage report, spec closure

## Contract

Close the remaining lexical-layer spec deltas after the initial Phase G
commit: immutable commit-SHA pinning (no branch refs at build time),
inline fetch verification, trigger provenance, build statistics,
per-rule coverage status, polysemy/modality tests, and the documented
upgrade procedure.

## Changes

- Manifests now resolve exact commit SHAs (codeload/<sha>):
  verbnet `9c6f7b949560189d5c72b863ee3cb47da4409a41` (tag vn-3.3),
  propbank-frames `c66e0ccf28b53f00051b187db83e937b5bee2e32` (main @
  pin), semlink `2636bf5a4ae9c93b669a1184a8aaae9ca21552d3` (master @
  pin). Archive hashes re-pinned to the commit-resolved zips; contract
  id re-derived (03a513ec…).
- `fetch_resources.py` verifies sha256 inline before install — a wrong
  byte can never land (spec §7).
- SemLink derivation explicit: `semlink_derivation.json` distinguishes
  attested (direct=0 in this release) from composed pb→fn (2,959).
- Fact provenance now records `trigger_lemma` + `trigger_surface`.
- `build_statistics.json` (spec §24) + per-rule `rule_coverage` in the
  compiled artifact (spec §25): 10 COMPLETE, 12 PARTIAL, 6 MANUAL_ONLY,
  0 CONFLICT across the 28 predicates.
- `resources/README.md`: pinned sources, licenses, build pipeline, the
  contract identity, and the 9-step upgrade procedure (never in-place
  mutation; old contracts reconstructable).
- New tests: polysemy (develop/run/support/hold/form expose candidate
  senses; tables never contain graph predicates), modality
  (hypothetical→QUALIFY, conditional→REJECT, negated→REJECT), contract
  bump isolation (policy assertions).

## Proof

- 61 unit + 14 integration + 3 guards green.
- Two clean rebuilds → identical contract id (03a513ec…) and identical
  tables_sha256 (GATE 1 test re-verified in-suite).
- verify_resources hard-fails on corruption (GATE 2).

## Rejected claims

- No silent upgrade to VerbNet 3.4 or current PropBank `main` — the
  compatibility family is SemLink 2's: VN 3.3 + Unified PropBank +
  FN 1.7, pinned at immutable revisions.
- No in-place mutation of compiled tables; no parallel source of truth.

## Open contract gaps

- Phase H: the empirical waterfall (lexical vs hybrid evidence modes,
  cohort breakdown by SemLink/PB/VN/FN coverage) — the extraction layer
  is frozen; changes must now be justified by measured deltas.
