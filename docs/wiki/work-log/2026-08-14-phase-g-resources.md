---
change_id: phase-g-lexical-resources
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: docs/wiki/decisions/0008-evidence-pass-boundary.md
---

# Phase G: the lexical-semantic compiler becomes real + G.1 evidence-pass boundary

## Contract

Make the lexical-semantic layer real: vendor and pin VerbNet 3.3,
Unified PropBank, FrameNet 1.7, and SemLink 2.0; flatten them into
immutable, lemma-keyed runtime tables; compile the rule pack against
the REAL resource index with hard build gates; and restore the true
two-pass evidence boundary (ADR-0008). Runtime never touches the raw
resources (GATE 10).

## Changes

- `resources/manifests/*.yaml`: pinned archives with sha256
  (verbnet vn-3.3, propbank-frames main, semlink master, framenet_v17
  via NLTK).
- `scripts/fetch_resources.py` / `verify_resources.py`: download +
  hard checksum gate (any mismatch fails the build).
- `scripts/flatten_resources.py`: deterministic flattening →
  `resources/compiled/<resource_contract_id>/` with 9 tables
  (lemma→VN classes, lemma→PB rolesets, PB argument glosses, PB→VN,
  VN→FN, composed PB→FN, frame index, resource index, manifest).
  Determinism digest (`tables_sha256`) proves byte-identical rebuilds
  (GATE 1). Upstream quirks are recorded, never papered over: 2
  malformed PropBank XMLs skipped; 2047 SemLink keys whose ids do not
  align with vendored VN 3.3 recorded as unresolved coverage.
- `scripts/compile_predicate_rules.py`: the build gate — every cited
  VN class / PB roleset / FN frame must exist in the FLATTENED index;
  SemLink endpoints must exist on both sides; inverses consistent;
  core types declared; determinism tuples unique. Emits
  `compiled_lexical.json` with trigger sets EXPANDED through real
  VerbNet class membership (GATE 5).
- Compiler runtime: loads the committed compiled artifact (drift and
  digest hard-fail), compiles from compiled triggers, carries
  `resource_contract_id` + `compiled_lexical_sha256` in fact
  provenance, and exposes `lexical_lookup()` — O(1) lemma → VN/PB/FN
  + SemLink tables.
- Extract workers: candidates are enriched from the real lookup
  (roleset when exactly one, VN classes, composed FN frames,
  `semlink_resolved` honest). Missing SemLink is absence, never a
  gate (GATE 4).
- Rule pack corrected AGAINST REAL DATA: found.01/member.01/Invention/
  Change_event do not exist in the pinned resources — citations fixed
  to establish.01, Membership, Creating, Undergo_change; VerbNet ids
  corrected to v3.3 numbering (use-105.1, turn-26.6.1, correspond-36.1.1).
- ADR-0008: GLiNER pass 2 restored as the coarse evidence proposer
  (may abstain); the lexical lane is trigger localization; mode flag
  `lexical` (default) / `hybrid`. Resources constrain; the compiler
  decides.

## Proof

- All 10 gates tested: byte-identical rebuilds, corruption hard-fail,
  invented roleset/frame build-fail, SemLink-absence compiles with
  semlink_resolved=false, class-member verbs beyond manual triggers
  found, unsupported never becomes ASSOCIATED_WITH, provenance carries
  the resource contract, runtime works with resources/vendor removed.
- Live proof: `founded(Marcus, Nova Systems)` extracted with
  provenance `roleset=establish.01`, `verbnet_classes=[base-97.1]`,
  `semlink_resolved=true`, `resource_contract_id=6ac1aeed...`.
- 50 unit + 14 integration + 3 guards green.

## Rejected claims

- No runtime parsing of raw resources (GATE 10); no fuzzy cross-version
  joins for unresolved SemLink ids; no SemLink-as-required-gate.
- No ASSOCIATED_WITH automatic fallback anywhere.

## Open contract gaps

- Qualification of an evidence-capable GLiNER release to flip the
  default to `hybrid` (ADR-0008 revisit clause).
- `resource_index.yaml` remains as curated documentation; the build
  gate no longer reads it.
