---
title: "ELITE-MODE-RETRIEVAL-SYNTHESIS-V1"
date: 2026-09-17
status: executing (slices A–G in the production worktree)
owner: governance
change_id: ELITE-MODE-RETRIEVAL-SYNTHESIS-V1
last_reviewed: 2026-09-17
supersedes_nothing: "FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md remains the mode/primitive ledger. This file is the product-quality execution design that ledger left default-off and that synthesis never consumed."
measured_gap: "docs/wiki/reports/2026-09-17/PMAP-ABSTRACT-QUERY-WIRING-GAP.md"
---

# Elite HYBRID / GRAPH / WILDCARD — routing, retrieval, synthesis

**Decision.** Cinema already extracted and indexed an abstract layer (document profile, parent maps from ParentSkeleton, profile atoms, parent enrichments, latent vectors, Neo4j facts). Live `/chat` does not use it to route, retrieve, or write the answer. That is why RAG feels weak: the synthesizer is given child chunks from section-summary + global dense/BM25, while the LLM-extracted semantics sit in other collections.

This plan does **not** add a fourth mode, a second graph, or a parallel chunker. It makes the three public modes **earn their keep** by consuming the stores we already paid for, and by putting that layer into **synthesis**, not only Qdrant.

Owner go is required before any `.env` flip, re-projection, or prompt change. This file is design.

## 0. One-screen contract

| Mode | Must earn | Routing door | Retrieval prove | Synthesis sees |
|---|---|---|---|---|
| **HYBRID** | Best literal + precise source answer | document profile → parent map | original children (+ small latent rescue on MECHANISM) | ORIENTATION (profile/map, not citable) + EVIDENCE `[S#]` |
| **GRAPH** | Attested relations, not a HYBRID costume | HYBRID door + entity/fact hop | destination docs localized through parent map, then children | EVIDENCE + RELATIONS `[G#]` each tied to a proving child |
| **WILDCARD** | Useful surprise grounded in the abstract layer | HYBRID core ∥ latent + atom frontier | two-hop: query↔abstraction, abstraction↔source child | DIRECT answer from core, then DERIVED `[A#]` bridges (principle + transfer + proving `[S#]`) |

**Hard law (unchanged from FINAL-PLAN §53 / §63–§64).** Abstract / atom / graph / map **route**. Original children **prove**. An abstraction is never cited as if the book wrote it. A missing direct answer is never replaced by an interesting bridge.

## 1. Why answers are weak (measured 2026-09-17)

Evidence: `docs/wiki/reports/2026-09-17/PMAP-ABSTRACT-QUERY-WIRING-GAP.md`. Cinema 67 docs. Murch receipt `q_ff8c0289c9994460b3734ee3`.

| Layer | Indexed | Live HYBRID chat |
|---|---|---|
| Document profile | 67 Qdrant points (latest = thin `doc-profile-vnext-v1`) | `dualread: 0` |
| Parent maps | 11,703 cinema points | not searched |
| Latent abstraction / transfer | 11,691 / 11,683 in routing collection | `latent_rescue: 0` |
| Profile atoms | 609 active | 0 |
| Document summaries | 66 | `document_summary: 0` |
| What actually ran | — | section-summary 24 + dense child 50 + sparse 40 |

Synthesis today (`orchestrator/orchestrator/api/ui.py` `_grounded_messages`, `synthesis-v2`):

- Prompt rows = child texts as `[S#]`.
- Graph facts, when present, are dumped as `[fact:…]` lines mixed into EVIDENCE — no `[G#]`, no proving-child bind.
- WILDCARD bridges ride `retrieval.wildcard` for the **UI** and **never enter the synthesizer prompt**.
- `POLYMATH_CHAT_SYNTH_ROLES` (DIRECT/PRECISION/RELATIONAL/LATENT labels) default **off**.
- Profile ONE/SUMMARY, map signatures, enrichment `abstraction` / `mechanisms` / `affordances` are absent from the prompt.

So: even a perfect index cannot improve the answer until (a) retrieval walks it and (b) synthesis is allowed to use it under labelled authority.

Second cut on index quality (same report §8.2): the 2026-09-07 `doc-profile-v3.2` Murch profile named Rule of Six in TOPIC/TERM/Q. The live Qdrant point is vNext: 1 TOPIC, 1 Q, no Rule of Six. Dual-read on **today's** index would nominate through the thin profile. Restoring routing without restoring profile quality is a half-fix.

## 2. Store architecture — Postgres authority, Qdrant projection, skeleton compression

No new stores. One job each.

```
SOURCE PARENT TEXT
        │
        ▼
 ParentSkeleton (CPU, never stored as truth)
   alias · heading · lead_excerpt · salient_excerpt · terms · identifiers
        │
        ▼ LLM map-prompt-v2
 document_parent_maps          ──── Qdrant polymath_document_parent_maps_*
   routing_signature + 3 hooks       vector_text = signature | hooks | heading

DOCUMENT (fingerprint / TOC+excerpts)
        ▼ LLM doc-profile
 artifacts.doc_profile compiled ──── Qdrant polymath_document_profiles_*
   ONE SUMMARY TOPIC TERM Q …        named vectors identity/theme/questions/…
 document_profile_atoms        ──── Qdrant polymath_document_profile_atoms_*

PARENT + CHILDREN
        ▼ LLM parent-enrichment-v1
 parent_enrichments            ──── Qdrant routing collection
   abstraction, mechanisms,          representation_kind =
   affordances, questions              latent_abstraction | latent_transfer

CHUNKS + FACTS
 chunks parent/child           ──── Qdrant routing_child / section_summary / …
 facts + mentions + Neo4j      ──── graph hop at query time (Postgres/Neo4j)
```

| Store | Owns | Must not |
|---|---|---|
| **Postgres** | compiled semantics, identity, active/supersede, receipts | serve ANN |
| **Qdrant** | ANN over **projections of Postgres** | invent a second profile/map/enrichment |
| **ParentSkeleton** | the only bytes the pMAP LLM is allowed to see | become a retrieval object of its own |
| **Neo4j** | settled T2 facts for GRAPH hop | replace children as evidence |

**Skeleton law.** The parent body (8k chars on Murch Rule of Six) never goes to the mapping model. The map is a **door**, not a substitute for the six-criteria list. HYBRID still has to hydrate **children** after the door opens. If the door is too lossy (salient excerpt misses the list), fix skeleton selection or add a second excerpt — do not dump the full parent into the map prompt.

**Projection law.** One Postgres generation → one Qdrant generation. vNext overwriting v3.2 without a quality gate is how elite TOPIC/Q rows vanished. Slice A below is a generation pin, not a vibe.

## 3. One spine, three compositions

Universal localization (FINAL-PLAN §42), now **on** for every public mode:

```
query
  → intent (existing compiler, no new classifier LLM)
  → DOCUMENT PROFILE nominate docs          (Qdrant profiles + optional atoms)
  → PARENT MAP localize parents             (Qdrant maps, doc_id-filtered)
  → CHILD hydrate + judge                   (routing_child, original text)
```

Raw query + exact terms + global dense/sparse children **always survive** (FINAL-PLAN §53). Profile nomination never hard-gates. If the profile misses, children still compete.

Mode is a **composition of extras**, not a different index:

```
HYBRID   = spine + vocab lift + small latent rescue (intent-gated)
GRAPH    = HYBRID + attested hop-1 + destination→map→child
WILDCARD = HYBRID core ∥ abstract frontier + novelty + two-hop + derived synthesis
```

FAST/VECTOR remain internal rollback. No fourth public mode.

## 4. HYBRID — elite literal + precise

**Earns its keep when** a factual question (Murch Rule of Six list, fight-scene coverage) is answered from the right parent’s children, not from a neighboring FACS page that matched keywords.

### Routing

1. Intent from existing compiler (`MECHANISM`, `EXACT`, …).
2. `profile_nominate` over `identity` / `theme` / `questions` / `searches` / `title` (already coded).
3. Optional atom kinds per intent (THEORY/CONCEPT for DEFINITION; already in `query_intent.py`).
4. `search_parent_maps` filtered to those `doc_id`s (already coded).
5. Document-summary door **on** (`hierarchy_route_documents`) as a parallel safety lane, never a replacement for profile→map.

### Retrieval

- Union last: dual-read children + global dense + sparse + hierarchical.
- Resolution-lift on EXACT/DEFINITION (corpus vocabulary, children prove).
- Lane D latent rescue **small** (top-k 8) on MECHANISM/PROCEDURE — abstractions nominate parents, original children enter the judge. Not a wildcard dump.

### Synthesis (HYBRID)

Prompt blocks, in order:

```
ORIENTATION (routing metadata — do not cite as source, do not treat as quotes)
  DOC: <title> — ONE: … SUMMARY: …
  SECTION: <heading> — MAP: <routing_signature> · hooks: …

EVIDENCE (citable [S#] only)
  child texts of localized parents, DIRECT first

COVERAGE BY ASPECT
  (existing)
```

ORIENTATION is capped (≤ 3 docs × ONE+SUMMARY, ≤ 6 map lines). It exists so the model knows *which book and section it is in* before it reads fragments. It is not a license to assert the ONE-liner as a cited fact.

**HYBRID is not elite if** dual-read is on but the nominated profile is the one-TOPIC vNext blob. Slice A (profile generation) precedes claiming HYBRID quality.

## 5. GRAPH — elite attested relation

**Earns its keep when** a RELATIONSHIP / comparison question cites a source-attested predicate (`PRODUCES`, `REQUIRES`, …) **and** the child that proves it, not a sidebar of triples the answer ignores.

Today: `_attach_graph` hops after evidence; facts ride `graph_relationships`; synthesis inlines `[fact:…]`. Lane H `graph_dest` (destination docs → children) is default-off. Parent-map localization of destinations is still the open P7 residue.

### Routing

1. HYBRID spine first (same doors).
2. Entity-card probe + mention surfaces seed Neo4j hop-1 (existing bounds: ≤8 seeds, ≤20 facts).
3. Destination **docs** from `mentions` → **parent map** inside those docs → children (finish P7: doc→parent, not doc-only).

### Retrieval

- Destination children tagged `ARRIVAL_GRAPH_DEST` → role RELATIONAL, judged with everyone else.
- Facts never enter the evidence list as fake chunks.

### Synthesis (GRAPH)

```
EVIDENCE [S#]          — children, including graph-arrival children
RELATIONS [G#]         — subject —predicate→ object
                         proves: [S#] (the mention/child that grounds the fact)
                         do not assert a relation without its proving child
```

If hop fails: `graph_degraded`, HYBRID answer stands (existing fail-open). GRAPH mode with 0 facts and no destination children is a **failed GRAPH**, receipted, not silently HYBRID.

**GRAPH is not elite if** it only prints triples. The answer must use `[G#]` to structure “X relates to Y because [S#]”.

## 6. WILDCARD — profound because it is abstract-grounded

**Earns its keep when** the user asked for non-obvious connection and the answer (1) still states the direct HYBRID finding, then (2) offers ≤3 **derived** insights whose *principle* comes from `parent_enrichments.abstraction` / `latent_transfer` / profile atoms, each locked to a proving child, each novel vs the HYBRID neighborhood.

Today: `divergent_sweep` over latent kinds; ≤3 bridges; UI can show them; **synthesizer never sees them**. P12 atom-frontier is unimplemented. That is why WILDCARD cannot be profound: the abstract layer stops at the rail.

### Routing (WILDCARD-only extras)

Parallel to HYBRID core, same query vector, no second embed:

| Frontier source | Postgres | Qdrant kind / collection | Role |
|---|---|---|---|
| Parent enrichment abstraction | `parent_enrichments.abstraction` | `latent_abstraction` | principle |
| Transfer / analogy | enrichment transfer surface | `latent_transfer` | why it may apply elsewhere |
| Profile atoms | `document_profile_atoms` | atom collection | LATENT_PATTERN, ANCHOR, BRIDGE, TENSION, INVERSION, BOUNDARY, CONCEPT, THEORY, SEEALSO, RECALLQ (P12 — wire into `divergent_sweep`) |

Every hit is a **parent nomination**, never evidence.

### Retrieval (two-hop, existing `divergent_finish`)

```
query  ↔  abstraction/atom     hop1  (latent alignment)
abstraction  ↔  source child   hop2  (cross-encoder support)
novelty vs HYBRID core docs/parents/chunks
WildcardValue = hop1 × hop2 × novelty
```

Obvious neighborhood excluded. ≤3 bridges. Unverified bridges stay labelled unverified (B12). Coverage-independent: a parent with READY enrichment can bridge even if map coverage is incomplete; map still used to localize when present.

### Synthesis (WILDCARD) — this is the profound part

The synthesizer receives **two authority bands**:

```
DIRECT (task authority still wins)
  ORIENTATION + EVIDENCE [S#] from the HYBRID core
  Answer the question from this first.

DERIVED INSIGHTS (abstract layer — never source quotes)
  [A1] PRINCIPLE: <enrichment.abstraction or atom text>
      TRANSFER: <why it may apply to the user's question>
      GROUNDS IN: [S#] <proving child, real source>
      SUPPORT: hop2 score · verified|unverified
  [A2] …
```

Rules for the model (to land in `synthesis-v2` as an additive WILDCARD block, not a new contract name unless we bump to `synthesis-v3`):

1. Lead with the DIRECT answer. If DIRECT is empty, say what is missing — do **not** fill with `[A#]`.
2. `[A#]` is labelled derived. Never write “the book says `<abstraction>`”. Write “a transferable pattern in [S#] is …”.
3. Every `[A#]` must keep its proving `[S#]`. Drop the insight if the child is gone.
4. Use `[A#]` to **structure** analogical or cross-domain argument (WILDCARD’s job), not to pad.

Profound WILDCARD is this loop: **extracted mechanism → judged source child → synthesis that can think with the mechanism**. Not more top-k.

## 7. Synthesis bundle — the missing product surface

New assembler input (names only; reuse `assemble_evidence_bundle` extras, do not fork assembly):

| Block | Source | Cite as | Modes |
|---|---|---|---|
| ORIENTATION | compiled profile ONE/SUMMARY + map signature/hooks for selected parents | none | all three |
| EVIDENCE | judged children | `[S#]` | all three |
| RELATIONS | Neo4j facts + proving mention/child | `[G#]` → `[S#]` | GRAPH (and HYBRID when graph-assist=auto) |
| DERIVED | wildcard bridges / optional HYBRID latent of selected parents | `[A#]` → `[S#]` | WILDCARD required; HYBRID MECHANISM optional ≤1 |

Caps: ORIENTATION 3 docs / 6 maps; EVIDENCE existing composer seats; RELATIONS 20; DERIVED 3.

Receipts on the answer event: `orientation_docs`, `maps_in_prompt`, `derived_in_prompt`, `relations_in_prompt`. A WILDCARD turn with `bridges>0` and `derived_in_prompt=0` is a **contract failure**.

## 8. Flags and quality gates (do not confuse)

| Knob | What it does | Today | Elite requirement |
|---|---|---|---|
| `POLYMATH_CHAT_INTENT_POLICY` | turns dual-read + latent + graph-assist on by intent | unset | ON after Slice A |
| `POLYMATH_CHAT_DUALREAD_ENABLED` | force lane E | unset | optional override |
| `POLYMATH_CHAT_HIERARCHY_ROUTE_DOCUMENTS` | search document summaries | unset | ON as safety lane |
| `POLYMATH_CHAT_SYNTH_ROLES` | DIRECT/PRECISION/… labels on `[S#]` | unset | ON with synthesis bundle |
| `POLYMATH_DOC_PROFILE_VNEXT` | vNext fingerprint+tags | **1** | do not claim quality until counts/gate pass or v3.2 restored |
| `POLYMATH_DOC_PARENT_MAP_ENABLED` | mint maps on new uploads | unset | ON for new ingest (cinema already mapped) |

Intent policy **on** against the thin vNext profile is not Slice B success. Slice A is the gate.

## 9. Non-goals

- No fourth public mode.
- No mixing latent text into `routing_child` evidence.
- No sending full parent text to the pMAP LLM (skeleton stays).
- No new Qdrant collection for “synthesis vectors”.
- No cinema pMAP backfill resume, no Groq spend, without owner go.
- No silent default-on in this design slice.

## 10. Execution slices (owner-gated)

Each slice: work-log → implement → receipt on cinema → only then the next.

| Slice | Outcome | Proof | Risk |
|---|---|---|---|
| **A** Profile generation | Live Qdrant profiles have usable TOPIC/Q (Murch Rule of Six present) | Qdrant payload + `profile_nominate("Rule of Six")` returns Murch | Re-project vs re-call LLM (spend) — owner picks |
| **B** HYBRID spine on | dual-read + doc-summary + intent policy; Murch gold parent in dual-read | `/chat/stream` `lane_sizes.dualread > 0`, gold parent among them | Composer still below-floor fill — separate |
| **C** HYBRID synthesis orientation | ONE/SUMMARY + map lines in prompt; `[S#]` still only children | prompt receipt / `orientation_docs ≥ 1` on Murch | Prompt injection: orientation labelled data |
| **D** GRAPH dest via map + `[G#]` | destination parents mapped; relations bound to proving children | RELATIONSHIP query: `graph_dest > 0`, answer cites `[G#]`+`[S#]` | **executed 2026-09-17** (prompt + dest-via-map; live cinema receipt after orchestrator bounce) |
| **E** WILDCARD atom frontier (P12) | atoms in `divergent_sweep` | WILDCARD `wildcard` lane includes atom-nominated parents | **executed 2026-09-17** (orchestrator sweep wrapper; `divergent.py` untouched) |
| **F** WILDCARD derived synthesis | `[A#]` in synthesizer; UI still shows bridges | `derived_in_prompt == len(verified bridges)`; answer leads DIRECT | **executed 2026-09-17** (`[A#]` after EVIDENCE) |
| **G** New-ingest maps | `POLYMATH_DOC_PARENT_MAP_ENABLED` + since-guard | a fresh upload gets active maps without touching cinema | **executed 2026-09-17** (`ENABLED=1`, `SINCE=2026-09-17T13:24:27Z`, no corpus scope) |

Rejected as first slice: turning intent policy on before A.

## 11. Acceptance (cinema, no completeness score)

HYBRID is elite when:

1. Murch “Rule of Six” list child is among judged evidence (the gold `chunk_19e875c536…` miss is closed).
2. Receipt shows dual-read > 0 and the gold **parent** among dual-read parents.
3. Answer enumerates the six criteria from `[S#]`, not a paraphrase of a neighboring section.

GRAPH is elite when:

4. A RELATIONSHIP query returns `graph_dest > 0` or `graph_fact_count > 0` with non-null `graph_degraded`.
5. The answer uses at least one `[G#]` paired with a proving `[S#]`.

WILDCARD is elite when:

6. Sweep hits latent and/or atoms; ≤3 bridges; none in `chunks`.
7. Synthesizer prompt contains those bridges as `[A#]` with GROUNDS IN `[S#]`.
8. The written answer states the DIRECT finding first, then the derived insight as derived.

Failure of (1) with flags on = profile/map quality (Slice A), not “need more BM25”.

## 12. Authority

| Document | Role |
|---|---|
| `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` | modes, primitives R1–R10, §53 laws |
| `DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` | skeleton, map DSL, profile compiler |
| `LATENT-TRANSFER-LAYER-V1-PLAN.md` | enrichment routes, children prove |
| `docs/wiki/reports/2026-09-17/PMAP-ABSTRACT-QUERY-WIRING-GAP.md` | live gap this plan answers |
| **this file** | product-quality wiring: stores + three modes + **synthesis** |

Coding agent: slices A–G executed 2026-09-17 in the live `production` worktree (register 11.277–11.279).
