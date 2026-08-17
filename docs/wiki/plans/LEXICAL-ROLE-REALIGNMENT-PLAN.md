---
owner: worker
last_reviewed: 2026-08-17
last_touched: 2026-08-17
status: draft
---

# Implementation Plan: Lexical-Role Realignment (ADR-0016)

Status: DRAFT — not authorized for implementation. This plan records
the concrete steps to realign the pipeline to the Kimi architecture
per ADR-0016. A named gate must authorize each phase.

## Summary of what changes

The current pipeline uses positional left/right binding with an early
type-compatibility veto. The Kimi architecture uses UD-tree argument
binding with PropBank semantic-role assignment, and applies types only
after structural candidates exist. The realignment moves the type
check from "before candidates form" to "after structural argument
candidates exist, before the compiler."

## Current vs target flow

```
CURRENT (to change):
  GLiNER types → _slot_compatible (HARD VETO) → left/right positional
  → candidate → lexical resources (consulted too late) → compiler

TARGET (Kimi):
  GLiNER pass 1 entities → GLiNER pass 2 evidence classes →
  spaCy UD structure → compiled lexicon (VN/PB/FN/SemLink) →
  PropBank ARG0/ARG1 assignment → structural argument binding →
  cheap type-pair precheck → predicate compiler →
  ontology validation → fact
```

## Phase 1: UD-tree argument binding (replaces positional)

**What:** Replace `_slot_compatible` + left/right positional binding in
`build_candidates` with dependency-tree argument identification.

**How:**
- From the spaCy parse (already available as `SentenceSlice.syntax`),
  identify the trigger token's syntactic dependents:
  - `nsubj` / `nsubj:pass` → grammatical subject
  - `dobj` / `obj` → grammatical object
  - `obl` / `pobj` (via prep) → oblique object
  - `agent` (passive) → by-agent
- Map entity spans to argument positions by checking which entity's
  head token fills each dependency slot
- Bounded linear window as RECALL NET only (for entities not caught
  by the tree, not as the primary mechanism)

**Files:** `workers/candidates.py` (build_candidates restructure)

**NOT changing:** the trigger localization (evidence_proposer stays),
the evidence class taxonomy, the rule pack

## Phase 2: PropBank ARG assignment

**What:** Actually assign PropBank ARG0/ARG1/ARG2 roles to entity
endpoints, instead of just carrying roleset IDs as metadata.

**How:**
- The compiled lexicon already maps trigger lemma → roleset (e.g.,
  "use" → use.01). The PB frameset for each roleset defines ARG
  labels with their semantic descriptions (e.g., use.01: ARG0=user,
  ARG1=thing used)
- After UD argument binding (Phase 1), assign:
  - syntactic subject (nsubj) → try ARG0 first
  - syntactic object (dobj/obj) → try ARG1 first
  - oblique/prepositional → try ARG2 or ARGM
- Voice normalization already exists (`_oriented_pair`); integrate
  with role assignment so passives swap correctly
- Store assigned roles on the RelationCandidate

**Files:** `shared/polymath_shared/rulepack/compiler.py` (role
assignment), `workers/candidates.py` (carry roles into candidates)

## Phase 3: Type-pair precheck AFTER structural candidates

**What:** Move the `_slot_compatible` type check from BEFORE argument
binding to AFTER structural candidates exist but BEFORE the compiler.

**How:**
- Remove the type filter from the entity selection loop in
  `build_candidates` (lines ~255-270)
- After UD-tree argument binding creates (subject, object) pairs:
  - Apply the CHEAP type-pair precheck: `_type_compatible(subject_type,
    object_type, evidence_class, rule_pack)` — this is a single
    dictionary lookup, not a per-signature loop
- Candidates that fail type-compat are recorded as traced losses
  (existing observability: OBJECT_TYPE_INCOMPATIBLE) but now they
  were STRUCTURAL candidates first, not type-filtered before structure

**Files:** `workers/candidates.py` (remove early filter, add post-
structural filter)

## Phase 4: Compiler receives role-annotated candidates

**What:** The compiler uses assigned PropBank roles + VN classes + FN
frames + type features to select the canonical predicate.

**How:**
- The compiler already receives `candidate.roleset`,
  `candidate.verbnet_classes`, `candidate.framenet_frames` — these
  are already populated from the compiled lexicon
- ADD: `candidate.assigned_roles` = {ARG0: span_text, ARG1: span_text}
- The compiler's predicate selection uses:
  1. Evidence class (from pass 2 trigger)
  2. Trigger lemma → roleset
  3. VN class membership
  4. FN frame compatibility
  5. Semantic roles (ARG0/ARG1 orientation)
  6. Type-pair compatibility (from Phase 3 precheck)
- The ontology signature check runs LAST as validation of the
  compiled interpretation, not as a pre-candidate gate

**Files:** `shared/polymath_shared/rulepack/compiler.py`

## Phase 5: Observability alignment

**What:** Update reason codes and trace events to reflect the new
pipeline order.

**How:**
- New reason codes:
  - `UD_SUBJECT_BOUND` / `UD_OBJECT_BOUND` / `UD_OBLIQUE_BOUND`
  - `UD_NO_ARGUMENT_IN_SLOT`
  - `ROLE_ARG0_ASSIGNED` / `ROLE_ARG1_ASSIGNED`
  - `TYPE_PRECHECK_PASS` / `TYPE_PRECHECK_FAIL` (after structural)
- Trace events record: trigger → UD binding → role assignment →
  type precheck → compiler entry → decision

## Phase 6: Qualification

**What:** Prove the realignment on dev + frozen I4.

- Dev: re-run QUALITY-PROBE with FULL trace — the key sentence
  ("A robust implementation uses bounded leases") should now produce
  a candidate because the UD tree binds robust implementation as
  nsubj→uses regardless of its Technology typing; the type precheck
  then filters (Technology→Technology for uses) — but the FIRST LOSS
  is now TYPE_PRECHECK_FAIL (honest), not SUBJECT_ENDPOINT_UNAVAILABLE
  (misleading)
- Frozen I4: baseline vs realigned — TP/FP/FN/P/R + all trace
  distributions

## What does NOT change

- GLiNER model/revision/threshold (frozen)
- Pass 1 entity extraction (unchanged)
- Pass 2 evidence class taxonomy (unchanged, ~18 classes)
- spaCy sidecar contract (syntax-evidence-v1, unchanged)
- Trigger localization (evidence_proposer, unchanged)
- Rule pack predicates/signatures (unchanged)
- Rescue semantics (unchanged)
- Admission (unchanged)
- Chunking (unchanged)
- I4 gold/scorer (unchanged)

## Estimated effort

Phases 1-3 are the core structural change (candidates.py restructure).
Phase 4 is compiler integration. Phase 5 is observability. Phase 6
is measurement. The type-pair precheck is RETAINED (per Kimi) — the
correction is ordering (after structural candidates), not elimination.

---

## APPENDIX A: Full Execution Directive Reference (KIMI-ARCHITECTURE-REALIGNMENT-V1)

This appendix preserves the complete execution directive verbatim as
the authoritative reference for each implementation phase. The phases
below map to the implementation plan phases above.

### SOURCE-OF-TRUTH INVARIANTS (I1–I12)

I1. GLiNER never decides a graph relation.
I2. Pass 2 uses evidence classes (~18), not graph predicates.
I3. Candidate generation is evidence-anchored.
I4. UD / spaCy is the primary structural binding source.
I5. PropBank rolesets must be operational, not decorative.
I6. Direction is role-based.
I7. VN / PB / FN / SemLink are active compiler inputs.
I8. Type compatibility may exist as a cheap pre-check, but only
    after structural argument candidates exist.
I9. The predicate compiler is the semantic-mapping authority.
I10. Ontology signature validation remains real.
I11. UNSUPPORTED means no edge. Never guess.
I12. Graph and retrieval architecture are out of scope.

### Phase-by-phase directive mapping

| Directive Phase | Content | Implementation Plan Phase |
|---|---|---|
| Phase 0 | Freeze executable baseline; version as legacy_v1 vs kimi_v1 | (pre-work) |
| Phase 1 | Repository-reality architecture diff (29 stages) | Phase 1 |
| Phase 2 | Restore Pass-2 responsibility (evidence classes) | (existing, verify) |
| Phase 3 | POS-aware lemma normalization | (existing I3R-R1, verify) |
| Phase 4 | Map entity spans to UD heads | Phase 1 |
| Phase 5 | Evidence-anchored candidate argument discovery | Phase 1 |
| Phase 6 | Primary UD patterns (active/passive/prep/copular/nominal/coord) | Phase 1 |
| Phase 7 | Coordination via dependency conj | Phase 1 |
| Phase 8 | PropBank role assignment (ARG0/ARG1/ARG2) | Phase 2 |
| Phase 9 | LexicalSemanticEvidence object | Phase 4 |
| Phase 10 | Type compatibility in its correct place (after structural) | Phase 3 |
| Phase 11 | Predicate compiler realignment | Phase 4 |
| Phase 12 | Full signature validation | Phase 4 |
| Phase 13 | Direction and voice (role-based) | Phase 4 |
| Phase 14 | Modality/negation/attribution (keep precision) | (existing, verify) |
| Phase 15 | Qualifiers (ARGM-TMP/LOC/measurement) | (existing, verify) |
| Phase 16 | Observability realignment | Phase 5 |
| Phase 17 | Fallback discipline (UD_PRIMARY vs SAFE_FALLBACK vs BOUNDED_RECALL) | Phase 5 |
| Phase 18 | QUALITY-PROBE-001 rerun | Phase 6 |
| Phase 19 | I4 regression (legacy vs kimi_v1) | Phase 6 |
| Phase 20 | Specific regression classes (active/passive, coordination, prep, etc.) | Phase 6 |
| Phase 21 | Candidate explosion gate (mandatory) | Phase 6 |
| Phase 22 | Pass-2 quality scored independently | Phase 6 |
| Phase 23 | Entity quality remains separate | Phase 6 |
| Phase 24 | Performance (ms/chunk, chunks/sec) | Phase 6 |
| Phase 25 | Lexical microbench (p50/p95/p99 µs/op) | Phase 6 |
| Phase 26 | spaCy performance measurement | Phase 6 |
| Phase 27 | Provider abstraction (GLiNER2-compatible boundary) | (existing, verify) |
| Phase 28 | Temporal durability (version identity) | Phase 5 |
| Phase 29 | Do not promote on architecture alone | Phase 6 |

### Qualification criteria (18 items)

1. GLiNER does not decide predicates.
2. Pass 2 emits coarse evidence classes.
3. Candidate generation is evidence-anchored.
4. UD syntax is primary argument-candidate evidence.
5. Broad left×right Cartesian pairing is eliminated.
6. PropBank roles are actually assigned to endpoints.
7. Canonical direction is role/voice based.
8. VN/PB/FN/SemLink participate before the predicate decision.
9. Type pre-check occurs only after structural candidate generation.
10. Full predicate signature validation remains enforced.
11. Unsupported/ambiguous cases abstain.
12. Existing negation/modality safety is preserved.
13. Exact provenance remains intact.
14. Observability explains every terminal outcome.
15. Candidate explosion is absent.
16. Determinism/idempotency remain intact.
17. Retrieval/text-memory behavior does not regress.
18. Frozen evaluation shows defensible semantic improvement OR
    clearly demonstrates the next bottleneck lies outside this drift.

### Hard freeze list

DO NOT change: GLiNER model/revision/threshold/query vocabulary/
arbitration; semantic chunking; extraction-context policy; entity
admission; canonical identity; predicate inventory/meanings; ontology
signatures (merely to improve scores); negation/modality policy; graph
projection; retrieval; I4 gold/scorer; frozen artifacts.

DO NOT: switch to GLiNER2; add GLiREL/Relex/LLM/embedding relation
classification/neural coreference; begin I5; auto-promote.

### Governance

ADR required (KIMI-ARCHITECTURE-REALIGNMENT-V1) stating responsibility
boundaries. Corrected candidate-generation rule:
EVIDENCE-ANCHORED + UD-BOUNDED + TYPE-COMPATIBLE + ROLE-ORIENTED
(not LEFT×RIGHT + EARLY TYPE VETO).

Update: CURRENT_STATE, TREE, ARCHITECTURE_CHANGELOG, work log,
experiment index. Do not delete legacy until qualified.

### Possible outcomes

- QUALIFIED_CANDIDATE
- NOT_QUALIFIED
- ARCHITECTURALLY_ALIGNED_BUT_QUALITY_BLOCKED
- INVALID

Production default stays legacy_v1 unless separately authorized.
