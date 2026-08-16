# I3 — Five-Document E2E Ingestion/Extraction Acceptance

Date: 2026-08-16
Base commit: `9000973` (E5 track closed; HEAD reconciled — no
subsequent architecture commits before this evaluation)
Verifier: `eval/i3_5doc/verify_i3.py`
Evidence: `eval/i3_5doc/evidence/evidence.json`
Corpus: `i3-five-doc-v1` (manifest `manifest_62574af466…`,
sha256 `2d69e5c69584d233fe7013264b88884e42312420347eec5211280e152164cfea`)

```
I3 FIVE-DOCUMENT E2E ACCEPTANCE: FAIL
```

## Corpus + gold (frozen before ingestion)

5 documents (cyber / psych / e-commerce / distributed systems /
warehouse transcript), exactly 3 paragraphs each; SHA256 in
`corpus/SHA256SUMS`. Gold authored and hashed BEFORE the first
ingestion (`gold/GOLD_SHA256SUMS`): 42 strict entity spans, 3
supported-predicate facts, 13 MUST-NOT-ASSERT fixtures, text-concept
sets + 10 frozen retrieval questions. No gold was modified after
observing results.

## Control plane — PASS

- Clean ingest: submitted 5 → 5/5 query_ready in 40s (1 transient
  `degraded` recovered by census).
- Stage chain: every run completed intake → extract →
  profile_document → project_qdrant → project_neo4j → canonicalize →
  project_canonical → verify_projections; no skipped stages, no
  duplicate stage attempts, receipts present, query_ready only after
  the full chain.
- Replay: 0 resubmitted, documents 5→5, facts 8→8, semantic hash
  equal. PASS.
- Order independence (reversed manifest): semantic hash equal. PASS.
- Concurrent ingestion (5 parallel intakes): semantic hash equal.
  PASS.
- Interrupt/resume (`POLYMATH_TEST_CRASH_AFTER_POINTS` fault
  injection): 1 injected failure, recovered 5/5, semantic hash equal.
  PASS.
- Versioning (one-sentence edit to doc 03): exactly 1 new document
  version, 4 unchanged, replay of changed content = no-op. PASS.
- Qdrant reconstruction (collection destroy + receipt
  supersede + census re-drive): converged, semantic hash equal on the
  re-run. PASS (first attempt recorded a transient mismatch — see
  defect D2).
- Neo4j reconstruction: converged, semantic hash equal. PASS.

## Entity extraction — measured, honest

Aggregate over the durable entity universe (see D1): P = 0.444,
R = 0.098, F1 = 0.160 (tp 4 / fp 4 / fn 37 / wrong_type 1).

GLiNER discovery itself is healthy (probe: 35 spans in doc 03 alone
with core labels at threshold 0.5). The recall gap is NOT a GLiNER
discovery miss: it is a durability design boundary (D1).

Error ownership: discovery 37 (gold spans never durable), typing 1
(`Manhattan Active Warehouse Management` canonicalized Organization;
gold allowed {Product, Technology}), admission 0, canonicalization 0.

## Fact extraction — FAIL (primary criterion)

P = 0.0 (8 false positives / 0 true positives / 3 false negatives).
All 3 gold facts missed (NO_ENDPOINT-class: subjects coreferent
("The gateway", "The company") or coordination-dependent).

The 8 accepted facts are noise from three failure classes, all of
which E3B targeted:

| class | example | root cause |
|---|---|---|
| noun false trigger | `uses(HarborPay, Authorization headers)` | trigger "application" (in "application logs") stemmed to the `use` verb family; surface-weak binding accepted a noun trigger the gate should reject |
| rule-pack trigger overreach | `founded(Summit Fulfillment, pilot)` | "start" ∈ founded verbs ("started its automation pilot"); object is a MENTION_ONLY generic |
| coordination pair explosion | 6× `associated_with` from one sentence ("installed robots in the Reno DC and connected the workflow to Manhattan") | every left entity paired with every right entity across the coordination boundary; the coordination-aware clause gate did not restrict binding |

Per the pass criteria — "No known E3B failure class may reappear" —
this gate FAILS. 4 of the 8 are Neo4j-eligible (all non-MENTION_ONLY
endpoints); 1 projected to the graph.

## Negative controls — 13/13 PASS (with caveat)

Every frozen MUST-NOT-ASSERT fixture passed individually (no
negation/modality/role-binding violation). Caveat: the 8 noise facts
are the same family of graph pollution the fixtures guard against;
the fixtures passed because none matched the exact prohibited
triples. Reported, not re-labeled.

## Generic graph hygiene — PASS (0 unexpected nodes, 0
mention-only projections)

`workflow` and `pilot` persisted as MENTION_ONLY and were correctly
parked (no Neo4j projection).

## Provenance — PASS at chunk granularity

8/8 facts: both endpoint surfaces present in the authoritative
evidence chunk text. Evidence spans record `chunk_char_start` only
(no end offset) — span-level exactness is not measurable under the
current contract; chunk-level traceability holds.

## Qdrant — PASS

15 chunk points + 20 routing points (5 doc summaries, 5 section
summaries, 10 routing children), all expected kinds present, 0
foreign points, 0 duplicate point ids within a collection.

## Neo4j — PASS at final state (defect D2)

4/4 eligible facts projected at final convergence, 0 orphans, 0
duplicates, 0 foreign facts, SPO direction preserved.

## Retrieval smoke — PASS

30/30 rows (10 frozen questions × FAST/HYBRID/GRAPH) rank the gold
document in the top 5; 26/30 at rank 1. GRAPH mode returns 1 graph
fact for the HarborPay-controls query and abstains from graph
evidence where the sparse graph has none (by design).

## Corpus isolation — PASS

0 foreign documents, chunks, facts, or citations with
`i3-five-doc-v1` authorization across FAST/HYBRID/GRAPH.

## Performance

- Total wall (first clean ingest): 40s for 5 docs (~7.5 docs/min).
- GLiNER entity pass per chunk: p50 measured inside stage attempts.
- Convergence after reconstruction: ~4-6 min (census re-drive).

## Defects (recorded, NOT repaired — per no-tuning rule)

- **D1 — entity durability boundary**: the production schema persists
  entities ONLY as fact endpoints (`_persist_decision`); every other
  GLiNER proposal is ephemeral. Discovered entities without an
  accepted fact never become canonical entities or mention rows. This
  is a design boundary, not a regression — but it makes the entity
  layer invisible to downstream recall and explains R=0.098.
- **D2 — projection/verification visibility race (transient)**:
  during the first reconstruction attempt and once during the initial
  ingest, `verify_projections` deleted freshly written Neo4j fact
  edges whose receipts had not yet committed (projector writes edges
  then receipts in separate transactions; verify reads both
  concurrently), leaving active receipts with missing edges until the
  next census cycle re-projected. Final states converged consistently
  (semantic hash equal), but the transient state is observable.
- **D3 — evidence span granularity**: `span_offsets` records only
  `chunk_char_start`; exact span-level provenance is not verifiable.
- **D4 — extract manifest placeholders**: the extract artifact
  manifest records `"gliner_model": "__PIN_MODEL__"` /
  `"gliner_revision": "__PIN_REVISION__"` (unresolved template
  literals) — documentation-level defect, no behavioral effect.

## Opportunity Control Plane Lock — PASS

I3 made zero changes to the authority boundary: no TrailSignal
authority inside Polymath, no adapter-owned durable database, no
third durable state machine, no opportunity-owned direct
Qdrant/Neo4j/MongoDB access, no speculative opportunity paths in
factual Neo4j. Polymath remains the durable knowledge/evidence
authority.

## Verdict

```
I3 FIVE-DOCUMENT E2E ACCEPTANCE: FAIL
```

FAILING GATE: fact precision — 8/8 accepted facts are noise
(P = 0.0) and three E3B-targeted failure classes reappeared on
realistic prose (noun false trigger, "start"→founded overreach,
coordination pair explosion). Control-plane, determinism,
reconstruction, retrieval, and isolation gates all pass. No repair
was performed and none is authorized by this plan.

NEXT: STOP. A repair phase (E3B binding gates for the observed
classes + the entity durability question) requires a separate
authorized gate.
