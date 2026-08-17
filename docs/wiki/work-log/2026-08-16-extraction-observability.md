---
change_id: extraction-observability-v1
owner: worker
date: 2026-08-16
status: complete
architecture_impact: adds-observation-layer-no-semantic-change
last_reviewed: 2026-08-16
---

# EXTRACTION-OBSERVABILITY-V1: remove black-box extraction behavior

## Contract

Authorized 2026-08-16: instrumentation, decision tracing, reason codes,
funnels, first-loss attribution, sentence explanations, survival
traces, CLI — OBSERVE ONLY. No semantic changes (GLiNER/chunking/
admission/rescue/candidates/predicates/frames/negation/canonicalization/
projection untouched); trace=off must be byte-identical; trace=full
must be semantically identical. The observer never sees evaluator gold.

## §1 Pipeline map (from repository reality, 2026-08-16)

1. chunk input: intake_worker.process_event → semantic_chunker.
   semantic_chunk_rows (POLYMATH_CHUNKER=semantic_v2) | chunker.
   plan_document (legacy_v1)
2. sentence mapping: extract_worker._sentences_of → summarizer.
   split_sentences (chunk-relative offsets via text.find)
3. GLiNER pass 1: extract_worker._entity_spans → GlinerClient.
   entity_pass(chunk_text, profile labels, threshold 0.5)
4. raw span normalization: _entity_spans maps raw_label → core via
   query_policy.canonical_of; unmapped → rejected list (audit)
5. spaCy syntax: extract_worker._syntax_evidence → SpacySyntaxClient
   (syntax-evidence-v1 attached per SentenceSlice)
6. noun chunks: rescue._trimmed_noun_chunks (determiner-trimmed)
7. boundary rescue: rescue.apply_boundary (exact-NP re-query)
8. missing-arg rescue: rescue.apply_missing_arguments
9. type reconciliation: rescue.apply_type_reconciliation
10. mention persistence: extract_worker._persist_mentions
11. admission: polymath_shared.entity_admission.allocate_entity_id
    (GLOBAL/CORPUS_SCOPED/DOCUMENT_SCOPED/MENTION_ONLY)
12. trigger localization: evidence_proposer.propose_evidence +
    localize_trigger (typed trigger contract, I3R-R1)
13. predicate selection: compiler._trigger_matches (+ trigger_
    predicate_id from localization)
14. pre-candidate filters: candidates._type_compatible — SILENT skip
    (THE black box found by QUALITY-PROBE-001) + argument-frame binding
    in build_candidates (trigger-scoped frames)
15. candidate construction: candidates.build_candidates →
    RelationCandidate
16. frame checks: compiler._frame_satisfied (pack v1.3.0 frames)
17. type/signature: compiler stage-3 signature validation
18. negation/modality: compiler._modality_decision + ScopeFlags
19. E3B gates: endpoint_binding.binding_gate_violation
20. fact persistence: extract_worker._persist_decision
21. graph eligibility: neo4j_eligibility + admission class
22. Neo4j projection: project_neo4j_worker.process_event

## Changes

- shared/polymath_shared/observability.py — extraction-observability-v1:
  typed reason codes (categories DISCOVERY/SYNTAX/RESCUE/ADMISSION/
  TRIGGER/ARGUMENT_BINDING/CANDIDATE/COMPILER/FACT), TraceEvent
  envelope (identity: run/doc/chunk/sentence/trace ids + contract
  versions; timing excluded from semantic hashes), TraceCollector
  (in-memory, batch flush — no per-event commits), funnel + waterfall
  + first-loss aggregation.
- Migration 0014: extraction_trace_events (deterministic event
  identity = content hash; one event can never overwrite another).
- Settings: POLYMATH_EXTRACTION_TRACE=off|summary|full (default off).
- extract_worker: observer threaded through entity spans, admission,
  rescue, sentence processing; per-sentence candidate pre-filter
  reasons via observer callbacks (no behavior change when off);
  compiler reasons mapped to stable codes; batch trace persist +
  funnel artifact at stage end.
- candidates.build_candidates: optional observer param recording
  type-incompatible skips, argument-binding outcomes, coordination.
- compiler: decisions already audited; reason→code mapping only.
- scripts/trace_report.py — trace run/sentence/surface/fact/
  waterfall (reads trace events + semantic tables).
- eval/quality_probe_002/ — QUALITY-PROBE-001 rerun in FULL mode with
  automatic explanations (no semantic config change).

## Proof

- Tests A-N (tests/determinism/test_extraction_observability.py):
  off≡baseline, full≡off semantics, reason codes for every rejection
  class, batch persistence non-loss, deterministic trace content,
  event non-overwrite.
- QUALITY-PROBE-002 rerun: "robust implementation uses..." first-loss
  explained from runtime evidence; 10 surface survival paths emitted.
- I4 diagnostic join (analysis only; scorer untouched).
- Full suite green; frozen artifacts unchanged.

## Rejected claims

- No extraction-quality claim: zero semantic changes made.

## Open contract gaps

- see final report.
