---
change_id: g42-seed-eligibility
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (measurement only; production unchanged)
---

# G4.2: deterministic graph seed eligibility qualification

## Contract

Test whether a deterministic query-to-entity seed eligibility contract
(identity vs substring coincidence) makes canonical bidirectional hop1
safe for production. Arms A (production outgoing), B (bidir +
permissive), C (bidir + exact identity), D (bidir + identity +
lexical genericity gate). Hard boundaries: no GLiNER/extraction/
compiler/canonicalization/graph-weight/cap/hop/reranker changes; no
LLM judge; no hand word lists; entity existence preserved.

## Changes

- `eval/g4_seed/manifest.json`, `qualify_g42.py` (pure deterministic
  seed policy + four arms + reranker top-10 selection + determinism
  re-checks), frozen arm artifacts, `generic_surface_audit.csv`
  (read-only canonicalization diagnostic), `REPORT.md`.

## Proof

- C (exact identity) eliminates engine→engineer and component→leaves
  substring explosions, but is IDENTICAL to B overall: q09 names its
  hub exactly, so identity gating does not reduce q09 noise.
- D (genericity gate) zeroes q09 noise but also gates legitimate
  single-word hubs (q01 the platform, q07 the database → 0/0) —
  stop condition #3 met.
- Diagnostic: three generic hubs exist in the live corpus with
  cross-document accumulation (platform 53 deg / 12 docs; system 36;
  model 36).

## Rejected claims

- No promotion; production unchanged (G3 ON, outgoing hop1, hop2
  rejected). Candidate code confined to eval/g4_seed/.

## Open contract gaps

- G4.2 FAIL — STOP. Next experiment (defined, not started):
  canonicalization-side (Layer 2) qualification for generic-hub
  identity accumulation, after which Layer 3 seed eligibility may be
  revisited.
