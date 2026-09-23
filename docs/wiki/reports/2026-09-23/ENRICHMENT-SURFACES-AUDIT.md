---
title: "ENRICHMENT-SURFACES-AUDIT — do the skeleton, pMAP, profile (SEEALSO, questions) and atoms reach the answers? (production 7eb767d)"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "AUDIT — read-only; no code, flag or data changed. Nine defects found, none fixed; the fixes are owner decisions (§6)."
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
| **Profile concepts / theories / seealso multivectors** (629 / 580 / 638 items) | nothing (`EXPLORATION_SURFACES`, `projection.py:28`, is read only by a test) | no | no | **produced, never read** |
| **Atoms** (609 for cinema: ≈ 1 per kind per doc) | Scout, lane G see-also fan-out, lift, WILDCARD, Corpus Explore | lane G: **175 rows, 87 alone, cited in 69 turns** (it fired in 93 turns) | only as coverage-line text or WILDCARD `[A#]` | used, but starved (defect 3) and rarely allowed (intent-gated) |
| **Aliases** (20 families, 71,934 aliases), pMAP identifiers / hooks, profile TERM / TOPIC, headings | resolution lift (lane F) only | **no: 0 of 7,806 candidates in 7 days** | no | **dead in practice** (defects 1–2) |
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

## 6. Recommended fixes (owner decisions; none executed)

Ranked by expected effect per unit of work:
1. **Resolution lift.** Either add a query-relevance term (embedding similarity of term to q0), drop identifier-shaped map ids
   and aliases unless the query names them, and keep every term's rows. Or turn the lane off until then:
   `resolution_lift="off"` in `INTENT_POLICY`, which saves about 1 s and 3 cross-encoder seats per turn for no loss.
   - This also decides how aliases reach retrieval at all.
   - For CODE-KNOWLEDGE-V1 identifiers ARE the vocabulary, so settle the lift design before slice C10.
2. **Re-project cinema's v3.2 profile items into the atom store.** This is a targeted projection from existing artifacts: no
   LLM, no re-ingest. It gives lane G, the Scout and Corpus Explore about ten times more SEEALSO / CONCEPT / THEORY items.
3. **Bridge labels.** Prefer atom text or profile ONE over the kind name or doc id (a precedence fix in
   `bridge_integration.py`), and fix the test that hides it.
4. **Profile concepts / theories / seealso multivectors.** Either search them (for example, add them to the RRF for
   RELATIONSHIP / EXPLORATORY) or stop producing them. After fix 2 they duplicate the atoms.
5. **Prompt.** Carry roles and latent seat labels past `ui.py:3519`, and drop PROFILE / BRIDGE probes from the coverage lines.
6. **Receipts.** Persist per-lane `lane_ms`, per-subquery timings and `latent_selection`; then measure the ~30 s retrieve.

Each fix is a separate admitted slice. Fixes 1, 3, 5 and 6 are orchestrator / shared code (stale-bundle fence, bounce).
Fix 2 is a data projection (check the corpus-scoped atom contract, 11.376).

## 7. Evidence and reruns

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
set -a; . ./.env; set +a
D=docs/wiki/experiments/enrichment-surfaces-2026-09-23
.venv/bin/python $D/receipt_audit.py $D/receipt_audit.json      # funnel per lane, enrichment-only share, lift ranks, latency
.venv/bin/python $D/surface_counts.py $D/surface_counts.json    # profile + atom stores per corpus
PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control \
  .venv/bin/python $D/replay_probe.py $D/replay_probe.json      # lift terms per intent + bridge-compiler labels (no LLM)
```

All three are read-only and cost nothing. `receipt_audit.py` reads a rolling 7-day window, so a rerun sees newer turns;
the committed JSON is the 2026-09-23 run.
