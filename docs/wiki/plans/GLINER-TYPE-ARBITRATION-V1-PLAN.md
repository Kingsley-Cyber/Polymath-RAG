---
owner: worker
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: draft
---

# GLINER-TYPE-ARBITRATION-V1 — Implementation Plan

Status: DRAFT — authorized for planning only. No implementation, no
execution, no commits. Awaiting explicit gate authorization.

## 1. Problem statement (acknowledged from measured evidence)

The vocabulary experiment (GLINER-QUERY-VOCAB-v2, commit 55269c8)
exposed a defect in the merge rule that is conceptually prior to both
EXTRACTION-CONTEXT-V1 and any predicate-signature work:

**Cross-context score comparison is invalid.** GLiNER scores are
conditional on the label set / query context:

- same span, same model: single label .929 → two labels .672
- larger label set: spans can disappear entirely

Therefore `.773 (identity pass) > .559 (alias pass) → keep Technology`
compares numbers that are not on the same scale. The current
`max(raw_score)` union rule destroys a potentially better type
hypothesis using an unreliable comparison.

Measured instance (QUALITY-PROBE):

```
robust implementation
├─ identity pass: Technology      .773
└─ alias pass:    Implementation method .559   → canonical Method

current merge → Technology wins (by raw score) → USES subject illegal
```

## 2. The three separated issues (not one)

1. **Vocabulary dilution** — understood and closed: flat multi-label
   queries are dead (measured); two-pass/per-alias querying is the
   surviving mechanism.
2. **Type arbitration** — the immediate problem: multiple legitimate,
   incompatible type hypotheses for the same span, resolved by an
   invalid rule.
3. **Zero-firing spans** — some bare abstract NPs fire under no tested
   label at 0.5; separate from arbitration; possibly context or
   threshold-calibration territory later.

## 3. Architectural distinction to introduce

```
SPAN DISCOVERY  ≠  TYPE HYPOTHESIS  ≠  CANONICAL TYPE DECISION
```

Today these are collapsed inside `_entity_spans`'s union merge. The
gate separates them:

```
GLiNER identity pass ─────┐
                          │
GLiNER alias pass ────────┼─→ TYPE HYPOTHESIS SET (per span)
                          │       robust implementation:
other qualified passes ───┘       { Technology .773@identity,
                                   Method .559@alias }
                                  ↓
                       INDEPENDENT ARBITRATION
                                  ↓
                     canonical type OR AMBIGUITY
                                  ↓
                     (existing admission / candidate /
                      compiler path unchanged)
```

## 4. Hard constraints (non-negotiable)

- **No predicate-aware arbitration.** The arbitration must not know
  which canonical type would make a USES (or any) slot legal. Choosing
  the type that makes the pending predicate provable is circular and
  manufactures compatibility.
- **No surface-pattern rules.** No `if "implementation" in surface:
  Method`. That is brittle tuning to recover one sentence.
- **Independent of downstream predicate, rescue, and compiler.**
- Frozen: GLiNER model/revision, threshold 0.5, rule pack, rescue
  acceptance semantics, candidate binding, predicate signatures,
  chunking config (per arm), I4 gold/scorer.
- Observability FULL trace required; every arbitration decision
  recorded as a trace event (hypotheses in, decision out, rule fired).

## 5. Candidate arbitration strategies (to be evaluated in dev phase)

All are predicate-blind. Selection happens on development material
before any frozen-I4 comparison:

A. **Alias-pass preference (structural):** when the identity pass and
   an alias pass both fire on a span, prefer the hypothesis whose
   query context had fewer competing labels (the pass with less
   dilution pressure). Rationale: dilution is measured; a score
   surviving a *harder* context may be more trustworthy. Must be
   validated, not assumed.

B. **Calibrated score normalization:** estimate per-context score
   distributions on development material (identity pass vs alias
   pass), normalize scores to a common scale (e.g., per-context
   z-score or rank), then compare. Requires a calibration corpus —
   never tuned on I4/probe-gold outcomes.

C. **Hypothesis retention + deferred decision:** don't arbitrate at
   discovery at all. Carry the full hypothesis set into admission;
   emit MENTION rows per hypothesis (typed differently); let the
   *existing* type-signature machinery surface conflicts as AMBIGUOUS
   (the compiler already abstains on ambiguity — precision-first).
   Candidates form only from unambiguous-typed endpoints. This moves
   arbitration cost downstream but stays predicate-blind because the
   signature check applies uniformly, not to rescue a specific slot.

D. **Disagreement → abstention:** if identity and alias passes disagree
   on canonical type and neither dominates under the chosen rule,
   mark the mention type-ambiguous (mention-only, no candidate
   binding). Conservative; converts wrong typings into misses rather
   than mis-typed facts.

The gate evaluates A–D on dev material (the already-frozen
CHUNKING-V2-QUALIFICATION corpus sentences + experiment-0005 phrase
set — NOT I4), selects ONE strategy (or a composition), then runs the
frozen-I4 comparison once.

## 6. Measurement plan

Dev phase (selection):
- per-arbitration-strategy typing decisions on dev spans with
  before/after hypothesis sets; record every decision + rule fired
- dilution-calibration measurements (score distributions per context)

Frozen phase (single run after selection):
- QUALITY-PROBE before/after: the 8-surface table + key USES sentence
  causal trace (robust implementation: hypotheses → arbitration →
  canonical → slot outcome)
- Frozen I4: TP/FP/FN/P/R vs v1 baseline + first-loss movement +
  rescue refusal rates + unexplained outcomes = 0
- Any correctly-typed-but-signature-rejected endpoints are RECORDED as
  evidence for a later predicate-signature gate (not repaired)

## 7. Success criteria

- Arbitration is predicate-blind (verifiable by inspection + tests)
- Every multi-hypothesis span has a traceable arbitration decision
- No regression on frozen I4 precision; recall movement reported
  honestly whatever direction
- The "robust implementation" case resolves through the chosen rule —
  to Method, to Technology, or to explicit ambiguity — with the rule
  firing recorded, NOT through any rule that references USES, slot
  legality, or the surface string
- Unexplained outcomes = 0

## 8. Sequencing (fits the frozen plan)

```
GLINER-QUERY-VOCAB-v2       DONE — NOT QUALIFIED (merge-rule defect found)
GLINER-TYPE-ARBITRATION-V1  ← THIS GATE (next, pending authorization)
    ↓
re-run quality probe / traces
    ↓
EXTRACTION-CONTEXT-V1       (unchanged position, after arbitration)
    ↓
re-run probe + frozen I4 → observability waterfall
    ↓
predicate-signature changes ONLY for correctly-typed rejections
    ↓
combined I4 → bars → I5 sealed
```

## 9. Explicitly out of scope

- Predicate-signature changes (USES.object_core stays frozen)
- EXTRACTION-CONTEXT-V1
- Threshold changes or calibration-as-default (calibration data may be
  *gathered* in dev phase; no threshold moves)
- Any new model, ontology type, or rescue semantic
- I5
