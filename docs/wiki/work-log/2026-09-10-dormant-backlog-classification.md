---
title: "WORK LOG — dormant backlog classified before any mutation (70 runs / 253 pending / 9 failed)"
change_id: DORMANT-BACKLOG-CLASSIFICATION-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (classification only — nothing requeued, nothing cancelled)
register: 11.197
package: "docs/wiki/plans/DORMANT-BACKLOG-CLASSIFICATION-V1.md"
architecture_impact: "none — read-only."
---

> **Ledger:** owner standing order 2026-09-10 — classify by generation/function/corpus first; no blind requeue,
> no blind cancellation. Register **11.197**.

## Contract

Requested outcome: classify the dormant backlog into valid owed · legacy owed · superseded · held · orphaned.

- **Smallest acceptance:** every one of the 70 runs, 253 pending tickets and 9 failed tickets lands in exactly
  one class, on evidence, with nothing mutated.
- **Owner / public contract:** none changed.
- **Inputs/outputs/persistence:** reads `runs`, `stage_tickets`, `documents`; writes one plan document.
- **Dependency edges:** feeds GAP-4 (control-plane age qualifier) and any future repair slice.
- **Verifier / rollback:** queries are re-runnable; nothing to roll back.

## Changes

- `docs/wiki/plans/DORMANT-BACKLOG-CLASSIFICATION-V1.md` — the classification.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register **11.197**; scaffold TREE.

## Proof

- **Nothing is SUPERSEDED.** Tested, not assumed: joining each open run's `metadata->>'source_name'` against
  `query_ready` runs in the same corpus gives `also_query_ready = 0` for cinema (64) and d7-h1-test (6). These
  are the only runs for their documents, so cancellation would abandon a document.
- **107 of 253 pending tickets are owed to a RETIRING subsystem** — `corpus_summary` 41, `document_summary` 39,
  `parent_summary` 27, which `PRODUCTION-RAG-MIGRATION-CUTOVER-V1` §68 marks STOP WRITER → RETIRE (S15→S17).
  A blanket requeue would spend provider quota producing state scheduled for deletion.
- **`vocabulary` (41) is NOT legacy** — it is read by `candidate_engine.py`, `chat_retrieval.py` and
  `chat_plan.py` (the final core); the cutover plan names corpus-vocabulary as Resolution Lift's precision
  input. Classified VALID OWED.
- **Orphans identified exactly:** the 3 d7-h1-test failed intakes carry
  `LEGACY_EVENT_UNRECOVERABLE intake.v1: missing ['source_name'] after adapter recovery` (attempt 1) — the event
  lacks the field, so no requeue can succeed; they are the same 3 runs that have no document. The 4th orphan is
  the cinema `intake` run (attempt 3 exhausted, no document).
- **Cheapest real repair identified:** 5 `project_qdrant` failures on real cinema documents — local projection,
  zero provider spend.
- `archived_at`/`archived_reason` are `NULL` on all 9 failed tickets — the archive path exists and is unused.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

## Rejected claims

- **"70 open runs means 70 stalled documents; requeue them."** REJECTED — their stage tickets are largely
  `done`; what remains is the tail, and the runs are HELD behind the cinema forensic hold, not stalled.
- **"253 pending tickets are all owed work."** REJECTED — 42% are owed to a subsystem the cutover plan retires.
- **"The failed intakes can be retried."** REJECTED for the 3 d7-h1-test ones — `LEGACY_EVENT_UNRECOVERABLE`
  means the event is missing `source_name`; a retry re-fails deterministically. Archive with a reason instead.
- **"Cancel the orphans now."** REJECTED as MY call — cancellation is a mutation the owner reserved. The
  classification is the deliverable; the disposition is the owner's.

## Open contract gaps

- No mutation performed: the 5 `project_qdrant` repairs, the 4 orphan archivals and the legacy-summary
  cancellation all remain owner-gated.
- The cinema `intake` failure's receipt was not read (only the ticket's `last_error_note`); the actual cause is
  unconfirmed — it is plausibly the near-duplicate refusal of 11.121 (the source name is the Sound Design twin),
  but that is a HYPOTHESIS, not evidence, and is recorded as such.
- No guard asserts "a pending ticket belongs to a non-retiring stage"; this classification is a one-off.
