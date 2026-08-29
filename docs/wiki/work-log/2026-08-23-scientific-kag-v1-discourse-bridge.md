---
change_id: scientific-kag-v1-discourse-bridge
owner: worker
date: 2026-08-23
status: complete
architecture_impact: adds-deterministic-discourse-resolution-to-v2
last_reviewed: 2026-08-23
---

# SCIENTIFIC-KAG-V1 SLICE E (phase 5.5): discourse bridge

## Contract

Owner decision: scientific writing is not sentence-level; the missing
layer is DETERMINISTIC discourse resolution positioned after Entity
Admission and before the compiler, resolving only already-admitted
entities. Forbidden and not used: LLM extraction, embedding relations,
generative RE, REBEL, coreference libraries.

## Capabilities

1. Definitional apposition (intra-sentence): an argument token inside
   an `appos` subtree binds through to the entity head it describes.
2. Controlled anaphora (cross-sentence): pronoun + previous-sentence
   durable subject + unique in window + distance <= 2 -> the pronoun
   span resolves to that subject. The resolved entity outranks the
   pronoun's own GLiNER label; downstream type signatures validate the
   RESOLVED type. Ambiguity or distance > 2 abstains.
3. Provenance: new BindingSource DISCOURSE_ANAPHORA (discipline tier
   SAFE_FALLBACK — honest: this is inference beyond raw UD), and
   dependency_path records `anaphora`.

Implementation lives in shared/polymath_shared/discourse_bridge.py
(pure functions over syntax tokens + admitted spans) with hooks in the
kimi_v2 argument binder only — no extract_worker spine change, no
admission change, no gate change.

## Changes

(Historical entry — recorded in the entry body above.)

## Proof

- Owner examples green: "Tree of Thoughts is a reasoning framework." /
  "It uses beam search." -> uses(Tree of Thoughts, beam search) via
  DISCOURSE_ANAPHORA; distance>2 abstains; apposition compound stays
  bound to its head entity.
- Full suite: 876 -> 879 passed.

## Open gaps

Phase 6 event reification; acceptance harness; 4-doc validation;
production ingestion staging.

## Rejected claims

(Historical entry — recorded in the entry body above.)

## Open contract gaps

(Historical entry — recorded in the entry body above.)
