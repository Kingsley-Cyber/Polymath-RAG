# R1 — Current Retrieval Posture Audit (READ-ONLY)

Frozen 2026-08-15. Audited against HEAD `2c9765a` (D4.1 REJECT, production
unwired). **IMPLEMENTATION STARTED = NO.** This report records only what
the repository currently does.

Sources inspected: `shared/polymath_shared/retrieval.py`,
`shared/polymath_shared/rerank.py`, `shared/polymath_shared/embedding_contracts.py`,
`orchestrator/orchestrator/api/{retrieve,chat,evidence}.py`,
`shared/polymath_shared/{evidence_assembly,answer_synthesis}.py`,
`workers/workers/{chunker,summarizer,document_profile_builder,project_qdrant_worker}.py`,
live Postgres/Qdrant state of the frozen I2 corpus.

## 1. Stage-by-stage posture

| Stage | Posture | Notes |
|---|---|---|
| query → document-summary retrieval | IMPLEMENTED AND ACTIVE (lexical only) | `score_profile()`: weighted term overlap over RetrievalProfile fields (`semantic_summary` w=3.0, `core_concepts` 2.5, …). NO document vectors — routing is purely lexical over the profile. |
| section/parent-summary retrieval | IMPLEMENTED AND ACTIVE (lexical only) | `parent_ranking` = `lexical_score(query, parent.summary)`. No dedicated parent vectors; parents are also indexed as Qdrant points (see dense lane note). |
| global child retrieval | IMPLEMENTED AND ACTIVE | Dense lane = Qdrant top-50 under the ACTIVE contract. **ACTIVE contract is `hash-embed-v1`: 512-dim deterministic hash-projection embeddings — a lexical-structure signal, not a neural semantic model.** Neural contract exists but is not the active contract. |
| lexical retrieval | IMPLEMENTED AND ACTIVE | `lexical_score()` (term-overlap, BM25-flavored) over up to 2000 children (in-memory corpus scan). |
| fusion | IMPLEMENTED AND ACTIVE | `rrf()` over RANKS only (k=60): four rankings (docs, parents, dense, lexical). G2 gate 6 semantics. |
| document grouping | PARTIALLY IMPLEMENTED | `selected_documents` = RRF-fused doc ids (top 10), each carrying the profile's `semantic_summary`. No doc-level evidence budget beyond that. |
| filtered child retrieval | MISSING | No document-filtered second-stage child search; selected children are the global dense+lexical RRF union capped at 40. |
| G3 reranker | IMPLEMENTED AND ACTIVE | `apply_rerank()` reranks BOTH `selected_documents` (on `semantic_summary`) and `selected_children` (on chunk text) with the pinned cross-encoder; candidate set never changes (ordering only); loud failure when unavailable. |
| graph augmentation | IMPLEMENTED AND ACTIVE | Corpus-authorized bidirectional hop1 (D2): seeds from entities attached to in-scope evidence; facts filtered to evidence-authorized corpus; 8-seed / 20-fact caps; HIGH_MEDIUM allowlist. |
| EvidenceBundle | PARTIALLY IMPLEMENTED | Typed lanes v2 (graph/text), but text items are admitted WITHOUT a support gate (D4/D4.1 REJECTED — the observed 96-item bundles) and there is no hierarchical budget. |
| synthesis | IMPLEMENTED AND ACTIVE | Deterministic-template-v2: graph claims + verbatim text passages; abstains only when both lanes empty. |

## 2. Feature checklist (production v4)

| Feature | Status |
|---|---|
| document summary vectors | MISSING (doc routing = lexical profile only) |
| section/parent summary vectors | PARTIALLY — parents get Qdrant points (hash-embed) and enter the dense lane, but they are not a dedicated routed summary index |
| globally searchable child vectors | ACTIVE (hash-embed-v1, both tiers: 28 child + 28 parent points in the I2 corpus) |
| independent representation retrieval | ACTIVE (4 lanes, per-hit provenance) |
| RRF | ACTIVE (ranks only) |
| document aggregation | PARTIAL (top-10 RRF doc ids; no budget/expansion) |
| document/section filters | MISSING |
| parent→child deepening | PARTIAL (siblings-under-hit-parent join only; no full section resolution) |
| exclusion of already-selected doc_ids | MISSING |
| MMR/diversity | MISSING |
| Pass-2 corpus reach | MISSING (no second pass anywhere in production) |
| FAST/HYBRID/GRAPH execution plans | MISSING in production — they exist ONLY as measurement constructs in `eval/measure_layers.py` |
| evidence-authorized graph seeding | ACTIVE (D2) |
| bounded hierarchical EvidenceBundle assembly | PARTIAL (typed lanes v2; no support admission, no hierarchical budget — D4/D4.1 findings) |

## 3. Deterministic summary audit (frozen I2 corpus)

### Document summaries

- Algorithm: extractive sentence scoring (word-frequency centroid), top-N
  sentences in document order, word-boundary truncation. Produced TWICE:
  `chunker.py` `document_summary` (max 6 sentences / 1600 chars) and
  `document_profile_builder.py` `semantic_summary` (max 5 sentences /
  1100 chars, computed over parent texts). Only `semantic_summary` is
  stored in `documents.retrieval_profile` and used for routing.
- Input: full normalized document text (chunker) / parent texts (profile).
- Max size: 1600 / 1100 chars.
- Selection: extractive centroid (not abstractive).
- Vectorization: NONE (lexical scoring only).
- Storage: `documents.retrieval_profile.semantic_summary` (JSONB) +
  chunk-plan `document_summary` (routing-card artifact only).
- Identity: document row (content-derived doc_id); no separate summary id.
- Provenance: `summary_contract=document-summary-v1` in the profile.
- Quality: **TOO SHALLOW FOR PRIMARY ROUTING.** Concrete examples from
  the frozen corpus:
  - `cyber/authentication.txt` → "Authentication establishes who a user
    is; authorization decides what they may do."
  - `cyber/encryption_basics.md` → "Encryption protects data
    confidentiality at rest and in transit."
  - `cyber/incident_response.pdf` → "Incident response proceeds through
    phases: preparation, detection, containment, eradication, and
    recovery."
  Each ≈ title + first sentence. Sessions/MFA/revocation, key
  management, and the recovery phase (which a routing query would need)
  are absent. For short single-parent documents the profile summary
  collapses to the opening sentence.

### Section/parent summaries

- Algorithm: `summarize_children()` — per-child 1-sentence extractive
  summaries, then a second extractive centroid over the concatenation
  (two-level centroid, stable under reorder); max 3 sentences / 600
  chars. Child rows also carry a 2-sentence / 420-char summary.
- Input: child chunk texts of the fanout group (fanout=4).
- Max size: 600 chars (parent), 420 chars (child).
- Selection: extractive centroid.
- Vectorization: hash-embed Qdrant points (same 512-dim contract as
  children) — but no dedicated summary index.
- Storage: `chunks.summary` on tier=parent rows; Qdrant payload
  carries `summary` + `tier`.
- Identity: `chunk_id(doc, index, text)` — content-derived.
- Provenance: none beyond chunk identity (no summary contract field).
- Quality: **PARTIALLY ENCOMPASSING — duplicated-child problem
  confirmed.** In the frozen corpus every document is single-parent
  (1-2 children << fanout 4), so parent summary == child summary ==
  child text head. Example (`psych/cognitive_load.md`): child summary,
  parent summary, and child text all begin with the identical sentence
  "Cognitive load theory distinguishes intrinsic load … from extraneous
  load …". Parents currently add almost no abstraction at this scale;
  they duplicate child content into the dense lane (28 parent points
  mirroring 28 child points).

## 4. Answers to the D4.1-derived questions

1. **q4 COMPOSITION_REQUIRED — can v4 assemble multiple
   sections/documents before synthesis?** NO. The bundle assembles
   per-candidate items (claims keyed to one fact/passage each); there
   is no stage that composes evidence across sections or documents.
   Synthesis validates each claim against its own support items.
   COMPOSITION_REQUIRED remains an open category for the future
   retrieval control plane.
2. **document_summary false-support behavior** → consistent with the
   audit: document summaries are extractive openings used for routing,
   and D4.1 showed them producing confident false supports when scored
   as evidence. R1 conclusion: treat document summaries as ROUTING
   representations, never as exact evidence items in the bundle.
3. **section_summary duplication** → confirmed above; the deterministic
   two-level centroid is stable but at current fanout/size it does not
   produce abstraction for primary hierarchical routing. Do not modify
   the generator (frozen); the control plane must treat parents as
   "may equal child content" representations.
4. **No support classifier** → the audit records the consequence: TEXT
   admission currently has no gate (D4/D4.1 REJECTED), so the control
   plane cannot rely on a per-passage support signal yet.

## 5. Gap summary vs the intended architecture

Intended: SUMMARIES ROUTE / CHILDREN PROVE / GLOBAL CHILD SEARCH
PROTECTS RECALL.

Present: global child search protects recall ✓; children prove (in
bundle) ✓ (unbounded); summaries route ✗ in the intended sense —
document routing is a thin lexical profile match, parents duplicate
children, and no summary-led Pass-2 / document aggregation / section
resolution / filtered deepening / MMR exists. FAST/HYBRID/GRAPH plans
are eval-only.

Also recorded (D4.1-adjacent): the ACTIVE embedding contract is
hash-embed-v1 — the "dense" lane is deterministic hash structure, not
neural semantics. The neural embed contract exists but is not active
(embedder sidecar down at audit time). This constrains any dense-led
routing design.

## 6. Stop line

Audit complete. No implementation started. No files beyond this report
and its work log were created.
