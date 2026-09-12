---
title: "WORK LOG — auditing the verifier for gates that could PASS on nothing"
change_id: VERIFIER-VACUITY-AUDIT-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.243
architecture_impact: "three gates in verify_final_state.py now require positive evidence that the thing was observed, not merely that no violation was seen. No behaviour outside the verifier."
---

> 11.240 found tests that hid failures behind skips. The same question applies with more
> force to the one command that certifies the whole REQUIRED FINAL STATE: can any of its
> gates pass on nothing?

## Contract

§18: a status must mean what it says, and `NOT_TESTED` is never green. A PASS that a
scan-of-nothing also produces is a `NOT_TESTED` wearing a PASS.

## Changes

**First, the worst shape — checked and clean.** An AST walk over every `gate(...)` call
confirms **no gate reports PASS from inside an exception handler**: all 13 gate calls
within `except` blocks report `NOT_TESTED` (12) or `FAIL` (1). The command that certifies
everything cannot certify an error.

**Then the subtler shape: a verdict that an empty input satisfies.** Checking every PASS
line's detail for positive numeric evidence flagged nine; six carry substantive
non-numeric evidence (actual mode values, the real `cache-control` header, the real
shas, a subprocess `rc`). Three were genuinely vacuous:

| gate | what it tested | what an empty input did |
|---|---|---|
| `retrieval_truthful_mode` | requested and executed modes do not CONFLICT | a response carrying **no mode metadata at all** passed — it could not tell "reported the right mode" from "reported nothing" |
| `outbox_corpus_scoped` | no `Seq Scan on outbox_events` | trivially true of a plan that never touched the table — a corpus with **zero documents** certified an index path it never used |
| `hot_path_no_toast_detoast` | the plan mentions no `payload`/TOAST | trivially true of an **empty plan** |

Each now requires positive evidence: an executed mode must be PRESENT and equal, and all
three modes must have answered; the outbox plan must actually mention `outbox_events` and
the corpus must have documents; the graph plan must carry an `Execution Time` line.

All three still PASS live — they were reporting truthfully, they simply could not have
detected the vacuous case.

## Proof

`tests/determinism/test_verifier_not_vacuous.py`, 6 tests: each gate is fed its vacuous
input and must FAIL (a response with no executed mode; a corpus with zero doc_ids; an
empty plan), and fed a real input and must PASS — so the strictness cannot be satisfied
by failing everything. Plus the AST invariant, pinned as a test so a future
`gate(..., PASS)` inside an `except` fails the suite.

## Rejected claims

- **"All nine flagged gates are vacuous."** Rejected on reading each: a gate whose detail
  is `HEAD=… upstream=… unpushed=0` or a literal `cache-control` header carries its
  evidence in a non-numeric form. The heuristic selected candidates; inspection decided.
- **"They pass now, so it does not matter."** Rejected: the gates pass because the system
  is healthy. The point of a gate is what it does when the system is not.

## Open contract gaps

- **`repo_guard.py` was then examined and is sound** — a negative result, recorded so the
  next reader does not repeat it. Its central check is a TWO-WAY diff
  (`declared - actual` and `actual - declared`), so neither an empty scaffold TREE nor an
  empty file scan can pass: each direction turns the other's emptiness into a loud list
  of errors. `check_dependencies` fails explicitly on unreadable JSON and on an empty
  `owners` map, and the work-log check reports `invalid front matter` rather than
  skipping a file it could not parse. Six `except` handlers, none of which return a
  success.
- `retire_claim_sets.py` / `retire_pronoun_facts.py` were NOT examined for the same
  shape. Both are owner-gated at the point of execution, so a vacuous "nothing to do"
  would be visible before anything irreversible happened — but that is an argument for
  lower priority, not for soundness.
