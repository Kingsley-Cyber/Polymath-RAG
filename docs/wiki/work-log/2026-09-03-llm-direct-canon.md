---
change_id: LLM-DIRECT-CANON (P0–P3, P5; P4 partial)
owner: governance
date: 2026-09-03
status: in progress — phase receipts below
architecture_impact: LLM-direct extraction declared canon (ADR-0017); tiered endpoint attestation replaces the anchor-chunk veto; open vocabulary projected to the graph; replay and grading re-based on the raw-response ledger and gold questions
last_reviewed: 2026-09-03
---

# WORK LOG — LLM-DIRECT-CANON: the LLM extractor stops living inside the GLiNER pipeline's shape

## Contract
Owner (2026-09-03): the repo was refactored from GLiNER + spaCy (Python-derived
facts for graph queries) to LLM extraction, but "it still affects how this
RAG works: it is being graded on that and made to adhere to the original
style. Write the plan, investigate the code path, use the graphify graph to
confirm dependencies, and fix it so LLM-direct is declared canon."
Plan of record: `docs/wiki/plans/LLM-DIRECT-CANON-PLAN.md`; decision:
`docs/wiki/decisions/0017-llm-direct-canon.md`.

## Investigation (what still enforced the tagger's rules, with numbers)
Last 20 extracted documents: 1,779 relations and 952 entities rejected by
attestation gates (UNATTESTED_ENTITY 825, UNATTESTED_RELATION_ENDPOINT 787,
NON_TERM_ENDPOINT 502, UNATTESTED_RELATION_QUOTE 470); 46 % of proposed
relations reached the facts table. 2,415 of 2,680 type coercions flattened
to Concept (17,222 Concept entities, the largest class). EXACT_REPLAY needed
a sentence-slice manifest (0 rows exist); retrieval validation graded fact
tuples; the fact admission chain rejected 147/148 LLM facts when enforced;
`extraction_provider` defaulted to `gliner`; CLAUDE.md prescribed spaCy /
rescue / rule-pack knobs for hand-started processes. graphify (14,729-node
graph, BFS depth 2, re-checked with grep) confirmed the dependency shape:
`gate.py:validate_and_normalize` is called only from `llm_provider.py:630`
and `llm_direct.materialize` is the only fact writer; nothing on the query
path imports the tagger modules; the only consumers of `facts.decision`
and `entities.core_type` are eligibility → Neo4j projection → graph
expansion, canonicalization and identity.

## Changes
1. **P0 canon.** ADR-0017; `RAG-ARCHITECTURE-V2.md` extraction-canon section
   (GLiNER + spaCy → history); CLAUDE.md law: the fleet `.env` is the only
   execution contract, the tagger knobs must not be set; `settings.extraction_provider`
   default `llm_live`.
2. **P1 ATTESTATION-LEVELS-V1** (`llm_extraction/gate.py`): a relation
   endpoint's attestation is a recorded level — quote › anchor ›
   neighborhood › document › abstract (every content token of the surface
   present in the anchor chunk); no support at all stays
   UNATTESTED_RELATION_ENDPOINT (invention). Junk surfaces, unattested quotes
   and interrogatives remain hard gates. `POLYMATH_EXTRACTION_ATTESTATION=strict`
   restores the pre-canon quote/anchor rule (rollback). Levels are counted in
   `merged.stats.endpoint_attestation`, carried on each evidence dict, stored
   in `evidence.span_offsets.endpoint_attestation` and `facts.provenance`
   (`gate_version = attestation-levels-v1`). `llm_direct.materialize` now
   types an unplaced endpoint by the normalized surface of a placed entity,
   else Concept — the old fallback routed the SURFACE through the TYPE
   mapper (`map_core_type(subj_s)`).
3. **P2 OPEN-VOCAB-SURFACED** (`project_neo4j_worker.py`): Entity nodes carry
   `raw_types` and `display_type` (most specific raw type when it differs
   from the core index type); REL edges carry `predicate_raw`.
4. **P3 LLM-DIRECT-REPLAY-V1** (`eval/v5/replay_llm_direct.py`): raw-response
   ledger (`extraction_call_receipts.raw_text`) → sanitize → gate →
   materialize against a capturing connection → fact-id set vs production;
   `--record-evidence` writes the EXACT_REPLAY evidence naming the gate
   version. <<REPLAY>>
5. **P4 retirement (partial).** `test_sval_doc01_red.py` skip-marked
   (historical candidate/role-binding path). Fence already path-aware
   (FENCE-PATH-AWARE-V1). Remaining: move `retrieval_validation.py`,
   `replay_full.py`, `shadow_settlement.py` to `eval/historical/`; guard
   `syntax_readiness` / `rescue` behind the gliner provider; runtime-budget
   entries marked historical (owner decisions on deletion pending).
6. **P5 grading** (`eval/v5/holdout/`): answer-level grader over `/chat`
   (expected document cited + required phrase present, abstention
   correctness, zero-tolerance counters: foreign-corpus citations, answers
   without citations, errors); a DEVELOPMENT seed set of 10 questions; the
   sealed set is owner-supplied and only a sealed run (hash-bound) writes
   `release_evidence/sealed_holdout.json`. First dev run: see Proof.

## Proof
- tests/determinism/test_attestation_levels.py 6 green (levels ordered and
  pure; cross-chunk endpoint kept with its level recorded; abstract needs
  token support, invention still rejected; strict policy restores the old
  rule; hard gates unchanged; materializer/projector carry the vocabulary);
  test_llm_extraction, test_term_surface_gate, test_llm_direct_pronoun_gate,
  test_neo4j_eligibility, integration test_llm_direct_facts: 42 green.
- CANARY (pre-registered targets in the plan: relation survival ≥ 70 %,
  junk in accepted = 0, abstract ≤ 25 %, sampled precision ≥ 18/20):
  Learning SQL (111 KB, child-chunk
  reconstruction of the book already in ecom-meta-v1, uploaded with a nonce
  to `probe-canon-2026-09-03`, run_0fdf6d77…), 144 children / 19
  neighborhoods, cloud lane mistral-small-2603 (the fleet's cloud floor is
  `POLYMATH_WORKER_CLOUD_MIN_BYTES=0`, so every document goes cloud now; the
  08-30 baseline of the same book ran local Qwen3.5-4B under a 450 KB floor
  — the model differs, so the clean gate-only comparison is the replay A/B
  below). Gate: 130 relations kept / 29 rejected (UNATTESTED_ENTITY 29,
  UNATTESTED_RELATION_QUOTE 28, NON_TERM 3, UNATTESTED_RELATION_ENDPOINT 0);
  endpoint levels quote 150 / anchor 69 / neighborhood 31 / document 1 /
  abstract 9 → survival among non-junk proposals 130/158 = 82 % (baseline
  54/103 = 52 %); abstract share 3 % (target ≤ 25 %); junk in accepted 0;
  128 facts written. Inspection of 20 sampled relations with an endpoint
  beyond the anchor chunk: 17/20 correct; the 3 misses are the model's
  predicate choice/direction (PRODUCES for "belongs to", CONSTRAINED_BY
  reversed), every sampled endpoint was a real term the sentence is about —
  the attestation level itself was right 20/20. Target ≥ 18/20 on the strict
  reading: MISSED BY ONE, on a dimension this change does not touch.
- Replay receipt: <<REPLAY-RECEIPT>>
- Dev holdout (not release evidence): 10 dev questions, HYBRID chat: supported 6, wrong 0,
  unexplained 4, zero-tolerance clean (0 foreign citations, 0 answers
  without citations, 0 errors), p50 2.6 s. The four unexplained are the
  finding: `sql-01` (inner vs outer join, Learning SQL), `aws-01` (shared
  responsibility model, AWS book) and `cysa-01` (scan vs pentest) all
  ABSTAINED on answerable questions — the answerability gate, not
  retrieval (the expected documents lead the FAST/HYBRID panels); `bo-01`
  cited Blue Ocean but the grader's required phrases were too narrow.
  Development numbers only; the sealed set is the owner's.

## Rejected claims
- "The type flattening is a data-loss bug." `entities.raw_types` already
  kept the open vocabulary as a set union; the loss was in projection and
  display, fixed by P2, not in identity (which stays core + surface).
- "Drop attestation." A quote absent from the document is invention; the
  quote gate stays. Only the anchor-chunk locality rule went.
- "Grade with the quick model grade." It runs the production gate on
  single-chunk neighborhoods, so it cannot see cross-chunk levels and its
  grounding metric is defined by the very rejections this change removes.

## Open contract gaps
- Pre-existing failures outside this slice, now classified: CHUNK-GAP
  (`test_child_spans_have_no_large_unexplained_gaps`: a 522-char gap
  between children — a chunker defect, not tagger history) and
  `test_batched_client_sizes_calls_from_the_budget` (batched-client test
  double out of date).
- Census promotion (`missing_chunk_receipts_for_run`) is still corpus-scoped.
- Owner decisions: P6 re-extraction of ecom-meta-v1 + cysa-study-v1 under the
  new gate; delete vs skip historical tests; retire the apple-ml LaunchAgent.
