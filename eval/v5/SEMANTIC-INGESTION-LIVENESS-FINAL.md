# SEMANTIC INGESTION LIVENESS — CENSUS + INSTRUMENTATION (V1)

Date: 2026-08-28 · Branch `architecture/evidence-first-v5`

**Headline: all three semantic lanes are LIVE. None is broken. But
PROCEDURE captures 1.24% of its opportunities and CONCEPT 5.43%, and
both losses are ARCHITECTURAL CEILINGS, not discovery failures.**

The mission's framing was right: "12 procedures across 11 books" is not
evidence of a broken lane. It is evidence of a lane that emits **at most
one artifact per document**.

---

## REQUIRED OUTPUT

```
START_HEAD:  5d28188
FINAL_HEAD:  (this commit)
TREE_CLEAN:  YES

LIVE_CORPUS: cysa-study-v1  (purpose=production, query_enabled=true)
DOCUMENTS:   12
CHILDREN:    7,085
PARENTS:     1,774
runs:        12 query_ready / 0 non-ready
(also present: vocab-canary-v1, purpose=probe, query_enabled=false)

FACT_FUNNEL (durable, per-document census shows NO document at zero):
  entity observations (raw_entity_proposals): 101,281
  span hypotheses:                             95,964
  mentions:                                   107,506
  entity admission decisions:                 286,221
  relation candidates:                         13,085
  fact admission decisions:                    13,110
  facts accepted:                               3,184
  evidence rows:                                3,063
  projected (neo4j active receipts):           18,879
  retrievable:                                 YES (GRAPH returns facts)
FIRST_ZERO_BOUNDARY: NONE — every one of the 12 documents carries the
  full chain from observations through facts-with-evidence.

PROCEDURE_FUNNEL:
  opportunities (imperative step sentences):      965
  candidates:                                 UNOBSERVABLE (no candidate
                                              stage exists; the compiler
                                              is the detector)
  compiler_attempts:                              12  (once per document)
  accepted:                                       12
  rejected:                                        0
  artifacts:                                      12
  projected:                                      12 (routing_procedure)
  retrievable:                                   YES (ASK procedure lane)
FIRST_ZERO_BOUNDARY: NONE. Capture ratio 12/965 = 1.24%.

CONCEPT_FUNNEL:
  opportunities (definitional sentences):       2,210
  candidates:                                 UNOBSERVABLE (same shape)
  compiler_attempts:                               12
  accepted:                                       120
  artifacts:                                      120
  projected:                                      120+ (routing_concept)
  retrievable:                                   YES (ASK concept lane)
FIRST_ZERO_BOUNDARY: NONE. Capture ratio 120/2,210 = 5.43%, with the
  max_concepts=10 cap BINDING IN 12 OF 12 DOCUMENTS.

PROCEDURE_EXISTING_ARTIFACT_COUNT: 12

PROCEDURE_YIELD_VERDICT:
  NOT healthy-low-yield, NOT discovery-recall, NOT callsite-regression.
  ARCHITECTURAL GRANULARITY CEILING — compile_procedure returns
  `dict | None`, i.e. ONE artifact per document, so 12 documents can
  never produce more than 12 procedures regardless of content.

REAL_POSITIVE_TRACES:
  FACT:      PASS (funnel traced end-to-end on all 12 documents)
  PROCEDURE: PASS (12/12 documents converted; artifact -> projection ->
             ASK retrieval verified)
  CONCEPT:   PASS (12/12 documents converted, cap binding)

KNOWLEDGE_ROUTER_LOCAL_ELIGIBILITY: PASS
  `_persist_knowledge_artifacts` evaluates BOTH compilers unconditionally
  and records routing only as metadata ("always evaluated; the compiler
  self-gates"). `_evidence_spans` likewise keeps the deterministic
  trigger path alive when the router deprioritises a lane. The owner
  invariant holds: document profile never vetoes local evidence.

PRODUCTION_CALLSITE_PINS: PASS
MUTATION_TESTS: PASS (and the FIRST version of the pin was too weak —
  see below)

SEMANTIC_LIVENESS:
  FACT:      LIVE
  PROCEDURE: LIVE
  CONCEPT:   LIVE_BUT_CAPPED

SENTINEL: PARTIAL — see SCOPE
CHAOS_MATRIX: PASS (4 ingestion dead-lane classes + 4 correct-zero cases)
HEALTH_ENDPOINT: PASS — GET /health/semantic

FULL_REGRESSION: 1074 passed / 83 failed / 13 skipped, failure set
  BYTE-IDENTICAL to the pre-change baseline (zero regressions).

PRODUCTION_GO: YES (observability); the ceilings are an owner decision.
```

---

## THE CENTRAL FINDING

`procedure_artifacts = 12` is simultaneously:

- **12 of 12 documents** — 100% of documents produced an artifact, and
- **12 of 965 opportunities** — 1.24% of the procedural evidence.

Both are true. Only the second is informative, and nothing in the system
could express it before this work.

### Why: document-scope compilation

`compile_procedure(...) -> dict | None` runs once per DOCUMENT over the
whole document text. Every imperative sentence in a 900-page book is
collapsed into ONE artifact:

| document | steps in its single artifact | confidence |
|---|---|---|
| Python Crash Course | 172 | 1.00 |
| Microsoft Sentinel in Action | 150 | 1.00 |
| CySA+ Practice Tests | 136 | 1.00 |
| CySA+ Study Guide | 135 | 1.00 |

Sampled goals show the conflation directly:

> "Make sure those requirements and missions are included in the Orient phase…"
> "Open source Behavioral Reputational Indicator of compromise Jamal is assessing the risk…"

Confidence is `min(1.0, 0.6 + 0.05 * len(steps))`, which saturates at 8
steps — so every artifact reports 1.00 regardless of coherence.

### Concept: a hard cap, binding everywhere

`compile_concepts(..., max_concepts: int = 10)`. Every one of the 12
documents produced **exactly 10**. Uniformity across books of wildly
different size and density is the signature of a binding cap, not of
content. 2,210 definitional sentences were seen; 120 survived.

---

## THE TWO ZEROES, CLASSIFIED

**`raw_predicate_evidence = 0`** — `NO_OPPORTUNITY_OBSERVED (configured
mode)`, not a defect. `_evidence_spans` only fills `raw_sink` when
`mode == "hybrid"`; production runs the lexical/anchor proposal mode, and
the relation path is `POLYMATH_RELATION_PIPELINE=legacy_v1`. Relation
candidates (13,085) come from the anchor path, which is working. The L1
predicate ledger is simply not the active mechanism.

**`extraction_trace_events = 0`** — `OBSERVABILITY_INSUFFICIENT`. The
TraceLedger exists, `trace.record(...)` is called, and `trace.flush(conn)`
is invoked at extract_worker:1383 — yet no rows are durable. Worth a
follow-up; it is the richest per-decision ledger in the system and it is
currently empty. **Not repaired here** (out of mission scope, and it does
not affect the funnel measurements, which use durable tables).

---

## INSTRUMENTATION ADDED

Migration 0038 `knowledge_lane_attempts` — one row per (document, lane):
`opportunities`, `accepted`, `capped`, `disposition`
(`NO_OPPORTUNITY` | `ACCEPTED` | `GATED`), `bundle_hash`.

`count_opportunities()` added to both compilers. These are **diagnostic
only** and deliberately share the compilers' own helpers
(`split_step_sentences`/`_is_imperative`, `_DEFINE_PATTERNS`), so the
ratio can never drift from what production actually evaluates.

`semantic_lane_status()` distinguishes the states an artifact count
cannot:

| status | meaning |
|---|---|
| UNOBSERVABLE | no instrumentation — **not** a zero |
| NO_OPPORTUNITY | no evidence existed; correct silence |
| SUSPECT | evidence existed, nothing came out — the dead-lane signal |
| LIVE_BUT_CAPPED | working, but truncating recall by design |
| LIVE | working |

`GET /health/semantic` reports opportunity, accepted, capture ratio,
capped-document count and last attempt per lane, plus the FACT funnel.

### The pin had to be mutation-tested twice

The first callsite pin asserted `"count_opportunities" in body`. Deleting
the procedure counter left it **green**, because the concept counter still
matched. It now asserts both module-qualified calls, and the mutation
fails it. A pin that cannot fail is not a pin — which is the whole lesson
of this line of work.

---

## SCOPE — what this mission did NOT do

- **No sealed sentinel corpus with FACT/PROCEDURE/CONCEPT positives and
  negatives.** A real 2-document corpus (`vocab-canary-v1`) was pushed
  through the full public path earlier in the session, proving the
  ingestion route works end to end, but it was not designed with
  per-lane positive/negative cases. The chaos matrix covers the dead-lane
  classes at contract level instead. **This is the largest remaining
  gap.**
- **`extraction_trace_events` not repaired** (diagnosed only).
- **No thresholds touched.** No admission loosened, no cap changed, no
  compiler semantics altered — per the mission's boundaries.
- **Retrieval quality of the artifacts not assessed.** A 172-step
  "procedure" is a liveness pass and a quality failure; this mission
  measured the former.

---

## RECOMMENDATION (owner decision — semantic policy)

The lanes work. What they produce is coarse. Two changes would convert
low capture into real knowledge, and both change what qualifies as an
artifact, so neither was made here:

1. **Compile procedures at SECTION/parent scope rather than document
   scope.** The chunk hierarchy already provides the boundaries. This is
   the single highest-value change: it would turn 12 conflated artifacts
   into procedures that correspond to actual tasks.
2. **Make `max_concepts` scale with document size, or move concept
   compilation to section scope.** The cap binding in 12/12 documents
   means recall is being decided by a constant, not by content.

Neither should be done by raising a number in isolation — both need the
same opportunity-vs-capture measurement now available to verify the
result.

## REPRODUCTION

```bash
POLYMATH_PG_DSN=... .venv/bin/python scripts/semantic_lane_census.py \
    --corpus cysa-study-v1            # add --backfill to write telemetry

curl -s 'http://127.0.0.1:7200/health/semantic?corpus_id=cysa-study-v1'

.venv/bin/python -m pytest tests/determinism/test_semantic_lane_liveness.py -q
```
