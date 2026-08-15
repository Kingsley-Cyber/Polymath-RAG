---
change_id: d3-text-evidence-lane
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: docs/wiki/decisions/0012-typed-evidence-support-lanes.md
---

# D3: typed evidence support lanes — TEXT and GRAPH are independent

## Contract

Per the user's architectural constraint: textual retrieval evidence
becomes a first-class, typed EvidenceBundle lane. TEXT_EVIDENCE
(document summary, section summary, child chunk, lexical/dense
retrieval evidence) and GRAPH_EVIDENCE (compiler facts,
graph-expanded facts) are INDEPENDENT support lanes: either may
support an answer on its own, both combine when available, and graph
evidence augments textual retrieval — it never gates it. No
special-case "no graph facts → dump chunks" fallback anywhere.

## Changes

- Contracts: `contracts/answer/v2/{evidence_bundle,chat_response}.schema.json`
  (lane, text_kind, lane counts).
- `evidence_assembly.py` v2.0.0: lane-typed items; document/section
  summary inputs; graph claim path unchanged.
- `answer_synthesis.py` deterministic-template-v2: typed validation
  (graph = token-surface grounding; text = verbatim passage
  containment, fail-closed); deterministic excerpt proposer; renderer
  emits graph sentences then cited passages; abstention only when both
  lanes are empty.
- `chat.py` + `evidence.py`: document summaries + section summaries
  flow into the bundle.
- Tests deliberately updated (recorded): 2 determinism tests flipped
  from graph-gating to TEXT-lane independence; 2 contract suites → v2
  schemas; 2 integration assertions → v2 contract ids + lane-aware
  claim counts. New tests: lane typing, locators, augmentation,
  verbatim fail-closed, mixed-lane rejection, non-verbatim rejection.

## Proof

- Unit/determinism/contracts: 0 failures. Integration: 0 failures.
- Live smoke corpus re-check: all six gate queries answer with cited
  in-corpus passages (10 text supports each, 0 foreign citations);
  vague "system" query gets passages from the actual document, zero
  graph authority.

## Rejected claims

- No generator/LMM involved; no fallback path; excerpts are
  deterministic windows over retrieved passages, verbatim-validated.

## Open contract gaps

- None for this lane. I1 (manifest-driven bulk ingestion) remains
  unblocked.
