---
title: "WORK LOG — P5a: profile_scout.py pure dual-projection fusion primitive"
change_id: PROFILE-SCOUT-P5A
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Adds the pure P5a fusion primitive per PROFILE-SCOUT-V1 (+ its refinement). shared/polymath_shared/document_profile/profile_scout.py holds the normalized ScoutHit/ProfileScoutResult types and fuse_profile_scout_hits() — deterministic RRF over two already-normalized ranked hit lists, AT MOST ONE contribution per doc per projection, full provenance, representative_text/surface (no derived capability). No I/O, no injected search, no LLM, no dependency beyond stdlib dataclasses. Not wired anywhere yet (P5b wires it). Additive; nothing else changes."
---

## Contract
Implement the frozen P5a primitive: a genuinely pure function that fuses two normalized
`ScoutHit` lists (DOCUMENT_PROFILE + PROFILE_ATOM) into a bounded `ProfileScoutResult` by RRF,
with per-projection single-vote collapse, full provenance, and verbatim representative pointers
— no I/O, no injected search callable, no interpretation. Acceptance: the ten owner tests pass
(deterministic ordering; both-projection contributions; repeated atoms = one vote; full
provenance; empty ⇒ empty; single-projection ok; top_k; doc_id tiebreak; scores provenance-only;
no planner/answer/gate fields).

## Changes
- New `shared/polymath_shared/document_profile/profile_scout.py`:
  - types `ScoutHit` (atom-only fields optional — profile hits are `{doc_id, source, rank}`),
    `ProjectionContribution`, `ProfileNomination` (`fused_score`/`rank`/`matched_surfaces`/
    `surface_types`/`representative_surface`/`representative_text`/`contributions`/`provenance`),
    `ProfileScoutResult`;
  - `fuse_profile_scout_hits(profile_hits, atom_hits, *, rrf_k=60, max_documents=8)` — collapse
    each projection to the doc's best rank → one RRF vote per projection; `fused_score` =
    Σ 1/(rrf_k+best_rank); order fused desc, doc_id asc; provenance keeps every hit; the best
    text-bearing hit is the representative.
- New `tests/determinism/test_profile_scout.py` — 11 asserting tests (the acceptance list).
- Register row 11.289. TREE: the module, the test, and this work-log.

## Proof
`PYTHONPATH=<worktree> .venv/bin/python -m pytest -q tests/determinism/test_profile_scout.py`
→ **11 passed**. Key asserts: `test_repeated_atoms_for_one_doc_are_a_single_projection_vote`
(3 atom rows ⇒ one vote at best_rank=1, `fused==1/61`, provenance len 3);
`test_raw_scores_are_provenance_only_not_cross_projection_calibrated` (a rank-1 profile hit with
no score beats a rank-5 atom hit with score 0.99; the 0.99 survives only in provenance);
`test_result_carries_no_planner_answer_or_gate_fields`. repo_guard / wiki_worm green.

## Rejected claims
- Calling search backends inside the primitive (rejected — P5a is pure; search+normalization is P5b).
- Deriving a semantic `capability` (rejected — verbatim `representative_text`/`representative_surface` only).
- Per-hit RRF votes (rejected — one vote per doc per projection via best-rank collapse).
- Treating raw profile/atom scores as comparable (rejected — RRF is rank-based; scores are provenance).

## Open contract gaps
- Not wired: P5b runs `projection.profile_nominate` + `search_atoms`, normalizes their outputs
  into `ScoutHit`s (profile → thin, atom → rich with SurfaceRegistry group), calls this fusion
  before `compile_plan`, and retires `_compiler_titles` — flagged + bounce-gated.
- `representative_*` is `None` for a profile-only nominated doc; proven here, exercised live in P5b.
- Live `PROFILE_ATOM` population per corpus is a P5b/L2 qualification gate.
