# Architecture changelog

Dated diffs of every architectural change. Each entry links to the ADR
that motivated it and the refactor that implemented it.

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
