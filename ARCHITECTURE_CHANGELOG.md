# Architecture changelog

Dated diffs of every architectural change. Each entry links to the ADR
that motivated it and the refactor that implemented it.

## 2026-08-14: verify cross-corpus chunk-deletion fix

- Bulk-acceptance run discovered `reconcile_neo4j` deleted other
  corpora's receipted chunk nodes (orphan check used corpus-scoped
  receipts against the shared graph). Fixed: orphans = chunks with no
  active receipt ANYWHERE; report value matches the deletion set.
  Regression test added; live stores re-driven to query_ready
  (work log 2026-08-14-bulk-acceptance-verify-fix).

## 2026-08-14: I0 native document materialization (ADR 0010)

- `shared/polymath_shared/materializer.py`: deterministic
  per-format materialization (TXT/MD/HTML/PDF/EPUB/DOCX) → normalized
  text + structural source map (page/chapter/section/paragraph) with
  typed loud failures; one new dependency (`pypdf`).
- Intake materializes inside the stage transaction; documents gain
  `source_hash`/`materialization`/`source_map` (migration 0006);
  extract consumes the authoritative Postgres chunks (single chunk
  lineage for native + text formats).
- New contract `contracts/ingestion/v1/materialization.schema.json`;
  public-domain book fixtures; live E2E proves the citation chain
  fact → evidence → chunk offsets → source-map → page/chapter
  (refactor 0007; work log 2026-08-14-i0-native-documents).
- Semantic extraction unchanged (Q1 locks still green).

## 2026-08-14: Q1 heterogeneous extraction qualification (PASS)

- Frozen qualification corpus `eval/gold/qualification_q1.yaml`
  (53 items, 11 classes) + frozen harness artifacts + frozen report
  `eval/q1/REPORT_Q1.md`: production (lexical) arm P/R 0.943, 0
  wrong-predicate, 0 wrong-scope; residual failures all catalogued
  classes. Regression locks in
  `tests/contracts/test_q1_qualification_regression.py`.
- Q1-discovered defect fixed: census chain reordered —
  canonicalize → project_canonical → verify_projections — so the
  verifier reconciles the canonical graph only when it is due
  (refactor 0006; work log 2026-08-14-q1-qualification).
- Production extraction declared qualified; further extraction
  changes require a demonstrated regression or separately measured
  improvement.

## 2026-08-14: C2 canonical KG + provenance projection

- New census stage `project_canonical` (after `canonicalize`):
  `(:CanonicalEntity)` nodes with C1 ids, `[:HAS_MEMBER]` edges
  carrying decision/basis/version, `(:Evidence)-[:FROM_CHUNK]->(:Chunk)`
  source links. Neo4j receives Postgres identities only.
- Receipt kinds `canonical_entity` / `canonical_membership` /
  `evidence_chunk`; `reconcile_canonical` in verify_projections
  (orphan receipts superseded before store-orphan scan; missing
  artifacts clear receipts and degrade loudly); census re-arm covers
  the canonical projection.
- Rebuildable from Postgres; replay no-op; incremental delta;
  destructive reconstruction + orphan detection proven live
  (refactor 0005; work log 2026-08-14-c2-canonical-kg).

## 2026-08-14: C1 Stage-2 corpus canonicalization (ADR 0009)

- New Postgres registry (migration 0005): `canonical_entities`,
  `canonical_memberships`, `canonicalization_decisions` — corpus
  layer ADDED on top of source-local knowledge, never erasing it.
- New census stage `canonicalize` (`canonicalize.v1`) after
  `verify_projections`; deterministic recompute + delete-stale /
  insert-missing diff inside one stage transaction.
- Conservative policy: SAME_AS only on normalized-exact-name +
  compatible type + mergeable class; ALIAS_OF only on explicit
  corpus-profile declarations; DISTINCT on incompatible types;
  homonym-risk classes abstain. No fuzzy/LLM merges. Content-hash
  canonical ids are order-independent and replay-safe.
- Wire contract `contracts/canonicalization/v1/`; refactor 0004; work
  log 2026-08-14-c1-canonicalization.

## 2026-08-14: R3b grounded answer generation + /chat

- New wire contract `contracts/answer/v1/chat_response.schema.json`
  (answer path; refactor 0003, work log 2026-08-14-r3b-grounded-answer).
- POST /chat: query → R3a EvidenceBundle → deterministic propose →
  validate → render. The validator, not the proposer, decides what may
  render: citations reference bundle item ids and retain locators;
  unsupported/fake-cited/ungrounded claims fail closed into the claim
  ledger; conflicts are represented, never arbitrated; epistemic scope
  survives; insufficient evidence abstains explicitly.
- Boundary kept: no retrieval re-implementation in the synthesizer, no
  direct store access, no C1/C2/R2/E1. R3a semantics untouched.

## 2026-08-14: R3a grounded EvidenceBundle assembly

- New wire contract `contracts/answer/v1/evidence_bundle.schema.json`
  (answer path; refactor 0002, work log 2026-08-14-r3a-evidence-bundle).
- POST /evidence on the orchestrator: deterministic bundle where every
  claim item carries fact/entity IDs, source document + span locator,
  provenance, epistemics, applicability, and retrieval lane; evidence-
  only items never carry claims. Unresolvable references and missing
  provenance are typed assembly errors mapped to HTTP 502 — loud, never
  silent.
- Boundary kept: R3a assembles evidence; final answer prose is R3b.
  No extraction change, no migration, no dependency-map change.

## 2026-08-13: initial scaffold

- Skeleton created by `scripts/scaffold_polymath_v4.py` (sha: f82bf2fc9fb1).
- Accepted Postgres as workflow authority.
- Accepted one host-native GLiNER runtime serving two logical passes.
- Added machine-readable dependency ownership and repository work logs.

## 2026-08-13: Phase B production foundation (ADR-0006)

- Workflow schema lands: documents, chunks, entities, evidence, facts,
  artifacts, receipts, outbox, control leases and heartbeats (migration
  0002).
- Transactional receipt boundary implemented in `polymath_shared.receipts`.
- Deterministic rule pack + predicate compiler (YAML data, compiled DAG,
  §15 compile-time checks).
- No-LLM ingestion layer: sentence-aligned parent/child chunking and
  extractive summaries.
- Orchestrator `/intake` commits one run + one outbox event per canonical
  input; control plane runs as a separate process with a Postgres lease.
- GLiNER runtime manifest pinned to urchade/gliner_medium-v2.1 @
  40ec419; `/ready` performs a real forward pass.
- Packaging: uv workspace; deployment: launchd units + Makefile.

## 2026-08-14: Phase F — disposable projections (ADR-0007)

- Qdrant + Neo4j become rebuildable projections with durable stages:
  project_qdrant, project_neo4j, verify_projections; the census chain
  grows to five stages with per-stage event types.
- Projection identity is derived (content hash of projection | kind |
  source | contract); Neo4j receives fact_id, Qdrant receives chunk_id
  — projections never invent semantic identity.
- VERIFY_PROJECTIONS reconciles receipts against live stores: store
  loss clears receipts (census re-drives), orphans are deleted, runs
  degrade until convergence.
- Embedding contract registry lands with hash-embed-v1 (deterministic,
  versioned); the neural embedder arrives in Phase G as a new contract.
- ADR-0007: deterministic lexical evidence lane replaces the neural
  evidence pass (measured, experiment 0001).
- Experiment 0002 recorded: frozen gold set + layer-wise recovery
  numbers (compiler 95.7% predicate accuracy on gold inputs).
- Neo4j moved to host ports 7475/7688 — the v3.3 graph on 7474 is
  never touched.



## 2026-08-14: Phase G hardening — immutable pins, coverage report, spec closure

- All resource manifests resolve exact commit SHAs (no branch refs at
  build time); archive hashes re-pinned; resource contract re-derived
  (03a513ec...).
- Fetch verifies checksums inline (wrong bytes never land); SemLink
  attested-vs-composed derivation recorded explicitly; fact provenance
  carries trigger_lemma + trigger_surface.
- build_statistics.json + per-rule coverage report (10 COMPLETE /
  12 PARTIAL / 6 MANUAL_ONLY / 0 CONFLICT).
- resources/README.md documents pinned sources, licenses, contract
  identity, and the upgrade procedure (contract migration, never
  in-place).
- Polysemy / modality / contract-isolation tests added.

## 2026-08-14: Phase G — the lexical-semantic compiler becomes real (+ G.1)

- VerbNet 3.3, Unified PropBank, FrameNet 1.7, SemLink 2.0 vendored,
  sha256-pinned, flattened into immutable lemma-keyed tables under
  resources/compiled/<resource_contract_id>/ (deterministic rebuilds,
  byte-identical — GATE 1).
- Rule pack compiles against the REAL resource index: invented
  citations fail the build (GATE 3); trigger sets expand through real
  VerbNet class membership (GATE 5); SemLink is evidence, never a gate
  (GATE 4); runtime reads only compiled tables (GATE 10).
- Rule citations corrected against real data (found.01 -> establish.01,
  VN 3.3 class numbering, real FN frame names).
- Facts carry resource_contract_id + compiled_lexical_sha256 in
  provenance; extract workers look up VN/PB/FN from the compiled
  tables (O(1), no raw-resource parsing).
- ADR-0008 restores the two-pass boundary: GLiNER pass 2 proposes
  coarse evidence (may abstain), the lexical lane localizes triggers,
  resources constrain, the compiler decides. Mode: lexical | hybrid.


## 2026-08-14: Phase H — lexical-semantic waterfall qualification

- Two-arm experiment (lexical baseline vs resource-enriched hybrid)
  over the frozen corpus with a clean contract boundary
  (load_rule_pack(use_resources=...) / candidates(enrich=...)).
- Verdict: NO MATERIAL BENEFIT — Δcorrect=0, Δincorrect=0, Δmissed=0
  on 33 units; determinism verified (identical repeated hashes).
- Finding: the frozen corpus is structurally blind to the resource
  boundary; isolation tests prove the arms differ (coin: UNSUPPORTED
  vs FOUNDED/CREATED). Corpus v1.1 (resource-expanded triggers,
  multi-sense disambiguation) is the gating artifact for the
  hybrid-default decision.


## 2026-08-14: Phase H v1.1 — boundary corpus freeze and rerun (REJECT)

- Corpus v1.1 (33 items, sha256 3ee7065a…) additive to the v1.0
  control; exercises the arm boundary: 11 expanded positives, 3
  class-breadth traps, 11 polysemy contrast items, passive-with-parse,
  ARG1→ARG2, assertion controls, alignment-gap, structural cohorts.
- Rerun verdict: REJECT — Δcorrect=+1, Δincorrect=+4, Δmissed=-4.
  VerbNet class expansion recovers 6 facts (created/acquired/uses) but
  asserts 4 wrong edges (3 traps + 1 oblique pairing) and the FN anchor
  filter suppresses 2 correct developed facts.
- Named mechanisms for the next measured experiments (NOT applied):
  expanded-trigger roleset constraint; composed-FN filter relaxation.
- Production extraction code unchanged; harness-only fixes recorded per
  the bug protocol; determinism verified across three runs per arm.

## 2026-08-14: Phase G1 — document semantic routing + retrieval primitives

- Document RetrievalProfile (bottom-up, deterministic, no LLM) with
  coverage accounting; the `profile_document` stage brings the census
  chain to six stages.
- Three parallel retrieval lanes — document router, parent router,
  global child — fused by reciprocal-rank fusion; document routing is
  never a recall gate (a child hit survives a zero-scoring document).
- POST /retrieve returns the routing trace: document ranking with
  reasons, parent hits, child evidence, bounded graph expansion
  (2 hops, high/medium-weight predicates only).
- Cross-domain acceptance: the validation query discovers Loop
  Engineering, Predicate Compiler, and Prompt Graph as complementary
  sources; unrelated filler stays out of the top ranks.

## 2026-08-14: Phase G2 — embedding contracts, dense lane, frozen G1

- The G1 cross-domain trace is frozen as a golden behavioral test.
- Frozen embedding contracts: content-hash contract ids, representation
  kinds, no backend field; hash-embed-v1 retained permanently as the
  zero-model test contract; neural contract pins
  Qwen/Qwen3-Embedding-0.6B @ 97b0c614be4d; the embedder sidecar is
  implemented host-native with a real /ready probe.
- Four independently inspectable lanes (document / parent / child dense
  / child lexical) with per-hit representation provenance; fusion stays
  rank-based RRF; a contract bump is a new index version, never a
  mutation.
- Receipt semantics: append-only projection_attempts + active claim
  flag — verification supersedes claims, never erases history.
- Qdrant moved to host port 6334; the live v3.3 stack on 6333 is never
  touched.

## 2026-08-15: E2/C1.1 production — entity admission boundary + bidirectional hop1

- Entity admission (qualified 2026-08-14, 100% gold + downstream G4
  PASS) is now production behavior at the identity allocation point:
  GLOBAL / CORPUS_SCOPED / DOCUMENT_SCOPED / MENTION_ONLY reference
  classes with a new identity contract (entity-identity-v2, migration
  0007 entities.admission_class). GLOBAL ids remain byte-compatible
  with canonical_entity_id.
- MENTION_ONLY mentions keep a stable evidence id, are persisted in
  Postgres, and are never projected as Neo4j Entity nodes; facts with
  a MENTION_ONLY endpoint are parked as unresolved evidence (Postgres
  authority, no graph edge). Generic hubs (the system / the model /
  the platform) can no longer enter the graph.
- Canonicalization input excludes DOCUMENT_SCOPED (doc-local
  identities never merge across documents) and MENTION_ONLY.
- Graph expansion promotes to the G4-measured canonical bidirectional
  hop1: two directed clauses inside one CALL () subquery, dedupe by
  fact_id, ORDER BY fact_id, LIMIT 20. An incoming edge only makes the
  EXISTING fact eligible — orientation is never invented. The frozen
  q09 generic-seed criterion no longer applies (generic surfaces
  cannot exist as graph nodes); G4.2 remains rejected as defense in
  depth.
- Compiler authority unchanged; Q1 frozen extraction qualification
  untouched (harness source-compatible via default corpus_id).

## 2026-08-15: D3 — typed evidence support lanes (TEXT / GRAPH, contracts v2)

- The EvidenceBundle and answer synthesis contracts bump to v2 with
  two INDEPENDENT typed support lanes: GRAPH (compiler/expanded fact
  claims) and TEXT (document summary, section summary, child chunk,
  lexical/dense retrieval evidence).
- Either lane supports an answer independently; graph evidence
  augments text and never gates it. Abstention only when both lanes
  are empty. Text claims are verbatim, fail-closed passages with
  exact locators; no special-case fallback and no generator.
- Live smoke corpus: all six gate queries now answer with cited
  in-corpus passages (zero foreign citations); the vague "system"
  query gains no graph authority.

## 2026-08-15: I1 — manifest-driven bulk ingestion (ADR 0013)

- Versioned closed-schema manifest (YAML, contracts/ingestion/v1)
  declares what should be ingested; paths resolve relative to the
  manifest; duplicate sources and unknown fields fail validation;
  manifest identity is order-stable (canonical semantic hash) and
  distinct from document content identity and run identity.
- Planning is read-only and derives actions from authoritative
  Postgres state; execution submits intake work through the ONE
  shared intake writer (POST /intake now delegates to it — the
  single-document path is unchanged); RETRY re-arms failed runs'
  outbox events without mutating stage history or receipts.
- CLI: scripts/ingest.py (plan/run/status) + make ingest-plan /
  ingest-run / ingest-status. Batch-bounded, resumable, idempotent
  (replay submits nothing). Deletions are explicitly deferred:
  manifest absence is never deletion authorization.

## 2026-08-15: I2 — corpus-scale integrity qualification (FAIL: queryability)

- Frozen 28-document multi-format qualification corpus + 4-document
  isolation corpus (tests/fixtures/i2/) with phase-based verifier
  (eval/i2/verify_i2.py).
- PASS: convergence (28/28 query_ready, 0 retries), eligibility-aware
  durable census, admission scale census, generic-hub check, identity
  invariants on persisted rows, corpus isolation, replay idempotency.
- FAIL (frozen, unpatched): TEXT lane returns 96 cited passages for
  an unsupported query — every retrieved passage counts as supported
  text evidence with no deterministic support bound. Owning layers
  recorded; fix deferred to a future change (D4), not started.
- Qualification only: no production behavior changed.

## 2026-08-15: D4 — TEXT support admission qualification (REJECT)

- Frozen D4 development set measured against the frozen retrieval+G3
  pipeline: no existing signal (dense, lexical, G3 rerank) separates
  answer support from topical relatedness; same-domain negatives
  outscore true positives; query-level threshold interval is empty.
- Verdict: REJECT — no text-support policy implemented; no
  threshold picked; no heuristics invented. An answerability model
  track is a pending user decision. I2 skipped gates remain unrun.

## 2026-08-15: D4.1 — answer-support model qualification (REJECT)

- Frozen 794-pair support qualification set; four deterministic
  candidates measured (NLI DeBERTa xsmall/base, QNLI distilroberta/
  electra). NLI is task-misaligned (recall ≈ 0). QNLI separates the
  bulk of negatives (p50 0.01-0.03 vs SUPPORTS p90 0.98) and runs at
  ~0.5-1.4 ms/pair, but no threshold reaches defensible precision
  (max 0.80 at R=0.09; contradiction pairs score as support; abstract
  term hallucination; one answerable query fails outright).
- Verdict: no candidate promoted; no production wiring. A 3-way
  supports/topic_only/contradicts classifier (fine-tune) is a pending
  user decision.

## 2026-08-15: R1A — deterministic summary routing substrate

- ONE canonical retrieval-summary contract (retrieval-summary-v2):
  coverage-preserving DOCUMENT_RETRIEVAL_SUMMARY and per-child
  SECTION_RETRIEVAL_SUMMARY, deterministic + source-derived, with
  versioned content identity (summ_<hash>) and per-sentence
  provenance; persisted authoritatively (migration 0008).
- Qualified the existing pinned neural embedding contract
  (Qwen3-Embedding-0.6B @ 97b0c614…, 1024-dim, sidecar verified);
  routing points projected under the neural contract in a separate
  collection with explicit representation_kind
  (document_summary / section_summary / child) — hash vectors are
  never semantically confused with neural vectors.
- Qualification: coverage fixture (v2 beats v1: concepts 0.870 vs
  0.837, section themes 0.778 vs 0.657, late content 0.889 vs 0.667,
  zero redundancy, no fabrication); frozen routing set (doc routing
  R@1 0.609→0.826, MRR 0.714→0.878; section routing R@1 0.652→0.696,
  MRR 0.736→0.805; global child control R@5 0.957). Rebuild
  deterministic. No control plane built (no RRF/FAST/HYBRID/GRAPH/
  MMR/Pass-2).

## 2026-08-15: R1B — summary-led Pass-1 retrieval

- Versioned Pass1RetrievalPlan (pass1-retrieval-v1) + deterministic
  engine: three corpus-filtered neural searches over the qualified
  routing projection (document_summary / section_summary / child) →
  RRF k=60 with per-lane contributions → explicit DocumentCandidate
  aggregation → bounded document/section resolution → filtered child
  deepening (corpus+doc+parent) → global-child rescue (recall safety)
  → dedupe → G3 (candidate-set invariant) → bounded hierarchical
  evidence. Routing summaries never become exact evidence.
- Reconciliation closed: verify + census cover routing receipts —
  neural routing points cannot silently disappear from a query-ready
  corpus.
- Qualification (frozen 34-query set): F = DOC R@1 0.882 / CHILD R@5
  0.971 / MRR 0.900, final-evidence recall 0.941; rescue improves
  0.912 → 0.941; G3 order-only; filter verification clean; cross-
  corpus isolation 0 leaks; deterministic; lanes ~8-15ms p50.
- No FAST/HYBRID/GRAPH exposure, no support classifier, no synthesis
  change (D4/D4.1 stand).

## 2026-08-15: R1C — FAST production route

- Versioned retrieval-mode contract (retrieval-mode-v1): FAST maps to
  the qualified pass1-retrieval-v1 plan; LEGACY retained explicitly
  as the frozen regression default; HYBRID/GRAPH not exposed.
- /retrieve, /evidence, /chat accept mode=FAST and consume ONE
  Pass-1 result (orchestrator/api/fast.py wraps the shared engine).
  FAST: neural routing only (no hash fallback), explicit readiness
  (query_ready + populated routing projection), loud 502 semantics,
  hierarchical trace, bounded evidence (graph lane empty by contract).
- Parity: repeated-request 0 mismatches; doc R@1 0.882 matches R1B;
  final-evidence recall 0.971 (R1B 0.941); latency p50 659 ms.
- Suites + guards green; frozen legacy golden contracts untouched.

## 2026-08-15: R1D — HYBRID retrieval (FAST + lexical; MMR REJECTED)

- HYBRID mode (hybrid-retrieval-v1) reuses the FAST engine: an
  independent corpus-filtered lexical child lane (exact terminology)
  joins the three neural lanes in four-lane RRF (k=60); lexical
  rescue arrival; bounded evidence; G3 invariant. FAST unchanged
  (R1C parity re-verified).
- Document-level MMR qualified over the frozen lambda grid
  {1.0, 0.9, 0.8, 0.7} using qualified document-summary vectors:
  every lambda<1.0 damages supporting-child recall (0.938→0.917;
  1.0→0.979) without improving doc R@1 → MMR REJECTED; production
  HYBRID = FAST + lexical, lambda 1.0 documented.
- Qualification (frozen 48-query set): FAST doc R@1 0.875/MRR 0.904
  vs HYBRID 0.896/0.935 (R@5 1.0); final evidence recall 0.938→1.0;
  52 lexical rescues; 2 lexical-exclusive gold children;
  composition readiness ok; isolation 0 leaks; deterministic.
- /retrieve, /evidence, /chat expose mode=HYBRID through one path.
  Suites + guards green.

## 2026-08-15: R1E — Pass-2 corpus reach qualification (REJECT)

- corpus-reach-v1 engine: Pass-1 document exclusion at retrieval
  time, deterministic Pass1ConceptState (generic-seed guard),
  summary-led reach lanes + optional lexical lane, RRF, section
  resolution, filtered deepening, G3 invariant, bounded reach budget,
  DIRECT vs CORPUS_REACH provenance, no recursion.
- Frozen 12-query qualification: query-only reach precision@3 0.056;
  ConceptState adds ZERO over query-only; lexical reach reaches
  precision 0.111 / child recall 0.333. Mostly redundant/topic-
  adjacent results; complementary docs not retained for 9-10/12
  queries. Pass-1 parity + determinism + isolation verified.
- Verdict: REJECT — no production exposure; HYBRID remains
  direct-only. Complementarity signal options are a future user
  decision (no LLM expansion used).

## 2026-08-15: R1F — production GRAPH mode

- GRAPH (graph-retrieval-v1) = promoted HYBRID + the D2-qualified
  evidence-authorized corpus-authorized bidirectional hop1 (8
  seeds / 20 facts, HIGH_MEDIUM, SPO preserved). One GRAPH result
  feeds /retrieve, /evidence, /chat.
- Hierarchical synthesis context: document summaries + section
  summaries as routing context, child chunks as exact evidence,
  graph facts as the GRAPH_RELATIONSHIPS lane — never conflated;
  synthesis untouched.
- Qualification (frozen 48-query set): HYBRID parity 0 mismatches;
  all facts corpus-authorized + SPO-exact + bounded; deterministic;
  0 isolation leaks; graph increment ~10ms (p50 7.3ms) over HYBRID
  p50 637.6ms. Suites + guards green. R1E remains frozen negative
  (no corpus reach).

## 2026-08-15: R2 — hierarchical synthesis audit (STOP: no generation model)

- Step-1 audit frozen (eval/r2/AUDIT.md): synthesis is
  deterministic-template-v2 only — no generative model, provider
  client, or model pin exists; hierarchy does not survive into the
  flat bundle; summaries/children distinguishable but validated
  identically; no composition stage; contradictions represented,
  never arbitrated.
- R2 §7 hard gate: GENERATION MODEL CONTRACT = MISSING → STOP.
  No implementation; retrieval frozen; model selection deferred to
  an explicit user decision.

## 2026-08-15: E3 — GLiNER-only local ingestion qualification (PASS)

- Frozen 14-doc multi-domain/multi-format corpus + 13-phase
  verifier. Proven: pinned GLiNER (40ec4193, mps, tofu digest) is the
  ONLY learned extraction model; golden path converges and replays
  idempotently; production evidence pass is lexical (hybrid GLiNER
  evidence pass NOT re-enabled); deterministic; Qdrant/Neo4j
  reconstruction exact; versioning/isolation/interrupt-resume pass;
  GLiNER outage fails loudly with no fallback and no silent
  query_ready.
- Quality findings recorded with ownership: low yield on realistic
  prose (compound misses), and wrong-edge cases from title-as-entity
  GLiNER proposals + compiler surface-weak pairings. Not patched
  (future qualified change).

## 2026-08-15: E3B — extraction quality repair (endpoint-binding gates)

- Deterministic compiler binding gates (endpoint-binding-v1,
  toggleable via POLYMATH_BINDING_GATES, default ON, pinned in the
  extract contract): relation-specific trigger evidence (has_role
  role inventory + noun-trigger rejection under surface_weak; owns
  control-lemma requires attachment; instance_of org-object requires
  specific phrasing), title/body pairing restriction,
  coordination-aware clause binding, surface-weak locality.
- On the two frozen documents: wrong edges 4 -> 0; all frozen
  negative controls eliminated; positive controls survive.
- Q1 gates-ON = EXACT frozen baseline (50/3/3, P/R 0.9434) — zero
  regression (lock added). Entity recall audit recorded honestly:
  GLiNER medium-v2.1 misses lowercase abstract compounds (ownership
  GLiNER_DISCOVERY, unpatched). No new learned model.

## 2026-08-15: E4 — entity recall failure analysis (measurement only)

- Psychology concepts missed by GLiNER medium-v2.1 are invisible at
  every measured threshold (0.3-0.6) and under all evaluated label
  schemas and label guidance: ownership GLiNER_DISCOVERY (model
  proposal surface favors capitalized/concrete spans). Boundary-class
  failures recorded separately (sibling/adjacent spans). Cyber
  misses are acronyms/compounds (discovery) plus adjacent-span
  boundaries.
- Recommendation: accept the discovery limitation; the only
  deterministic lever is a future span-normalization study (not
  attempted). No production change; frozen labels/threshold/model.

## 2026-08-15: E5 — deterministic concept candidate layer (analysis)

- Analysis frozen (eval/e5/ANALYSIS.md): a deterministic concept
  layer is architecturally safe for GRAPH precision by structural
  separation (retrieval-only sink — it can never create entities,
  facts, admission decisions, or graph edges) and recall-positive at
  the concept level (20-line deterministic noun-phrase prototype
  recovers 6/13 abstract concepts vs GLiNER's 2/13; 12/13 strings
  literally present in the text). The open qualification is SUMMARY
  precision, measurable with the frozen R1B routing set + R1A
  coverage fixture. R1E's ConceptState rejection does not transfer
  (different sink: pass-1 summary enrichment vs pass-2 expansion).
- No implementation; recommendation recorded (E5B pending user
  authorization).

## 2026-08-15: E5B deterministic concept inventory (part 1)

- `shared/polymath_shared/concept_inventory.py`: pure deterministic
  concept extraction for retrieval metadata (`concept-inventory-v1`,
  `routing-concept-enriched-v1`). No runtime owner, no persistence, no
  model dependencies. Concepts never feed entities/facts/graph.
- Frozen qualification docs extended with `eval/e5b/corpus/youtube.md`;
  evidence + report in `eval/e5b/`; 10 pure determinism tests.
- Retrieval `retrieval-summary-v2` untouched; experimental Qdrant
  collections deferred to part 2 (routing A/B vs R1B 0.882).
  (work log `2026-08-15-e5b-concept-inventory.md`)

## 2026-08-16: E5B part 2 routing qualification — REJECT

- Frozen routing A/B on the re-ingested I2 corpus: candidate
  (retrieval-summary-v2 + concept-inventory-v1 under
  routing-concept-enriched-v1, disposable collections
  routing_document_summary_concept_e5b /
  routing_section_summary_concept_e5b) vs baseline. Harness reproduced
  the frozen R1B numbers exactly; candidate doc/sec R@1 0.882 -> 0.853
  (one query each; both real regressions psychology), R1A coverage
  unchanged, graph/extraction/Neo4j zero-delta, determinism green.
  Verdict REJECT; no production integration, no tuning.
  (work log `2026-08-16-e5b-routing-qualification.md`)

## 2026-08-16: E5 track closeout — CLOSED

- E5 closed with two distinct findings: the deterministic concept
  candidate primitive (`concept-inventory-v1`) is preserved as
  qualified experimental research infrastructure with NO production
  use; the concept-enriched routing representation
  (`routing-concept-enriched-v1`) is REJECTED (frozen A/B: R@1
  0.882 -> 0.853, psychology regressions, coverage unchanged).
- Production architecture unchanged in every lane (entity/graph:
  GLiNER + admission + E3B gates + compiler; retrieval:
  retrieval-summary-v2 + Qwen3 embedding + FAST/HYBRID/GRAPH).
- E5C hypotheses frozen as unauthorized future research; preferred
  future shape is rank fusion of independent lanes, not concatenated
  single-embedding enrichment.
  (work log `2026-08-16-e5-track-closeout.md`)

## 2026-08-16: I3R repository-realigned extraction + control-plane repair

- Rule pack v1.2.0 becomes the production default: typed trigger
  contract (the compiler tests only the lexical arm that authorized a
  trigger), bounded verb-form matching, uses noun triggers moved to
  multiword constructions, founded restricted to Organization objects.
- build_candidates: trigger-scoped surface argument frames replace
  the left×right Cartesian product; predicate-region coordination
  boundaries; bounded entity lists; type-compatible nearest slots;
  bounded definite-description reference resolution.
- Durable mentions (migration 0009): every accepted GLiNER proposal
  persists with provenance; factless referential entities durable;
  graph stays fact-driven.
- Verifier orphan semantics realigned (deletion requires no
  authoritative source); in-flight projections kept; query_ready is
  revocable via invalidate_corpus_projections; census re-drives
  missing neo4j receipts.
- exact-evidence-v1 provenance (migration 0010) + real GLiNER pins in
  the extract manifest + unresolved-pin guard.
- I3 rerun: false facts 8→0; reconstruction hash-equal; retrieval
  30/30; Q1/E3B locks byte-identical. I3 is a repair regression —
  production acceptance requires a fresh I4 holdout.
  (work log `2026-08-16-i3r-repair.md`)

## 2026-08-16: I4 fresh heterogeneous acceptance — FAIL (no production change)

- Frozen capability matrix derived from executable config, fresh
  five-document corpus + three-class fact gold + four-tier entity
  gold. Control plane/durability/provenance/graph/retrieval gates all
  green on the fresh holdout; fact extraction FAILS the frozen bar
  (P 0.500 / R 0.385 vs >=0.95 / >=0.70) driven by GLiNER fresh-domain
  span boundary/typing behavior and a leads/has_role shared-trigger
  emission surface. No repairs performed.
  (work log `2026-08-16-i4-fresh-acceptance.md`)

## 2026-08-16: SYNTAX-BOOTSTRAP — spaCy syntax sidecar (install + wire only)

- Explicitly authorized infrastructure gate: `sidecars/spacy_runtime/`
  (own isolated venv — spaCy/Thinc never enter the root GLiNER venv),
  spaCy 3.8.15 + en_core_web_sm 3.8.0 + thinc-apple-ops 1.0.0 pinned;
  NER disabled at load and asserted absent at startup, in /health, and
  in /ready. GLiNER remains the only entity/relation proposal model.
- New versioned wire contract `syntax-evidence-v1` (batched tokens +
  noun chunks, offsets relative to the supplied sentence text,
  offset-invariant enforced server-side) served on :8744 as
  sidecar-cpu; registry entry + launchd unit + digest-pinned manifest
  (no TOFU placeholder).
- Optional `SpacySyntaxClient` wired into the extract worker between
  the GLiNER passes and build_candidates, behind
  `POLYMATH_SYNTAX_PROVIDER` (default `disabled`): disabled is
  byte-identical production; enabled + unavailable sidecar fails
  loudly. Syntax evidence attaches to SentenceSlice for a future
  reconciliation layer; nothing downstream consumes it in this gate.
- SPACY_BACKEND=apple|cpu switches float backends explicitly via
  thinc set_current_ops (reported in health, never silent).
- Q1/E3B/I3R regression locks unchanged with the provider disabled.
  (work log `2026-08-16-syntax-bootstrap.md`)

## 2026-08-16: I4R-A boundary reconciliation (flag-gated, default off)

- Explicitly authorized I4R umbrella gate, first staged sub-gate.
  spaCy noun chunks (determiner-trimmed) align against pass-1 GLiNER
  spans over the same sentence slices; a span strictly inside a larger
  argument NP is re-queried at the existing pinned GLiNER sidecar via
  a new additive batched POST /rescue (same model/revision, frozen 0.5
  threshold; /infer untouched). Acceptance is exact-full-span-only
  (start==0, end==len, same label). Accepted -> the argument binds to
  the expanded span; refused -> BOUNDARY_UNRESOLVED: the original
  proposal stays durable, the fact abstains. No deterministic
  promotion.
- New flag POLYMATH_RESCUE (off | on | stage list); default off keeps
  the stage contract hash byte-identical. Rescue provenance records
  deterministic request identities (rescue-v1|kind|revision|
  threshold|text|ordered labels).
- work log `2026-08-16-i4r-a-boundary.md`; measurement in
  `eval/i4r/REPORT.md`.

## 2026-08-16: temporal extraction architecture alignment

- semantic-query-policy-v1: canonical types -> provider-facing label
  vocabulary resolved through a versioned policy; domain-module label
  table relocated to the policy; raw provider labels + pass_kind +
  query_policy_version preserved on every mention (migration 0011);
  ExtractionManifest carries the query policy. Compiler/predicates
  cannot see provider aliases (guarded by test).
- Extraction contract identity now always includes query policy,
  syntax contract, and rescue policy (incl. disabled state): every
  interpretation is reproducibly attributable; upgrades follow the
  observe->freeze->version->reprocess->diff->evaluate->promote
  lifecycle with disposable projections rebuilt from authority.
- Label-vocabulary sensitivity recorded as probe evidence (experiment
  0005); alias adoption requires a named GLINER-QUERY-VOCAB gate.
- I4R staged repair plan paused at A (implemented, flag-gated OFF,
  unmeasured) pending explicit authorization; no acceptance test run.
  (work log `2026-08-16-temporal-extraction-architecture.md`)

## 2026-08-16: TEMPORAL-INTERPRETATION-V1 recorded as deferred gate

- Alignment status: complete-with-one-deferred-durability-gap.
  Version attribution exists (contract identity in receipts);
  first-class interpretation versioning — (source_content_version,
  extraction_contract_hash) = interpretation owning mentions/entities/
  facts/evidence/canonicalization/projection eligibility, with
  promotion selecting the current interpretation — is a NAMED
  DEFERRED production gate, required before the first real
  model/query-policy upgrade. Not built now to protect I4R.
  (work log `2026-08-16-temporal-interpretation-deferred.md`)

## 2026-08-16: I4R-A boundary reconciliation measured on frozen I4

- First staged I4R measurement (development regression): P 0.500 ->
  0.625 (+0.125), R 0.385 unchanged; envelope 7/8, must-not 18/18,
  provenance 15/15 exact. 15 boundary candidates, 2 GLiNER-confirmed
  expansions, 13 refused -> BOUNDARY_UNRESOLVED abstentions (FP 10->6).
  Reproduced twice; frozen artifacts hash-verified and byte-restored.
- Provenance repair discovered by the measurement: stage artifacts
  merged instead of first-write-wins (manifests had been swallowing
  audit/syntax/rescue evidence since inception); regression-tested.
  (eval/i4r/REPORT.md, work log 2026-08-16-i4r-a-boundary.md)

## 2026-08-16: I4R-B missing-argument rescue measured on frozen I4

- Cumulative (A+B): P 0.667 (baseline 0.500), R 0.462 (baseline
  0.385); envelope 7/8, must-not 18/18, provenance exact. Normal-
  vocabulary queries per temporal directive §10; quantified NPs
  excluded as non-referential (B07 audit -> general rule).
  (eval/i4r/REPORT.md, work log 2026-08-16-i4r-b-missing-argument.md)

## 2026-08-16: I4R-C type reconciliation measured (zero delta, precision-safe)

- Slot-incompatible entities re-queried over their argument NP with the
  normal vocabulary; only slot-legal full-span answers re-type. Frozen
  I4: 9 candidates, 0 applied (none slot-legal), bar unchanged
  (P 0.667 / R 0.462 cumulative). (eval/i4r/REPORT.md)
