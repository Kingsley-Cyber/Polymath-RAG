---
title: "DORMANT BACKLOG CLASSIFICATION — 70 open runs / 253 pending tickets / 9 failed, classified before any mutation"
change_id: DORMANT-BACKLOG-CLASSIFICATION-V1
owner: governance
date: 2026-09-10
last_reviewed: 2026-09-10
status: complete (classification); NOTHING requeued, NOTHING cancelled
architecture_impact: "none — read-only classification. Owner standing order 2026-09-10: classify by generation/function/corpus BEFORE any requeue or cancellation."
register: 11.197
---

# Dormant backlog — classified, not swept

Owner order (2026-09-10): *"Do NOT status-sweep or bulk-mutate… First classify them… valid owed work ·
legacy owed work · superseded · held · orphaned. No blind requeue. No blind cancellation."*

**Nothing was mutated.** Every number is a read against durable state at 2026-09-10T21:00.

## 1. The 70 "open" runs (`status IN ('intake','reconciling','degraded')`)

| corpus | status | runs | oldest → newest | classification |
|---|---|---|---|---|
| cinema | `reconciling` | 63 | 2026-09-05 → 09-07 | **HELD** — 63 real documents; blocked behind the cinema forensic hold (pMAP under-coverage), not stalled workers |
| cinema | `intake` | 1 | 2026-09-07 | **ORPHANED** — no document; its intake ticket failed at attempt 3 |
| d7-h1-test | `reconciling` | 6 | 2026-09-04 → 09-05 | 3 **HELD** (documents exist, test corpus) · 3 **ORPHANED** (no document, no `source_name`) |

**None is SUPERSEDED.** Tested directly: no open run's `source_name` has a `query_ready` twin in the same
corpus (`also_query_ready = 0` for both corpora). These runs are the *only* runs for their documents —
cancelling them would abandon the document, not tidy a duplicate.

Their stage tickets are overwhelmingly `done` (intake/extract/doc_profile/profile_document/parent_enrichment
66 each; canonicalize/project_neo4j/project_qdrant 61; project_canonical 49; compile_objects/parent_summary/
verify_projections 43). The pipeline got most of the way; what is pending is the tail.

## 2. The 253 `pending` tickets — the decisive split

| bucket | tickets | stages | classification | why it matters |
|---|---|---|---|---|
| **legacy summary subsystem** | **107** | `corpus_summary` 41 · `document_summary` 39 · `parent_summary` 27 | **LEGACY OWED — retirement-bound** | `PRODUCTION-RAG-MIGRATION-CUTOVER-V1` §68 marks the legacy summary worker + `summary_jobs`/`parent_summaries`/`document_summaries`/`corpus_summaries` as **STOP WRITER → RETIRE** (S15→S17). **Requeuing these spends provider quota producing state the cutover plan schedules for deletion.** |
| **vocabulary** | **41** | `vocabulary` | **VALID OWED** | `vocabulary` is read by the FINAL core — `candidate_engine.py`, `chat_retrieval.py`, `chat_plan.py`; the cutover plan names corpus-vocabulary as Resolution Lift's precision input. This is live-path work. |
| **final pipeline tail** | **105** | `verify_projections` 27 · `compile_objects` 27 · `project_canonical` 21 · `project_neo4j` 9 · `canonicalize` 9 · `profile_document` 4 · `project_qdrant` 4 · `extract` 4 | **VALID OWED** | final-path stages on real documents |

**The headline: 107 of 253 pending tickets (42%) are owed to a subsystem being retired.** A blanket requeue
would spend real provider quota on them. That is precisely the outcome the owner's "no blind requeue" order
prevents.

## 3. The 9 `failed` tickets

| corpus | stage | n | recorded reason | classification |
|---|---|---|---|---|
| d7-h1-test | `intake` | 3 | `LEGACY_EVENT_UNRECOVERABLE intake.v1: missing ['source_name'] after adapter recovery` (attempt 1) | **ORPHANED — unrepairable by design.** The event lacks the field; a requeue cannot succeed. These are the 3 orphan d7-h1-test runs in §1. |
| cinema | `intake` | 1 | failure receipt committed, attempt 3 exhausted | **ORPHANED** — the cinema open `intake` run in §1 (source `Sound Design The Expressive Power of Music, Voi…`). Attempts exhausted; needs the receipt read before any retry decision. |
| cinema | `project_qdrant` | 5 | failure receipt committed, attempt 3 exhausted | **VALID OWED** — projection failures on real cinema documents; repairable, and the cheapest real work in the backlog (local Qdrant, no provider spend). |

## 4. Recommended disposition (owner decides — nothing done)

1. **Do nothing to the 107 legacy-summary tickets** until the cutover's STOP WRITER decision (S15) lands. Then
   they are cancelled *as part of retirement*, not requeued.
2. **The 5 `project_qdrant` failures are the safe first repair** — local projection, zero provider spend,
   pinned by ticket id.
3. **The 41 `vocabulary` + 105 tail tickets are genuine owed work**, but they belong to cinema runs that are
   HELD behind the forensic hold. They unblock with cinema, not before.
4. **The 4 orphaned intakes** (3 unrecoverable + 1 exhausted) should be archived with a reason, not retried —
   `stage_tickets.archived_at`/`archived_reason` exist for exactly this and are currently unused (`NULL` on all 9).
5. **Never by status sweep.** Every action above is pinned by ticket id or batch id (MEDIC SCOPING LAW: stale
   batches wake up).

## 4b. Re-classified under the owner's five-way taxonomy (2026-09-10, after U-2 CLEARED)

`U-2 FORENSIC HOLD: CLEARED` changes one class: cinema's runs are no longer FORENSICALLY HELD. They become
CURRENT OWED WORK awaiting bounded resumption — the work is real, permitted and simply not done yet.

| class | runs | stage tickets | pMAP batches | what it means |
|---|---|---|---|---|
| **CURRENT OWED WORK** | **66** (cinema 63 + d7-h1-test 3) | **146** pending on final-path stages — `vocabulary` 41 · `verify_projections` 27 · `compile_objects` 27 · `project_canonical` 21 · `project_neo4j` 9 · `canonicalize` 9 · `profile_document` 4 · `project_qdrant` 4 · `extract` 4 — plus **5 failed** `project_qdrant` (cinema) | **6 frozen** on expired leases (D-2), holding **90 parents** | real work on the live path; unblocks with cinema resumption. The 5 `project_qdrant` failures are the cheapest repair in the backlog (local projection, zero provider spend). |
| **LEGACY OWED WORK** | — | **107** — `corpus_summary` 41 · `document_summary` 39 · `parent_summary` 27 | — | owed to the summary subsystem the cutover marks **STOP WRITER → RETIRE** (S15→S17). **Requeuing spends provider quota building state scheduled for deletion.** Cancel these AS retirement, never requeue. |
| **SUPERSEDED** | **0** | 122 (already terminal) | 122 batch rows | **No open run is superseded** — tested: no open run's `source_name` has a `query_ready` twin, so each is the only run for its document and cancelling one abandons the document. |
| **FORENSICALLY HELD** | **0** *(was 66)* | 0 | 0 | Emptied by `U-2 FORENSIC HOLD: CLEARED` (register 11.204). |
| **ORPHANED** | **4** (1 cinema `intake` + 3 d7-h1-test) | **4 failed** `intake` | — | The 3 d7-h1-test ones are unrepairable BY DESIGN — `LEGACY_EVENT_UNRECOVERABLE intake.v1: missing ['source_name']`; a retry re-fails deterministically. Archive with a reason; do not retry. |

**Totals:** 70 open runs = 66 current-owed + 4 orphaned. 253 pending tickets = 146 current-owed + 107
legacy-owed. 9 failed = 5 current-owed (repairable) + 4 orphaned. Still **nothing requeued, nothing
cancelled, nothing swept.**

**The 282 "open stalls" on `/health/pipeline` are this same backlog seen from the health surface**
(`PENDING_ON_PREDECESSOR×221` + `PENDING_ADVANCE_BLOCKED×32` + `RUN_SETTLED_NOT_PROMOTED×29`), with 0 queued
tickets and 0 blocked workers. The V2 Control Plane renders that distinction explicitly (register 11.203)
rather than presenting dormant records as current pipeline failure.

## 5. Cross-reference

- GAP-4 in `FRONTEND-V2-CONTRACT-INVENTORY-V1` depends on this: `control_plane.summary.processing` counts these
  70 runs with no age qualifier, so cinema renders `processing: 64` for runs last touched 2026-09-07. The fix
  needs the live/dormant boundary that this classification supplies.
- The 6 pMAP batches frozen on expired leases (D-2 in `U2-FORENSIC-CLOSURE-AUDIT-V1`, 90 parents) are a
  SEPARATE frozen set, not counted above — they live in `document_parent_map_batches`, not `stage_tickets`.
