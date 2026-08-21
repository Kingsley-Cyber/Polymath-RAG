# ENTITY-PROVIDER-FORENSICS-V1 — report

**READ-ONLY.** Code `v4-semantic-freeze` lineage (branch `forensics/entity-provider-v1`,
authority sha `8241bf94892ef0c8…` unchanged). No patches, no model swap, no
heuristic added. Production model: `urchade/gliner_medium-v2.1` @ `40ec4193…`.
Counterfactual: `fastino/gliner2-base-v1`, in-process, PyTorch/MPS, identical
texts, bare labels, label counts, threshold 0.5, and frozen Harbor downstream
for both arms. Rescue held out of BOTH arms (its re-queries go to the resident
medium sidecar, which would inject medium into the gliner2 arm).

Materials: i4 corpus (development) + two never-ingested calibration
transcripts supplied by the evaluator. Sealed smq1 documents were used for
lineage citation only, never for experiments.

---

## OUTPUT 1 — FAILURE WATERFALL (21 cases, UNEXPLAINED = 0)

Every case traced through: raw provider response (chunk-level, production
labels) → label mapping → rescue replay → persisted mention → admission.
Stage evidence in `waterfall_stages.json`.

| case | surface | bucket | first-divergence evidence |
|---|---|---|---|
| A05s | radiology review board | PROVIDER_NOT_PROPOSED | absent from chunk-level raw (12 labels); found at SENTENCE level 0.69 — context-length sensitivity |
| A10o | load-testing harness | PROVIDER_NOT_PROPOSED | absent chunk-level (20 labels); present sentence-level 0.69 |
| A14o | shift scheduling model | PROVIDER_NOT_PROPOSED | absent chunk-level; bare-phrase re-query finds it 0.60 |
| A16o | quality database | PROVIDER_NOT_PROPOSED | absent chunk-level |
| A09s | Nimbus billing service | PROVIDER_WRONG_EXTENT | raw = `Nimbus` 0.60; partial then also deleted by rescue |
| A09o | Nimbus Cloud platform | PROVIDER_WRONG_EXTENT | raw = `Nimbus Cloud` (missing `platform`) |
| A12s | Crestline plant | PROVIDER_WRONG_EXTENT | raw = `Crestline` 0.91→ persisted IDENTITY durable |
| A07s | Nimbus Cloud | PROVIDER_CORRECT_PIPELINE_DROPPED | raw EXACT Organization 0.90–0.95 ×3; deleted by refused-widening deletion (ledger 63) |
| SM3 | JointHOI | PROVIDER_WRONG_TYPE | raw Organization 0.57; `Method` was present in the queried inventory |
| SM4 | DiffH2O | PROVIDER_WRONG_TYPE | raw Document 0.54; `Method`/`Technology` present |
| A11s | Crestline Automation | ADMISSION_CORRECT_REFUSAL | raw EXACT 0.95; heading-only occurrence, row 47 ruling; gap is limitation 73 (extent/alias), not an error |
| LR1 | engineering group | ADMISSION_CORRECT_REFUSAL | raw EXACT; LOCAL_REFERENCE, antecedent not durable |
| LR2 | vision system | ADMISSION_CORRECT_REFUSAL | raw EXACT; generic head cannot constitute |
| LR3 | pump failure | ADMISSION_CORRECT_REFUSAL | raw EXACT; no antecedent |
| LR4 | production stoppage | ADMISSION_CORRECT_REFUSAL | raw EXACT; no antecedent |
| SM1 | L5 emphasis dynamics | ADMISSION_FALSE_PROMOTION | raw `Concept` 0.60 — a broad candidate BY DESIGN; acronym regex `^[A-Z][A-Z0-9]{1,}$` matched `L5` and promoted the whole phrase |
| SM2 | resting micro-sway amplitude | ADMISSION_FALSE_PROMOTION | raw `Measurement` 0.65; spaCy PROPN on `sway` promoted the phrase |
| R1–R3 | founded / causes / member_of FPs | RELATION_LAYER | S6B attribution; endpoints non-durable, never projected |
| TYP1 | Kubernetes | OTHER_EXPLAINED | raw `Framework` 0.62 at chunk level (`Technology` 0.86 at sentence level); mapping Framework→Product created the historical error — a MAPPING loss, not a bad model choice |

```
PROVIDER_NOT_PROPOSED            4
PROVIDER_WRONG_EXTENT            3
PROVIDER_CORRECT_PIPELINE_DROPPED 1
PROVIDER_WRONG_TYPE              2
ADMISSION_CORRECT_REFUSAL        5   (verified as designed)
ADMISSION_FALSE_PROMOTION        2
RELATION_LAYER                   3
OTHER_EXPLAINED                  1
UNEXPLAINED                      0
```

Two corrections to prior belief, from raw evidence: the smq1 phrase
promotions arrived as raw `Concept`/`Measurement` — the provider behaved as
the broad candidate generator the architecture asks it to be; ADMISSION
promoted them. And `Kubernetes→Product` is a label-MAPPING loss
(Framework→Product), not a model typing failure.

### New latent defect found during the counterfactual (no patch applied)

**Sub-token spans crash the extract stage.** A provider span nested inside a
single syntax token — `instagram` inside the URL token
`https://www.instagram.com/reel/…` — yields zero covering tokens, and
`identity_evidence(require_syntax=True)` raises `RetryableDependencyUnavailable`
("syntax unavailable") even though syntax is present. In production this
fails the extract stage deterministically on any URL-bearing document, and
retries cannot succeed. Neither i4 nor smq1 contains a triggering span; both
calibration transcripts do. Layer B_admission (token-filter conflates "no
covering tokens" with "no syntax"). **Release risk for the
structurally_different register.** Ledger row 75.

---

## OUTPUT 2 — GLINER-2 COUNTERFACTUAL

7 documents, 15 chunks, identical conditions. Full data: `cf_analysis.json`.

### Latency (chunk-level median, MPS)

| doc class | medium | gliner2 |
|---|---|---|
| i4 chunks | 63–79 ms | 49–64 ms |
| transcripts | 122–132 ms | 85–90 ms |

gliner2 is ~20–35 % faster at CHUNK length. This does not contradict the
sentence-level bake-off (equal at ~34 ms) — latency is context-length
dependent, and the earlier equality held only at sentence scale.

### i4 gold endpoints (38 instances checked)

- **gliner2 FIXES 5**: `radiology review board` (EXACT Organization),
  `load-testing harness`, `quality database`, `shift scheduling model`,
  `Nimbus billing service` (full extent).
- **gliner2 WORSENS 6**: `QBank item database`→`QBank`,
  `Mentor assessment engine`→`mentor`, `Coachlight review app`→`Coachlight`,
  `FreightNet routing platform`→`FreightNet`,
  `QuickScale invoicing system`→`QuickScale`, `Portside warehouse`→ABSENT.
- Unchanged-partial on both: `Nimbus Cloud platform`, `Crestline plant`,
  `Crestline automation team`.

**Net gold coverage: −1.** The two models contract COMPLEMENTARY shapes:
medium misses common-noun-only compounds outright; gliner2 contracts
`ProperName + common-noun-tail` compounds to the bare proper token.

### Typing

gliner2 fixes `Kubernetes`→Technology (vs Framework→Product) and
`engineering group`→Organization (vs Person). It regresses `Groq`→Person
(vs Organization) on a transcript. Several Technology↔Product drifts are
neutral.

### Downstream through frozen Harbor — the decisive axis

| doc | proposals m/g2 | durable m/g2 |
|---|---|---|
| i4 (5 docs) | 88 / 77 | 45 / 38 |
| transcript 1 | 54 / 116 | 5 / **11** |
| transcript 2 | 25 / 52 | 9 / **19** |

On messy registers gliner2 proposes ~2.1× as much and **more than doubles
what survives frozen Harbor**, with a materially higher false fraction.
Adjudication of its transcript durables: `66 seconds` (TimeReference
IDENTITY GLOBAL), `Comment` (Document), `matcha lattes` (Product),
`virgin/whore` (Concept), `~60-word sparse threshold` (Measurement — the
EXACT phrase-scope class as `resting micro-sway amplitude`),
`auto applied UTM parameters`, `CRM`, `Google article`, plus a 4-way
fragmentation of the UTM concept family and `Techne Writing` split across
THREE types (Person/Organization/Method → three GLOBAL ids). Medium's
transcript false durables are fewer (`simp`→Person, `URL`, a 2-way
Techne Writing split, `Samrush`/`Seamrush` transcription variants).

### Per current failure class

| class | gliner2 verdict |
|---|---|
| 1. spans never proposed | **FIXED** (all 4, exact) |
| 2. extent contraction | **WORSE** (fixes 1, keeps 3, introduces 6 new) |
| 3. typing errors | MIXED, mildly better (Kubernetes, engineering group; regresses Groq) |
| 4. label inventory | NOT_PROVIDER_OWNED |
| 5. phrase-scope identity leakage | **WORSE** (`~60-word sparse threshold`, `auto applied UTM parameters`; durable volume ×2.1 with higher false fraction) |
| 6. rescue deletion | NOT_PROVIDER_OWNED |

---

## OUTPUT 3 — LABEL INVENTORY ANALYSIS

Independent of model choice:

1. **Genuinely missing types.** No profile carries `Model`/`Algorithm`/
   `Paper`-like labels for research artifacts EXCEPT `software_tech` (which
   has `Model`, `Dataset`). `media_film` and `facs_body` (the smq1 profiles)
   do not — so `JointHOI`/`DiffH2O` had no precise label available. But
   `Method` WAS available and not chosen: those two cases are model choice
   errors first, inventory gaps second.
2. **Mapping coarseness is a distinct loss channel.** `Framework→Product`
   turned a defensible raw label into the historical `Kubernetes→Product`
   error; `Dataset→Document` similarly lossy. The mapping is part of the
   frozen query policy; noting, not changing.
3. **Wrong-type-with-correct-label-present** (model choice): JointHOI,
   DiffH2O, Groq (gliner2), engineering group (medium).
4. **Label count**: dilution (row 64) affects the RESCUE re-query lane;
   pass-1 chunk behaviour is dominated by context length, not count, in the
   cases traced.

**Proposed future experiment (design only, NOT run):**
`ENTITY-PROVIDER-QUERY-QUALIFICATION-V2` — factorial on a fresh sealed
provider-qualification set with span gold:
models {medium, gliner2} × inventory {core-12, core-12+Model/Algorithm/Paper}
× label count {12, 17, 20}, bare representation only (descriptive already
refuted by GLINER-SPEED-V1). Score span availability, extent, typing, and —
mandatory — false durable identities through frozen Harbor. Acceptance
requires no net-negative gold extent and no increase in false durables.

---

## OUTPUT 4 — MODEL-SWAP DECISION

**C. PROVIDER MODEL IS NOT THE DOMINANT PROBLEM.** (Operationally: keep
GLiNER medium — A follows from C.)

GLiNER-2 fails the stated bar for B: it fixes the four never-proposed
endpoints but introduces six new gold extent contractions (net −1 on gold)
and produces an unacceptable increase in false durable identities on messy
registers (durable volume ×2.1, higher false fraction, including new
instances of the exact phrase-scope class under investigation).

The dominant traced losses are owned elsewhere: the rescue deletion defect
(pipeline, ledger 63), admission phrase promotion (acronym regex + PROPN
mis-tag single-token evidence), relation over-generation, and extent/alias
linking (limitation 73) — none of which a provider swap addresses.

---

**STOP.** No implementation. Artifacts: `waterfall.py`, `waterfall_stages.json`,
`bench_stage1.py`, `cf_inputs.json`, `cf_medium.json`, `cf_gliner2.json`,
`cf_stage2.py`, `cf_analysis.json`.
