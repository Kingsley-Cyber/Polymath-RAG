---
change_id: smoke-admission-e2e-fail
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (no production change; gate FAILED under hard-stop)
---

# Live entity-admission E2E smoke gate — FAIL (hard stop, no patch)

## Contract

Run the realistic metacognition document through the full production
path (intake → extract → admission v1.1 → identity v2 → compiler →
Postgres → canonicalization → Qdrant → Neo4j → bidirectional hop1 →
G3 reranker → EvidenceBundle → grounded answer) as a smoke gate, with
frozen baseline (GLiNER medium-v2.1 @ 40ec4193, admission v1.1,
rule pack 1.0.1, lexical-only compiler, G3 ON, hop2 rejected, no span
repair). No tuning, no patching. Record defects and stop.

Input: `tests/fixtures/smoke/metacognition_excerpt_test.md` (sha256
`4ba7ee1675b4d58a6a8f69d1041dc0978dd36ea2e6a6da8a0e38e1cf140dbea5`),
corpus `smoke-admission-2026-08-15`, run
`run_3f1febc37be39528eae66a0896765c06ac60a1fb1b79ad2597d2c8b50241f7d6`.

## Changes

- `tests/fixtures/smoke/metacognition_excerpt_test.md` (test-ingest
  fixture, content identical to the provided document; TREE-declared).
- Evidence frozen at `/tmp/polymath-smoke/evidence.json` (span-level
  census + defect records). No production file modified.

## Proof / Results

- Pipeline stages all executed `ok` through the real stack (live GLiNER
  sidecar, pinned model verified via manifest) with real census.
- Admission behavior verified correct at the graph boundary:
  MENTION_ONLY entities (learner ×2) never projected; 0 mention-node
  leakage; 0 edges for the smoke corpus (both facts parked in
  Postgres); no new `system` hub created (GLiNER never proposed
  `system` in this document).
- Span-level census over 41 accepted GLiNER spans: GLOBAL=5,
  CORPUS_SCOPED=11, DOCUMENT_SCOPED=0, MENTION_ONLY=25.
- Admission wiring proven extraction-neutral: old (41bbaed) vs new
  build_candidates produce identical candidates (233) and identical
  chunk-level accepted facts (26) on identical inputs.

## Defects (recorded, NOT patched)

1. **D1 — census non-convergence on parked facts.** Owning layer:
   `control/control/census.py` `_missing_projection_receipts`
   (project_neo4j branch) + `workers/workers/verify_worker.py`
   reconcile_neo4j `missing_facts`. The admission-filtered projector
   legitimately skips facts with MENTION_ONLY endpoints
   (`fact_2ade95ee…`, `fact_bb7b639c…`, both `Metacognition
   associated_with learner` in `chunk_567d6206…` of
   `doc_4ba7ee16…`), but the receipt census still expects active
   neo4j receipts for every fact with evidence. Result: infinite
   re-drive loop, run stuck `reconciling`, never `query_ready`.
   Blast radius is corpus-wide (legacy corpora with generic-hub facts
   — gate1–7, g2-*, cd-*, admission-* — are also stuck reconciling
   under the same mechanism).
2. **D2 — graph-lane cross-corpus leak.** Owning layer:
   `orchestrator/orchestrator/api/retrieve.py` `_neo4j_expand` seed
   MATCH has no corpus scoping. With corpus_id pinned to the smoke
   corpus, the vague query `How does the system work?` and Q2 answered
   from the legacy `g4_e2e` corpus (`component NxM … the worker
   pool`), 20 citations each pointing at another corpus. Pre-existing
   seed-matching behavior (the rejected G4.2 area), surfaced by the
   gate's citation-grounding requirement.

Observation (not a defect): the document yields only 2 accepted facts
under the frozen per-sentence lexical compiler; queries 1/3/4/5
abstained with 0 citations. Also: title-case `Metacognitive
Monitoring` classifies GLOBAL while lowercase `metacognitive
monitoring` classifies CORPUS_SCOPED (case-sensitivity of the
proper-name signal).

## Rejected claims

- No extraction or admission defect: admission decisions matched
  policy intent at the graph boundary; identity allocation behaved
  exactly as unit-tested.
- Replay, Neo4j reconstruction, and determinism hashes NOT RUN (hard
  stop on first requirement failure). Listed as not-run in the frozen
  evidence.

## Open contract gaps

- Receipt census must learn about parked facts (D1).
- Graph expansion seed resolution must be corpus-scoped (D2).
- Both are out of scope for this gate; next authorized work is to
  decide fix order with the user, not to patch unilaterally.
