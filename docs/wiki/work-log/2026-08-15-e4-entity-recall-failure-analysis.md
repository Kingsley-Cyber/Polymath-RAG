---
change_id: e4-entity-recall-failure-analysis
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (measurement-only analysis; no production change)
---

# E4: entity recall failure analysis (psychology/metacognition) — GLiNER discovery limitation

## Contract

Measurement-only: determine WHY the psychology concepts are missed,
classify ownership (model / label schema / prompt / threshold /
boundary / preprocessing), evaluate label-schema and threshold
variants WITHOUT touching production, and produce a recommendation.
No production changes; no threshold changes; no new model.

## Changes

- `eval/e4/analyze_e4.py` + `eval/e4/evidence.json`: raw-proposal
  inspection, per-concept classification (FOUND_EXACT /
  FOUND_OVERLAP / WRONG_BOUNDARY / MISSED), label schema variants
  A/B/C, threshold sweep 0.3–0.6, label-guidance experiment, and the
  cyber-document comparison — all against the frozen local GLiNER
  sidecar (gliner_medium-v2.1 @ 40ec4193, mps).

## Proof

Baseline (production labels, 0.5): psychology 2/13 FOUND_EXACT;
cybersecurity 12/20 FOUND_EXACT.

Threshold sweep (psychology): 0.6 → 1/13; 0.5 → 2/13; 0.4 → 3+2
overlap; 0.3 → 5+2 overlap. Even at 0.3, 6 of 13 remain MISSED and
proposal count grows 12 → 31 (noise). Lower thresholds do NOT
recover the concept class.

Label schemas: A (generic 5 labels) → 5 proposals, 2 found; B
(psych-specific: Cognitive Process / Learning Strategy /
Metacognitive Concept / Psychological Mechanism / Mental State) → 3
proposals, 2 found; C (mixed + Theory/Strategy/Cognitive Function) →
6 proposals, 0 found + 2 overlap. Domain-specific labels provide
ZERO recall benefit.

Label guidance ("Psychological concept including cognitive processes,
learning mechanisms...") → 2 found + 1 overlap. No benefit.

Boundary evidence: "metacognitive control" was proposed as
"metacognitive monitoring" (sibling-span confusion); "Elasticsearch"
→ "Elasticsearch cluster"; "site reliability engineer" →
"security engineering team" (adjacent-span proposals). GLiNER DOES
see adjacent concrete spans but does not fire on the abstract
lowercase compounds.

## Ownership table (baseline)

| Failure | Class | Owner |
|---|---|---|
| judgments of learning, processing fluency, familiarity effect, illusion of competence, working memory, retrieval practice, corrective feedback, self-regulated learning, local regulation, global regulation | MISSED (no proposal at any threshold 0.3–0.6) | GLiNER_DISCOVERY |
| metacognitive control | WRONG_BOUNDARY (sibling span) | GLiNER_BOUNDARY |
| AWS, CloudTrail, STRIDE, bearer token | MISSED (acronyms/compounds) | GLiNER_DISCOVERY |
| Elasticsearch, HTTP Authorization header, site reliability engineer, Security Architecture Council | WRONG_BOUNDARY / adjacent-span | GLiNER_BOUNDARY |

No admission/canonicalization/projection loss observed anywhere: every
span GLiNER proposed correctly reached downstream stages in E3/E3B.

## Root cause

GLiNER medium-v2.1's proposal surface favors capitalized proper
nouns and concrete technology/product terms. Lowercase abstract
multiword psychological constructs are largely invisible at every
measured threshold; label wording and schema changes do not recover
them (measured, not assumed). This is a MODEL-DISCOVERY limitation,
not a schema/prompt/threshold/preprocessing defect.

## Recommendation (smallest change)

- Accept the discovery limitation (Option A) for the invisible
  concepts: no deterministic intervention recovers them without a
  model change, which is out of scope and explicitly forbidden to
  recommend casually.
- The WRONG_BOUNDARY/adjacent-span slice (cyber compounds) is the
  only deterministic-lever candidate: a future span-normalization
  study could be measured; NOT attempted in this gate (E3B forbids
  patching).
- Multi-pass domain labels and threshold reduction measured and
  REJECTED (no recall benefit / noise).
- Production unchanged: frozen labels, frozen 0.5 threshold, frozen
  model.

## Rejected claims

- No new model recommended; no threshold/label changes; no
  production modification of any kind.

## Open contract gaps

- If recall of abstract lowercase constructs becomes a requirement, a
  future model qualification (bake-off, frozen protocol) is the only
  honest path — deferred to a user decision.
