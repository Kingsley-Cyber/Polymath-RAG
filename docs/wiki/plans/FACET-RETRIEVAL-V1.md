---
title: "FACET-RETRIEVAL-V1 — a flat question answered from the underlying material across documents: facets, diversity by construction, mapped WILDCARD subqueries, profiles that match giant documents, cross-document synthesis"
date: 2026-09-27
last_reviewed: 2026-09-27
status: "ACTIVE — plan of record (register 11.545); the owner's decisions of 2026-09-27 are in §2"
owner: "@king"
scope: "The chat query compiler (facets), the one retrieval core every mode and /retrieve use (seats per facet, per-document quotas, MMR), WILDCARD's second pass (mapped subqueries), document profiles for giant documents, the synthesis prompt for synthesis tasks, the gap check. Not in scope: a document picker (rejected by the owner), new retrieval modes."
---

# FACET-RETRIEVAL-V1

## 1. The finding (2026-09-27, receipt `q_e09925df009649c6be872299`, WILDCARD, cinema)
The question "create an ecommerce story prompt and direction for an AI video ad that plays on emotions" got an answer that claimed
the library "doesn't bridge emotional direction to video model controls". The library does (`handbook.html`, "04. Motion core ›
Granular motion control", a table of control dialects per model). Three causes, all measured:
1. **A facet with no search.** The compiler's three USER queries were about storytelling and psychology; "direction for an AI video
   ad" got none. Only a PROFILE probe borrowed from another document ("Augmenting prompts for better text-to-video generation")
   reached the section, at rank 9, and it did not survive the cut to 37 reranked candidates.
2. **A profile that does not describe its document.** The handbook (3.2 MB, 802 sections) has a book-sized profile built from
   its front matter: core concepts `cpcs, cpcs-mx, compiler, yaml, json…`, "use for questions about how to HAS PROPERTY". The
   profile lane (dualread, the scout's probes, see-also and bridge atoms) cannot route motion, camera or prompt-control
   questions to it. The section maps exist (802 of 802); the door to them is blank.
3. **One document crowded the answer.** Of 15 seats, the Adweek copywriting book took 8 (53 %); Ogilvy, Bruce Block, the
   Multistage pipeline paper and the handbook were retrieved and cut. The dominance guard is 60 %, so it did not fire.
   The aspect seats seated nothing (`aspect_seats: []`): the aspects were weak.
Also: FACS, Grammar of the Shot and Film Directing Cinematic Motion were never searched for (no facet asked), and one section
deepening timed out (lane deadline 3 s).

## 2. The owner's decisions (2026-09-27, verbatim where it matters)
- "the compiler should be corpus agnostic for subqueries" — facets come from the QUESTION, never from which documents exist.
- "this should work for all retrieval layers" — the one core every mode uses, `/retrieve`, and deep research's searches.
- "book keeper is not the rag i want. cross document retrieval and why is good things … although the query was flat, it can
  most definitely be answered for underlying things" — no document picker; the system finds the connections.
- "abstractions should be elite and document synthesis" — the answer synthesizes principles across documents, then specifics.
- "if we need more retrieved chunks im open" — the evidence budget may grow.
- "maybe mmr, and max documents lanes of 3 to be chosen" — MMR over the final pool; at most 3 seats per document per lane.
- "wildcard should use its lanes to create better mapped subqueries" — WILDCARD's latent, atom, bridge and see-also lanes
  produce a second pass of subqueries mapped to what the library holds, per facet.
- "diversity is important" — the handbook has a direct answer, and the answer must still draw across documents.

## 3. Design
### 3.1 Facets (the compiler, corpus-agnostic)
- A facet is a part of the question that could be answered on its own: the compiler names 2–5 facets from the resolved request
  (no library names in the prompt, no profile input at this step), each with one USER-origin query. Existing aspect types
  (MECHANISM, CAUSAL, COMPARISON, COUNTERPOINT, PROCEDURE, EXAMPLE, ADJACENT) become the WAY a facet is asked, not the reason
  a query exists. `max_subqueries` (10) stays; PROFILE / BRIDGE / WILDCARD queries attach to the facet they serve.
- Every query carries `facet_id`; the plan carries `facets: [{id, name, query_ids}]`; the receipt carries
  `facets_covered` / `facets_uncovered` (a facet is covered when ≥ 1 of its queries returned evidence above the floor).
- A single-facet question (a lookup) is unchanged: one facet, one query.

### 3.2 Diversity by construction (the core, every mode)
- Seats: `synthesis_max` 15 → 24 (the owner is open to more chunks; the synthesis prompt already caps its context).
- Per facet: reserved seats (2 when the facet has evidence above `aspect_weak_floor`), generalizing today's aspect seats.
- Per document per lane: at most 3 seats (`compose_doc_soft_max` becomes a hard per-lane quota); across the set the dominance
  share drops 0.6 → 0.4 when ≥ 3 documents score within the gap.
- MMR: a real maximal-marginal-relevance pass over the reranked pool (λ = 0.7, cosine on the child embeddings already in hand)
  fills the remaining seats; the receipt says how many seats MMR changed and which documents it added.
- All of this lives in `candidate_engine.compose_final` (one place), so FAST / HYBRID / GRAPH / WILDCARD / GNN, `/retrieve`
  and deep research get it.

### 3.3 WILDCARD's mapped subqueries (second pass)
- Pass 1 runs the facets. WILDCARD's lanes (the atom frontier, verified bridges, see-also blends, latent candidates) return
  what the library holds around each facet; pass 2 turns those into subqueries (origin WILDCARD, `facet_id` set, ≤ 2 per
  facet, ≤ 6 total), gated against the question by the reranker (`probe_gate`, floor 0.2), then retrieved and fused like any
  other subquery. The receipt lists the mapped subqueries and what each found.

### 3.4 Profiles that match giant documents
- A document with more than 300 sections gets one **section profile** per top-level heading (the same surfaces a document
  profile has: questions, searches, concepts, see-also, anchor, bridge…), indexed beside document profiles and used by the
  same lanes (dualread, the scout's probes, see-also fan-out, bridges). The document profile itself is rebuilt from a
  stratified sample across ALL sections, never from the first pages.
- An audit script scores every profile against its document (coverage of the document's top terms and section titles by the
  profile's surfaces) and lists the worst; `handbook.html` and the VES handbook are rebuilt first.

### 3.5 Cross-document synthesis (the answer)
- For GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE tasks the prompt asks first for the principles (abstractions) the evidence
  supports, each cited from ≥ 2 documents where the evidence allows, then the specifics per facet, naming the documents; a
  "sources by document" panel; the uncovered facets are listed honestly (§3.6). Evidence graded as in deep research (strong =
  ≥ 2 documents, single source, contested).

### 3.6 The gap check (safety net)
- Every "the evidence doesn't cover X" sentence becomes a targeted search before it is written; found → added with citations,
  not found → "the passages found don't cover X", the searches tried in the receipt.

## 4. Slices
| Slice | What | Proof |
|---|---|---|
| **F1** — DONE 11.546 | Facets in the compiler + `facet_id` on queries + the receipt fields | Contract tests: the receipt's question yields ≥ 4 facets incl. "directing the AI video model"; a lookup yields 1; no library name in the prompt |
| **F2** — DONE 11.546 | Seats per facet, the per-lane document quota, dominance 0.4, MMR, 24 seats — in `compose_final` for every mode | Unit tests on fixed pools; `/retrieve` and every chat mode byte-identical when the flags are off |
| **F3** | WILDCARD's mapped subqueries | Tests with fake lanes: atoms → gated subqueries → a second pass; the receipt |
| **F4** | Section profiles for giant documents + the audit + the handbook / VES rebuild | The audit before/after; the handbook's profile names motion, camera, prompting |
| **F5** | Cross-document synthesis prompt + sources by document + graded evidence | Tests on the prompt and the answer model |
| **F6** | The gap check | Tests: a claimed gap with passages becomes citations |
| **F7** | Live proof: the receipt's question, the two "anime" questions of 2026-09-27, three more of the owner's — documents cited, facets covered, seats per document, before/after | The owner sees the table and the answers |

Order: F1 + F2 + F4 in parallel; then F3, F5, F6; then F7 after one deploy.
