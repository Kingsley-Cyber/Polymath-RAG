# R0 — Polymath Repository Reality / Architecture Reconciliation

Inspection-only audit. No code, config, test, or artifact changes.
Repository is the source of truth; all claims below cite executable
code at HEAD `9000973`.

HEAD: `9000973` (E5 track closeout)
WORKTREE: dirty only with uncommitted `eval/i3_5doc/` (frozen I3
acceptance artifacts — left intact per instructions)
I3 STATUS: frozen FAILED acceptance test (fact precision 0.0)

---

## 1. ACTUAL END-TO-END PIPELINE

Real stage chain (control/control/census.py:18 `STAGE_CHAIN`):
`intake → extract → profile_document → project_qdrant →
project_neo4j → canonicalize → project_canonical →
verify_projections`

| step | module | input | output | store | identity | event out | consumer |
|---|---|---|---|---|---|---|---|
| intake | `shared/polymath_shared/intake_submission.py:submit_intake` (called by orchestrator `/intake` and control `execute_manifest`) | canonical payload {corpus_id, source_name, media_type, content_b64} | runs row (status intake), outbox `intake.v1` | Postgres | `run_id(corpus_id, payload)` (identity.py:59) | `intake.v1` | intake worker |
| intake worker | `workers/workers/intake_worker.py` | intake.v1 event | documents row, chunks rows (parent+child via `workers/chunker.py:materialize_chunks`, parent_fanout 4), routing-card artifact, receipt, status reconciling | Postgres | `document_id(sha256(normalized bytes))`, `chunk_id(doc_id, idx, text)` | `chunked.v1` | census→extract |
| extract | `workers/workers/extract_worker.py` | chunked.v1 | GLiNER pass-1 entity spans + pass-2 evidence spans per sentence slice; `workers/candidates.py:build_candidates`; `rulepack/compiler.py:compile_relation`; persisted: entities (fact endpoints ONLY), facts, evidence rows; manifest artifact | Postgres | `entity_id(type,surface)`, `fact_id(predicate,subj,obj,qualifiers)`, `evidence_id(fact,doc,chunk,offsets,rule)` | none (receipt→census) | census→profile |
| profile_document | `workers/workers/profile_worker.py` | extract receipt | `retrieval_summaries` rows (document_retrieval_summary + section_retrieval_summary, contract retrieval-summary-v2) | Postgres | `summary_id` content-derived | none | census→project_qdrant |
| project_qdrant | `workers/workers/project_qdrant_worker.py` | profile receipt | chunk points (collection `qdrant_collection_name(corpus, active_contract=hash-embed-v1)`) + routing points doc/section/child (collection under `NEURAL_EMBED_CONTRACT`) | Qdrant | point id = `qdrant_point_uuid(chunk_id|summary_id)` | none | census→project_neo4j |
| project_neo4j | `workers/workers/project_neo4j_worker.py` | qdrant receipt | MERGE Document/Chunk/Entity/Fact(+REL)/Evidence nodes; receipts (chunk/fact/evidence kinds) | Neo4j + Postgres receipts | fact_id/predicate on REL | none | census→canonicalize |
| canonicalize | `workers/workers/canonicalize_worker.py` | neo4j receipt | `canonical_entities`, `canonical_memberships`, `canonicalization_decisions` — reads entities **JOIN facts** (canonicalize_worker.py:46-48) | Postgres | `canonical_id` | none | census→project_canonical |
| project_canonical | `workers/workers/project_canonical_worker.py` | canonicalize receipt | MERGE CanonicalEntity + HAS_MEMBER + evidence FROM_CHUNK | Neo4j | canonical_id | none | census→verify |
| verify_projections | `workers/workers/verify_worker.py` | canonical receipt | store-vs-receipt reconciliation; supersedes stale claims; final status `query_ready` or `degraded` | Postgres receipts + Neo4j/Qdrant deletion | receipt ids | none | census |

Commit point: one Postgres transaction per stage = artifact + receipt +
status transition (workers use `stage_transaction`/`tx`). Store writes
(Qdrant/Neo4j) are NOT in that transaction — receipts claim them after
the fact.

## 2. GLINER

- Invoked: `extract_worker.py:_entity_spans` (pass 1) and
  `_evidence_spans` (pass 2, only when `POLYMATH_WORKER_EVIDENCE_PROPOSAL_MODE=hybrid`;
  default mode is `lexical` — pass 2 is lexical only in production
  today; I3 ran lexical).
- Runtime model: `sidecars/gliner_runtime/manifest.toml` —
  `id = "urchade/gliner_medium-v2.1"`, revision from manifest
  (`40ec4193…`), loaded host-native (mps), served at 127.0.0.1:8740.
- Labels: `profile_router.py` builds `label_set` = 12 core types +
  active profile modules (software_tech/psych_cognition/
  commerce_marketing/etc. — module selection by filename/keywords,
  intake routing card).
- Thresholds: entity 0.5 (`ENTITY_THRESHOLD`, extract_worker.py:63),
  evidence 0.4.
- Raw proposal structure: `EntitySpan` dataclass
  (doc_id, chunk_id, start, end, text, core_type, score,
  extractor_version) — in memory only.
- Proposal persistence: **none directly**. `_persist_decision`
  (extract_worker.py:373) inserts entities rows ONLY for the subject
  and object of an ACCEPTED fact.
- Proposal loss point: any proposal that never becomes a fact endpoint
  disappears when the extract stage's transaction commits. The I3
  probe (35 spans on doc 03 alone) vs 9 durable entities proves
  discovery is fine and durability is the gap.

## 3. ENTITY DURABILITY

`shared/polymath_shared/entity_admission.py` assigns classes by
surface heuristics (proper-name structure, versioned ids, acronyms →
GLOBAL/CORPUS_SCOPED; bare generics → MENTION_ONLY; mid cases →
DOCUMENT_SCOPED). Identity: `allocate_entity_id` (type+surface for
GLOBAL; corpus/doc/mention-scoped hashes otherwise).

| class | identity | persisted where | canonicalized | fact endpoint | Neo4j | retrievable |
|---|---|---|---|---|---|---|
| GLOBAL | `ent_hash(core,surface)` | entities table **only if fact endpoint** | yes (via facts join) | yes | yes (class≠MENTION_ONLY) | graph seeds/canonical nodes |
| CORPUS_SCOPED | corpus+type+surface hash | same | yes | yes | yes | same |
| DOCUMENT_SCOPED | corpus+doc+type+surface hash | same | yes | yes | yes | same |
| MENTION_ONLY | `mention_+hash(doc,chunk,offsets,type)` | same | no | yes (parked) | **no** (`ADMITTED_SQL`) | not in graph; text only |

Does an admitted entity require fact participation to become durable?
**YES.** Only `_persist_decision` writes `entities`; the canonicalizer
reads entities through a facts join; nothing else persists spans.
The documented admission architecture and the executable durability
architecture are NOT the same thing: admission *classifies* every
proposal at candidate time (in memory), but classification alone
creates no durable state.

## 4. COMPILER

- Trigger representation: `EvidenceSpan.text` + `trigger_lemma` set by
  `evidence_proposer.py:localize_trigger` — a bare lowercase string.
- Matching: `rulepack/compiler.py:_trigger_matches` — literal equality
  of lemma against `verbs[]`, `nouns[]`, or substring for
  `multiword[]`. Noun and verb lists are separate in the pack, but the
  lemma is category-less: **both lists are consulted for every
  trigger**, so lexical category is effectively lost after
  localization.
- Normalization/stemming: `localize_trigger` — nouns match exact word
  boundary (`\bapplication\b`); verbs match **prefix with any suffix**
  (`\bstart\w*\b`). There is no true lemmatizer.
- `"application logs"` mechanism: "application" matches the `uses`
  NOUN inventory word-boundary → trigger "application" → uses
  candidate pair HarborPay × Authorization headers accepted
  (endpoint proximity + single-clause passes all gates).
- `"started its automation pilot"` mechanism: verb list of `founded`
  contains "start"; prefix match `\bstart\w*` captures "started" →
  lemma "start" → founded fires.
- Trigger→endpoint association: `workers/candidates.py:build_candidates`
  — for each evidence span, subject candidates = ALL entities ending
  before the trigger, object candidates = ALL entities starting after
  it (sorted by distance), **full cross product**.
- `surface_weak`: `compiler.py:_oriented_pair` — when the sentence has
  no syntactic parse record (spaCy optional/absent) orientation is
  surface order and the decision is marked `weak: true`;
  `_is_weak` returns True when parse missing or no roleset.
- E3B (`endpoint_binding.py`, invoked in compiler stage 3b,
  `POLYMATH_BINDING_GATES=1` default): has_role role-inventory,
  has_role/owns/instance_of trigger-attachment rules, title/body
  pairing, coordination-aware clause gate, surface-weak locality
  (100-char window). All of these run AFTER candidate pairing
  (build_candidates → compile_relation) — nothing gates the cross
  product itself. The only pre-pairing filter is the type-signature
  pre-check in build_candidates (`_type_compatible`), which does not
  consider clause membership.

## 5. COORDINATION

I3 sentence trace (warehouse doc, sentence 1):

- entities/spans seen: Locus Robotics, autonomous mobile robots,
  Reno Distribution Center, workflow, Manhattan Active Warehouse
  Management (5).
- triggers seen: "connected" (associated_with).
- clauses/windows: `_COORDINATION_SPLIT_RE =
  r",\s+while\s+|,\s+but\s+|;\s+"` (endpoint_binding.py:34) — no bare
  " and " splitting → the sentence is ONE clause to the gate
  ("single_clause").
- candidate pairs generated: 3 left × 2 right = 6.
- rejected: 0 (all pass type pre-check, binding gates, signature).
- accepted: 6.

Failure owner: **endpoint enumeration** (Cartesian cross product in
build_candidates, docstring contradicts the loop) compounded by
**coordination handling** (bare " and " not in the split pattern).
Sentence segmentation and trigger locality behaved as coded.

## 6. FACT DURABILITY

- First persisted: `_persist_decision` (extract_worker.py) — facts +
  evidence + endpoint entities in ONE insert batch per accepted
  candidate.
- Authoritative: Postgres `facts` (decision ACCEPT/QUALIFY/REJECT —
  REJECT not persisted; QUALIFY persists).
- Identity: `fact_id(predicate, subject_id, object_id, qualifiers)`
  content-derived; replay no-op.
- Endpoints are admission-class identities (not canonicalized yet;
  canonicalization happens later and maps local→canonical).
- Facts CAN point to MENTION_ONLY endpoints → parked in Postgres
  (`neo4j_eligibility.py`: eligible iff both classes ≠ MENTION_ONLY).
- Eligibility decided at projection time by the shared SQL predicate
  used by projector, census, and verifier.
- Parked facts still sit in Postgres facts/evidence (retrieval text
  lanes can surface their evidence chunks); they just never reach
  Neo4j. I3 example: `founded(Summit Fulfillment, pilot)` — pilot is
  MENTION_ONLY → parked (correct parking, wrong fact).

## 7. POSTGRES

| table | auth/derived | identity | created by | consumed by |
|---|---|---|---|---|
| corpora | auth | corpus_id | execute_manifest | census, workers |
| runs | auth | run_id(payload) | submit_intake | census, all workers |
| documents | auth | doc_id(content sha256) | intake worker | everything |
| chunks | derived | chunk_id(doc,idx,text) | intake worker | extract, projectors, verify |
| retrieval_summaries | derived | summary_id(content) | profile worker | qdrant routing, retrieval |
| stage_attempts | auth record | (run, stage, started_at) | stage_transaction | census |
| artifacts | derived record | artifact_id | workers | verifiers/audits |
| receipts | derived claim | receipt_hash(stage contract) | workers | census, verify |
| entities | derived, fact-coupled | entity_id/mention_id | extract (fact endpoints only) | canonicalizer, projectors |
| facts | derived | fact_id | extract | projectors, verify, retrieval |
| evidence | derived | evidence_id | extract | provenance, projectors |
| canonical_entities/memberships/decisions | derived | canonical_id | canonicalize worker | project_canonical, verify |
| projection_receipts | derived claim | receipt_hash | projectors | census gap detection, verify |
| outbox_events | auth queue | event_id + idempotency_key | stage commits | workers (claim_events) |

Entity durability is ARCHITECTURAL, not evaluator visibility: there is
simply no table a factless proposal could inhabit.

## 8. QDRANT

Production collections per corpus:
- `polymath_<corpushash>_embed_13e804b011d77db6` (hash-embed-v1
  active contract): chunk points (parent+child), payload
  {chunk_id, chunk_index, content_hash, corpus_id, doc_id,
  embedding_contract, parent_id, summary, text, tier}, point id =
  uuid5(chunk_id).
- `polymath_<corpushash>_embed_e794ec4cab197a3f` (NEURAL_EMBED_CONTRACT,
  Qwen3-Embedding-0.6B @ `97b0c614…`): routing_document_summary (5),
  routing_section_summary, routing_child — payload carries
  representation_kind + corpus_id/doc_id/parent_id + text; point id =
  uuid5(summary_id|chunk_id).

Reconstruction source: authoritative rows in Postgres
(chunks/retrieval_summaries) — projectors re-derive everything.
`concept-inventory-v1` participates NOWHERE in production
(E5B REJECTED); only disposable `routing_*_concept_e5b` collections
exist as frozen experiment residue.

## 9. NEO4J

Write order (project_neo4j_worker.process_event): `_apply_constraints`
→ `_write_graph` (MERGEs, Neo4j session) → `_receipts` (Postgres
rows) → status reconciling. Edge visibility and receipt commit are in
**different transactions/stores** — an observable window exists where
the edge exists with no receipt.

Verifier (verify_worker.py:290-320): orphan = edge whose fact_id has
no ACTIVE receipt anywhere (global) → DELETE edge; missing = active
receipt with no edge → receipt active=FALSE so census re-drives;
ineligible edges (both-endpoint check, corpus-independent) → DELETE.
Edge-exists-receipt-pending = the race window: verify deletes it, the
projector then commits the receipt, leaving an active receipt with no
edge until the next verify/census cycle.

D2 timeline: [project_neo4j: MERGE 4 facts into Neo4j] →
[verify runs for an earlier doc: reads 4 edges, reads 1 committed
receipt (other 3 pending)] → [deletes 3 edges as orphans] →
[project_neo4j commits 3 receipts] → active receipts, 3 missing
edges; self-healed on a later census cycle (I3 final state 4/4).

## 10. QUERY_READY

Set by verify_worker: `writer.run_status("query_ready")` only when
`loss==0 and problem==0` across qdrant+routing+neo4j+canonical
reconciliation at that instant. Census then promotes the run.

Guaranteed at the transition: all 8 stages last-attempt ok, no
missing projection receipts per census check, and the verifier's
instantaneous store-vs-receipt comparison was clean.

NOT guaranteed: (a) stability — a later verify tick of ANOTHER corpus
or a projector crash can disturb shared-store state without re-running
this run's verify (census only iterates runs with status in
(intake, reconciling, degraded) — query_ready runs are never
re-examined; census.py:62); (b) the reconstruction supersede path —
externally superseded receipts of a query_ready run produce no gap and
no re-drive (this is exactly what I3's reconstruction phase exposed);
(c) the transient race windows of §9.

## 11. PROVENANCE

Stored per fact: evidence row {fact_id, doc_id, chunk_id,
span_offsets={chunk_char_start: N}, rule_id, gliner_scores,
extractor_version, rule_version}; facts.provenance JSON {trigger_lemma,
trigger_surface, orientation, weak, scope, roleset, resource ids}.
Proven levels: CHUNK-LEVEL yes (exact chunk text); SENTENCE-LEVEL
partial (slices are sentence-scoped in memory but the sentence index is
NOT persisted — only chunk offsets); TRIGGER-LEVEL yes (lemma+surface
in provenance, char positions not stored); EXACT CHARACTER SPAN no
(chunk_char_end not recorded — only chunk_char_start).

## 12. RETRIEVAL

FAST = `pass1_retrieve` (pass1.py): three lanes
(document_summary/section_summary/global child over the NEURAL
collection) → RRF (k=60) → document aggregation (max 5) → section
resolution (2/doc) → filtered child deepening + global child rescue →
G3 rerank (sidecar 8743). HYBRID = hybrid.py `hybrid_fast_retrieve`
(pass1 + lexical child lane, RRF fusion). GRAPH = graph.py
`graph_retrieve`: hybrid pass1 → seed surfaces (query+evidence terms,
max 8) → `_neo4j_expand` hop-1 (HIGH/MEDIUM allowlist, max 20 facts)
→ graph facts attached as evidence lane; abstains when graph has
nothing (I3: 1 graph fact for the HarborPay query, 0 elsewhere).

Corpus authorization: Qdrant filters on corpus_id payload field for
all lanes; graph expansion filtered by corpus-scoped seeds/evidence.

**Does D1 (entity durability) damage text retrieval? NO — text lanes
(summaries + child chunks + lexical) never consult the entities
table.** D1 only reduces entity/graph observability (sparse graph,
no canonical nodes for factless entities). Proved by I3: retrieval
was 30/30 top-5 while entity recall was 0.098.

## 13. CONTROL PLANE

Event chain per stage: worker claims outbox event (idempotency-keyed,
SKIP LOCKED) → stage_transaction (artifact + receipt + attempt row +
status) → optional outbox event for the next stage or receipt-driven
census scheduling (projection stages have NO outbox event; census
gaps from receipt absence drive them — census.py `_missing_projection_receipts`).
Commit point: the Postgres stage transaction. Idempotent: content
identities (run_id/doc_id/chunk_id/fact_id/summary_id/point ids) —
replay is a no-op at every level. Reconstructed: Qdrant points +
Neo4j subgraph from Postgres authority. Temporarily inconsistent:
store-vs-receipt windows (§9), and pre-verify projection gaps
(status reconciling/degraded).

## 14. DOCUMENTATION/CODE RECONCILIATION

| claim | documented | actual code | match | consequence |
|---|---|---|---|---|
| "GLiNER proposes; deterministic code decides" | ADR-0007/E3 | true — but code ALSO decides what is remembered | PARTIAL | factless proposals vanish |
| entity admission durability | E2/C1.1 "WIRED (production)" with classes + MENTION_ONLY parking | classes computed in-memory; persistence only via fact endpoints | CONTRADICTION | I3 R=0.098 |
| MENTION_ONLY behavior | "never projects to Neo4j; parked in Postgres" | true for fact endpoints; non-endpoints never parked at all | PARTIAL | invisible mentions |
| canonical entity persistence | canonicalize stage per corpus | works, but input universe = fact endpoints | PARTIAL | sparse canonical set |
| graph projection eligibility | both endpoints admitted | exact (shared SQL) | MATCH | |
| receipt commit point | "artifact+receipt+status in one Postgres tx" | true; store writes outside that tx | PARTIAL | D2 race |
| query_ready semantics | "required projections verify" | instantaneous check; no later re-verification path | CONTRADICTION | silent post-convergence drift |
| E3B coordination protection | coordination-aware clause binding | only ", but"/", while"/"; patterns — bare "and" unprotected | CONTRADICTION | I3 6× explosion |
| exact evidence provenance | source-map/chunk citation | chunk_char_start only; no end, no sentence id persisted | PARTIAL | span-level claims unprovable |
| concept lane production status | E5 CLOSED, non-production | confirmed — zero production wiring | MATCH | |

## 15. I3 RECLASSIFICATION

| finding | class | owner |
|---|---|---|
| D1 entity durability (R=0.098) | REAL DEFECT vs documented admission architecture (or DOCUMENTATION DEFECT vs executable design — the design decision to persist only fact endpoints is consistent inside the code; the docs claim more) → MIXED | extract_worker._persist_decision / entity_admission docs |
| D2 projection race | REAL DEFECT (observable intermediate state; self-heals) | verify_worker vs project_neo4j_worker ordering |
| reconstruction-no-redrive | REAL DEFECT (query_ready runs are census-invisible) | control/census.py non-terminal-only iteration |
| D3 provenance | EXPECTED DESIGN BOUNDARY (chunk-char-start-only is the contract) | evidence schema |
| D4 manifest placeholders | DOCUMENTATION DEFECT ("__PIN_MODEL__" literals) | extract_worker manifest builder |
| noun false trigger ("application logs") | REAL DEFECT (noun/verb category lost at localization; pack noun list too broad) | evidence_proposer.localize_trigger + rule pack vocabulary |
| start→founded | REAL DEFECT (prefix matching + "start" in founded verbs) | rule pack v1.0.1/1.1.0 vocabulary |
| coordination explosion | REAL DEFECT (cross product + bare-"and" split gap) | workers/candidates.py:build_candidates + endpoint_binding._COORDINATION_SPLIT_RE |

GLiNER discovery failure vs proposal-lost: **no GLiNER discovery failure
was observed in I3** — the raw proposals exist; the loss is downstream
durability.

## 16. MOST IMPORTANT ARCHITECTURAL DISCONNECTS

1. Entity admission classifies in memory; only fact endpoints persist.
   The documented entity-admission-v1.1 durability claim and the
   executable schema disagree.
2. query_ready is a point-in-time verification with no re-verification
   path (census ignores terminal runs), while shared stores can change
   underneath it (cross-corpus verify deletions, reconstruction).
3. The candidate cross product + comma-only coordination split means
   the E3B binding layer never sees a clause boundary where a bare
   "and" is the only coordinator — the I3 explosion is the direct
   consequence.

## 17. POSSIBLE REPAIR SURFACES (labeled, not recommended)

- POSSIBLE REPAIR SURFACE: persist discovered spans (mention table or
  artifacts) independent of facts; feed canonicalization from that
  source.
- POSSIBLE REPAIR SURFACE: restrict build_candidates to the single
  nearest left/right endpoint (or clause-scoped), add "and"-aware
  coordination splitting.
- POSSIBLE REPAIR SURFACE: type-aware trigger localization (preserve
  POS origin; drop "application"/noun triggers from uses or require
  syntactic attachment).
- POSSIBLE REPAIR SURFACE: pack vocabulary edit for founded/start
  (Q1-R v1.1.0 did not change it — a new pack version would).
- POSSIBLE REPAIR SURFACE: receipt-then-edge ordering (write receipts
  in the same commit as graph writes, or make verify edge-tolerant).
- POSSIBLE REPAIR SURFACE: census re-verification of terminal runs on
  receipt supersede.

VERDICT: REPOSITORY MODEL UNDERSTOOD

NEXT: STOP. No code changes.
