---
change_id: LLM-DIRECT-CANON (P0–P3, P5; P4 partial)
owner: governance
date: 2026-09-03
status: P0–P6 (P6 launched 2026-09-03 — receipts below); owner findings resolved
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
   version. RECEIPT-COMPLETENESS-V1 came out of building it: on
   canary 1 only 9 of 14 responses had been receipted — reissue calls
   bypassed the ledger on both the write and the read side — so a ledger
   replay could cover 14 of 19 neighborhoods (`_reissue` now goes through
   the receipt-aware `_call` wrapper: reissues are read from and written
   to the ledger like first-pass calls). Canary 2 then stored 14/14
   receipts, but the replay still diverged (extra 47 / missing 9): the
   disposition rules read `finish_reason` ("length" = truncated call →
   split, last item re-issued) and the ledger did not carry it; the
   artifact's per-call `raw_head` match is an unreliable bridge (identical
   200-char prefixes). Migration 0048 adds `finish_reason` to the receipt
   ledger; the writer, the provider's cache seam and
   `LLMExtractionClient.extract_from_raw` carry it both ways. The replay
   harness drives `run_proposals` itself (same batching, alias maps,
   splits, dispositions), answers every call from the ledger, forbids
   the network, and decodes any missed batch by the provider's own key
   rule. Local-lane documents go through `extract_batched`, which has no
   cache seam — not replayable yet (declared).
5. **P4 retirement (owner 2026-09-03: "retire 3, delete 2").**
   - `com.polymath.apple-ml` LaunchAgent booted out and disabled (it served
     the sibling stack's embed :8082 / rerank :8081 / arbiter :8085; its
     GLiNER :8740 and spaCy :8744 were already dead; nothing in v4 uses any
     of them — the v4 sidecars are supervised slots on :8742/:8743 and the
     local batched lane on :8755 is a separate process). Plist kept;
     rollback = `launchctl enable gui/501/com.polymath.apple-ml &&
     launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.polymath.apple-ml.plist`.
   - 29 test files deleted — every file whose subject is the retired
     rule-pack / syntax-interpreter / GLiNER-rescue path (docstrings and
     imports checked one by one): sval_doc01_red, kimi_candidates,
     kimi_v2_candidates, kimi_role_direction, syntax_batching,
     syntax_readiness_v3, i3r_r1/r2/r3, i4r_a/b/c/d, q1r_v110_revision,
     spoken_relation_adapter, compiler, fact_scope_recall,
     category_d_followup, discourse_bridge, span_hypotheses,
     reference_completion, lexical_semantic_evidence, scientific_predicates,
     predicate_compiler_v2 (determinism); syntax_provider_gate,
     trigger_compilation, lexical_resource_gates, phase_h_harness
     (contracts); spacy_syntax_sidecar (integration). KEPT on purpose:
     admission/identity tests (entity_admission, fact_admission,
     admission_interpreter_s4, s4b, subtoken_span_admission,
     admission_projection — the identity boundary canonicalization still
     uses), execution_bundle, extraction_observability, batched_pass1 and
     the sidecar/supervisor tests (current infrastructure), killchain
     (mixed, holds the CHUNK-GAP defect), latent_rescue (the latent layer,
     not GLiNER rescue), layout_and_slice_evidence (layout evidence is
     current), query_policy (the core-type ontology the gate maps into),
     and the `tests/historical_boundary.py` pin helper (still used by two
     kept files).
   - `replay_full.py`, `shadow_settlement.py`, `retrieval_validation.py`
     moved to `eval/historical/` with a README; the rescue lane was
     already unreachable under llm_live (`rescue_stages = ()`); the two
     sidecars stay in `runtime_budget.yaml` as caps only.
   - NOT deleted (next step, owner call): the retired CODE itself —
     `workers/candidates.py`, `kimi_*`, `syntax.py`, `rescue.py`,
     `polymath_shared/rulepack/`, `syntax_readiness.py`,
     `sidecars/{spacy,gliner}_runtime` — still imported by the
     `extraction_provider=gliner` branch of `extract_worker.py`.
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
- Replay receipt: canary 3 (same book, fresh nonce, first document
  whose ledger carries `finish_reason`): 13 calls (6 reissues, 2 truncated,
  1 salvaged), 13/13 receipts with finish_reason; replay through
  `run_proposals` from the ledger, 15 cache hits / 0 misses, dispositions
  reproduced (returned 13, reissued 4, incomplete_kept 2) → **IDENTICAL:
  103 replayed = 103 production facts, extra 0, missing 0**
  (`release_evidence/exact_replay.json`, gate EXACT_REPLAY PASS). The SAME
  stored responses re-gated under `strict` (the pre-canon anchor-chunk rule)
  yield 79 relations / 76 facts — 27 facts (26 %) of what the LLM correctly
  proposed would have been discarded; the tiered levels on this document:
  quote 134 / anchor 47 / neighborhood 15 / document 2 / abstract 14.
- Dev holdout (not release evidence): 10 dev questions, HYBRID chat: supported 6, wrong 0,
  unexplained 4, zero-tolerance clean (0 foreign citations, 0 answers
  without citations, 0 errors), p50 2.6 s. The four unexplained are the
  finding: `sql-01` (inner vs outer join, Learning SQL), `aws-01` (shared
  responsibility model, AWS book) and `cysa-01` (scan vs pentest) all
  ABSTAINED on answerable questions — the answerability gate, not
  retrieval (the expected documents lead the FAST/HYBRID panels); `bo-01`
  cited Blue Ocean but the grader's required phrases were too narrow.
  Development numbers only; the sealed set is the owner's.

## Round 2 (owner 2026-09-03: "I agree with all 3 decisions, fix the chunker bug, and your findings need to be resolved")
1. **P6 re-extraction is now a real mechanism.** `reingest_corpus.py` re-arms
   intake and lets contract drift decide which stages regenerate; the
   extract stage's contract (`contract_identity()`) did not contain the
   gate, so a gate change would have CARRIED the old extraction. The
   identity now carries `gate = {version, attestation_policy}` — a gate
   change is a contract change. Receipt keys derive from the identity, so
   every receipt records `contract_ident` (migration 0049; 88 receipts
   keyed under the pre-change identity were stamped by reproducing their
   keys) and the ledger replay translates a window to the key of the era
   the document was extracted in. <<P6>>
2. **CHUNK-GAP-ACCOUNTING-V1 (the chunker bug).** The killchain fidelity
   check (`test_child_spans_have_no_large_unexplained_gaps`) failed on a
   522-char gap. Forensics from the spool: the gaps are title pages, part
   dividers and heading lines that the tier chunker (`tier_v3`) drops by
   the v3.3 doctrine (sub-stub sections under 15 body words; heading lines
   never enter child text) — recorded NOWHERE, so doctrine and data loss
   were indistinguishable (Innovator's Dilemma had 0 `document_layout`
   rows; the tier path never persisted layout at all). Fix:
   `tier_chunk_layout()` returns rows + layout evidence (`heading`,
   `dropped_stub`, `dropped_empty`), intake persists it, the layout
   contract is v2, and the fidelity check now measures the UNEXPLAINED
   gap (not covered by layout evidence). Rows and chunk ids are
   byte-identical to before. Existing documents carry no dropped-span
   evidence until re-ingested — P6 does that.
3. **Census promotion run-scoped** (`census._missing_projection_receipts`):
   the same corpus-barrier defect as this morning's advance predicate,
   now closed on the promotion side (legacy runs without a resolvable
   document keep the corpus-wide check).
4. **Cloud floor — finding RETRACTED.** I had flagged
   `POLYMATH_WORKER_CLOUD_MIN_BYTES=0` as "the privacy floor is off" and
   set it to 450 KB. `llm_extraction/policy.py` records the owner's own
   decisions: rule v2 (2026-08-30) made the threshold a THROUGHPUT router,
   not a privacy boundary, and CLOUD-FIRST-V1 (owner-blessed 2026-09-02)
   set the floor to 0 because the local 4B lane measured 76–89 %
   quarantine on small books against 0–5 % on the cloud lanes. The 450 KB
   setting was reverted to 0 within the hour (the fleet ran with it for
   ~15 min; cysa's documents still rode cloud via assist). The stale
   "privacy rule" sentence in CLAUDE.md is corrected.
5. **Local lane supervised and budgeted:** the batched 4B server on :8755
   had run as a hand-started process for 3 days 18 h outside the
   supervisor and outside `runtime_budget.yaml`. It is now the
   `local_extractor` slot (ALWAYS resident; health :8755/ready; memory
   cap 10 GB via `POLYMATH_LLM_LOCAL_MEMORY_GB`), the retired GLiNER/spaCy
   caps are gone, and the fleet budget is 29 GB on the 32 GB machine
   (serve profile 27.55 / 28.5 ceiling). Under CLOUD-FIRST-V1 it is the
   assist/fallback lane, so it wakes with the extract lane instead of
   holding 10 GB while idle. `run_proposals` waits for :8755/ready before
   the first local call (the projector's readiness gate, ported).
6. **The abstentions were not a gate defect.** Learning SQL lives in
   cysa-study-v1 (the dev question pointed at ecom-meta-v1), its text is
   partly OCR noise and holds one child mentioning JOIN; the AWS book
   never mentions "shared responsibility" or "vulnerability scan". The
   admission gate abstained correctly on ungrounded questions. The dev
   set is re-grounded in phrases the books contain: supported 90 %,
   wrong 0 %, unexplained 1 (`sb-02` "call to action": StoryBrand holds
   28 matching children, chat abstained — the one genuine case, open).
7. **Decisions executed:** apple-ml LaunchAgent retired; 29 interpreter-
   path test files deleted (list above); P6 launched.

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
- `sb-02` (StoryBrand "call to action") abstains although 28 children match —
  the one unexplained dev-holdout case after re-grounding.
- Retired code (`workers/candidates.py`, `kimi_*`, `syntax.py`, `rescue.py`,
  `polymath_shared/rulepack/`, `syntax_readiness.py`, the two sidecar runtimes)
  is still importable behind the gliner provider branch.
