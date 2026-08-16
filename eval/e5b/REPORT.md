# E5B — Deterministic Concept Inventory Qualification (Part 1: Quality + Invariants)

Date: 2026-08-15
Status: **Part 1 complete (evidence frozen). Part 2 (routing A/B vs R1B
0.882 R@1) is pending full-stack bring-up + I2 re-ingestion — see
Open gaps.**
Implementation: `shared/polymath_shared/concept_inventory.py` (contract
`concept-inventory-v1`, routing representation
`routing-concept-enriched-v1`).
Verifier: `eval/e5b/verify_e5b.py` → `eval/e5b/evidence.json`.
Frozen docs: `eval/e3/corpus/docs/metacognition.md`
(`173a6a965e…`), `eval/e3/corpus/docs/metacognition_copy.md`
(`72aa463d…`), new `eval/e5b/corpus/youtube.md`
(`d24cfb187f…`).

## What the layer is

A deterministic, dependency-free concept extractor that runs over
already-chunked text: sentence-local 2–5-token content-phrase
candidates → fragment pre-filter (verb guard, weak-modifier lead,
genericity guard, >3-token spans) → longest-useful-span overlap policy
(span-containment independence; context-noise suppression) →
frequency-first deterministic ranking with `concept_id` tie-break →
budget admission (doc grid {4,8,12}, section grid {3,6,8}).

Concepts are retrieval metadata ONLY: `concept_<hash(normalized |
concept-inventory-v1)>` identity, per-occurrence provenance, original
surface + offsets. No entities, no facts, no graph, no admission
inputs. Identity normalization: NFKC, case fold, whitespace collapse,
hyphen≡space and slash≡space equivalence.

## Results (frozen evidence)

Candidate recall vs gold (GLiNER exact-match baseline in parentheses):

| doc | candidates | admitted @8 | admitted @12 | GLiNER baseline |
|---|---|---|---|---|
| psychology (13 gold) | **13/13** | 5/13 (P 0.625) | 5/13 (P 0.417) | 2/13 |
| cybersecurity (15 gold) | 12/15 | 3/15 (P 0.375) | 4/15 | — |
| youtube (12 gold) | 11/12 | 3/12 (P 0.375) | 4/12 | — |

- psychology section grid: union recall 4/13 at section budget 6.
- Error ownership (psychology, 13 gold): 5 ADMITTED,
  6 RANKED_OUT_BY_BUDGET, 1 OVERLAP_DROPPED (working memory —
  doc has no independent occurrence), 1 PRE_FILTER_REJECTED
  (metacognitive control — resolved to RANKED_OUT_BY_BUDGET in the
  final policy). NOT_GENERATED cases elsewhere are spec-conformant:
  alphanumeric product tokens (`OAuth 2.0`, `Keycloak 26.2`,
  `Elasticsearch`) and 4-token hyphen compounds
  (`buy-one-get-one`).
- Invariants: graph+facts zero-delta True (hash `04fcafa9b1201bbe…`
  identical before/after); two clean runs identical; concurrent run
  identical; replay identical; edited doc changes candidate set,
  unmodified docs unchanged; performance 2.4 ms/doc.
- R1A coverage A/B: enriched representation never reduces concept
  coverage vs baseline (equal or better on all 9 fixture docs).
- Pure determinism tests: `tests/determinism/test_concept_inventory.py`
  (10 tests, all green, no stores/sidecars).

## Verdict

Recall-positive vs the GLiNER-only baseline (2/13 → 13/13 candidate
recovery, 5/13 admitted at budget 8) with zero graph/extraction
delta. The dominant failure class is RANKED_OUT_BY_BUDGET —
single-occurrence concepts tie-break by `concept_id` when the ranking
tuple is exhausted; in production the `in_summary_text` component of
the ranking tuple (empty in this harness) is the intended tie-breaker.
Per E5 gate rules: **no production promotion, no contract mutation of
retrieval-summary-v2, EVEN ON PASS → STOP.** Part 2 routing A/B is
required before E5B is complete.

## Open gaps

1. **Routing A/B (part 2) pending**: Qdrant/Neo4j/Redis/orchestrator/
   control were down at qualification time. Requires: stack bring-up,
   I2 corpus re-ingestion (28 docs, live pipeline), R1B re-measure
   (expect 0.882 R@1 doc), then build disposable experimental
   collections `routing_document_summary_concept_e5b` /
   `routing_section_summary_concept_e5b` from `enriched_representation`
   with the same embedder pin and re-run the frozen R1B query set —
   no material regression + concept-lane comparison.
2. `in_summary_text` tie-breaker unmeasured in the harness (empty
   summaries); production uses real routing summaries.
3. 4-token concepts (per-bridged or multi-hyphen compounds) are
   pre-filtered by the >3-token span rule.
