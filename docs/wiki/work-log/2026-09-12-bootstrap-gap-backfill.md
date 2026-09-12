---
title: "WORK LOG — bootstrap gap analysis: 3 missing register rows, a polluted attempt ledger, a gate that closed itself"
change_id: BOOTSTRAP-GAP-BACKFILL-2026-09-12
date: 2026-09-12
owner: governance
last_reviewed: 2026-09-12
status: complete (ledger reconciled to reality; one defect fixed)
register: 11.205, 11.208, 11.210
architecture_impact: "none — ledger backfill plus test isolation for the attempt recorder. No production behaviour changed."
---

> **Ledger:** `/polymath-bootstrap` Step 3b. Repository state is the authority; this slice
> reconciles the ledger to it.

## Contract

- **Smallest acceptance:** every unpushed/recent mutation is represented in the register, the CONTINUITY
  checkpoint matches live reality, and no accounting surface carries fabricated data.
- **Owner / public contract:** unchanged.
- **Verifier / rollback:** register monotonicity check + a ledger-growth assertion; `git revert`.

## Changes

- `PLAN-AUTHORITY-REGISTER.md` — rows **11.205** (D-1 terminal-state classifier) and **11.208** (F12 E2E)
  appended; both were CITED by work-logs on disk but never existed. Row **11.210** records four mutations that
  shipped with neither work-log nor register row (`b8351f9`, `844432c`, `4b5143e`, `df41d67`).
- `tests/conftest.py` — sets `POLYMATH_ATTEMPT_LEDGER=0` for the whole test session.
- `llm_provider_attempts` — 2 fabricated rows purged (pinned by primary key).

## Proof

- **Register drift, measured:** `grep '^| 11\.2'` returned `…202, 203, 204, 206, 207, 209` — **205 and 208
  absent**, while `2026-09-11-d1-terminal-state-classifier.md` and `2026-09-11-f12-e2e-and-fixes.md` both
  declare those numbers in frontmatter. The commits carrying those work-logs (`b91f5de`, `2eda3dd`) show
  `reg=0`. After backfill the sequence is contiguous `11.200 … 11.210`.
- **Attempt-ledger pollution, found and fixed:** the ledger held 2 rows for lanes `cp_success` / `cp_refused`,
  which exist in NO configured topology — unit tests exercising `complete_one` with fake lanes were writing to
  the production ledger, because the recorder fires whenever `POLYMATH_PG_DSN` is set and the test suite runs
  against the dev database. `POLYMATH_ATTEMPT_LEDGER=0` in `conftest.py` closes it; verified by running the
  limiter/controller suites with the row count unchanged at 2 before and after. The 2 rows were then purged by
  primary key, selected by "lane not present in any configured topology" rather than by name.
- **A gate closed itself:** the previous checkpoint recorded *runtime bundle NOT uniform (3 hashes), bounce
  due*. Live now: ONE bundle `83d3fd1298cf8394`, `bundle_integrity` READY, 17 workers healthy. The supervisor
  restarted the workers onto current code on its own, so no bounce is owed.
- **D-1 proven live, independently of its own tests:** cinema batches in the last hour include a terminal
  `HTTP_429`. Before D-1 a dispatched 429 could be relabelled `LIMITER_REFUSED`; it is now booked as what it is.
- **Cinema is genuinely paused:** 36 done / 12 pending / **0 ready / 0 leased**, no claimable ticket anywhere,
  last provider call 23:59:13 against a bootstrap at 00:23 — 24 minutes of silence. Maps static at 5,668.

## Rejected claims

- **"The fleet needs a bounce."** REJECTED on measurement — the checkpoint said so, the live bundle says
  otherwise. The repo is the authority over my own previous note.
- **"The 4 pMAP workers running means cinema resumed."** REJECTED — they were restarted by the supervisor and
  hold no claimable work; the ticket census and 24 minutes of provider silence prove it.
- **"Leave the 2 ledger rows; they are harmless."** REJECTED — a reconciliation surface containing invented
  attempts is worse than an empty one, because every future `attempts.reconcile()` would quietly include them.
- **"Write retrospective work-logs for the four uncovered commits."** REJECTED — inventing a contemporaneous
  record after the fact is fabrication. The discipline miss is recorded in 11.210 instead.

## Open contract gaps

- Four mutations shipped without work-logs; that is now recorded, not repaired.
- The attempt ledger is empty (0 rows) because the only real traffic predates the recorder. It has not yet
  observed a live provider attempt — `attempts.reconcile()` is therefore unexercised against real data.
- Conformance L2–L5 remain unbuilt; 47 components remain `NOT_TESTED`.
