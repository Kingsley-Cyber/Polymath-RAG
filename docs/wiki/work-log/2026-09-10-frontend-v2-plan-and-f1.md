---
title: "WORK LOG — FRONTEND-V2-PLAN persisted as authority + F1 shell/navigation/design system"
change_id: FRONTEND-V2-PLAN
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (plan ACTIVE; F1 shipped and browser-verified against the live backend)
register: 11.199
package: "docs/wiki/plans/FRONTEND-V2-PLAN.md + frontend-v2/"
architecture_impact: "frontend only. Greenfield app beside the legacy one; NO backend contract changed; the legacy frontend/ is untouched."
---

> **Ledger:** owner directive 2026-09-10 workstream B — "the design is approved; it just is not on disk."
> Register **11.199**. No backend change, no provider spend.

## Contract

Requested outcome: persist the approved greenfield design as a repository authority, then build F1.

- **Smallest acceptance:** the plan exists as an ACTIVE authority; a greenfield app boots, routes the approved
  navigation, and renders the readiness triad from REAL backend responses.
- **Owner / public contract:** none changed.
- **Inputs/outputs/persistence:** reads backend contracts; writes one plan + a new `frontend-v2/` app.
- **Dependency edges:** `frontend-v2/src/lib/api.ts` → the orchestrator's HTTP contracts (read-only).
- **Verifier / rollback:** `npm run build` (tsc strict + vite) and a live browser session; rollback = delete
  `frontend-v2/` (nothing depends on it; the legacy UI is untouched).

## Changes

- `docs/wiki/plans/FRONTEND-V2-PLAN.md` — **status ACTIVE**, scope greenfield replacement, backend
  architecture FROZEN, old frontend LEGACY/rollback. Captures navigation, Chat controls, the five lane states,
  the Evidence Inspector rule, Compare Retrieval, Answer Review, the Files readiness triad, Graph, the
  function-first Control Plane, phases F0–F12 and the qualification corpora.
- `frontend-v2/` — new app (React 19 + TS strict + Vite 6, matching the legacy toolchain, sharing none of its
  code): `lib/contracts.ts` (typed mirrors of verified backend shapes), `lib/api.ts` (the ONE client + a
  streaming SSE reader), `lib/readiness.ts` (the triad), `lib/useAsync.ts`, `components/{Pill,ReadinessTriad,
  PhaseStub}.tsx`, `screens/Overview.tsx`, `styles/app.css` (the design system), `App.tsx` (shell + nav).
- `docs/wiki/plans/FRONTEND-V2-CONTRACT-INVENTORY-V1.md` — **GAP-6** added (found by F1, below).
- `scripts/repo_guard.py` — `frontend-v2/dist/` added to `IGNORED_PREFIXES` (vite build output is git-ignored
  and content-hashed, exactly the `node_modules` rationale already in that list; the V2 SOURCE is declared).
- `.claude/launch.json`, scaffold TREE declarations, register row.

## Proof

- `npm run build` = `tsc --noEmit` (strict, `noUncheckedIndexedAccess`, `noUnusedLocals`) + `vite build`:
  **green**, 36 modules, 232 kB.
- **Browser-verified live** at `localhost:5273/v2/` against the running orchestrator: the Overview screen
  rendered `SEMANTIC_COMPLETE`, `VNEXT_COMPLETE`, `50/50 parents mapped` and the real semantic counts for
  `rag-canary`; navigation routes between Overview / Chat / Files / Graph / Control Plane / Settings.
- **The honesty property demonstrated by accident, then fixed:** `/ready` was missing from the dev proxy, so
  the browser got a 404. The triad rendered CONTROL READY = **UNKNOWN** ("/ready not reachable") instead of
  defaulting to green — which is exactly the designed behaviour. Proxy fixed; it then rendered a real verdict.
- **GAP-6 discovered by F1 (new):** with the proxy fixed, CONTROL READY renders **DEGRADED — 282 open stalls**
  on a completely idle fleet (`queued_tickets: 0`, `blocked_workers: 0`, `live_workers: 13`,
  `medic_actions_15m: []`). The 282 decompose exactly into the dormant backlog:
  `PENDING_ON_PREDECESSOR×221` + `PENDING_ADVANCE_BLOCKED×32` + `RUN_SETTLED_NOT_PROMOTED×29`. **CONTROL READY
  therefore cannot read green until the dormant backlog is dispositioned** — the primary health verdict is
  pinned by history, not by anything happening now. Same class as GAP-4.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

## Rejected claims

- **"Refactor the legacy frontend into V2."** REJECTED — owner law and plan §0.1. `frontend/` is untouched;
  V2 shares no code with it.
- **"Compute CONTROL READY in the client from four endpoints."** PARTIALLY REJECTED and labelled: the client
  composes a *presentational* verdict from `/ready` + `/health/pipeline`, but `readiness.ts` documents that the
  real fix is GAP-1 (a backend `control_ready` verdict) so two screens cannot disagree. No retrieval, ranking or
  readiness POLICY is reimplemented in TypeScript.
- **"Show `query_ready` as the readiness badge."** REJECTED — `readiness.ts` refuses the field by construction;
  the Overview screen renders it only as a labelled counter-example.
- **"Paint CONTROL READY green because the fleet looks fine."** REJECTED — it reads DEGRADED because the
  backend says DEGRADED. GAP-6 is recorded rather than smoothed over.

## Open contract gaps

- F2–F12 unbuilt. **F6 blocked on GAP-2, F7 blocked on GAP-3** (no compare and no review contract exist).
- GAP-1 (no single CONTROL-READY verdict), GAP-4 and now GAP-6 (health counters with no dormancy qualifier)
  are backend work, unstarted.
- No automated frontend test yet — F11's job. The proof above is a build plus a human-verified browser session.
- The dev proxy path list is a maintenance hazard: a single-segment backend path missing from it returns a vite
  404 rather than an error (exactly the `/ready` bug). A contract test that walks `/openapi.json` against the
  proxy list would close it; not built.
