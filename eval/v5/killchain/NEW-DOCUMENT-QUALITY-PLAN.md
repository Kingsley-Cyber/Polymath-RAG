# Validation plan — ingest one new document to measure real quality

Goal: prove the V2 contracts actually improve extraction and retrieval on a
document the system has never seen, **without** consuming the one production
rebuild.

Safe by construction: the new file goes into its **own corpus**
(`quality-probe-v1`), never `cysa-study-v1`. P14 remains untouched and still
rebuilds exactly once.

---

## Preconditions — 3 blockers, all measured just now

None of these are optional. Ingesting before fixing them produces a result that
looks like a quality verdict but isn't.

| # | blocker | measured state | why it invalidates the test |
|---|---|---|---|
| 1 | **Chunk V2 is not the ingest default** | `CHUNK_FROZEN_PARAMS` (`workers/workers/intake_worker.py:42`) has no `separator_mode`, so `plan_document` returns `chunk-structure-v1` | We would measure V2 procedures and concepts sitting on **V1 flattened chunks** — a mixed generation. Every P2/P6 gain would be invisible and the result would read as "the fixes didn't help" |
| 2 | **GLiNER sidecar down** (`:8740`) | `000` | Entity extraction cannot run *at all*. No mentions → no candidates → no facts. Also the reason 5 test files can't be collected |
| 3 | **Fleet BLOCKED** | 2 of 2 live workers quarantined, `BUNDLE_STALE_CODE_DRIFT` | Workers refuse every ticket by design. The ingest would hang with zero progress — exactly the stall P10 now makes visible |

Also down but **not** blockers: reranker `:8743` (affects retrieval ordering,
not extraction) and spaCy `:8744` (syntax lane; note its absence in the report
rather than blocking on it).

### Precondition fixes, in order

```
0a. wire Chunk V2 as the ingest contract
    CHUNK_FROZEN_PARAMS += separator_mode=SEPARATOR_SOURCE
    -> this is a P13 freeze decision made early, deliberately
    -> old corpora keep their stamped v1 contract; nothing re-identifies

0b. start GLiNER            :8740   (make dev-gliner)
0c. restart the worker fleet on current code
    -> clears BUNDLE_STALE_CODE_DRIFT
    -> verify: GET /health/pipeline == HEALTHY or IDLE, never BLOCKED
```

Gate before proceeding: `/health/pipeline` must not report BLOCKED, and
`test_source_recovery_key.py` + `test_runtime_config_contract.py` must be green.

---

## The document

What makes a good probe — ideally the file has several of these, and we record
which it actually exercises:

- prose with **hard line wraps** (the P6 defect)
- markdown **headings between sentences** (the P2 defect)
- at least one clean **affirmative SVO fact** (`X was developed by Y`)
- a **negated / hedged / attributed** statement that must NOT become a fact
- **two or more distinct procedures** (the P3 defect)
- more than ten **definitions** (the P4 ceiling)
- a **table**, a **code block**, a **nested list**
- named entities that also appear in `cysa-study-v1` (leakage probe)

A technical manual, runbook, or textbook chapter hits most of these. If the file
lacks a category, that category is simply reported as "not exercised" — we do
not synthesise content into it.

---

## A/B design — the only way to attribute the gain

Ingest the **same file twice**, into two corpora:

```
quality-probe-v1-legacy   chunk-structure-v1   (control)
quality-probe-v1          chunk-structure-v2   (treatment)
```

Everything else identical. Any difference is attributable to the chunk contract
and what it unblocks. Without the control this measures "does the pipeline
work", not "did the fixes help".

Cost: two ingests of one document. Cheap, and it is the difference between a
number and an attribution.

---

## What to measure, by boundary

Using the boundary doctrine — at each step: can valid information disappear, can
invalid information be created, can the same thing be produced twice, can it
fail while looking healthy?

| boundary | measure | expected under V2 |
|---|---|---|
| **A→B** source → chunk | contract stamp; newlines present; heading glued mid-text; literal coverage vs source | `chunk-structure-v2`; headings never glued; zero unexplained loss |
| **B→C** chunk → sentence | fragment rate (slices not ending in terminal punctuation) | near zero — the P6 soft-wrap fix |
| **C→D** → mentions | admitted entities by class; pronoun endpoints | pronouns `MENTION_ONLY`, never durable |
| **D→E** → candidates | `relation_candidates.decision` + reason distribution | clean affirmatives NOT rejected as `scope_gate: negated` |
| **E→F** → facts | accepted facts; hard negatives | affirmatives accepted; negated REJECT; hedged/attributed QUALIFY |
| **E→F** → artifacts | procedures per document; concepts per document | procedures ≈ one per task, not one per doc; concepts not pinned at exactly 10 |
| **F→G** → projections | PG vs Qdrant vs Neo4j counts | missing 0, orphan 0, foreign 0 |
| **G→H** retrieval | FAST / HYBRID / GRAPH over questions the document answers | answer-bearing chunk retrieved |
| **H→K** answer | citations resolve to chunks that contain the claim | every claim traceable; abstains when unsupported |
| **cross-cut** | corpus isolation | a `quality-probe-v1` query never returns `cysa-study-v1` evidence, and vice versa |
| **cross-cut** | health honesty | `/health/pipeline` tracks reality throughout; no silent stall |

---

## Pass / fail — judged by the release-blocker rule, not by pretty numbers

**Blocks release** (any one of these fails the probe):

- source loss: content in the file provably unreachable in every lane
- false knowledge: a negated or refuted statement stored as an accepted fact
- unsupported answer: a citation that does not contain the claim
- corpus leakage: probe evidence in a `cysa-study-v1` answer, or the reverse
- pipeline failure: a stage stops with no BLOCKED signal
- a stage reporting healthy while producing nothing

**Does NOT block release** — record and move on:

- V2 not beating V1 on some individual count
- imperfect ranking, or the answer-bearing chunk at rank 4 instead of 1
- concepts or procedures below what a human would extract
- exact-chunk recall short of 100% when another chunk carries the answer

That asymmetry is the point. We are qualifying correctness, not chasing metrics.

---

## Sequence

```
1. fix preconditions 0a-0c, confirm /health/pipeline not BLOCKED
2. create corpus quality-probe-v1-legacy, ingest the file (v1 control)
3. create corpus quality-probe-v1,        ingest the file (v2 treatment)
4. verify_ingestion on both — must report safe_claims + vector conservation
5. run the boundary table above, A/B, one report
6. run FAST / HYBRID / GRAPH against questions the document answers
7. write eval/v5/killchain/NEW-DOCUMENT-QUALITY-REPORT.md
8. delete both probe corpora, then re-check graph/vector delta = 0
   -> this doubles as the P9 deletion-lifecycle proof on a real corpus
```

Step 8 matters: it turns cleanup into evidence.

---

## What this does and does not prove

**Proves:** the V2 contracts work end to end on unseen input; extraction gains
are attributable to the chunk contract; retrieval reaches the evidence;
citations are honest; deletion prunes cleanly.

**Does not prove:** behaviour at 12-book scale, concurrency or ordering
invariance (P11, deferred), or crash recovery (P19, deferred). Those stay
deferred unless the rebuild surfaces them.

**Does not replace** P14. Production still rebuilds exactly once, from
`documents.source_hash`, after P13 freeze.
