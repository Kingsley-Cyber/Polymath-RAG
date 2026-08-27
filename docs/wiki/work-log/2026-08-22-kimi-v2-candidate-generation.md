---
change_id: kimi-v2-candidate-generation
owner: worker
date: 2026-08-22
status: complete
architecture_impact: replaces-relation-intake-mechanism-v2-mode
last_reviewed: 2026-08-22
---

# PREDICATE-COMPILER-V2 SLICE 2: syntax-grounded candidate generation

## Contract

Owner decision record: the relation generator is the remaining defect;
the intake mechanism is replaced, not filtered. This slice adds
`kimi_v2_candidates.py` as a new pipeline mode (`POLYMATH_RELATION_PIPELINE
=kimi_v2`). Production default stays legacy_v1 until the owner flips
after shadow A/B; legacy_v1/kimi_v1 remain frozen for comparison and
replay.

V2 algorithm (per decision record):

1. spaCy sentence parse is the input (tokens + UD deps from sidecar
   syntax-evidence-v1). No parse -> no predicate.
2. Predicate occurrences originate at spaCy tokens:
   `token.lemma_ in authored registry` with POS gating (VERB/AUX for
   verbal predicates, NOUN for nominal). ADP "like"/"unlike" can never
   be a trigger because no token of that POS carries a licensed lemma.
3. Arguments bind only from dependency structure: nsubj/nsubj:pass for
   subjects; dobj/obj/iobj (+ attr/acomp/oprd under AUX copulas) for
   objects; prep>pobj subtrees for nominal predicates ("Tesla is part
   of the automotive industry" -> part_of(Tesla, industry)).
   Coordination via conj + governor-argument propagation stays in-clause.
4. No recall nets. A slot with no dependency-bound entity emits no
   candidate. Proximity, definite-description resolution, and any
   chunk-wide pairing are absent by construction.
5. Every candidate carries the slice-1 provenance fields; each satisfies
   `v2_binding_refusal() is None` by construction.

Policy honored: nominal triggers kept under dependency confirmation;
regex passive fallback not used on this path (slice 2b retires it
production-wide); SAFE_LOCAL_PATTERN never runs in V2.

## Changes

- `workers/workers/kimi_v2_candidates.py` (new): registry index over
  the authored pack, token-originated predicate occurrences, UD-only
  binding, PropBank role assignment + lexical-semantic evidence reused
  from kimi_v1 machinery so the compiler input shape is unchanged.
- `workers/workers/kimi_candidates.py`: dispatch recognizes `kimi_v2`.
- `workers/workers/extract_worker.py`: compiler routing sends kimi_v2
  candidates to `compile_relation_kimi`; builder call passes through
  unchanged otherwise.

Not touched (per owner instruction): GLiNER, Entity Admission,
Fact Admission gates F1–F8, knowledge tiers, retrieval.

## Proof

- Stress-category unit coverage arrives with slice 3's frozen suite;
  this slice's tests prove mechanism-level properties: token origin
  rejects ADP triggers, missing parse yields zero candidates, every
  emitted candidate passes v2_binding_refusal, nominal prep-of pattern
  binds part_of direction.
- Full suite green before change: 839 passed, 68 skipped (HEAD 1f08cd9).

## Rejected claims

- "kimi_v1 with the fallbacks removed would be equivalent." — v1 still
  discovers triggers from regex text-scan evidence spans and binds by
  surface order when the tree misses; that is the association
  philosophy. V2 derives occurrences from tokens instead.
- "The generator could flip the dispatch default." — cutover is the
  owner's act after gates pass, per execution order.

## Open contract gaps

- Slice 3 frozen stress suite; slice 4 shadow A/B vs legacy_v1;
  slices 5–7 corpus validations, book pool, release gates.
