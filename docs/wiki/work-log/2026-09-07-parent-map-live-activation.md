---
title: "WORK LOG — parent-MAP live activation on a tiny cohort (step 3)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-PARENTMAP-ACTIVATION
date: 2026-09-07
owner: worker (durable map generation on a controlled cohort)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.150
package: scripts/parent_map_canary.py, docs/wiki/experiments/parent-map-canary-2026-09-07.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "First LIVE parent-MAP generation. scripts/parent_map_canary.py runs build_parent_skeletons -> map_prompt -> groq/compound-mini -> compile_maps -> run_document_mapping on a tiny cohort, writing durable 0054 maps for those docs (the controlled activation; reversible via --cleanup). It touches ONLY the 0054 parent-map tables for the named docs — no chunks/profiles/retrieval/Qdrant. The limiter (map_canary lane) enforces rate/AIMD on compound-mini. Verifies complete mapping, restart idempotency, and durable SQL state live; partial recovery + missing-alias repair are unit-proven in S9 (test_doc_parent_map_worker)."
---

# WORK LOG — parent-MAP live activation (step 3)

## Contract

Owner /goal step 3: "Wire `map_prompt → routed Compound Mini → run_document_mapping`.
Activate only on a tiny controlled document cohort first. Verify partial recovery,
restart idempotency, missing-alias repair, shared-budget accounting, and durable SQL
state." This is the first live parent-MAP generation — bounded to a tiny cohort, before
any scaled backfill (owner gate: no mass-backfill until the E2E gates pass).

Owner: `worker`. Verifier: `scripts/parent_map_canary.py` (exit 0 = PASS) + the S9
durability suite (`test_doc_parent_map_worker`, partial/repair/idempotency with a fake
infer) + S7a accounting (`test_groq_accounts`). Rollback: `--cleanup` deletes the
cohort's batches/maps/exclusions.

OUT of scope: the S7b router-into-pool wiring (scaled-backfill optimization; a 2-3-doc
canary uses a direct compound-mini client) and the Qdrant projection (step 4).

## Changes

- **`scripts/parent_map_canary.py`** (new, SPENDS + WRITES): loads a tiny cohort's
  parents (with `chunk_id`), builds a live `infer` (`build_map_prompt` → a
  `groq/compound-mini` `LLMExtractionClient` on the `map_canary` limiter lane), runs
  `run_document_mapping`, then re-runs to assert restart idempotency (0 re-inference,
  same active set) and reports per-doc mapped/complete/state. `--cleanup` rolls back.
- **experiment JSON**, **scripts/README** row, **TREE** line, this work-log.

## Proof (LIVE, dev fleet)

```
set -a; . ./.env; set +a
.venv/bin/python scripts/parent_map_canary.py --corpus cinema --docs 1   -> PASS (Circumplex 20/20)
.venv/bin/python scripts/parent_map_canary.py --corpus cinema --docs 3 --out docs/wiki/experiments/parent-map-canary-2026-09-07.json
   -> PASS: Circumplex 20/20, Multistage Pipeline 11/11, Affective Movement 19/19 —
      each complete, restart-idempotent (2nd run re-inferred nothing, same active set),
      durable maps in the 0054 tables. The map_canary limiter halved once on a rate
      event and recovered (AIMD enforcement working); 0 unresolved.
```

50 parents across 3 docs now carry durable `groq/compound-mini` routing maps — the
controlled activation. Complete mapping + restart idempotency + durable SQL state are
proven LIVE; partial recovery + missing-alias repair are proven deterministically in the
S9 unit suite (a fake infer that drops an alias → 73/90 persist, only the 17 repaired);
shared-budget accounting is proven in the S7a unit suite.

## Rejected claims

- **Not** a mass backfill: 3 docs only; the maps persist as the first real cohort. Broader
  generation is gated on step 4 (projection reconciliation) + the owner's step-5 gates.
- **Not** the scaled router: the canary uses a direct compound-mini client on one key;
  the shared-budget router-into-pool (S7b) is the backfill-scale optimization (S7a's
  accounting is already unit-proven).
- **Not** a projection: maps are in Postgres only; projecting them to the contract-scoped
  Qdrant collection + reconciliation is step 4.

## Open contract gaps

- Step 4: project these 3 docs' maps via `parent_map_projection` (embedder + Qdrant) and
  verify Postgres active-map count == projected point count + purge/rebuild.
- S7b router-into-pool wiring is owed before the scaled backfill (so compound + mini share
  the account budget under load).
