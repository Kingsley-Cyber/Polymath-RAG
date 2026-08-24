# SUMMARY INTELLIGENCE RUNTIME + DEDUPLICATION REALIGNMENT
## Design of record — POLYMATH_STAGE_WORKER_IMPLEMENTATION (owner, 2026-08-23)

Binding implementation specification. Supersedes any ad-hoc worker idea.
Everything here must hold: control plane owns scheduling, dependencies,
retries, leases, replay, audit; workers ONLY consume a ticket, produce a
deterministic artifact, write a receipt, finish the ticket.

---

## PART A — STAGE WORKER SYSTEM

### Non-goals
No changes to GLiNER, Entity Admission, Fact Admission. No new knowledge
facts from summaries. Summaries never influence T2 truth. They consume
settled knowledge only.

### Ticket contract
    ticket_id (uuid) · stage ∈ {PARENT_SUMMARY, DOCUMENT_SUMMARY,
    CORPUS_MAPPING, VOCABULARY_MAPPING} · corpus_id · document_id ·
    parent_id · input_hash · contract_version · state ∈ {READY,
    CLAIMED, RUNNING, COMPLETE, FAILED, RETRY_WAIT} · attempts ·
    worker_id · created_at · completed_at

Lifecycle: READY →(lease) CLAIMED → RUNNING → COMPLETE | FAILED →
RETRY_WAIT. Never RUNNING forever.

### Derived DAG (order enforced)
knowledge_settled → parent_summary_ticket → document_summary_ticket →
corpus_mapping_ticket → vocabulary_mapping_ticket.

### Workers
- PARENT_SUMMARY: input ONLY accepted entities/facts/events +
  parent-child relationships. NEVER raw document text, unfiltered
  GLiNER output, or candidate facts. Output artifact:
  summary_id, parent_id, corpus_id, derived_from{facts,entities,events},
  concepts, content_hash, summary_version, provenance.
- DOCUMENT_SUMMARY: input parent summaries. Computes document_map:
  entities_frequency, concepts, methods, domains, questions_answered,
  supporting_parent_ids.
- CORPUS_MAPPING ("hive map"): input document summaries → corpus_id,
  dominant_domains, important_entities, dominant_concepts,
  common_predicates, research_topics, document_clusters.
- VOCABULARY_MAPPING: input parent summaries + document summaries +
  corpus summary → concept families {canonical, aliases, related_terms,
  supporting_artifacts, confidence, provenance}. FORBIDDEN: raw keyword
  frequency only; embedding-only clustering; automatic entity merging;
  modifying facts.

Idempotency gate before generation: `if artifact_exists(input_hash):
return EXISTING`. Same input ⇒ same output hash.

Vocabulary runs as part of the corpus-mapping phase (batched), not
per-document. Parent summaries create vocabulary CANDIDATES; document
summaries classify/organize; corpus summaries map research landscape.

### Storage (Postgres)
Tables minimum: summary_jobs, summary_artifacts, parent_summaries,
document_summaries, corpus_summaries, concept_vocabulary. Every table
carries corpus_id, artifact_hash, contract_version, created_by_worker,
created_at, source_ids.

### Projections
Qdrant collections: parent_summary_vectors, document_summary_vectors,
corpus_summary_vectors, concept_vectors. Payload:
{corpus_id, summary_id, artifact_hash, source_type}.
Neo4j: (Document)-[:HAS_SUMMARY]->(DocumentSummary);
(Concept)-[:SUPPORTED_BY]->(Summary). NEVER Summary-created→Entity.
Summaries are navigation objects, not facts.

### Failure handling
Retry max_attempts 5, exponential backoff → dead letter FAILED_PERMANENT
with exception + stack trace + input hash + worker version. Replay =
delete summaries/vectors/graph projections, re-run stage, identical
artifact hashes required.

### Diagnostics
Per run: stage_metrics {tickets_processed, success, failure,
avg_latency_ms, p95_latency_ms, skipped_idempotent, corpus_id,
worker_version}.

### Acceptance tests (must add)
1. duplicate ticket → one artifact, zero duplicates
2. worker crash mid-run → lease expires, reclaimed, completes
3. forced summary failure → knowledge stays READY, summary FAILED,
   retry created
4. corpus isolation (cyber vs biomedical): no vocabulary/summary bleed
5. full rebuild replay → identical hashes

One controlled subsystem: **Summary Intelligence Runtime**.

---

## PART B — DEDUPLICATION REALIGNMENT

Deduplication is IDENTITY RESOLUTION. Not summarization, not vocabulary,
not graph cleanup. Pipeline position:

RAW EVIDENCE → MENTION DISCOVERY (GLiNER) → ENTITY ADMISSION →
ENTITY RESOLUTION / DEDUP → CANONICAL ENTITIES → FACT/EVENT ADMISSION →
SUMMARY INTELLIGENCE (consumes canonical objects ONLY).

1. Document dedupe FIRST: document_identity = SHA256(normalized_content
   + corpus_id + ingestion_contract_version). Same doc → skip extraction,
   reuse artifacts; same doc + new pipeline version → reuse raw document,
   rerun DERIVED stages only.
2. Entity resolution: mention → candidate identity → admission decision →
   canonical entity {entity_id, corpus_id, canonical_name, entity_type,
   aliases, evidence_mentions, resolution_status}. Never surface-merge
   ("BERT"/"Bert"/"bert model" are mentions, not proof).
3. Corpus isolation MANDATORY: canonical_identity = hash(corpus_id +
   normalized_name + ontology_type). cyber::virus ≠ biomedical::virus.
4. Concept families merge ONLY with provenance (supported_by artifacts).
   Never "embedding similarity > 0.9 therefore merge". Embeddings
   propose; evidence decides.
5. Fact dedupe by (subject, predicate, object) triple: same triple with
   new evidence GROWS the evidence list; the fact does not duplicate.
6. Contradictions: never latest-wins. Claim record keeps multiple values
   with per-value support ({92%: paper_A}, {89%: paper_B}).
7. Summary workers consume CANONICAL objects only — prevents BERT /
   bert / the model / the architecture appearing as four concepts.
8. Control plane tracks identity_resolution stages: document_dedupe,
   entity_resolution, concept_resolution, fact_resolution (status +
   version each). Every merge writes a merge_receipt {merge_id,
   source_ids, target_id, reason, confidence, evidence}.
9. Batch behavior at scale: fingerprint → dedupe → parallel extraction →
   entity-resolution batch → fact settlement → BATCHED summary refresh
   windows. Never rebuild vocabulary per document.

Rule of record: every summary artifact references CANONICAL IDs and
never creates new identity. Summary Intelligence inherits a clean
knowledge substrate.

---

## ADDENDUM (owner, 2026-08-23) — D4/D5/D6 refined requirements

D3 boundary confirmed. Risk moves UP into aggregation scope; D4/D5 need
stricter rules than D3. The layer must be FULLY AUDITABLE.

### D4 Corpus Mapping Worker
Purpose: "What does this corpus contain?" — a NAVIGATION MAP. Truth
remains Evidence → Fact Admission → Fact Ledger.
Input contract: document_summaries ONLY (never raw docs/chunks/GLiNER
output/candidate entities/unadmitted facts).
Batch trigger policy — never per-document tickets:
    triggers: document_count_threshold | scheduled_refresh |
              manual_rebuild
    threshold.documents: 100 · debounce_minutes: 30
Weighted composition (NOT mention counting):
- concept weight = frequency + document spread + evidence density
  ("attention in 45 documents across 3 domains with 400 supporting
  facts" outranks raw repetition)
- entity importance = entity_frequency + fact_degree +
  document_distribution (BERT: 23 documents / 74 facts / 4 events)
- predicate map for routing: trained_on:182 · evaluated_on:97 …
Output fields each carrying source_document_summary_ids,
artifact_hash, contract_version: concepts, entities, domains,
predicates, document_clusters (e.g. architecture papers / evaluation
papers / training methodology).

### D5 Vocabulary Mapping Worker — most dangerous stage
Rule: vocabulary can suggest semantic bridges; it can NEVER redefine
knowledge.
Input allowed: parent summaries + document summaries + corpus summary +
accepted concepts.
Concept family merge requires ALL of:
1. same domain (AI-corpus attention terms may family; cross-domain no)
2. supporting evidence overlap (same supporting documents OR same
   accepted-fact neighborhood)
3. NEVER merge entities ("Transformer architecture" vocabulary vs
   "Transformer model" entity stay separate)
Forbidden behaviors that MUST have failing tests:
- embedding-only merge ("cosine .92 therefore alias" → NO)
- frequency-only vocabulary ("top 100 words become concepts" → NO)
- raw noun-phrase extraction as concepts → NO

### D6 Hardening (before production)
1. corpus rebuild determinism — delete corpus_summary + concept_family,
   replay ⇒ identical artifact hashes
2. vocabulary contamination test — AI "model"=ML-model vs Cyber
   "model"=threat-model ⇒ two separate families, no bleed
3. summary drift test — change ONE source document ⇒ only dependent
   summaries invalidate, not whole-corpus rebuild
4. scale test @10k documents — documents/sec, summary jobs/sec,
   memory, queue depth, failed tickets, retry count
5. projection recovery — delete Qdrant summaries + Neo4j summary links,
   replay ⇒ identical projections

### Auditability mandate
Every D4/D5 artifact must be fully auditable: source_document_summary_
ids, artifact_hash, contract_version on every field-bearing record;
rejection/merge decisions carry reasons (merge_receipts per Part B).

---

## ADDENDUM 2 (owner, 2026-08-23) — D4 completion contract + ordering lock

### Gate before anything else
Any stage test can execute ALONE, in ANY order, on a clean control-plane
state. A derived-data stage must not depend on execution order. Fix the
D3/D4 test isolation first (per-test corpus reset fixture).

### Corrected remaining order
1. Fix D4 completion contract
2. Build D5 vocabulary
3. Lock DEDUP identity model
4. D6 hardening
5. Build projections (Qdrant summary/concept collections; Neo4j
   HAS_SUMMARY / SUPPORTED_BY / SUPPORTED_BY-evidence)
6. Acceptance harness (human labels)
7. Enforcement flip

Reason: projections and validation depend on STABLE IDENTITIES, so dedup
precedes projections and validation.

### D4 revised weighting model (replaces additive score)
    importance = document_spread * evidence_density * concept_strength
Multiplicative, not additive. Example: Transformer in 80 documents /
400 parent summaries / 200 facts beats "attention" repeated 10,000
times in ONE document.
No field without source IDs:
- concepts[].source_documents
- entities[].source_documents
- predicates[].supporting_fact_ids

### D5 frozen rules
Allowed inputs ONLY: parent summaries · document summaries ·
corpus summary · accepted concepts. NEVER GLiNER spans / raw nouns /
raw chunks / embedding neighbors / unadmitted facts.
Merge requires: same domain + shared evidence + summary support.
Forbidden forever: embedding-only merges · frequency-only vocabulary ·
raw noun phrases as concepts.
Vocabulary NEVER decides entity identity ("BERT relates_to concept
transformer architecture" is the strongest claim it may make).
Corpus isolation: ai_v1::model ≠ cyber_v1::model.
Output shape per family: canonical, aliases[], supported_by{summaries,
facts, corpus}, provenance.

### Final production gate (all PASS before enforcement flip)
Extraction · Entity Admission · Fact Admission · Event Admission ·
Summary DAG · Vocabulary · Dedup · Projection rebuild · Acceptance
harness.

---

## ADDENDUM 3 (owner, 2026-08-23) — FINAL SEQUENCE: identity, replay, throughput

Remaining work is PRODUCTION INTEGRITY, not extraction logic. Locked
order (do not run 10k before identity+projections are frozen — that
measures a moving target):

    1 DEDUP identity model
    2 Projection layer
    3 Projection recovery validation
    4 10k scale test
    5 Acceptance harness (human labels)
    6 Nine-gate production review
    7 Enforcement flip

### 1 Identity model
document_hash = sha256(normalized_content + corpus_id +
ingestion_contract_version). Same hash ⇒ reuse artifacts, no
re-extraction. Same hash + NEW pipeline version ⇒ raw document survives,
DERIVED artifacts regenerate.
Store document_identity {document_id, corpus_id, content_hash,
ingestion_version, first_seen, last_processed}.

entity_key = hash(corpus_id + normalized_name + entity_type).
No cross-corpus merge ever (AI::BERT and Cyber::BERT are different
namespaces). Every merge writes a merge_receipt {merge_id,
source_entities[], target_entity, reason, evidence[]} — never silent.

fact_key = hash(subject_id + predicate + object_id). "BERT was
pretrained using BooksCorpus" after "BERT trained_on BooksCorpus" ⇒ ONE
fact, MORE evidence. Contradictions never overwrite: claim_set keeps
competing values each with its own support ({91%: paper_A}, {94%:
paper_B}) — the graph represents disagreement.

### 4 Projection layer
Qdrant collections: summary_documents · summary_parents ·
concept_families. Payload: {corpus_id, artifact_id, artifact_hash,
summary_type}.
Neo4j DERIVED NAVIGATION ONLY: (Document)-HAS_SUMMARY->(DocumentSummary);
(Concept)-SUPPORTED_BY->(DocumentSummary); (Fact)-SUPPORTED_BY->
(Evidence). NEVER Summary-CREATED->Entity — summaries do not create
knowledge.

### 5 Projection recovery gate
Delete Qdrant summary collections + Neo4j summary relationships; keep
Postgres ledger; replay ⇒ same points, same relationships, same hashes.
If not deterministic, projection is not done.

### 6 Scale metrics (after stability)
Intake docs/sec + MB/sec + duplicate-skip rate; extraction GLiNER/spaCy
throughput + candidate counts; knowledge admissions/sec + facts/sec +
events/sec; summaries parent/doc/corpus/vocabulary rates; infrastructure
RAM/CPU/GPU-MPS/Redis queue depth/Postgres connections/worker
utilization/retries/dead letters.

### 7 Acceptance harness = the production gate
Not "does it run" but "does it produce the knowledge a human researcher
expects": entity_recall · predicate_precision · event_recall ·
evidence_support. A scientific KAG prefers a MISSING FACT over a FALSE
FACT.

### Nine-Gate Production Review
G1 deterministic ingestion · G2 entity identity stable · G3 predicate
compiler validated · G4 fact admission validated · G5 event/temporal
validated · G6 summary DAG deterministic · G7 vocabulary contamination
prevented · G8 projection rebuild succeeds · G9 acceptance harness meets
target (>=90% supported, <=5% wrong). All PASS ⇒ enforcement flip.

Adding more models is not the bottleneck. Identity, replay, projection
recovery, and measured throughput turn the prototype into a production
scientific KAG.

---

## ADDENDUM 4 (owner, 2026-08-23) — STEP 4 scale-validation spec

Question: can the control plane sustain a large derived knowledge
workload without memory leaks, duplicate work, starvation, or
nondeterministic state? Measure EACH STAGE independently.

Dataset (10k): repeated documents · similar documents · different
domains · small + large files. Track duplicate_percentage.

Intake: docs/sec, bytes/sec, duplicate_skip_rate, failed_documents,
queue_depth. EXPECT: duplicates never enter extraction.
Extraction: GLiNER docs/sec + memory peak; spaCy same.
Knowledge settlement: entities_created, entity_merges, facts_created,
fact_growth, events_created, rejection_rates. WATCH: entity explosion,
duplicate identities, false fact growth.
Summary runtime per worker: jobs_completed, jobs_per_second,
p50/p95_latency, retries. Corpus mapping batch: refresh_duration,
documents_processed, concepts_updated, vocabulary_updates.
Infrastructure: Postgres connections/query_latency/locks; Redis
queue_depth/memory; Qdrant points_written/write_latency; Neo4j
relationships/transaction_time; RAM peak/CPU/GPU memory.

Failure injection required: worker crash (lease expires → reclaimed →
no duplicate artifact); store loss (delete Qdrant collection ⇒
projection rebuild only); queue overload (100k tickets ⇒ backpressure,
no OOM).

Success criteria: duplicate processing 0 · artifact collisions 0 ·
orphan projections 0 · tickets failing without dead letter 0 · rebuild
hash mismatch 0 · uncontrolled memory growth 0 · corpus leakage 0.

STEP 5 labels must cover entity correctness, predicate correctness,
event correctness, evidence grounding, retrieval usefulness.
"Scaling and evaluation are the remaining unknowns — not architecture."

---

## ADDENDUM 5 (owner, 2026-08-23) — live-run monitoring spec (scale-10k-v1)

Queue health (critical): pending/running/complete/failed/retry_wait
counts per stage · oldest_ticket_age · throughput_per_stage.
THE question: is one slow stage starving the pipeline?

Extraction: documents_processed, docs/sec, GLiNER avg_ms+p95_ms+
memory_peak, spaCy same. WATCH: continuously rising memory; workers
slowing over time; queue growth without recovery.

Entity admission: mentions_seen, accepted, mention_only, rejected,
merge_candidates, canonical_entities_created. 10k docs is where
IDENTITY EXPLOSION appears: documents up but entities growing
uncontrollably = dedup failure.

Facts: predicate_candidates, qualified, rejected, top_rejection_reasons.
A scientific KAG REJECTS AGGRESSIVELY — a clean graph is the goal, not
a huge one.

Summary runtime (first real test of the new layer): parent/document
jobs, latency, throughput, artifact_duplicates. Corpus mapping must NOT
run 10,000 times — expect: documents complete → batch threshold → ONE
corpus refresh.

Failure injections after workload stabilizes:
1 worker crash mid-ticket ⇒ lease expires → reclaim → retry → COMPLETE,
  0 duplicate artifacts
2 store loss: delete Qdrant summary collections ⇒ Postgres unchanged,
  Neo4j unchanged, projection rebuilt
3 queue overload: more tickets than workers ⇒ bounded growth, stable
  memory, no OOM ("containers consuming memory doing nothing" is
  answered by idle scale-down + bounded queues)

Seven-zero acceptance targets before advancing:
duplicate processing 0 · artifact hash collision 0 · orphan projection 0
· uncontrolled retries 0 · failed ticket without dead letter 0 · corpus
contamination 0 · rebuild mismatch 0.

Remaining questions are exactly STEP 4b / STEP 5 / nine gates:
1 Can it sustain large ingestion? 2 Can it recover from failures?
3 Does it produce human-expected scientific knowledge?

---

## ADDENDUM 5a — LIVE FINDING (2026-08-23): D7 starvation reproduced at scale

scale-10k-v1 froze mid-first-wave with the fleet healthy:
extract 24/96 done · 72 pending READY-to-advance · worker alive+idle ·
zero progress over 90s. Root cause matches owner defect D7 exactly:

`backpressure_paused()` counts extract tickets ACROSS ALL CORPORA
(watermark 64, hardcoded stage) and gates `ensure_run_tickets`
globally (main.py:89). At 10k-doc scale the watermark saturates on the
first generation, freezing new-ticket creation corpus-wide — including
advancement of already-created tickets behind it.

STATUS: BLOCKING STEP 4b. Required fix (next slice):
per-corpus watermark scoping in backpressure_paused + regression test
"one busy corpus cannot starve another". Nothing is lost — all 96
first-wave tickets persist; resume is automatic after the fix.

---

## ADDENDUM 5b (2026-08-23) — D7 fix verified partial; second layer exposed

After the hierarchy fix + control-plane restart: extract done climbed
24 → 42 (resume proof — persisted tickets reclaimed automatically),
then plateaued with 54 pending while the worker idled.

SECOND LAYER CONFIRMED: `advance_tickets` scans
`ORDER BY created_at LIMIT 256` over ~80k tickets (D7 head-of-line).
At 10k scale the window fills with other corpora/stages' older tickets,
so wave-2 extract tickets never reach the front to be advanced.
Fix design (next slice): cursor-paged advancement per stage (keyset on
created_at,ticket_id) + per-stage round-robin so no single stage's
history monopolizes the window. Same pattern as D7: deterministic,
bounded, resumable.

State: nothing lost; 42 extracts durable; scale run resumes after the
advancement-paging fix.

---

## ADDENDUM 6 (owner, 2026-08-23) — D7 SCHEDULER HARDENING PASS

Scope escalation: do NOT only implement keyset paging. Harden the
advancement system into a real distributed workflow engine. Do not
mark D7 complete until: no starvation · no duplicate claims · no lost
tickets · no orphan completions · deterministic replay.

### H1 — cursor must operate on the ELIGIBLE WORK SET
Keyset paging over raw table order still skips work when tickets
mutate state mid-scan. Required index:
    idx_ready_stage_queue ON stage_tickets(stage,status,corpus_id,ticket_id)
Cursor walks the eligible set (stage,status,corpus_id,ticket_id), not
table position.

### H2 — retry starvation
Separate queues: READY_QUEUE / RETRY_QUEUE / DEAD_LETTER_QUEUE.
Never mix new work with delayed recovery work.

### H3 — corpus fairness
Per-corpus watermarks fix admission; advancement can still bias
alphabetically. Weighted fair scheduling (corpus weights, e.g. AI:5 /
Cyber:1) or round-robin between corpora.

### H4 — atomic claims
Two workers must never receive the same ticket:
    UPDATE stage_tickets SET status='RUNNING', worker_id=:worker
    WHERE id IN (SELECT id ... WHERE status='READY' LIMIT 256
                 FOR UPDATE SKIP LOCKED)
Claim happens in ONE transaction.

### H5 — artifact-before-complete invariant
Crash between artifact write and completion ⇒ COMPLETE-without-artifact.
State machine: CLAIMED → PROCESSING → ARTIFACT_WRITTEN →
RECEIPT_COMMITTED → COMPLETE. Completion REQUIRES artifact exists +
hash verified + receipt committed. Never PROCESSING→COMPLETE.

### H6 — queue amplification metric
10k docs × fan-out could mint 260k tickets. Track ticket_amplification
{documents, generated_tickets, ratio}. 1 document = 1000 tickets is a
design problem.

### H7 — corpus lifecycle
ACTIVE | PAUSED | DRAINING | ARCHIVED. ARCHIVED: no new tickets,
existing finish, projections frozen.

### H8 — automatic backpressure recovery
No permanent pause flags. Pressure is computed per tick from queue
depth/utilization; extract resumes automatically when summary workers
drain.

### H9 — scheduler indexes at 1M scale
(stage,status,corpus_id,ticket_id) · (worker_id,status) ·
(next_retry_at,status).

### H10 — observability completeness
Every ticket answers "why is this waiting?": id, stage, state, corpus,
created_at, claimed_at, worker, attempts, last_error, next_retry,
blocked_reason. No mystery queues.

### Regression tests required for EVERY item (failure injection each).
Use monotonic ticket_sequence/bigint cursor — NEVER created_at
(collisions/backfills/retries/imports). Independent per-corpus cursors.
Scheduler metrics: oldest_ready_ticket_age{stage,corpus},
cursor_position, ready_count, claimed_last_minute. Healthy = ready_count↑
AND claimed_last_minute↑; broken = ready_count↑ AND claimed=0.

Finding of record: the first D7 failures were not random bugs — the
control plane is becoming the limiting architecture. This pass hardens
it accordingly.

---

## ADDENDUM 5c (2026-08-23): OPEN BLOCKER — advancement paging (D7 second layer)

After the D7 hierarchy fix + restart, scale-10k-v1 remains stalled:
extract 42 done / 54 pending, worker idle, and NEW corpora (e.g.
test-validation-v1) get NO tickets created. Both symptoms trace to the
unfixed HALF of D7: `advance_tickets` discovery scans
`ORDER BY created_at LIMIT 256` over ~80k tickets — wave-2 and other
corpora never enter the window, and ticket CREATION for new runs is
starved behind it.

REQUIRED NEXT SLICE (D7-H1 wiring): keyset-paged per-(stage,corpus)
advancement consuming eligible_page() + scheduler_cursors (both landed,
5208ee3), replacing the LIMIT-256 scan. Then: scale resumes, new corpora
admit, addendum-5 metrics become collectable.

Also fixed en route: _admitted_facts init-placement regression
(NameError) introduced by the acceptance-block patch — caught by STEP
4b failure monitoring, root-caused via receipts.error.

---

## ADDENDUM 5d (2026-08-23): CREATION-WINDOW FLIP-FLOP STARVATION

Third layer of D7 found live: `_ensure_tickets_backpressure_gated`'s
candidate window (LIMIT 32, oldest-first) fills entirely with a
saturated corpus's ~9,900 runs whenever that corpus momentarily dips
below the watermark (workers complete tickets between ticks), then
re-saturates — flip-flopping every tick. Younger corpora NEVER enter
the window. Verified: manual ensure created 384 tickets while
test-validation-v1 (ingested hours ago) still had zero.

FIX SPEC (next slice):
- Sticky hysteresis: persist `creation_paused_until_drain` per corpus;
  once marked, a corpus stays out of the candidate window until active
  < watermark/2 (not just < watermark).
- Or simpler and stronger: candidate window orders/excludes by
  per-corpus ACTIVE count directly in SQL (`corpus_active < watermark`
  join), so window membership can't be gamed by completion timing.
Regression: young-corpus run + saturated old corpus ⇒ young gets
tickets within one tick regardless of worker completion timing.

Current committed state: conditional-exclusion SQL correct but
insufficient alone; control plane restarted with it; scale-10k
extraction continues (done climbing); test-validation-v1 still queued.

---

## ADDENDUM 5e (2026-08-23): ROOT CAUSE FOUND — contract-pin claim refusal

The 63 READY scale-10k tickets all HAVE live undelivered claim events,
the extract worker is ALIVE and polling, yet nothing is claimed.
Diagnosis: the worker advertises UPGRADED contracts (bundle
v5-production-005 / pack 1.4.0 / policy v3) while every scale-10k run
pins the PRE-upgrade execution_contract. Contract-pinned claiming
refuses the mismatch SILENTLY at the lease step.

This is not a bug in contract pinning — it is the missing RECONCILIATION
half of the identity model (addendum 3): "same source + new pipeline ⇒
reuse raw document, regenerate derived artifacts." Nothing implements
that regeneration path yet, so post-upgrade runs are stranded.

REQUIRED (STEP 1c): pipeline-version reconciliation at the control
plane — when a run's pinned contract differs from current worker
contracts and its corpus is ACTIVE, mint a successor run (new
processing_run row) and migrate ticket chains, preserving document
identity. Until then: any corpus ingested BEFORE an upgrade is
permanently frozen mid-pipeline after every upgrade.

Interim operational unblock (no code): delete the stranded runs'
ticket/outbox rows and re-submit the manifest — fresh runs pin current
contracts. Proven working on test-validation-v1 this session.

---

## ADDENDUM 5f (2026-08-23): STEP 1c IMPLEMENTED — reconciliation live

`control/control/reconciliation.py::reconcile_contract_drift` runs in
every control tick BEFORE ticket creation. When an open run's pinned
contract differs from the fleet's current contracts it mints a
deterministic successor run (`run_<hash(reconciles, contract)>`),
pins CURRENT contracts, copies immutable lineage (metadata +
intake_payload verbatim), and closes the old run as
`status='superseded'` with `superseded_by_run_id` — ZERO deletion,
tickets/events/attempts preserved as history.

Selective regeneration (T4): `STAGE_CONTRACT_DEPENDENCIES` declares
each stage's contract keys; DONE stages whose keys are all unchanged
carry into the successor as run-scoped copies with
`carried_from_run` provenance; changed-dependency stages regenerate.
One-active-intent invariant: partial unique index
`runs_one_successor_idx` (migration 0029) allows at most one successor
per superseded run, ever.

SECOND ROOT CAUSE found during verification (migration 0030):
`outbox_events` had NO index on `(run_id, event_type)` — every
`_emit_ticket_event` lookup seq-scanned a 1.4 GB table; control ticks
observed wedged 5-6+ MINUTES inside that single SELECT, starving all
worker claims independent of contract pinning. Indexed; wedges = 0
since restart. This is why scale-10k stalled even where pins matched.

Verified live: control restarted → stranded corpora reconciled
(successor runs visible with lineage), intake 742 done and climbing,
extract claiming again, zero wedged transactions. Regression proof:
tests/integration/test_contract_reconciliation.py T1-T4
(queued upgrade · mid-processing upgrade · replay determinism ·
policy-only carry) — 4/4 green.

---

## ADDENDUM 5g (2026-08-23): DRAIN CAPTURE + TWO MORE SCALE DEFECTS CLOSED

Continuous capture (30s JSONL, eval/v5/scale/metrics_drain_2026-08-23.jsonl):
done 2597→2683 and climbing; dead letters 0 throughout; GPU ~51%
active; knowledge surface stable (227k mentions, 26.3k entities,
8.5k facts — identity-explosion watch still NEGATIVE).

Defect 4 (claim ordering): 2,643 ungated legacy-lane events sat at the
event_id head, starving 369+ gated READY tickets behind them — the
convergence metric read flat while real work bypassed lease/backpressure/
contract gates entirely. Fix: gated events sort first (1d14f0e).

Defect 5 (census per-entity loop): _missing_projection_receipts ran one
SELECT PER ENTITY inside the tick transaction (py-spy caught it live);
complete runs with hundreds of chunks held the tick open MINUTES while
every claim queued behind it. Fix: set-based anti-join, same result
(census fix committed). This is the root of the recurring "wedged
tick" signature from addenda 5a-5e.

Also fixed en route: reconciliation successors needed their parents'
PRODUCED outbox payloads verbatim (intake.v1 corpus_id, chunked.v1
doc_id) — bare {run_id} fallbacks crashed every gated claim with
KeyError and burned retry budget until repaired (ce6f3c0, fd436af).

Known-open: /rescue calls intermittently stall to the 300s client
timeout under GPU contention (pre-existing MPS limitation, now
quantified: bursts of ~16 jobs/min between multi-minute stalls).
Watch: created>completed during load, completed catches up after.

---

## ADDENDUM 5h (owner, 2026-08-23): LOCKED VALIDATION ORDER — post-drain

    1 TEST.md successor completes
    2 Compare against old baseline
    3 ACCEPTANCE HARNESS on the replay output   <- inserted by owner
    4 Identify remaining missed facts
    5 Fix compound-NP binding
    6 Authored predicate registry updates
    7 Replay
    8 Acceptance harness

No predicate changes before step 2's baseline comparison. Harness runs
TWICE: once after replay to size the gap (step 3), once after the fix
arc to prove movement (step 8).

Lineage observation recorded: test-validation-v1 reconciled in TWO
hops (v1-pin -> v3-pin within 90s) because policy resolution drifted
between mints. One-successor index held; nothing lost; pin-resolution
stability is a watch item, not a blocker.

---

## ADDENDUM 5i (owner, 2026-08-23): MISSION SEQUENCE LOCKED

Track separation directive: production reliability (drain/control
plane) and intelligence quality (Compiler v2) advance independently.
NO v2 splice into the live drain. No bundle change. No run
invalidation during Phase 1.

    P1 Finish drain (dead letters=0, queue converges, no stranded
       tickets, projection receipts complete). Capture final metrics.
    P2 Promote Compiler v2 to production candidate path (shadow ->
       enforce). Preserve evidence contracts, admission logic,
       replay determinism, provenance. Every candidate records:
       semantic_frame_id, lexical_resource_source, role_mapping,
       predicate_mapping_rule, dependency_path, evidence_span.
    P3 TEST.md replay comparison (baseline vs v2): recovered facts,
       missing facts, false positives, rejected-with-reason.
    P4 Entity discovery follow-on ONLY after v2 validation
       (corpus/dataset/benchmark registries; no capitalized-noun
       acceptance).
    P5 Acceptance harness: entity_recall, predicate_precision,
       event_recall, evidence_support + v2 metrics
       (semantic_frame_accuracy, role_binding_accuracy).
    FINAL Intelligence brief (9 sections per owner spec).

Operating rules unchanged: no verb dictionary, no embedding truth,
no LLM relations, no weakened gates. Misses classified A-E before
any patch.

Phase-1 telemetry continues via drain_metrics.jsonl sampler.

---

## ADDENDUM 5j: acceptance harness armed (owner COVERAGE_GATE schema)

eval/v5/acceptance/harness.py scores every mission gate against live
state with honest verdicts (PASS/FAIL/PENDING + measured values):
extraction coverage+integrity · summary lineage per level · vocabulary
merge receipts · retrieval routing population. Current run: YELLOW —
summary/vocabulary PENDING (stages queued behind drain), retrieval
SCORED (20k routing summaries), extraction facts awaiting cutover
replay scoring. Gates: coverage>=90% precision>=95% support>=95%
role_binding_err=0 FP=0.
