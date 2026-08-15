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
