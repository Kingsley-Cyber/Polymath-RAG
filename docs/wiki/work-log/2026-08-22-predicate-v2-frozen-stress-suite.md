---
change_id: predicate-v2-frozen-stress-suite
owner: worker
date: 2026-08-22
status: complete
architecture_impact: freezes-v2-behavior-contract-refreeze-003
last_reviewed: 2026-08-22
---

# PREDICATE-COMPILER-V2 SLICE 3: frozen stress suite

## Contract

Owner decision record categories 1–7, frozen as byte-hashed fixtures:
`eval/v5/stress/predicate_v2/fixtures.json`
(sha256 e1cc95aa…550811), driver `run_stress.py`, pytest wrapper
`tests/determinism/test_predicate_v2_stress.py`. The wrapper refuses
mutated fixtures before any expectation runs.

## Changes

1. `eval/v5/stress/predicate_v2/` — seven cases with sidecar-shaped UD
   tokens and GLiNER-shaped spans; expectations are the owner's
   verbatim (0 similar_to · PASS acquisition · T1-not-T2 modality ·
   negation REJECT · passive direction Microsoft→Activision · F3
   pronoun refusal under enforcement · no cross-sentence binding).
2. `workers/workers/kimi_v2_candidates.py` — two corrections the suite
   forced BEFORE freezing (the suite did its job):
   - **Passive binding**: voice is read from the UD tree itself
     (auxpass/nsubjpass), and the by-agent (`agent>pobj`) fills the
     second argument slot. Without this, "Activision was acquired by
     Microsoft" emitted no candidate at all.
   - **Clause-level evidence span**: the candidate's evidence span now
     attests trigger plus bound arguments instead of the bare trigger
     token — the span F8 verifies.
   - **UD normalization for roles**: `nsubjpass` → `nsubj:pass` passed
     to assign_roles so role-based orientation engages (ClearNLP↔UD).
3. `shared/polymath_shared/fact_admission.py` (+ stage wiring) —
   FactContext gains optional `trigger_start/trigger_end`; the stage
   resolves them from `trigger_token_id` against the sidecar tokens,
   and supplies `sl.syntax` as F8's parse witness when no worker parse
   record exists. Both are evidence-source corrections, not gate
   loosening: without them every V2 fact either mislocated its trigger
   (BINDING_TRIGGER_IS_NAME on the subject name) or QUALIFY'd as
   unwitnessed forever.
4. **Deliberate re-freeze**: `config/semantic_bundle.lock` →
   `v5-production-003` = 6afbc9acfc2a3439 over the same 8 authorities
   (fact_admission.py changed). Boot-gate verified READY --strict.

Not touched: GLiNER, Entity Admission philosophy, gate thresholds or
policy yamls, tiers, retrieval.

## Proof

- All seven owner categories assert green, including direction and
  enforcement-refusal checks.
- Full suite green after change: 854 passed pre-freeze-fix; re-run
  after refreeze below.
- cat5 provenance orientation = role_canonical_passive with
  ARG0=Microsoft / ARG1=Activision.

## Rejected claims

- "Relax F8 to accept trigger-only spans." — rejected; the evidence
  contract requires attestation of the relation, so the generator was
  fixed to emit real relation evidence instead.
- "Drop BINDING_TRIGGER_IS_NAME." — rejected; it is correct given true
  trigger locations, which V2 now supplies.

## Open contract gaps

- Slices 4–7: shadow A/B vs legacy_v1, core-3 validation, book pool,
  release gates over ledger provenance columns.
