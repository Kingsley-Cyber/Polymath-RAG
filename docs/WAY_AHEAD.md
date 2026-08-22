# POLYMATH — SITUATIONAL SUMMARY & WAY AHEAD

State as of 2026-08-22, branch `architecture/evidence-first-v5`,
HEAD `9c8d1c2`, 692 tests passing, fleet 14/14 alive.

---

## 1. ONE-PARAGRAPH SITUATION

The evidence layer is finished and trustworthy. The knowledge layer is
not, and now we know exactly why and by how much. Ingestion, evidence
durability, determinism, crash recovery, isolation and text retrieval
are production-grade and measured. The canonical graph is not: ~29% of
projected edges were wrong before admission gating, and the deterministic
admission boundary built to fix that plateaus at ~60% supported / ~29%
wrong — short of the 90/5 bar. Separately, one operational defect
(projection lease starvation) currently blocks the 25-book corpus from
becoming queryable at all.

---

## 2. WHAT IS SOLID (do not re-litigate)

| capability | evidence |
|---|---|
| Evidence-first ledger (T0) | 174,650 raw proposals, 197,168 span hypotheses, append-only; rescue destruction abolished |
| Deterministic replay | settlement replays exactly from ledger; sealed sets replay DETERMINISTIC |
| Crash recovery | GLiNER SIGKILL mid-run, 3-fault storm, full reboot — all auto-recovered, zero evidence lost |
| Ingest throughput | 709s → 315s per book (2.25×), now provider-bound (77% GLiNER); ceiling quantified at ~1.25× more |
| Text retrieval | FAST/HYBRID verified working and invariant across all this work |
| Corpus isolation | typed refusals, proven in earlier phases |
| Sealed qualification | smq1, smq2-books, smq3-biomed; hedged biomedical prose produced ZERO causal edges |
| Runbooks | RUNBOOK, INGEST, SUPERVISION, RECONSTRUCTION — exercised for real during the incident |

**Scale proven:** 25 books, 238 MB source, 146k mentions, 2.5 GB
Postgres, ~10 books/hour through extract on one GPU.

---

## 3. THE TWO LATEST IMPLEMENTATIONS

### 3.1 POLYMATH-FACT-ADMISSION-V1 (`3877695`, matured in `9c8d1c2`)

A deterministic gate chain between L4 RelationCandidate and L5
CanonicalFact. Eight ordered fail-closed gates:

| gate | what it enforces | biggest catch |
|---|---|---|
| F1 PROVENANCE | doc/chunk/offsets/trigger/endpoints present | 50 |
| F2 REGION | body prose only; index/biblio/TOC/caption/heading/code refuse | 160 |
| F3 ENDPOINTS | durable + graph-eligible + not pronominal (POS, not a stoplist) | 115 |
| F4 ASSERTION | scope flags + clause-local negation, modality, irrealis, contrast | 128 |
| F5 PREDICATE | declared triggers; inherited ones need PropBank/FrameNet sense agreement | 156 |
| F6 SIGNATURE | (settled subject class, predicate, settled object class) | 75 |
| F7 DIRECTION | orientation **witnessed by grammar**; flips only when licensed | 190 |
| F8 SUPPORT | endpoints must occupy **argument positions** of the trigger's clause | 737 |

Supporting: `fact_admission_policy.yaml` (declarative region licensing,
orientation metadata, modal/contrastive classes, predicate strength),
`source_region.py` (REGION-POLICY-V1), shadow + explain harnesses,
54-case test suite.

**Key design property:** the whole ledger replays in **10.2 seconds**, so
a semantic iteration costs seconds instead of a re-ingestion. Eight
iterations were run in one night.

**Result: FAIL, not cut over.** 1,521 graph-pool facts → 92 admitted.
Every admitted fact classified against its evidence span (whole
population, not a sample): **60.4% supported / 11.0% questionable /
28.6% wrong** vs a 29/33/38 baseline.

### 3.2 KNOWLEDGE STRATIFICATION T0/T1/T2 (`9c8d1c2`, migration 0021)

Tiers are now persisted and queryable, not conceptual:

```
T0 EVIDENCE      observed, append-only, never a claim
T1 INFORMATION   interpreted/plausible — candidates, QUALIFY, REJECT,
                 facts admission did not pass
T2 KNOWLEDGE     asserted — every recorded decision PASSed
```

`fact_admission_decisions` + `knowledge_tier_facts` view. A fact reaches
T2 only if **every** decision recorded for it passed — one reject
demotes it. `shadow = TRUE` means the decision documents what admission
*would* do; cutover flips the flag rather than rewriting history.

Live: **T1 = 7,491 facts · T2 = 89 facts · 8,744 decisions, all shadow.**

---

## 4. WHAT THE MEASUREMENTS ACTUALLY TELL US

**Per-predicate precision is the most actionable number we have:**

| predicate | n | supported | wrong |
|---|---|---|---|
| part_of | 11 | 73% | 18% |
| uses | 37 | 70% | 19% |
| associated_with | 6 | 67% | 17% |
| founded | 5 | 60% | 40% |
| **similar_to** | 14 | **29%** | **71%** |
| created | 3 | 33% | 67% |

Two conclusions:
1. `similar_to` is **not assertable** — its triggers (`like`, `parallel`,
   `related to`) mean exemplification or concurrency as often as
   similarity.
2. Even the best predicate is at ~19% wrong, so **predicate filtering
   alone cannot reach 5%.**

**Confirmed second-order risks:**
- Identity fragmentation → recall loss: 47 of 75 signature rejections
  (63%) involve a fragmented surface.
- Over-constraint: `is_a` and `instance_of` fell to **zero** (127 facts,
  the taxonomy backbone) via the copula-complement rule. A predicate
  hitting exactly zero is a gate defect, not a semantic result.

**Rule-pack defect found (reported, not patched — pack is frozen):**
predicate verb lists were auto-expanded from VerbNet classes without
sense disambiguation. `obtain-13.5.2` inserted *make/source/receive* into
`acquired`; `use-105.1` inserted *work* into `uses`; a communication
class inserted *collaborate* into `similar_to`. This is the root of the
whole predicate-misfire class.

---

## 5. OPEN BLOCKERS, RANKED

### P0 — projection lease starvation (OPERATIONAL, blocks everything)
`release-books-v1`: extraction and settlement are **complete** (25/25),
but projections cannot finish — 24 tickets failed, retry budget burned.
Two stacked causes, both still in code:
1. health probes check liveness (`/manifest`), not inference readiness,
   so a wedged sidecar looks healthy indefinitely (16h outage observed);
2. the worker batch-claims up to 4 tickets but the lease keeper renews
   only the one being processed, so waiting tickets expire un-renewed and
   burn `attempt` without any real failure.

**Consequence: the 25-book corpus is not queryable.** No GRAPH or FAST
retrieval on it until this is fixed. This is the single highest-value
fix and it is pure engineering — no semantics involved.

### P1 — graph precision (SEMANTIC, blocks the "knowledge graph" claim)
28.6% wrong after gating. Ranked fixes, in order:
1. `COPULA-COMPLEMENT-BINDING-V2` — recover `is_a`/`instance_of` (127 facts)
2. demote `similar_to`-class predicates to T1 on the evidence above
3. participial-inversion ("used in X") and comparison-trigger gates
4. **entity-admission gate** — extent (`Pavlovian` → `pavlov`) and
   structural entities (`Figure 4-7` as a Document). No relation gate can
   substitute for this; it caps achievable precision.

### P2 — identity fragmentation (7.7% of surfaces)
Same-referent typing drift on the highest-value entities (Snort 6 ids,
Kafka 5). Costs recall, never precision. Fix is a settled-class
compatibility relation — **not** a fall back to raw provider type.

### P3 — throughput / capacity
Provider-bound; ≤1.25× remains without changing the frozen model.
300-book projection: ~30–42h wall, ~30 GB Postgres. Linear, no
super-linear term observed.

---

## 6. DECISION POINTS FOR PLANNING

**A. What is Polymath being sold as?**
Today the defensible label is: *a deterministic, fault-tolerant,
evidence-first ingestion and text-retrieval system with an experimental
graph layer.* That is genuinely strong and shippable. "Knowledge graph"
is not defensible yet. Choosing the narrower label unblocks release now;
choosing the broader one means committing to §5 P1 first.

**B. Fix operations or semantics first?**
P0 is days of engineering with a certain payoff (corpus becomes
queryable, unattended ingest becomes safe). P1 is open-ended semantic
work with a measured ceiling. Recommend P0 first regardless of A.

**C. Is 90/5 the right bar?**
It is the right bar *for asserted knowledge*. But the stratification now
makes a second option available: ship T1 as "plausible information"
surfaces (queryable, provenance-carrying, never asserted) and keep T2
tiny and clean. That may deliver more user value sooner than pushing T2
precision to 90%.

**D. Entity layer or relation layer?**
The evidence says the entity layer is now the binding constraint — extent
errors, structural entities, and typing drift all originate there and cap
what any relation gate can achieve. A post-freeze entity-admission gate is
probably higher leverage than more relation gates.

---

## 7. DO NOT TOUCH

Semantic freeze (GLiNER pin/threshold/labels, Harbor, canonicalization,
predicate compiler), frozen artifacts (`eval/i4/gold/`,
`eval/i4/verify_i4.py`, `eval/admission/artifacts/`), sealed sets, the
append-only ledger discipline. Authority hash is `fd68fc57…`; the three
fence pins assert it.

---

## 8. WHERE THINGS LIVE

| what | where |
|---|---|
| full forensic report (19 sections, verdict) | `FINAL_FORENSIC_REPORT.md` |
| fact-admission qualification (15 deliverables) | `eval/v5/FINDINGS_fact_admission_v1.md` |
| throughput findings | `eval/v5/FINDINGS_phaseB.md` |
| sealed qualifications | `eval/sealed/FINDINGS_*.md` |
| labelled precision evidence | `eval/v5/forensics/fact_admission_labels.json` |
| handoff + ranked actions | `CURRENT_STATE.md` |
| iteration loop (10s) | `eval/v5/fact_admission_shadow.py` |
| per-candidate diagnosis | `eval/v5/fact_admission_explain.py` |
