---
title: "ENRICHMENT-SURFACES-AUDIT — do the skeleton, pMAP, profile (SEEALSO, questions) and atoms reach the answers? (production 7eb767d)"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "AUDIT — read-only; no code, flag or data changed. Nine defects found, none fixed; the fixes are owner decisions (§6). Same-day addendum (register 11.416): §8 field inventory, §9 owner intent + root cause (every enrichment lane is judged against q0), §6 revised to wire the fields in; §10 design lineage + WILDCARD finding + the owner's sequencing (document RAG before code RAG); §11 concepts / theories as routers to real chunks, not hydration (register 11.417); §12 owner intent = grounded learning value + where the path context is lost + the path-aware judge decision; §13 execution-design input mapped to code; §5 timing corrected (register 11.418); §14 proposed compiler contract assessed + admitted as input (register 11.419)."
owner: "@king"
scope: "Every document-enrichment surface, from its store to the evidence the synthesizer sees and the citations in the answer, measured on 1,508 live pipeline turns (cinema; 139 distinct questions, mostly qualification runs through the UI streaming endpoint) plus in-process replays and a static trace."
---

# ENRICHMENT-SURFACES-AUDIT

**Owner question, 2026-09-23:** audit the document extraction skeleton and the profile to see whether they are used and whether
they reach the answers, for example SEEALSO and questions.

**Method.** Evidence class per claim: EXECUTED (observed by running code or reading live stores) or READ (concluded from code).
- EXECUTED — the retrieval funnel of **1,508 live pipeline turns** (7 days to 2026-09-23, all modes, status ok). Every turn
  records in `query_receipts.meta.funnel` which lane brought each candidate chunk, the cross-encoder order, the rows the
  model saw (`selected`) and the rows the answer cited. Script: `receipt_audit.py`.
  - Population (corrected 2026-09-23, 11.418): all ran the real retrieval code on the live fleet through the UI streaming
    endpoint, but they are mostly qualification / harness runs, not owner-typed questions:
    - 139 distinct questions;
    - 1,128 of the turns on 2026-09-18;
    - 1,397 with deterministic synthesis and 111 with model synthesis.
  - The lane measurements describe the retrieval pipeline, mostly as configured before the subquery cap moved to 10.
- EXECUTED — store counts: Qdrant profiles, atoms and parent maps, plus the Postgres concept families and aliases the lift
  reads. Script: `surface_counts.py`.
- EXECUTED — in-process replays of real turns (no LLM call): the resolution-lift terms, one turn per intent, and the concept
  labels the bridge compiler receives. Script: `replay_probe.py`.
- READ — a static trace of every surface from producer to prompt at `7eb767d`, with spot-checked anchors.

All evidence is in `docs/wiki/experiments/enrichment-surfaces-2026-09-23/`.

## 1. Verdict per surface

"Evidence" means rows the synthesizer saw. "Alone" means no other lane found that chunk. All numbers cover 1,508 turns.

| Surface (cinema store) | Read at query time by | Reaches the evidence? | Reaches the prompt as text? | Verdict |
|---|---|---|---|---|
| **Parent skeleton** | nothing; it is an ingestion input to pMAP building | through pMAP only | no | used indirectly (via pMAP) |
| **pMAP** (11,993 routing points) | lane E dual-read (profile → map parents → children), lane H graph destination, the WILDCARD sweep, lift terms (hooks / identifiers) | yes, through lane E (below) | yes: ORIENTATION shows the signature and ≤ 3 hooks; identifiers never | **used, reaches answers** |
| **Profile identity / title / theme + questions + searches** (67 / 67 docs, v3.2; 984 questions, 991 searches) | RRF document nomination in the Profile Scout, lane E and lift document choice | yes, through lane E: **4,705 rows, 458 alone, cited in 1,069 turns** | ORIENTATION shows profile ONE / SUMMARY for ≤ 3 docs; question text never | **used for routing, reaches answers** |
| **Profile concepts / theories / seealso multivectors** (629 / 580 / 638 items) | nothing (`EXPLORATION_SURFACES`, `projection.py:28`, is read only by a test). Designed for GRAPH / WILDCARD discovery (`selection.py:8-12`), never wired | no | no | **produced, never read** |
| **Atoms** (609 for cinema: ≈ 1 per kind per doc) | Scout, lane G see-also fan-out, lift, WILDCARD, Corpus Explore | lane G: **175 rows, 87 alone, cited in 69 turns** (it fired in 93 turns) | only as coverage-line text or WILDCARD `[A#]` | used, but starved (defect 3) and rarely allowed (intent-gated) |
| **Aliases** (20 families, 71,934 aliases), **pMAP exact identifiers** (41,350), **profile terms** (668) | resolution lift (lane F) only | **no: 0 of 7,806 candidates in 7 days** | no | **dead in practice** (defects 1–2). pMAP hooks, profile topics and headings also feed the lift, but reach answers by other paths (§8) |
| **Document + section summaries** | lane A hierarchical route (votes + deepening) | **12,400 rows (59% of all evidence), 301 alone, cited in 1,199 turns** | no: removed before the prompt (EVIDENCE-DIET-V1, `ui.py:1538-1544`) | used for routing, reaches answers |
| **Latent abstraction / transfer points** | lane D latent rescue; the WILDCARD sweep | **1,158 rows, 400 alone** | WILDCARD `[A#]` only | used, reaches answers |
| **Entity cards** | lane A votes, graph seeds | through lane A | no | routing only |
| **Neo4j facts** | GRAPH mode, or HYBRID with RELATIONSHIP intent; lane H | lane H: 12 rows in 17 turns | yes, as `[G#]` relations | used; lane H is marginal |
| **Corpus map rows** | ASK mode only | not in chat | no | not read by chat |

**Headline.** 86% of the evidence the model saw (18,206 / 21,163 rows) was also found by plain dense / sparse child search.
- **9.1%** (1,917 rows) was found only by enrichment-driven lanes, which is 7.8% of cited rows.
- 4.9% came from subquery / bridge seats.
- **43% of turns (652 / 1,508) cited at least one row that only enrichment found.**

Per mode, the enrichment-only share of evidence is FAST 13.8%, HYBRID 7.1%, GRAPH 5.7% and WILDCARD 5.4%. GNN is 100%, since
its only lane is the GNN route.

Enrichment earns its place as a router: it seats unique evidence in about half of all turns. Its text rarely reaches the
prompt, which is by design: routing, never evidence.

## 2. Per-lane funnel (7 days, 1,508 turns)

| lane (source surface) | turns fired | chunks brought | → cross-encoder pool | → evidence | alone | → cited | alone |
|---|---:|---:|---:|---:|---:|---:|---:|
| A hierarchical (summaries) | 1,367 | 39,214 | 17,906 | 12,400 | 301 | 10,255 | 238 |
| B dense child (baseline) | 1,367 | 67,450 | 21,956 | 16,443 | 1,828 | 13,873 | 1,470 |
| C sparse child (baseline) | 1,026 | 39,777 | 12,315 | 7,857 | 707 | 6,904 | 810 |
| E dual-read (profile → pMAP) | 1,301 | 28,829 | 8,425 | 4,705 | 458 | 3,968 | 411 |
| D latent rescue (latent points) | 906 | 14,675 | 3,122 | 1,158 | 400 | 876 | 247 |
| G see-also fan-out (SEEALSO / BRIDGE / ANCHOR atoms) | 93 | 2,157 | 525 | 175 | 87 | 172 | 85 |
| I GNN route | 14 | 168 | 167 | 162 | 148 | 78 | 76 |
| H graph destination | 17 | 136 | 53 | 12 | 1 | 12 | 1 |
| **F resolution lift** (aliases, map ids, terms) | **1,301** | **7,806** | **2,797** | **0** | 0 | **0** | 0 |
| subquery / bridge seats (no lane) | 557 | — | — | 1,040 | — | 2,578 | — |

The cross-encoder decides. In the 952 turns where lift chunks entered its pool, 13,176 of the 14,337 evidence rows (92%)
came from cross-encoder ranks 1–15. The lift chunks sat at ranks 21 and below: 2,786 of their 2,797 pool seats. None of them
was also found by another lane.

## 3. SEEALSO and questions (the owner's two examples)

**SEEALSO**
- **The profile's 638 SEEALSO items (9.5 per doc) are never searched.** Only the atom store's 59 SEEALSO atoms (≈ 1 per doc)
  are.
- Lane G probes children with SEEALSO / BRIDGE / ANCHOR atom text. It runs only for RELATIONSHIP and EXPLORATORY intents, so
  it fired in 93 of 1,508 turns.
- When it fires it works: evidence in 70 turns, citations in 69, and half of its evidence rows (87 of 175) came from no
  other lane.
- In the answer prompt, SEEALSO text appears only as coverage-line text, where it is mis-rendered (defect 6), or as
  WILDCARD `[A#]`.
- In the bridge compiler it appears as the literal label "SEEALSO" (defect 2).

**Questions**
- The profile's 984 questions (14.7 per doc) are searched on every non-FAST turn. They are one of five surfaces in the RRF
  document nomination (with identity, title, theme and searches) that feeds the Profile Scout, lane E and the lift's document
  choice.
- Through lane E they help seat 4,705 evidence rows, 458 of them alone. The receipt keeps no per-surface attribution inside
  the RRF, so the questions' own share cannot be separated from the other four.
- Question text never reaches the prompt. RECALLQ atoms (65) are a separate atom kind that only the RECALL intent reads.

**Skeleton.** The parent skeleton has no query-time reader. It shapes the pMAP at ingestion, and the pMAP carries it into
answers through lane E and ORIENTATION.

## 4. Defects (ranked by effect on answers; none fixed)

1. **Resolution lift picks identifier tokens, never vocabulary** (EXECUTED + READ).
   - One replay per intent (9 of 9) lifted terms like `A1, A2, A3`, `A100, A7, B2`, `ADR12, ADX16, AIM57`, `A1, A4, ANG6618`.
   - Cause (`resolution_lift.py:105-118`): the score has no query-relevance term. `semantic_support` is never set, locality
     is always 1 because `chat_retrieval.py:363` passes `top_evidence_docs=docs`, and identifier form earns +0.14.
     Identifier-shaped pMAP ids and digit-bearing aliases therefore win.
   - Cost: in 7 days the lane fired in 1,301 turns, put 0 of 7,806 chunks into the evidence, and still took 2,797
     cross-encoder seats (≈ 3 of 32 in 952 turns). It spent about 1 s per turn (1,062 ms in the replay).
   - **The 71,934 aliases reach retrieval only through this lane, so today they contribute nothing to answers.**
2. **The bridge compiler sees atom-kind names and raw doc ids, never concept text** (EXECUTED + READ).
   - Three real questions produced 24 concept labels: 15 kind names (`THEORY`, `TENSION`, `SEEALSO`…), 9 `doc_…` ids and
     0 text.
   - Cause: the Scout sets `surface = atom_kind` (`profile_scout.py:144`), and `bridge_integration.py:46` prefers
     `representative_surface` over `representative_text`. Profile-only nominations carry no text, so they fall through to
     the doc id.
   - `test_bridge_integration.py:31` hides this by setting surface = text.
   - The effect on bridge quality is not measured. The bridges still read on-topic, because the compiler also sees the
     question.
3. **Cinema's atom store is the wrong profile generation** (EXECUTED + READ).
   - The store holds 609 cinema atoms, about 1 per kind per doc (the vNext canary shape), while cinema's live profile is
     v3.2 with 580 THEORY, 629 CONCEPT and 638 SEEALSO items.
   - Cause: `scripts/profile_atom_canary.py:33-40` projected the latest artifact, which was vNext. `commerce-v1` holds
     ≈ 10 atoms per kind per doc.
   - **About 90% of cinema's v3.2 THEORY / CONCEPT / SEEALSO items never reach an atom lane.**
4. **Lane F keeps only the first lifted term's rows** (EXECUTED + READ).
   - `chat_retrieval.py:371-377` searches up to 3 terms × 6 rows, but `candidate_engine.py:860` caps the lane at 6 rows.
     Terms 2 and 3 are embedded and searched, then thrown away.
   - The receipt still lists all three terms.
5. **Role labels are dropped** (READ). The row rebuild at `ui.py:3519` drops the evidence role, which was already known, and
   also the latent-selection seat labels (`latent_role`, `latent_lineage`, set at `ui.py:2192-2197`).
6. **The coverage block tells the model it has no evidence for see-also probes** (READ).
   - `_coverage_lines` (`ui.py:2370-2389`) lists PROFILE and BRIDGE probes as aspects. `candidate_engine.py:1506` marks
     them weak, so the prompt says "NO EVIDENCE RETRIEVED: say so explicitly".
   - `_maybe_resolve` (`ui.py:1805`) already excludes these origins; the coverage block does not.
7. **ORIENTATION follows routing documents, not cited parents** (READ). `ui.py:3557-3568` keys it to lane A's selected
   documents and sections, so the pMAPs of the parents actually cited are never loaded. GNN turns get no map lines.
8. **Lane D has an all-or-nothing budget** (READ). `latent/rescue.py:56-58` returns no parents when the first search passes
   400 ms, discarding what it already gathered.
9. **Receipt gaps** (EXECUTED + READ). `meta.latent` is always `None` on v2 (`chat_retrieval.py:654`). The
   latent-selection seats are not persisted. Per-lane `lane_ms` is computed but not written, so the receipt cannot say which
   lane is slow (§5).

## 5. Where the time goes (corrected 2026-09-23, register 11.418)

`meta.phase_ms` holds cumulative marks (ms since the turn started), not durations:
- compile = the `compile` mark;
- retrieval = `retrieve` − `compile`;
- synthesis = `generate` − `assemble`.

This section first read the `retrieve` mark as the retrieval duration and reported "≈ 30 s live retrieve". That was wrong.

Owner-style turns since the `5df4536` deploy (n = 6, all with model synthesis, all before the 11.411 thinking fix):

| mode | compile | retrieval | synthesis | total |
|---|---:|---:|---:|---:|
| HYBRID (n 2) | 12.6 s | 18.4 s | 51.4 s | 82.5 s |
| GRAPH (n 1) | 11.6 s | 19.3 s | 34.0 s | 65.0 s |
| WILDCARD (n 1) | 11.6 s | 19.8 s | 42.8 s | 74.3 s |
| GNN (n 2) | 11.8 s | 3.0 s | 48.6 s | 63.5 s |

- **Compile ≈ 12 s.** The compiler call (1.6–3.2 s) and the bridge compiler (1.5–2.6 s) are two sequential model calls and
  account for about 4–5 s. The receipt does not attribute the rest.
- **Retrieval ≈ 19 s** for the modes with depth lanes; GNN takes 3 s.
- **Synthesis 34–51 s**, before thinking was turned off on the wire.
- **The 7-day "before" medians are not a clean baseline.** They are mostly harness turns: deterministic synthesis, different
  plans, compile 2.4–2.7 s, retrieval 6.1–9.2 s. The GNN turns (the same population on both sides) show no deploy effect:
  compile 10.3 → 11.8 s, retrieval 3.3 → 3.0 s.
- Attributing the time needs per-step timings (defect 9 / §6 fix 6) and a timing trace of one slow turn (§13).

## 6. Recommended fixes (owner decisions; none executed; revised after the owner's statement of intent, §9)

The owner's intent (§9) is that these fields are used at query time: they feed the conditional rank system, so that
information at a different abstraction level can win in retrieval and synthesis, and they give the bridge compiler more
bridges and hops. The fixes therefore wire the fields in; none of them removes a field. Ordered so the root cause comes first:

1. **Give every enrichment probe its own lineage: conditional rank for lanes D, E, F, G and H.** Each probe gets its own query
   id, its probe text and a lineage class (LATENT, PROFILE, PRECISION, GRAPH) instead of q0's id. The probes are:
   - the latent-kind search (D);
   - the profile → map route (E);
   - the lifted term (F);
   - the atom text (G);
   - the graph destination (H).

   The existing LATENT-QUERY-FUSION-V2 then preserves each probe's local winners. The judge scores those chunks against
   their probe text, which is the pattern WLK2C already uses for bridges, with a q0-groundedness floor so off-topic chunks
   still fail. This is where the dropped, latent-but-relevant chunks come back.
   - Measure with the owner's metrics: local-winner survival per lineage, q0 groundedness, chain precision.
   - GNN stays out: it is its own mode.
2. **The bridge compiler uses the profile's abstract fields.** Its grounded concept set becomes the documents' `concepts`,
   `theories` and `seealso` text (1,847 items for cinema) plus atom text, instead of kind names and doc ids (defect 2). The
   bridges it writes already get conditional judging, so this is the shortest path to "more bridges".
   - Includes the one-line precedence fix in `bridge_integration.py:46` and the test that hides it.
3. **Re-project cinema's v3.2 `concepts` / `theories` / `seealso` into the atom store.** This is a projection from existing
   artifacts: no LLM, no re-ingest, and it respects the corpus-scoped atom contract (11.376). Lane G, the Scout and Corpus
   Explore then see about ten times more items (defect 3).
4. **SEEALSO for hops in GRAPH mode.** Each `seealso` item points to target documents, whose children become GRAPH-lineage
   probes under fix 1. One hop fits the current architecture.
   - Bounded multi-hop traversal is the item CONTINUITY defers until Librarian DONE_AND_PROVEN, so it needs the owner's
     word to lift that deferral.
   - Today no mode reads the `seealso` multivector, although `selection.py:8-12` names GRAPH / WILDCARD as its consumers.
5. **Repair the resolution lift so it becomes a PRECISION lineage.**
   - Select terms by relevance to the query, and drop identifier-shaped map ids and aliases unless the query names them.
   - Keep every term's rows; its chunks then ride fix 1.
   - `terms` (668) and the pMAP's 41,350 `exact_identifiers` reach answers only through this lane.
   - Until the repair lands, `resolution_lift="off"` in `INTENT_POLICY` saves about 1 s and 3 judge seats per turn at no
     measured loss.
   - For CODE-KNOWLEDGE-V1 identifiers ARE the vocabulary, so settle this before slice C10.
6. **Receipts.** Persist per-probe lineage, local-winner survival, `latent_selection`, per-lane `lane_ms` and per-subquery
   timings. Without them, fixes 1–5 and the ≈ 12 s compile + ≈ 19 s retrieval (§5) cannot be attributed.
7. **Synthesis sees the abstraction level.** Carry role and latent seat labels past `ui.py:3519`, so the model knows a row is
   COMPLEMENTARY or LATENT rather than DIRECT. Stop listing PROFILE / BRIDGE probes as "NO EVIDENCE RETRIEVED" aspects
   (defects 5–6). This is how a different abstraction level also wins in synthesis, not only in retrieval.

Each fix is a separate admitted slice. Fixes 1, 2, 4, 5, 6 and 7 are orchestrator / shared code (stale-bundle fence, bounce).
Fix 3 is a data projection.

## 7. Evidence and reruns

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
set -a; . ./.env; set +a
D=docs/wiki/experiments/enrichment-surfaces-2026-09-23
.venv/bin/python $D/receipt_audit.py $D/receipt_audit.json      # funnel per lane, enrichment-only share, lift ranks, latency
.venv/bin/python $D/surface_counts.py $D/surface_counts.json    # profile + atom stores per corpus
PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control \
  .venv/bin/python $D/replay_probe.py $D/replay_probe.json      # lift terms per intent + bridge-compiler labels (no LLM)
.venv/bin/python $D/field_inventory.py cinema $D/field_inventory.json   # every profile / pMAP field with item totals (§8)
PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control \
  .venv/bin/python $D/wildcard_probe.py 4 $D/wildcard_probe.json   # WILDCARD frontier on real turns + direct atom frontier (§10)
```

All three are read-only and cost nothing. `receipt_audit.py` reads a rolling 7-day window, so a rerun sees newer turns;
the committed JSON is the 2026-09-23 run.

## 8. Field inventory: every field the profile, the parent skeleton and the pMAP produce (addendum, same day)

Owner, same day: the skeleton "is more than see also". It is: the profile alone has nine fields. Counts are for cinema
(EXECUTED, `field_inventory.py`); the readers are READ from code, with anchors.

### 8.1 Document profile v3.2 (67 of 67 documents; 5,151 list items)

| Field | Cinema total | How it is stored | Read at query time by | Reaches the evidence? | Reaches the prompt as text? |
|---|---:|---|---|---|---|
| `one` | 67 | inside the `identity` dense vector (`compiler.py:909-912`) | RRF document nomination (Scout, lane E, lift document choice) | yes (lane E) | yes: ORIENTATION, ≤ 240 characters, ≤ 3 documents (`ui.py:2464-2516`) |
| `topics` | 661 | pooled into the same `identity` vector ("Topics: …", one vector per document, not per topic); also payload | the same RRF; the lift (TOPIC terms) | yes, as part of `identity` | no |
| `summary` | 67 | the `theme` dense vector (`compiler.py:914-917`) | the same RRF | yes (lane E) | yes: ORIENTATION, ≤ 400 characters |
| `questions` | 984 | multivector (one vector per question) | the same RRF (MaxSim) | yes (lane E); its own share is not separable inside the RRF | no |
| `searches` | 991 | multivector | the same RRF | yes (lane E) | no |
| `concepts` | 629 | multivector | **nothing** | **no** | no |
| `theories` | 580 | multivector | **nothing** | **no** | no |
| `seealso` | 638 | multivector | **nothing** | **no** | no |
| `terms` | 668 | payload only (not a vector, `projection.py:4`) | the lift only (TERM terms) | **no** (lift 0 of 7,806) | no |

- The document title (source name) is a tenth vector, `title`, in the same RRF. It is not a compiled field.
- **Tally:**
  - 1,975 list items (38%) route answers (`questions`, `searches`);
  - 661 (13%) route as one pooled string per document (`topics`);
  - **2,515 (49%) never reach an answer** (`concepts`, `theories`, `seealso`, `terms`).
- `profile_nominate` searches only `ANSWER_SURFACES` = identity, theme, questions, searches, title (`projection.py:27, :40`).
  Its `surfaces` argument could take `EXPLORATION_SURFACES`, but no caller passes it.

### 8.2 Parent skeleton (per parent; deterministic; built at ingestion, never stored for query time)

| Field | Used for |
|---|---|
| `heading_path` | the pMAP prompt, and the compact heading inside the pMAP `routing` vector text (`parent_map_projection.py:64-75`) → lanes E, H and the WILDCARD sweep. Passage breadcrumbs in the prompt come from the chunk's own heading path, not from the skeleton |
| `salient_excerpt`, `lead_excerpt` (headingless parents only), `key_terms` | the pMAP prompt only (they shape the signature and hooks the model writes) |
| `identifiers` | the pMAP prompt, which yields `exact_identifiers` (§8.3) |
| `region_role`, `ordinal`, `source_position`, `alias`, `parent_id`, `text_hash`, `skeleton_hash` | bookkeeping and prompt layout. Query-time region roles come from a separate chunk lookup (`candidate_engine.py:708`) |

The skeleton has no query-time reader. Its value reaches answers only through the pMAP fields it shapes.

### 8.3 pMAP (11,993 active maps)

| Field | Cinema total | Read at query time by | Reaches the evidence? | Reaches the prompt as text? |
|---|---:|---|---|---|
| `routing_signature` | 11,993 | the `routing` vector (signature + hooks + compact heading) → lane E dual-read, lane H localization, the WILDCARD sweep | yes (lane E: 4,705 rows) | yes: ORIENTATION, ≤ 160 characters |
| `semantic_hooks` | 35,838 (≈ 3 per map) | the same `routing` vector; the lift (MAP_HOOK terms) | yes, through the vector | yes: ≤ 3 hooks per map in ORIENTATION |
| `exact_identifiers` | 41,350 (≈ 3.4 per map) | **the lift only** (MAP_ID terms). Not in the routing vector, never in the prompt | **no** | no |
| `quality_flags`, hashes, `provider`, `model` | — | ingestion and projection bookkeeping | — | — |

1,023 maps carry an identifier shaped like `A1` / `A445` / `ADR12` (`^[A-Z]{1,4}[0-9]{1,5}$`). These are the tokens the lift
picked in every replay (defect 1).

### 8.4 vNext atoms (atom store; frozen 2026-09-08 canary snapshot, not produced now)

The atom store holds ten vNext kinds for cinema, about one atom per kind per document (609 in total).
- Three kinds have a v3.2 counterpart: CONCEPT, THEORY, SEEALSO. The v3.2 profile carries about nine items per document for
  each, but none of those are in the atom store (defect 3).
- Seven kinds exist only as this snapshot: ANCHOR, BRIDGE, RECALLQ, LATENT_PATTERN, INVERSION, TENSION, BOUNDARY. The
  current v3.2 prompt does not produce them. `POLYMATH_DOC_PROFILE_VNEXT=0`.
- Readers: Scout, lane G (SEEALSO / BRIDGE / ANCHOR), Corpus Explore, WILDCARD, the lift.
- Only lane G's share is attributable in receipts (175 evidence rows). The Scout's and Corpus Explore's effect lands in the
  subquery / bridge rows. The bridge compiler receives these atoms as kind names (defect 2).

## 9. Owner intent and the root cause (same day)

**Owner, 2026-09-23:** the profile fields exist to be used at query time. They feed the conditional rank system so that
information at a different abstraction level wins in retrieval and synthesis, and they allow more bridges and hops, so
the compiler's bridging must use them. GNN is excluded. In GRAPH, SEEALSO can drive hops or traversal. The owner's
diagnosis: the design got complicated when subqueries entered the equation, and chunks that were retrieved (subdued,
latent, but relevant) were dropped when ranked against the original query.

**The code agrees with that diagnosis** (READ, anchors at `7eb767d`):
1. Every enrichment lane tags its chunks with q0's query id: lanes D, E, F, G, H, I at `candidate_engine.py:814, 846, 863,
   882, 900, 919`.
2. The LATENT-QUERY-FUSION-V2 fusion assigns lineage by query. `lineage_class` puts any lane of q0's query in class Q0
   (`ranked_fusion.py:82`), and local-winner preservation keeps each QUERY's top five across all of its lanes
   (`preserved_winners`, `ranked_fusion.py:159`). An enrichment lane's winners must therefore beat q0's own dense / sparse
   winners to be preserved.
3. The turn makes exactly one judge call, and it scores every candidate against q0: `select_evidence` →
   `rerank_children(result.context.query, rows)` (`candidate_engine.py:1447`).
4. Only BRIDGE-origin subqueries get a conditional second pass: WLK2C grades the bridge pool against the bridges and seats
   it with C5, gated by q0 grounding (`ui.py:2140-2206`). The enrichment lanes never enter that pool.

**The measurement shows the consequence** (EXECUTED, `receipt_audit.json`, 1,508 turns). Survival from the judge's pool into
the evidence falls with the lane's distance from q0's own signal:

| lane | pool → evidence | chunks only this lane found: pool → evidence |
|---|---:|---:|
| B dense child (q0's own signal) | 75% (16,443 / 21,956) | 55% (1,828 / 3,294) |
| A hierarchical (summaries) | 69% | 35% |
| C sparse child | 64% | 19% |
| E dual-read (profile → pMAP) | 56% | 24% (458 / 1,934) |
| D latent rescue | 37% | 21% (400 / 1,861) |
| G SEEALSO fan-out | 33% | 20% (87 / 426) |
| H graph destination | 23% | 3% (1 / 32) |
| F resolution lift | 0% | 0% (0 / 2,797) |

The bridge compiler is the one path whose output gets conditional judging, and it is fed atom-kind names instead of the
profile's concepts, theories and seealso (defect 2). So the conditional rank system exists, but the enrichment the owner
built for it never reaches it. Fixes 1 and 2 (§6) close that gap.

## 10. Design lineage: what the repository already says about the owner's idea (same day)

**Owner, 2026-09-23** (summarized from the message):
- Complete document RAG before CODE-KNOWLEDGE-V1.
- Alongside the pMAP, the structure extraction's conditional ranking and the document-level extractions should power
  document- and domain-level synthesis with different ideas.
- The reranker number should not be the final determinant.
- Each skeleton field (questions, searches, concepts, theories…) should be a modular conditional bridge and ranking.
- Query → subqueries → bridges, document routing, chunk / document retrieval, synthesis.
- WILDCARD was meant to be the poster-child layer that fully embodies this: documents are abstracted far enough that
  domain-level synthesis and bridges let latent chunks related to the query win.
- "I don't think I designed and solidified the idea."

| Owner idea | Where the repository already says it | Built? | Measured today |
|---|---|---|---|
| Abstract documents so latent-but-relevant knowledge wins, and synthesis thinks with it | FINAL §1.2 Depth (l.190: how far beyond the user's vocabulary to search); FINAL §41 WILDCARD objective (l.1829: "maximize useful surprise subject to source grounding, semantic support, novelty"); ELITE §6 (l.243: "extracted mechanism → judged source child → synthesis that can think with the mechanism"); LQF-V2 l.21-22 ("what information needs (explicit + latent) must be satisfied, and what evidence ranks highest FOR EACH") | partly | Latent lanes survive the judge 20–37% of the time; dense survives 55–75% (§9) |
| Every profile field is modular | FINAL §7 (l.451): the field → retrieval contract gives every field a technique and a role in each mode | for ROUTING (lanes A, D, E, F, G, H); not for ranking | concepts / theories / seealso multivectors never searched; atoms vNext-sized (§8) |
| … as conditional bridges and rankings | WLK2A finding 5 (l.76) and recommendation (l.88): judge a chunk against q0 AND the bridge that retrieved it, with roles DIRECT / COMPLEMENTARY / DIVERGENT, "NOT max(q0, bridge)". Option (b) (l.96), bridges from profile concept text, was held back because good concept text was "unverified" | BRIDGE subqueries only (WLK2C) | v3.2 profiles now hold that text (1,847 items), but the bridge compiler receives kind names (defect 2) |
| The reranker number is not the final determinant | LQF-V2 l.22-24: "different ranking authorities at different stages": retrieval rank (does it answer THIS local need?) → fusion → C4 (is this need tied to q0?) → C5 (does it add useful information?) → CA4. ELITE §6 (l.214): WildcardValue = hop1 × hop2 × novelty | bridges (WLK2C) and the WILDCARD sweep only | **Contradicted by the FINAL governing law** (l.39) "cross-encoder = final judge" and §51 (l.2244) "source relevance authority", inherited from the July "cross-encoder as the sole scoring authority" decision. Never amended; every other candidate gets one judge call against q0 |
| Query → subqueries → bridges + document routing + chunk / document retrieval + synthesis | CHAT-QUERY-COMPILER-PLAN, PROFILE-SCOUT-V1, WLK2C, LQF-V2, CORPUS-EXPLORER-V1 | yes, live | 127 of 1,508 turns (8.4%, every mode) skip retrieval entirely: the compiler's no-retrieval route, owner backlog B20 |
| WILDCARD is the poster child | FINAL §40 (l.1768): all ten atom kinds strong, SEEALSO / BRIDGE / ANCHOR on, broad frontier, ≤ 3 discoveries, each atom → MAP → child → support validation. ELITE §6 (l.190): "profound because it is abstract-grounded", with DIRECT + DERIVED `[A#]` synthesis bands | frontier yes; atom frontier wired (slice E); `[A#]` synthesis executed 2026-09-17 | See the WILDCARD finding below |
| Document- and domain-level synthesis with different ideas | ELITE §7 (l.245): bundle ORIENTATION / EVIDENCE / RELATIONS / DERIVED. FINAL §44–47: roles DIRECT / PRECISION / RELATIONAL / LATENT | bundle yes; roles are dropped at `ui.py:3519` (defect 5) | The synthesizer cannot tell a DIRECT row from a LATENT one |

**WILDCARD finding** (EXECUTED, `wildcard_probe.json`; 4 real turns replayed):
- Each turn produced 55–59 latent candidates and 3 verified bridges.
- All 12 bridges came from the latent abstraction / transfer channels, none from atoms.
- Run directly, the same atom-frontier calls work: 12 atoms and 16 atom-nominated parents per turn. None wins a bridge; the
  cinema atoms are thin vNext labels such as "Camera operation decisions".
- In the live path that frontier sits in a bare `except: pass` with no receipt (`chat_retrieval.py:919`).
- Whether the `[A#]` bridges reach the synthesis prompt is not recorded in the receipts.

**Verdict.** The owner designed most of this, across four owner-authorized documents written in two weeks: FINAL
2026-09-07, ELITE 2026-09-17, WLK2A 2026-09-18, LQF-V2 2026-09-19. It was never joined into one design:
1. FINAL's law "cross-encoder = final judge" was never amended to LQF-V2's multi-authority ranking, so the code applies it
   to everything except bridges and the WILDCARD sweep.
2. No document says each profile field is its own conditional bridge with its own ranking:
   - FINAL §7 made the fields modular for ROUTING;
   - WLK2A / LQF-V2 made conditional RANKING work for queries and bridges;
   - nobody joined the two.
3. WILDCARD embodies it only at the latent-point level:
   - its atom frontier is fed thin vNext atoms and never wins a bridge;
   - the profile's concepts / theories / seealso never reach it;
   - HYBRID / GRAPH get none of its two-hop judgement.

**Sequencing (owner, 2026-09-23):** document RAG is completed before CODE-KNOWLEDGE-V1. The first slice of that track is one
consolidated plan of record that does four things:
- amends the FINAL law to the multi-authority ranking;
- joins FINAL §7 with the WLK2A / LQF-V2 ranking model field by field;
- names WILDCARD as the full embodiment (every field, two-hop value, DERIVED synthesis), with HYBRID / GRAPH taking the
  subsets §7 assigns them, GNN excluded, and GRAPH using SEEALSO for hops;
- lists the §6 fixes as its execution slices.

## 11. Concepts and theories: routers to real chunks, not hydration (owner guidance + design sketch, same day)

**Owner, 2026-09-23:** "We have to be careful selecting concepts and theories as hydrations to be fed, because they can also
be more powerful if used as abstraction bridging and routing for relevant chunks from other documents and / or chunks.
Essentially I don't know how to design this where they can be used to find real document chunks relevant to my query,
unless they are used as subqueries for sparse and dense?"

**Rule (consistent with FINAL's law, l.34-43: routing-inferred artifacts are never factual evidence).**
- A concept or theory is a ROUTER. It finds real chunks, and the real chunks are the evidence.
- Its text reaches the synthesizer only as a labelled derived principle bound to a real chunk already in the evidence
  (ELITE §6 DERIVED `[A#]` → `[S#]`), capped.
- It is never loaded into the prompt as bulk context: cinema has about 18 concept / theory items per document.

**Design sketch (a PROPOSAL for the consolidated document-RAG plan; owner to confirm).** The subquery / probe is the
mechanism that fetches real chunks, so the answer to the owner's question is yes. Four things around it make it work:
1. **Select a few items per turn, not all 1,209.** Search q0 against the profile's `concepts` / `theories` (and `seealso`)
   multivectors: one corpus-filtered MaxSim query. These multivectors exist today and nothing queries them (§8.1).
   - Score each item of the top documents against q0 locally, and keep the top k: HYBRID about 2–3, WILDCARD about 5–8.
   - Each item keeps (doc, field, text, vector, hop1 = item ↔ q0).
   - The item vectors are already stored, so a probe needs no embedder call.
2. **Route each selected item through three doors, all ending at real children:**
   - *global door*: the item vector searches the child index across ALL documents (dense), plus sparse over the item's
     specialist terms when it has any. This is the cross-document abstraction bridge; lane G does the same today for SEEALSO
     atom text;
   - *home door*: the item vector searches its own document's parent maps → parents → children (FINAL §42: atom → MAP →
     child);
   - *neighbour door* (GRAPH / WILDCARD): the item vector searches OTHER documents' concept / theory items → documents that
     share the abstraction → their parent maps → children. This can also be precomputed offline, with no LLM, as a
     concept-neighbour edge list, which becomes the GRAPH hop table next to SEEALSO.
3. **Judge conditionally, not against q0 alone.** A chunk that arrived through an item scores chunk ↔ item (hop2,
   cross-encoder with the item text as the query) × item ↔ q0 (hop1). That is ELITE's WildcardValue without the novelty
   term.
   - A q0-groundedness floor still applies, so tangents die.
   - Roles: DIRECT (chunk ↔ q0 strong); COMPLEMENTARY (reached through the item and q0-grounded); DERIVED (WILDCARD, tighter
     floor).
   - The probes carry their own lineage (§6 fix 1), so LQF-V2 preserves their local winners.
4. **Feed the same selected items to the bridge compiler** as its grounded concept set (§6 fix 2). Its 1–3 natural-language
   bridges take the WLK2C conditional pass that already exists.

**Evidence the pattern works** (all from this audit or earlier findings):
- WLK2A's bridge-primary test: judging chunks against a good bridge seated the expert material, wc01 0 → 10.
- Lane G, which probes children with atom text: half of the evidence rows it seats come from no other lane, even under
  q0's judge.
- WILDCARD's latent frontier, the same shape with latent abstraction vectors: 3 verified bridges on each of 4 real turns.

**Cost to control.**
- Each selected item costs a child search, a map search and extra judge pairs.
- Live compile is already about 12 s and retrieval about 19 s (§5). k stays small in HYBRID, and the per-probe timings
  (§6 fix 6) land first.

## 12. Owner intent: grounded learning value — and where the path context is lost (same day)

**Owner, 2026-09-23 (verbatim, shared from another conversation):** "I want a RAG pipeline that taps into latent or subdued
chunks, since a lot of my corpus knowledge is documents I'm not well versed on, so I may not know how to query properly. I'm
using it to improve my knowledge."

**The objective this implies: rank for grounded learning value, not literal query satisfaction.**
- The question is the starting point of a learning need, not a complete specification.
- A chunk can earn its place in five ways, always with source support: it answers directly, supplies a prerequisite, explains
  a mechanism, corrects a premise, or offers a transfer (with its limits).
- Novelty alone earns nothing.

**Policy input the owner shared.** These are recommendations from that conversation; the owner has not decided yet.
1. Separate "worth following" (a bridge's ability to retrieve evidence) from "worth including" (a chunk's supported
   contribution). No answer-worthiness filter runs before a bridge has retrieved its targets.
2. Select a bridge for a specific need: "what missing part of this question could following this bridge resolve?" Topical
   relatedness is not enough, and matching a subquery is not enough if the subquery has drifted.
3. Judge evidence with its path attached: question → subquery → bridge → source chunk. The judge asks:
   - does the source support the relationship the path depends on;
   - does that help the learning need;
   - does it add something beyond the evidence already selected?
4. Select by contribution, with no guaranteed seats. A bridge stays in the context only when it is needed to explain the
   connection. The answer shows the connection and labels analogies.
5. Rejected there:
   - fixed bridge quotas;
   - automatic boosts for abstract chunks;
   - unconditional protection of subquery winners;
   - multiplied hop scores as the verdict;
   - a universal standalone query-similarity floor;
   - guaranteed direct-first ordering;
   - novelty boosts.

**Where the path context is lost today** (READ, code at `7eb767d`). That conversation left this open; the code answers it:

| Stage | What the judge receives | Anchor |
|---|---|---|
| Retrieval, lanes D–I | the chunk is tagged with q0's id; the probe that found it is forgotten | `candidate_engine.py:814–919` |
| Bridge generation | atom-kind names and doc ids instead of concept text | `bridge_integration.py:46` |
| Main judge (every candidate) | (q0, the isolated chunk): one cross-encoder call | `candidate_engine.py:1447` |
| Bridge pass (WLK2C; bridge subqueries only) | three separate pairwise scores, combined by floors and then seated by caps with q0-primary non-displacement (see below) | `latent_selection.py:65–96`, `latent_eligibility.py:142`, `latent_portfolio.py:47` |
| Synthesis | role, latent-seat and lineage labels are dropped; the model never sees why a chunk is there | `ui.py:3519` |

The three bridge-pass scores are q0↔chunk (reused), q0↔bridge and bridge↔chunk. No judge sees question + bridge + chunk
together, and none asks whether the source supports the relationship.

**What this changes in this report's recommendations:**
- **Withdrawn as the admission rule:** §11 step 3 (the two-hop product with a q0-groundedness floor as the verdict) and the
  seat budgets proposed in chat. Hop scores stay, as "worth following" signals.
- **§6 fix 1 splits in two:**
  - carry the full path end to end (keep);
  - a path-aware admission judge (new; a design decision).
- **Laws that conflict with the objective** (owner decisions):
  - FINAL "cross-encoder = final judge" (l.39);
  - FINAL §47 "LATENT may never substitute for DIRECT";
  - WLK2C's q0-primary non-displacement;
  - ELITE §6 rule 1 (lead with DIRECT; never fill with `[A#]`) and the WILDCARD novelty term.

  What survives from them: an unsupported connection never enters, and the answer says when a direct answer is missing.
- **Unchanged:**
  - profile metadata routes and is never evidence;
  - §6 fixes 2, 3 and 6;
  - fix 7 becomes "make the connection visible": the concept, why it matters, the supporting source, and analogy labels.

**Open design decision for the plan: how the path-aware admission judge works.**
- (A) One batched LLM judge over a shortlist of full paths, returning support, contribution type and adds-beyond.
- (B) The cross-encoder with a composed path query. Cheap, but it measures relevance only.
- (C) Two stages: cross-encoder signals build the shortlist ("worth following"), then one batched LLM judge admits ("worth
  including").
- (D) Hand the paths to the synthesizer and let it choose and label.

Recommendation: C. Acceptance fixtures:
- a useful bridge that is dropped today (a WLK-10 wc01-class case);
- a vague bridge that must fail (a lift `A1` term, or a merely topical bridge);
- direct evidence that stays eligible.

Plus the frozen baselines and the owner's three metrics.

## 13. Execution design input the owner shared, mapped to today's code (same day; not yet decided)

**The principle the owner shared** (from the same outside conversation): keep dependent waiting small.
- Precompute relationships at index time.
- Have the EXISTING compiler plan the independent probes together (learning need, probes, and the relationship each probe
  investigates), instead of adding model calls per stage.
- Start the original-question search while compilation runs.
- Search concurrently, merge duplicates while keeping their paths, and batch the conditional judging (question + bridge
  relationship + source text).
- Expand a second round only for an identified evidence gap.
- Do not prune against q0 before conditional judging sees the candidates.
- Verify that a reranker given bridge text actually judges conditional relevance.
- Measure before promising a response time: a timing trace of one slow turn, showing which operations wait on others.

| Principle | Today (READ / EXECUTED) | Gap |
|---|---|---|
| Relationships precomputed at index time | concept / theory / seealso vectors stored per document (profile multivectors); document → parents via pMAP | no concept → parent / chunk links; no concept-neighbour table |
| One compiler call plans all probes | the compiler emits intent + USER / PROFILE / BRIDGE subqueries (1.6–3.2 s); the bridge compiler is a SECOND sequential model call (1.5–2.6 s) and gets kind names | fold bridge generation into the one planning call, fed the selected concept items |
| q0 search starts during compilation | the phase marks run in sequence (compile → retrieve); whether any lane is prestarted during compile is not visible in receipts | measure it with the timing trace |
| Concurrent search | lanes D–I run one after another outside `lane_deadline_s` (feasibility report §9) | run them concurrently under the deadline |
| Batched conditional judging | one q0 judge call + the WLK2C pass (1 + #bridges calls), pairwise only (§12) | one batched path-aware admission judge (§12 option C) |
| No pruning against q0 first | the fusion cap and judged prefix run before any conditional judgment; lanes D–I compete inside q0's preservation pool (§9) | per-probe lineage + local winners carried to admission (§6 fix 1) |
| Expand only for gaps | single pass today, no second round | keep; add a gap-triggered round only with a named missing need |

**First measurements the plan needs** (both $0, before any design is finalized):
1. A timing trace of one slow turn with per-step, wait-on-what timings: compiler, Scout, bridge compiler, each lane, fusion,
   judge, WLK2C pass, assembly, synthesis.
2. A trace of one dropped chunk from its bridge / probe through final selection, showing what question and context each
   judge received (one useful bridge dropped today, one vague bridge that must fail).

## 14. Proposed compiler contract: assessment and incorporation (same day)

**Input.** The owner shared a compiler specification written in another tool: "RAG compiler for grounded discovery". It is
admitted byte-identical as a proposal input at `docs/document-rag/inputs/2026-09-23-rag-compiler-contract.md` (sha256
`ff71a2bf…`); its own status line reads "proposed design". What it asks for:
- the compiler emits search hypotheses and evidence requirements, never verdicts;
- every exploratory request completes "Investigate X because it could help the user understand Y; look for Z";
- four inquiry dimensions: precision, depth, cross-domain connection, synthesis across documents;
- a ranking contract of three questions: does the source support the relationship; does that advance the learning
  objective; what does it add?
- a latency contract: concurrent independent work, batched scoring, no per-route model calls, expansion only for named gaps;
- an acceptance table and an implementation boundary: map to existing owners, implement demonstrated gaps only.

**Assessment: adopt, adapted.**
- It matches every conclusion of §9–§13.
- It supplies the half that the path-aware judge (§12) needs: the reason each probe exists, and what evidence would
  confirm it.
- About half of its schema already exists (EXECUTED: 40 recent plans, 223 queries; READ: `chat_plan.py:119-175`):

| Spec field | Today | Gap |
|---|---|---|
| `original_query` | `ChatPlan.original_request` | — |
| `learning_need` | `ChatPlan.retrieval_goal` exists but is **never filled** (0 / 40) | populate it |
| `constraints` | `user_constraints` + `explicit_constraints` (CONSTRAINT-AWARE-RETRIEVAL-V1) | split explicit from inferred |
| `inquiry_requirements` | `must_answer` (39 / 40) | add the four dimensions |
| `request_id`, `origin` | `CompiledQuery.id`, `origin` (USER / PROFILE / BRIDGE / CORPUS_EXPLORE) | mark model hypotheses distinctly |
| `query_or_reference` | `query` text; `inspired_by_profile` doc ids | reference profile ITEMS (concept / theory items), not only documents |
| `expected_contribution` | `role` / `reason` are generic (e.g. "bridge/complementary <- doc_…"). `target` is documented as the information need, but bridges store a **doc id** there, and `profile_surface` stores the atom kind | new specific field; fix the `target` misuse |
| `evidence_requirement` | — | new |
| `synthesis_targets` | `response_type` / `task_type` (coarse) | new |
| `depends_on` | — | record it; execute later |
| `operation` | lanes chosen by mode × intent policy, not per request | not needed in v1 |

Downstream, `retrieval_lineage` / `subquery_provenance` already carry lineage for subqueries and bridges. The enrichment lanes
and the judge do not (§12).

**Adaptations (my recommendation):**
1. Make it Part B of the ONE document-RAG plan of record, not a separate design. §10 showed the cost of four unjoined plans.
2. Extend `ChatPlan` / `CompiledQuery`: populate `retrieval_goal`; add the expected contribution, evidence requirement,
   inquiry dimensions and synthesis targets; stop storing doc ids in `target`.
3. Fold the bridge compiler into the one planning call, fed the selected profile items (concept / theory / seealso text + item
   ids, §11 step 1). That fixes defect 2 and saves one sequential model call (1.5–2.6 s).
4. v1 executes independent requests only. `depends_on` is recorded; at most one gap-triggered round comes later.
5. Keep the new fields compact, and measure compile time before and after. The compile phase is already ≈ 12 s for
   owner-style turns (§5).
6. **Protect compiler reliability.** Over 7 days (1,490 plans), 10% came from a backup model lane and 5% were deterministic
   fallbacks. Missing new fields must degrade to today's behaviour, and the fallback rate must be measured.
7. The three ranking questions ARE the path-aware admission judge (§12, option C). The spec rightly demands proof: A/B a
   cross-encoder with a composed path query against one batched LLM judge on the acceptance fixtures.
8. Its rule that general-sounding questions in the corpus-learning workflow must not skip retrieval would reverse owner
   backlog B20. Today 8.4% of turns skip retrieval. This is an owner decision; explicit "don't search" is still respected.
9. **Acceptance cases:**
   - the spec's table;
   - WLK-10, which was built for latent knowledge a general model would not surface;
   - a handful of owner-labelled questions (what the owner would want to learn);
   - the §12 fixtures.

**Risks:**
- Latency: a larger compiler output plus one judge call. Owner-style turns already take 63–83 s end to end (before the
  thinking fix).
- JSON reliability of a richer schema.
- The judge being anchored by confident but wrong "expected contributions". They are hypotheses; the judge verifies against
  source text.
- "Learning value" is judged partly subjectively, so owner-labelled fixtures are required.
