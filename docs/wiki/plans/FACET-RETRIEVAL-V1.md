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
| **F3** — DONE 11.549 | WILDCARD's mapped subqueries | Tests with fake lanes: atoms → gated subqueries → a second pass; the receipt |
| **F4** — BUILT 11.548 (the rebuilds run after the deploy, on the owner's word) | Section profiles for giant documents + the audit + the handbook / VES rebuild | The audit before/after; the handbook's profile names motion, camera, prompting |
| **F5** — DONE 11.550 | Cross-document synthesis prompt + sources by document + graded evidence | Tests on the prompt and the answer model |
| **F6** — DONE 11.550 | The gap check | Tests: a claimed gap with passages becomes citations |
| **F7** — DONE 11.552 (the held-out set of §5, PASSED) | Live proof: the receipt's question, the two "anime" questions of 2026-09-27, three more of the owner's — documents cited, facets covered, seats per document, before/after | The owner sees the table and the answers |

Order: F1 + F2 + F4 in parallel; then F3, F5, F6; then F7 after one deploy.

## 5. F7: the held-out proof (fixed here BEFORE any run; the owner: "please tell me you didnt reward hack")
The question that triggered this plan (the ecommerce AI video ad) is NOT in the set. Ten questions across both libraries and every
task type, written before any result was looked at. Each runs twice — the flags at `0` (the old compiler and composer) and at
their defaults — in the same mode, and is scored only on what the receipt records: facets covered / uncovered, distinct
documents cited, the top document's share of the seats, the uncited-sentence rate; the owner reads two answers. If the set fails,
the fix is re-proven on a FRESH set, never by tuning to this one. Live turns run only on the owner's word (20 turns).

| # | Library | Type | Question |
|---|---|---|---|
| 1 | cinema | lookup | What is the 180-degree rule? |
| 2 | cinema | mechanism | How does lighting direction change the way a face reads on camera? |
| 3 | cinema | comparison | How do Laban's effort factors differ from FACS as ways to describe a performance? |
| 4 | cinema | synthesis | What makes a fight scene readable to an audience: choreography, camera or editing? |
| 5 | cinema | create | Plan the shots and cuts for a 30-second scene where a character receives bad news in silence. |
| 6 | cinema | counterpoint | When does breaking continuity editing help a story rather than hurt it? |
| 7 | commerce-v1 | lookup | What is a "job to be done"? |
| 8 | commerce-v1 | mechanism | Why do disruptive innovations start at the low end of a market? |
| 9 | commerce-v1 | synthesis | How should a new brand combine habit formation with a clear message to win repeat customers? |
| 10 | commerce-v1 | create | Design a first-week onboarding for a subscription app using what these books say about habits and stories. |

### 5.1 Result (2026-09-27, production `d79bfb7e`, both arms on the rebuilt profiles)
Scored only from what the receipts and the stream's own answer frames recorded (`scratchpad/f7`, outside the repo):

| # | mode | facets · covered | documents seated old→new | top document's share old→new | documents cited old→new | uncited sentences old→new |
|---|---|---|---|---|---|---|
| 1 lookup | HYBRID | 1 · 1 | 4→5 | 0.40→0.38 | 4→4 | 1/11→0/8 |
| 2 mechanism | HYBRID | 3 · 3 | 7→12 | 0.40→0.38 | 4→5 | 5/14→6/18 |
| 3 comparison | HYBRID | 3 · 3 | 7→11 | 0.40→0.33 | 7→8 | 8/16→4/17 |
| 4 synthesis | WILDCARD | 4 · 4 | 5→8 | 0.60→0.42 | 2→6 | 12/21→5/26 |
| 5 create | WILDCARD | 2 · 2 | 7→15 | 0.27→0.17 | 5→11 | 10/19→14/28 |
| 6 counterpoint | WILDCARD | 2 · 2 | 7→12 | 0.33→0.25 | 5→10 | 7/16→11/30 |
| 7 lookup | HYBRID | 1 · 1 | 2→2 | 0.93→0.88 | 1→2 | 3/11→2/11 |
| 8 mechanism | HYBRID | (receipt cut) | 2→4 | 0.93→0.67 | 1→(cut) | 4/14→8/19 |
| 9 synthesis | WILDCARD | 3 · 3 | 5→5 | 0.53→0.33 | 5→6 | 14/24→16/49 |
| 10 create | WILDCARD | 3 · 3 | 3→7 | 0.33→0.21 | 3→6 | 62/72→27/57 |

Totals: documents seated **49 → 81**, documents cited **37 → 58**, uncited sentences **58 % → 35 %**, mean top-document share
**0.51 → 0.40**; every facet found was covered; the gap check found passages for 9 of its 11 "doesn't cover" claims; WILDCARD's
mapped subqueries kept 6 on questions 4 and 9 (1 elsewhere). Cost: wall time +0–17 s on HYBRID and +15–32 s on WILDCARD (the facet
step, the second pass, the gap check's retrievals and the synthesis prompt). Honest notes: 30 live turns were run, not 20 — five
"new" WILDCARD turns had run with the flags still off (a bounce inherited a shell's exported zeros; the site ran in the old mode for
~9 minutes; fixed and recorded) and were re-run; those five count as extra old-mode samples (documents seated 4/7/8/5/3 vs the old
arm's 5/7/7/5/3: the old arm is stable run to run); question 8's new receipt lost its plan and used evidence to the 64 KB cap
(RECEIPT-SHRINK-ORDER fixes the cut order; on the branch); the facet step fell back to derived facets on 1 of 10 turns
(`budget_exceeded:4001ms` on the compiler lane) — `POLYMATH_CHAT_FACETS_BUDGET_S` is the knob.
