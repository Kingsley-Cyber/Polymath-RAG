---
title: "ENRICHMENT-SURFACES-AUDIT — do the skeleton, pMAP, profile (SEEALSO, questions) and atoms reach the answers? (production 7eb767d)"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "AUDIT — read-only; no code, flag or data changed. Nine defects found, none fixed; the fixes are owner decisions (§6). Same-day addendum (register 11.416): §8 field inventory, §9 owner intent + root cause (every enrichment lane is judged against q0), §6 revised to wire the fields in."
owner: "@king"
scope: "Every document-enrichment surface, from its store to the evidence the synthesizer sees and the citations in the answer, measured on 1,508 real UI chat turns (cinema) plus in-process replays and a static trace."
---

# ENRICHMENT-SURFACES-AUDIT

**Owner question, 2026-09-23:** audit the document extraction skeleton and the profile to see whether they are used and whether
they reach the answers, for example SEEALSO and questions.

**Method.** Evidence class per claim: EXECUTED (observed by running code or reading live stores) or READ (concluded from code).
- EXECUTED — the retrieval funnel of **1,508 real UI chat turns** (7 days to 2026-09-23, all modes, status ok). Every turn
  records in `query_receipts.meta.funnel` which lane brought each candidate chunk, the cross-encoder order, the rows the
  model saw (`selected`) and the rows the answer cited. Script: `receipt_audit.py`.
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

## 5. Latency signal found in the same receipts

The live retrieve phase roughly tripled after the `5df4536` deploy (subquery cap 3 → 10):

| | before (7 days) | after (all turns since the deploy) |
|---|---|---|
| HYBRID | p50 9.2 s (n 567) | 29.8 s and 32.2 s |
| GRAPH | p50 8.6 s (n 263) | 30.9 s |
| WILDCARD | p50 11.6 s (n 282) | 31.4 s |
| GNN | p50 15.8 s (n 13) | 14.7 s and 15.0 s |

GNN runs no subqueries and did not change. The warm in-process replay of the same plans measured 5.3–5.7 s (register 11.408).

INFERRED, n = 4: the extra subqueries and bridge seats cost far more live than in the warm replay. The receipt cannot
attribute the time (defect 9). Before changing the cap, persist per-lane and per-subquery timings and measure. The lanes D–I
deadline gap (feasibility report §9) is the other candidate.

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
   timings. Without them, fixes 1–5 and the ≈ 30 s live retrieve (§5) cannot be measured.
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
