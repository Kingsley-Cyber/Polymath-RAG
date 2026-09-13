---
title: "WORK LOG — RAG-finish Phase 17 (read-only dry-run) + Phase B assessment — both OWNER-GATED"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (read-only reconciliation + gate documentation; NO backfill, NO spend, NO cutover)
last_reviewed: 2026-09-09
status: complete (read-only prep) — resume + Phase B remain OWNER-GATED
register: 11.198 (pending)
package: docs/wiki/work-log/2026-09-09-rag-finish-phase17-reconciliation-dryrun.md
architecture_impact: "None. Read-only reconciliation dry-run for the held cinema corpus + explicit statement of the owner-gated unblocks for Phase 17 (existing-corpus backfill) and Phase B (doc_profile DAG reorder). No provider quota spent, no writes, no cutover, forensic hold intact."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 17** (existing-corpus reconciliation) + **PHASE B**
> (doc_profile DAG reorder) + register **11.198**. The 2026-09-08/09 Groq forensic HOLD remains active.

## Contract

Do NOT resume cinema/existing-corpus backfill while the forensic hold is active. Perform every read-only
reconciliation/diagnostic/preparation step and leave the exact owner-gated unblock explicit. Resolve Phase B
only if repository authority permits it without violating migration/cutover gates; otherwise leave it
explicitly owner-gated.

## Phase 17 — read-only reconciliation dry-run (cinema)

`scripts/vnext_readiness_report.py --corpus cinema --json` (read-only Postgres; no models, no writes, no
network):

| metric | value |
|---|---|
| total_documents | 67 |
| documents_by_state | NOT_STARTED 28 · MAP_PARTIAL 25 · MAP_COMPLETE 14 |
| vnext_maps_complete_documents | 14 |
| parents.eligible | 11,993 |
| parents.mapped | 1,449 |
| parents.excluded | 368 |
| **parents.unresolved** | **10,176** |
| map_batches | done 121 · partial 937 · leased 6 (stale leases from the stopped backfill) |
| map_contract on existing maps | `map-compiler-v1` (UNGROUNDED — map-prompt-v1 era, NOT the grounded generation) |
| profiles (vNext) | regenerated 67/67 earlier (11.169); the profile scale is current |

**Interpretation:** cinema's pMAP scale is ~12% complete and its existing 1,449 maps predate Phase 6
grounding (they are `map-prompt-v1` skeleton-only). Under the fresh-doc pipeline's grounded generation
(`map-prompt-v2` + grounding_hash in batch identity), those maps are a DIFFERENT generation. The 6 leased
batches are stale (the stopped backfill's leases) and expire/reap on their own — left untouched (no writes
under the hold).

## The exact owner-gated unblock (Phase 17)

1. **Forensic hold's bounded Groq quota-topology probe** (owner-authorized, SPENDS a tiny provider budget) —
   the gate item recorded in 11.185 / `docs/wiki/reports/2026-09-09/07_NEXT_ACTION.md`. Not run here.
2. **A generation decision** (owner + migration authority), because cinema's maps are ungrounded:
   - (a) resume the EXISTING ungrounded generation — map only the 10,176 unresolved parents under
     `map-compiler-v1` (≈ 10,176/15 ≈ **~680 pMAP calls owed**), keeping the 1,449 as-is; OR
   - (b) RE-MAP cinema under the grounded generation — all 11,993 eligible (≈ **~800 pMAP calls**), which
     supersedes the 937 partial batches + 1,449 ungrounded maps (a new batch identity). This is the
     current-generation-scoping choice (§4.2 "old contracts never satisfy current-generation completion").
   Either path uses `scripts/parent_map_backfill.py --corpus cinema --project`; **path (b) also needs the
   backfill's infer closure upgraded to build `DocumentGroundingContextV1`** (currently it passes
   `grounding=None`) — a small offline code change deferred until the owner picks the generation, so the
   resume produces exactly the intended generation.
3. Then a bounded owner-reviewed canary on cinema, then the resume; the pool-drain + conservation
   instrumentation (11.185) + the auto-minted PMAP pool make this drain across the six Groq accounts.

**DO NOT resume the backfill on a quota reset.** The hold's probe + the generation decision are prerequisites.

## Phase B — doc_profile DAG reorder — OWNER-GATED (not resolved here)

The DOCUMENT-PROFILE "Phase B" moves `doc_profile` ahead of `verify_projections` in STAGE_DAG so legacy
`QUERY_READY` REQUIRES the profile. That changes the frozen STAGE_DAG **and** the legacy `query_ready`
completion contract for EVERY corpus (a cutover-affecting change) — it violates the migration/cutover gate
without explicit authority, so it is **left owner-gated**. The fresh-doc canary's need is already met by the
scoped **doc_profile-early** emit (8366b0b), which produces the vNext profile in parallel WITHOUT touching
STAGE_DAG or `query_ready`. When the owner authorizes the cutover, Phase B is the reorder + dropping
`doc_profile` from `NON_BLOCKING_STAGES`.

## Changes

None to code/schema/runtime. This is a read-only reconciliation dry-run + explicit documentation of the
owner-gated unblocks for Phase 17 and Phase B. The only artifact is this work-log.

## Proof

- Dry-run counts above are from the read-only report; no writes, no provider call.
- Forensic hold intact: no backfill run, no cinema map/profile regenerated, no leases touched.

## Rejected claims

- **NOT resumed** — no cinema backfill, no spend, no cutover. The unblock is explicitly the owner's probe +
  generation decision.
- **Phase B NOT implemented** — it is a cutover-gated STAGE_DAG + query_ready change; the scoped early-mint
  covers the fresh-doc path without it.

## Open contract gaps

- All owner-gated: the bounded Groq probe, the cinema generation decision (+ the backfill grounding upgrade
  for path b), and the Phase B cutover.
