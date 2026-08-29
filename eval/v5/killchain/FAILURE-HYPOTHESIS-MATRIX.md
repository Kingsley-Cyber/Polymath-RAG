# FAILURE HYPOTHESIS MATRIX (H1–H50)

Verdicts from the killchain audit against the LIVE corpus
(`cysa-study-v1`, 12 documents / 7,085 children) at HEAD `8cd25c3`.

`UNAUDITED` is used honestly where a hypothesis was not reached in this
pass — it is NOT a pass.

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Source fidelity loss | **FAIL (P1, escalated pass 3)** | 0 of 7,085 chunks contain a newline; code indentation, table rows, list hierarchy flattened by `" ".join` (chunker.py:72). Documented by the chunker itself; layout captured separately in `document_layout`. |
| H2 | Silent truncation | **FAIL (P2/P3)** | 245 caps registered. `MAX_ENTITIES=10` binds on 58.6% of parent summaries (1,771/3,021); `source_sentence[:300]` truncates 9 concept artifacts. |
| H3 | Coverage gaps / duplication | **PASS** | 7,073 inter-chunk gaps: 6,888 are 1–2 chars (separators), 116 are 5–9, max 70 (pandas table alignment). ZERO overlaps, ZERO duplicate chunk ids, all documents start at offset 0. |
| H4 | Document boundary failure | PASS (prior) | Cross-corpus content collision refused; duplicate-document guard verified earlier this session. |
| H5 | Chunking semantic damage | **FAIL (P2)** | Table header row and its data row land in DIFFERENT chunks with alignment destroyed (Python for Data Analysis, offset 468347). Same root cause as H1. |
| H6 | Hierarchy damage | PASS | 7,085 children + 1,774 parents reconcile; no order inversions. |
| H7 | Document-region false suppression | PASS | 13 adversarial negatives pinned; 96.0% body; objectives map protected by positive-content override. |
| H8 | Entity observation loss | **PASS + FINDING (P2)** | offsets 100% exact (20,000 sampled); punctuated identifiers intact; 15.33% of surfaces map to multiple entity_ids (`you` -> 747). Pass 2. |
| H9 | Predicate / relation failure | **FAIL (P1)** | 557/3,184 facts (17.5%) carry a pronoun endpoint: `you --instance_of--> microsoft`. 7 reached Neo4j; MERGE created the endpoints, so edges are answerable. Pass 2. |
| H10 | Semantic router starvation | PASS | Both compilers evaluated unconditionally; routing recorded as metadata only. |
| H11 | Procedure representation ceiling | **FAIL (P2)** | 965 opportunities → 12 artifacts (1.24%); one artifact per DOCUMENT; 172-step conflated artifacts at confidence 1.00. |
| H12 | Concept representation ceiling | **FAIL (P2)** | 2,210 opportunities → 120 artifacts (5.43%); `max_concepts=10` binds in 12/12 documents. |
| H13 | Confidence saturation | **FAIL (P3, confirmed on data)** | confidence is a CONSTANT: all 12 procedures exactly 1.00 (8..172 steps), all 121 concepts exactly 0.90. Pass 2. |
| H14 | Dedup / canonicalization corruption | **FAIL (prior, P1)** | Vocabulary family layer merged EDR↔SIEM on co-occurrence; qualified NO-GO and left disabled. |
| H15 | Artifact lineage failure | PASS | All artifacts carry source_chunk_ids + bundle hash; no orphans found. |
| H16 | Summary corruption | PASS | Routing verified: both CySA books top-ranked with clear margin. |
| H17 | Embedding contract drift | PASS | Single contract `neural-embed-v1` across all corpora; projection pin-verified. |
| H18 | Representation payload drift | PASS | All 5 representation kinds reconcile exactly (delta 0). |
| H19 | PG/Qdrant/Neo4j divergence | **PARTIAL (P4)** | Qdrant EXACT (delta 0). Neo4j holds 12,428 Fact nodes vs 3,184 PG facts — stale nodes from deleted corpora. Contained (see H26). |
| H20 | Retrieval lane deadness | PASS | 9 lanes instrumented; chaos matrix + correct-zero cases. |
| H21 | Retrieval score / fusion pathology | PARTIAL | Boilerplate ranking fixed (region demotion); RRF flatness (~15% spread) noted, not exploited. |
| H22 | Exact literal lookup | **PASS** | `ATT&CK`, `802.11`, `Windows NT 10.0` retrieve chunks containing the literal. Pass 2. |
| H23 | Paraphrase lookup | PASS (prior) | Depth profile + neighbour expansion resolved the measured failure. |
| H24 | Cross-document completeness | PARTIAL | `max_documents` unchanged by depth profile (pinned); full multi-book enumeration not re-measured. |
| H25 | Depth over-trigger | PASS | 14-case intent matrix; over-trigger found and narrowed. |
| H26 | Graph failure | **PASS (P0 boundary held)** | 30 graph facts over 3 queries, **0 unauthorized** — stale Neo4j nodes CANNOT surface. |
| H27 | Query scope failure | PASS | Zero foreign `corpus_id` values in either Qdrant collection. |
| H28 | Reranker failure | PASS | Degrades to fusion order with typed `meta.degraded`; wake-wait verified. |
| H29 | Evidence assembly loss | **FAIL (fixed, P1)** | 900-char evidence surface vs 1,200-char chunks — fixed to 1,600 earlier this session. |
| H30 | Citation failure | **PASS** | 10/10 locators resolved to authoritative chunks in the correct corpus; no chunk id spans corpora. Pass 2. |
| H31 | Abstention failure | PASS | Negative control refuses and names what is missing. |
| H32 | Competing-model collapse | PASS | IR lifecycle answer preserved NIST (4-phase) AND PICERL separately. |
| H33 | Transcript failure | **PASS (structural)** | sentinel transcript ingested via the real path; speaker turns, disfluency, ambiguous acronym and exact identifiers survive into chunk text; no parallel truth system. Pass 3. |
| H34 | Table / code / structured text | **FAIL (P1, escalated pass 3)** | See H1/H5. ~23% of chunks carry structured content now flattened (360 table-like, 532 code-like, 792 numbered lists). |
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
| H45 | Irrelevant data changes answer | **PARTIAL** | corpus-scoped collections make cross-corpus interference structurally impossible (H27 PASS); same-corpus dilution untested. Pass 3. |
| H46 | Duplicate document amplification | PASS (prior) | Two-layer duplicate guard verified live. |
| H47 | Order dependence | **NOT TESTABLE AS DESIGNED** | identical content cannot exist in two corpora — CROSS_CORPUS_CONTENT_COLLISION refused sentinel-b. The duplicate guard blocks the standard experiment. Pass 3. |
| H48 | Deletion / archive staleness | **FAIL (P4)** | Neo4j retains Fact/Entity nodes after corpus deletion (H19). Contained by authorization. |
| H49 | Future format unknown | PARTIAL | Materializer fails loud on unsupported formats; no typed PARTIAL-support signal for structure-lossy formats. |
| H50 | Good answer hides internal failure | PASS | Liveness evaluates component + callsite + opportunity + contribution, not just output. |

## Coverage

Audited with evidence: **45 of 50** (pass 1: 38, pass 2: +5, pass 3: +2).
Unaudited: **1** (H36 batch/concurrency invariance).
Not testable as designed: **1** (H47 — blocked by the duplicate guard).
Partial: **5**.

**Pass 3 escalated H1/H34 from P2 to P1**: line flattening was proven to
CAUSALLY SUPPRESS concept extraction, not merely misrepresent structure.

Unaudited hypotheses are listed as such deliberately — declaring them
PASS without measurement would be the exact failure mode this audit
exists to eliminate.
