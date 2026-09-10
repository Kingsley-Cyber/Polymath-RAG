---
title: "WORK LOG — Operational UI: Control Plane screen (functional pools + model/account lanes, frontend Slice 3)"
change_id: OPERATIONAL-UI-V1
date: 2026-09-09
owner: frontend (ControlPlaneView) — renders CONTROL-PLANE-STATUS-V1, recomputes nothing, shows no secret
last_reviewed: 2026-09-09
status: complete (Slice 3 of the operational-UI frontend; Chat selectors + acceptance gate follow)
register: 11.187
package: frontend/src/components/ControlPlaneView.tsx, frontend/src/components/Sidebar.tsx, frontend/src/App.tsx, frontend/src/api.ts, frontend/src/types.ts, frontend/src/app.css, frontend/vite.config.ts, frontend/dist/*, scripts/scaffold_polymath_v4.py
architecture_impact: "Frontend-only. Repurposes the existing 'Fleet' rail slot into the 'Control Plane' screen (§10 — Control Plane belongs in the rail; no navigation structure added or removed, the old fleet board is preserved as a drill-down inside it). Renders the CONTROL-PLANE-STATUS-V1 backend authority: corpus summary + the four functional pools (GRAPH_EXTRACTION / DOCUMENT_PROFILE / PMAP / CHAT), each drilling into its model→account/key lanes and (GRAPH) predicate distribution. No status math in React; no API-key value ever rendered. Committed dist rebuilt; scaffold dist-hash declaration updated."
---

> **Ledger:** operational-UI brief §3 (Control Plane screen) + §4 (function-pool cards) + §5 (graph counters/predicates) + §6 (pMAP efficiency) + §7 (profile counters) + §8 (model/account lanes, view-only, non-secret) + §10 (rail preserved, drill-downs) + register **11.187**. No pipeline/architecture change.

## Contract

One machinery-health screen that answers "is the machinery healthy?" — a corpus summary plus a card per
FUNCTIONAL POOL, each drilling into FUNCTION → MODEL → API-KEY/ACCOUNT LANES. Every number is the
CONTROL-PLANE-STATUS-V1 authority; the frontend renders, never recomputes (§11), and the lane view exposes the
api-key env NAME only, never a value (§8, §14). LOCAL limiter refusals are shown as a metric DISTINCT from
ACTUAL HTTP 429 (§4). parent_enrichment is labelled a legacy bridge, never a fifth pool (§3).

## Changes

- **`types.ts` / `api.ts`**: `ControlPlane`, `PoolStatus`, `PoolProvider` (one optional-field shape covering both
  the graph and pMAP provider blocks), `PoolLanesDetail`/`LaneDetail`, `PredicateRow`; `fetchControlPlane`,
  `fetchPoolLanes`, `fetchPredicates`.
- **`ControlPlaneView.tsx`** (new): corpus summary strip (documents / semantic ready / processing / blocked);
  a `PoolCard` per pool in drain order GRAPH_EXTRACTION → DOCUMENT_PROFILE → PMAP → CHAT — healthy-lanes pill
  (green / amber-disabled / **red on a credential gap**), queue depth (queued/processing/retry/failed; CHAT shown
  as a latency pool, not a queue), and pool-specific provider counters. GRAPH: requests / neighborhoods / dropped
  / **unaccounted (red if >0)** / entities / relations + a **predicate distribution** drill-down (§5). PMAP:
  requests / valid maps / **maps-per-request efficiency** (§6) / **limiter refused (LOCAL) vs HTTP 429 (ACTUAL)**
  / transport-err / empty-200 (§4). A **model → account/key lane** drill-down per pool (§8): lane, account-env
  NAME, reachability, role/family, capacity (rpm·rpd·concurrency·**MAP batch cap**), and LIVE AIMD limiter state.
  The prior fleet board (workers / AIMD lanes / job queue) is preserved as a collapsible "Fleet detail" section,
  with the parent_enrichment legacy-bridge note (§3).
- **`Sidebar.tsx` / `App.tsx`**: the machinery rail slot relabelled "Fleet" → **"Control Plane"** (view id
  `fleet` → `control`), now rendering `ControlPlaneView` scoped to the selected corpus. No rail item added/removed.
- **`app.css`**: `.cp-*` classes; defined the previously-referenced-but-unstyled `.view-scroll` (scroll container
  the Control Plane and Fleet views both use).
- **`vite.config.ts`** (dev only): added `/control_plane`, `/fleet`, `/reasoning_modes` to the API proxy list
  (they were unproxied, so the dev server could not reach them).
- **`frontend/dist/*` + scaffold**: rebuilt bundle; dist-hash declaration → `index-CyMARVoR.js`/`index-DiBIeCEH.css`.

## Proof

- `npm run build` green (294 modules). LIVE, browser-verified at :5173/ui (proxy → :7200), corpus rag-canary:
  summary 10 docs / 10 ready / 0 processing / 0 blocked; GRAPH_EXTRACTION 13/13 lanes, 24 requests, 50
  neighborhoods, **0 unaccounted**, 168 entities, 65 relations; predicate drill-down ACTS_ON 16 … IS_A 1; lane
  drill-down renders model→account with the api-key env NAME only (`SILICONFLOW_API_KEY_1`, `GEMINI_API_KEY_1`,
  `GROQ_API_KEY_1`) — **no secret value** — plus live AIMD limiter (`3/3 ↑77/↓105 289/day`). PMAP 6/6 lanes, 9
  requests, 50 valid maps, **5.56 maps/request**, **limiter refused 0 / HTTP 429 0 shown as separate metrics**;
  the compound-mini lanes render `2rpm · 230rpd · 1c · batch 15` with family isolation `groq_acct_1..6`. CHAT
  labelled a latency pool. Zero console errors.
- `repo_guard` ok; `wiki_worm --check` ok.

## Rejected claims

- **No navigation replaced** — the existing "Fleet" rail slot is relabelled and upgraded; the fleet board itself
  is retained as a drill-down. Same rail item count (§10, §14).
- **No secret rendered** — the lane view shows the api-key env NAME + reachability only; the backend payload
  carries no key value (verified: the ONLY `*_API_KEY_*` strings on the page are env-var names).
- **limiter_refused ≠ HTTP 429** — rendered as two separately-labelled counters (§4); never conflated.
- **pMAP 15 is not a global cap** — the batch cap is shown per-lane as the model's qualified batch, with the
  efficiency tooltip naming the architectural target 60 (§6, §14).
- **Not a corpus scan per render** — the screen polls ONE summary endpoint (5 s); lane/predicate detail is
  fetched only on drill-down (§12).

## Open contract gaps

- `cross_lane_recoveries` (named in §4) has no counter in CONTROL-PLANE-STATUS-V1 yet; the screen shows the
  conservation counters that DO exist and does not fabricate it (§14). Add it when the backend exposes it.
- Live AIMD limiter state is best-effort — a lane with no controller row renders "idle (no traffic yet)".
- Slice 4 (Chat selectors: Query Type / Intent / Model / Reasoning; reasoning DEFAULT LOW, no auto-escalate) and
  Slice 5 (§13 acceptance test + durability close-out) remain.
