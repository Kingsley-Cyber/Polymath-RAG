# POLYMATH — CODEX ENGINEERING HANDOFF

Written 2026-08-26 · Final agent HEAD `a14d5fd` · branch
`architecture/evidence-first-v5` · tree clean.
This file supersedes all previous session notes as the incoming-agent
entry point. Read top-to-bottom, then verify against code — this
handoff is evidence-based but not exempt from your own reconstruction.

---

## 1. Mission

POLYMATH is an evidence-first RAG / KAG system: ingest real documents,
preserve verbatim evidence, extract durable knowledge artifacts (FACT /
PROCEDURE / CONCEPT) through deterministic, admission-gated compilers,
project them into dense (Qdrant) + graph (Neo4j) substrates, and answer
questions with grounded, citation-backed retrieval across three modes
(VECTOR / HYBRID / GRAPH).

The strategic product requirement still ahead: **real-world transcripts**
(technical tutorials, lectures, interviews, SOPs) must feed the SAME
FACT / PROCEDURE / CONCEPT knowledge layer and enhance Graph/KAG
retrieval. See §16–18.

## 2. Repository state

- Branch `architecture/evidence-first-v5`; `main` frozen at v4 baseline.
- HEAD `a14d5fd`, tree clean at handoff commit.
- ~45-commit epoch behind this handoff: control/performance closure →
  retrieval contracts → G1 neural cutover → query scope → modern pilot →
  archive-lifecycle + summary-waterfall fixes.

## 3. Runtime environment

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
export POLYMATH_PG_DSN="postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
git status   # must be clean before boot (dirty tree fails integrity gate)

# stores
docker ps    # polymath-v4-{postgres,redis,qdrant,neo4j}-1

# fleet (pipeline profile; boots supervisor -> control + workers + sidecars)
env POLYMATH_PG_DSN="$POLYMATH_PG_DSN" POLYMATH_PROFILE=pipeline \
  POLYMATH_RELATION_PIPELINE=kimi_v1 POLYMATH_PREDICATE_V2=enforce \
  POLYMATH_SYNTAX_PROVIDER=spacy \
  nohup bash scripts/boot_polymath.sh > /tmp/polymath_fleet/boot.log 2>&1 & disown
```

Boot MUST be `disown`ed (a non-detached boot was killed by shell-session
recycling once — measured). Verify after ~2 min:

```bash
SLOTS=$(.venv/bin/python -c "import sys; sys.path.insert(0,'shared'); from polymath_shared.runtime_budget import profile_slots; print(','.join(profile_slots('pipeline')))")
POLYMATH_FLEET_ONLY="$SLOTS" .venv/bin/python eval/v5/verify_live_build.py
# expect => PASS (13/13 enforced components)
curl -s http://127.0.0.1:8740/ready   # gliner; 8742 embedder; 8744 spacy
pgrep -f control.main | wc -l         # must be exactly 1
```

## 4. Architecture at a glance

```
SOURCE (pdf/epub/md/txt/html)
  → intake_worker      normalize(NFC/BOM/CRLF) → materialize (typed failures)
                       doc_id = content-addressed; profile routing;
                       legacy_v1 chunker (children ≤1200c sentence-aligned,
                       parents = fanout-4 centroid summaries); layout evidence
  → extract_worker     GLiNER spans → rescue → identity → E1–E7 entity
                       admission → relation candidates → predicate compiler →
                       F1–F8 fact admission (ENFORCE) → facts+evidence;
                       procedure/concept artifact compilation behind router lanes
  → canonicalize/project_*   Neo4j + Qdrant + canonical projections (receipted)
  → summaries worker   parent/document/corpus summaries + vocabulary
  → verify_worker      store-vs-artifact reconciliation
  → query_ready        census promotion via generation barrier
ASK  query_scope (fail-closed) → stored-object routes (/ask today)
     + pass1/hybrid/reach machinery (orchestrator FAST/HYBRID/GRAPH)
```

Authoritative chain order and stage specs live in
`control/control/tickets.py::STAGE_DAG` (artifact keys there are
contract-pinned by `tests/determinism/test_stage_dag_contract.py`).

## 5. Stores

- **Postgres** — workflow authority: runs, documents, chunks,
  retrieval_summaries, facts/evidence, procedure/concept artifacts,
  tickets/outbox/attempts/cursors, corpora (+ purpose/query_enabled/
  embedding_contract_id), archived_corpora, query_workspaces,
  dead_letter_archive, projection_receipts.
- **Qdrant** — rebuildable dense projections; collection name embeds
  corpus-hash + embedding-contract id; routing lanes separate.
- **Neo4j** — rebuildable graph: Document–HAS_CHUNK→Chunk structural
  layer + eligible Fact/Entity semantic layer.
Redis = disposable notification. Postgres receipts prove state; logs do not.

## 6. Control plane — GO, FROZEN

Incremental census (dirty-run watermark `scheduler_cursors['__census__']`,
same-tx durable write), bulk receipt-completeness anti-joins (one
corpus-scoped query per projection per tick), bulk gap scheduler
(byte-identical idempotency keys), two-lane claim ordering
(fresh-run lane → ticketed → event_id FIFO), TICK-CACHE-V1 shared
anti-joins, ARCHIVED-CORPUS exclusions. Full report:
`eval/v5/scale/CONTROL-PERFORMANCE-FINAL-CLOSEOUT.md`
(cold seed 3226 s → 100 s; incremental census 0.31 s; foreground
query_ready ≈90 s under load; GO gate 16/16 MEASURED).
**Do not reopen without a measured regression of its acceptance contract.**

## 7. Knowledge artifacts

| artifact | table | compiler | provenance | retrieval |
|---|---|---|---|---|
| FACT | facts + evidence | predicate compiler → F1–F8 (ENFORCE) | bundle-stamped, span offsets | Neo4j eligible edges + /ask FACT route |
| PROCEDURE | procedure_artifacts | compile_procedure behind router lane | source_chunk_ids + bundle hash | /ask PROCEDURE route + qdrant routing_procedure |
| CONCEPT | concept_artifacts | compile_concepts behind router lane | supporting_chunks + bundle hash | /ask CONCEPT route + qdrant routing_concept |

Belief/attributed statements never become universal assertions
(F-gates + concept separation enforce this).

## 8. Knowledge Router (KNOWLEDGE-ROUTER-V1.1)

`shared/polymath_shared/knowledge_router/` — deterministic document-level
classifier (`classify_document(full_text)`): metadata + structure +
lexicon-density signals → mode confidences + routing tiers
`always / preferred / optional / disabled`.

Modes: SCIENTIFIC_RELATIONAL · PROCEDURAL · CONCEPTUAL · NARRATIVE ·
REFERENCE. It is a COST OPTIMIZER, not a gatekeeper (owner correction
v1.1): one ingestion engine, multiple grounded representations. Under
`PREDICATE_V2=enforce` it can disable the scientific_predicate lane per
document; procedure/concept lanes persist unless explicitly disabled.

CRITICAL DISTINCTION: source format/genre (transcript, book, paper…) ≠
knowledge type. A transcript may mix FACT+PROCEDURE+CONCEPT.

Known placeholders: `routing_policy.py`, `confidence.py` exist but are
EMPTY (0 lines). No historical/opinion modes. No separate per-type
worker processes (deliberate, per owner correction).

## 9. Summary intelligence

CHILD (verbatim proof) → PARENT chunk (fanout-4 centroid) → PARENT
SUMMARY rows (local orientation) → DOCUMENT SUMMARY (document
intelligence) → CORPUS SUMMARY/MAP (navigation across accumulated
knowledge). Vocabulary = subordinate normalization support, never a
knowledge authority. Waterfall contract: summary stages complete
tickets WITHOUT stage_attempt rows — advancement accepts a committed
DONE ticket as equivalent completion proof
(SUMMARY-ATTEMPT-EQUIVALENCE, `tickets.py::_stage_attempt_ok`).

## 10. Retrieval — implemented vs intended

IMPLEMENTED TODAY:
- `/ask` stored-object routes (FACT/PROCEDURE/CONCEPT/POLYMATH) with
  explicit fail-closed scoping (§12) — orchestrator/api/ask.py.
- FAST/pass1: promoted Pass-1 semantic route, single implementation
  (`shared/polymath_shared/pass1.py`, plan `pass1-retrieval-v1`) used by
  production AND qualification; Qdrant payload filter is
  `representation_kind` ('routing_child', 'routing_section_summary',
  'routing_document_summary', routing_procedure/concept).
- HYBRID: promoted plan = FAST + lexical (R1D: lexical PROMOTED, MMR
  REJECTED λ<1.0) — `hybrid.py`.
- GRAPH: promoted HYBRID + evidence-authorized hop-1 canonical
  expansion, 8 seeds/20 facts SPO-preserved (`reach.py`,
  `graph-retrieval-v1`).
- Behavioral harness: `eval/v5/retrieval/three_mode_benchmark.py`
  (+G1 hash-vs-neural comparator).

INTENDED / NOT COMPLETE: unified EVIDENCE-BUNDLE assembly contract,
corpus-map-guided query planning inside the orchestrator routes, BM25
inverted index (lexical is computed Python term-overlap today),
accuracy-judged benchmark (current results are behavioral only).

## 11. Embedding G1 (owner decision executed)

Production default = **neural-embed-v1**: Qwen/Qwen3-Embedding-0.6B @
revision `97b0c614…`, 1024-dim cosine/L2, instruct prefix on QUERY side
only. Contract is CORPUS STATE (`corpora.embedding_contract_id`,
migration 0034); worker resolves pin before projecting; unknown pin
raises. hash-embed-v1 retained as deterministic test/fallback provider,
never default. Existing collections were never reinterpreted
(measured: 71 dual-projected / 4 neural-only / 0 hash-only at flip).
Qualification: same-query hash 0/9 vs neural 6/9 weak-labeled hits —
`eval/v5/retrieval/G1-HASH-VS-NEURAL.md`.

## 12. Query scope (QUERY-SCOPE-V1)

`shared/polymath_shared/query_scope.py`: exactly one explicit mode —
CORPUS / CORPORA / WORKSPACE (`query_workspaces` table) /
ALL_AUTHORIZED (= purpose='production' AND query_enabled). Missing
scope → typed `QUERY_SCOPE_REQUIRED` (HTTP 422). No implicit
all-corpus search exists; regression-pinned. Corpora carry
`purpose` (production/evaluation/fixture/probe) + `query_enabled`
(migration 0035; backfilled fail-closed — only a six-corpus production
allowlist is enabled).

## 13. Corpus lifecycle

`archived_corpora` (migration 0036): an archived corpus is OUTSIDE the
scheduling lifecycle — excluded from ticket-creation rotation, from
contract-drift reconciliation, its gaps are never re-armed, its events
are never claimable (`archived_at` claim guard), and the registry
survives runtime cleanup (superseded-ticket signal AND registry row are
both consulted). Origin: scale-10k-v1's dead chains regenerated via
drift reconciliation and repeatedly occupied the claim FIFO; archival +
registry ended it. Restore = delete the registry row.

## 14. Modern pilot (pilot-modern-v1) — measured

Fresh ingest under G1 defaults: 3 real PDFs attempted (Bowart/Bernays/
Hogan persuasion domain) → 2 ingested (Bowart PDF corrupt → typed
CorruptedDocumentError, archived as deliberate evidence). 920 child
chunks, 3,811-parent-scale machinery exercised, 1 PROCEDURE, 21
CONCEPTS, **0 relation candidates / 0 facts**, full summary waterfall
DONE, 1,129-point neural collection, Neo4j Document+Chunk substrate
written (458+462 HAS_CHUNK), both runs query_ready.
Interpretation warning: do NOT generalize "narrative ⇒ no facts".
Correct status: concept/procedure extraction DEMONSTRATED on narrative
material; FACT yield zero UNDER THE CURRENT CANDIDATE-DISCOVERY PATH;
transcript relational coverage REQUIRES INDEPENDENT QUALIFICATION (§16).
Full detail: `eval/v5/retrieval/STAGE-K-PILOT-RELEASE-BOOKS.md` +
`docs/wiki/work-log/2026-08-25-stage-k-pilot.md`.

Reference corpus release-books-v1 (25 technical books): 15,205 children,
7,934 facts, 22/25 doc summaries (3 predate the summaries worker),
neural collection 18,823 points — the FACT-heavy qualification corpus.

## 15. What is frozen (do not reopen casually)

- CONTROL/PERFORMANCE architecture (GO, closeout report).
- Extraction semantics: GLiNER pin, predicate compiler trigger allowlist,
  Harbor identity, E/F admission gates (charter-frozen).
- G1 neural contract fields (model/revision/dim/prefix) — changes need
  a NEW contract id + qualification.
- RECEIPT-VERDICT-STORE-V2 semantics (MISSING delays, never advances).
- Query-scope fail-closed contract.
- Applied migrations (append-only; 0031–0036 are the recent epoch).

## 16. What is NOT finished

1. **Transcript relational qualification** (the big one — §18).
2. Evidence-bundle assembly contract + corpus-map-guided planning in
   orchestrator routes.
3. BM25 inverted index (lexical = Python term-overlap today).
4. Accuracy-judged three-mode evaluation (sealed labelled set).
5. release-books-v1 backfills: 3 legacy doc summaries; procedure/concept
   lanes predate migration 0033 for that corpus.
6. Empty placeholder modules: knowledge_router/routing_policy.py,
   confidence.py.
7. Autovacuum/bloat operational hygiene (documents hit 38× bloat once).

## 17. Transcript requirement (product north star)

A transcript is a SOURCE FORMAT containing MIXED knowledge types. The
intended behavior: supported RELATIONAL statements → FACT candidates;
instructions → PROCEDURE; explanations/schools → CONCEPT — all through
the existing durable knowledge layer, enhancing Graph/KAG retrieval.
Do not build a parallel "transcript pipeline".

## 18. Highest-priority next investigation

Transcript relational path, strictly in this order:

1. Ingest ONE realistic technical transcript (explicit relational
   language: "X uses Y", "A configures B") into a fresh corpus.
2. Observe: does `classify_document` permit the scientific_predicate
   lane? (check `_prof["routing"]["disabled"]` in extract_worker).
3. Are relation_candidates minted (>0)?
4. If candidates>0: what do F1–F8 admit? Read rejection reasons.
5. Only then touch anything — and NEVER loosen the frozen compiler
   without owner decision.

Outcome taxonomy: A good · B routing/wiring gap · C candidate-discovery
coverage gap · D admission rejection inspection.

## 19. Final qualification still required

Fresh mixed corpus (technical + narrative + one real transcript) →
verify ingestion → hierarchy → artifacts (all three types >0 where the
material supports them) → summaries → corpus map → neural projection →
graph → query_ready → scoped VECTOR/HYBRID/GRAPH panel → grounded /ask.

## 20. Reports Codex must read

- `eval/v5/scale/CONTROL-PERFORMANCE-FINAL-CLOSEOUT.md`
- `eval/v5/retrieval/G1-HASH-VS-NEURAL.md`
- `eval/v5/retrieval/STAGE-K-PILOT-RELEASE-BOOKS.md`
- `eval/v5/retrieval/THREE-MODE-BENCHMARK-V1.md`
- `docs/contracts/RETRIEVAL-CHUNK-HIERARCHY-V1.md`
- `docs/contracts/RETRIEVAL-STORAGE-CONTRACT-V1.md`
- `OVERNIGHT-PRODUCTION-READINESS-REPORT.md`
- `eval/v5/scale/INGESTION-WATERFALL-V1.md`

## 21. Tests to run first

```bash
.venv/bin/python -m pytest tests/determinism/test_knowledge_router.py \
  tests/determinism/test_query_scope.py \
  tests/determinism/test_embedding_contract_registry.py \
  tests/determinism/test_stage_dag_contract.py \
  tests/determinism/test_event_adapter_dict_cursor.py \
  tests/determinism/test_scheduler_bulk.py \
  tests/determinism/test_receipt_verdict_store.py \
  tests/determinism/test_lock_contention_v2.py \
  tests/determinism/test_incremental_census.py \
  tests/determinism/test_claim_starvation.py \
  -p no:cacheprovider -q
```
(~70 tests, seconds.) Known pre-existing failures elsewhere: 3
bundle-pin stale-authority hashes, 2 vocabulary IndexErrors, syntax-
provider env-leak flakes — documented traps, not regressions.

## 22. Boot/fence commands

See §3. Fence is mandatory after ANY commit (bundle id embeds git HEAD;
docs-only commits still shift it). Restart is safe; workers re-drive
idempotently — but avoid restarting mid-extraction (attempts roll back,
receipt checkpoints survive, work redoes).

## 23. Historical traps (paid for; do not rediscover blindly)

- dict_row vs tuple cursor unpacking in shared SQL helpers.
- Entry-point wiring drift between refactors (arity bug killed 1,864
  ticks while component tests passed) — pin call sites.
- Per-run receipt EXISTS loops / per-gap scheduling (hours → ms when
  batched; completeness truth is CORPUS-scoped).
- Strict FIFO claim starvation of fresh work (two-lane ordering).
- Work-less corpora pinning the creation round-robin window.
- Ticket chains minted after progress must reconcile history (born-done).
- STAGE_DAG artifact-key drift vs worker payloads (contract test now).
- Qdrant payload vocabulary: children are `representation_kind=
  'routing_child'`; tier-only payloads are invisible to dense lanes.
- Summary waterfall needs DONE-ticket equivalence (no attempts written).
- Archived chains resurrect via contract-drift reconciliation unless the
  corpus is in `archived_corpora`.
- pkill leaves PG backends: sweep `idle in transaction` before DDL.
- launchctl no-ops under ~/Documents (TCC); boots must be disowned.

## 24. Finish definition

Production GO for retrieval requires: transcript relational path
qualified (§18 outcome A), fresh mixed-corpus qualification (§19)
including all three artifact types from real material, sealed judged
three-mode evaluation, evidence-bundle contract implemented, and the
release-books backfills either done or explicitly waived. Everything
else above is already GO'd and frozen.
