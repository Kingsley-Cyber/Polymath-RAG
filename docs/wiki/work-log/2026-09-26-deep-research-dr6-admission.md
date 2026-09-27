---
change_id: DEEP-RESEARCH-DR6-ADMISSION
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The research-moves design (broad / deep / adjacent / inverse, a deterministic controller, a relevance gate) admitted into DEEP-RESEARCH-MODE-V1 as §10 and slices DR6a–DR6d."
architecture_impact: "docs only: docs/wiki/plans/DEEP-RESEARCH-MODE-V1.md (§5 rows, §10)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR6: admitting the research moves

## Contract
- The owner asked (2026-09-26) how deep research can "go deep and adjacent and breadth appropriately, and inverse but aligned with
  questions". The design was answered in chat. Then the owner said "go for the deep research moves design".

## Changes
- DEEP-RESEARCH-MODE-V1 §10 (DECIDED): the four moves and the search each uses, the planner grammar, the controller's
  intent weights and level signals, gap nodes, the relevance gate and spawn floor, report grouping, interfaces, receipts,
  UI, tests, and the live A/B acceptance.
- §5 gains DR6a (engine), DR6b (route + `/retrieve` `intent`), DR6c (UI), DR6d (live A/B).

## Proof
- Every surface §10 names already exists and was read, not assumed:
  - `query_intent.classify_intent` / `INTENT_POLICY` / `apply_intent_policy` (atom kinds, SEEALSO fan-out, graph
    destinations);
  - DOCUMENT-SCOPED-RETRIEVE-V1 (`document_ids` on the default lane);
  - `probe_gate.gate_probes` (floor 0.2, the reranker);
  - `build_evidence_rows(explore=True)` (2 rows per document);
  - the engine's plan → retrieve → extract → merge loop.

## Rejected claims
- "Moves need new retrieval modes": no. They pick among what exists, plus one optional `intent` input on `/retrieve`.

## Open contract gaps
- HYBRID answers one library per call (`single_corpus_or_422`). A multi-library deep research run needs a search per library;
  this is out of DR6's scope.
