---
change_id: sr1-span-repair
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (candidate module not wired into production)
---

# SR1: bounded deterministic span repair

## Contract

Keep GLiNER medium-v2.1 and repair incomplete multiword spans with
cheap deterministic Python logic. GLiNER stays the semantic detector;
repair only improves boundaries of spans GLiNER already proposed.
Precision-first; dev promotion bar overlap ≥0.50 / multiword ≥0.60
with type accuracy ≈ ≥0.80 and false-span safety; held-out stays
untouched unless the dev bar clears.

## Changes

- `shared/polymath_shared/span_repair.py` (new, candidate module —
  NOT wired into production): bounded-span-repair-v1, lattice ±2
  tokens, max 3 words, head-preserving, BOUNDARY_STOP word classes,
  left-only default, opt-in right expansion, full provenance.
- `eval/sr1/qualify_sr1.py` (new): SR1-A / SR1-B arms over the EM1
  clean contract with repair confusion reporting.
- Frozen artifacts + `eval/sr1/REPORT_SR1.md`.

## Proof

- Dev grid: no configuration clears the bar. Best recall point
  SR1-A @0.30 (overlap 0.519, mw 0.627) sits at type accuracy 0.759
  and false-span 0.473 (+0.106 vs baseline). Precision-first points
  (0.40–0.45) gain little (overlap ≤0.413).
- Unrecoverable span classes measured: (1) unseeded multiword
  mentions (GLiNER proposes nothing inside at usable thresholds);
  (2) low-threshold seeds with collapsed type accuracy; (3)
  right-side compounds blocked by the noun/verb ambiguity.
- Determinism verified on every run. Held-out untouched.

## Rejected claims

- No model training/switch; no compiler/signature/scope/threshold
  change; no held-out consumption; no production wiring of repair.

## Open contract gaps

- SR1 FAIL. I1 remains BLOCKED. Escalation per the brief: record the
  unrecoverable span classes and return for a new architecture
  decision (no immediate training).
