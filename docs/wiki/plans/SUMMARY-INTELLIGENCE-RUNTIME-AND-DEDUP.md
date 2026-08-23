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
