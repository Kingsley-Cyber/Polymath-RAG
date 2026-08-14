# Phase H — Lexical-Semantic Waterfall Qualification

## PHASE H VERDICT: NO MATERIAL BENEFIT

```text
Δ-correct   = 0
Δ-incorrect = 0
Δ-missed    = 0
```

The verdict framework: `Δcorrect = 0 AND Δincorrect = 0` → **NO MATERIAL
BENEFIT**. This is a corpus finding, not a layer finding (see §L): the
frozen corpus contains **zero examples that exercise the difference
between the arms**. The arms are proven different (isolation tests: a
class-member trigger compiles UNSUPPORTED in the baseline and FOUNDED in
the hybrid), but every gold trigger in the frozen corpus was authored
from the manual YAML vocabulary, so the two arms converge identically
on all 33 scoring units.

## A. Frozen contracts

```text
git_commit            12645c1
resource_contract_id  03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150
tables_sha256         0ac3002ad2a2fcd79e33549faedfdc890f1d0f427852f5ae105f23c1a1ec81f1
rule_pack_version     1.0.1
ontology_version      core-v1
gold corpus           eval/gold/relations_v1.yaml v1.0 (sha256
                      80585e35…, NEVER modified during the experiment)
arm boundary          baseline: load_rule_pack(use_resources=False) +
                      candidates(enrich=False)
                      hybrid:   load_rule_pack(use_resources=True) +
                      candidates(enrich=True)
                      compiler DAG identical (compile_relation)
```

## B. Corpus

```text
28 items (Band A canonical mechanics + Band B failure taxonomy)
23 gold triples + 5 abstention items
33 scoring units (gold triples + spurious-edge accounting)
cohorts: C1 PB=25, C2 VN=17, C3 FN=8, C4 direct SemLink=8,
         C5 composed-only=0, C6 alignment-gap=0, C7 no-coverage=3,
         C8 polysemous=1 ("run"), C9 assertion-control=4, C0 manual-only=3
```

## C. Overall result

| Metric | Lexical | Hybrid | Delta |
|---|---:|---:|---:|
| Correct | 29 | 29 | 0 |
| Incorrect | 2 | 2 | 0 |
| Missed | 2 | 2 | 0 |
| Correct abstentions | 5 | 5 | 0 |
| Spurious edges | 2 | 2 | 0 |
| Direction errors | 0 | 0 | 0 |
| Assertion errors | 0 | 0 | 0 |
| Precision | 0.935 | 0.935 | 0 |
| Recall | 0.935 | 0.935 | 0 |

## D. Paired verdict

```text
Δ-correct   = 0
Δ-incorrect = 0
Δ-missed    = 0
```

All 33 units transition in the NEUTRAL cells: 29 `CORRECT → CORRECT`,
2 `INCORRECT → INCORRECT`, 2 `MISSED → MISSED`.

## E. Waterfall (where the losses are)

```text
33 units
 ├─ 2 incorrect: spurious edges
 │    b06: (The team, founded, startup) — extra pair from the nested
 │         sentence, compiled but not gold
 │    b13: (Alice, founded, Acme) — the OUTER speaker compiled as the
 │         agent; gold names Bob. Attribution-role assignment is a
 │         candidate-generation gap, not a compiler error.
 └─ 2 missed
      a02: "Acme was founded by John" — passive orientation needs a
           syntactic parse; frozen inputs carry none → W7 loss.
      b11: "The protocol converts plaintext into ciphertext" — gold
           (plaintext → ciphertext) requires ARG1→ARG2 pairing; v1
           candidate generation pairs only left-subject → right-object
           → W2 loss.
```

Both arms identical here — the losses are upstream of the enrichment
boundary (candidate generation / orientation), so resource enrichment
cannot help or hurt them.

## F. Resource cohorts

| Cohort | n | baseline correct/incorrect/missed | hybrid correct/incorrect/missed |
|---|---:|---|---|
| C0 manual-only | 3 | 3/0/0 | 3/0/0 |
| C1 PropBank | 25 | 22/1/2 | 22/1/2 |
| C2 VerbNet | 17 | 15/1/1 | 15/1/1 |
| C3 FrameNet | 8 | 6/1/1 | 6/1/1 |
| C4 direct SemLink | 8 | 6/1/1 | 6/1/1 |
| C7 no coverage | 3 | 3/0/0 | 3/0/0 |
| C8 polysemous | 1 | 1/0/0 | 1/0/0 |
| C9 assertion control | 4 | 4/0/0 | 4/0/0 |

C5 (composed-only) and C6 (alignment-gap) are n=0 in the frozen corpus.
Coverage does not predict outcomes here: identical results across
cohorts because the corpus cannot discriminate the arms.

## G. Predicate breakdown

14 of 28 predicates have gold examples (see
`predicate_breakdown.csv`). Every predicate with gold support compiles
identically in both arms; the only losses are `founded` (a02, passive
orientation) and `transforms_into` (b11, candidate generation). No
predicate has an arm-dependent delta.

## H. Polysemy

The five families are essentially absent from the frozen corpus:
`develop` n=0, `run` n=1 (a04 "runs on" — single-sense in context),
`support` n=0, `hold` n=0, `form` n=0. The corpus cannot measure whether
resource enrichment reduces wrong-sense selection. The lookup tables DO
expose candidate senses (unit-tested: `TestPolysemy`), but no frozen
example exercises multi-sense disambiguation.

## I. Safety behavior

All 4 assertion-control items behave identically and correctly in both
arms: b01 negated → REJECT, b02 speculative → QUALIFY, b03 question →
REJECT, b12 negated+comparison → REJECT. Passive orientation (a02)
misses in both arms identically. Zero assertion regressions.

## J. Regressions

`baseline correct → hybrid incorrect`: **none** (n=0).

## K. Improvements

`baseline wrong/missed → hybrid correct`: **none** (n=0).

## L. Known gaps (why the corpus is blind)

1. **Gold-trigger construction bias.** The frozen corpus v1.0 was
   authored alongside the manual trigger YAML (experiment 0002). Every
   gold evidence trigger is therefore in the manual vocabulary; class
   expansion has nothing to add on this corpus.
2. **No resource-expanded trigger examples.** The 58 class-expanded
   triggers (e.g. `coin` ∈ create-26.4) never appear in gold.
3. **No multi-sense disambiguation examples** (C8 ≈ empty).
4. **No direct-vs-composed discrimination examples** (C5 n=0).
5. Upstream gaps carried forward: 2,047 unaligned SemLink→VN ids
   (C6 n=0 in corpus), 2 malformed PropBank XMLs.
6. **Probe (outside the frozen verdict):** `coin` compiles UNSUPPORTED
   in the baseline and FOUNDED(John, Acme) / CREATED(John, "the term")
   in the hybrid. The CREATED sense is correct; the FOUNDED sense shows
   class-membership breadth can reach the wrong Polymath sense — a
   real risk that the frozen corpus cannot currently measure. This is
   the single most important follow-up cohort for corpus v1.1.

## M. Conclusion

1. Did the layer improve extraction? **Unmeasurable on this corpus —
   the arms converge identically on all 33 units.**
2. Additional correct facts: **0**.
3. Additional incorrect facts: **0**.
4. Which resources produced measurable value? **None measurable here**
   (the isolation tests prove the layer CHANGES compilation; the corpus
   never asks it to).
5. Which predicates benefited? **None measurable.**
6. Which predicates did not? **All identical.**
7. Dominant remaining misses: **candidate generation (W2: b11) and
   orientation (W7: a02 passive)** — both upstream of the resource
   boundary, neither addressable by lexical enrichment.
8. Should hybrid become the production default? **Not decided by this
   experiment.** The data cannot promote it (NO MATERIAL BENEFIT) and
   cannot reject it (zero regressions, and the isolation probes show
   the layer is inert wherever the corpus is blind). The decision must
   wait for a corpus that exercises the boundary — specifically
   resource-expanded triggers and multi-sense disambiguation.

## Harness defect fixes (per the experiment bug protocol)

Three harness-only defects were found and fixed during the experiment;
production code was untouched. Both arms were rerun after each fix.

1. **Substring offset misassignment** (a09): right-side entity search
   anchored before the evidence span; "cognition" (substring of
   "Metacognition") was mis-assigned. Fixed: right-side search starts
   after the evidence span. Regression test added.
2. **Attributed gold scoring** (b13): gold `attributed: true` now
   expects QUALIFY (like `qualified`), not ACCEPT.
3. **Spurious-edge accounting**: predicted facts matching no gold
   triple are now INCORRECT units (b06, b13 surfaced as the two
   spurious edges) instead of being invisible.

## Determinism

```text
baseline predictions sha256  0afdd1a4… (run 1 == run 2)
hybrid   predictions sha256  aed28607… (run 1 == run 2)
```

## Artifacts

`eval/phase_h/artifacts/`: manifest, frozen_inputs, gold, both arms'
predictions + hashes, both arms' waterfalls, metrics, paired
transitions, predicate breakdown, resource cohorts, assertion
breakdown, polysemy breakdown, coverage report, changed examples.
