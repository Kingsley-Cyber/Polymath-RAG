# FINAL KILLCHAIN REPORT

Date: 2026-08-28 · Branch `architecture/evidence-first-v5`

**Verdict: `PRODUCTION_GO: YES` for correctness and containment.
No P0 remains open. The dominant open risk is P2 — structured content
(code, tables, lists) is flattened, and PROCEDURE/CONCEPT capture is
limited by representational ceilings rather than by discovery.**

```
START_HEAD:  8cd25c3
FINAL_HEAD:  (this commit)
TREE_CLEAN:  YES

CORPORA_TESTED:    2  (cysa-study-v1 production, vocab-canary-v1 probe)
DOCUMENTS_TESTED:  14
CHUNKS_TESTED:     7,100 children + 1,779 parents

SOURCE_FIDELITY:            FAIL (P2 — structure, not content)
UNEXPLAINED_SOURCE_GAPS:    0
   7,073 inter-chunk gaps, ALL explained: 6,888 of 1-2 chars
   (separators), 116 of 5-9, max 70 (pandas table alignment).
   0 overlaps, 0 duplicate chunk ids, every document starts at 0.

SILENT_TRUNCATION_DEFECTS_FOUND: 3
SILENT_TRUNCATION_DEFECTS_FIXED: 1 (evidence 900 -> 1,600 chars, prior)
   remaining: MAX_ENTITIES=10 (binds 58.6%), source_sentence[:300] (9)

FACT:
  LIVE: YES
  OPPORTUNITY_CAPTURE: 3,184 facts / 13,085 relation candidates (24.3%)
  QUALITY_FINDINGS: no document at zero anywhere in the funnel

PROCEDURE:
  LIVE: YES
  OPPORTUNITIES: 965   ARTIFACTS: 12   CAPTURE: 1.24%
  GRANULARITY_VERDICT: DOCUMENT-SCOPE CEILING (one artifact per
    document; 172/150/135-step conflated artifacts, confidence 1.00)
  NEW_CONTRACT_IF_ANY: none — owner decision (see below)

CONCEPT:
  LIVE: YES (LIVE_BUT_CAPPED)
  OPPORTUNITIES: 2,210   ARTIFACTS: 120   CAPTURE: 5.43%
  GRANULARITY_VERDICT: HARD CAP max_concepts=10, binding 12/12 documents
  NEW_CONTRACT_IF_ANY: none — owner decision

ENTITY_FINDINGS:        UNAUDITED (H8)
RELATION_FINDINGS:      UNAUDITED (H9)
NEGATION_MODALITY:      UNAUDITED (H9)
TRANSCRIPT_FINDINGS:    UNAUDITED (no transcript in live corpus)
STRUCTURED_DATA_FINDINGS: FAIL — 0/7,085 chunks retain a newline;
  ~23% carry structured content (360 table-like, 532 code-like,
  792 flattened numbered lists). Table header and data rows separate
  into different chunks with alignment destroyed.

SUMMARY_FINDINGS:       PASS (routing verified, clear margin)
EMBEDDING_CONTRACT:     PASS (single neural-embed-v1, pin-verified)
QDRANT_RECONCILIATION:  PASS (delta 0 across all 5 representation kinds)
NEO4J_RECONCILIATION:   PARTIAL (12,428 Fact nodes vs 3,184 PG facts —
                        stale, contained by authorization)

FAST:               PASS
HYBRID:             PASS
GRAPH:              PASS (0 unauthorized facts over 30 returned)
RERANKER:           PASS (degrades typed, never silently)
EVIDENCE_ASSEMBLY:  PASS (after the 900-char repair)
CITATIONS:          UNAUDITED (H30)
ABSTENTION:         PASS

METAMORPHIC:        PARTIAL (M6/M7 prior; M3/M4/M5 unaudited)
FAULT_INJECTION:    PASS (chaos matrices: 8 retrieval + 4 semantic)
CRASH_RECOVERY:     PARTIAL (bundle fence observed working)
FRESH_SENTINEL:     NOT BUILT (see gap)
RECONSTRUCTION:     UNAUDITED

TESTS_MUTATION_VERIFIED: 3 (2 failed first and were strengthened)

NEW_BLIND_SPOTS_FOUND: 4
NEW_BLIND_SPOTS_FIXED: 4 (all as pinned gates)
  1. no gate on literal coverage gaps          -> pinned (<=128 chars)
  2. no gate on structure flattening           -> pinned
  3. no gate proving graph authorization holds -> pinned (P0 boundary)
  4. empty telemetry table explained by config -> pinned

P0_FINDINGS: 0 open  (control-plane livelock + dead rescue lane were
             P0 and were fixed earlier in this session)
P1_FINDINGS: 0 open  (evidence truncation fixed; vocabulary over-merge
             qualified NO-GO and left disabled)
P2_FINDINGS: 4 open  — structure flattening (H1/H5/H34), procedure
             ceiling (H11), concept ceiling (H12), MAX_ENTITIES=10
P3_FINDINGS: 2 open  — confidence saturation (H13), source_sentence[:300]
P4_FINDINGS: 1 open  — stale Neo4j nodes after deletion (H19/H48)

FULL_TEST_SUITE: 1,080 passed / 83 failed / 13 skipped — failure set
  BYTE-IDENTICAL to the pre-change baseline (zero regressions)

PRODUCTION_GO: YES
```

## The three findings that matter

**1. Structured content is flattened (P2, H1/H5/H34).** Zero of 7,085
chunks contain a newline. `_pack_sentences` joins sentences with a
space, so code indentation, markdown tables, list hierarchy and
transcript turns do not survive into the text that reaches evidence,
citations and the model. Measured consequence: in *Python for Data
Analysis*, a pandas table's header row and its data row land in
different chunks with 70 characters of alignment discarded between them.

This is **documented behaviour** — the chunker says so, and layout is
captured separately in `document_layout` for exactly this reason — but
its cost is not documented: for a corpus containing four code-heavy
books, "show me the code / read this table" is structurally degraded.

Repair is NOT free: chunk ids are content-addressed, so changing the
join re-identifies every chunk and invalidates every downstream
artifact. Source is retained on the spool (9.6 MB), so it is
recoverable — but it is a re-ingest, and therefore an owner decision.

**2. PROCEDURE and CONCEPT ceilings (P2, H11/H12).** Confirmed from the
prior mission and unchanged: procedures compile at DOCUMENT scope (one
artifact per document, 1.24% capture, 172-step conflations at confidence
1.00), and concepts are capped at 10/document with the cap binding in
every document (5.43% capture). Both lanes are LIVE; both are lossy by
construction.

**3. Graph divergence is real but contained (P4, H19/H26/H48).** Neo4j
holds 12,428 Fact nodes against 3,184 facts in Postgres — stale nodes
surviving corpus deletion. This would be P0 if it were answerable. It is
not: graph expansion is evidence-authorized and corpus-authorized, and
30 facts returned over 3 live queries contained **zero** unauthorized
results. The boundary is now pinned by a test, so if it ever breaks the
finding escalates to P0 automatically.

## Two corrections to earlier reports

Honesty about prior claims, since both were mine:

- **`extraction_trace_events = 0` is NOT an observability defect.**
  `POLYMATH_EXTRACTION_TRACE` defaults to `"off"`; `record()` no-ops and
  `flush()` correctly writes nothing. Previously reported as
  OBSERVABILITY_INSUFFICIENT. It is REJECTED_BY_DESIGN.
- **The Neo4j divergence was initially suspected as dangerous.** Testing
  the authorization boundary downgraded it from P0 to P4. Measurement,
  not intuition, decided it.

## Unresolved owner decisions

1. **Structured-text fidelity** — accept flattening, or re-chunk with
   structure preservation (invalidates all chunk ids; requires
   re-ingest from the retained spool).
2. **Procedure granularity** — document scope vs section/neighbourhood
   scope. Recommended: section scope, since the chunk hierarchy already
   provides boundaries.
3. **Concept granularity** — `max_concepts=10` as durable-knowledge cap
   vs presentation cap.

## Honest coverage statement

**38 of 50 hypotheses audited with evidence; 8 unaudited; 4 partial.**

Unaudited: H8 (entity offsets), H9 (relation/negation/modality), H22
(exact literal lookup), H30 (citation resolution), H33 (transcript),
H36 (batch/concurrency invariance), H45 (irrelevant-data metamorphic),
H47 (order dependence). A sealed fresh-ingest sentinel (Phase 13) was
NOT built.

These are recorded as UNAUDITED rather than PASS. Marking an unmeasured
hypothesis green would be precisely the failure class this whole audit
exists to eliminate.
