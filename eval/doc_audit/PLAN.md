# SINGLE-DOCUMENT QUALITY AUDIT — test plan

Authored BEFORE execution. Question is not "does it match gold" but
**"are the facts it emits accurate and useful, and which mechanism
changes that."**

## Question

For one document at a time: of the facts emitted, how many are usable in
a knowledge graph, and does changing the relation binder or the chunker
change that — in which direction, at what cost?

## Design: one control, two single-axis variables

| arm | relation_pipeline | chunker | rescue | pack | syntax |
|---|---|---|---|---|---|
| **CONTROL** | legacy_v1 | legacy_v1 | on | 1.3.0 | spacy |
| **VAR-BIND** | **kimi_v1** | legacy_v1 | on | 1.3.0 | spacy |
| **VAR-CHUNK** | legacy_v1 | **semantic_v2** | on | 1.3.0 | spacy |

Exactly one axis moves per arm. Held constant everywhere: GLiNER model
`urchade/gliner_medium-v2.1` @ `40ec4193` at threshold 0.5, query policy
v1 (identity), rescue = all stages, rule pack 1.3.0, spaCy syntax live,
the frozen corpus, admission policy v1.1, canonicalizer.

Document is a STRATUM, not a variable: all 5 documents run in every arm
and are reported individually. Nothing is averaged across documents.

## Two answer keys

**Key A — frozen I4 gold** (`eval/i4/gold/fact_gold.json`). Authored
before any extraction existed; boundary-strict. Gives TP/FP/FN. Unbiased.

**Key B — utility key** (`KEY_B.json`, authored here from document TEXT
only). Judges usefulness, which gold does not measure: a fact can match
no gold row and still be worth having, and can match nothing while being
actively misleading.

> **Bias disclosure:** Key B is NOT blind. Before authoring it I had
> already seen VAR-CHUNK's FP/FN lists for all 5 documents and its full
> emitted-fact list for doc 05. Items marked `pre_known: true` were
> visible to me first and must be discounted. Items marked
> `pre_known: false` were derived from the text alone.

## Verdict vocabulary (Key B)

- `CLEAN` — true against the text AND both endpoints are referable
  entities. Usable in a graph.
- `MISLEADING` — defensible but drops or distorts the sentence's actual
  content (e.g. binds the agent to the patient instead of patient to
  recipient).
- `JUNK` — endpoint is not a referable entity (bare plural, unresolved
  definite description). Creates a meaningless node.
- `FALSE` — contradicted by the text.

## Pre-registered predictions (falsifiable)

1. **VAR-BIND recovers the ditransitives.** "Crestline linked the vision
   system to the quality database" (doc 03) and "Corval linked the
   QuickScale invoicing system to the FreightNet routing platform"
   (doc 05) should bind ARG1<->ARG2, not ARG0<->ARG1. CONTROL is
   expected to emit `associated_with(crestline|corval -> ...)` instead.
2. **VAR-BIND reduces MISLEADING but not JUNK.** Junk is an admission
   failure; no binder change can refuse a bare plural.
3. **VAR-CHUNK raises fact count AND junk count** vs CONTROL.
4. **No arm merges duplicate identities.** Canonical clusters == entity
   count in every arm (canonicalization is currently a no-op).
5. **`causes(pump failure -> production stoppage)`** (doc 03, explicit
   "caused") should be found by ALL arms; if no arm finds it, the
   `causes` predicate is unreachable, not mis-bound.

A prediction that fails is reported as failed.

## Metrics per arm per document

facts emitted · gold TP/FP/FN (doc-scoped) · Key B verdict counts ·
trap sentences wrongly asserted · duplicate-identity pairs ·
canonical clusters vs entities.

## What decides what

- MISLEADING drops in VAR-BIND -> the ADR-0016 binder earns promotion
  on quality grounds independent of its aggregate P/R.
- JUNK constant across arms -> the admission gate is the blocker, and
  neither binder nor chunker work will move it.
- Fragmentation constant across arms -> canonicalization is the blocker,
  and it is orthogonal to both.
