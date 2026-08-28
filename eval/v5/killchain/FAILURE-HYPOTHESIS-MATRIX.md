# FAILURE HYPOTHESIS MATRIX (H1–H50)

Verdicts from the killchain audit against the LIVE corpus
(`cysa-study-v1`, 12 documents / 7,085 children) at HEAD `8cd25c3`.

`UNAUDITED` is used honestly where a hypothesis was not reached in this
pass — it is NOT a pass.

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Source fidelity loss | **FAIL (P2)** | 0 of 7,085 chunks contain a newline; code indentation, table rows, list hierarchy flattened by `" ".join` (chunker.py:72). Documented by the chunker itself; layout captured separately in `document_layout`. |
| H2 | Silent truncation | **FAIL (P2/P3)** | 245 caps registered. `MAX_ENTITIES=10` binds on 58.6% of parent summaries (1,771/3,021); `source_sentence[:300]` truncates 9 concept artifacts. |
| H3 | Coverage gaps / duplication | **PASS** | 7,073 inter-chunk gaps: 6,888 are 1–2 chars (separators), 116 are 5–9, max 70 (pandas table alignment). ZERO overlaps, ZERO duplicate chunk ids, all documents start at offset 0. |
| H4 | Document boundary failure | PASS (prior) | Cross-corpus content collision refused; duplicate-document guard verified earlier this session. |
| H5 | Chunking semantic damage | **FAIL (P2)** | Table header row and its data row land in DIFFERENT chunks with alignment destroyed (Python for Data Analysis, offset 468347). Same root cause as H1. |
| H6 | Hierarchy damage | PASS | 7,085 children + 1,774 parents reconcile; no order inversions. |
| H7 | Document-region false suppression | PASS | 13 adversarial negatives pinned; 96.0% body; objectives map protected by positive-content override. |
| H8 | Entity observation loss | UNAUDITED | — |
| H9 | Predicate / relation failure | UNAUDITED | — |
| H10 | Semantic router starvation | PASS | Both compilers evaluated unconditionally; routing recorded as metadata only. |
| H11 | Procedure representation ceiling | **FAIL (P2)** | 965 opportunities → 12 artifacts (1.24%); one artifact per DOCUMENT; 172-step conflated artifacts at confidence 1.00. |
| H12 | Concept representation ceiling | **FAIL (P2)** | 2,210 opportunities → 120 artifacts (5.43%); `max_concepts=10` binds in 12/12 documents. |
| H13 | Confidence saturation | **FAIL (P3)** | `min(1.0, 0.6 + 0.05*len(steps))` saturates at 8 steps — every procedure reports 1.00 regardless of coherence. |
| H14 | Dedup / canonicalization corruption | **FAIL (prior, P1)** | Vocabulary family layer merged EDR↔SIEM on co-occurrence; qualified NO-GO and left disabled. |
| H15 | Artifact lineage failure | PASS | All artifacts carry source_chunk_ids + bundle hash; no orphans found. |
| H16 | Summary corruption | PASS | Routing verified: both CySA books top-ranked with clear margin. |
| H17 | Embedding contract drift | PASS | Single contract `neural-embed-v1` across all corpora; projection pin-verified. |
| H18 | Representation payload drift | PASS | All 5 representation kinds reconcile exactly (delta 0). |
| H19 | PG/Qdrant/Neo4j divergence | **PARTIAL (P4)** | Qdrant EXACT (delta 0). Neo4j holds 12,428 Fact nodes vs 3,184 PG facts — stale nodes from deleted corpora. Contained (see H26). |
| H20 | Retrieval lane deadness | PASS | 9 lanes instrumented; chaos matrix + correct-zero cases. |
| H21 | Retrieval score / fusion pathology | PARTIAL | Boilerplate ranking fixed (region demotion); RRF flatness (~15% spread) noted, not exploited. |
| H22 | Exact literal lookup | UNAUDITED | — |
| H23 | Paraphrase lookup | PASS (prior) | Depth profile + neighbour expansion resolved the measured failure. |
| H24 | Cross-document completeness | PARTIAL | `max_documents` unchanged by depth profile (pinned); full multi-book enumeration not re-measured. |
| H25 | Depth over-trigger | PASS | 14-case intent matrix; over-trigger found and narrowed. |
| H26 | Graph failure | **PASS (P0 boundary held)** | 30 graph facts over 3 queries, **0 unauthorized** — stale Neo4j nodes CANNOT surface. |
| H27 | Query scope failure | PASS | Zero foreign `corpus_id` values in either Qdrant collection. |
| H28 | Reranker failure | PASS | Degrades to fusion order with typed `meta.degraded`; wake-wait verified. |
| H29 | Evidence assembly loss | **FAIL (fixed, P1)** | 900-char evidence surface vs 1,200-char chunks — fixed to 1,600 earlier this session. |
| H30 | Citation failure | UNAUDITED | — |
| H31 | Abstention failure | PASS | Negative control refuses and names what is missing. |
| H32 | Competing-model collapse | PASS | IR lifecycle answer preserved NIST (4-phase) AND PICERL separately. |
| H33 | Transcript failure | UNAUDITED | No transcript in the live corpus. |
| H34 | Table / code / structured text | **FAIL (P2)** | See H1/H5. ~23% of chunks carry structured content now flattened (360 table-like, 532 code-like, 792 numbered lists). |
| H35 | Scale-dependent semantics | **FAIL (found, contained)** | Vocabulary family count FELL as corpus grew (5→2); quadratic union-find. Qualified NO-GO. |
| H36 | Batch / concurrency nondeterminism | UNAUDITED | — |
| H37 | Crash / restart semantics | PARTIAL | Bundle fence observed working (workers quarantined on code drift). |
| H38 | Version / contract drift | PASS | Bundle fence + pinned plan versions. |
| H39 | Feature flag / environment drift | **FAIL (P3, found)** | `POLYMATH_EXTRACTION_TRACE` defaults off — an "expected" telemetry table was empty purely by configuration. |
| H40 | Health-check lies | PARTIAL | Sidecar readiness probes real `/ready`; deep inference capability not probed. |
| H41 | Control-plane starvation | **FAIL (fixed, P0)** | Reconcile livelock + dead rescue lane, both repaired earlier this session. |
| H42 | Observability lies | **RESOLVED (not a defect)** | `extraction_trace_events=0` is correct: trace mode defaults to "off". Earlier report corrected. |
| H43 | Tests that do not test | **FAIL (fixed)** | Two pins survived mutation and were strengthened (vocabulary callsite; semantic lane counters). |
| H44 | Duplicate evidence false corroboration | PASS (prior) | Support identity is the parent neighbourhood, not the summary row — proven necessary (1,241 parents carry 2 summaries). |
| H45 | Irrelevant data changes answer | UNAUDITED | — |
| H46 | Duplicate document amplification | PASS (prior) | Two-layer duplicate guard verified live. |
| H47 | Order dependence | UNAUDITED | — |
| H48 | Deletion / archive staleness | **FAIL (P4)** | Neo4j retains Fact/Entity nodes after corpus deletion (H19). Contained by authorization. |
| H49 | Future format unknown | PARTIAL | Materializer fails loud on unsupported formats; no typed PARTIAL-support signal for structure-lossy formats. |
| H50 | Good answer hides internal failure | PASS | Liveness evaluates component + callsite + opportunity + contribution, not just output. |

## Coverage

Audited with evidence: **38 of 50**. Unaudited: **8** (H8, H9, H22, H30,
H33, H36, H45, H47). Partial: **4**.

Unaudited hypotheses are listed as such deliberately — declaring them
PASS without measurement would be the exact failure mode this audit
exists to eliminate.
