---
title: "WORK LOG — P5b-a: pure producer→ScoutHit normalization"
change_id: PROFILE-SCOUT-P5B-NORMALIZE
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Adds the pure half of P5b — normalizing the two real producers into ScoutHit lists — to the scout module: profile_hits_from_doc_ids (profile_nominate's ordered doc_ids → thin hits) and atom_hits_from_search (search_atoms rows → rich hits, group injected). Pure, no I/O, no registry import. The I/O orchestration + ui.py wiring is P5b-b."
---

## Contract
Provide the deterministic normalization from the two real producers to `ScoutHit`, so the P5b
wiring stays thin (I/O only). Profile hits are thin (`profile_nominate` returns bare doc_ids);
atom hits are rich (`search_atoms` rows). The SurfaceRegistry group is injected, so the pure
module keeps no registry dependency. Acceptance: the helpers produce correctly-ranked ScoutHits
and fuse end to end.

## Changes
- `shared/polymath_shared/document_profile/profile_scout.py`:
  - `profile_hits_from_doc_ids(doc_ids)` → thin ScoutHits (rank = position; surface/text/score None).
  - `atom_hits_from_search(rows, *, group_of)` → rich ScoutHits (surface = atom_kind; surface_type
    via injected `group_of`; text/score from the row); drops rows without a doc_id.
- `tests/determinism/test_profile_scout.py` — 3 new tests (thin profile hits, rich atom hits with
  injected group, normalized→fused end to end). No scaffold/register-file changes (both files declared).

## Proof
`pytest tests/determinism/test_profile_scout.py` → **14 passed** (11 fusion + 3 normalization).
`contract_impact --staged` → CHANGED {PROFILE_SCOUT_FUSION, PROFILE_SCOUT_OUTPUT}; downstream
consumers listed. Additive only — no behavior change to `fuse_profile_scout_hits`.

## Rejected claims
- Import SurfaceRegistry into the pure scout module (rejected — `group_of` is injected so the module stays decoupled and pure).
- Do normalization inside `fuse` (rejected — normalization is a separate, injectable concern the wiring owns).

## Open contract gaps (impact dispositions)
- `PROFILE_SCOUT_FUSION` / `PROFILE_SCOUT_OUTPUT`: **UPDATED** (additive pure helpers; existing fusion + schema unchanged, proven by the 11 prior tests still green = **TESTED_UNCHANGED**).
- `PROFILE_SCOUT_INPUT` / `PROFILE_SCOUT_WIRING`: **DEFERRED** to P5b-b (the `ui.py` I/O wiring calls these helpers + the real searches, retires `_compiler_titles`, behind `POLYMATH_PROFILE_SCOUT`).
- `QUERY_PLANNER` / `RETRIEVAL_RECEIPT`: **NOT_AFFECTED** by this pure slice (touched only by P5b-b).
