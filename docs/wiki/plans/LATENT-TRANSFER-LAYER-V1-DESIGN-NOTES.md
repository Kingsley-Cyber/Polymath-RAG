---
change_id: LATENT-TRANSFER-LAYER-V1-DESIGN-NOTES
owner: governance
date: 2026-08-30
status: reference
architecture_impact: none (design ingestion record for LATENT-TRANSFER-LAYER-V1-PLAN)
last_reviewed: 2026-08-30
---

# Additional RAG layer — design-ingestion notes (one file per pass)

Running notes. Each part is read in its own pass; normative details are
recorded here verbatim-in-spirit before the next file is opened. These
notes feed the implementation plan (files/deps/execution).

---

## Part 1 — `~/Downloads/Adapter.txt` (884 lines) — PARENT_ENRICHMENT adapter

**Headline decision.** Do NOT replace the deterministic parent summary. Add a
separate `PARENT_ENRICHMENT` artifact, ONE LLM forward call per parent.
Governing rule stays: **SUMMARIES ROUTE / CHILDREN PROVE** → extended to
**ENRICHMENT ROUTES / CHILDREN PROVE**.

### Current-state facts the doc relies on (verify against code)
- Semantic chunker: each child has exact offsets, `heading_path`, own
  `summary`, `parent_id`; parent = deterministic group of children; parent
  span = first child start → last child end.
- Summary worker: `run_parent_summary_ticket` gathers children text +
  accepted facts + entities; `_parents_of_docs()` selects only
  `chunk_id, parent_id, text` (drops heading_path/offsets/order).
- `build_parent_summary()` is intentionally small: ≤4 rendered facts, 10
  entities, 10 concepts; falls back to start of parent text when no facts.
- Summary runtime already has transactional/idempotent persistence:
  `summary_jobs`, `summary_artifacts`, `input_hash`, `output_hash`,
  `parent_summaries`.
- FAST deliberately fails when its routing projection isn't ready →
  enrichment MUST NEVER be a readiness dependency.
- Qdrant is a rebuildable projection with receipts; `representation_kind`
  vocabulary exists (`routing_document_summary | routing_section_summary |
  routing_child | routing_procedure | routing_concept`).
- pass1 contract: embed once → doc summary / section summary / global child
  → RRF → documents → sections → filtered child deepening → global child
  rescue → children. "Document routing is not allowed to prevent a global
  child hit from surviving."

### Output contract `parent-enrichment-v1` (exact shape required)
```
schema_version, parent_id, parent_summary,
hierarchy[]: {child_id, ordinal, heading_path[], summary, key_points[]}
extract{}:  claims[{text, source_child_ids}], definitions[{term, definition, source_child_ids}],
            principles[{text, source_child_ids}], relationships[{subject, relation, object, source_child_ids}],
            procedures[], constraints[], examples[]
latent{}:   abstraction{text, source_child_ids},
            mechanisms[{cause, relation, effect, conditions[], source_child_ids}],
            affordances[{capability, action, desired_effect, source_child_ids}],
            pseudo_queries[{text, source_child_ids}]
coverage{}: input_child_ids[], covered_child_ids[], omitted_child_ids[]
```
Four planes: RAW = child.text (never duplicated by the LLM); COMPRESSED MAP =
hierarchy[]; STRUCTURED INVENTORY = extract{}; TRANSFERABLE = latent{}.

### LLM input (structurally explicit)
`_parents_of_docs()` for enrichment must select
`chunk_id, parent_id, chunk_index, heading_path, char_start, char_end, text, summary`
(`tier='child' AND parent_id IS NOT NULL ORDER BY chunk_index`).
Prompt blocks: `[PARENT] parent_id`, `[EXISTING_PARENT_SUMMARY]`, per-child
`[CHILD] id / ordinal / heading_path (joined " > ") / char_start / char_end / TEXT`,
`[SETTLED_FACTS]`, `[CANONICAL_ENTITIES]`.

### Runtime / persistence
- New job kind `parent_enrichment.v1`, OPTIONAL stage downstream of
  `parent_summary.v1` (which stays COMPLETE independently). LLM down →
  `PARENT_ENRICHMENT FAILED/RETRY`, corpus stays retrievable.
- Table `parent_enrichments(enrichment_id PK, parent_id, corpus_id, doc_id,
  source_hash, compiler_contract, model_contract, prompt_hash,
  parent_summary, hierarchy JSONB, extract JSONB, latent JSONB, coverage JSONB,
  source_child_ids TEXT[], artifact_hash, status CHECK IN (READY, INVALID, STALE),
  UNIQUE(parent_id, source_hash, compiler_contract))` + indexes on
  parent_id, doc_id, corpus_id.
- Full JSON envelope also stored in `summary_artifacts` with
  `stage='PARENT_ENRICHMENT'` (artifact + typed-table pattern).
- Chain: summary_artifacts (immutable envelope) → parent_enrichments
  (queryable authority) → Qdrant projection.
- NEVER write into `retrieval_summaries` (deterministic, non-generative
  contract). Provenance distinction: retrieval_summaries = deterministic;
  parent_enrichments = LLM-enriched.

### What gets embedded (bounded)
| representation | embed | kind |
|---|---|---|
| enriched parent summary | yes (1) | `latent_parent_summary` |
| abstraction | yes (1) | `latent_abstraction` |
| mechanisms | yes, individually | `latent_mechanism` |
| affordances | yes, individually | `latent_affordance` |
| pseudo-queries | yes, individually | `latent_pseudo_query` |
| hierarchy child digests | not initially | — (trace/coverage only) |
| full extract JSON | NO (never one blob) | — |
Expected ≈ 9 extra vectors per parent (1+1+2+2+3). Cap it.
Point payload: `representation_kind, enrichment_id, parent_id, doc_id,
corpus_id, source_child_ids[], compiler_contract, source_hash, text`.
Point identity = hash(enrichment_id + representation_kind + ordinal + text)
— deterministic, fits receipt/idempotent re-projection.

### Retrieval integration (Pass-1 seam)
Optional LATENT lane in parallel with current pass-1 (same single query
embedding): latent_parent_summary / abstraction / mechanism / affordance /
pseudo_query hits → **collapse to parent_ids** → join candidate sections →
existing child deepening → existing rerank → exact child evidence.
A latent hit is NEVER evidence and its text is never answered from; it only
nominates a parent. Recall protection inherited from pass1 (routing never
gates a global child hit).

### Non-negotiable validation before persistence
- every `source_child_id` ∈ input child set; unknown id → REJECT
- `hierarchy` must contain every input child; missing → REJECT
- `coverage.omitted_child_ids == []`
- malformed JSON → REJECT
- `source_hash = hash(child_id + child.text + heading_path + child order +
  compiler_contract)`; any child change → old row STALE → regenerate →
  re-project its latent vectors.

### Implementation boundary
Do NOT make `semantic_chunker.py`, `pass1.py`, `retrieval_summaries.py`
depend on an LLM. Existing FAST/HYBRID/GRAPH must keep working if the entire
enrichment system is deleted or broken.

### Mapping to real seams (from the code map)
- Summary runtime: `workers/workers/summary_worker.py` /
  `summary_worker_impl.py` (`run_parent_summary_ticket`, `_parents_of_docs`,
  `build_parent_summary`); tables from `0024_summary_intelligence.sql`
  (`summary_jobs:8`, `summary_artifacts:29`, `parent_summaries:42`).
- Projection: `workers/workers/project_qdrant_worker.py:308 _routing_rows`,
  `:495 _write_routing_slice` (payload contract), `:295-303` kind constants.
- Query: `shared/polymath_shared/pass1.py:350 pass1_retrieve` (injected
  `routing_search`), `orchestrator/orchestrator/api/fast.py:53
  FastSearcher._search` (filters by `representation_kind`),
  `shared/polymath_shared/query_shape.py:120 plan_for_query`.
- LLM transport to reuse: `shared/polymath_shared/llm_extraction/client.py`
  (local/cloud lanes, limiter, gate-style sanitize) — enrichment gets its own
  Pydantic contract + validator, same lane/boundary policy.

### Open questions for the plan (do not assume)
- Which lane runs enrichment (local 4B vs cloud by doc size like extraction)?
- Where does the LATENT lane get exposed: new mode, or a flag on FAST/HYBRID?
- Does `/ask` (stored-objects route) read `extract{}`? (doc is silent)

---

## Part 2 — `~/Downloads/Adapter 2.md` (1,686 lines) — the LATENT TRANSFER LAYER as an optional sidecar

**Framing.** The new capability is an OPTIONAL LLM-enriched retrieval
sidecar, never part of the required retrieval path. Baseline
(FAST / HYBRID / GRAPH → normal evidence) continues unchanged; the latent
layer adds `abstraction / mechanism / affordance / pseudo-query` channels.
Polymath becomes two branches: **Evidence Layer ("What says X?")** =
vector / lexical / entity / graph; **Transfer Layer ("What helps X?")** =
abstraction, mechanism, affordance, pseudo-query, analogy, concept-sense.
Key combination = mechanism + affordance + global abstraction (more than
RAPTOR/LiteSemRAG).

### Graph model (DEFERRED — explicitly "delay changing Neo4j")
Proposed node types `(:Chunk)(:Parent)(:Document)(:Concept)(:Entity)(:Frame)
(:Mechanism)(:Abstraction)(:PseudoQuery)(:ConceptSense)`; edges `CHILD_OF,
ABSTRACTS, EVOKES_FRAME, HAS_ROLE, REALIZES_MECHANISM, ANSWERS,
SEMANTICALLY_RELATED, ANALOG_OF, CO_OCCURS, BRIDGES`. Mechanism nodes are
DELEXICALIZED ("Variation of a controllable dynamic parameter changes the
perceived qualitative character of an observable behavior", not "Laban
Effort changes movement quality"). Cross-document/cross-domain RAPTOR
**forest** (global semantic clusters: Laban + cinematography + UX → one
abstraction), not one tree per book. HopRAG idea adopted ONLY for
index-time pseudo-question creation + edge construction; query-time
traversal stays deterministic (no LLM traversal/reasoning at query time).
→ Phase 1 keeps Neo4j UNCHANGED; Postgres holds enrichment receipts/
metadata; Qdrant holds the latent vectors.

### Affordance (distinct from mechanism)
Index-time question: "What can this knowledge be USED to change?" (not which
domain it belongs to). Serves "How can I improve / make X more efficient /
why does X feel wrong" queries — transferable functions. Examples: Laban →
control perceived force, communicate intentionality, create temporal
contrast; information theory → reduce uncertainty, distinguish signal from
noise; control theory → stabilize dynamic systems, correct deviation.

### Query time is deterministic
Channels run from ONE query embedding: child/parent semantic, abstraction,
mechanism, affordance, pseudo-query → union seeds → deterministic Neo4j
expansion (existing) → support aggregation → reranker → MMR/domain
diversification → evidence packet. Initial scoring model (only if a fused
score is needed):
`score = .30 semantic + .25 mechanism + .20 abstraction + .10 pseudo_query + .10 graph_support + .05 bridge_support`.
Record WHICH CHANNEL produced each candidate (for P6 attribution).

### Generation: ONE forward pass inside the existing parent-summary pass
"Parent Summarizer" → "Parent Semantic Compiler": children → one LLM call →
{summary, abstraction, mechanisms, affordances, pseudo_queries} → schema
validation → canonicalization → hash → receipt → projection. NOT five
calls. Output contract (Part 2 shape; Part 1's `parent-enrichment-v1` is
the superset):
```
summary; abstraction{principle, domain_independent_description};
mechanisms[{cause, relation, effect, conditions[]}];
affordances[{action, desired_effect}]; pseudo_queries[str]
```
Bounds (qualification): 1 abstraction + 2 mechanisms + 2 affordances +
3 pseudo-queries = 8 vectors/parent; production cap 1 + 3 + 3 + 4 = 11.
"Don't generate a giant amount of enrichment per parent" (vector bloat,
noisy retrieval).

### Separation / purity rules
- `Parent{parent_id, content_hash, summary, embedding}` UNCHANGED.
- `ParentEnrichment{parent_id, source_content_hash, enrichment_version,
  abstraction(+vector), mechanisms[](+vectors), affordances[](+vectors),
  pseudo_queries[](+vectors)}`; conceptually `Parent -HAS_ENRICHMENT->
  ParentEnrichment` (but keep out of Neo4j initially).
- NEVER fold mechanisms/affordances/pseudo-queries into the parent summary
  text: `summary_vector` stays pure; separate `abstraction_vector /
  mechanism_vector / affordance_vector / pseudoquery_vector`.
- Phase 1 storage: four optional vector namespaces `latent_abstraction,
  latent_mechanism, latent_affordance, latent_pseudoquery` (Part 1 adds
  `latent_parent_summary`); every point stores `parent_id, document_id,
  corpus_id, content_hash, enrichment_version, type, text`.

### The hard interface boundary
**"Latent layer produces additional parent IDs."** latent search → parent
IDs → EXISTING parent/child resolution → EXISTING reranker → EXISTING
evidence packet. No new evidence pipeline. Contract:
`candidates = baseline_candidates ∪ latent_candidates`; latent can ADD,
never REQUIRED; never `baseline → latent → retrieval` (dependency).

### Fail-open + budget
`baseline = retrieve_baseline(q); try: latent = retrieve_latent(q) except:
latent = []; return fuse(baseline, latent)`. Latent budget 100–300 ms
initially; timeout / failure / missing enrichment → zero latent candidates.
NEVER HTTP 500/502 from latent unavailability; only telemetry shows it.

### Flags / modes
`LATENT_RETRIEVAL_ENABLED=false` default; per-channel
`LATENT_ABSTRACTION_ENABLED / LATENT_MECHANISM_ENABLED /
LATENT_AFFORDANCE_ENABLED / LATENT_PSEUDOQUERY_ENABLED`. Better: expose
`retrieval_mode: baseline | baseline_plus_latent` (A/B trivial).

### Evaluation: its OWN suite — P6 LATENT_TRANSFER_RECALL
Do not mix into existing retrieval evals. Case shape: `query,
obvious_domains[], latent_domains[], acceptable_mechanisms[],
forbidden_shortcuts[]` (e.g. explicit "video prompt" mention, same named
entity). Metrics: LatentRecall@10/@20, CrossDomainRecall@K,
MechanismRecall@K, UniqueDomainCount@K, BridgePrecision@K,
**FalseAnalogyRate** (critical), AnswerLift_with_latent vs _without.
Per-channel unique-relevant-hit attribution table → kill channels that add
nothing (e.g. pseudo-query vs mechanism).

### Reconciliation Part 1 ↔ Part 2 (for the plan)
- Output contract: use Part 1 `parent-enrichment-v1` (superset: hierarchy[],
  extract{}, coverage{}) with Part 2 bounds and Part 2's abstraction shape
  `{principle, domain_independent_description}` folded into `latent.abstraction`.
- Storage: Part 1 `parent_enrichments` table + `summary_artifacts` envelope.
- Kinds: Part 1's five (`latent_parent_summary` + the four channels).
- Retrieval boundary: Part 2's "parent IDs only", fail-open, budgeted,
  flag-gated, channel-attributed; Part 1's collapse-to-parent → existing
  child deepening is the same rule.
- Neo4j: unchanged in Phase 1 (both agree). Graph node/edge model = later phase.
- Evaluation: P6 suite (Part 2) + Part 1 validation invariants as unit tests.
