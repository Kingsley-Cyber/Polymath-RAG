---
title: "WORK LOG — parent-MAP projection canary: reconciliation + purge/rebuild (step 4)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-PARENTMAP-PROJECTION
date: 2026-09-07
owner: worker (projection of the cohort's maps)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.151
package: scripts/parent_map_projection_canary.py, docs/wiki/experiments/parent-map-projection-canary-2026-09-07.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "Projects the step-3 cohort's active 0054 maps to the contract-scoped parent-map Qdrant collection (polymath_document_parent_maps_<embedding contract>, additive — never the chunk/profile/summary collections) via parent_map_projection (S10) + the embedder, and verifies the §14 reconciliation gate (Postgres active-map count == projected point count) + purge/rebuild. Owner-authorized Qdrant projection, bounded to the cohort. No chunks/profiles/retrieval-readers touched."
---

# WORK LOG — parent-MAP projection canary (step 4)

## Contract

Owner /goal step 4: "Wire embedder + contract-scoped Qdrant collection + projection
receipts. Verify Postgres authoritative count == projected active-map count. Verify
purge/rebuild handling before broader generation." The §14 projection gate.

Owner: `worker`. Verifier: `scripts/parent_map_projection_canary.py` (exit 0 = PASS) +
S10's determinism suite (`test_parent_map_projection`). Rollback: `--purge-only`.

## Changes

- **`scripts/parent_map_projection_canary.py`** (new): loads each cohort doc's ACTIVE
  0054 maps, reconstructs `CompiledMap`s, builds the skeleton manifest from the parents,
  projects via `parent_map_projection.project_parent_maps` (embedder + Qdrant), then
  reconciles (`PMP.reconcile`: Postgres count == projected count) and exercises
  purge→0→rebuild→restored. `--purge-only` rolls back.
- **experiment JSON**, **scripts/README** row, **TREE** line, this work-log.

## Proof (LIVE, dev fleet)

```
set -a; . ./.env; set +a
.venv/bin/python scripts/parent_map_projection_canary.py --corpus cinema --docs 3 \
   --out docs/wiki/experiments/parent-map-projection-canary-2026-09-07.json   -> PASS
```

Collection `polymath_document_parent_maps_embed_e794ec4cab197a3f`: Circumplex 20 maps →
20 points, Multistage 11 → 11, Affective Movement 19 → 19 — **reconcile == True** for
each (Postgres active-map count == projected point count), purge → 0, rebuild → restored.
50 parent-map routing points now exist in the contract-scoped collection alongside the
50 durable maps in Postgres.

## Rejected claims

- **Not** a mutation of existing collections: the parent-map collection is separate and
  contract-named (§14 blue/green); chunk/profile/summary collections are untouched.
- **Not** a broader projection: bounded to the 3-doc cohort; scaled projection accompanies
  the controlled backfill (owner step 5), gated on these reconciliation results.

## Open contract gaps

- Projection RECEIPT persistence into `projection_receipts` (so the S11 readiness report
  can count `vnext_maps_projected` + corpus-purge covers these points) is owed before the
  scaled backfill — the reconciliation here is a live count check, not yet a receipt row.
- The scaled backfill needs the S7b router-into-map-infer (spread compound-mini across the
  6 accounts under load) — the step-3 canary used a single-key direct client.
