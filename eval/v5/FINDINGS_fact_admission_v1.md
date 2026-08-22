# POLYMATH-FACT-ADMISSION-V1 + KNOWLEDGE STRATIFICATION

# VERDICT: **FAIL** — implemented, qualified, **not cut over**

The admission boundary works and moves precision substantially, but it
does not reach the mandated bar. Per the cutover rule, production
canonical facts and the Neo4j projection are **untouched**; every
decision is persisted with `shadow = TRUE`.

| required | measured | |
|---|---|---|
| SUPPORTED ≥ 90% | **60.4%** | FAIL |
| WRONG ≤ 5% | **28.6%** | FAIL |
| UNEXPLAINED = 0 | **0** | PASS |
| wrong direction = 0 | 2 of 91 | FAIL |
| pronoun/ineligible endpoints = 0 | **0** | PASS |
| index/bibliography/heading/caption relations = 0 | **0** | PASS |
| modal/hypothetical → unconditional = 0 | **0** | PASS |
| acquired/developed frame misfires = 0 | **0** | PASS |

---

## 1. Architecture actually implemented

```
L4 RelationCandidate
        │
        ▼   FactAdmissionV1  (shared/polymath_shared/fact_admission.py)
   F1 PROVENANCE     doc/chunk/offsets/trigger/endpoints present
   F2 REGION         body prose only; index/biblio/TOC/caption/heading/code refuse
   F3 ENDPOINTS      durable + graph-eligible + not pronominal (POS, not a stoplist)
   F4 ASSERTION      scope flags + clause-local negation, modality, irrealis, contrast
   F5 PREDICATE      declared triggers, then sense-agreeing inherited ones
   F6 SIGNATURE      (settled subject class, predicate, settled object class)
   F7 DIRECTION      orientation witnessed by grammar; flips only when licensed
   F8 SUPPORT        endpoints must occupy ARGUMENT POSITIONS of the trigger's clause
        │
        ▼
   PASS → Tier 2   QUALIFY(reason) → Tier 1   REJECT(reason) → Tier 1
```

Supporting components: `fact_admission_policy.yaml` (declarative region
licensing, orientation metadata, modal/contrastive classes, predicate
strength), `source_region.py` (REGION-POLICY-V1),
`eval/v5/fact_admission_shadow.py` (full-ledger replay),
`eval/v5/fact_admission_explain.py` (per-candidate diagnosis),
`tests/determinism/test_fact_admission.py` (54 cases).

## 2. Tier-0 / Tier-1 / Tier-2 mapping — persisted, not conceptual

Migration `0021_knowledge_tiers.sql` adds `fact_admission_decisions` and
the `knowledge_tier_facts` view.

| tier | contents | live count |
|---|---|---|
| **T0 EVIDENCE** | documents, chunks, sentence_slices, document_layout, raw_entity_proposals, evidence | 174,650 raw proposals; 8,391 evidence rows |
| **T1 INFORMATION** | mentions, span_hypotheses, relation_candidates, QUALIFY + REJECT decisions, facts admission did not pass | 34,501 candidates; **7,491 facts** |
| **T2 KNOWLEDGE** | facts where every recorded decision PASSed and endpoints are graph-eligible | **89 facts** (shadow) |

A fact reaches T2 only if *every* decision recorded for it passed — one
REJECT anywhere demotes it. Admission is fail-closed, so a fact is never
promoted by its most favourable evidence. `shadow = TRUE` means the
decision documents what admission *would* do; cutover flips the flag
rather than rewriting history.

## 3. Before / after fact count

| | before | after |
|---|---|---|
| L4 candidates examined | 8,744 | 8,744 |
| graph-pool facts (durable endpoints) | 1,521 | — |
| **admitted (T2 candidate)** | 1,521 | **92** (6.0%) |
| qualified (T1) | — | 90 rows |
| rejected (T1) | — | 1,624 rows |
| documents represented | 24 | 22 |

## 4/5. Precision — every admitted fact classified, not sampled

With only 92 admitted facts the whole population was judged against its
evidence span (labels committed at
`eval/v5/forensics/fact_admission_labels.json`).

| | baseline (pre-admission pool) | after |
|---|---|---|
| SUPPORTED | 29% | **60.4%** (55) |
| QUESTIONABLE | 33% | **11.0%** (10) |
| WRONG | 38% | **28.6%** (26) |

Wrong edges fell from 38% to 28.6% while volume fell 94%. Real, but far
from 5%.

### Per-predicate precision (the most actionable result)

| predicate | n | SUPPORTED | WRONG |
|---|---|---|---|
| uses | 37 | 70% | 19% |
| **similar_to** | 14 | **29%** | **71%** |
| part_of | 11 | 73% | 18% |
| associated_with | 6 | 67% | 17% |
| founded | 5 | 60% | 40% |
| created | 3 | 33% | 67% |
| developed | 3 | 67% | 33% |
| member_of | 3 | 33% | 0% |
| alias_of / located_in / acquired | 5 | 100% | 0% |

`similar_to` is not assertable at all: its "comparison" evidence class is
carried by polysemous triggers (`like`, `parallel`, `related to`) that
mean exemplification or concurrency as often as similarity. Even the
strongest predicate (`uses`) sits at 19% wrong — **predicate filtering
alone cannot reach the bar.**

## 6. Per-gate rejection census (graph pool)

| gate | reason | n |
|---|---|---|
| F8_SUPPORT | BINDING_ROLE | 679 |
| F5_PREDICATE | PRED_FRAME | 156 |
| F7_DIRECTION | DIRECTION_UNWITNESSED | 117 |
| F3_ENDPOINTS | ENDPOINT_SUBJ_PRONOMINAL | 115 |
| F2_REGION | REGION_CAPTION | 88 |
| F6_SIGNATURE | SIGNATURE | 75 |
| F2_REGION | REGION_INDEX | 72 |
| F7_DIRECTION | DIRECTION_UNLICENSED | 67 |
| F4_ASSERTION | MODALITY / CONTRASTIVE / IRREALIS / NEG_SCOPE | 51 / 43 / 34 / — |
| F1_PROVENANCE | MISSING_INPUT | 50 |
| F8_SUPPORT | BINDING_TRIGGER_IS_NAME | 34 |
| F8_SUPPORT | BINDING_COPULA_COMPLEMENT | 24 |
| F7_DIRECTION | DIRECTION_PASSIVE_AMBIGUOUS | 6 |

**Rejections by region:** BODY_PROSE 1,460 · CAPTION 88 · INDEX 72 ·
CODE 3 · BIBLIOGRAPHY 1. Structure suppression is a small share of the
total: the bulk of refusal is grammatical, not regional.

## 7. Predicate distribution before → after

uses 489→37 · part_of 263→11 · similar_to 251→14 · founded 113→5 ·
associated_with 95→6 · acquired 80→1 · stated_in 78→1 · instance_of
71→0 · developed 69→3 · created 66→3 · depends_on 59→1 · is_a 56→0 ·
located_in 32→2 · member_of 26→3.

## 8. Recall cost

94% of the graph pool refused. `is_a` and `instance_of` fall to **zero**
(127 facts) — the taxonomy backbone is gone. A predicate landing on
exactly zero is a gate-defect signature, not a semantic result; the
copula-complement rule (F8) is the cause. **COPULA-COMPLEMENT-BINDING-V2
is the first fix in any next iteration.**

## 9. Identity-fragmentation impact on valid facts (risk 1 — CONFIRMED)

- 1,240 fragmented durable surfaces (7.7%).
- **Of 75 SIGNATURE rejections, 47 (63%) involve a fragmented surface.**
  Fragmentation is measurably converting into relation-recall loss
  through the type-signature gate, exactly as predicted.
- 56 of 92 admitted facts (61%) still touch a fragmented surface, so
  fragmentation does not block admission by itself.

Mitigation is *not* to fall back to raw provider type (R1). It is a
settled-class compatibility relation — a future gate.

## 10. Remaining false-positive mechanisms

| mechanism | example | layer |
|---|---|---|
| polysemous comparison triggers | `similar_to(splunk, ip address)` — "extracts elements **like** IP addresses" | relation |
| predicate strengthening on weak verbs | `developed(nexatech, splunk)` — "NexaTech **implemented** Splunk" | relation |
| participial "used in X" inversion | `uses(bigtable data model, cassandra)` — "the model (**used in** Cassandra)" | relation |
| alternatives read as usage | `uses(static libraries, dlls)` — the text contrasts them | relation |
| author bylines | `created(rik farrow, gmail)` | relation/structure |
| single-entry reference lines below the bibliography threshold | `uses(alex shvartsman, …)` | region |
| **entity extent** | `employs(prc, pavlov)` from "Pavlovian" | **upstream** |
| **structural entities** | `located_in(figure 4-7, location)` | **upstream** |

Six of eight are relation-layer and reachable by further gates; two are
entity-layer and cap what any relation gate can achieve.

## 11. Runtime cost

**10.2 s** for the entire 8,744-candidate ledger (4,303 unique sentences
parsed, batched at 512), including persistence. Region classification is
cached per chunk; gates are pure functions over a prebuilt context. No
document is rescanned — the 289M-regex failure mode is not repeated.
FactAdmission is not a throughput risk; a full semantic iteration costs
seconds instead of a re-ingestion.

## 12. GRAPH retrieval impact

**None.** No cutover occurred, so the projected graph is byte-identical
to before this mission. The measured *potential* impact if cut over
today: graph edges would fall from ~1,436 to ~89, which would make GRAPH
mode far sparser — a further reason not to cut over at 28.6% wrong.
(Note: `release-books-v1` projections remain blocked by the separate
lease-starvation incident, §13 of the forensic report.)

## 13. FAST / HYBRID invariance

**Invariant, structurally and empirically.** No retrieval, embedding or
Qdrant code was touched. Verified live after the change: FAST on
`smq3-biomed-v1` returns its document with 8 evidence spans and
orchestrator health `ok`. T0 and T1 are untouched — 174,650 raw
proposals, 34,501 relation candidates, 8,391 evidence rows — so every
fact refused from T2 remains fully retrievable as text and queryable as
Tier-1 information.

## 14. Neo4j reconstruction proof

Not applicable this mission and deliberately so: **no projection was
rebuilt** because nothing was cut over. `facts` (8,414 rows) and
`projection_receipts` (13,652) are unchanged; the admission decisions
live in a separate additive table. The reconstruction path itself was
proven exact in V5 Phase 9 and is unaffected. Reconstruction becomes a
required gate only at cutover.

## 15. Recommended final release verdict

**NOT PRODUCTION READY as a knowledge graph — and do not cut over
FactAdmission V1 either.** Promoting 89 facts at 28.6% wrong would trade
a large untrustworthy graph for a tiny untrustworthy one.

What this mission did establish, and what should be kept:

1. **The stratification is right and is now real.** T0/T1/T2 are
   persisted and queryable; evidence survives every refusal; the graph
   can be made small without losing information.
2. **The admission boundary is the correct architecture** and is cheap
   enough (10 s) to iterate against the ledger indefinitely.
3. **A rule-pack defect was found**: predicate verb lists were expanded
   from VerbNet classes without sense disambiguation (`make`/`source`/
   `receive` → `acquired`, `work` → `uses`, `collaborate` →
   `similar_to`). Reported, not patched — the pack is frozen.
4. **The ceiling is now measured**: deterministic syntactic gates over
   the current entity layer plateau near 60–70% supported. Reaching 90%
   requires (a) COPULA-COMPLEMENT-BINDING-V2, (b) demoting
   `similar_to`-class predicates to Tier 1 on the evidence above,
   (c) participial-inversion and comparison-trigger gates, and
   critically (d) an **entity-admission gate** for extent and structural
   entities, which no relation gate can substitute for.

Ranked next actions: (a) → (d) above, then re-qualify. The harness,
policy, tier tables and labelled evidence set are all committed and
ready for that iteration.
