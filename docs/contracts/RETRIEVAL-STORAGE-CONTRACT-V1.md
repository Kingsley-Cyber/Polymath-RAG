# RETRIEVAL-STORAGE-CONTRACT-V1

Status: **ACTUAL BEHAVIOR** (audited from production code + live stores
2026-08-25, HEAD `9331f9a`). Postgres is authoritative; Qdrant/Neo4j are
rebuildable projections; lexical retrieval is computed, not indexed.
Every gap flagged below is real and measured today.

## 1. POSTGRES (authoritative retrievable state)

| state | table | notes |
|---|---|---|
| documents | `documents` | doc_id content-addressed; profile, materialization, source_map |
| child+parent chunks | `chunks` | tier ∈ {child,parent}; chunk_index; parent_id; layout_map; char offsets |
| summaries | `retrieval_summaries` | summary_id PK; kind (`document_retrieval_summary`, `section_retrieval_summary`); contract; provenance jsonb |
| canonical facts | `facts` + `evidence` | T2 settled knowledge only (Neo4j-eligibility predicate governs projection) |
| procedure artifacts | `procedure_artifacts` | title/goal/steps_json/tools_json |
| concept artifacts | `concept_artifacts` | name/description/aliases (migration 0033) |
| corpus map | `corpora.profile` + retrieval_summaries at corpus scope | routing card lives in intake artifact payloads |
| provenance | receipts + facts.provenance.generated_by_bundle_hash | execution-bundle stamped |

## 2. QDRANT (dense projections)

Collections (live audit: 153 collections):
- evidence/routing: `polymath_<corpus-hash>_<embed-contract>`
- routing lanes: separate collections
  (`routing_document_summary_*`, `routing_section_summary_*`,
  plus procedure/concept lanes).

### Embedding contracts (frozen, content-hashed ids)

| id | model | dim | status |
|---|---|---|---|
| `embed_13e804b011d77db6` (hash-embed-v1) | none (char-3gram hash) | 512 | settings DEFAULT — zero-model test contract |
| `embed_e794ec4cab197a3f` (neural-embed-v1) | Qwen/Qwen3-Embedding-0.6B @ pinned revision | 1024 | served by embedder sidecar |

**GAP G1 (measured)**: BOTH exist live across corpora. The settings
default is the HASH contract — any corpus projected without an explicit
override is semantically near-useless for paraphrase. Contract choice
must become an explicit per-deployment decision; mixed-contract queries
are impossible by construction (collection name carries the contract),
but operators must know which corpora live where.

**What text is embedded (type-aware, deterministic):**

| representation_kind | text embedded |
|---|---|
| document_profile / routing_document_summary | document/section retrieval-summary TEXT from `retrieval_summaries.summary_text` |
| parent_summary | parent chunk text (already a centroid SUMMARY, see chunk contract) |
| child_chunk / routing_child | verbatim child chunk text |
| routing_procedure | `"{title}. {goal}.\n1..n steps\nTools: …"` (deterministic serializer) |
| routing_concept | concept serializer over name/description/aliases |
| query | query text under contract's `query_prefix` |

Prefix discipline: neural contract applies its instruct prefix to the
QUERY side only; document kinds unprefixed. No JSON serialization is
ever embedded.

### Point payload (all points)

`representation_kind`, `corpus_id`, `doc_id`, `parent_id`,
`chunk_id` (children), `summary_id` (summary/artifact objects),
`source_name` (summary rows), embedding contract implied by collection
name. Point id = `qdrant_point_uuid(summary_id or chunk_id)` — stable,
idempotent upserts. Receipts (`projection_receipts`) checkpoint every
512 rows; crash ⇒ re-done work, never lost knowledge.

### GAP list (Qdrant)

- G2: charter metadata list (source_tier, media_type, timestamps) is
  NOT in point payloads today — extend deliberately with a new payload
  version, do not mutate existing points in place.
- G3: no alias/alias-normalized field on concept points beyond the
  serialized text.

## 3. LEXICAL (BM25)

**THERE IS NO BM25 INDEX.** `retrieval.lexical_score` is deterministic
Python term-overlap ("BM25-flavored") scored IN MEMORY over candidate
rows fetched from Postgres (`fetch_children` etc.). Exact-match
strength therefore depends entirely on which rows the fetchers pull,
not on an inverted index.

**GAP G4 (structural)**: identifiers/acronyms/commands/model names can
only be found if the candidate set already contains them. The three-mode
benchmark must measure this honestly; a real lexical index (Postgres
FTS/GIN on chunks.text + artifacts fields) is the sanctioned fix when
measurements justify it.

Required retrievable lexical fields once built: child verbatim text;
parent summary; document title/source_name + summary; fact
subject/predicate/object/source surface; procedure title/goal/steps/
tools; concept name/description/aliases.

## 4. NEO4J (graph projection)

Content: typed canonical entities + memberships + eligible FACTS with
evidence_chunk links (+ canonical_entity/canonical_membership/evidence
receipts). Derived/rebuildable; full wipe→rebuild proven previously.

Rules preserved (do not violate during retrieval work):
- No embedding-similarity edge may ever become graph truth.
- No generic RELATED_TO edges to boost recall.
- MENTION_ONLY-dependent facts stay parked in Postgres (no synthetic
  graph nodes).
- GRAPH_HOPS=2 / GRAPH_MAX_FACTS=20 in `shared/retrieval.py` — note:
  charter default is hop1; hop2 exists in code and must be either
  measured or gated before GRAPH freeze.

## 5. DETERMINISM

Same query + corpus + store state + policy ⇒ same ordered ids:
rankings derive from sorted(-score, id) keys everywhere; RRF k=60
deterministic; dense lane order = sidecar return order under fixed
contract/batch. Retrieval policy version must be recorded with eval
output (open obligation for the benchmark harness).
