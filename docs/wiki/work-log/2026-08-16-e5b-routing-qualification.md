---
change_id: e5b-routing-qualification
owner: governance
date: 2026-08-16
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: complete
architecture_impact: none (qualification only; experimental Qdrant collections
  are disposable; no production collection, contract, or dependency changed)
---

# Work Log: 2026-08-16 — E5B part 2 routing qualification — REJECT

## Contract

Run the frozen routing A/B authorized by E5B: A = qualified
retrieval-summary-v2 representations (production Qdrant points,
untouched); B = retrieval-summary-v2 + bounded concept-inventory-v1
serialization under routing-concept-enriched-v1, projected ONLY into
the disposable experimental collections
`routing_document_summary_concept_e5b` /
`routing_section_summary_concept_e5b` with the frozen embedder pin
(Qwen3-Embedding-0.6B @ `97b0c614…`). No summary/candidate/ranking/
budget/embedding policy changes. No tuning after observing results.
Owner: governance (qualification). Inputs: frozen R1B query set
(`eval/r1b/queries.json`, git-frozen at `1c75735`), live re-ingested
I2 corpus (28 main + 4 isolation docs). Outputs: frozen evidence
`eval/e5b/{routing_ab,coverage_ab,retention,zero_delta,evidence_p2}.json`
+ report. Persistence effect: two disposable Qdrant collections only.

## Changes

- `eval/e5b/routing_ab.py` (new): validated routing A/B harness
  (pass1_retrieve with kind-aware collection override; both corpus
  collections searched to mirror R1B exactly; point-id rebuild
  determinism).
- `eval/e5b/coverage_ab.py` (new): R1A coverage A/B on the frozen
  coverage fixture (A = retrieval-summary-v2, B = v2 + concepts).
- `eval/e5b/retention.py` (new): pre-budget deterministic ranks of
  all 13 psychology gold concepts.
- `eval/e5b/zero_delta.py` (new): graph/extraction/Neo4j zero-delta
  reconfirmation after concept projection.
- `eval/e5b/freeze_p2.py` + `evidence_p2.json` (new): consolidated
  frozen evidence with verdict.
- `eval/e5b/REPORT.md`: part-2 section appended (part 1 intact).
- Infrastructure: Redis container recreated to apply the host port
  mapping (compose.yaml unchanged); orchestrator/control/8 workers
  started host-native with the .env DSN; I2 corpus re-ingested live
  (250s, p50 122.6s/doc, 28/28 + 4/4 query_ready).

## Proof

- Harness validation: baseline arm reproduces the frozen R1B numbers
  exactly (doc R@1 0.882, sec R@1 0.882, MRR 0.910/0.897).
- Candidate arm: doc R@1 0.853 (−0.029), R@3 0.941 (+0.029), R@5
  0.941 (+0.029), MRR 0.888 (−0.022); sec R@1 0.853 (−0.029), R@3
  0.941, R@5 0.941, MRR 0.882 (−0.015).
- Query deltas: doc 1 improved / 29 unchanged / 4 regressed; sec
  1 improved / 31 unchanged / 2 regressed. Real regressions are both
  psychology: `p1_sectionled_2` 1→3 (iso/memory_note.txt concept list
  absorbs the query term "calibration"), `p1_cross_1` 2→3. One psych
  query improved (`p1_paraphrase_5` 6→3 doc, 99→3 sec).
- R1A coverage: unchanged in both arms (0.870/0.778/0.889, redundancy
  0.0); size +74%.
- Zero-delta after projection: graph ✓, extraction ✓, Neo4j concept
  nodes 0 ✓.
- Determinism: two candidate runs identical; point ids identical
  across collection rebuild.
- Performance: ~1 ms/doc concept extraction; embedding +64% batch
  wall for +74% text; search latency unchanged.

## Rejected claims

- No routing improvement claimed: R@1 regresses by one query in each
  lane; coverage unchanged.
- No production promotion, no contract changes, no summary/ranking/
  budget/guard/serialization tuning after observation.
- No rewrite of part-1 evidence (`eval/e5b/evidence.json` untouched;
  the metacognitive-control classification correction is recorded in
  part-2 evidence, not back-edited).

## Open contract gaps

- E5C hypotheses recorded only: occurrence-count admission floor,
  summary-co-occurrence admission gate, corpus-level frequency
  normalization, short-document budget reduction.
- The `in_summary_text` ranking component (present in `ba363ec`,
  used as committed) remains an untested-as-admission-gate signal.
