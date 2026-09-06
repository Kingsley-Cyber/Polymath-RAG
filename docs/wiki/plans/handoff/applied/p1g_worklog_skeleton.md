---
title: "WORK LOG — P1.g conversation regression suite: the §5 fixtures, the owner's exact thread and every measured gate, frozen and checkable"
change_id: CHAT-REGRESSION-SUITE-V1
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P1.g)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.97
package: eval/fixtures/chat_regression_suite.json, tests/determinism/test_chat_regression_suite.py, scripts/chat_baseline.py
architecture_impact: "A frozen manifest (`eval/fixtures/chat_regression_suite.json`) names every conversation fixture (including the owner's exact video-gen thread) with its expectations, every baseline set (B, L, M) with the gate thresholds measured in P1.a–P1.c, the carry probe's law and the latency rules. `tests/determinism/test_chat_regression_suite.py` runs in CI (determinism.yml already runs the directory): manifest integrity, fixture presence and shape, the deterministic correction layer's guarantees per fixture, and the `--check` evaluator; its live part (`-k live`) replays every conversation through the runtime against its expectations. `scripts/chat_baseline.py --check B|L|M:<tag>` turns any measured run into a pass/fail against the frozen gates (exit 1 on regression)."
---

# WORK LOG — P1.g conversation regression suite

Plan gate (ledger row, read from disk): *suite in CI (determinism.yml).*

## Contract

CONTRACT_BLOCK

## Changes

CHANGES_BLOCK

## Proof

PROOF_BLOCK

## Rejected claims

REJECTED_BLOCK

## Open contract gaps

GAPS_BLOCK
