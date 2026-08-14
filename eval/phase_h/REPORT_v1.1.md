# Phase H v1.1 — the lexical-semantic boundary verdict

## PHASE H (v1.1) VERDICT: REJECT

```text
Δ-correct   = +1
Δ-incorrect = +4
Δ-missed    = -4
```

The precision-first rule is decisive: `Δincorrect > 0` → **the hybrid
cannot become the production default as-is**. Class expansion recovered
6 facts the baseline missed, but it asserted 4 wrong edges (3 trap
cohort + 1 spurious pairing) and suppressed 2 facts the baseline
handled correctly. The data now names the exact failing mechanisms —
that is the gate working as designed.

## A. Frozen contracts

```text
git_commit            <recorded at run time in artifacts_v1.1/manifest.json>
resource_contract_id  03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150
tables_sha256         0ac3002ad2a2fcd79e33549faedfdc890f1d0f427852f5ae105f23c1a1ec81f1
rule_pack_version     1.0.1  ·  ontology core-v1
corpus v1.1           eval/gold/relations_v1.1.yaml
corpus v1.1 sha256    3ee7065acba980cbc61eeccc935774f864b9e677c60652c7f9f357253b5b484c
corpus v1.0 control   relations_v1.yaml @ fdfd75b4… (byte-identical; the
                      v1.0 rerun under the fixed harness reproduces the
                      v1.0 verdict: NO MATERIAL BENEFIT, 29/2/2, delta 0)
```

Corpus v1.1 was authored once and never modified afterward; the freeze
hash above is the binding identity. Harness defects discovered during
the run were fixed per the experiment bug protocol and both arms were
rerun on the unchanged corpus.

## B. Corpus v1.1 composition (33 items)

```text
EXPANDED_POSITIVE   11   (coin, author, inherit, recover, exploit, reuse,
                          inherit-passive, author-modality, inherit-negated,
                          recover-conditional, transmute)
CLASS_BREADTH_TRAP   3   (coin→founded, arrange→founded, confer→similar_to)
POLYSEMY            11   (develop x3, run x2, support x2, hold x2, form x2)
PASSIVE_PARSE        3
ARG1→ARG2            2
ASSERTION_CONTROL    3   (speculative / negated / conditional × expansion)
ALIGNMENT_GAP        2
STRUCTURAL           2
NO_RELATION          1
```

## C. Overall result (35 scoring units)

| Metric | Lexical | Hybrid | Delta |
|---|---:|---:|---:|
| Correct | 25 | 26 | +1 |
| Incorrect | 0 | 4 | +4 |
| Missed | 8 | 4 | -4 |
| Precision | 1.000 | 0.867 | |
| Recall | 0.758 | 0.867 | |
| F1 | 0.862 | 0.867 | |

## D. Paired transition matrix

```text
CORRECT -> CORRECT                         20
CORRECT -> INCORRECT                        3   (all three traps)
CORRECT -> MISSED                           2   (develop x2, FN-filter)
CORRECT_ABSTENTION -> INCORRECT             1   (e03 spurious parent edge)
MISSED -> CORRECT                           6   (recovered positives)
MISSED -> MISSED                            2   (ARG1->ARG2 exposure)
```

## E. Improvements (baseline missed → hybrid correct, n=6)

```text
v11_e01 coin    created(Acme, the brand name)      PB coin.01 + VN create-26.4
v11_e03 inherit acquired(firm, the subsidiary)     PB inherit.01 + VN obtain-13.5.2
v11_e04 recover acquired(company, the assets)      PB recover + VN obtain-13.5.2
v11_e05 exploit uses(model, the feature set)       VN use-105.1
v11_e06 reuse   uses(engine, the waste heat)       VN use-105.1
v11_v02 inherit-passive  acquired(firm, subsidiary) (frozen parse + expansion)
```

## F. Regressions (n=6, each with its mechanism)

```text
v11_t01 "John coined Acme"          -> hybrid FOUNDED(John, Acme)
        mechanism: class-expanded trigger accepted with no sense
        constraint; coining is not founding. THE trap.
v11_t02 "John arranged a conference" -> hybrid FOUNDED(John, conference)
        mechanism: same — arrange ∈ build-26.1/create-26.4.
v11_t03 "The board conferred a title" -> hybrid SIMILAR_TO(board, title)
        mechanism: confer ∈ correspond-36.1.1; conferring is not resembling.
v11_e03 "inherited ... from its parent" -> hybrid acquired(firm, its parent)
        mechanism: candidate pairing treats the oblique complement as a
        second object; spurious second edge.
v11_p01 "Microsoft developed Windows" -> hybrid MISSED
v11_v03 "Windows was developed by Microsoft" -> hybrid MISSED
        mechanism: the FrameNet anchor filter drops the developed rule —
        the candidate's COMPOSED frames (Mass_motion, Processing_materials)
        do not intersect the rule's cited frames (Creating). Enrichment
        suppresses a rule the baseline handled.
```

## G. Class-breadth risk verdict

The hypothesis is now measured, not hypothesized:

```text
class-expanded triggers recovered 6 correct facts
and created 3 wrong asserted edges
and (via the FN filter) removed 2 correct facts
```

The narrowest failing mechanism, per the trap examples: **an expanded
trigger is accepted on evidence-class + signature alone, without a
roleset/sense constraint** (coin has exactly ONE roleset, coin.01 — the
mapping exists but nothing requires it to be compatible with the
rule's semantics). Candidate for the next measured extraction
experiment (NOT applied here): require resolved-roleset compatibility
for class-expanded triggers.

## H. Polysemy contrast sets

```text
develop  p01 CORRECT both arms (baseline); hybrid MISSED via FN filter
         p02 intransitive -> CORRECT abstention, both arms
         p03 Document object -> CORRECT abstention (signature gap), both arms
run      p04 uses CORRECT both arms; p05 race-sense CORRECT abstention
support  p06/p07 no rule exists -> CORRECT abstention both arms
         (coverage exists; no rule consumes it — coverage != correctness)
hold     p08 owns CORRECT both arms; p09 contain-sense CORRECT abstention
form     p10 founded CORRECT both arms; p11 intransitive CORRECT abstention
```

On this corpus the resource layer did NOT perform additional sense
disambiguation in any polysemy item: every changed polysemy outcome is
a regression (develop/FN filter), and every correct polysemy outcome
was already correct in the baseline. Sense-narrowing value remains
unproven — flagged for a dedicated sense-disambiguation experiment.

## I. Safety behavior

```text
negated (v11_m02)       CORRECT abstention both arms (gate holds)
conditional (v11_m03)   CORRECT abstention both arms (gate holds)
speculative (v11_m01)   baseline abstained (no trigger); hybrid QUALIFY
                        created(...) certainty=speculative — correct per
                        the modality policy, scored as improvement-class
passive (v11_v01/v03)   orientation resolves identically in both arms
                        with frozen parse; v1.0's W7 gap was an input
                        gap, not a compiler defect (recorded)
direction regressions   0
assertion regressions   0
```

## J. Coverage is not correctness (v1.1 measurement)

```text
items with PB coverage        29  -> changed outcomes: +5 correct, +4 incorrect
items with VN coverage        26  -> (subset, same changes)
items with FN coverage        17  -> 2 correct facts LOST via the FN filter
items with direct SemLink     26  -> no case where SemLink changed the
                                     decision beyond what PB/VN already did
composed-only rolesets         0  -> resource topology finding: every
                                     composed pb->fn roleset also has a
                                     direct pb->vn mapping in this contract
alignment-gap items            2  -> g01 (manual absorb, working) CORRECT
                                     both arms; g02 (abdicate) abstention
                                     both arms. The gap hurt nothing here.
```

## K. Measured waterfall failure owners (both arms, unchanged)

```text
W2  candidate generation  v11_a01, v11_a02 (ARG1->ARG2 pairing absent)
W3/W6 FN anchor filter    v11_p01, v11_v03 (hybrid-only regression)
CLASS_BREADTH             v11_t01..t03 (hybrid-only spurious)
SPURIOUS PAIRING          v11_e03 parent edge (hybrid-only)
```

## L. Verdict and next steps

1. Did the layer improve extraction? **Yes: +6 recovered facts.**
2. Additional correct: **+6 gross (net +1 with the 3 converted-correct
   lost + 2 suppress regressions).**
3. Additional incorrect: **+4.**
4. Measurable resource value: **VerbNet class expansion (use-105.1,
   obtain-13.5.2, create-26.4) drove all 6 recoveries; PropBank/FN
   provenance attached but changed no decision beyond VN; direct
   SemLink changed nothing measurable.**
5. Benefiting predicates: **created (+1), acquired (+2), uses (+2),
   +1 passive acquired.**
6. Harmed predicates: **founded (+3 wrong), similar_to (+1 wrong),
   developed (-2 suppressed).**
7. Dominant remaining gaps: **the FN anchor filter (fix candidate: do
   not exclude on composed-only frame mismatch) and the missing
   roleset-sense constraint on expanded triggers.**
8. Hybrid as production default? **NO — rejected by the precision-first
   rule (Δincorrect = +4 > 0).** The layer is not broken; it is
   unconstrained. The two named mechanisms are the next measured
   experiments.

## Determinism

```text
v1.1 baseline sha256  6b2dbac8…  (run 1 == run 2 == run 3)
v1.1 hybrid   sha256  a40546d5…  (run 1 == run 2 == run 3)
v1.0 control rerun reproduces its frozen verdict exactly.
```

## Harness defect fixes (bug protocol, production untouched)

1. substring offset misassignment (v1.0 a09) — fixed + regression test
2. attributed-gold scoring (v1.0 b13) — fixed + regression test
3. spurious-edge accounting — fixed + union transition accounting test
4. oriented-fact recording (passive inversion recorded as surface
   order) — fixed + regression test
All fixes are harness-only; both arms rerun on both corpora.
