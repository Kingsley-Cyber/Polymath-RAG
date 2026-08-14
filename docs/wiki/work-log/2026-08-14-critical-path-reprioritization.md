---
change_id: critical-path-reprioritization
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none
---

# Reprioritize: RAG v1.0 application E2E is the critical path

## Contract

Move the release-gate ordering from extraction improvement (E1) to the
unfinished application path: answer/evidence assembly, /chat,
canonicalization, MCP, scale, operations, acceptance. Record the new
sequence in the checklist and bootstrap state without changing any
production code, frozen corpus, or default.

## Changes

- `RAG_E2E_CHECKLIST.md`: critical path R3a → R3b → C1 → C2 → R2 →
  M1–M5 → R4 → O2 → O1 → A1 → V1; R2 marked bypassable for the first
  /chat E2E; E1-a/E1-b/D1 moved to "Deferred measured improvement".
- `CURRENT_STATE.md`: yaml next_actions updated; Retrieval State,
  Open Risks, Current Workstream, Next Authorized Actions, deferred-
  improvement section, and checklist reference updated.
- `NEXT_SESSION.md`: new-agent instruction (do NOT begin E1; critical
  path first), remote blocker marked resolved, Docker approval ledger.
- `AGENTS.md` §2: new rule 10 — never prune Docker volumes or delete
  bind-mounted store data without explicit approval.
- Docker cleanup (user-approved only): build cache pruned (20.76GB),
  dangling image `b5c028faaade` removed, five OOM-killed v3.3 worker
  containers removed AFTER preserving `docker inspect`/log evidence to
  `~/repo-backups/oom-evidence-2026-08-14/`. No volumes touched.

## Proof

- `make guards` green (preflight, repo guard, wiki worm) after edits.
- 77 unit tests passed / 15 skipped; 12 integration passed / 2 skipped.
- Docker: build cache 32.63GB → 11.88GB; volumes byte-identical
  (81.81GB, 26 volumes, all links unchanged).
- Frozen hashes re-verified: fdfd75b4…, 3ee7065a…, 03a513ec…,
  0ac3002a…, 5c58adbd….

## Rejected claims

- No production code, schema, corpus, or default changed.
- E1 is not deleted: it remains a frozen, deferred measured-improvement
  gate with an explicit re-entry condition (E2E acceptance failure on
  the lexical path).

## Open contract gaps

- None introduced. Critical path work starts at R3a.
