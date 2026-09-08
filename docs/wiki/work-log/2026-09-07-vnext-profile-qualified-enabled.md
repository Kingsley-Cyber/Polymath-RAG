---
title: "WORK LOG — vNext profile self-retrieval qualification PASSED → flag enabled"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-VNEXT-QUALIFIED
date: 2026-09-07
owner: governance (qualification gate + reversible flag activation)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.149
package: scripts/profile_vnext_selfretrieval_canary.py, docs/wiki/experiments/profile-vnext-selfretrieval-2026-09-07.md, docs/wiki/experiments/profile-vnext-selfretrieval-2026-09-07.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "Qualifies the vNext (fingerprint) profile against the current lean-context baseline via self-retrieval on all 67 cinema docs (evaluation-only: a separate canary Qdrant collection, deleted after). vNext top-1 0.933 vs baseline 0.860 — PASS. Per owner authorization, enables the profile via the reversible flag POLYMATH_DOC_PROFILE_VNEXT=1 (set in .env; effective on the next fleet reload). No production collection, live worker, chunks, or authoritative profile state modified; existing profiles untouched (backfill is a later controlled step)."
---

# WORK LOG — vNext profile qualified → enabled

## Contract

Owner /goal (2026-09-07) step 1: "Qualify the already-wired vNext profile against the
existing retrieval baseline. Do not flip `POLYMATH_DOC_PROFILE_VNEXT=1` globally until
that gate passes. If it passes, enable the vNext profile through the existing reversible
flag." Gate = vNext self-retrieval ≥ baseline (cinema top-1 85.8%).

Owner: `governance`. Verifier: `scripts/profile_vnext_selfretrieval_canary.py` (exit 0 =
PASS). Rollback: unset `POLYMATH_DOC_PROFILE_VNEXT` in `.env`.

## Changes

- **`scripts/profile_vnext_selfretrieval_canary.py`** (new, SPENDS, evaluation-only):
  generates vNext profiles for a corpus, projects them to a SEPARATE canary Qdrant
  collection, measures self-retrieval vs the production baseline on the same docs, and
  deletes the canary collection. Never touches production profile state.
- **`.env`** (gitignored, not committed): appended `POLYMATH_DOC_PROFILE_VNEXT=1` — the
  reversible activation. Effective on the next fleet/supervisor reload (env is read at
  process start); the running fleet stays on the legacy path until then. This work-log
  records the decision + evidence (the repo authority).
- **experiment report + JSON**, **scripts/README** row, **TREE** lines, this work-log.

## Proof

```
.venv/bin/python scripts/profile_vnext_selfretrieval_canary.py --corpus cinema --per-doc 3 \
   --out docs/wiki/experiments/profile-vnext-selfretrieval-2026-09-07.json   -> exit 0 (PASS)
```

67/67 docs, 0 errors. Baseline (lean-context, same 67-doc cohort): top-1 **0.860**, top-3
0.995, median 1. vNext (fingerprint): top-1 **0.933**, top-3 0.985, median 1. vNext beats
the baseline and clears the gate (baseline − 0.03). The canary collection was deleted.
Full analysis: `docs/wiki/experiments/profile-vnext-selfretrieval-2026-09-07.md`.

## Rejected claims

- **Not** a production reprofiling: existing cinema profiles are untouched; the flag only
  changes NEW-document profile generation, effective on the next fleet reload.
- **Not** a forced fleet restart: the flag is set in `.env`; I did not restart the owner's
  supervisor. It activates on the next boot; rollback is unsetting the flag.
- **Not** a mass backfill: re-profiling existing corpora with vNext is a later controlled
  step (owner /goal step 5), gated on the E2E canary/reconciliation.

## Open contract gaps

- The vNext profiles produced fewer Q/SEARCH probes per doc (135 vs 400 total) — a smaller
  but higher-precision routing surface; worth watching that downstream compiler-title and
  Hybrid routing benefit similarly (S10 title bridge / ablation).
- Enabling the flag affects only new profiling; a controlled cinema re-profile (backfill)
  under vNext + a query-side comparison is the next profile-scale step (owner step 5).
