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
   the document was extracted in. P6 LAUNCHED 17:05Z: `reingest_corpus.py cysa-study-v1 --execute`
   → the next control tick superseded both runs and minted successors;
   intake re-ran within 30 s (the two documents now carry
   `document_layout` rows `dropped_stub` 2 + `heading` 220 (AWS) and
   `dropped_stub` 3 + `heading` 216 (Learning SQL) — the first documents
   under CHUNK-GAP-ACCOUNTING-V1) and extract re-leased on the new
   contract (receipts stamped with the new `contract_ident`).
   `reingest_corpus.py ecom-meta-v1 --execute` at 17:09Z: 10 runs
   reconciling, intake and extract tickets flowing. The 15-minute
   450 KB floor detour (item 4) changed the identity twice; runs that
   finished a stage under the interim identity are re-minted once more
   by contract drift — bounded extra calls, no manual repair. Progress:
   `/status?corpus_id=…`, `scripts/trace_stalls.py`, and per-lane
   receipts (`extraction_call_receipts.created_at`). Completion is hours
   (cloud ring, ~8,500 children, then projection, summaries, enrichment).
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
8. **STALL-TRACER-V1.3 (from watching P6).** Two false-positive classes:
   READY_NO_CLAIM_EVENT on `parent_enrichment` (owner-triggered stages mint
   per-RUN claim events whose payload has no `ticket_id`; the tracer's
   anti-join required one — 6/6 "eventless" tickets had a pending event),
   and READY_UNCLAIMED on extract tickets queued behind 3 busy extract
   workers. The claim-event predicate now accepts per-run events, and a
   claimable READY ticket whose lane has every live worker leased is a
   queue, not a stall (checked AFTER the no-event and no-live-slot
   defects, which stay traced). Tests: test_stall_tracer 11.
9. **P6 makes the corpus unqueryable while it converges.** `reingest_corpus`
   supersedes every run and intake re-chunks (GENERATION-PURGE removes the
   old rows), so `/retrieve` and `/chat` answer 502 `corpus_not_ready` for
   ecom-meta-v1 and cysa-study-v1 until the successors are query_ready —
   by the serving contract (fast.py), not a fault. The two 502s I first
   read as a reranker cold start were this. Recommendation (plan, next
   slice): blue/green re-ingest — regenerate into a shadow corpus id and
   swap the alias when converged, so a contract change never takes the
   product down.
10. **Full determinism + contracts suite after the deletions (1 run, P6 in
   flight):** 12 failures → classified: 4 contract tests validate a LIVE
   /chat response against the v2 schemas and the schemas lagged the
   runtime (`meta.verdict`, `answer_admission`, `uncovered_query_terms`,
   `citation.human_locators`, claim status `withheld_insufficient_coverage`,
   evidence-item `presentation`) — schemas updated, the tests need a
   query_ready corpus to re-run; `test_raw_evidence_ledger` pins the
   semantic-authority hash, which ATTESTATION-LEVELS-V1 moved on purpose —
   pin moved with the reason; `test_kimi_observability_phase5` imported a
   deleted interpreter-path test — deleted (30th file);
   `test_fact_endpoint_eligibility::test_retirement_preserved_raw_observations…`
   is the GLiREL-era relation_candidates pin — skip-marked (ADR-0017);
   `test_evidence_truncation` and `test_graph_lifecycle_v2` read live data
   mid-purge (concepts whose chunks were regenerated; Neo4j nodes whose
   Postgres rows were purged before the successor's projection) — re-check
   after P6, real defects if they persist; `test_llm_controller` is the
   pre-existing batched-client double.
11. **RECEIPT-LOOKUP-BATCH-V1 (found by the tracer during P6).** Four ecom
   runs failed `project_qdrant` at 17:30Z with `psycopg.OperationalError:
   number of parameters must be between 0 and 65535`: the projector's
   already-current lookup sent one VALUES list over the CORPUS-wide want
   set (3 bind parameters per row), and the re-chunked corpus crossed
   libpq's ceiling. The lookup is batched (10,000 rows per query, same
   result set; test_receipt_lookup_batch). The four stages were retried
   after the fleet restart (`scripts/retry_failed_stage.py`).
   STALL-TRACER-V1.3 final shape: capacity and busyness are judged per
   worker TYPE from the lease-owner prefix (`<type>-<pid>-<hash>`; the
   registrations join broke whenever pruning or a restart removed the
   holder's row), the chain carries a per-ticket live-work flag (leased by
   a live holder, or claimable and queued behind a saturated lane), and
   the probe tests own their capacity so the live fleet cannot skew them.

12. **RETIREMENT-DELETE-V1 (owner: "delete the retired code").** The
   GLiNER/spaCy/rule-pack path is gone from the tree, not parked behind a
   provider branch. `extract_worker.py` is rewritten LLM-direct only
   (1,986 → 324 lines; `EXTRACTOR_VERSION = llm-direct-worker-v2`; a
   non-`llm_live` provider raises instead of falling through). Deleted:
   `sidecars/gliner_runtime/`, `sidecars/spacy_runtime/`, their toml pins,
   4 v1 extraction schemas, 9 workers (`candidates`, `kimi_candidates`,
   `kimi_v2_candidates`, `syntax`, `rescue`, `evidence_proposer`,
   `fact_admission_stage`, `reprocess_worker`, `entity_admission_stage`),
   `polymath_shared/{syntax_readiness,discourse_bridge,fact_admission}.py`,
   the whole `polymath_shared/rulepack/` package and its yaml packs,
   `fact_admission_policy.yaml`, `scripts/compile_predicate_rules.py`,
   `tests/historical_boundary.py` and 14 more retired-path test files
   (`git log --diff-filter=D` for the list). Relocated, not deleted:
   `compound_heads.py` (the 10 compound head nouns, now read from
   `config/ontology/scientific-predicate-ontology-v2.yaml`),
   `verb_inventory.py` (the 190 verbs the rule pack used to supply at
   import time, frozen as data — the old loader fell back to an EMPTY set
   on any import error, a silent fallback), `workers/knowledge_artifacts.py`
   (the Procedure/Concept persister the `compile_objects` stage imports; it
   lived inside the extract worker), and 18 eval harnesses under
   `eval/historical/`. Settings lost `gliner_url`, `spacy_url`,
   `syntax_provider`, `evidence_proposal_mode`, `rule_pack_version` and the
   `RescueSettings` block; the execution contract lost `rule_pack`,
   `syntax_provider`, `rescue_stages`, `gliner_url`, `rule_pack_file_sha`
   and the S3 syntax claim gate; `STAGE_CONTRACT_DEPENDENCIES` and the
   config-drift env list follow. `bundle_integrity` now pins
   `llm_extraction/gate.py` + `workers/llm_direct.py` as authorities and its
   census asks for a production caller of the GATE (three: extract worker,
   llm_provider, llm_direct); the semantic bundle lock was re-frozen
   deliberately as `v5-production-002-llm-direct` (members changed:
   `fact_admission.py` gone, gate + writer added; `admission_interpreter.py`
   lost its spaCy readiness assert). Tests were retargeted rather than
   deleted wherever the invariant survives: compatibility gating on
   `chunker`/`query_policy`, staleness on `semantic_bundle`, the two
   semantic-authority pins moved (`7b7fbcd284b47850`), the projection
   reconstruction fixture builds facts the way `llm_direct.materialize`
   writes them, the lane-affinity test uses the policy boundary for both
   lanes (a 1,000-byte document is CLOUD-lane under floor 0), and the two
   summary idempotency tests now retry the SAME content-addressed ticket
   (their second-job-row leg predates the 08-28 `(stage, input_hash)`
   unique index — a test that had been failing since P23, not since today).
   AGENTS.md's tree, the TREE in `scaffold_polymath_v4.py` (45 rows removed,
   19 renamed, 3 added) and `scripts/README.md` follow the tree.
   Net: 117 tracked files, +393 / −17,752 lines.

13. **GENERATION-SWAP-V1 (owner: "do the blue/green reingest") + the
   post-deletion canary.** Canary first: a fresh one-document corpus
   (`canary-llm-direct-0903`, Meyer's vector-database chapter, 14 KB)
   submitted through `scripts/ingest.py` on the deleted tree went
   `query_ready` in 117 s; the extract artifact is `llm_direct`
   (63 facts, 117 entities, 12 of 12 neighborhoods accounted, 0
   unaccounted); FAST answers in 1.3 s with 9 citations, HYBRID with 7.
   One compound question ("what problem do they solve AND how do they
   index") abstained — the answerability gate, same class as the dev
   holdout finding (question grounding), not the extractor.
   Blue/green: `reingest_corpus.py --execute` took a corpus offline because
   it strands the serving run (502 `corpus_not_ready` until the successor
   converges; P6 measured minutes for cysa, hours for a book). Now
   `--blue-green` mints a SHADOW successor beside the serving run
   (`control.reconciliation.mint_shadow_successor`: predecessor untouched,
   `runs.metadata.blue_green = {supersedes, generation,
   predecessor_generation, regenerated/carried stages}`); intake skips the
   GENERATION-PURGE for such runs, so when the chunker changed the new
   generation's rows coexist with the serving rows — migration 0050 makes
   `(doc_id, chunk_index)` unique PER GENERATION (`COALESCE(chunk_contract_version,'')`)
   and `chunk_id` stays the content-addressed key; readers hide in-flight
   generations (`polymath_shared.generation.chunk_visible_sql`, a
   parameter-free correlated NOT EXISTS pasted into the FAST neighbor
   expansion, the HYBRID lexical fallback, both `retrieve` row loaders,
   `_resolve_chunk` and the evidence-chunk lookups in chat/evidence;
   Qdrant lanes add one `must_not chunk_contract_version = g` per hidden
   generation — new points carry the field, legacy points pass);
   promotion swaps atomically (`control.generation_swap.swap` inside
   `apply_promotions`' transaction: predecessor + open tickets superseded,
   old-generation chunk rows purged for every re-chunked document,
   `concept_artifacts`/`procedure_artifacts` with no surviving supporting
   chunk removed, `blue_green.swapped_at` stamped; Neo4j Chunk/Evidence
   nodes and Qdrant points of the purged rows swept best-effort — a sweep
   failure is logged, never rolls the promotion back). The persister now
   UPSERTs (`supporting_chunks`/`source_chunk_ids` refreshed on replay)
   instead of `DO NOTHING`, which is what left one concept pointing at
   purged chunks after P6 (item 12's finding). Extraction-only successors
   (same chunker) share the chunk rows: nothing is hidden, the swap purges
   nothing; the FACT tier is not generation-isolated mid-swap (old facts
   keep their evidence on the shared rows) — documented gap, see below.
   **CONTRACT-DRIFT BLIND SPOT (found while designing the drill):** the
   execution contract had no key for the LLM gate — `contract_identity()`
   (receipts) carried it, `default_execution_contract()` did not — so a
   gate/attestation change was invisible to `reconcile_contract_drift` and
   `reingest_corpus.py` answered "nothing to re-ingest" after the very
   change that needs one (P6 only worked because `semantic_bundle` moved in
   the same commit). `worker_contracts()` now carries
   `extraction_gate = <GATE_VERSION>/<attestation policy>` (one constant,
   `gate.GATE_VERSION`, shared with the receipt identity); `extract`
   depends on it and on `ontology_file_sha` (it did not!), and
   project_neo4j/canonicalize/project_canonical depend on it in place of
   the dead `rule_pack` key. Consequence: every live run now pins a stale
   contract; healthy `query_ready` runs are never touched by the reconciler
   (no open tickets), which is exactly the condition `--blue-green` consumes.
   Two more consequences of the same reading: `compile_objects` had NO
   declared contract dependencies, so a successor always carried it and the
   Procedure/Concept artifacts of a re-chunked corpus were never re-grounded
   (the dry run of the new `scripts/sweep_orphan_derivatives.py` found 121
   concepts + 445 procedures pointing only at purged chunks, and 1,697
   orphan Neo4j Chunk nodes from P6); it now depends on
   `semantic_bundle`/`extraction_gate`/`chunker`, and its persistence
   contract is `knowledge-artifact-persistence-v2` (the upsert), so the
   fleet re-grounds every corpus's artifacts once after this restart. The
   sweep script clears what no re-run can re-ground (dry run by default;
   receipt below).

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
- ~~Retired code still importable behind the gliner provider branch~~ —
  DELETED (item 12, RETIREMENT-DELETE-V1).
- Fact-tier generation isolation: an extraction-only blue/green successor
  writes its facts beside the predecessor's (both evidenced on the shared
  chunk rows; `materialize` is insert-only). The swap does not purge the
  old extraction's facts/evidence. Next: stamp evidence rows with the
  successor run's `extraction_gate`/contract identity and purge the
  predecessor's at swap.
- ecom-meta-v1 still pins the pre-`extraction_gate` contract (10 runs); its
  blue/green re-extraction is an owner cost decision:
  `scripts/reingest_corpus.py ecom-meta-v1 --execute --blue-green`.
- Lifecycle findings surfaced by the post-P6 invariant tests (both are the
  purge's doing, not the extractor's): Neo4j keeps 437 Evidence + 1,697 Chunk
  nodes whose Postgres rows the intake purge deleted
  (`test_no_derived_node_outlives_its_postgres_row`), and one
  `concept_artifacts` row keeps `supporting_chunks` from the purged
  generation because the persister is `ON CONFLICT DO NOTHING` on a
  content-addressed id (`test_truncated_concepts_still_hydrate_full_text`).
  Both belong to GENERATION-SWAP-V1: the swap must sweep derived nodes and
  refresh derived artifacts for every replaced chunk. `test_llm_controller`
  (batched-client double) remains the pre-existing failure.
