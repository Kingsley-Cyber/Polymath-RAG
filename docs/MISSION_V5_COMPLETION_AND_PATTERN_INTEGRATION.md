# Polymath V5 — Completion + Targeted Open-Source Pattern Integration

Governing mission for `architecture/evidence-first-v5`. This does not
replace the release mission; it **appends** a bounded improvement track
that activates only where holdout evidence identifies entity-layer
ownership.

Recorded 2026-08-22, at the point where the pipeline first had a clean
fast iteration loop.

---

## Why this is recorded now and not earlier

Until today the work was debugging infrastructure and semantic failures.
It is now a clean enough baseline to reason about *targeted* improvement
instead of firefighting:

| layer | state |
|---|---|
| Evidence layer | mature |
| Ledger | durable |
| Replay | deterministic |
| Crash recovery | tested |
| Extraction | **known quality ceiling** |
| Entity admission | **main research target** |
| Fact admission | improving, not yet a production KG |
| Retrieval | next |

The `core-3-v1` corpus (3 short documents, full pipeline in ~6 minutes)
is now the **unit test bench**. The mistake to avoid is making semantic
changes directly against the 25-book corpus again. The evidence ledger
was built precisely to enable this fast loop — use it.

---

## Enforced order

```
1. Finish core-3 retrieval baseline
        |
2. Run open-source pattern research      (read-only; may run in parallel)
        |
3. Pick ONLY entity-layer improvements
        |
4. A/B on the small corpus
        |
5. Promote ONLY if T2 truth improves
        |
6. Return to 25-book qualification
```

Research is read-only and changes nothing, so it may run concurrently
with step 1. **Implementation may not begin before step 3.**

---

## Absolute constraints

Unchanged from the release mission, restated because the research track
is where they are most likely to erode:

**Do not** rewrite the architecture · replace the evidence-first design ·
replace the GLiNER provider during release closure · introduce
LLM-generated facts · create embedding-only knowledge edges · promote
co-occurrence into facts · weaken Fact Admission · bypass provenance ·
remove deterministic replay.

**Fact Admission remains the final authority boundary.**

Anything that alters mention interpretation, entity identity, graph
eligibility, canonical membership or fact identity requires a **new
versioned contract**. Frozen contracts are never mutated in place.

---

## The core diagnosis

The relation layer is being **starved and contaminated by upstream
entity quality plus weak relation semantics**.

```
text
 |
GLiNER
 |
entities  (wrong boundary, wrong type, fragmented identity)
 |
relations  <- receives bad arguments
 |
facts      <- gate rejects good things OR accepts bad ones
```

The highest leverage is therefore **not another entity extractor**:

1. Make entities trustworthy
2. Resolve identities
3. *Then* redesign relation extraction/admission around high-quality
   endpoints

Target shape:

```
              ENTITY PIPELINE
                    |
       +------------+------------+
       |                         |
 entity mentions          entity candidates
       |                         |
       +------------+------------+
                    |
            ENTITY RESOLUTION
                    |
            canonical entities
                    |
            RELATION EXTRACTION
                    |
        subject / predicate / object
                    |
             FACT VALIDATION
```

---

## Measured issues

### ISSUE 1 — Entity extent / boundary errors (highest priority)

```
Pavlovian conditioning  ->  Pavlov
Crestline Automation    ->  Crestline
Figure 4-7              ->  admitted as a Document identity
```

GLiNER finds something plausible; the **boundary** is wrong. Relation
extraction cannot recover from incorrect endpoints.

Needed: span arbitration · NER + noun-chunk reconciliation ·
token-aligned validation · nested entity resolution · structural-artifact
rejection.

### ISSUE 2 — Identity fragmentation

`Kafka` / `Apache Kafka` / `Apache Kafka Streams` / `Kafka Streams API`
become separate identities. Measured **~7.7%**.

Needed: deterministic entity resolution · canonical keys · alias
management · lemma normalization · source-priority promotion. Must
improve recall **without creating false merges**.

### ISSUE 3 — Type inventory gaps / type drift

```
JointHOI -> Organization      Framework -> Product
DiffH2O  -> Document          Paper     -> Document
Kubernetes -> Product         Method    -> Organization
```

Root cause: GLiNER only sees the labels it is given.

Needed: ontology mapping · label hierarchy · type normalization ·
domain-adaptive labels.

### ISSUE 4 — Fact precision

Development corpus moved **38% wrong → 14.5% wrong**. Target **≤5%
wrong, ≥90% supported**. Development numbers are not release evidence.

Weak triggers observed on `core-3-v1`: `similar_to`, `created`,
`acquired`, `uses`, `member_of`, `founded`, `part_of`, `instance_of` —
weak because the **triggers are ambiguous**.

The answer is explicitly **not more relation models**. It is argument
extraction · predicate sense disambiguation · semantic role alignment ·
dependency-based relation extraction.

Comparison targets, with their standing here:

| system | shape | standing |
|---|---|---|
| Stanford OpenIE family | dependency parse → (subject, relation phrase, object) | good argument boundaries, no fixed label set, noisy → **candidate generation only, never truth** |
| REBEL (Babelscape) | seq2seq → triples | many relation types, but hallucination risk and low determinism → **probably not a production path here** |
| DyGIE++ / SciIE | span repr → entities → relations → coreference | relations extracted **after** entity spans exist; jointly reasons over span pairs rather than finding random relations → **closest to the needed shape** |

Existing predicate authority (VerbNet / PropBank / FrameNet / SemLink /
spaCy) is composed with, never replaced.

### ISSUE 5 — Graph retrieval scaling

Target ~300 books, millions of chunks. Needed: bounded traversal · max
depth · visited-node tracking · metadata edges · query planning ·
expansion limits · deterministic ordering · provenance returned.

---

## Reference repositories

### `DerwenAI/strwythura` — entity engineering

Import **only** these three patterns, each as a new versioned contract:

**`ENTITY_SPAN_ARBITRATION_V1`** — combine GLiNER spans + spaCy noun
chunks + token boundaries + subsumption rules.

```
GLiNER: "Crestline"          spaCy: "Crestline Automation"
                    |
          candidate: "Crestline Automation"
```

Requires evidence. **Never automatically expand all noun chunks.** Every
decision emits accepted span / rejected span / reason / evidence receipt.

**`TOKEN_ALIGNED_VALIDATION`** — before admission, verify the GLiNER
character span is a valid spaCy token span. Invalid spans become
**ABSTAINED**, not runtime failures.

**`LEMMA_KEY_CANONICALIZATION`** — surface form → normalized lemma →
identity candidate.

- Allowed: alias candidate generation, identity hints, source priority
- Forbidden: embedding-only merge, fuzzy merge without evidence

Worth studying: `EntityStore`, `tokenize_lemma`, source-priority
promotion. **Do not blindly copy its merging.**

### `datastax/graph-rag` — retrieval scaling only

**Do not import its extraction.**

**Declared-edge retrieval**: retrieval follows *existing* graph edges and
never invents relationships.

**`GRAPH_RETRIEVAL_POLICY_V1`**:

```yaml
max_depth: 2
max_candidates: bounded
visited_tracking: true
deterministic_ordering: true
provenance_returned: true
```

### `AVoss84/graph-rag` — comparison only

Do not import embedding-similarity edges, co-occurrence knowledge, or
raw concept-graph promotion. These build **associative** graphs, not
validated knowledge.

---

## Phases

**A — Finish operational qualification.** Supervision, restart testing,
checkpoint recovery, projection convergence, reconstruction.
Acceptance: no data loss, no duplicate semantic state.

**B — Entity improvement qualification.** Begins **only** after release
measurement identifies entity ownership. Creates
`ENTITY_PROVIDER_ADMISSION_V2` from `ENTITY_SPAN_ARBITRATION_V1` +
`ENTITY_CANONICALIZATION_V1` + `ENTITY_TYPE_MAP_V2`. Every change
requires a sealed test, a regression, and both precision **and** recall.

**C — Graph retrieval scaling.** Creates `GRAPH_RETRIEVAL_POLICY_V1`:
bounded hops, traversal budgets, deterministic ranking, provenance
return. **No graph creation logic.**

---

## Validation framework

Per change: inspect current implementation → compare with reference →
confirm it solves a *measured* failure → implement the smallest
compatible change → run regression → measure → commit.

Measured dimensions:

| entity | facts | retrieval |
|---|---|---|
| extent accuracy | supported % | FAST latency |
| fragmentation | wrong % | HYBRID latency |
| false merges | recall | GRAPH latency |
| typing accuracy | | determinism |

---

## Final decision rule

If operational reliability passes **and** the sealed holdout passes →
**PRODUCTION RELEASE**.

If retrieval works but T2 knowledge fails precision → release as an
**evidence-first retrieval system with an experimental knowledge
graph**.

**Never sacrifice truth for graph density.**

If the holdout fails: do not tune against sealed material. Classify
failure ownership first.
