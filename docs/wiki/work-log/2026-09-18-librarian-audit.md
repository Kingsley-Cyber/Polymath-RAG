---
title: "WORK LOG — Librarian rescan + bug pass (with the new impact tooling)"
change_id: LIBRARIAN-AUDIT-2026-09-18
date: 2026-09-18
owner: governance
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Rescan of the completed Librarian work (P4/P4a/P1-P2/ELITE/P5a) with the new contract-impact tooling + graft + ruff. No production code rewritten — no real regression found. One actionable safety guard added (surface-taxonomy drift). Two low-severity debt items recorded, not fixed."
---

## Contract
Use the new tooling immediately against the completed Librarian work; do not assume slices are
correct because their focused tests passed. Validate every finding; repair actual issues; classify
the rest (REAL BUG / FALSE POSITIVE / DEBT). Acceptance: the impacted-test set is green, findings
are classified, and no working code is rewritten on a tool report alone.

## Changes
- New `tests/determinism/test_surface_taxonomy_drift.py` (3 tests) — asserts every surface-name
  literal curated outside SurfaceRegistry (projection.py ANSWER/EXPLORATION, selection.py
  DIRECT/DISCOVERY/PRESENCE) stays a valid registry surface, and the nomination sets stay within
  projected surfaces. Converts the audit's drift finding into a guarded invariant.
- No production code changed (no real bug found).

## Proof
Blast radius (scripts/contract_impact.py --range cf1ee4f..1b21038): 10 changed contracts +
correct downstream closure. Impacted determinism suite (15 files across the full blast radius):
**140 passed**. New drift guard: 3 passed. `ruff --select S` clean on the new code. Findings
classified below.

### Findings (validated)
- `projection.py` ANSWER_SURFACES / EXPLORATION_SURFACES — **FALSE POSITIVE**. projection.py
  imports the registry (`DENSE_SURFACES`/`MULTI_SURFACES`, "single source (P4a)"); the two local
  sets are curated nomination subsets, proven `⊆ DENSE∪MULTI` (extra = ∅). Now drift-guarded.
- `selection.py` DIRECT/DISCOVERY/PRESENCE_SURFACES — **DEBT (low)**. Purpose-specific P4 fitness
  families (not the registry's `group`s), correct today; string-literal drift risk only. Now
  drift-guarded. Fix (derive from a registry fitness attr) deferred — not a bug.
- `scripts/profile_atom_canary.py` — **DEBT (low)**. A manual dev canary that calls the SAME
  `profile_atom_projection.project_atoms` into the SAME idempotent collection as the DAG wiring
  (11.283) — redundant, NOT conflicting. Retire candidate after P5b; harmless meanwhile.
- `POLYMATH_PROFILE_SCOUT` flag — **NOT A FINDING**: correctly absent (contract status = pending, P5b).
- callers of `search_atoms` / `profile_nominate` — **NOT A FINDING**: all in `chat_retrieval.py`
  (dualread) + the pure P5a docstring; every consumer uses the current signatures; the producer
  asymmetry (profile → doc_ids, atoms → rich) is handled correctly in dualread and in P5a.

## Rejected claims
- Rewrite the projection.py/selection.py surface tuples into registry lookups (rejected — validated correct + purpose-specific; a guard is the right, non-invasive fix).
- The profile_atom canary conflicts with the DAG wiring (rejected — idempotent shared collection; redundant, not conflicting).
- A large blast radius implies a bug (rejected — the impacted suite is green; the radius is expected for a foundational schema).

## Open contract gaps
- DEBT: `selection.py` fitness families are literals, not registry-derived (drift-guarded, not eliminated).
- DEBT: `scripts/profile_atom_canary.py` is redundant with the DAG wiring — retire after P5b lands.
