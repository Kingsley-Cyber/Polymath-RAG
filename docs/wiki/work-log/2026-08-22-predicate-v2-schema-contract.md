---
change_id: predicate-v2-schema-contract
owner: worker
date: 2026-08-22
status: complete
architecture_impact: extends-L4-provenance-no-semantic-change
last_reviewed: 2026-08-22
---

# PREDICATE-COMPILER-V2 SLICE 1: schema contract

## Contract

Owner decision record (2026-08-22): the relation generator, not the
gates, is the remaining defect. V2 replaces association-based intake.
This slice makes provenance measurable so every later phase is auditable;
it changes no admission semantics and generates no candidates.

Policy decisions recorded by the owner and honored here:

- nominal triggers: KEEP under dependency confirmation only
- regex passive fallback: REMOVE from production (diagnostics only)
- SAFE_LOCAL_PATTERN definite descriptions: T1 retrieval enrichment only,
  never canonical identity or T2 facts

## Changes

1. `shared/polymath_shared/contracts.py`
   - `BindingSource` gains `UD_DEPENDENCY`, `NOMINAL_DEPENDENCY`
     (existing members retained — frozen replay depends on them).
   - `RelationCandidate` gains optional provenance fields:
     `document_id`, `sentence_id`, `trigger_token_id`,
     `subject_token_id`, `object_token_id`, `dependency_path`,
     `binding_source`.
   - New hard rule `v2_binding_refusal()`: a candidate with
     `trigger_token_id None` refuses `NO_TRIGGER_TOKEN`; a candidate
     whose binding source is not a V2 dependency source refuses
     `UNLICENSED_BINDING_SOURCE`. No exceptions.
2. `stores/postgres/migrations/0023_predicate_v2_provenance.sql`
   - idempotent columns on `relation_candidates`: `trigger_token_id`,
     `subject_token_id`, `object_token_id`, `dependency_path`,
     `binding_source`, `sentence_id`; index on `binding_source`.
3. `shared/polymath_shared/raw_evidence.py`
   - L4 row + INSERT carry the new columns. Legacy/kimi_v1 candidates
     persist NULL token ids — which is precisely the measurable signal
     the acceptance gates will count. Content hash of `candidate_id`
     unchanged: provenance is an attached measurement, not identity.

Not touched (per owner instruction): GLiNER, Entity Admission,
Fact Admission gates F1–F8, knowledge tiers, retrieval.

## Proof

- New tests (`tests/determinism/test_predicate_v2_schema.py`): enum
  members exist; refusal rule fires on missing token / non-dependency
  source and passes on UD/NOMINAL sources; L4 row emits the new columns,
  NULL for legacy-shaped candidates.
- Migration applied to the live store; `information_schema` shows the
  six new columns.
- Full suite green before change: 832 passed, 68 skipped (HEAD 5245dd6).

## Rejected claims

- "Slice 1 could also flip the dispatch default." — no. Production keeps
  running legacy_v1 until the owner flips after shadow A/B; this slice
  only makes the difference measurable.
- "binding_source belongs inside lexical_semantic_evidence only." — a
  top-level column is required for gate SQL without JSON traversal, and
  kimi_v2 sets it before any compiler runs.

## Open contract gaps

- kimi_v2 generator does not exist yet (slice 2); nothing produces
  UD_DEPENDENCY rows in production until then.
- Acceptance-gate SQL over these columns arrives with slice 7.
