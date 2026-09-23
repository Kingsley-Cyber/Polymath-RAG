---
title: "DOCUMENT-SKELETON-V1 — what the document skeleton (profile + pMAP) is, what it is for, and how retrieval must use it"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "CANON — owner-stated 2026-09-23 (register 11.437). Read before touching retrieval, routing, ranking, WILDCARD, the document profile or pMAP."
owner: "@king"
scope: "Every chat retrieval mode over document corpora (cinema). Ingest producers (doc_profile, doc_parent_map) and query-time consumers (scout, bridges, lanes D / E / G / H, WILDCARD)."
---

# DOCUMENT-SKELETON-V1

## 1. The owner's law (2026-09-23, verbatim)
- "the skeleton job is to either help find document, similar documents and bridges other documents at the abstract level
  because semantics is automatic with rag. this is the bread ad butter of wildcard."
- "i dont think it should hydrae unless you c have a justified reason, and being to determinsitic it is at the document level
  and represent documents that whys its too overview to hydrate."
- "i dont want to implement a llm judge it adds latency"
- "ensure future coding models understands the deep skeleton structure to include pmap. i always remind yall."

## 2. What the skeleton is: two layers, both written by an LLM at ingest, both embedded

### 2.1 The document profile: one per document (DOCUMENT-PROFILE-V1)
- An LLM reads a document prompt and writes tagged fields.
- `shared/polymath_shared/document_profile/compiler.py` normalizes, validates and grounds them into a `Record`. Its
  fields:
  - identity: `one_liner`, `summary`, `topics`, `terms`;
  - direct: `questions`, `searches`;
  - semantic: `theories`, `concepts`;
  - discovery: `seealso`;
  - the research-index surfaces: `latent_pattern`, `anchor`, `recallq`, `tension`, `bridge`, `inversion`, `boundary`.
- `shared/polymath_shared/surface_registry.py` (CANONICAL-SURFACE-REGISTRY-V1) is the single authority for each surface:
  - **profile vector:** dense = title / identity / theme; multi = questions / searches / theories / concepts / seealso.
    These make the one global profile point per document.
  - **atom kind + family.** Atoms are the addressable items in their own collection:
    - mechanism = THEORY, CONCEPT, LATENT_PATTERN, BOUNDARY;
    - relational = SEEALSO, BRIDGE, ANCHOR, TENSION, INVERSION;
    - rediscovery = RECALLQ.
  - **lexical:** terms, topics, anchor.
  - **graph:** seealso / bridge / tension are `resolve_on_use`. They become a PROFILE_SYNTHETIC edge only after both ends
    resolve to real corpus documents, never a direct edge from profile text.
- Stored in Postgres, projected to Qdrant `polymath_document_profiles_*` (the profile point) and
  `polymath_document_profile_atoms_*` (atoms).

### 2.2 pMAP, the document parent map: one per retrieval-eligible parent section (DOCUMENT-SEMANTIC-INDEX-V1)
- `document_profile/parent_skeleton.py` builds a deterministic ParentSkeleton per parent, with no LLM: alias,
  heading_path, one source-authored salient excerpt, key terms, exact identifiers.
- The parent-map LLM writes, per parent, a `routing_signature`, `semantic_hooks` and `exact_identifiers`
  (`map_compiler.py` `CompiledMap`).
- Stored in Postgres, projected to Qdrant `polymath_document_parent_maps_*`.
- It routes a question to the right SECTION of the right document, and from there to that section's real child chunks.

**The skeleton = profile + atoms + pMAP.** A change to "the skeleton" that ignores pMAP is incomplete.

## 3. What the skeleton is FOR
1. **Find documents:** which books and which sections matter for this question.
2. **Find similar documents:** neighbours at the document level.
3. **Bridge documents at the abstract level:** concept, theory, tension and see-also links between documents that the
   question's words would never connect.

Chunk-level semantics is automatic with dense / sparse RAG. The skeleton adds the document-level, abstract routing that
chunk similarity cannot. **It is the bread and butter of WILDCARD.**

## 4. How retrieval MUST use it
1. **Route, don't hydrate.**
   - Skeleton text (profile fields, atoms, pMAP signatures) selects documents, sections and bridges.
   - The evidence handed to synthesis is REAL child chunks from those documents.
   - Skeleton text enters the prompt only with a stated, justified reason: a short label (the bridge that found a chunk),
     or a labelled derived principle bound to a real chunk, capped.
2. **A skeleton-found chunk keeps its path.**
   - The path = which profile item, pMAP route, bridge or atom found it.
   - It carries its own path id through fusion, the judge and synthesis.
   - Never file it under the literal question's id.
3. **Lanes switch on from the plan and the mode, not from one intent word.** GRAPH = see-also, one hop (owner decision D8).
   Skeleton lanes run whenever the scout nominated documents.
4. **No LLM judge on the retrieval path** (latency). Ranking stays deterministic:
   - per-path seats in fusion (LQF-V2 strata);
   - the existing cross-encoder;
   - the literal question as a floor;
   - the skeleton item as context only where a path needs it.
5. **The cross-encoder score against the literal question is not the final authority** for skeleton-found chunks
   (DOCUMENT-RAG-COMPLETION-V1 amends FINAL l.39).

## 5. Where it lives in code
- **Ingest, profile:**
  - `document_profile/{prompt.py, profile_prompt_vnext.py, context.py, compiler.py, grounding.py, projection.py,
    profile_atom.py, profile_atom_projection.py}`, plus `surface_registry.py`;
  - worker `doc_profile`.
- **Ingest, pMAP:**
  - `document_profile/{parent_skeleton.py, map_prompt.py, map_compiler.py, map_batches.py, parent_map_projection.py}`;
  - worker `doc_parent_map`.
- **Query time:**
  - `document_profile/profile_scout.py`: nominations → PROFILE probes (`ui._add_profile_expansion`);
  - `bridge_integration.py` + `bridge_compiler.py`: concept bridges → BRIDGE probes;
  - `candidate_engine.py` lanes:
    - D latent rescue;
    - **E dual-read (profile → pMAP → parent → children)**;
    - G SEEALSO fan-out;
    - H graph destination;
  - `chat_retrieval._retrieve_wildcard`: the WILDCARD atom frontier;
  - `query_intent.py`: lane switches per intent (the §6 defect).

## 6. Measured state (RETRIEVAL-PATHWAYS-5Q, register 11.436, five live cinema turns)

| Lane | Candidates | Cut before the judge | Reached the final evidence | Cited |
|---|---|---|---|---|
| dense child | 250 | 68% | 23.6% | 19.6% |
| pMAP dual-read (E) | 116 | 79% | 13.8% | 9.5% |
| latent rescue (D) | 82 | 87% | 6.1% | 6.1% |
| SEEALSO fan-out (G) / graph destination (H) | 0 | never ran | — | — |

Root causes (READ in code):
1. Lanes G / H are intent-gated (`query_intent.py` L149–L158, L182–L185). All five turns compiled to SYNTHESIS, GRAPH
   mode included.
2. Lanes D–I tag every hit with the PRIMARY query's id (`candidate_engine.py` `query_ids=[ctx.query_id]`, L814–L919). So
   the query-stratified fusion (LQF-V2, on) ranks skeleton hits inside the literal question's stratum, and the cap cuts
   them.
3. The judge scores each chunk against the literal question only.

## 7. Invariants for every coding session
- Read this file before touching retrieval, routing, ranking, WILDCARD, the profile or pMAP.
- Never remove a skeleton surface, or stop producing one.
- Never hydrate skeleton text into synthesis without a justified, labelled reason.
- Never add an LLM judge to the retrieval path.
- The skeleton includes pMAP.
