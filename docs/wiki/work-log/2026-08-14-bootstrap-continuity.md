---
change_id: bootstrap-continuity
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none
---

# Bootstrap continuity system

## Contract

A brand-new agent with zero chat history must be able to reconstruct
the repository's operational state, frozen constraints, evaluation
evidence, and next permitted action from repository files alone.

## Changes

- `AGENTS.md`: new §0 Mandatory Bootstrap — mandatory read order
  (AGENTS → CURRENT_STATE → NEXT_SESSION → ARCHITECTURE), the
  "chat history is not authoritative project state" rule, never-assume
  rules, staleness contract, and a where-to-find table.
- `CURRENT_STATE.md`: authoritative state snapshot verified against
  git + artifacts (branch/HEAD, test counts, frozen hashes, evaluation
  verdicts with exact numbers, production-vs-experimental split,
  Stage 1/Stage 2 extraction status, prohibitions, verification
  commands, reference resolution order).
- `NEXT_SESSION.md`: short handoff (last completed, verified commit,
  next authorized E1 experiments, do-not-do list).
- `README.md`: AI Agent Bootstrap pointer.
- Scaffold TREE registers the new files.

## Proof

- Every fact in CURRENT_STATE.md was verified this session: HEAD
  3ada0af on main, clean tree; 77 unit + 12 integration tests green;
  frozen hashes re-computed (fdfd75b4…, 3ee7065a…, 03a513ec…,
  0ac3002a…, 5c58adbd…); guards green.
- New-agent simulation (repository-only walk) answered all 12
  questions without chat context; no bootstrap blockers found.

## Rejected claims

- No production code, schemas, corpora, or defaults were changed.
- No speculative ADRs created; existing ADRs already cover the
  architectural decisions the spec listed.

## Open contract gaps

- Bootstrap files must be re-verified whenever HEAD moves (staleness
  contract in AGENTS.md §0).
