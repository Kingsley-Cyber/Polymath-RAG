---
change_id: CODEX-HANDOFF-EPOCH-CLOSEOUT
owner: governance
date: 2026-08-26
status: complete
architecture_impact: none (documentation/handoff epoch record)
---

# EPOCH CLOSEOUT — control/performance → G1 → scope → pilot (2026-08-25/26)

## Contract

Final handoff epoch: leave the repository self-describing for an
independent Codex session. Canonical entry:
`NEXT_SESSION_HANDOFF.md` ("POLYMATH — CODEX ENGINEERING HANDOFF").

## Changes

Documentation-only closeout commit. The engineering epoch it records
(commits `4bc430d..a14d5fd`, ~30 commits):

| date | milestone | measured result |
|---|---|---|
| 08-25 | EVENT-ADAPTER dict-cursor fix (4bc430d) | extract/intake crash-loop ended |
| 08-25 | TICK-ARITY + census telemetry (ad81e24) | 1,864 dead ticks ended |
| 08-25 | BULK-RECEIPT-COMPLETENESS (1c872f3) | >100 min tick → 0.23 s phase |
| 08-25 | SCHEDULER-BULK (a56df8e) | schedule_gaps 52 s → 5 s |
| 08-25 | CONTROL/PERFORMANCE GO+FROZEN (4a3086a) | cold seed 3226 s → 100 s; incremental census 0.31 s |
| 08-25 | Stage B/C contracts (c491d64) | actual-behavior retrieval contracts |
| 08-25 | Stage J harness + live run (0ef35d7) | 30/30 cells, behavioral |
| 08-25 | QUERY-SCOPE-V1 (7c9638a) | fail-closed scoping, migration 0035 |
| 08-25 | Stage K pilot (429c5d7) | release-books qualified end-to-end |
| 08-26 | G1 neural cutover QUALIFIED (f121b79) | registry migration 0034; hash 0/9 vs neural 6/9 |
| 08-26 | Pilot stall forensics epoch (4bebc6f…a14d5fd) | creation round-robin, chain-history reconcile, verify DAG keys, payload vocabulary, archive registry (0036), summary-attempt equivalence |
| 08-26 | Modern pilot query_ready | 2/3 real docs (1 corrupt-typed), full waterfall DONE |

## Proof

Bounded suite green at handoff (router/scope/dag/adapter/scheduler/
verdicts/lock/census/starvation/registry ≈70 tests). Fence PASS 13/13
at final HEAD. Evidence reports listed in handoff §20.

## Rejected claims

- FACT yield on narrative pilot material is zero UNDER THE CURRENT
  candidate-discovery path — not a general claim about transcripts.
- Three-mode results are behavioral, not accuracy-judged.

## Open contract gaps

See handoff §16 (transcript qualification is item #1).
