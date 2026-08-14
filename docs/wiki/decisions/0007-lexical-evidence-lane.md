---
owner: sidecar-gpu
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: accepted
---

# ADR-0007: Replace neural evidence-span extraction with a deterministic lexical evidence lane

## Context

The Kimi architecture (docx §2, §4) assigns GLiNER pass 2 the job of
proposing coarse evidence spans (18 classes) so the compiler can map
(entity types × evidence class × trigger) onto canonical predicates.
The pinned runtime is `urchade/gliner_medium-v2.1` @ `40ec419`.

## Decision

Evidence discovery is performed by the deterministic lexical lane
(`workers/evidence_proposer.py`): exact matches of the rule pack's
compiled trigger vocabulary (verbs, nouns, multiword) with light lemma
stripping. GLiNER remains the entity-span proposer only.

## Measured basis (experiment 0001)

- `gliner_medium-v2.1` produced **zero** usable relation-evidence spans
  across every label style and threshold tested (class ids, descriptive
  prompts, short noun-phrase prompts; thresholds 0.05–0.5).
- `gliner-multitask-large` fires, but the spans are entity nouns, not
  verb phrases ("uses" evidence matched the span "Kubernetes" at 0.97)
  — wrong span semantics for a predicate compiler.

## Consequences

- Higher determinism: the evidence layer has no stochastic component.
- Lower inference cost: one GLiNER call per chunk, not two.
- Recall is bounded by lexical/rule coverage and must be measured
  explicitly (experiment 0002 owns that measurement).
- The sidecar wire contract keeps the `evidence` task for future
  qualification; it is not wired into the production path.

## Rejected

- Reintroducing a neural evidence pass "because the original research
  had one" — experimentally falsified on the pinned model.
