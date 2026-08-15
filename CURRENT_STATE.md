# Current Repository State

Last verified: 2026-08-14
Verified against commit: `1b11662` (roadmap restored: entity-architecture escalation stopped; evidence chain frozen)
Active branch at verification: `main` (working tree clean)

```yaml
current_phase: g3-verdict-recorded # G3 reranking gate PASS (candidate, not default); next = G5/G4 per roadmap
repository:
  branch: main
  head: 1b11662
  frozen_artifacts: [see Frozen Artifacts section]
  evaluations: [experiment-0001, experiment-0002, phase-h-v1.0, phase-h-v1.1, qualification-q1, q1r-validation, ep1, em1, sr1]
  next_actions: [g5-evidence-assembly, g4-scale-qualification, i1-bulk-ingestion]
  do_not_do: [see Explicitly Prohibited Actions]
  known_gaps: [see Known Limitations]
```

## System Status

- **Build pipeline**: `preflight ok`, `repo guard ok`, `wiki ok` (verified at the commit above).
- **Unit tests**: 152 passed, 22 skipped (skips = integration / neural-gated gates) — verified.
- **Integration tests**: 19 passed, 2 skipped (`POLYMATH_INTEGRATION=1` + live stores; Qdrant on 6334, Neo4j on 7688, Postgres on 5432) — verified.
- **Extraction verdict**: hybrid resource enrichment **REJECTED as production default** (Phase H v1.1: Δincorrect = +4 > 0). The lexical lane remains the production default.
- **Q1 qualification verdict: PASS** (frozen report `eval/q1/REPORT_Q1.md`): production lexical arm P/R 0.943 on the 53-item heterogeneous corpus; 0 wrong-predicate, 0 wrong-scope; every residual failure is a catalogued class; pipeline E2E clean with real GLiNER. **Production extraction is qualified. Further extraction changes require a demonstrated regression or separately measured improvement.**

## Current Architecture

Six process roles (`AGENTS.md` §1): orchestrator / worker / sidecar-gpu /
sidecar-cpu / store / control. Authoritative files: `ARCHITECTURE.md`,
`architecture/dependencies.json`, `AGENTS.md`. ADRs: `docs/wiki/decisions/`
(0000-template, 0001 GLiNER two-pass, 0002 Postgres-not-Mongo,
0003 no-GPU-in-Docker, 0004 control-plane-separate-process,
0005 sidecar-contract, 0006 packaging-deployment, 0007 lexical evidence
lane, 0008 evidence-pass boundary).

Production path per run (census-driven, eight stages; Q1 reorder:
canonical projection precedes verification):
`intake → extract → profile_document → project_qdrant → project_neo4j →
canonicalize → project_canonical → verify_projections`, with receipts
as the commit point (one Postgres transaction: artifact + receipt +
status + outbox event).

## Production Components

- Orchestrator FastAPI: `/intake` (idempotent: same canonical input →
  same `run_id`), `/runs/{id}`, `/retrieve`, `/health`, `/ready`, `/sidecars`.
- Workers: intake, extract, profile_document, project_qdrant,
  project_neo4j, verify_projections (all queue-driven, lease-safe, fault
  injection for crash tests only under `POLYMATH_TEST_CRASH_*`).
- Control plane: separate process; Postgres lease + desired-state census
  + outbox re-arm; heartbeats.
- GLiNER runtime sidecar: pinned `urchade/gliner_medium-v2.1` @
  `40ec419335d09393f298636f471328b722c6da9e`; entity pass only;
  `/ready` performs a real forward pass.
- Embedder sidecar: pinned `Qwen/Qwen3-Embedding-0.6B` @
  `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` (neural embed contract,
  G2); `/ready` performs a real forward pass.
- Deterministic predicate compiler: 28-rule pack v1.0.1, compiled
  against real VN/PB/FN/SemLink tables (contract below).
- Stores: Postgres (workflow authority), Qdrant + Neo4j (disposable
  projections with destructive-reconstruction guarantees), Redis
  (notification only).

## Experimental Components

- **Hybrid evidence proposal mode** (`POLYMATH_WORKER_EVIDENCE_PROPOSAL_MODE=hybrid`):
  ADR-0008. NOT the default. Measured on v1.1 and rejected as default
  (see evaluations). Default is `lexical`.
- **Neural dense retrieval lane** (G2): implemented and tested
  (POLYMATH_NEURAL_EMBEDDER=1); usable, not a production default.
- **Reranker sidecar**: scaffold stub only (G3 not implemented).

## Ingestion State

- Chunking is **sentence-aligned structural chunking** (child ≤1200
  chars, parents of 4 children). **There is no semantic chunking** in
  this repo — chunk boundaries are structural; semantic layers exist
  above the chunks (parent summaries, document retrieval profile, dense
  child vectors). Changing this requires an ADR + requalification.
- Chunk identity is content-hashed (`sha256(doc_id|index|text)`);
  re-chunking unchanged text is a no-op.
- Parent summaries and the document RetrievalProfile are deterministic
  extractive — **no LLM anywhere in the ingestion layer**.
- No-LLM ingestion is an invariant of this repository.
- **Native document materialization (I0, ADR 0010)**: intake
  materializes PDF/EPUB/DOCX/TXT/MD/HTML deterministically
  (`shared/polymath_shared/materializer.py`) into normalized text +
  a structural source map (page/chapter/section/paragraph) persisted
  on `documents.source_hash` / `materialization` / `source_map`
  (migration 0006). Failures are typed and LOUD (never a silent empty
  document); one new dependency (`pypdf`). The extract worker consumes
  the authoritative Postgres chunks. TXT behavior is byte-stable vs
  the Q1-qualified path. The citation chain is now
  fact → evidence → chunk offsets → source-map → page/chapter.

## Retrieval State

- G1 (document routing profiles + three parallel lanes + RRF fusion)
  and G2 (embedding contracts, neural dense lane, four-lane ablation)
  are implemented; the G1 golden trace is frozen as a behavioral test
  (Loop Engineering rank 0, Predicate Compiler rank 1, Prompt Graph
  rank 2; filler excluded).
- Document routing is **never a recall gate** (tested invariant).
- **R3a (grounded EvidenceBundle assembly)**: implemented — POST
  /evidence (orchestrator) + deterministic assembler in
  `shared/polymath_shared/evidence_assembly.py`, contract
  `contracts/answer/v1/evidence_bundle.schema.json`. Claim items carry
  fact/entity IDs, source document + span locator, provenance,
  epistemics, applicability, retrieval lane; evidence-only items never
  carry claims; unresolved references / missing provenance fail loudly
  (502). Live E2E verified.
- **R3b (grounded answer generation + /chat)**: implemented — POST
  /chat runs the R3a bundle through a deterministic
  propose→validate→render pipeline
  (`shared/polymath_shared/answer_synthesis.py`, contract
  `contracts/answer/v1/chat_response.schema.json`). The validator is
  the trust boundary: supports must resolve to real bundle items,
  fabrication tokens are rejected, conflicts are represented (never
  arbitrated), epistemic scope survives, insufficient evidence
  abstains. Live E2E verified (cited grounded conflict answer).
- **Not implemented** (critical path now): C1 Stage-2 corpus
  canonicalization, C2 canonical KG, R2/G3 reranking (bypassable
  initially), R4 scale qualification. See `RAG_E2E_CHECKLIST.md` for
  the full critical path.

## Knowledge Extraction State

- **Stage 1 (document-local)**: implemented and production — GLiNER
  entity proposal → deterministic candidate generation → lexical trigger
  localization → real-resource lookup → deterministic compiler →
  facts + evidence + provenance (rule id, rule version,
  `resource_contract_id`, `compiled_lexical_sha256`, roleset/VN/FN,
  `semlink_resolved`).
- Evidence-pass boundary (ADR-0008): GLiNER pass 2 proposes coarse
  evidence (may abstain on the pinned model); the lexical lane
  localizes triggers; resources constrain; the compiler decides.
- **Stage 2 (corpus-level canonicalization): implemented (C1, ADR
  0009).** The `canonicalize` stage maintains a deterministic corpus
  registry (`canonical_entities`, `canonical_memberships`,
  `canonicalization_decisions`, migration 0005) that ADDS canonical
  identities on top of source-local entities — local entity/fact/
  evidence rows are never mutated. Conservative policy: SAME_AS only
  on normalized-exact-name + compatible type + mergeable class;
  ALIAS_OF only on explicit corpus-profile declarations; DISTINCT on
  incompatible types; homonym-risk classes abstain. Canonical ids are
  content hashes (order-independent, replay-safe, incremental delta).
- **Stage 2 canonical KG projection: implemented (C2).** The
  `project_canonical` stage projects the registry into Neo4j:
  `CanonicalEntity` nodes (C1 ids verbatim) +
  `HAS_MEMBER` edges carrying decision/confidence/basis/version +
  `Evidence-[:FROM_CHUNK]->Chunk` source links. Rebuildable from
  Postgres; replay no-op; incremental delta; orphan detection and
  census re-arm live-proven. Neo4j never decides identity; no
  synthetic facts; conflicts stay distinct.
- The 28-predicate rule pack is frozen at v1.0.1; changes require a
  measured delta (see Prohibited Actions).

## Knowledge Graph State

- Neo4j is a disposable projection of Postgres facts (constrained MERGE,
  uniqueness constraints, one `REL` edge per `fact_id`).
- VERIFY_PROJECTIONS reconciles store vs receipts; store loss clears
  claims (never erases the append-only `projection_attempts` history);
  orphan detection is fail-loud (degrade → census re-drive).
- Traversal policy: high/medium-weight predicates only for expansion;
  `ASSOCIATED_WITH` excluded except as terminal; 2-hop cap.
- No community/summary layer over the graph (not built).

## Current Evaluation Results

All results are frozen evidence — see `eval/phase_h/REPORT.md`,
`eval/phase_h/REPORT_v1.1.md`, `docs/wiki/experiments/0001-*.md`,
`docs/wiki/experiments/0002-*.md`.

| Evaluation | Corpus | Verdict | Key numbers |
|---|---|---|---|
| exp 0001 GLiNER evidence pass | probe text | REJECT | medium-v2.1: zero usable evidence spans at any threshold; multitask-large fires with entity-style spans |
| exp 0002 compiler recovery | relations_v1 (frozen fdfd75b4…) | recorded | compiler on gold inputs: predicate 95.7%, direction 100%, abstention 100%; E2E: P 66.7 / R 60.0 / F1 63.2, duplicates 0, unsupported 28.2% |
| Phase H v1.0 | relations_v1 | NO MATERIAL BENEFIT | Δ=0 across 33 units; corpus structurally blind to the resource boundary; isolation proven (coin probe: baseline UNSUPPORTED vs hybrid FOUNDED/CREATED) |
| Phase H v1.1 | relations_v1.1 (frozen 3ee7065a…) | **REJECT** (hybrid as default) | baseline 25/0/8 vs hybrid 26/4/4; Δcorrect +1, Δincorrect +4, Δmissed −4; 6 recovered facts; 3 class-breadth traps fired; 2 developed suppressions via the composed-FN anchor filter; 1 spurious oblique-pairing edge; polysemy: no sense-gain measured; composed-only cohort n=0 by resource topology |

**Named measured mechanisms (NOT yet fixed — that is deliberate):**
1. Class-expanded triggers are accepted without a roleset/sense
   constraint (the `coin → FOUNDED` trap class).
2. The FrameNet anchor filter over-rejects when a candidate's FN frames
   came from composed PB→VN→FN chains (suppressed 2 correct `developed`
   facts).

**Production impact of Phase H v1.1:** none — production extraction
code was not changed; only harness fixes (oriented-fact recording, union
transition accounting, `--gold` selection, parse/cohort passthrough)
landed, with regression tests.

## Frozen Artifacts

```yaml
- name: corpus_v1_control
  path: eval/gold/relations_v1.yaml
  version: "1.0"
  sha256: fdfd75b499eddab1f353e6ce7c9d2b600d3d0ab226cae8f2e7b06f5419503694
  freeze_reason: control/regression corpus (Phase H v1.0 + exp 0002)
  mutable: false
  change_requires: [ADR or explicit authorization, new corpus version]

- name: corpus_v1_1_boundary
  path: eval/gold/relations_v1.1.yaml
  version: "1.1"
  sha256: 3ee7065acba980cbc61eeccc935774f864b9e677c60652c7f9f357253b5b484c
  freeze_reason: lexical-semantic boundary gate corpus (Phase H v1.1)
  mutable: false
  change_requires: [ADR or explicit authorization, new corpus version]

- name: resource_contract
  path: resources/compiled/03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150/
  resource_contract_id: 03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150
  tables_sha256: 0ac3002ad2a2fcd79e33549faedfdc890f1d0f427852f5ae105f23c1a1ec81f1
  freeze_reason: vendored VN 3.3 + unified PB + FN 1.7 + SemLink 2 flattened tables
  mutable: false
  change_requires: [upgrade procedure in resources/README.md, both-arms rerun]

- name: compiled_rule_artifact
  path: resources/compiled/<contract>/compiled_lexical.json
  rule_pack_version: "1.0.1"
  compiled_lexical_sha256: 5c58adbd3cfc18e2e8b28245d5166dbb2920a33210ca7ccc0051231b421c8806
  mutable: false
  change_requires: [scripts/compile_predicate_rules.py rebuild]

- name: g1_golden_trace
  path: tests/integration/test_cross_domain_routing.py (golden ordering assertion)
  freeze_reason: frozen G1 behavioral trace (Loop 0 / Compiler 1 / PromptGraph 2)
  mutable: false

- name: hash_embed_contract
  path: shared/polymath_shared/embedding_contracts.py (HASH_EMBED_CONTRACT)
  freeze_reason: permanent zero-model deterministic test contract (never deleted)
  mutable: false
```

Resource source pins (immutable commits, sha256-verified archives):
verbnet `9c6f7b949560189d5c72b863ee3cb47da4409a41` (tag vn-3.3);
propbank-frames `c66e0ccf28b53f00051b187db83e937b5bee2e32`;
semlink `2636bf5a4ae9c93b669a1184a8aaae9ca21552d3`; framenet_v17 (NLTK).

**Frozen-data policy:** evaluation failures are fixed in the
implementation or the harness, not by editing frozen gold data after
evaluation begins, unless the established bug protocol explicitly
permits a new corpus version.

## Known Limitations

- W2 candidate generation: no ARG1→ARG2 (theme→result) pairing
  (measured: v11_a01/a02 MISSED in both arms).
- W7 orientation: passive inversion requires a syntactic parse; frozen
  evaluation inputs may lack one (v1.0 a02). spaCy integration is
  optional; without it the compiler marks orientation weak.
- Composed-FN anchor filter over-rejection (measured mechanism #2).
- Class-breadth trap (measured mechanism #1).
- Upstream lexical gaps: 2,047 unaligned SemLink→VN ids (recorded,
  never fuzzy-joined); 2 malformed upstream PropBank XMLs skipped by
  name; composed-only cohort is n=0 by resource topology.
- Embedder + GLiNER weights digests are trust-on-first-use;
  `POLYMATH_REQUIRE_PINNED=0` until production digests are recorded.
- Single-controller lease (multi-controller deferred, PLAN.md).
- G3/G4/G5 retrieval layers and the answer path are not built.
- Stage 2 corpus-level canonicalization + canonical KG projection now
  exist (C1 + C2).

## Open Risks

- The hybrid default decision is gated on the two E1 experiments; until
  they run, do not enable hybrid in production. E1 is DEFERRED measured
  improvement work (not a RAG v1.0 blocker); it returns to the critical
  path only if an E2E acceptance test shows one of the named defects
  blocking the production lexical path.
- Class-expanded triggers can assert wrong predicate senses on
  out-of-vocabulary sentences (measured, unfixed by design).

## Current Workstream

Phase H (empirical qualification) — complete. Extraction architecture
frozen at commit 3ada0af. Milestone A (CORPUS_INGEST_READY): R3a/R3b
COMPLETE, C1 COMPLETE, C2 COMPLETE, Q1 COMPLETE (PASS), I0 COMPLETE → I1 → I2.
Milestone B
(RAG_V1_E2E):
R2 → M1–M5 → R4 → O2 → O1 → A1 → V1. E1-a/E1-b are deferred measured
improvements.

## Measured Extraction Backlog (consolidated, frozen evidence)

Everything below is frozen measurement, not open speculation. Fixes are
prioritized ONLY by demonstrated downstream waterfall/retrieval delta —
never by armchair promise.

1. **E1-a / E1-b** (deferred measured improvements, Q1-frozen):
   class-expanded trigger roleset constraint; composed-FN anchor
   filter. Evidence: `eval/phase_h/REPORT_v1.1.md`.
2. **Realistic-prose entity boundary gap** (EP1/EM1/SR1, all FAIL):
   GLiNER medium-v2.1 cannot seed or repair the multiword concept
   spans long-form prose relations need, at any precision-safe
   operating point; three larger zero-shot models and deterministic
   span repair did not clear the floors. Unrecoverable span classes
   recorded in `eval/sr1/REPORT_SR1.md`. Entity-architecture
   escalation is STOPPED; a future fix requires a demonstrated
   downstream delta under the same frozen protocol (heldout_ep1_v1
   remains untouched and one-shot).
3. **Rule-pack v1.1.0 candidate** (Q1-R): zero drift on all frozen
   corpora, bogus worker->leads class removed, but realistic recall
   not achieved — candidate only, production default stays 1.0.1.

## Next Authorized Actions

MILESTONE A — CORPUS_INGEST_READY (C1+C2+Q1+I0 COMPLETE):

1. **I1**: manifest-driven bulk ingestion controller. BLOCKED on the
   documented realistic-prose entity boundary gap — and I1 is NOT
   authorized to force a new entity-architecture decision. It resumes
   when a deliberate product decision addresses the gap or accepts
   the documented conservative prose coverage.
2. **I2**: corpus-scale integrity run.

CORPUS_INGEST_READY = C1 + C2 + Q1 + I0 + I1 + I2 pass.

MILESTONE B — RAG_V1_E2E (after Milestone A):
R2 (reranker, bypassable) → M1–M5 (MCP) → R4 → O2 → O1 → A1 → V1.

## Deferred Measured Improvement (NOT critical path)

- **E1-a**: class-expanded triggers require resolved-roleset
  compatibility. Hypothesis: `coin`-class traps become abstentions.
- **E1-b**: FN anchor filter must not exclude a rule on composed-only
  frame mismatch. Hypothesis: restores the two suppressed `developed`
  facts.
- Each experiment: fix in code → rerun Phase H harness on frozen v1.1
  → report Δ before/after → only then decide promotion. Production
  defaults change ONLY on a measured precision-first pass.
- Do NOT begin E1 work while critical-path gates are incomplete.

## Explicitly Prohibited Actions

- Change production extraction behavior (compiler rules, trigger
  vocabularies, ontology, thresholds, chunking, predicate set) without a
  measured waterfall delta on frozen corpora.
- Modify frozen corpora (`eval/gold/*.yaml`) after freeze; a defect
  requires a NEW corpus version, never an edit.
- Fuzzy-join or manufacture SemLink mappings.
- Treat composed PB→VN→FN chains as direct attestations.
- Enable hybrid evidence mode or neural dense retrieval as production
  defaults without the measured gates above.
- Introduce an LLM into ingestion/summarization/relation compilation.
- Add GPU services to Docker; add new core tools without the footprint
  ladder; break prompt-caching or transactional-receipt invariants.
- Collapse the four format projections; encode gendered/species
  stereotypes; assert unproven conditioning effects.
- Reintroduce a neural evidence pass on the basis of the original Kimi
  design alone (ADR-0007 + experiment 0001 falsified it on the pinned
  model; a new model requires qualification evidence first).
- Train a model, introduce a decoder-based entity extractor, promote
  span repair, or accept/degrade the entity gate without a measured
  downstream waterfall/retrieval delta under the frozen protocol
  (roadmap restoration 2026-08-14).

## Verification Commands

```bash
git status --short && git branch --show-current && git rev-parse HEAD
make guards                     # preflight + repo guard + wiki worm
.venv/bin/python -m pytest tests -q                 # 77 passed / 15 skipped (verified)
POLYMATH_INTEGRATION=1 \
  POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath" \
  POLYMATH_QDRANT_URL="http://127.0.0.1:6334" \
  POLYMATH_NEO4J_URI="bolt://127.0.0.1:7688" \
  POLYMATH_NEO4J_PASSWORD=polymath-dev \
  .venv/bin/python -m pytest tests/integration -q   # 12 passed / 2 skipped (verified)
shasum -a 256 eval/gold/relations_v1.yaml eval/gold/relations_v1.1.yaml
python3 scripts/verify_resources.py
python3 scripts/flatten_resources.py   # deterministic; same contract id expected
python3 scripts/compile_predicate_rules.py
.venv/bin/python eval/phase_h/harness.py \
  --gold eval/gold/relations_v1.1.yaml --outdir eval/phase_h/artifacts_v1.1
```

Note: Qdrant for THIS repo is on host port **6334** (the user's live
v3.3 stack owns 6333/7474 and must never be touched); Neo4j on 7688.

## Authoritative References

1. `AGENTS.md` (bootstrap + contract)
2. `CURRENT_STATE.md` (this file)
3. `NEXT_SESSION.md`
4. `ARCHITECTURE.md`, `architecture/dependencies.json`, `PLAN.md`
5. `docs/wiki/decisions/` (ADRs), `docs/wiki/work-log/` (append-only),
   `docs/wiki/experiments/`
6. `eval/phase_h/REPORT.md` (v1.0), `eval/phase_h/REPORT_v1.1.md` (v1.1)
7. `resources/README.md` (resource pipeline + upgrade procedure)
8. `scripts/README.md` (managed scripts registry)
9. `RAG_E2E_CHECKLIST.md` (release-gate checklist — next unchecked gate: I1)
