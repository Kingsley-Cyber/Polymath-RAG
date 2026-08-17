# EXTRACTION-CONTEXT-V1: measurement report — NOT QUALIFIED

## Dev matrix (key sentence + anaphora case, frozen GLiNER, threshold .5)

### KEY SENTENCE: "A robust implementation uses bounded leases,
deterministic stage contracts, and transactional claim operations..."

| Policy | robust implementation | bounded leases | det. stage contracts | trans. claim ops |
|---|---|---|---|---|
| C0 FOCAL_ONLY | Technology .546 | Technology .858 | Technology .840 | Process .913 |
| C1 HEADING+FOCAL | **DISAPPEARS** | Technology .895 | Document .874 | Process .846 |
| C2 PREVIOUS+FOCAL | Technology .672 | Technology .799 | Document .906 | Process .642 |
| C3 HEADING+PREV+FOCAL | Technology .540 | Technology .727 | Document .935 | Process .535 |

**CONTEXT DOES NOT FIX THE KEY SENTENCE.** "robust implementation" stays
Technology (or disappears) under every context variant. The failure is a
TYPE-CLASSIFICATION issue, not a context-starvation issue.

### ANAPHORA: "The company employs three new instructors"

| Policy | "The company" | "Brightpath Learning" |
|---|---|---|
| C0 FOCAL_ONLY | Organization .833 (→ FP) | absent |
| C2 PREVIOUS+FOCAL | **DISAPPEARS** | .987 (context-owned, dropped) |

Context DOES eliminate this FP source: when the antecedent is visible,
GLiNER stops proposing the generic "The company" and proposes the real
name instead — which is then correctly classified OUTSIDE_FOCAL and
dropped. The focal chunk gets no generic endpoint. **This is the one
measured context benefit.**

### TYPING REGRESSION: "deterministic stage contracts"

| Policy | typing | USES object legal? |
|---|---|---|
| C0 | Technology .840 | YES |
| C1 | Document .874 | NO |
| C2 | Document .906 | NO |
| C3 | Document .935 | NO |

Context makes this WORSE: surrounding "contracts" prose pulls GLiNER
toward Document typing, breaking a currently-working endpoint.

## NET ASSESSMENT

- ANAPHORA: context helps (removes generic FP endpoints)
- KEY SENTENCE: context does not help (typing issue, not context)
- DETERMINISTIC STAGE CONTRACTS: context actively hurts (breaks typing)

NO POLICY DOMINATES: C2 fixes anaphora but breaks deterministic-stage-
contracts typing; C1 makes the key span disappear; all variants leave
the key sentence's USES failure unresolved.

## VERDICT: NOT QUALIFIED

No context policy is qualified. The mechanism (envelope construction,
hard-boundary enforcement, offset ownership classification) is
implemented, tested, and committed as dormant infrastructure
(POLYMATH_EXTRACTION_CONTEXT=C0_FOCAL_ONLY default = byte-identical).
The measured evidence says the dominant extraction failure is neither
arbitration (6/190 conflicts) nor context starvation on the key class —
it is **type classification under the frozen GLiNER model**.

## Evidence for future gates

1. The key-sentence typing failure ("robust implementation" Technology)
   persists under all context configurations → the remaining lever is
   either the model itself or the predicate signature (if Technology
   is genuinely the best available typing and the USES subject should
   accept Technology, that is a signature decision).
2. The anaphora FP elimination is real and valuable — worth revisiting
   if a future typing fix makes context the remaining bottleneck.
3. The deterministic-stage-contracts typing degradation under context
   is a caution: more context is not monotonically better for GLiNER
   typing on the frozen model.
