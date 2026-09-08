---
title: "WORK LOG — controlled routed parent-MAP backfill (step 5 start)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-CONTROLLED-BACKFILL
date: 2026-09-07
owner: worker (routed generation + projection at cohort scale)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.153
package: scripts/parent_map_backfill.py, docs/wiki/experiments/parent-map-backfill-2026-09-07.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "The controlled routed backfill: scripts/parent_map_backfill.py generates parent maps through the S7b route_groq (shared-budget spread across the six compound-mini accounts) + projects them, idempotently and resumably. It proved the routed pipeline at cohort scale AND surfaced two findings before any mass run: (1) a router single-account-pinning bug (route_groq looked up limiter lanes under provider 'cloud' instead of 'llm_cloud' → get_lane always missed → no spread) — FIXED (register: the fix commit), now distinct_accounts_used 1 → 6; (2) a full backfill is Groq-RPM/RPD-paced and resumable — the shared accounts are heavily loaded (profiles + maps), so large docs' many batches 429 and complete over time, not in one run. Touches only the 0054 tables + the parent-map Qdrant collection for the cohort. No mass backfill."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P1 substrate** — this work-log is the EVIDENCE for that ledger row (the MD phase table is the control point; this does not duplicate it).

# WORK LOG — controlled routed parent-MAP backfill (step 5)

## Contract

Owner /goal step 5: "controlled cohorts → backfill". After the step 1-4 E2E gates
passed, run a CONTROLLED (bounded, one corpus) routed backfill to prove the pipeline at
cohort scale and surface scaling issues before any mass run (owner gate: no mass-backfill
before the E2E gates pass).

Owner: `worker`. Verifier: `scripts/parent_map_backfill.py` + the S9/S10 durability
suites + the parent-map/projection canaries. Rollback: `parent_map_canary.py --cleanup`
/ `parent_map_projection_canary.py --purge-only` per doc.

## Changes

- **`scripts/parent_map_backfill.py`** (new): per doc, `run_document_mapping` with a
  ROUTED compound-mini infer (`route_groq` picks the least-loaded account's `map_groq`
  lane; `POLYMATH_GROQ_ROUTER`), then projects via `parent_map_projection`. Idempotent +
  resumable (already-mapped parents re-infer nothing; projection upserts by point id).
  Reports the lane spread + per-doc completeness.
- **experiment JSON**, **scripts/README** row, **TREE** line, this work-log.

## Proof (LIVE, dev fleet, 8-doc cinema slice)

```
POLYMATH_GROQ_ROUTER=1 .venv/bin/python scripts/parent_map_backfill.py --corpus cinema --limit 8 --project
```

- **Routed spread WORKS** (after the provider fix): `distinct_accounts_used: 6`
  (`map_groq1..6` = 30/1/1/2/2/2) — the router spreads across all six accounts and routes
  AROUND 429-locked ones. Before the fix it pinned 39/39 calls to `map_groq1`.
- **Mechanism proven**: 4/8 docs fully mapped + projected (the 3-doc canary cohort +
  Bayesian); the pipeline (skeleton → map_prompt → routed compound-mini →
  run_document_mapping → project) runs end to end at cohort scale.
- **Rate-limit finding**: 4/8 docs (the largest: Bruce 297 parents, Breakthrough 90,
  Blain 264, Anatomy 71) did NOT fully map in one run — the shared Groq accounts are
  heavily loaded today (67 profiles + 67 self-retrieval qualification + prior map runs),
  so `compound-mini` 429s and the many batches of a large doc complete over time. This is
  the paced, resumable reality of a full backfill — surfaced before any mass run.

## Rejected claims

- **Not** a mass backfill: one corpus, an 8-doc slice; the maps persist + are resumable.
  A full corpus/multi-corpus backfill is a PACED operation (RPD 230/account/day × 6),
  run over time as budgets reset — not a single in-session run.
- **Not** a router failure: the router now spreads (6 accounts) and correctly avoids
  throttled accounts; incompleteness is the account rate-limit budget, not the routing.

## Open contract gaps

- Full cinema (+ other corpora) backfill is Groq-RPM/RPD-paced; complete it over time
  (resumable) with the accounts fresh, ideally decoupled from concurrent profile load.
- The full shared-budget accounting for routing should also snapshot the PROFILE lanes on
  each account (route_groq currently snapshots only the map pin) so it sees profile usage
  on the shared accounts — a refinement for concurrent profile+map load.
- Next dependency (step 5 back half): the retrieval-runtime SHADOW route (vNext profile →
  parent-map → child, measured against the current retrieval, no ranking effect), then
  dual-read, then cutover — the live query-path integration.
