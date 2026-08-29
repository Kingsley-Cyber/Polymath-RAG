---
change_id: summary-layer-s1-stages-envelope
owner: worker
date: 2026-08-23
status: complete
architecture_impact: adds-background-summary-stages-non-blocking
last_reviewed: 2026-08-23
---

# SUMMARY-VOCABULARY-LAYER SLICE S1: stages + artifact envelope

## Contract

Owner design of record (docs/wiki/plans/SUMMARY-VOCABULARY-LAYER.md):
the summary waterfall runs as BACKGROUND intelligence after settlement;
its failure degrades summaries, never blocks ingestion.

## Changes

1. `control/control/tickets.py`: four new DAG stages after settlement —
   parent_summary / document_summary / corpus_summary / vocabulary,
   each with its own `.v1` event type; NON_BLOCKING_STAGES + is_blocking;
   generation_barrier now excludes them from corpus promotion counting.
2. `contracts/summaries/v1/envelope.schema.json` + 
   `summary_layer.py::build_envelope/validate_envelope`:
   content-addressed provenance envelope (artifact_id = hash(input_hash,
   output_hash); input over derived_from ids; output over payload) with
   version/model/prompt_version/derived_from/created_at.
3. Pinned DAG test updated to the extended chain.

Workers themselves are S2–S4; this slice makes them schedulable and
their outputs contract-shaped. No worker logic, no model calls.

## Proof

- New tests: stage order/non-blocking membership; envelope roundtrip
  validates clean, rejects missing input_hash, output-hash tracks payload.
- Full suite: 886 -> 891 passed.

## Open gaps

S2 parent-summary worker; S3 document; S4 corpus; S5 vocabulary
admission; S6 router integration.
## Rejected claims

(Historical entry — recorded in the entry body above.)

## Open contract gaps

(Historical entry — recorded in the entry body above.)
