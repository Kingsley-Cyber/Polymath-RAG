---
change_id: extraction-audit-v1
owner: worker
date: 2026-08-22
status: complete
architecture_impact: adds-durable-extraction-audit-no-semantic-change
last_reviewed: 2026-08-22
---

# EXTRACTION-AUDIT-V1: per-document ms-timed audit report

## Contract

Owner request: the extraction phase must be auditable and capture time
in ms. Every extract run now writes a durable JSON report
(`extraction_audit` key inside the stage artifact,
`artifacts(run_id, stage='extract')`), plus a structured log line.
Monotonic `perf_counter` only; integer milliseconds; no semantic
effect — trace=off behaviour unchanged except for the added artifact.

## Report shape (extraction-audit-v1)

```
contract, run_id, corpus_id, document_id, relation_pipeline, bytes,
timing_ms { total, gliner, spacy, rescue, entity_admission,
            persist_mentions, predicate_compile, fact_admission, writes },
counts { chunks, sentences, gliner_entity_proposals,
         gliner_entity_rejected, evidence_spans,
         entity_admission_considered/refused, mentions_persisted,
         relation_candidates_by_decision{...},
         facts_passed/qualified/rejected/withheld }
```

## Changes

- `workers/workers/extract_worker.py`: counters at each stage boundary;
  fact-admission timing accumulated around `_fact_stage.admits`
  (separate timer — does not perturb `candidates_compile_s`);
  audit assembled after flush and persisted via `writer.artifact`.
  The legacy `perf` artifact key is retained for continuity.

Not touched: generators, gates, admission semantics, projections.
Projection/intake stage timing lives in those workers and remains a
reported gap of the mission's full phase-0 spec; this slice covers the
extract stage end to end.

## Proof

- Re-run of corpus wedding-niche-v1 produced an audit artifact with
  all keys populated; SQL:
  `SELECT payload->'extraction_audit' FROM artifacts WHERE run_id=… AND stage='extract'`.
- Full suite green post-change (855 passed pre-change baseline).

## Open contract gaps

- intake/projection stages have their own loops; same audit pattern
  should be replicated there when the owner admits that slice.
