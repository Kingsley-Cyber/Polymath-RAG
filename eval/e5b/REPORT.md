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

---

# E5B Part 2 — Routing Qualification (frozen evidence `evidence_p2.json`)

Date: 2026-08-16 | Base: `ba363ec` | Stack: full (Postgres/Qdrant/Neo4j/
Redis + embedder/GLiNER/reranker sidecars + orchestrator/control +
8 workers). I2 corpus re-ingested live: 28 + 4 isolation docs query_ready
(250s, p50 122.6s/doc).

## Harness validation

Baseline arm reproduced the frozen R1B numbers EXACTLY:
doc 0.882/0.912/0.912 MRR 0.910; sec 0.882/0.912/0.912 MRR 0.897.
(Discrepancy reported: the sha recorded in `eval/r1b/result.json` is a
stale hardcoded constant; the git-frozen queries file sha is
`0eadb8c51e…` and its content yields the frozen numbers.)

## IN_SUMMARY_TEXT

Present in `ba363ec`: YES — 6th ranking-tuple component (+1 when the
normalized concept occurs in the normalized summary concat). Used
exactly as committed; not altered.

## Results

| metric | baseline | candidate | delta |
|---|---|---|---|
| doc R@1 / R@3 / R@5 | 0.882 / 0.912 / 0.912 | 0.853 / 0.941 / 0.941 | −0.029 / +0.029 / +0.029 |
| doc MRR | 0.910 | 0.888 | −0.022 |
| sec R@1 / R@3 / R@5 | 0.882 / 0.912 / 0.912 | 0.853 / 0.941 / 0.941 | −0.029 / +0.029 / +0.029 |
| sec MRR | 0.897 | 0.882 | −0.015 |

Query deltas: doc improved 1 / unchanged 29 / regressed 4;
sec improved 1 / unchanged 31 / regressed 2. The two real regressions
are BOTH psychology: `p1_sectionled_2` (retrieval_practice.md 1→3 —
iso/memory_note.txt's concept list absorbs the literal query term
"calibration") and `p1_cross_1` (metacognitive_monitoring.md 2→3 —
working_memory.txt and the iso note outrank it). One psychology query
improved (`p1_paraphrase_5`, doc 6→3, sec 99→3).

R1A coverage A/B: 0.870 / 0.778 / 0.889 / redundancy 0.0 in BOTH arms
(+376 chars, +74% representation size) — no coverage improvement.

Psychology retention ranks (pre-budget deterministic order): admitted
ranks 1,2,4,5,7; budgeted-out ranks 21–45; `metacognitive control`
filtered at admission (rule-pack verb lemma), correcting part 1's
RANKED_OUT_BY_BUDGET label (part-1 evidence left intact; correction
noted here).

Safety: graph zero-delta ✓, extraction zero-delta ✓, Neo4j concept
nodes 0 ✓ (1711 nodes/1618 rels unchanged). Determinism ✓ (two runs
identical; point ids identical across rebuild). Performance: ~1 ms/doc
extraction over 64 inventories, embedding +64% batch wall time for the
+74% text, search latency unchanged (7–10 ms p50).

## Verdict

**REJECT.** The bounded concept inventory does not improve the
qualified routing representation: primary R@1 regresses by one query
(0.882 → 0.853) and the regressed queries are psychology — the domain
the lane exists to help. Coverage unchanged. Per the decision rule
("if routing does not improve or regresses: REJECT"), the E5B
representation fails qualification even though candidate extraction
itself works (part 1: 13/13 candidates vs GLiNER 2/13).

No tuning performed after observation (budget, ranking, guards,
dictionaries, serialization all frozen at `ba363ec`). Recorded E5C
hypotheses only: occurrence-count admission floor, summary-co-occurrence
gate, corpus-level frequency normalization, short-document budget
reduction.

NEXT: STOP. No production integration, no reruns.
