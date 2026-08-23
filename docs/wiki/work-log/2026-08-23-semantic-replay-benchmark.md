---
change_id: semantic-replay-benchmark-v1
owner: worker
date: 2026-08-23
status: complete
architecture_impact: adds-durable-regression-benchmark-record
last_reviewed: 2026-08-23
---

# SEMANTIC-REPLAY-BENCHMARK-V1

## Contract

Owner addition before production: every corpus ingestion produces a
machine-comparable record so regressions are diffable across pipeline
versions. Written per extract run as `replay_benchmark` inside the
stage artifact (`artifacts(run_id, stage='extract')`), next to the
timing audit.

## Record fields (all seven owner-required + histograms)

run_id · corpus_id · document_id · pipeline_version
(`<extractor>+<relation_pipeline>`) · build_sha (env) ·
entity_contract_version (`admission-harbor-v2`) ·
predicate_pack_version (from the loaded pack) ·
vocabulary_version (`semantic-query-policy-v3`) ·
counts {fact_count, fact_qualified, event_count (0 until phase-6
reification lands), relation_candidates, mentions_persisted} ·
rejection_histogram {entity_admission by E-gate, compiler_decisions by
disposition, fact_admission_gates + fact_admission_reasons}.

## Changes

`workers/workers/extract_worker.py`: benchmark assembled from already-
computed counters (no extra passes) and persisted via writer.artifact.

Corpus-level comparison is SQL over artifacts ⋈ runs; no new endpoint
until the production-staging slice.

## Proof

Live record captured for corpus wedding-niche-v1 under pack 1.4.0 /
policy v3 / kimi_v2: predicate_pack_version=1.4.0,
vocabulary=semantic-query-policy-v3,
rejection_histogram.entity_admission={E7_DURABILITY: 12}.
Full suite green post-change.
