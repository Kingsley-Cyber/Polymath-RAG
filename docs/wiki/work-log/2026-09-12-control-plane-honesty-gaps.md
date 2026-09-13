---
title: "WORK LOG — CONTROL PLANE honesty: GAP-1 composed control_ready, GAP-4 age-qualified processing, GAP-6 active/dormant stall split"
change_id: CONTROL-PLANE-HONESTY-V1
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.211
architecture_impact: "additive backend fields + one new composed verdict on /control_plane; no retrieval/ranking/pipeline architecture change; no schema change; no producer stopped."
---

> Executor session, owner directive 2026-09-11 (\"take over as implementation agent... transition
> from inspection to code changes\"). Closes three named gaps from
> `docs/wiki/plans/FRONTEND-V2-CONTRACT-INVENTORY-V1.md` that the frontend had already fenced off
> with client-side hedges (`processingIsTrustworthy() -> false`, an inline `dormant` recomputation,
> and a two-call `controlReady(ready, pipeline)` composition) rather than presenting as fact.

## Contract

`shared/polymath_shared/control_plane_status.py::control_plane_status()` is already documented as
"the single backend authority for control-plane health — the UI renders it, never recomputes it"
(11.187). Three of its fields violated that contract on inspection:

- **GAP-1**: no single CONTROL READY verdict existed. The frontend derived one itself from two
  independent calls (`/ready` + `/health/pipeline`), which is recomputation, not rendering — two
  screens composing it differently could disagree (they already did: `App.tsx`'s badge and
  `Overview.tsx`'s triad used slightly different derivations of the same two responses).
- **GAP-4**: `summary.processing` counted runs in `('intake','reconciling','degraded')` with no age
  qualifier. Live measurement (11.190/11.195 era): 64 runs reported "processing" on `cinema` that
  had not moved since 2026-09-07.
- **GAP-6**: `/health/pipeline`'s `stalls_open` pinned `state` to `DEGRADED` on a fleet with 0 queued
  tickets and 0 blocked workers — 282 dormant backlog records (the owner's own 11.197
  classification: `PENDING_ON_PREDECESSOR×221 + PENDING_ADVANCE_BLOCKED×32 +
  RUN_SETTLED_NOT_PROMOTED×29`) kept a healthy, idle fleet reading DEGRADED forever.

## Changes

- `shared/polymath_shared/pipeline_health.py`:
  - `DORMANT_STALL_DIAGNOSES` — the four diagnoses that, BY CONSTRUCTION of
    `control/control/stall_tracer.py::diagnose_pending()`, only exist when nothing live is running
    behind them (`diagnose_pending` returns `None` — no row at all — whenever a live predecessor or
    sibling is running). `_degradation()` now splits `stalls_open` into `stalls_active` /
    `stalls_dormant`; the DEGRADED/HEALTHY state gate keys off `stalls_active`, not the raw total.
    The IDLE fallback now also carries the split so a dormant-only fleet still reports the count
    (never discarded, never hidden — just no longer mistaken for a live defect).
  - `DORMANT_RUN_AGE_SECONDS = 180` — reuses the owner's standing 3-minute stall rule
    (`stall_tracer.STALL_THRESHOLD_S`), restated locally rather than imported across the
    `shared/` → `control/` layer boundary (AGENTS.md §5: one authority per layer, no upward
    dependency).
  - `control_ready(conn, *, sidecars, live_seconds)` — the ONE composed verdict: sidecars down (any
    but the optional `cloud-modal`) → `blocked`; fleet `BLOCKED` → `blocked`; fleet `DEGRADED`
    (active stalls only, post GAP-6) → `degraded`; `HEALTHY`/`IDLE` → `ready`. Carries the full
    `pipeline_health()` snapshot under `pipeline` so callers needing detail (queued/blocked/live
    counts, stall diagnoses) don't need a second call.
- `shared/polymath_shared/control_plane_status.py`:
  - `processing` split into `processing_active` / `processing_stalled` via
    `DORMANT_RUN_AGE_SECONDS` against `runs.updated_at` (which every status-transition writer
    already bumps — `receipts.py`, `manifest_ingest.py`, `scheduler.py`, `reconciliation.py`,
    `generation_swap.py` — confirmed by inspection, not assumed). `processing` itself is kept
    unchanged (active + stalled) for any existing reader.
  - `control_plane_status()` takes an optional `sidecars: dict[str, bool]` and returns
    `control_ready` (from `pipeline_health.control_ready`) in its response.
- `orchestrator/orchestrator/api/ui.py::control_plane()`: takes `request: Request`, reads
  `request.app.state.sidecars` (the same in-process objects `/ready` already reads — this data
  cannot come from Postgres) and passes readiness through to `control_plane_status()`.
- `frontend-v2/src/lib/contracts.ts`: `ControlPlane.control_ready` + the two new summary fields.
- `frontend-v2/src/lib/readiness.ts`: `controlReady()` reduced from a two-argument composition
  (sidecars + pipeline state, with its own DEGRADED/READY logic) to a pure passthrough of the
  backend's verdict. `processingIsTrustworthy()` deleted — the thing it hedged against is fixed.
- `frontend-v2/src/App.tsx`, `screens/Overview.tsx`, `screens/Files.tsx`, `screens/ControlPlane.tsx`:
  all four `controlReady(ready.data, pipeline.data)` call sites now fetch `/control_plane` and pass
  `control_ready` straight through. `ControlPlane.tsx` no longer calls `/ready` or
  `/health/pipeline` directly at all — `/control_plane`'s embedded `control_ready.pipeline` is its
  only health source now (GAP-1's "one call" in practice, not just in principle for this screen).
  The dormant-stall banner and the `processing` stat now read the backend's own
  active/dormant and active/stalled splits instead of recomputing them from
  `stalls_open>0 && queued===0 && blocked===0`.

## Proof

- New `tests/determinism/test_pipeline_health.py` (8 cases, DB-free scripted connection):
  the exact live GAP-6 shape (221+32+29 dormant, 0 queued) now reads `IDLE` not `DEGRADED`
  while still reporting `stalls_dormant=282`; one ACTIVE diagnosis mixed in still degrades;
  a dormant backlog alongside a live queue reads `HEALTHY`; `control_ready` covers dark
  sidecars (including the `cloud-modal` exemption), quarantined workers, an active-degraded
  fleet, and the dormant-only/all-sidecars-up case reading `ready`.
- `tests/determinism/test_control_plane_status.py` updated (not weakened) for the new
  `summary` shape and asserts `control_ready`; declared in `scripts/scaffold_polymath_v4.py`.
- `.venv/bin/python -m pytest tests/determinism/test_pipeline_health.py
  tests/determinism/test_control_plane_status.py tests/determinism/test_pipeline_blocked_health.py
  tests/determinism/test_medic.py -q` → 26 passed.
- `cd frontend-v2 && npm run build` (`tsc --noEmit && vite build`) → green, no type errors from the
  four call-site rewrites.
- `repo_guard.py` / `agent_preflight.py` green after the change; `bundle_integrity.py` unaffected
  (neither edited file is a member of `config/semantic_bundle.lock`'s BUNDLE_MEMBERS — this is
  operational health surface, not a semantic authority).
- Fence: `shared/polymath_shared/{pipeline_health,control_plane_status}.py` sit inside the
  HASH-FENCE-V2 fingerprinted dirs, so the edit is fleet-visible; a controlled
  `scripts/boot_polymath.sh` bounce follows this commit (open runs were `reconciling×69,
  intake×1`, 0 ready/leased tickets — nothing mid-claim at edit time; fleet was 17/11/1-bundle
  healthy immediately after the edit, confirming the fence had not yet tripped anything).

## Rejected claims

- None of the numbers this slice reports were adjusted, cleared, or excluded to reach a
  particular verdict — the same 282 dormant rows still exist and are still counted, just no
  longer conflated with an active defect. No `stall_traces` row was deleted or resolved.

## Open contract gaps

- **GAP-5** (`/documents/summary` unpaginated) — watch only, no action per its own entry; unchanged.
- The remaining "still-live legacy producer" question from 11.190 (`auto_enrich_on_chunks` /
  `parent_enrichment` auto-mint scope for new documents) is a SEPARATE investigation
  (directive §11), not addressed by this slice.
