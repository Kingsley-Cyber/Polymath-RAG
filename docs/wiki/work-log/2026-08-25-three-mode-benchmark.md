---
change_id: THREE-MODE-BENCHMARK-V1
owner: governance
date: 2026-08-25
status: implemented
architecture_impact: none
---

# THREE-MODE BENCHMARK V1 HARNESS (2026-08-25)

## Contract

Same 10-query set (exact_fact / identifier / procedure / concept /
paraphrase / broad / relationship / cross_domain / ambiguous /
no_answer) through VECTOR, HYBRID, GRAPH against one corpus under ONE
embedding contract; deterministic RRF fusion (k=60); per-query×mode
captures with latency. Behavioral only — NO accuracy claims without a
sealed judged set.

## Changes

eval/v5/retrieval/three_mode_benchmark.py:
- VECTOR: dense over routing_document_summary + section summaries +
  children (neural contract, sidecar-embedded query with instruct
  prefix).
- HYBRID: dense ∪ python term-overlap lexical → RRF.
- GRAPH: hybrid top-5 child seeds → their docs' eligible facts via
  Postgres evidence join (typed subject/predicate/object surfaces),
  evidence backfill by construction.
- First live run: release-books-v1 @ neural-embed-v1
  (polymath_a5dd094b555c_embed_e794ec4cab197a3f, 18,823 points).

## Proof

- All 30 query×mode cells executed; latencies VECTOR ~0.57–0.66 s,
  HYBRID ~0.91–1.85 s, GRAPH ~0.91–1.0 s (includes embed round trip).
- Behavioral sanity: q03 returns verbatim "To install Splunk on AWS…";
  q05 paraphrase lands on-call/reliability content; q10 (no-answer)
  still returns k nearest — abstention belongs to the answer layer;
  GRAPH emits typed facts ("splunk|uses|field aliasing").
- Artifacts committed alongside (json + md).

## Rejected claims

- NOT claiming VECTOR/HYBRID/GRAPH quality ranking — hypotheses remain
  unjudged until a sealed labelled set exists.
- NOT tuning any lane to make a ranking look right.

## Open contract gaps

- Lexical lane scans fetched rows (GAP G4) — no BM25 index yet.
- GRAPH facts limited to seed-doc-anchored evidence (hop0-style);
  Neo4j hop expansion intentionally not exercised until hop policy is
  frozen.
