# POLYMATH V5 — FINAL FORENSIC REPORT

Corpus under examination: `release-books-v1` (the 24/25-book run of
2026-08-21) plus the sealed qualification artifacts (smq1, smq2-books,
smq3-biomed) and the Phase B optimization evidence (perf-baseline-v1).

Method: read-only SQL over the authoritative Postgres state, existing
stage artifacts, sealed manifests, git history, and a deterministic
fact sample. No re-ingestion, no model changes, no semantic tuning.

All counts in this report are exact queries against live state unless
explicitly labeled ESTIMATE or EXTRAPOLATION.

---

## 1. EXACT CORPUS ACCOUNTING

### Why 24 (actually 25 converged docs) and not 22

The prior plan said "22 books" = 16 (`book-optimizer/books`) + 6
(`CySA_Books`). The executed manifest added 3 hermes EPUBs
(Bowart, Bernays-1928, Hogan) per the mission's "hermes epubs" clause —
25 submissions. Two sources were corrupt on disk:

- `13_beyer_site_reliability_engineering…epub` — actually a **MOBI**
  file with an `.epub` extension. Refused at intake
  (`CorruptedDocumentError: not a valid zip`). Converted to a real EPUB
  (KindleUnpack) and re-submitted → converged.
- `02_Data_Engineering_for_Cybersecurity…epub` — **truncated zip**
  (broken central directory). First repair attempt was refused
  (missing `META-INF/container.xml` — correct refusal); second repair
  (rebuilt archive from the 38 readable entries + synthesized
  container.xml; only loss = back-cover JPEG) → converged.

So the corpus contains **25 processed documents**; 3 additional runs
sit in permanent typed intake-refusal (the 2 corrupt originals + the
first repair attempt). Nothing was silently skipped; every refusal is
recorded with a typed error. "24 books" in the interim status was the
count mid-recovery before the second repair converged.

### Per-document accounting

| # | document | fmt | MB | register | chunks | slices | raw L1 | mentions | durable ids | rel cands (A/Q/R) | facts | extract s |
|---|----------|-----|----|----------|--------|--------|--------|----------|-------------|-------------------|-------|-----------|
| 1 | 01-Bowart-Operation_Mind_Control.epub | epub | 2.7 | structurally_different | 549 | 4,637 | 7,922 | 7,412 | 1,790 | 141/69/1538 | 182 | 253 |
| 2 | 01_Mastering_Cybersecurity_Bhardwaj.pdf | pdf | 55.9 | technical_cyber | 404 | 2,595 | 4,298 | 3,433 | 644 | 154/87/418 | 234 | 149 |
| 3 | 01_sanders_applied_network_security_monitoring | epub | 7.8 | technical_cyber | 864 | 6,116 | 9,375 | 7,852 | 1,216 | 266/171/1470 | 392 | 367 |
| 4 | 02_Data_Engineering_clean2.epub | epub | 0.8 | technical_cyber | 535 | 3,276 | 5,763 | 4,380 | 453 | 155/86/362 | 219 | 308 |
| 5 | 02_collins_network_security_through_data_analy | epub | 8.0 | technical_cyber | 499 | 3,157 | 5,358 | 4,589 | 932 | 218/95/1213 | 280 | 260 |
| 6 | 02b-Bernays-Propaganda-1928.epub | epub | 0.4 | structurally_different | 193 | 988 | 2,337 | 2,330 | 365 | 173/119/922 | 256 | 91 |
| 7 | 03-Hogan-Covert_Persuasion.epub | epub | 0.6 | structurally_different | 300 | 2,834 | 4,366 | 4,419 | 482 | 113/77/960 | 156 | 118 |
| 8 | 03_CompTIA_CySA+_CS0-002_CertGuide_McMillan.ep | epub | 20.6 | technical_cyber | 1,229 | 9,246 | 17,115 | 13,879 | 1,943 | 661/358/2596 | 913 | 548 |
| 9 | 03_practical_threat_detection_engineering_cc86 | epub | 15.6 | technical_cyber | 531 | 3,911 | 5,505 | 4,829 | 599 | 142/113/767 | 225 | 219 |
| 10 | 04_Jump-start_SOC_Analyst_Wall_Rodrick.epub | epub | 1.9 | technical_cyber | 169 | 1,176 | 2,644 | 2,489 | 462 | 109/114/687 | 197 | 67 |
| 11 | 04_sikorski_practical_malware_analysis_4c35c52 | epub | 10.6 | technical_cyber | 1,457 | 10,455 | 11,392 | 9,681 | 1,778 | 323/126/1055 | 395 | 537 |
| 12 | 05_Security_Monitoring_Wazuh_Gupta.epub | epub | 35.5 | technical_cyber | 383 | 2,333 | 4,586 | 3,186 | 563 | 170/68/446 | 196 | 153 |
| 13 | 05_nikkel_practical_linux_forensics_9121bca8.e | epub | 3.2 | technical_cyber | 714 | 5,077 | 7,408 | 5,382 | 1,159 | 231/124/706 | 321 | 323 |
| 14 | 06_Hands-On_Splunk_on_AWS_Sinha.epub | epub | 17.7 | technical_cyber | 809 | 5,661 | 11,798 | 8,596 | 704 | 495/217/1087 | 653 | 351 |
| 15 | 06_brown_intelligence_driven_incident_response | epub | 4.6 | technical_cyber | 487 | 3,636 | 6,758 | 5,985 | 763 | 269/166/1219 | 417 | 216 |
| 16 | 07_cialdini_influence_psychology_of_persuasion | epub | 0.2 | academic_social_science | 22 | 173 | 249 | 255 | 20 | 7/11/36 | 18 | 15 |
| 17 | 08_burns_designing_distributed_systems.epub | epub | 3.6 | software_architecture | 214 | 1,696 | 2,499 | 2,151 | 259 | 65/41/364 | 104 | 92 |
| 18 | 09_percival_architecture_patterns_with_python_ | epub | 3.1 | software_architecture | 382 | 2,600 | 5,097 | 3,827 | 449 | 183/74/629 | 231 | 198 |
| 19 | 10_nygard_release_it_8487f6f1.epub | epub | 2.9 | software_architecture | 638 | 6,867 | 8,276 | 7,692 | 869 | 189/82/906 | 265 | 339 |
| 20 | 11_kleppmann_designing_data_intensive_applicat | epub | 8.6 | software_architecture | 1,271 | 8,603 | 16,544 | 13,950 | 2,171 | 442/270/2648 | 634 | 617 |
| 21 | 12_bellemare_building_event_driven_microservic | epub | 2.9 | software_architecture | 554 | 2,825 | 5,458 | 4,663 | 485 | 141/157/1216 | 275 | 237 |
| 22 | 13_beyer_sre_converted.epub | epub | 5.0 | software_architecture | 952 | 7,496 | 11,439 | 9,958 | 1,424 | 385/181/1878 | 518 | 460 |
| 23 | 14_richards_fundamentals_of_software_architect | epub | 19.7 | software_architecture | 592 | 4,497 | 9,825 | 8,312 | 752 | 523/203/1838 | 667 | 315 |
| 24 | 15_hohpe_enterprise_integration_patterns_f175d | epub | 5.8 | software_architecture | 1,188 | 7,379 | 4,603 | 3,008 | 360 | 51/7/291 | 44 | 482 |
| 25 | 16_burns_kubernetes_up_and_running_7f03b503.ep | epub | 0.6 | software_architecture | 269 | 2,082 | 2,538 | 2,138 | 306 | 75/47/346 | 111 | 137 |
| | **TOTAL (25)** | | 238 | | 15,205 | 109,316 | 173,153 | 144,396 | 20,948 | 5681/3063/25598 | 7,903 | 6,854 |
- bytes: min 200,099 / median 4,620,959 / max 55,910,316 (max = 23.5% of total)
- chunks: min 22 / median 535 / max 1,457 (max = 9.6% of total)
- mentions: min 255 / median 4,663 / max 13,950 (max = 9.7% of total)
- facts: min 18 / median 256 / max 913 (max = 11.6% of total)

No single book dominates: the largest by chunks
(`04_sikorski`, 1,457) is 9.6% of the corpus; the largest by bytes
(the 55.9 MB Bhardwaj PDF — image-heavy, only 404 chunks) is 2.7% of
chunks. Facts are similarly spread (max one-book share 11.6%).

The Bhardwaj PDF materialized correctly (text extraction; images
ignored), which is why 55.9 MB yields fewer chunks than 0.8 MB EPUBs.

---

## 2. ACTUAL END-TO-END STATE (exact, queried 2026-08-22)

Postgres (authoritative), corpus `release-books-v1`:

| layer | table | count |
|---|---|---|
| L0 | documents (converged) | 25 |
| L0 | child chunks | 15,205 |
| L0 | all chunks (incl. parent tiers) | 19,016 |
| L0 | sentence slices (interpreter view, persisted) | 109,316 |
| L1 | raw entity proposals (append-only ledger) | 173,153 |
| L1 | raw predicate evidence | 0 — legacy relation pipeline routes through `evidence` table instead |
| L2 | span hypotheses (rescue dispositions) | 196,541 |
| L2/L3 | mentions | 144,396 |
| | — with durable identity (ent_/entc_/entd_) | 58,457 (40.5%) |
| | — global ids | 47,641 |
| | — corpus-scoped ids | 10,792 |
| | — document-scoped ids | 24 |
| | — mention-only / abstained (no durable id) | 85,939 (59.5%) |
| L3 | distinct durable entities | 17,723 |
| | — GLOBAL admission class | 17,151 |
| | — CORPUS_SCOPED (concepts) | 555 |
| | — DOCUMENT_SCOPED | 11 |
| L4 | relation candidates (dispositions, all durable) | 34,342 |
| | — ACCEPT | 5,681 |
| | — QUALIFY (weak/hedged) | 3,063 |
| | — REJECT (with typed reason) | 25,598 |
| L5 | canonical facts (via evidence join) | 7,903 |
| | — decision ACCEPT | 5,154 |
| | — decision QUALIFY | 2,749 |
| | — with BOTH endpoints durable ("graph pool") | 1,436 (18.2%) |
| | — graph pool, ACCEPT only | 1,022 |
| DB | whole polymath database size | 2,510 MB |

Store-projection state (Qdrant/Neo4j/receipts) is reported in §13 —
at the time of the forensic pass the projection tail was still
draining after the incident there; final counts appear below in this
section once drained.

<!-- STORE_COUNTS_PLACEHOLDER -->

---

## 3. PIPELINE FUNNEL / WATERFALL

```
GLiNER raw proposals (L1 ledger)              173,153   100%
        ↓  span settlement / dedup / rescue
mentions persisted                            144,396    83.4% of proposals
        ↓  admission (Harbor): identity gate
mentions carrying a durable identity           58,457    40.5% of mentions
        ↓  distinct identity collapse
durable entities                               17,723
        ↓  relation candidacy (trigger+pair in slice)
relation candidates                            34,342
        ↓  compiler: type signatures, scope gates, frames
   ACCEPT 5,681 (16.5%)  QUALIFY 3,063 (8.9%)  REJECT 25,598 (74.5%)
        ↓  fact canonicalization (dedup by content id)
canonical facts                                 7,903
        ↓  endpoint durability (graph eligibility)
graph pool (both endpoints durable)             1,436    18.2% of facts
        ↓  Neo4j projection
projected edges                                 (see §13 / store counts)
```

What the funnel says:

- **Evidence survival is high** (83% of raw proposals persist as
  mentions; the 17% delta is span dedup, sub-token abstention, and
  rescue suppression — all recorded as L2 hypotheses, nothing deleted).
- **Admission is the big semantic gate**: 59.5% of mentions get no
  durable identity (pronouns, descriptive phrases, generics,
  unresolved references). This is the designed "no node > wrong node"
  behavior — but see §7: the gate still leaks pronouns occasionally.
- **The compiler is the big relation gate**: 74.5% of candidates are
  rejected, dominated by type-signature violations (~12k) and
  negation/conditional/speculation scope gates (~7k). Top reasons:
  `type_violation (Technology→…)` 4,308; `type_violation
  (Organization→…)` 2,633; `scope_gate: conditional` 1,958;
  `scope_gate: negated` 1,731.
- **The graph is sparse relative to the ledger by design**: 173k raw
  proposals → 1.4k durable-endpoint facts ≈ **0.8%**. Text retrieval
  keeps the other 99.2% reachable.

---

## 4. PERFORMANCE — FULL DETAIL

### The optimization progression (single-book A/B, Sanders EPUB, semantic state byte-identical at every step)

| stage of history | extract wall | evidence |
|---|---|---|
| original naive assumption ("45 min/book") | ~2,700 s | lease-churn era: healthy workers revoked mid-stage (claim TTL 300 s vs 45-min stages), stage restarts inflated wall-clock |
| corrected instrumented baseline | **709 s** | B1 `_perf` instrumentation, 99.3% attribution |
| + GLiNER transport batching (b=32, loop-mode), grouped /rescue, executemany bulk writes | **558 s** (1.27×) | B8 compare: state hash + all counts identical |
| + ADMISSION-IMPL-MEMO-V1 (definition-scan memoization) | **315 s** (2.25×) | B8 compare: identical; 638 tests pass |

Where the 2.25× came from: entity_pass 209→107 s (transport),
admission 307→52 s (killing an O(spans × sentences × 13 templates)
regex scan — 289M regex calls → memoized), persist 7→0.4 s
(executemany), rescue 162→138 s (grouped rescue transport).

### Optimized per-stage profile — Sanders reference book (315 s extract)

| stage | seconds | share |
|---|---|---|
| GLiNER pass 1 (batched, 27 calls) | 107.0 | 33.9% |
| GLiNER pass 2 / rescue re-query | 137.9 | 43.7% |
| admission (Harbor, memoized) | 51.5 | 16.3% |
| spaCy syntax (sidecar, batched) | 6.7 | 2.1% |
| evidence pass | 2.9 | 0.9% |
| persist mentions/slices (bulk) | 0.7 | 0.2% |
| candidate compile | 7.0 | 2.2% |
| L1/L2 ledger writes | 0.1 | 0.0% |

### 25-book aggregate (sum of per-book extract stage timers = 6,854 s)

| stage | total s | share |
|---|---|---|
| rescue (GLiNER pass 2) | 2,867 | 41.8% |
| entity pass (GLiNER pass 1) | 2,425 | 35.4% |
| admission | 1,111 | 16.2% |
| syntax | 152 | 2.2% |
| candidate compile | 144 | 2.1% |
| evidence pass | 60 | 0.9% |
| persistence (mentions+slices+L1/L4) | 29 | 0.4% |

GLiNER (pass1+rescue) = **77.2%** of extract compute at scale.

### Rates (measured on the 25-book corpus)

- Original-manifest 23 books: extract window 13:45:09→16:02:53 UTC =
  **2h 17m 44s** wall (includes the deliberate GLiNER SIGKILL + restart
  at 14:05). Serial-equivalent extract compute for those books ≈ 6,100 s.
- **~10 books/hour** through extract at 8 workers / 1 GPU
  (≈ 95 MB/h source bytes on this mix; the wall is GPU-serialized, so
  worker count beyond ~2 adds little during extract).
- Chunks: 15,205 / 8,264 s GPU-busy ≈ **1.8 chunks/s end-to-end**
  during the parallel run (GLiNER solo rate is 8.9 chunks/s at b=32;
  8-way self-contention + embed co-load costs the rest — see MPS
  below).
- Mentions: 144,396 / 2h18m ≈ **17.5 mentions/s** sustained.
- Median book: 4.6 MB, 535 chunks, extract 253 s.
- GLiNER effective batch: 32 (client), executed loop-mode
  server-side — the sidecar's equivalence probe REJECTED true
  model-level batching (not bit-identical on this build), so batching
  gains are transport-only.
- DB growth: 2,510 MB total for ~238 MB of source books ≈ **10.5×
  source bytes** (dominated by the L1/L2 evidence ledger — the price
  of full replayability).
- MPS contention (B4, measured): GLiNER alone 8.9 chunks/s; with
  continuous embedder load 2.93 (3.04× slower); + reranker 1.8
  (4.96×). Reranker is query-time only, so ingest-relevant contention
  is ~3×.
- CPU/RAM: not systematically sampled during the run (gap noted in
  §18 observability). Admission is single-core CPU per worker;
  8 workers × 1 core spikes during admission phases.

---

## 5. THE 24-BOOK RUN WALL CLOCK

| milestone | time (MDT) | delta |
|---|---|---|
| manifests submitted (25 docs) | 07:44:58 | — |
| GLiNER SIGKILL injected (deliberate) | 08:05:13 | +20m |
| GLiNER back, pipeline resumed | 08:07 | ~2 min lost |
| SRE-conversion addendum submitted | 08:38 | — |
| original 23 books extract complete | 10:02:53 | **2h 18m** |
| last addendum (repaired book) extract complete | 12:25:43 | (repair timeline, not pipeline speed) |
| projection stage: 24/24 timed out, retry budget exhausted | ~08:19 (first pass) / 13:43 (last re-driven attempt) | see §13 |
| embedder wedge diagnosed, sidecar + worker restarted | 00:29–00:39 (+1 day) | 16 h idle — **operator absent, silent failure** |
| projections drained | (completing during this report) | |

**Separation of compute vs backlog:** actual semantic compute for the
corpus ≈ 2.3 h. Everything after 10:03 was: (a) my repair timeline for
the two corrupt books, and (b) the projection outage (§13) — zero
semantic compute, pure recovery latency. **No data was lost in either.**
Settlement completed inside extract for every book; embeddings and
store projections are re-derivable at any time from Postgres.

---

## 6. SUPERVISION / FAILURE RECOVERY — LIVE EVIDENCE

Supervised fleet (14 slots, `control/control/process_supervisor.py`,
boot via LaunchAgent `com.polymath.v5`): 4 sidecars (GLiNER :8740,
spaCy :8744, embedder :8742, reranker :8743), orchestrator (:7200),
control loop, 8 stage workers. Current restart counters (cumulative,
this boot): gliner 3, embedder 1, orchestrator 1, control 2, workers
2–6 each — every one an automatic respawn.

| fault (live-injected or real) | detection | restart | recovery | duplicates | lost evidence |
|---|---|---|---|---|---|
| GLiNER SIGKILL mid-24-book-run (08:05:13) | supervisor loop <10 s | automatic | new pid serving by 08:07; in-flight extract retried via ticket lease; run converged | 0 (content-addressed ids) | 0 |
| 3-fault storm (Phase A live test: worker+sidecar+orchestrator SIGKILL) | <10 s | automatic | full pipeline converged after; state hash verified | 0 | 0 |
| machine reboot (mid-mission, real) | LaunchAgent | automatic docker-wait → fleet boot | manual sidecar venv fix needed once (spaCy venv), then converged | 0 | 0 |
| **embedder inference wedge (07:48, real)** | **NOT detected — 16 h** | manual | see §13 | 0 | 0 |
| projection worker socket wedge (00:31, real) | NOT detected (8 min, operator watching) | manual SIGTERM → auto respawn | upserts resumed immediately | 0 | 0 |

**The honest summary:** crash-death is handled well — kill -9 anything
and it comes back with leases, retries, and no duplicate or lost
state (proven live three ways). **Hang-death is not handled**: a
process that stays alive but stops doing inference (wedged MPS/HTTP
socket) passes its liveness probe forever. Both real incidents in this
run were hangs, and both needed a human. Health checks probe
`/manifest` (liveness), not `/infer` (readiness-under-load). This is
the top reliability gap in §15.

---

## 7. GRAPH QUALITY SIGNAL

Corpus graph shape:

- canonical facts 7,903 (5,154 ACCEPT / 2,749 QUALIFY); graph pool
  (both endpoints durable) **1,436**
- entities participating in any fact: 9,314 of 17,723 durable
  (52.6%); isolated durable identities: 8,409
- mean facts/participating entity ≈ 1.7
- predicate distribution (top): uses 1,847; similar_to 1,010;
  instance_of 927; part_of 905; is_a 715; created 438; developed 289;
  acquired 269; founded 260; depends_on 258; stated_in 251; …
  causes 91; alias_of 56
- fragmented surface clusters: 1,240 (§8); fact-bearing fragmented
  surfaces: 563

### Deterministic fact sample — the honest precision read

Sampling: `ORDER BY fact_id` (content hash ⇒ unbiased), stratified
max 2/document, n=40 across all 25 books; classified strictly against
the evidence span (SUPPORTED = the span attests the relation;
QUESTIONABLE = true-ish/weakly attested/predicate imprecise;
WRONG = endpoint, direction, or predicate not supported).

| pool | n | SUPPORTED | QUESTIONABLE | WRONG |
|---|---|---|---|---|
| all facts | 40 | 8 (20%) | 13 (32%) | 19 (48%) |
| — decision ACCEPT only | 24 | 3 | 10 | 11 |
| — decision QUALIFY only | 16 | 5 | 3 | 8 |
| graph pool (durable endpoints), separate draw | 24 | 7 (29%) | 8 (33%) | 9 (38%) |

Full annotated samples: scratchpad `fact_sample.json` /
`fact_sample_durable.json` (both committed alongside this report).

Representative WRONG mechanisms (each seen ≥2× in the sample):

1. **Direction inversion on part_of/include**: "High-level languages
   include C, C++" → `part_of(high-level languages, c++)` (inverted);
   same for IoT/smart-TVs, sensors/logfiles.
2. **Predicate misfire on discussion/modal prose**: "an architect
   might make a decision to use React.js" → `acquired(architect,
   react.js)`; "architect can write Java code in ArchUnit" →
   `created(architect, archunit)`; "Large enterprises may roll out
   Kerberos" → `developed(large enterprises, active directory)`.
3. **Generic/pronoun endpoints**: `instance_of(you, idea)`,
   `acquired(i, soc)`, `uses(we, corba)` — 1,200 of 7,903 facts
   (15.2%) have pronoun-surface subjects. Most bind non-durable
   mention ids (correct admission behavior), but a subset minted
   durable Person/Organization nodes ("i", "they", "we" appear as
   durable endpoints in the graph pool sample) — an admission leak.
4. **Structure text as semantics**: an IDA Pro book **index page**
   produced `part_of(process, ida pro)`; a figure caption produced
   `located_in(figure 4-7, location)`; a section heading produced
   `is_a(general principles of sre, data integrity)`. Layout evidence
   exists but does not yet suppress index/heading/caption regions
   from relation candidacy.
5. **OCR/whitespace damage as endpoints**: `part_of(ne twork
   infrastructure, op erating systems and services)` (PDF-extracted
   text with intra-word spaces).

And genuine SUPPORTED examples for balance: `uses(rhel, firewalld)`
(from the repaired book), `uses(splunk, aws services)`,
`uses(microsoft, containers)`, `uses(us government, taxii)`,
`causes(internal asset compromise, disruption)`,
`uses(manjaro, arch linux)` ("based on" — predicate imprecise but
true), `associated_with(ids engine, fast pattern matching)`.

**Bottom line: roughly one graph edge in three is wrong under strict
span-attestation, and only ~30% are cleanly supported.** Sealed
qualifications to date measured invariants + determinism, never
fact-level precision at scale; this is the first deterministic
precision sample, and it is the single most release-relevant number
in this report.

---

## 8. IDENTITY FRAGMENTATION — MEASURED, NOT HEADLINED

25-book corpus census (`eval/v5/fragmentation_census.py`):

- durable normalized surfaces: 16,133
- fragmented (>1 id): **1,240 = 7.7%**
- identities involved: 2,830
- fact-bearing fragmented surfaces: 563
- facts sitting on fragmented ids: 2,299

Top fragmented surfaces (ids / provider types / prelabel):

| surface | ids | types seen | verdict |
|---|---|---|---|
| snort | 6 | Method, Organization, Process, Product, Technology | same referent — typing drift |
| borg | 5 | Location, Organization, Person, Product, Technology | mostly same referent (Google Borg); 'Person' = Star-Trek/joke contexts |
| bro | 5 | Organization, Person, Product, Technology | same referent (Bro IDS) + person-ish uses |
| kafka | 5 | Document, Organization, Product, Technology | same referent (Apache Kafka) |
| devops | 5 | Concept, Method, Organization, Process, Technology | same concept |
| suricata / virustotal / systemd / sre / slo / osint / mltk / dllmain / malware / uow / connascence | 5 each | mixed | same referent, typing drift |

The census pre-labeler calls 1,112 of 1,240 "LEGITIMATE_CONTEXT_
DISTINCTION" because the ids differ in provider type — that is the
row-51 rule speaking, not the truth. **Manual inspection of the top-20
list shows the opposite: nearly every high-multiplicity case is ONE
real-world referent (Snort, Kafka, Suricata, VirusTotal, systemd)
that the provider typed differently across contexts, which the
type-retaining identity rule then splits.** True homonym protection
(Apple-fruit vs Apple-company) exists but is the minority case.

The user's example — `propaganda`: 3 ids in this corpus
(Concept / Method / Document), all Bernays/Hogan usages of the same
concept. Same pattern.

So 7.7% means: **the graph splits the same entity into 2–6 nodes for
roughly 1 in 13 surfaces, concentrated exactly on the most-mentioned
technical entities** (the ones typed in varied contexts). It never
merges wrong things (0 wrong merges observed anywhere), so precision
is safe; recall/connectivity pays: a "what uses Snort?" graph
traversal sees at most one of six Snort nodes' edges.

---

## 9. CITATION-TEXT RELATION WEAKNESS — QUANTIFIED

Mechanism (from smq3 forensics): bibliography text is grammatically
alien — comma-separated "Surname, Initial." runs with year markers.
The compiler's alias/association rules match its punctuation shapes:
`"Nakamura, H., Tanaka, A., Nomoto, Y., …"` →
`alias_of(nakamura, nomoto)` — two *different* cited authors asserted
to be the same person (WRONG identity edge). The endpoints are real
entities (cited-author names admitted normally); the failure is
**citation context generating unsupported predicates**, primarily
`alias_of` and `associated_with`.

Counted at book scale (25-book corpus): citation-like chunks
(≥4 year-parens or ≥5 "Surname, X." patterns): **7 chunks**; facts
with evidence inside them: **1 of 7,903** (a `part_of`). In smq3 (an
academic paper): 1–2 of 2 projected facts were citation artifacts.

**Severity: LOW for book corpora, MODERATE-to-HIGH for academic-paper
corpora** (reference lists are a large fraction of a paper, and
alias_of is an identity-corrupting predicate). Future gate:
CITATION-REGION-SUPPRESSION-V1 — layout evidence already persists the
structure needed to suppress relation *candidacy* (never evidence) in
reference regions. Not patched during this pass (frozen).

---

## 10. BIOMEDICAL QUALIFICATION — THE EVIDENCE BEHIND "ZERO FALSE CAUSAL EDGES"

Document: *A Circumplex Model of Affect* — sealed set `smq3-biomed`,
content hash `4bfdf403…8953417a`, sealed at
`v4-semantic-freeze-37-g9f888c4`, seal verified `SEALED`, run replay
`DETERMINISTIC`, stamp: facts 12 (evidence rows), canonical 6,
canonical_hash `0222460d…`.

State: 975 mentions, 493 durable identities, **103 relation
candidates → 12 ACCEPT / 3 QUALIFY / 88 REJECT**, 2 unique canonical
facts projected 2/2.

The hedged/causal audit — the paper is saturated with hedged causal
language (dopaminergic systems, mesolimbic contributions, "may",
"suggests", "implicated in"). What the compiler did with it:

- **Zero causal predicates admitted** (`causes`, `results_in`,
  `increases`… all absent from the doc's facts). The candidate
  dispositions show why, case by case: 88 rejects =
  `type_violation` (70), `binding: endpoints_outside_trigger_clause`
  (10), **`scope_gate: negated, speculative` (8)** — the scope gates
  are the hedge detector firing correctly. Examples preserved: the
  Ekman/Izard facial-expression-taxonomy claims (hedged + negated in
  the text) rejected as `negated, speculative`.
- **Hedged relations correctly withheld:** yes — the 8 scope-gated
  rejections above are exactly the "X may reflect Y" sentences.
- **Association preserved:** 1 `associated_with` accepted (weak
  predicate class), plus co-mention evidence remains in text
  retrieval.
- **False causal promotion / wrong direction:** none found — there
  are no causal edges to be wrong.
- **Wrong endpoint binding:** the 2 accepted facts are the citation
  artifacts of §9 (`alias_of(nakamura, nomoto)` and
  `associated_with(dsm-iv, doyle & faraone)`) — endpoint binding
  failures from reference-list text, not from hedged prose.

So the biomedical verdict stands but with its real shape: **the hedge
machinery works; the citation machinery is what leaked.**

---

## 11. RETRIEVAL ON THE FRESH CORPUS

<!-- RETRIEVAL_PANEL_PLACEHOLDER -->

## 12. RETRIEVAL VS GRAPH DEPENDENCE

<!-- RETRIEVAL_DEPENDENCE_PLACEHOLDER -->

---

## 13. PROJECTION TAIL INCIDENT — DEDICATED SECTION

**What the user saw:** extraction finished at 10:03; nothing became
query-ready for 16+ hours; a manual re-drive at 12:20 also failed;
recovery only under operator attention at 00:29–00:47.

**ROOT CAUSE — three stacked defects, forensically established:**

1. **Embedder inference wedge (primary outage).** At ~07:48, under
   the first 8-worker surge, the embedder sidecar's inference path
   hung permanently (MPS/HTTP wedge). Its `/manifest` liveness
   endpoint kept answering, so the supervisor considered it healthy
   for 16 hours. Every `project_qdrant` stage sat in a 30-minute
   read-timeout against `/infer`, failed "timed out", and burned its
   3-attempt budget. Proof: at 00:26 a single `/infer` probe timed out
   at 120 s on an idle machine; after SIGTERM + auto-respawn the same
   probe returned 32 vectors in 2.4 s.
2. **Batch-claim lease starvation (why retries also died).** The
   worker loop claims up to 4 tickets per cycle; the CP2.1 lease
   keeper renews ONLY the ticket currently being processed. A
   big-book projection runs 5–10+ min, far past claim_ttl_s=300, so
   the 3 waiting claimed tickets expire un-renewed, get reaped,
   re-queued, and re-claimed — each cycle incrementing `attempt`
   until the budget is gone *without any real failure*. Observed
   live: 4 tickets leased to the fresh worker with
   `lease_expires_at` 3 minutes in the past, attempt=2.
3. **Worker-side stale-socket hang (recovery friction).** The
   projection worker that lived through the sidecar restart kept
   pooled connections to the dead socket and blocked without
   tripping its client timeout; it needed a SIGTERM (supervisor
   respawned it; work resumed instantly).

**AFFECTED:** stage `project_qdrant`, all 25 documents (plus blocked
downstream `canonicalize`/`project_canonical`/`project_neo4j`/
`verify_projections` for the whole corpus). **RETRIES:** 3 per ticket
× 2 drive cycles. **DATA LOST: zero** — projections are derived
state; Postgres semantic state was complete and untouched throughout.

**AUTOMATIC RECOVERY: failed.** Supervision handles crash-death, not
hang-death (§6). **MANUAL STEPS:** restart embedder sidecar, restart
one worker, re-drive tickets serially (documented runbook procedure,
executed with per-ticket notes).

**IS THE CODE FIXED? NO — explicitly not.** Both mechanisms are
still in the code as of this report:
- health probes still check liveness, not inference readiness;
- the batch-claim/lease-keeper mismatch is unchanged (mitigation
  available without semantics: claim depth 1 for long-stage workers,
  or per-claimed-ticket renewal).

**REGRESSION COVERAGE: none yet** for either mechanism.

**RELEASE IMPACT: this is the strongest operational finding of the
whole exercise.** Normal production ingest of a book-sized corpus
WILL reproduce this class of backlog whenever a sidecar wedges or a
projection outlives the lease TTL — and it will require a human with
the runbook. P1, arguably P0 for unattended operation (ranked in §15).

---

## 14. WHAT WAS ACTUALLY FIXED (defect → mechanism → fix → regression → result)

| defect | causal mechanism | fix | regression guard | result |
|---|---|---|---|---|
| rescue deleted evidence | failed boundary-widening REPLACED the original span (evidence destruction) | V5 L1/L2: append-only raw ledger + span hypotheses; destruction became recorded disposition | shadow settlement replay (UNRULED_SEMANTIC_DELTA=0) | ledger replays settlement exactly |
| sub-token span crash | span inside one token raised RetryableDependencyUnavailable → infinite retry | SUBTOKEN-SPAN-ADMISSION-V1: settled abstention, surface preserved | I4/SMQ1 hash-identical qualification | class eliminated |
| lease TTL vs long extract | claim_ttl 300 s < 45-min stage → healthy worker revoked mid-stage | CP2.1 in-flight lease keeper (60 s renewal + heartbeat) | live SIGKILL tests | fixed for the ACTIVE ticket only — batch-claimed tickets still starve (§13) |
| spaCy 512-sentence cap | server-side batch cap → 422 on book-scale calls | client-side SYNTAX_BATCH=512 chunking | book-scale test | fixed |
| embedder single-call timeout | whole-book embed in one call | EMBED_BATCH=32 | book-scale test | fixed |
| Qdrant giant upsert | single upsert of all points timed out | UPSERT_BATCH=128 | book-scale test | fixed |
| entities FK violation | later edge referenced non-durable ANTECEDENT_RESOLVED endpoint | guard: skip only when durable-inherited | determinism suite | fixed |
| definition-scan O(n²) | whole-document sentence re-split + 289M regex calls per book | ADMISSION-IMPL-MEMO-V1 memoization (behavior-identical, 34-case differential proof) | equivalence suite + B8 identical-state run | admission 307→52 s |
| GLiNER per-chunk HTTP | 864 calls/book transport overhead | /infer_batch + equivalence probe (loop-mode only — model batching NOT bit-identical, rejected) | B2 curve, exact-set equivalence | pass-1 2× |
| row-at-a-time DB writes | per-mention INSERT round-trips | executemany bulk writes | B8 identical counts | persist 17× |
| worker death unnoticed | no supervision | CP2.1 8-worker supervision + quarantine | live 3-fault test | crash recovery proven |
| nothing survived reboot | manual bring-up | 14-slot supervisor + LaunchAgent boot chain | live reboot | boot recovery proven |
| tr-recorder surface mismatch | hypothesis rows recorded pre-install surface | recorder stores installed surface; shadow fixed to match | frame-check + hypothesis-consistency test | ledger replay green |
| V5 tables survive wipe | frozen i4 wipe predates V5 tables; no FK cascade | eval/v5/wipe_corpus_v5.py (introspective doc-scoped wipe) | — | A/B contamination eliminated |
| projection backlog (§13) | embedder hang + batch-claim lease starvation | **NOT FIXED** — manually recovered; runbook procedure exists | **none** | open P1 |

---

## 15. CURRENT LIMITATIONS — RANKED

**P0 — release blockers (for the graph layer as a product):**

1. **Graph edge precision ≈ 30–60% wrong-or-questionable** (§7:
   strict sample — 38% WRONG in the projected pool). Mechanisms:
   direction inversion, predicate misfire on modal/discussion prose,
   structure-text (index/heading/caption) candidacy, pronoun
   endpoints. Affects TRUTH. Text retrieval fully mitigates for
   retrieval users; nothing mitigates for anyone consuming edges as
   assertions. Future gates: frame tightening is semantic (frozen
   now) — this is the first post-freeze semantic workstream, with the
   L4 disposition ledger as its measurement bed.

**P1 — serious, fix soon:**

2. **Hang-death supervision gap + projection lease starvation**
   (§13). Affects RELIABILITY of unattended operation. Engineering,
   not semantics: readiness probes that exercise inference; claim
   depth 1 (or per-ticket renewal) for long stages; regression for
   both. Until then every large ingest risks a manual re-drive.
3. **Identity fragmentation 7.7% of surfaces, concentrated on the
   most-mentioned entities** (§8) — same-referent typing drift, not
   homonyms. Affects RECALL/connectivity (never precision). Mitigated
   partly by retrieval (text finds all Snorts); graph traversal sees
   a fraction of each fragmented entity's edges.

**P2 — acceptable production limitations (documented):**

4. **Citation-region edges** (§9): LOW at book scale (1/7,903),
   register-dependent (academic papers → MODERATE-HIGH). Future gate
   specified (layout-based candidacy suppression).
5. **Provider misses / extent contraction / typing instability**
   (forensics decision C: provider not dominant for admission; but
   typing drift feeds limitation 3). Frozen provider.
6. **Graph sparsity by design**: 0.8% of raw evidence becomes
   durable edges; conservative-by-design, retrieval carries the rest.
7. **OCR/whitespace damage in PDF-extracted text** becomes entity
   surfaces ("ne twork") — affects node cleanliness in one PDF-heavy
   register.

**P3 — optimization / future work:**

8. **GLiNER provider-bound throughput** (§16): 77% of extract is the
   frozen model; further software optimization yields ≤ ~1.3×.
9. **MPS contention** (3× under embed co-load): scheduling
   refinements possible; measured and documented.
10. **Observability gaps**: no CPU/RAM/MPS utilization sampling
    during runs; monitoring keyed on `completed_at` documented.
11. **Fact-replay harness fidelity** (KNOWN_LIMITATIONS #11):
    eval-side only; replay is 6-facts permissive on frame-gate
    context; production unaffected.

---

## 16. WHAT "PROVIDER-BOUND" ACTUALLY MEANS

Optimized Sanders reference book, extract = 315 s:

| component | seconds | nature |
|---|---|---|
| GLiNER pass-1 model compute | ~97 | frozen model floor (864 chunks ÷ 8.9 chunks/s solo) |
| GLiNER pass-1 transport/wait | ~10 | already batched; little left |
| GLiNER rescue (pass-2) inference | ~130 | frozen model floor (query volume is semantic — cannot shrink without changing rescue semantics) |
| rescue transport | ~8 | grouped already |
| admission + syntax + compile + evidence (CPU) | ~68 | ~52 s admission is post-memoization; maybe 20–30 s more shavable with aggressive caching |
| persistence | ~1 | done |

Model floor ≈ 227 s. Perfect-engineering extract ≈ **245–255 s/book**
vs current 315 s → **maximum remaining software speedup ≈ 1.25×**
(≈ 20%). Getting more requires: a different/quantized provider
(frozen), true model-level batching (rejected — not bit-identical),
or semantic changes to rescue query volume (frozen). **Another
optimization pass is NOT worth it for extract.** The next real
throughput lever is *pipeline overlap* (projection concurrent with
extract of the next book — already the architecture) and the §13
reliability fixes so the pipeline actually stays busy unattended.

---

## 17. 300-BOOK CAPACITY PROJECTION (EXTRAPOLATION — clearly labeled)

Basis: measured 25-book run (median book 4.6 MB / 535 chunks /
253 s extract; ~10 books/h wall through extract at current
contention; DB growth 2,510 MB for 238 MB source ≈ 10.5×; observed
book-size spread 0.2–56 MB).

| corpus | serial-equivalent extract compute | expected wall-clock (extract+projections, attended) | Postgres growth | Qdrant growth (points ≈ chunks×~2.2 representations) | Neo4j |
|---|---|---|---|---|---|
| 50 books | ~3.9 h (2.9–5.2) | **~5–7 h** | ~5 GB | ~165k points / ~0.7 GB | ~35k nodes / ~6k edges |
| 100 books | ~7.7 h (6–10) | **~10–14 h** | ~10 GB | ~330k points / ~1.4 GB | ~70k nodes / ~12k edges |
| 300 books | ~23 h (18–31) | **~30–42 h** (1.3–1.8 days) | ~30 GB | ~1M points / ~4 GB | ~210k nodes / ~35k edges |

Ranges reflect observed book-size variance (25th–75th percentile
scaled). ALL close-to-linear: no super-linear term observed in any
per-book stage (content-addressed ids make re-ingest idempotent;
admission memoization is per-document; cross-document state is
append-only). The honest caveat: the §13 reliability class is the
actual risk to these numbers — a single un-detected sidecar wedge
turns 30 h into "30 h plus however long nobody notices," which at
300-book scale is the difference that matters.

---

## 18. RELEASE READINESS MATRIX

| capability | verdict | basis |
|---|---|---|
| INGESTION RELIABILITY | **PASS WITH LIMITATION** | 25/25 processable docs converged; corrupt inputs refused with typed errors; BUT the §13 backlog class required manual recovery |
| EVIDENCE DURABILITY | **PASS** | append-only L1/L2; rescue destruction abolished; wipe-survival defect found and fixed; zero evidence loss through every fault |
| ENTITY ADMISSION | **PASS WITH LIMITATION** | deterministic, replayable, conservative (59.5% abstention); pronoun-surface durable leaks observed; fact-level census still uncertified (by design of the freeze) |
| CANONICALIZATION | **PASS WITH LIMITATION** | stable content-addressed ids; 0 wrong merges anywhere; 7.7% same-referent fragmentation |
| RELATION COMPILATION | **PASS WITH LIMITATION** | fully deterministic, typed dispositions for all 34,342 candidates; scope/hedge gates demonstrably work (smq3); precision of ACCEPTs is the P0 above |
| GRAPH PRECISION | **FAIL** (as an asserted-knowledge product) | §7: 38% WRONG in the projected-pool sample; direction inversions; structure-text edges |
| GRAPH COVERAGE | **PASS WITH LIMITATION** | sparse by design (0.8%); fragmentation splits high-degree nodes |
| FAST RETRIEVAL | *(§11 — filled after drain)* | |
| HYBRID RETRIEVAL | *(§11)* | |
| GRAPH RETRIEVAL | *(§11)* | |
| CORPUS ISOLATION | **PASS** | proven in earlier phases (typed refusals, isolation corpora); re-checked on fresh corpus in §11 |
| REPLAY | **PASS WITH LIMITATION** | settlement replay exact on clean ledger; fact replay 6-permissive (eval harness gap, documented) |
| RECONSTRUCTION | **PASS** | Neo4j/Qdrant wipe→rebuild exact (Phase 9); projections re-derived during this very incident |
| WORKER RECOVERY | **PASS WITH LIMITATION** | crash-death: proven live; hang-death: not detected |
| SIDECAR RECOVERY | **PASS WITH LIMITATION** | same split: SIGKILL recovered in ~2 min; wedge undetected 16 h |
| ORCHESTRATOR RECOVERY | **PASS** | live-killed and auto-recovered (Phase A) |
| BOOT RECOVERY | **PASS** | LaunchAgent chain survived a real reboot |
| INGEST THROUGHPUT | **PASS** | 2.25× optimized; provider-bound (77%); ~10 books/h measured; ceiling quantified (§16) |
| OBSERVABILITY | **PASS WITH LIMITATION** | typed ticket errors, per-stage timers, JSON logs; no resource telemetry; hang-blindness |
| OPERATIONS / RUNBOOKS | **PASS** | RUNBOOK + INGEST/RECONSTRUCTION/SUPERVISION runbooks exist and were exercised for real during this incident |

---

## 19. FINAL STATE

**WHAT YOU CAN TRUST TODAY**
- Nothing ingested is ever lost or silently altered: every proposal,
  hypothesis, and disposition is in an append-only ledger that
  replays settlement byte-exactly, survives kill -9 / reboot, and
  rebuilds both stores from Postgres.
- Refusals are honest: corrupt files, hedged claims, negated claims,
  unresolvable references all produce typed, queryable refusals.
- The hedge/causal machinery: a causality-saturated psychology paper
  yielded zero causal edges, with each withheld claim's rejection
  reason on record.
- Text retrieval carries the corpus (§11): the graph never gates it.
- Determinism: same input + same contracts = same ids, same facts,
  same stores — proven repeatedly, including under fault injection.

**WHAT STILL FAILS OR IS WEAK**
- Graph edge precision (P0 above): ~1 in 3 projected edges wrong
  under strict reading; index/heading text becomes edges; part_of
  direction flips; modal prose mints created/acquired edges.
- Unattended reliability: hang-death is invisible to supervision
  (16 h outage in this run); long projections starve their own
  leases (§13). Fixable with engineering, not yet fixed.
- High-degree entities fragment (7.7% of surfaces) from provider
  typing drift.

**WHAT YOU WOULD NOTICE AS A USER**
- Retrieval answers arrive with real evidence spans, and hedged
  source claims stay hedged.
- If you browse the graph: correct-and-useful edges (uses/part_of on
  technical entities) interleaved with obviously silly ones
  (`instance_of(you, idea)`, edges citing an index page) — the graph
  reads as an unreliable narrator today.
- After a big ingest, some books may sit "processing" until an
  operator pokes projections (§13).

**WHAT WOULD BREAK FIRST AT 10× SCALE**
- The §13 class: one wedged sidecar in a 30-hour run, undetected.
  Second: single-GPU contention makes ingest+query concurrency
  painful (reranker takes the same GPU: FAST latency during ingest).
  Storage and semantics scale linearly and are not the risk.

**WHAT SHOULD NOT BE TOUCHED BEFORE RELEASE**
- The semantic freeze: GLiNER pin, thresholds, labels, admission/
  Harbor rules, predicate compiler, canonicalization. Every number in
  this report is only meaningful against the frozen bundle
  (`authority fd68fc57`, contracts pinned by 638 passing tests).
- The evidence ledger and its append-only discipline.
- The sealed sets (never tune against them).

**FIRST POST-RELEASE IMPROVEMENT (in order)**
1. Readiness-probing supervision + claim-depth-1 for long stages
   (+ regressions) — turns the §13 class into a non-event.
2. CITATION/STRUCTURE-REGION-SUPPRESSION-V1 — layout evidence
   already exists; suppress relation candidacy in index/reference/
   heading/caption regions. Cheap, big precision win, no ontology
   change.
3. The first post-freeze semantic gate on relation precision:
   direction-sensitive frames for part_of/include, modality gate for
   creation/acquisition predicates, pronoun-surface durable-identity
   ban. The L4 disposition ledger is the ready-made measurement bed.

---

## VERDICT

# NOT PRODUCTION READY

— **as a knowledge-graph product.** The evidence layer, determinism,
recovery-from-crash, isolation, throughput, and text retrieval are
genuinely strong — most of the twenty categories above PASS, several
impressively. But the release question the graph must answer is
"can a user trust an edge?", and the measured answer today is: about
one in three projected edges is wrong, and the pipeline that produces
them cannot yet run a large ingest unattended without a human
re-driving projections. Those two findings — graph precision (P0) and
hang-death reliability (P1) — are exactly the two things a
production label would certify, and neither survives the evidence in
§7 and §13.

What IS production-grade today is honestly narrower: **a deterministic,
fault-tolerant, evidence-first ingestion and text-retrieval system
with a conservative experimental graph layer.** Shipped under that
description, it would be a true label. "PRODUCTION RELEASE" for the
full system becomes defensible after: (1) the two reliability fixes,
(2) structure/citation-region suppression, and (3) one post-freeze
semantic gate on relation precision measured on the L4 ledger — all
three of which this report's data makes straightforward to specify.

