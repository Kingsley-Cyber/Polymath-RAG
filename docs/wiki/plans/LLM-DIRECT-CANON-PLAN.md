---
change_id: LLM-DIRECT-CANON
owner: governance
date: 2026-09-03
status: adopted — executing (phase receipts appended below as they land)
architecture_impact: LLM-direct extraction (llm-direct-v1) becomes the ONLY canonical extraction path; the GLiNER/spaCy span-tagger contracts (attestation-as-gate, sentence-slice manifest, rule-pack replay, fact-tuple grading) are retired from enforcement and kept as history
last_reviewed: 2026-09-03
---

# LLM-DIRECT CANON — plan of record

## Contract (owner, 2026-09-03)
"This repo has been refactored upon the old GLiNER model which manually used
Python, GLiNER and spaCy to derive facts and use them for graph queries. We
moved from that, but it still affects how this RAG works: it is being graded
on that and made to adhere to the original style. Write the plan, investigate
the code path, use the graphify graph to confirm dependencies, and fix it so
LLM-direct is declared canon."

## Evidence (measured 2026-09-03, last 20 extracted documents)
| Old rule applied to LLM output | Measured effect |
|---|---|
| Attestation gates: UNATTESTED_ENTITY 825, UNATTESTED_RELATION_ENDPOINT 787, NON_TERM_ENDPOINT 502, UNATTESTED_RELATION_QUOTE 470, NON_TERM_SURFACE 127, INTERROGATIVE 20 | 1,779 relations + 952 entities rejected; 1,613 facts written of ~3,500 proposed relations (46 % survive) |
| Core-type coercion (`map_core_type` → `concept_default`) | 2,415 of 2,680 coercions flatten to Concept; LLM types (Device, Protocol, Certification, Methodology, Strategy…) survive only in `entities.raw_types`; Concept = 17,222 entities, the largest class |
| Fact admission chain (F3_ENDPOINTS) | rejected 147/148 LLM facts when enforced → observe-only since; dead weight |
| EXACT_REPLAY gate (`eval/v5/replay_full.py`) | requires sentence-slice-manifest-v1; `sentence_slices` = 0 rows; unprovable by construction |
| Retrieval validation (`eval/v5/retrieval/retrieval_validation.py`) | ground truth = "top admitted fact tuples" → the system is graded on reproducing its own graph |
| GRAPH release gate | "T2 not qualified" — a tagger-era tier qualification |
| Build fence | enforced GLiNER/spaCy sidecars until FENCE-PATH-AWARE-V1 (2026-09-03) |
| Settings | `extraction_provider` default is still `gliner` ("frozen default"); production runs only because `.env` overrides it |
| CLAUDE.md operating rules | still prescribe `POLYMATH_SYNTAX_PROVIDER=spacy POLYMATH_RESCUE=on POLYMATH_WORKER_RULE_PACK_VERSION=1.5.0 …` for hand-started processes |
| Tests | 75 test files and 166 eval files reference the old path; the standing failures are GLiREL / sval / syntax-readiness era |

A representative rejection: "marine research unit MEASURES water temperature,
salinity and plankton density" — a correct fact, rejected
UNATTESTED_RELATION_ENDPOINT because the subject sits in the neighbouring
chunk, not in the anchor chunk of the quote. That is a span-tagger locality
rule, not a truth rule.

## Dependency map (graphify `graphify-out/graph.json`, 14,729 nodes, BFS depth 2; every claim re-checked with grep)
- **Gate → facts:** `shared/polymath_shared/llm_extraction/gate.py:validate_and_normalize` (TERM-SURFACE-GATE at L493, attestation L560–650) is called ONLY from `workers/workers/llm_provider.py:630`; its `NormalizedExtraction` flows to `workers/workers/llm_direct.py:materialize` (facts/evidence/mentions/entities, `extract_worker.py:1204`). Rejections/coercions land in the extract-stage artifact (`llm_rejections`, `llm_coercions`). Tests pinning it: `tests/determinism/test_llm_extraction.py` (L182 unattested entity, L199 unattested endpoint, L224 concept_default), `test_term_surface_gate.py`, `tests/integration/test_llm_direct_facts.py`.
- **Old path (sentence slices / spaCy / GLiNER):** `shared/polymath_shared/clients.py` (SpacySyntaxClient L291, GlinerClient), `sidecars/spacy_runtime`, `sidecars/gliner_runtime` (incl. `rescue()` L312), `workers/workers/extract_worker.py:_slices` L368 + the `provider == "gliner"` branch (L93/L946) + legacy fact writer L2120, `workers/workers/syntax.py:parse_sentence`, `workers/workers/candidates.py:SentenceSlice`, `workers/workers/rescue.py`, `shared/polymath_shared/syntax_readiness.py`, `shared/polymath_shared/raw_evidence.py:bundle_manifest(require_slices=True)`, `workers/workers/reprocess_worker.py:328`, `eval/v5/shadow_settlement.py` + `replay_full.py`, `control/control/census.py` (compute_census reads slice-era receipts only through `verify_projections` — unaffected). Nothing on the query path imports them; `graph_retrieve`/`fast_retrieve`/`hybrid_fast_retrieve` reach them only through the shared `evidence.py` node.
- **Type/decision consumers:** `facts.decision` → `shared/polymath_shared/neo4j_eligibility.py` → `workers/workers/project_neo4j_worker.py` (MERGE Fact L83) → `orchestrator/api/retrieve.py:456` (facts authorized for graph expansion). `entities.core_type` → identity (`identity.entity_id(core, surface)`), Neo4j `e.core_type` (L71; `raw_types` NOT projected), canonicalization (`project_canonical_worker.py`, `entity_admission_stage.py`), fast/hybrid filters. `facts.provenance` already carries `predicate_raw` / `predicate_method`.

## Design law after this plan
1. **LLM-direct is the extraction canon.** `extractor_version = llm-direct-v1`; the gate is the only authority; a fact is durable knowledge iff its QUOTE is attested verbatim in the document. Endpoint surfaces are bound to the quote, not required to be substrings of the anchor chunk.
2. **Attestation is a recorded level, not a veto** (except junk): `quote` › `anchor` › `neighborhood` › `document` › `abstract` (all content tokens of the endpoint present in the anchor chunk). NON_TERM (junk surfaces), UNATTESTED_RELATION_QUOTE and INTERROGATIVE stay hard gates; an endpoint with no token support anywhere in the anchor chunk stays rejected (that is invention).
3. **The open vocabulary is data.** `raw_types` (already a set union on entities) and `predicate_raw` (already in provenance) are projected to Neo4j and surfaced in the graph view; core type and the 17+1 predicate enum remain the INDEX vocabulary, never the truth.
4. **Grading follows the product.** Retrieval is graded on answers to gold questions (sealed holdout), never on fact-tuple self-consistency. Replay is graded from stored raw LLM responses (`extraction_call_receipts.raw_text`), never from the interpreter view.
5. **The span-tagger path is history.** Selectable for forensics (`extraction_provider=gliner`), never default, never enforced by a gate, fence or test.

## Phases (each: tests → repo_guard → commit → fleet restart where shared/ or workers/ changed)
| # | Slice | Change | Proof / target (pre-registered) |
|---|---|---|---|
| P0 | CANON DECLARATION | ADR-0017; CLAUDE.md law rewritten (canon env, no spaCy/rescue/rule-pack knobs); `RAG-ARCHITECTURE-V2.md` extraction section; `settings.extraction_provider` default `llm_live`; register row | repo_guard ok; settings test updated; fleet env unchanged (already llm_live) |
| P1 | ATTESTATION-LEVELS-V1 | gate.py tiered endpoint attestation + per-level counters in `merged.stats`; materialize binds endpoint offsets to the quote when the surface is not in the anchor and records `endpoint_attestation` in evidence offsets + fact provenance; entity type for unplaced endpoints looked up by normalized surface (the current `map_core_type(surface)` call routes a SURFACE through the TYPE mapper) | unit tests for all five levels + the token rule; CANARY on the probe corpus (A/B texts re-uploaded with a nonce, same lanes): relation survival ≥ 70 % (from 46 %), junk endpoints in accepted = 0, `abstract` share ≤ 25 %, 20 sampled tiered relations ≥ 18 correct by inspection; quick grade (2-chunk key, reference model) extraction score ≥ baseline − 0.03 and rel_recall ≥ baseline |
| P2 | OPEN-VOCAB-SURFACED | Neo4j projector sets `e.raw_types` + `e.display_type` (most specific raw type, else core) and `r.predicate_raw`; brain-view uses display_type | projection test; a Concept-typed entity with raw_types shows its raw type in `/api/graph` |
| P3 | LLM-DIRECT-REPLAY-V1 | `eval/v5/replay_llm_direct.py`: stored `extraction_call_receipts.raw_text` → sanitize → gate → in-memory materialize → fact-id set vs production; `--record-evidence` writes `release_evidence/exact_replay.json`; `release_gates.gate_exact_replay` reads it (contract text updated: replay from the ledger of raw responses) | identical fact set on a freshly extracted document; the gate version is part of the evidence |
| P4 | RETIREMENT | historical tests skip-marked with reason (list below); `retrieval_validation.py` + `replay_full.py` + `shadow_settlement.py` moved to `eval/historical/` with a README; `syntax_readiness` / `rescue` guarded behind `extraction_provider == "gliner"`; runtime budget entries for the two sidecars marked historical; fence stays path-aware | full determinism suite: 0 failures outside the declared skip list |
| P5 | GRADING | `eval/v5/holdout/`: gold-question schema (question, corpus, expected_docs, must_include_any, expects_abstain), deterministic grader over `/chat` (doc hit@k, phrase presence, abstention correctness, latency) reading query receipts; a DEVELOPMENT seed set is not release evidence — the sealed set is owner-supplied | `release_gates.gate_holdout` reads the sealed result; GRAPH gate re-expressed as "GRAPH lane lifts holdout accuracy by ≥ X or is cut" |
| P6 | RE-EXTRACTION (owner decision) | re-extract ecom-meta-v1 + cysa-study-v1 under the new gate (≈ 60 MB source; a few dollars on the current lanes, hours of wall) | fact count and type diversity before/after; holdout accuracy not lower |

## Historical tests to skip-mark (P4) — reason "historical GLiNER/spaCy path, LLM-DIRECT-CANON"
Filled from the 2026-09-03 run (see work-log): the sval trio, the killchain
child-span gap check, the llm_controller fake, the GLiREL-era
relation_candidates pin, the re-ingest orphan-concept artifact pin and the
two syntax_readiness_v3 tests. Deleting them is an owner decision; skipping
keeps the history readable.

## Rollback
`POLYMATH_EXTRACTION_ATTESTATION=strict` restores anchor-only endpoint
attestation (the tier policy is a setting; default `tiered`). Facts carry
the gate version in provenance, so the two populations are separable.
Re-extraction never deletes: identities are content hashes, replays write 0 rows.

## Rejected claims
- "Keep everything as-is; the LLM path works." It works at 46 % relation
  survival and grades itself against its own graph.
- "Drop attestation entirely." A quote that is not in the document is
  invention; that gate stays. Only the locality rule goes.
- "Change entity identity to raw types." Identity stays (core, surface);
  raw types are projected, not folded into ids (that would re-shard every
  entity and re-run canonicalization for a display concern).

## Owner decisions outstanding
1. Re-extract the two production corpora under the new gate (P6)?
2. Delete or skip the historical tests (P4)?
3. Retire the `com.polymath.apple-ml` LaunchAgent (its GLiNER/spaCy ports
   are down already; it may still serve the sibling repo's embed/rerank —
   not touched here).

## Phase receipts (appended as they land)
- 2026-09-03 P0–P2 landed (4a4b67d, a611961): ADR-0017, architecture canon
  section, CLAUDE.md law, `llm_live` default; ATTESTATION-LEVELS-V1 with
  `strict` rollback; open vocabulary projected to Neo4j; 42 tests green;
  historical sval fixtures skip-marked.
- 2026-09-03 P1 CANARY (Learning SQL, 111 KB, 144 children, cloud lane
  mistral-small-2603 — the fleet's cloud floor is 0 B today): 130 relations
  kept / 29 rejected; UNATTESTED_RELATION_ENDPOINT 0 (was 36 of 86 on the
  same text under the old rule); endpoint levels quote 150 / anchor 69 /
  neighborhood 31 / document 1 / abstract 9; survival among non-junk
  proposals 82 % (baseline 52 %; target ≥ 70 % MET); abstract share 3 %
  (≤ 25 % MET); junk in accepted 0 (MET); inspection of 20 beyond-anchor
  relations 17/20 correct (target 18/20 MISSED BY ONE — the misses are the
  model's predicate choice, endpoints right 20/20).
- 2026-09-03 P5 landed: `eval/v5/holdout/` grader + dev seed set. First dev
  run: supported 60 %, wrong 0 %, unexplained 4 (three abstentions on
  answerable questions → answerability-gate finding, one grader phrase too
  narrow), zero-tolerance clean. Not release evidence.
- 2026-09-03 P3: `eval/v5/replay_llm_direct.py` drives the provider's own
  pipeline from the raw-response ledger. Building it found
  RECEIPT-COMPLETENESS-V1 (reissue calls were never receipted; the ledger
  lacked `finish_reason`, which the disposition rules read) — fixed
  (f34ddb6, migration 0048). Canary 3 (first fully-ledgered document): replay IDENTICAL, 103/103 facts,
  extra 0 / missing 0 → EXACT_REPLAY PASS; the same responses under `strict`
  lose 27 facts (26 %).
- 2026-09-03 P4 complete (owner: "retire 3, delete 2"): apple-ml LaunchAgent
  retired (disabled, plist kept); 29 interpreter-path test files deleted
  (list in the work-log); interpreter harnesses moved to `eval/historical/`.
  Retired CODE remains behind the gliner provider branch — next owner call.
- 2026-09-03 P6 running. Lesson: `reingest_corpus` takes the corpus offline
  (502 corpus_not_ready) until convergence because intake purges the old
  generation. Next slice: BLUE/GREEN RE-INGEST (shadow corpus id + alias swap).
