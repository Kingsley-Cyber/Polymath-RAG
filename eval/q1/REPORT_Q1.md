# Q1 Qualification Report — heterogeneous production extraction

Status: FROZEN — PASS
Date: 2026-08-14
Experiment: heterogeneous production extraction qualification (gate Q1,
Milestone A → CORPUS_INGEST_READY)

## Qualification manifest

| Field | Value |
|---|---|
| corpus | `eval/gold/qualification_q1.yaml` v `q1.0` (53 items, 11 classes) |
| corpus sha256 | `2ce1d237d222e1feaf573747abb53c3a618d557b561667f22d5d336c1dbe380a` |
| scorer | `eval/phase_h/harness.py` (frozen Phase H harness, unchanged) |
| scorer sha256 | `94fdc6a9a92abb9f9ae0206e4b4d67ac4e42ad93f4fa9e80fefa0f5efc5b656c` |
| rule pack | v1.0.1 (frozen, unchanged) |
| compiled lexical sha256 | `5c58adbd3cfc18e2e8b28245d5166dbb2920a33210ca7ccc0051231b421c8806` |
| resource contract | `03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150` |
| tables sha256 | `0ac3002ad2a2fcd79e33549faedfdc890f1d0f427852f5ae105f23c1a1ec81f1` |
| pipeline/commit (harness artifacts) | `ea07368` (compiler/rulepack unchanged through all Q1 fixes) |
| production arm measured | `baseline` (lexical lane — the production default) |
| exposure count | 2 (1 authoring-validation run used ONLY to align entity types to the frozen ontology signatures; 1 frozen qualification run) |
| label | qualification regression (NOT held-out/independent; authored against the frozen ontology; results locked by `tests/contracts/test_q1_qualification_regression.py`) |

## Document classes (per-class breakdown, baseline arm)

| Class | Items | CORRECT | INCORRECT | MISSED | Notes |
|---|---|---|---|---|---|
| BUSINESS | 9 | 9 | 0 | 0 | |
| TECH | 8 | 7 | 0 | 1 | t05: W2 same-side pairing (known limitation) |
| SCIENCE | 6 | 5 | 1 | 0 | s05: spurious second object edge |
| PEOPLE | 4 | 3 | 0 | 1 | p04: leadership trigger ambiguity probe |
| GEO | 3 | 3 | 0 | 0 | |
| TIME | 3 | 2 | 0 | 1 | tm03: temporal rule cannot express event LOCATION (type constraint) |
| CLASSIFY | 4 | 3 | 2 | 0 | c03: part_of direction on whole-first phrasing + reversed spurious edge |
| SCOPE | 6 | 6 | 0 | 0 | negation/conditional/question/speculative/hypothetical/attributed all correct |
| NO_REL | 4 | 4 | 0 | 0 | abstention controls: no false facts |
| PASSIVE | 3 | 3 | 0 | 0 | frozen parse direction correct (ps01/ps02); ps03 correct abstention |
| OOV | 3 | 3 | 0 | 0 | 2 correct abstentions + 1 correct uses via "leverages" |
| **total** | **53** | **50** | **3** | **3** | |

## Counts (baseline = production lexical arm; 56 scored units)

- correct 50 / incorrect 3 / missed 3
- **precision 0.9434** · **recall 0.9434** (F1 ≈ 0.943)
- wrong-predicate count: **0**
- wrong-direction count: **1** (q1_c03)
- wrong-scope count: **0** (all 6 assertion-control items correct)
- missed count: **3** (q1_t05, q1_p04, q1_tm03)
- unsupported rate: abstention + OOV controls 7/7 correct; spurious edges 2 (q1_c03 reversed edge, q1_s05 extra object edge)
- hybrid arm (measured, NOT production): 49/2/1/4 — Δcorrect −1, Δmissed +1 vs baseline; consistent with the Phase H v1.1 REJECT (hybrid stays off)

## Recurring failure classes (catalogued, NOT blocking)

1. **part_of direction on whole-first phrasing** ("consists of"): whole→part
   inversion + a reversed spurious edge (q1_c03). Precision-cost class;
   structural phrasing is rare in real corpora.
2. **Spurious multi-object pairing**: one trigger, two right-side
   entities → both edges asserted (q1_s05). Same class as the Phase H
   oblique-pairing finding.
3. **W2 same-side pairing**: gold endpoints both on one side of the
   trigger are never paired (q1_t05). Known limitation (CURRENT_STATE
   W2 entry), recall-only.
4. **Leadership trigger ambiguity**: overlapping `leads`/`has_role`
   vocabularies abstain without roleset evidence (q1_p04). Deliberate
   conservative behavior.
5. **Temporal rule cannot express event location**: `occurred_at`
   requires a TimeReference object (q1_tm03). Ontology constraint, not
   a crash.

No new failure class was discovered by Q1. The Q1-discovered defect
was operational (below), not extraction-quality.

## Canonicalization errors

- Pipeline E2E over 9 heterogeneous documents: canonicalize +
  project_canonical committed for every run, **0 canonicalization
  errors**, registry converged (16 canonical entities / 16
  memberships), replay no-op, incremental-convergence and
  destructive-reconstruction already proven by the C1/C2 suites.
  The mini-corpus produced no cross-document merge opportunities
  (unique surfaces by construction); merge behavior is covered by
  `tests/determinism/test_canonicalizer.py` and the C1/C2 E2E suites.

## Evidence/provenance integrity (pipeline E2E, real GLiNER)

- 10 facts / 10 evidence rows; **0 facts without evidence**;
  **0 facts missing provenance** (rule_id + resource_contract_id +
  compiled_lexical_sha256 present on every accepted fact).
- All facts ACCEPT; predicates: located_in 5, developed/has_role/
  leads/occurred_at/part_of 1 each.

## Operational failures

- 9 docs × 8 stages = 72 stage commits; **0 failed attempts**;
  **0 degraded runs** on a clean corpus (after the Q1 fix below).
- Q1 DISCOVERED a repeatable operational defect: `verify_projections`
  ran before `canonicalize`/`project_canonical` and reconciled
  canonical state that was not yet due → false degraded status on
  every incremental ingestion. Fixed by reordering the census chain
  (canonical projection now precedes verification); the temporary
  verify-side gating was reverted. Fix validated: 0 degradations over
  the full heterogeneous run; full suites green.

## Regression tests added

- `tests/contracts/test_q1_qualification_regression.py`: freezes the
  corpus hash, scorer hash, and the baseline metrics (P/R/counts).
  Any compiler/rule-pack change that moves these numbers fails CI.

## Final verdict

**PASS — extraction qualified for bulk corpus ingestion.**

- 0 wrong-predicate, 0 wrong-scope, precision 0.943 on heterogeneous
  input; every residual failure is a catalogued, non-blocking
  limitation with a known class; the production path (lexical lane,
  frozen compiler v1.0.1) is unchanged; pipeline integrity is clean
  end to end with real GLiNER.

**Production extraction is qualified. Further extraction changes
require a demonstrated regression or separately measured improvement.**
