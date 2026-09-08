---
title: "WORK LOG — parent-MAP backfill bounded concurrency (~6× coverage throughput)"
change_id: PARENT-MAP-BACKFILL-CONCURRENCY-V1
date: 2026-09-08
owner: governance (backfill throughput; one script enhancement)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.170
package: scripts/parent_map_backfill.py, scripts/scaffold_polymath_v4.py
architecture_impact: "The parent-MAP backfill (RETRIEVAL-MIGRATION step 5 / FINAL-PLAN D-10 coverage) mapped one document at a time — a single Groq call in flight, leaving five of the six routed accounts idle (~15 maps/min). It is the coverage bottleneck for the D-10 HYBRID uplift measurement + every downstream value qualification (P5 fan-out reaching children, P7 graph destinations, P11/P13). Added bounded document-level concurrency (`--concurrency`, default 6) so `route_groq` spreads across all six accounts at once — the same 6-way concurrency the vNext profile regen already proved. Additive + reversible (`--concurrency 1` = the old sequential behaviour); run_document_mapping stays idempotent/resumable and now catches per-doc errors so one failure never kills the batch."
---

> **Ledger row:** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S12** (existing-corpus backfill) + `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` **D-10** (the uplift coverage gate). Throughput enabler, not a new capability.

# WORK LOG — parent-MAP backfill bounded concurrency

## Contract

Accelerate the cinema parent-MAP backfill without changing its output contract: same idempotent,
resumable, contract-scoped per-document mapping + projection, just N documents in parallel so the
six routed Groq accounts are used at once instead of one at a time. Must stay reconciled and
migration-safe (no cutover implication); a per-document failure must not abort the batch.

Owner: `governance`. Verifier: the canary run (below) + the run summary (`errored_docs`,
`distinct_accounts_used`). Rollback: `--concurrency 1` restores the exact sequential path.

## Changes

- **`parent_map_backfill.py`:** `--concurrency N` (default 6). The per-document work
  (`run_document_mapping` + optional projection) moved into `_process_one(doc)` run over a
  `ThreadPoolExecutor`. Each doc is independent — its own `tx()` pool connection (thread-safe
  pool), `route_groq` spreading Groq calls across the six accounts (limiter enforces per-account
  capacity), and the shared qdrant client + embedder handling concurrent requests. Added a per-doc
  `try/except` so a single Groq/DB failure records an `errored` row and the batch continues
  (resumable next run). A print lock keeps the progress log legible. Summary now reports
  `errored_docs` + `concurrency`.

## Proof

- **Thread-safety verified before enabling:** `tx()` = `get_pool().connection()` (fresh pooled
  connection per call, thread-safe); `route()` reads the shared limiter registry + in-flight and
  spreads across accounts; `run_document_mapping` is per-doc independent + idempotent (§36.5).
- **Canary (cinema, 5 docs, `--concurrency 5`, `--project`):** wall **7.2 s**, **errored_docs 0**,
  `distinct_accounts_used 3` (the docs needing fresh inference spread across map_groq1/2/3) — no
  races, no errors, account spreading confirmed. (`complete_docs 4/5` = one large doc still partial,
  a data characteristic, not a failure.)
- Precedent: the vNext doc_profile regen ran the identical 6-way account concurrency (67 docs in
  ~5 min via six supervised slots) with 0 invalid.

## Rejected claims

- **NOT a coverage/uplift claim.** This makes the backfill faster; it does not itself complete
  coverage or measure uplift. D-10 uplift stays GATED until coverage is high enough (§26 no
  premature cutover).
- **NOT an output change.** Byte-for-byte the same maps/projection as the sequential path
  (idempotent per-doc); only the scheduling changed.

## Open contract gaps

- The `--project` resume-projection gap (a fully-mapped doc on resume has `parents_mapped=0` →
  projection skipped) is unchanged by this slice; a standalone parent-map projector/reconcile pass
  remains the clean follow-up before cutover (noted in the vNext-profile-atom-regen work-log).

## CORRECTION (2026-09-08) — concurrency >1 is counterproductive; root cause = route_groq single-account pinning

The canary (5 docs) spread across 3 accounts and looked healthy, but **at scale concurrency >1
single-account-pins and is worse than sequential**, so the default is reverted to `--concurrency 1`.

- **Measured:** a `--concurrency 3` full-corpus pass made **633 of ~640 map calls on `map_groq1`**
  (map_groq2–6: 1–2 each), saturating that one account (429s) and netting only **+13 maps / 6
  complete docs** in 63 s — WORSE than the sequential ~15 maps/min.
- **Root cause:** `route_groq.route` picks the account with the most shared remaining budget from a
  point-in-time `capacity_snapshot`. **Sequentially** each call sees the prior call's draw and
  rotates; **concurrently** the N threads read near-identical snapshots and all choose the same
  best account (`map_groq1`) — the exact "single-account pinning" `groq_routing.py` documents for
  the 8-doc backfill, re-triggered by parallelism. The limiter then enforces that one account's
  capacity, so the extra threads just pile onto it.
- **Resolution:** default `--concurrency 1` (sequential = the account-spreading path). The flag
  stays for when the router is fixed. **The real unblock for a parallel backfill is a
  concurrency-aware `route_groq`** (atomically reserve/decrement per-account capacity, or
  round-robin/least-in-flight under concurrent callers) — a scoped follow-up on
  `shared/polymath_shared/document_profile/groq_routing.py` + `groq_router.choose`. Until then the
  backfill is a steady sequential capacity-gated campaign (~15 maps/min), and coverage for D-10 is
  multi-session.
