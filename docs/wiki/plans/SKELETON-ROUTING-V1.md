---
title: "SKELETON-ROUTING-V1 — how the document skeleton (profile + atoms + pMAP) routes, bridges and is judged at query time"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "DESIGN OF RECORD — designed and implemented by the agent under the owner's delegation (2026-09-23: \"if you want you can design whatever is missing and implement it, i trust you, as long as you can justify why this atomic profile skeleton is used for routing, cross domain, etcs in compiler design\"). Flag-gated: POLYMATH_CHAT_SKELETON_ROUTES, POLYMATH_CHAT_CONTEXTUAL_JUDGE (both live since 2026-09-23, register 11.441). V1.1 (§9) rides the same flags; its probe doors have their own flag POLYMATH_CHAT_SKELETON_PROBES, left OFF on evidence."
owner: "@king"
scope: "Chat retrieval over document corpora (cinema): route activation, path preservation, judged seats, contextual (path-aware) judgement. No new model, no LLM judge, no re-embedding, no prompt rewrite."
implements: "DOCUMENT-SKELETON-V1 §4; DOCUMENT-RAG-COMPLETION-V1 Parts C/D (routes + one-hop GRAPH) and the Part A amendment (the question's cross-encoder score is not the final veto for indirect evidence)."
---

# SKELETON-ROUTING-V1

## 1. The owner's intent in one paragraph
Retrieval should reach knowledge the owner does not know how to ask for.
- Chunk-level semantics is automatic with RAG.
- The skeleton works at the document level: an LLM-written profile per book, addressable atoms, and pMAP per section.
  It finds documents, finds similar documents, and bridges documents at the abstract level.
- Evidence is always real chunks.
- A chunk found through the skeleton must keep that discovery path, and must be judged by what it contributes along the
  path, not only by its literal similarity to the question.
- No LLM judge (latency). No hydration of skeleton text.
- WILDCARD is where this matters most.

## 2. Why the atomic profile skeleton is the right routing substrate
Each surface answers a different routing question. The code-level authority is `surface_registry.py`.

| Surface (family) | Routing question it answers | Why it cannot be replaced by chunk RAG |
|---|---|---|
| questions / searches (direct, multi-vector) | "Which book answers a question phrased like mine?" | The owner's wording rarely matches a book's vocabulary. The profile states the book's answerable questions in reader language. |
| theories / concepts (semantic / mechanism atoms) | "Which book explains the *mechanism* behind my question, even in another domain?" | A mechanism ("delayed resolution builds anticipation") is stated abstractly in the profile. The chunks that explain it may never mention the owner's domain words. |
| seealso / bridge / tension / inversion / anchor (relational atoms) | "Which neighbouring, contrasting or transferable knowledge sits next to this book?" | These are between-document relations. No single chunk carries them. |
| latent_pattern / boundary (mechanism atoms) | "Which structure recurs, and where does the claim stop?" | Structure and scope are document-level properties. |
| recallq (rediscovery atoms) | "Which book is the natural anchor for this question?" | Anchoring is a whole-book judgement. |
| pMAP routing signature + semantic hooks (per section) | "Inside a nominated book, which SECTION carries it?" | It turns a book-level hit into a section, then into that section's real chunks. |

**Atoms are addressable per item.** One probe per abstract idea, so a single strong concept can route even when the rest
of its book is off-topic. The global profile point averages a book. The atoms keep each idea separable. That is what makes
cross-domain bridging possible.

## 3. The flow (what the code now does when the flags are on)
1. **The compiler plans the facets.** q0 + USER aspects (existing). The profile scout nominates documents from the
   profile's multi-vectors, and those become PROFILE probes. The bridge compiler derives BRIDGE probes from the nominated
   concepts (existing). Every probe carries its origin.
2. **Doors open from the plan and the mode (`skeleton_routes.apply_skeleton_routes`), never from one intent word:**
   - HYBRID: the profile → pMAP door (lane E) + mechanism atoms nominate documents. SEEALSO fan-out (lane G) opens when the
     scout nominated documents.
   - GRAPH: + SEEALSO fan-out + graph destination (lane H) + graph facts. One hop (D8). The compiler's `graph_useful` no
     longer vetoes the owner's GRAPH choice.
   - WILDCARD: every door: all atom kinds, latent rescue (lane D), G, H, with 3 judged seats per route.
   - FAST / GNN: unchanged, by the owner's definitions.
3. **pMAP finds sections; retrieval fetches real chunks** (lane E, existing). The section's routing signature (Postgres)
   now travels with its children as the path's *need*.
4. **Every skeleton hit keeps its path** (`skeleton_paths`).
   - Lanes D / E / G / H stamp `rt:latent` / `rt:pmap` / `rt:seealso` / `rt:graph` beside the primary id.
   - The query-stratified fusion (LQF-V2, on) gives each path its own stratum and preserved top seats, so it survives the
     120-candidate cap.
   - Each route is registered as an aspect, so the judge reserves it `route_prefix_seats` seats.
   - Route ids are never plan query ids and never coverage lines.
5. **Contextual judgement: the existing cross-encoder, no LLM** (`contextual_judge`).
   - Direct candidates keep the question's score.
   - Skeleton-route candidates are judged against **"question — need"**, whatever the question scored (the need is the
     route's section signature / atom / destination). This sets `route_score` = σ(path) × connection.
   - A PROFILE / BRIDGE probe candidate is re-judged only when the question alone would veto it (σ < 0.5).
   - A need must connect to the question: one extra call scores every skeleton need against the question. Below
     `contextual_conn_floor` (0.3) it earns nothing (the vague "everything involves uncertainty" bridge).
   - A rescue (σ ≥ 0.5 on the path) sets `context_score`.
   - **The question's score is never overwritten.** The replay showed that overwriting it let path chunks displace strong
     direct evidence (Rabiger's "the audience knew more than she did" was lost on the suspense question).
   - Bounded: ≤ 4 needs × 3 candidates + 1 connection call.
   - Scope: `POLYMATH_CHAT_CONTEXTUAL_JUDGE=1` = every opened mode; `wildcard` = WILDCARD only (deployed).
6. **Selection: the existing composer.** The relevance / diversity / fill slots keep the question's order.
   - A route earns an aspect seat ONLY through a candidate that serves its need (`route_score` ≥ floor). It is
     "represented" only by such a candidate.
   - A PROFILE / BRIDGE path may seat a rescued candidate.
   - With paths on and the judge off, routes reach the judge and win seats on merit alone. That is where the measured gain
     came from.
   - WLK2C reuses a rescued row's contextual score and never recomputes it, so no question-only filter comes back.
7. **Synthesis: real chunks only.** A latent seat is labelled with the need that found it (E3 / S1c). No skeleton text is
   hydrated.

## 4. What stays unchanged
- The profile prompt (it already asks for mechanisms, transferable concepts and neighbouring knowledge).
- Embeddings.
- The GNN mode.
- FAST.
- The answer-level abstention rules.

## 5. Latency budget
- Route seats add ≤ 2–3 judged candidates per opened route.
- The contextual judge adds ≤ 13 cross-encoder pairs per turn, only when indirect candidates are at risk.
- Both are measured in the replay and the live check (§7). No LLM call is added.

## 6. Flags and rollback
- `POLYMATH_CHAT_SKELETON_ROUTES=1` → doors by plan + mode, path ids, route seats, GRAPH hop.
- `POLYMATH_CHAT_CONTEXTUAL_JUDGE=1` → path-aware judgement (requires the first).
- Both default off: byte-identical behaviour when unset (tests).
- Rollback = unset + bounce.

## 7. Evaluation
- `docs/wiki/experiments/skeleton-routing-2026-09-23/`:
  - `replay.py` ($0): today's five stored plans × {off, paths, judge};
  - the owner-capped live check (≤ 10 queries).
- Success means:
  - skeleton paths reach the final evidence;
  - direct evidence is still present;
  - no answer loses its direct grounding;
  - judge latency stays bounded.

## 8. Known gaps (next slices)
- **Atoms.** Since 2026-09-08 only ONE atom per kind per cinema book is active (≈ 10 per kind are inactive). The global
  profile point still holds 10–15 items per field. The repair (re-activate / re-project the full atom set) waits for the
  owner.
- ~~**Lane D (latent rescue) carries no need text yet.**~~ Closed in V1.1 (§9): the latent abstraction / transfer text that
  found the parent is its need.
- **WILDCARD's sweep** can emit a "principle" that is only a profile question with no source. That needs a grounding check.
- **Per-probe skeleton routing.** Built in V1.1 (§9.2) and measured: it does not pay yet, so its flag stays off. The limiter
  is probe quality (§9.4), not the door.

## 9. V1.1 — what the live check taught, and what changed (2026-09-23 evening)

### 9.1 The live check of V1 (5 of the owner's 10 queries; register 11.441)
Same five questions as RETRIEVAL-PATHWAYS-5Q, flags on, after one bounce:

| turn | skeleton lanes in final evidence (before → after) | skeleton chunks cited (before → after) | retrieval time (before → after) |
|---|---|---|---|
| HYBRID "weighty movement" | 2 → 3 | 0 → 2 | 15.1 → 14.3 s |
| WILDCARD same | 1 → 5 | 0 → 3 | 15.3 → 18.4 s |
| HYBRID "suspense without dialogue" | 5 → 8 | 4 → 6 | 11.5 → 12.3 s |
| WILDCARD same | 4 → 10 | 4 → 8 | 10.7 → 14.0 s |
| GRAPH "lighting and colour" | 9 → 19 | 8 → 19 | 14.4 → 13.8 s |

Counts are lane memberships (a chunk found by two skeleton lanes counts twice). Every answer kept its direct grounding.
The +13 s on the HYBRID suspense turn was the compiler (11.3 s that turn) and synthesis, not retrieval.

It also exposed four defects:
1. **Receipts:** `latent_selection` was always null (the LATENT-DIAGNOSTICS frame was wired where WLK2C's seat
   calibration belongs), and the path-aware judge left no receipt.
2. **The graph path's need was a document id.** The judge read "question — doc_3f9a…".
3. **The skeleton lanes ran one after another** (D 1.3 s + E 1.5 s + G 0.4 s + H 1.9 s).
4. **The judge read at most 4 needs, in prefix order.** A path whose needs sat lower was never judged.

### 9.2 Probe doors — built, measured, and left off (`POLYMATH_CHAT_SKELETON_PROBES`)
"The skeleton works with my subqueries":
- Each planned probe drives the dual-read door itself.
  - A PROFILE probe (a question from one book's profile) goes into THAT book's pMAP sections.
  - A BRIDGE probe starts at its source book and adds the books the profile and atoms nominate for it.
  - A USER facet takes the nominated books.
- Children are ranked against the question blended with the probe (the unit mean of the two vectors).
- Candidates are tagged `[probe id, rt:probe]` and keep the probe as their need.

Replay of tonight's five plans, deployed config ± probe doors ($0):
- The probe chunks sat at union ranks 65–110. They rarely reached the judge.
- Judged against the question, most scored below zero.
  - The probes themselves were often off-target ("How do television techniques influence film editing…" for a suspense
    question).
  - They reached the final set in 2 of 5 turns, and changed it only once.
- In WILDCARD they displaced two cross-domain finds (*Force Dynamic Life Drawing*, *The Laban Workbook*). The set
  dropped from 8 books to 6.

So the flag stays off, and the code stays (`_probe_order`, `_doc_fair_parents`, `_blend`, `dualread_search(docs=, nominate=,
signatures=)`) for the probe-quality slice (§9.4).

### 9.3 What shipped (rides `POLYMATH_CHAT_SKELETON_ROUTES`; the probe flag stays unset)
- **Parallel skeleton lanes.** Lanes D–H run concurrently on a pool of their own (`parallel_route_lanes`). They are merged in
  the fixed lane order, so the union is the sequential run's (test-proven).
- **Every path carries a readable need.**
  - Latent rescue: the latent abstraction / transfer text of the best hit (`LatentParent.need`).
  - Graph destination: the fact that reached the book ("lighting influences mood", from the hop's subject / predicate /
    object), never its doc id.
- **The path-aware judge is path-fair.**
  - The connection check runs first, over every skeleton need, in one call. A vague need earns nothing and no longer spends its
    path's turn.
  - Each path's strongest usable need is judged before any path gets a second.
  - WILDCARD reads up to 6 needs (one per door); other modes read 4.
- **Receipts (S1d).**
  - `latent_selection` = WLK2C's seat calibration.
  - `retrieval_trace.contextual` (judged / needs / pairs / promoted / vague).
  - `retrieval_trace.probe_routes` (when probes run).
  - Their timings sit under `trace_ms`.

Replay, production V1 against V1.1 in the deployed config (tonight's five plans):
- The final evidence set is identical in 5 of 5 turns.
- Engine core time: 5.0 → 3.8 s, 6.7 → 4.8 s, 5.2 → 3.7 s, 6.4 → 4.3 s, 6.3 → 4.0 s.
- Retrieval wall time is 1.3–2.3 s lower per turn.
- The WILDCARD judge now reads 6 needs in 0.45–0.64 s (V1: 3 needs, about 0.2 s). The parallel lanes pay for it.

Evidence: `docs/wiki/experiments/skeleton-routing-2026-09-23/`:
- `live_results.json`, `live_compare.json`: the V1 live check.
- `replay_probes.json`: probe doors.
- `replay_v1_deployed.json` against `replay_v11_deployed.json`.

### 9.4 Next (not started)
- **Probe quality gate.** Score each PROFILE / BRIDGE probe against the question with the same cross-encoder before it
  spends candidate slots and judged seats, one batched call. Route only well-connected probes through the probe doors, then
  re-measure §9.2.
  - "A vague bridge earns nothing" moves from judge time to plan time.
  - This is the compiler-side half of the owner's "skeleton works with my subqueries".
- The atom repair (§8) still waits for the owner.

