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
