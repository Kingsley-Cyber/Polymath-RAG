---
triggered_by: ADR-0012 (typed evidence support lanes)
status: done
last_reviewed: 2026-08-15
last_touched: 2026-08-15
---

# Refactor 0009: D3 typed evidence support lanes (TEXT / GRAPH)

ADR-0012 promoted textual retrieval evidence to a first-class typed
EvidenceBundle lane. This refactor materialized it:

- `contracts/answer/v2/evidence_bundle.schema.json` and
  `contracts/answer/v2/chat_response.schema.json`: v2 schemas with
  the `lane` (graph|text) and `text_kind` (document_summary /
  section_summary / child_chunk) fields; meta gains
  graph_claim_count / text_evidence_count (bundle) and
  text_support_count (response).
- `shared/polymath_shared/evidence_assembly.py` v2.0.0: every item is
  lane-typed; the assembler accepts document_summaries and
  section_summaries (deterministic `doc:<id>` / `section:<id>`
  locators); graph claim path is byte-identical to v1.
- `shared/polymath_shared/answer_synthesis.py`
  deterministic-template-v2: typed-lane validation — GRAPH claims keep
  the token-surface grounding rule; TEXT claims require verbatim
  containment in a supporting passage; mixed-lane support fails
  closed; default proposer emits deterministic excerpts (window around
  the query's rarest long token); renderer emits graph sentences first
  then cited passages; abstention only when both lanes are empty.
- `orchestrator/orchestrator/api/chat.py` and `evidence.py`: pass
  document summaries (retrieval_profile.semantic_summary) and section
  summaries (parent chunk summaries) into the bundle.

Affected dependents verified: G3 rerank path unchanged; graph lane
grounding/conflicts/epistemics unchanged; frozen tests updated
deliberately (2 determinism, 2 contract suites, 2 integration
assertions) — recorded in work log
2026-08-15-d3-text-evidence-lane.md; new lane tests added (independence,
augmentation, verbatim fail-closed, mixed-lane rejection, lane typing,
locators). Full unit + integration suites green.

Live smoke verification: all six metacognition gate queries now answer
with cited in-corpus passages (text_support=10, 0 foreign citations);
the vague "system" query gains no graph authority.
