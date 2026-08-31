---
change_id: CENSUS-WEDGE-RESTORATION-V1
owner: control-plane
date: 2026-08-31
status: complete
architecture_impact: control (tickets sweep guard, census + bulk want-sets children-only) + one-off run surgery (successors parked, originals re-pinned); corpus back to query_ready with latent live
last_reviewed: 2026-08-31
---

# WORK LOG — CENSUS-WEDGE-RESTORATION-V1 (three wedges, one outage, service restored)

## Contract
The corpus went user-visibly `corpus_not_ready` after latent projection.
Root-caused and fixed THREE stacked wedges; retrieval restored with the
latent layer live on the full corpus.

## Changes — the three wedges (all measured)
1. **Census killed by the DAG-less stage**: `advance_tickets` swept the
   owner-triggered parent_enrichment ticket and `_STAGE_SPEC[stage]`
   KeyError'd — the WHOLE advancement phase dead since 05:18, every
   corpus frozen mid-chain. Fix: unknown stages skip the sweep (they
   mint their own events at the button).
2. **1C successor carry-gap**: CONTRACT-RECONCILIATION minted successor
   runs for the era drift, but ticket advancement reads stage artifacts
   PER-RUN — carried-done stages have no artifact rows under the
   successor, so its chain can never become ready. Parked both
   successors (tickets superseded, runs superseded, reason recorded),
   re-pinned the verified-complete ORIGINAL runs to the current
   contract (§0b: mixed-era is legal; receipts/attempts carry truth),
   restored their qdrant tickets from 'superseded' to 'done'.
3. **The F6 want-set had THREE copies**: verify._desired_chunk_ids was
   fixed with F6, but census._missing_projection_receipts AND
   tickets._corpora_with_missing_chunk_receipts still wanted parent
   chunk receipts — "65 projection receipts missing" (exactly the
   retired parents) plus a corpus-wide barrier block kept every run at
   reconciling forever. Both now children-only for qdrant (neo4j
   untouched).

## Proof
- compute_census by hand after fixes: promote=[both runs], gaps=[],
  barrier passed → live census promoted; corpus `query_ready`.
- Full-corpus reach probe (AWS content): 3 latent parents (abstraction
  + transfer channels), 8 original children admitted, degraded None.
- P6 re-run over the FULL enriched corpus: attribution abstraction=12,
  transfer alive; results file refreshed.

## Rejected claims
- "Fix the 1C carry-gap properly tonight" — deferred, not rejected:
  artifact-lineage-aware advancement is the real fix and belongs to the
  reconciler's owner; a task chip records it. Service first.

## Open contract gaps
- 1C successor runs cannot progress on carried stages (artifact rows
  are per-run) — reconciler needs lineage-following artifact checks
  before the next fleet-wide contract drift on a large corpus.
- The want-set is now children-only in THREE places; a shared
  `desired_chunk_ids(conn, scope)` helper would end the copy drift.
