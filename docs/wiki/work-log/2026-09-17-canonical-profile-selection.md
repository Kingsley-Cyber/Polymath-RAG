---
change_id: CANONICAL-PROFILE-SELECTION-V1
owner: king
date: 2026-09-17
status: complete
status_note: "Guard live (10 first projections 09-21). Leftover moved to the gap register as D-05: the refusal path never fired live and no rearm passes force=True. (was: implemented)"
architecture_impact: adds a fitness-gated canonical-selection guard before document-profile projection
last_reviewed: 2026-09-17
---

## Contract

Librarian checklist P4 (critical-path slice 1). Canonical profile selection becomes an
explicit, fitness-gated stage: a newly compiled profile that is materially thinner than the
active last-known-good projection must NOT silently overwrite it. Fitness is measured BY
FAMILY from the projected surface counts the payload already carries — `direct` (questions,
searches) and `discovery` (theories, concepts, seealso), plus the identity/theme anchors —
so no schema change is required. Only the answerability core (direct + anchors) blocks a
replacement; discovery-only shrinkage is allowed ("good for what", not "good/bad"). The
sanctioned rearm/override projects anyway via `force=True`.

## Changes

- `shared/polymath_shared/document_profile/selection.py` (NEW): pure `profile_fitness()` +
  `select()` (`CANONICAL-PROFILE-SELECTION-V1`). Decisions: `first_projection`, `forced`,
  `regression_lost_anchors`, `regression_direct_thinned`, `improvement`, `accepted`.
- `shared/polymath_shared/document_profile/projection.py`: `project_profile()` gains
  keyword-only `existing_surfaces` + `force`; computes `new_counts`, runs the guard, and on a
  refused replacement returns a `kept_last_known_good` receipt WITHOUT upserting (the richer
  point stands). New `fetch_existing_surfaces()` reads the active point's `surfaces` counts
  defensively (any error → None → projects, so the guard can never wedge ingestion). Default
  `existing_surfaces=None` preserves every existing caller's behaviour.
- `workers/workers/doc_profile_worker.py`: the projection stage fetches the active point's
  counts, passes them to the guard, and treats `kept_last_known_good` as a success (skips the
  vector-readiness gate, artifacts the decision, returns).
- Tests (NEW/extended): `tests/determinism/test_profile_selection.py` (6 asserts on the pure
  guard incl. thin-refused-over-rich and discovery-only-allowed); guard integration +
  `fetch_existing_surfaces` cases appended to `tests/determinism/test_document_profile_projection.py`.

## Proof

`PYTHONPATH=<worktree> .venv/bin/python -m pytest tests/determinism/test_profile_selection.py
tests/determinism/test_document_profile_projection.py tests/determinism/test_document_profile_stage.py
tests/determinism/test_document_profile_compiler.py tests/determinism/test_profile_atom.py` →
40 passed, 3 skipped. The decisive assert: `test_guard_refuses_a_thin_profile_over_a_richer_active_one`
projects a thin REPS (direct=5) against a rich active (direct=30) and asserts
`kept_last_known_good is True`, reason `regression_direct_thinned`, and `q.upserts == []`.

## Rejected claims

- "Guard on a single quality float." Rejected — the audited regression is a UNIT-COUNT
  collapse (Q15→Q1); a scalar quality confidence (self-disclaimed as non-semantic) would not
  reliably catch it. Fitness is counted by family from the surfaces the payload already holds.
- "Store fitness in Postgres now (migration)." Deferred — the active point's payload already
  carries `surfaces` counts, so the guard needs no schema change. First-class fitness columns
  belong to the later projection-integrity slice (P1/P2).
- "vNext ON should force overwrite." Rejected — vNext producing a thin profile is exactly the
  case to block; `force` is reserved for the explicit rearm/operator override.

## Open contract gaps

- Live proof pending: the worker seam (`fetch_existing_surfaces` → guard) is unit-proven but
  not yet demonstrated on a real fleet projection (a bounce + a doc_profile run on a
  non-forensic-hold corpus). Ledger status for the live path: IMPLEMENTED_NOT_PROVEN.
- `force` is not yet threaded from a rearm/backfill trigger into the worker (worker always
  passes the protective default). A later slice wires the operator override.
