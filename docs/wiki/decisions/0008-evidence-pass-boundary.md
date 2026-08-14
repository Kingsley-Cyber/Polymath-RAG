---
owner: sidecar-gpu
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: accepted
---

# ADR-0008: Restore the GLiNER evidence-pass boundary

## Context

ADR-0007 recorded that the pinned GLiNER medium model produced zero
usable evidence spans (experiment 0001) and replaced the neural
evidence pass with the deterministic lexical lane. Production runs used
`POLYMATH_EVIDENCE_PROPOSAL_MODE=lexical`, which made the lexical lane
*be* pass 2 rather than part of it. The Kimi architecture keeps the two
responsibilities separate:

```text
GLiNER Pass 1 entities → candidate generation
→ GLiNER Pass 2 coarse evidence spans
→ lexical trigger localization
→ UD/voice/scope
→ lexical-semantic lookup
→ predicate compiler
```

## Decision

1. Pass 2 is GLiNER's job: the evidence task proposes coarse evidence
   spans (the 18-class inventory) as linguistic recall BEYOND the
   enumerated trigger vocabulary. On the pinned model it may abstain —
   that is a measured, recorded proposal set, not an error.
2. The lexical lane is trigger LOCALIZATION: deterministic anchors that
   map proposed/visible evidence onto rule-pack triggers. It never
   pretends to be the neural pass.
3. The compiled lexical tables (Phase G) constrain; the compiler
   decides. A GLiNER-proposed span that no rule-pack trigger can
   localize compiles to UNSUPPORTED — neural recall is bounded by the
   curated lexicon, and semantics stay deterministic.
4. `POLYMATH_EVIDENCE_PROPOSAL_MODE`:
   - `lexical` (default today): pass 2 abstains; the lane proposes.
   - `hybrid`: GLiNER proposals merge with lexical anchors; the
     compiler applies the same gates either way.
   A qualified evidence model (per experiment 0001's revisit clause)
   flips the default to `hybrid` — a model release change, gated by
   qualification evidence.

## Consequences

- The two-pass boundary exists structurally even while the pinned pass-2
  model abstains: switching to hybrid is configuration + qualification,
  not re-architecture.
- The invariant is unchanged: GLiNER proposes, resources constrain, the
  compiler decides. Silence is valid.
