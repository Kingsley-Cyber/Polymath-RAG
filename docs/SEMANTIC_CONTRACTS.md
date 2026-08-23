# SEMANTIC CONTRACTS — versioned authorities

Every artefact that can change what Polymath ASSERTS is versioned. A
historical run stays replayable because no historical contract is ever
mutated in place: a change means a NEW version with its own identifier,
policy file and tests.

Read with `docs/ARCHITECTURE.md` (tiers) and
`eval/v5/FINDINGS_fact_admission_v1.md` (measurements).

---

## 1. Tier map

```
T0 EVIDENCE      observed; append-only; never a claim
T1 INFORMATION   interpreted and plausible; provenance-carrying; not asserted
T2 KNOWLEDGE     asserted; every recorded gate decision passed
```

Promotion is governed by two admission boundaries, in this order:

```
GLiNER mentions ─► ENTITY-KNOWLEDGE-ADMISSION-V1 ─► admissible endpoints
                                                          │
RelationCandidates ─────► FACT-ADMISSION-V1 ─────► CanonicalFact (T2)
```

Neither boundary deletes anything. A refusal withholds promotion; the
mention, the candidate, the span and the provenance all remain queryable
at T0/T1.

---

## 2. Frozen upstream contracts (unchanged by this work)

| contract | identity |
|---|---|
| GLiNER provider | `urchade/gliner_medium-v2.1` @ `40ec419335d09393f298636f471328b722c6da9e` |
| semantic authority hash | `fd68fc57f4c18057…` (asserted by three fence tests) |
| entity Harbor / admission-harbor-v2 | unchanged |
| canonicalization | unchanged |
| predicate rule pack | `core-predicates-v1.4.0.yaml`, byte-frozen (SCIENTIFIC-KAG-V1: research predicates + 35-type backbone; supersedes v1.3.0, which remains loadable for pinned replay) |
| layout evidence | `layout-evidence-v1` |
| slice manifest | `sentence-slice-manifest-v1` |
| syntax evidence | `syntax-evidence-v1` (spaCy, pinned) |

**Known defect in the frozen pack, reported not patched:** predicate
verb lists were expanded from VerbNet classes without sense
disambiguation — `obtain-13.5.2` inserted *make/source/receive* into
`acquired`, `use-105.1` inserted *work* into `uses`, a communication
class inserted *collaborate* into `similar_to`. FACT-ADMISSION-V1's F5
compensates by requiring PropBank/FrameNet sense agreement for
class-inherited triggers. Correcting the pack itself is a future
version.

---

## 3. FACT-ADMISSION-V1

* contract id: `fact-admission-v1`
* policy: `shared/polymath_shared/fact_admission_policy.yaml`
  (`fact-admission-policy-v1`)
* code: `shared/polymath_shared/fact_admission.py`
* tests: `tests/determinism/test_fact_admission.py`
* replay: `eval/v5/fact_admission_shadow.py` (whole ledger, ~10 s)
* explain: `eval/v5/fact_admission_explain.py`

Ordered, fail-closed. First REJECT decides; QUALIFY demotes to T1
without stopping the chain, so the decision log records every reason.

| gate | question | representative refusals |
|---|---|---|
| F1 PROVENANCE | can this be audited and replayed? | `MISSING_INPUT` |
| F2 REGION | does the source region license assertion? | `REGION_INDEX`, `REGION_CAPTION`, `REGION_BIBLIOGRAPHY` |
| F3 ENDPOINTS | are both endpoints assertable referents? | `ENDPOINT_*_PRONOMINAL`, `ENDPOINT_*_NOT_KNOWLEDGE` |
| F4 ASSERTION | does the document assert it, or entertain it? | `MODALITY`, `IRREALIS`, `NEG_SCOPE`, `CONTRASTIVE`, `NOMINALIZED_CLAUSE`, `ATTRIBUTED_CLAUSE` |
| F5 PREDICATE | does the evidence license THIS predicate? | `PRED_FRAME`, `PRED_STRENGTHENED`, `PREDICATE_T1_ONLY` |
| F6 SIGNATURE | is (settled type, predicate, settled type) licensed? | `SIGNATURE` |
| F7 DIRECTION | is the orientation witnessed? | `DIRECTION_UNWITNESSED`, `DIRECTION_UNLICENSED`, `DIRECTION_PASSIVE_AMBIGUOUS` |
| F8 SUPPORT | do the endpoints occupy argument positions? | `BINDING_ROLE`, `BINDING_TRIGGER_IS_NAME`, `BINDING_COPULA_COMPLEMENT`, `CROSS_SENTENCE` |

Policy data (declarative, versioned, no code change to retune):
region licensing · per-predicate orientation metadata · participial
inverse prepositions · modal auxiliaries (closed class) · contrastive
markers · irrealis and attribution governors · predicate strength
ordering · `t1_only_predicates`.

### Predicate assertability

`similar_to` is **T1-only**. Measured on the whole admitted population:
29% supported / 71% wrong. Its comparison triggers (`like`, `parallel`,
`related to`) mark exemplification or concurrency at least as often as
similarity and no deterministic contract separates the senses. It
remains fully provenanced Tier-1 information.

---

## 4. ENTITY-KNOWLEDGE-ADMISSION-V1

* contract id: `entity-knowledge-admission-v1`
* policy: `shared/polymath_shared/entity_admission_policy.yaml`
  (`entity-admission-policy-v1`)
* code: `shared/polymath_shared/entity_knowledge_admission.py`
* tests: `tests/determinism/test_entity_knowledge_admission.py`

Harbor decides INTERPRETATION and is untouched. This decides whether an
interpreted entity is strong enough to be ASSERTED as a canonical node.

| gate | refuses |
|---|---|
| E1 PROVENANCE | no offsets / chunk / surface |
| E2 REGION | index, bibliography, TOC, caption, heading, code |
| E3 SPAN | span cutting a word (`Pavlovian` → `pavlov`), surface/offset disagreement |
| E4 EXTENT | naming class headed by an adjective or non-nominal |
| E5 STRUCTURAL | `Figure 4-7`, `Table 13.7`, `Chapter 5`, `this book` |
| E6 TYPE | class outside the settled vocabulary |
| E7 DURABILITY | non-durable, MENTION_ONLY, pronoun-headed |

Genuine names containing structural words (`Table Mountain`) are matched
by `fullmatch` and survive.

F3 of the fact chain consumes these verdicts and attributes the reason to
the entity layer, so forensics separates "the relation gate failed" from
"the endpoint was never admissible".

---

## 5. REGION-POLICY-V1

* code: `shared/polymath_shared/source_region.py`
* shared by both admission boundaries — one structural truth.

Persisted layout evidence is the first authority. It is thin in practice
(13 of 25 documents, `heading` only), so structure is also derived from
the immutable chunk text by shape alone: citation density, page-reference
density, dot-leader and index-line geometry, code/config key lines,
caption line prefixes.

Chunk text is NORMALIZED — newlines are often stripped — so line
geometry alone is insufficient and density signals carry the rest. This
is the LAYOUT-EVIDENCE-V1 lesson restated: layout cannot be recovered
from normalized text, so it must be measured, never assumed.

Measured over 15,205 real chunks: BODY_PROSE 98.4%, INDEX 1.5%,
BIBLIOGRAPHY/CODE/HEADING <0.1%. Deliberately conservative.

---

## 6. LONG-STAGE-LEASE-CORRECTNESS-V1 (control plane)

Not a semantic contract, but it governs whether semantics ever run.

Invariant: **a ticket's `attempt` may increase only because an execution
failed, or because the worker executing it disappeared.** A ticket that
merely waited never consumes a retry.

* claim depth 1 at every worker entry point (`held` == `being processed`)
* lease renewal is owner-scoped
* the reaper distinguishes a stale owner (charge + quarantine) from a
  live heartbeating one (no charge, no quarantine, reason recorded)
* readiness (`/ready`, real forward pass, 503 when unusable) is probed
  periodically, not only at spawn; bounded restarts, storm-protected
* sidecar clients are connect-fast (5 s) and read-patient (300 s), rebuild
  the pool on transport faults, and end in typed `SidecarUnavailable`

Tests: `tests/integration/test_lease_correctness.py`,
`tests/determinism/test_supervisor_readiness.py`,
`tests/determinism/test_client_resilience.py`.

---

## 7. Persistence of decisions

Migration `0021_knowledge_tiers.sql`:

* `fact_admission_decisions` — one row per (fact, candidate, contract,
  policy) with outcome, gate, reason, flip, and a `shadow` flag.
* `knowledge_tier_facts` — derived tier per fact. **T2 requires every
  recorded decision to PASS**; one reject demotes.

`shadow = TRUE` means the decision documents what admission WOULD do
without governing the projected graph. Cutover flips the flag; it never
rewrites history.

---

## 8. Changing a contract

1. New version identifier; never edit a historical policy or pack.
2. Development suite covering the mechanism plus PASS controls.
3. Full L4 replay (~10 s) with a rejection census and per-predicate
   survival.
4. Adjudicate a fresh holdout that was sealed before inspection.
5. Only then flip `shadow` for that contract version.
6. Record the resulting authority hash and update the fence pins.
