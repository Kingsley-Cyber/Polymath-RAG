# INGESTION-WATERFALL-V1 — Phase 4B measurements

Date: 2026-08-24/25 · Branch `architecture/evidence-first-v5`
Corpus under load: `scale-10k-v1` backlog (~4.3k pending tickets,
~370+ successor runs, 21k chunks, 12k runs total history)

## CONTROL TICK PROFILE (measured)

| Metric | Before P4A | After P4A/V3 |
|---|---|---|
| Heartbeat cadence | **dead since Aug 23 12:41 UTC** (>1 day) | alive; full tick ~10-13 min cold, ms-level lease-skips |
| Dominant phase | `_receipts_present` corpus-wide anti-join COUNT **per candidate ticket** inside tick tx | same check, memoized + early-exit; remaining cold pass ≈ one EXISTS walk per (pending run × projection) |
| Sampling attribution (96% of 24 samples) | receipts anti-join | — |
| Full-tick duration (measured) | >24 min, sometimes never completing | 762,888 ms cold first pass (log: `tick_ms= 762888.1`); warm skip ticks 11-29 ms |
| Small-corpus entry during bulk | starved (no tickets created) | **full 12-ticket DAG created** (`lock-test-a-v1`) |

### Remaining bottleneck classification

`DATABASE_BOUND → PYTHON_BOUND (incremental-census gap)`:
even with receipt verdicts bounded, every tick re-derives census over
**25,442 stage_attempts / 10,216 active runs in Python**
(`compute_census` loads all attempts ordered) and re-runs contract
reconciliation scans across all active runs. Telemetry therefore
justifies the charter-gated incremental redesign:

- dirty-run set from `stage_attempts.started_at > last_watermark`
- census re-derived only for dirty runs
- unchanged historical runs skipped entirely

This is the single highest-leverage next change; everything else in the
tick is already set-based or memoized.

## DOCUMENT WATERFALL (extract stage, measured via extraction-audit-v1)

From the genre-probe documents (small docs, enforce mode):

| Stage | ms |
|---|---|
| total extract | ~2,030 |
| gliner entity+evidence passes | ~1,100 |
| rescue | ~820 |
| syntax (spacy sidecar) | ~20 |
| admission + mentions | ~20 |
| predicate compile | <1 |
| fact admission | <1 |

Queue-wait dominates end-to-end for interactive docs while a bulk
backlog drains (observed: extract 'ready' for ~8-11 min under
scale-10k fair-share). Service time itself is seconds.

## Stage timing contract fields

Implemented this slice: ticket-level `created_at/updated_at`,
lease columns, attempt counters, bundle hash on outputs, and
extraction-audit per-stage timings inside extract. The full
per-phase queue/compute/lock split table (charter §4B REQUIRED_STAGE_FIELDS)
is specified above and lands with the incremental-census work, which
owns the eligible_at/claimed_at transitions.
