# SR1 Span-Repair Report

Status: FROZEN
Date: 2026-08-14
Outcome: **FAIL on the dev promotion bar — held-out preserved**

## Baseline reference (EM1 clean contract, medium-v2.1)

| metric @0.45 | baseline |
|---|---|
| overlap recall | 0.356 |
| multiword recall | 0.449 |
| type accuracy | 0.824 |

## Implementation

`shared/polymath_shared/span_repair.py` — `bounded-span-repair-v1`:
candidate lattice (±2 tokens), max 3 words, head-preserving, hard
boundary rules (BOUNDARY_STOP verb/prep/conj/determiner classes, no
punctuation/sentence/timestamp/speaker crossing), left expansions
accepted for modifier-like tokens, right expansions restricted to
plural-noun-like tokens and opt-in (`allow_right`) because plural
nouns are not deterministically separable from 3rd-person verbs
("events" vs "shifts"); provenance preserved (raw span + rule +
version); deterministic (verified every run).

Arms:
- SR1-A = deterministic left-only repair (precision-first default)
- SR1-B = full lattice gated by a local GLiNER score check

## Dev measurement (frozen artifacts in eval/sr1/artifacts/)

| Arm @thr | overlap R | mw R | type acc | false | exact P | repairs (correct/incorrect) |
|---|---|---|---|---|---|---|
| baseline @0.30 | 0.452 | 0.551 | 0.734 | 0.367 | 0.102 | — |
| SR1-A @0.30 | 0.519 | 0.627 | 0.759 | 0.473 | 0.405 | 22 (1/21) |
| SR1-A @0.35 | 0.442 | 0.551 | 0.793 | 0.477 | 0.409 | 20 (1/19) |
| SR1-A @0.40 | 0.413 | 0.517 | 0.826 | 0.423 | 0.450 | 18 (1/17) |
| SR1-A @0.45 | 0.380 | 0.466 | 0.835 | 0.383 | 0.477 | 17 (1/16) |
| SR1-B @0.45 | 0.356 | 0.441 | 0.824 | 0.393 | 0.508 | 32 (1/31) |

Promotion bar: overlap ≥ 0.50 AND multiword ≥ 0.60 AND type accuracy
≈ ≥ 0.80 AND false-span not materially worse. No configuration clears
the bar: the only recall-qualifying operating points (0.30–0.35) sit
at type accuracy 0.76–0.79 and false-span +0.10–0.11 worse than
baseline. The precision-first secondary path also fails (false-span
+8 pts even at 0.40).

## Why repair cannot reach the bar (measured, not hypothesized)

Repair is bounded by the brief's principle: it may only improve the
boundary of a span GLiNER already detected. Two span classes dominate
the remaining misses:

1. **Unseeded multiword mentions**: gold phrases where GLiNER medium
   proposes NO token inside at usable thresholds ("cognitive load" —
   no "load" proposal; "sleep deprivation" — no "deprivation"
   proposal). Repair cannot invent them by design.
2. **Low-threshold seeds**: bare heads appear mainly below 0.45,
   where core-type accuracy collapses (0.73–0.76) and false spans
   flood (+0.10–0.11). Repairing them trades the precision the whole
   stack depends on.
3. Right-side compounds ("outbox events") are dropped by the
   deterministic grammar (plural-noun vs 3rd-person verb ambiguity);
   the SR1-B local score gate did not recover them safely.

## Held-out

`heldout_ep1_v1` was NOT run and remains untouched.

## Verdict

SR1 FAIL on the dev bar. Per the SR1 brief: do not train a model now;
record the unrecoverable span classes (above) and return for a new
architecture decision. Production remains gliner_medium-v2.1 @
40ec4193, rule pack 1.0.1, no repair enabled. I1 remains BLOCKED.
