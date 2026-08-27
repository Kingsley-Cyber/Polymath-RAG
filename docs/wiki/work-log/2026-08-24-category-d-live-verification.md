---
change_id: category-d-live-verification-recovery
owner: worker
date: 2026-08-24
status: complete
architecture_impact: none (defect repair + bounded binding recall inside existing kimi_v1 lane)
last_reviewed: 2026-08-24
---

# CATEGORY-D live verification + definite-head repair + C3c possession recall

## Contract

Complete the CATEGORY-D slice by verifying the committed dep-label fix
(12c713d) against the LIVE fleet, then recover the two remaining doc01
target facts (`trained_on`, `evaluated_on`) through bounded, deterministic
repairs only. No new predicates, no admission weakening, no schema change.
Frozen architecture untouched; kimi_v1 candidate generation is the only
behavioral surface.

Smallest acceptance criteria:

1. Fleet restarts clean under `kimi_v1`+`shadow`+`spacy` with bundle
   `v5-production-006`; `verify_live_build.py` scoped to pipeline slots
   returns PASS.
2. Live extraction of tagged doc01 yields `introduced_by` ACCEPT
   (CATEGORY-D fix proven end-to-end).
3. "The model was trained on X" binds via I3R-R3 definite recall after
   aux-tail head repair → `trained_on` candidate + fact.
4. "…examined Orion's performance … including ReasonBench" binds Orion as
   evaluation theme via C3c possession inheritance (unique type-compatible
   document-history entity; ambiguity abstains) → `evaluated_on` candidate
   + fact.
5. Red fixtures `test_sval_doc01_red.py` converted from unconditional
   markers into real assertions of the three bindings (their stated
   purpose); determinism tests added for both repairs.

## Inputs / outputs / persistence

Inputs: doc01 text (tagged variant), sidecars GLiNER/spaCy/embedder,
rule pack v1.4.0. Outputs: relation_candidates rows (L4) and facts rows
(L5) for corpus `s-val-doc01-cutover-v1`. Persistence effect confined to
normal pipeline tables.

## Changes

1. `workers/workers/candidates.py::_resolve_definite_description`: strip
   closed-class auxiliary/adverb tail from the captured definite phrase
   before head-word matching ("the model was" → head "model"). Bounded
   closed-class list only; zero/ambiguous matches still abstain.
2. `workers/workers/kimi_candidates.py`: C3c — in the FRAME anchor path,
   when the oriented theme token carries a UD `poss` child whose surface
   equals exactly ONE subject-type-compatible entity in
   `doc_entities_history`, bind that entity as theme endpoint with
   `BindingSource.SAFE_LOCAL_PATTERN`. Fail-closed on zero/multiple hits.
3. `tests/determinism/test_sval_doc01_red.py`: replace the three
   unconditional RED markers with real candidate-compilation assertions
   (the file's documented exit condition), keeping the anchors test.
4. Operational recovery recorded here: orphans killed (34894, 52270 — one
   was spamming PG auth failures ~11h), telemetry copied to
   `eval/v5/scale/`, bundle deliberately re-frozen `v5-production-006`
   over commit 266aa81 (owner E-1 pronoun ban, previously unfrozen).

## Proof

- Local repro pre-fix: `SUBJECT_ENDPOINT_UNAVAILABLE` for trained
  evidence (observer output captured in session).
- Post-fix repro: candidates include Orion--trained_on-->HorizonText and
  Orion--evaluated_on-->ReasonBench.
- LIVE (corpus `s-val-doc01-cutover-v3`, run
  `run_330446b2…ffffcc81`, shadow, kimi_v1, spacy): relation_candidates
  rows ACCEPT for introduced_by / trained_on / evaluated_on with
  subject `Orion Adaptive Reasoning Model`; persisted facts verified by
  candidate→fact join. UNSUPPORTED rows are correct rejections (Date,
  Architecture, Experiment-type) — zero false positives.
- `pytest tests/determinism/test_sval_doc01_red.py
  tests/determinism/test_category_d_followup.py
  tests/determinism/test_kimi_candidates.py` → 14 passed.

## Pre-existing failures recorded (NOT introduced here; unchanged)

- `test_evidence_bundle` / `test_raw_evidence_ledger` /
  `test_span_hypotheses` bundle-pin tests hard-pin authority
  `6976e483…` while the live authority is `557afbc3…` — pins went stale
  at an earlier licensed change; they fail identically on clean HEAD.
- `test_vocabulary_mapping` ×2 IndexError — fails identically on clean
  HEAD.
- `agent_preflight.py`/`repo_guard.py`: ~200 COMMITTED files flagged
  undeclared (scaffold TREE is stale repo-wide, includes
  NEXT_SESSION_HANDOFF.md itself) + 12 older work-logs missing required
  sections. Systemic, pre-dates this slice.
- `tests/contracts/test_syntax_provider_gate.py` ×2 pass under default
  env, fail only when POLYMATH_SYNTAX_PROVIDER=spacy leaks into the test
  process (env-sensitivity, not a code regression).

## Rejected claims

- "Drain was converging" — false at handoff time: open flat at 5156 for
  25+ min, worker refused all leases on contract mismatch.
- "Fixtures were already green post-12c713d" — false: they are
  unconditional `pytest.fail` markers; unit verification covered binding
  primitives, not this document's sentences.

## Open contract gaps

- Frame-path C3-definite uses per-slice `prev_slice_entities`, which is
  always empty because extract_worker calls build_candidates one slice at
  a time — cross-sentence frame-definite resolution can never fire today.
  Recorded, not repaired in this slice (separate owner decision).
- Query-side intent routing and artifact persistence remain pending
  (charter phases P2/P5).
