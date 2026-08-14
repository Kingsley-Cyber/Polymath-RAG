---
owner: sidecar-gpu
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# Experiment 0001: can GLiNER propose evidence spans?

## Question

The docx design gives pass 2 the job of proposing coarse evidence spans
(18 classes) so the compiler can map (entity types x evidence class x
trigger) onto predicates. Does the pinned GLiNER medium model do this
at a usable threshold?

## Method

- Sidecar: gliner-runtime, `urchade/gliner_medium-v2.1` @ 40ec419, CPU.
- Probe text: "John founded Acme in 2012. Acme uses Kubernetes. The GPU
  is a component of the workstation."
- Pass 2 label styles tried: (a) class ids only; (b) full descriptive
  prompts (docx §4.1); (c) short noun-phrase prompts. Thresholds
  0.05–0.5.
- Contrast model: `knowledgator/gliner-multitask-large-v0.5` with the
  descriptive prompts.

## Results

- gliner_medium-v2.1: ZERO spans for every style and threshold. The
  model was NER-trained; arbitrary event-ish labels never fire.
- gliner-multitask-large: fires, but the spans are ENTITY NOUNS, not
  verb phrases — "uses" evidence matched the span "Kubernetes" (0.97).
  Wrong span semantics for a predicate compiler.
- Entity pass on the same model (pass 1): excellent — John/Person 0.99,
  Acme/Organization 0.98, 2012/TimeReference 0.94, Kubernetes/Technology
  0.97.

## Decision

REJECT GLiNER as the evidence-pass proposer. SHIP the deterministic
lexical lane (`workers/evidence_proposer.py`): evidence spans are exact
matches of the rule pack's compiled trigger vocabulary (verbs, nouns,
multiword) with light lemma stripping. Bounded recall by design; the
curated lexicon is the coverage ceiling (docx §22, stated openly).

Pass 1 (entities) stays GLiNER through the pinned runtime.

## Revisit

If a future GLiNER release is trained for event/relation span proposals,
re-run this experiment before re-enabling the evidence task
(`POLYMATH_EVIDENCE_PROPOSAL_MODE`).
