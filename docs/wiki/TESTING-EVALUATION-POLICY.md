---
title: "Testing / Evaluation Reasoning Policy"
owner: "@king"
date: 2026-09-19
last_reviewed: 2026-09-19
status: active
scope: "Governs how any agent tests, evaluates, qualifies, or debugs Polymath. Authoritative — referenced from AGENTS.md and the polymath-bootstrap skill. Hypothesis-driven and decision-oriented, not exhaustive by default."
---

# TESTING / EVALUATION REASONING POLICY

When creating, modifying, qualifying, or debugging Polymath, testing must be **hypothesis-driven and decision-oriented**, not exhaustive by default.

The objective is not to maximize the number of test turns. The objective is to obtain the **smallest amount of high-quality evidence sufficient to answer the engineering question being asked**.

## 0. Classify the question first

Before choosing a test, name which question you are answering — the class dictates the experiment:

```text
1. IMPLEMENTATION   "Does the code work?"
                    → unit / synthetic tests

2. MECHANISM        "Did the mechanism CAUSE the intended behavior?"
                    → fixed-input PAIRED test (freeze upstream, vary only the mechanism)

3. QUALITY          "Does this improve representative behavior?"
                    → 15–20 stratified cases

4. SAFETY           "Did anything important regress?"
                    → 15–20 risk-stratified sentinel

5. RELEASE          "Do we need authoritative benchmark regeneration?"
                    → full regression only when justified
```

An end-to-end A/B (class 3) answers "is it better on representative behavior", NOT "did the mechanism
cause it". Only a class-2 fixed-input paired test isolates causation. Do not report an end-to-end
improvement as causal proof of a specific mechanism.

**Control before volume.**

```text
DO NOT substitute additional sample volume for experimental control.

Before increasing N, ask whether the current uncertainty is caused by:
  - too few observations   → increase N selectively
  - confounded inputs      → CONTROL THE VARIABLES FIRST
```

If two conditions receive different upstream inputs (plan, bridges, retrieval, RankedLane[]), more runs
will not turn a confounded comparison into a clean causal one — freezing the upstream will.

## 1. Start with the decision, not the benchmark

Before running a test, explicitly state:

```text
QUESTION:
What exact engineering question are we trying to answer?

HYPOTHESIS:
What behavior should occur if the implementation is correct?

FAILURE CONDITION:
What observable result would disprove or weaken that hypothesis?

DECISION:
What action will be taken after PASS, FAIL, or INCONCLUSIVE?
```

Do not run a large benchmark simply because one exists.

---

## 2. Use the smallest sufficient test

Default testing ladder:

```text
UNIT / SYNTHETIC PROOF
        ↓
SMOKE: 5–8 cases
        ↓
STRATIFIED QUALITY GATE: 15–20 cases
        ↓
TARGETED EXPANSION only if evidence is insufficient
        ↓
FULL REGRESSION only when specifically justified
```

A PASS at one level does **not automatically trigger the next larger test**.

Escalate only when:

* the current evidence is inconclusive,
* an observed failure needs localization,
* the change affects a broader surface than the smaller test covers,
* or a release/milestone explicitly requires authoritative regression.

---

## 3. Do not accidentally multiply test size

When the owner asks for:

```text
15–20 questions
```

interpret that as approximately:

```text
15–20 meaningful executions
```

unless the hypothesis specifically requires multiple conditions or modes.

Do NOT automatically transform:

```text
20 questions
```

into:

```text
20 × 4 retrieval modes = 80 executions
```

Cross-product testing requires an explicit reason.

Ask conceptually:

```text
Does this question need to run in every mode?

If NO:
    assign it to the mode/path that best exercises the invariant.

If YES:
    explain what cross-mode hypothesis is being tested.
```

---

## 4. Stratify instead of taking the first N cases

Small tests must preserve meaningful coverage.

For retrieval-quality qualification, construct approximately 15–20 cases across the important risk surfaces, such as:

```text
unsupported / hallucination
named-source recall
pMAP localization
q0 preservation
provenance / lineage
multi-source synthesis
latent/complementary retrieval
known difficult or sensitivity cases
```

Do not merely take the first 20 rows of a gold set if the ordering creates category bias.

Prefer a smaller stratified set over a larger poorly targeted set.

---

## 5. Separate different scientific questions

Do not use one giant test to answer multiple unrelated questions.

### Mechanism question

```text
Does V2 fusion preserve useful evidence that V1 loses?
```

Use:

```text
fixed upstream state
same RankedLane[]
same candidate arrivals
same local rankings

        ├── V1
        └── V2
```

Then compare only the changed mechanism.

A targeted 8–10 case paired replay may be more informative than dozens of noisy end-to-end runs.

### Production safety question

```text
Did this change regress important system behavior?
```

Use a 15–20 case stratified quality gate checking:

```text
hallucination
q0 preservation
provenance
source localization
success@K
MRR where applicable
multi-source behavior
```

### Cross-mode question

Only execute FAST/HYBRID/GRAPH/WILDCARD combinations when the hypothesis actually concerns differences between those modes.

---

## 6. Control confounds before increasing sample size

When comparing implementations, first determine whether upstream nondeterminism can alter the inputs.

Prefer:

```text
CONTROL VARIABLES
before
MORE RUNS
```

For causal comparisons, freeze as much upstream state as possible.

```text
q0
→ query plan
→ Scout
→ bridges
→ retrieval
→ RankedLane[]

FREEZE HERE

        ├── policy A
        └── policy B
```

If A and B receive different upstream evidence, do not describe downstream differences as clean causal proof.

---

## 7. Reuse frozen baselines

If an authoritative baseline already exists, do not continuously recompute it.

Use the frozen baseline as the comparison authority unless:

* relevant implementation semantics changed,
* the corpus materially changed,
* the benchmark itself changed,
* the baseline is suspected to be invalid,
* or a milestone explicitly requires full regeneration.

For Polymath, full CA5 remains an authoritative regression benchmark.

A smaller test should use a different name, such as:

```text
CA5-SENTINEL
STRATIFIED-REGRESSION-20
V2-QUAL-GATE
```

A sentinel PASS means:

```text
No regression detected in the scoped qualification set.
```

It must NOT be reported as:

```text
Full CA5 passed.
```

---

## 8. Full regressions are exceptional

Do not run expensive matrices such as:

```text
64 queries × 4 modes
```

during ordinary iteration unless the current decision genuinely requires that evidence.

Full regression is appropriate for:

```text
release qualification
major architecture cutover
final milestone
suspected broad regression
benchmark-baseline regeneration
small-test evidence that requires broader investigation
```

It is not the default response to every successful implementation.

---

## 9. Stop when the engineering question has been answered

At every test stage ask:

```text
Do we already have enough evidence to make the current decision?
```

If YES:

```text
STOP.
Report the result.
Make the decision.
```

Do not continue testing solely to make the evaluation look more thorough.

Thoroughness comes from:

```text
good hypotheses
good stratification
controlled comparisons
correct metrics
representative edge cases
clear stopping criteria
```

not raw turn count.

---

## 10. Default execution budget

Unless there is an explicit justification otherwise:

```text
tiny implementation check:
1–5 tests

smoke:
5–8 executions

normal iteration qualification:
15–20 executions

paired mechanism comparison:
~8–10 cases × 2 conditions
≈ 16–20 executions

combined serious decision:
usually <= 30–40 executions

>40 executions:
requires explicit justification

full benchmark:
milestone/release/special investigation only
```

These are reasoning defaults, not arbitrary hard limits. Increase them only when the evidence requires it.

---

## 11. Before launching any test, output this mini-plan

```text
TEST QUESTION:
...

WHY THIS TEST:
...

CASES:
N

EXECUTIONS:
N

STRATIFICATION:
...

CONTROLLED VARIABLES:
...

METRICS:
...

PASS:
...

FAIL:
...

ESCALATION CONDITION:
...

STOP CONDITION:
...
```

If `EXECUTIONS` is substantially larger than `CASES`, explain why.

If there is no clear reason, reduce the test.

---

# Governing Principle

> **Use the smallest controlled, stratified experiment that can answer the current engineering question with enough confidence to make the next decision. Expand testing only because evidence demands it, not because more testing is possible.**
