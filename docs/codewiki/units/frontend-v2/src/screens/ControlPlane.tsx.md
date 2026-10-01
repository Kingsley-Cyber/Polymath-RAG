# unit: frontend-v2/src/screens/ControlPlane.tsx
anchor: frontend-v2/src/screens/ControlPlane.tsx:1-172

## purpose
React operator screen (feature "F10 — Control Plane", FRONTEND-V2-PLAN §9) showing per-corpus machinery health: readiness badge, worker/stall counters, per-function pool stats, and a per-lane drill-down table. Enforces two honesty rules: local `limiter_refused` must stay visually distinct from a real HTTP 429, and dormant stalls must not be shown as live failures. — frontend-v2/src/screens/ControlPlane.tsx:9-24 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ControlPlane | function, named export (React component) | ({ corpusId: string }) -> JSX element | frontend-v2/src/screens/ControlPlane.tsx:25 | frontend-v2/src/App.tsx (FACTS.importers) |
| Stat | function, module-private (not exported) | ({ label: string; value: number; note?: string; bad?: boolean }) -> JSX element | frontend-v2/src/screens/ControlPlane.tsx:163 | ControlPlane only |

## contracts

**ControlPlane** — frontend-v2/src/screens/ControlPlane.tsx:25
- in: prop `corpusId: string` (:25); data from `api.controlPlane(corpusId, s)` re-run on deps `[corpusId]` (:27); `api.poolLanes(fn, s)` re-run on deps `[fn]`, skipped with `Promise.resolve(null)` while `fn === null` (:28).
- out: rendered screen; readiness badge = `settled(cp, (d) => controlReady(d?.control_ready))` (:30).
- pre: `api`, `useAsync`, `controlReady`, `settled`, `Pill` importable from ../lib/api, ../lib/useAsync, ../lib/readiness, ../components/Pill (:1-5).
- post: every pipeline numeric is rendered only if `typeof === "number"`, else coerced to null and its row/stat hidden (:33-37, :50-52).

Response shape consumed from the backend:
- `control_ready.pipeline`: `causes: string[]`, `stalls_active`, `stalls_dormant`, `queued_tickets`, `live_workers`, `blocked_workers` (:31-37).
- `contract`, `summary.documents`, `summary.vnext_served ?? summary.semantic_ready`, `summary.basic_profile`, `summary.blocked`, `summary.processing_active`, `summary.processing_stalled` (:72-81).
- `pools[f]`: `queued`, `processing`, `retry`, `failed`, `lanes.active`, `lanes.total`, `provider.{limiter_refused, http_429, provider_requests, valid_maps_persisted}` (:88-121); each provider stat renders only when the literal key is present (`"limiter_refused" in prov` :112, `"http_429" in prov` :116, `"provider_requests" in prov` :120, `"valid_maps_persisted" in prov` :121).
- lanes drill-down: `models[].model`, `models[].lanes[].{lane, account_env, role, reachability, capacity.rpd}` (:131-140).

## effect surface
- network: `api.controlPlane(corpusId, s)` — frontend-v2/src/screens/ControlPlane.tsx:27 [DERIVED]; `api.poolLanes(fn, s)` — frontend-v2/src/screens/ControlPlane.tsx:28 [DERIVED]. Per GAP-1 comment, `/control_plane` is the ONLY health call this screen makes (:21-23).
- browser state: `useState<string | null>` holding selected pool `fn` (:26).
- Postgres: none read, none written (FACTS tables_read = [], tables_written = []).
- Qdrant / files / subprocesses / env flags: none in this unit.

## invariants

INVARIANT: length(FUNCTIONS) = 4, exactly `["GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"]` — frontend-v2/src/screens/ControlPlane.tsx:7 [DERIVED]
  fails-if: a fifth backend pool is invisible, or a card renders for a nonexistent pool.
INVARIANT: selected fn ∈ FUNCTIONS ∪ {null} — only writer is `setFn(fn === f ? null : f)` — frontend-v2/src/screens/ControlPlane.tsx:96 [DERIVED]
  fails-if: `api.poolLanes(fn)` is called with an unknown function name.
INVARIANT: readiness = backend verdict via `controlReady(d?.control_ready)`, not re-derived from queued/blocked counts — frontend-v2/src/screens/ControlPlane.tsx:18-19,30 [DERIVED]
  fails-if: frontend and backend disagree on DEGRADED.
INVARIANT: each pipeline counter type ∈ {number, null} via `typeof p.X === "number" ? p.X : null` — frontend-v2/src/screens/ControlPlane.tsx:33-37 [DERIVED]
  fails-if: undefined/NaN reaches the DOM as a stat.
INVARIANT: absent pool counters render 0 (`pool?.queued ?? 0`), absent basic profile renders `basic_profile ?? 0`, vNext readiness falls back `vnext_served ?? semantic_ready` — frontend-v2/src/screens/ControlPlane.tsx:75-76,101-104 [DERIVED]
  fails-if: a missing field blanks the card instead of showing 0.
INVARIANT: `reachability === "active"` is the only value rendered `pill--ready`; every other value renders `pill--blocked` — frontend-v2/src/screens/ControlPlane.tsx:137-139 [DERIVED]
  fails-if: an unknown reachability string looks healthy.
INVARIANT: lane table shows `account_env` names only — frontend-v2/src/screens/ControlPlane.tsx:135,146-148 [DERIVED]
  fails-if: secret values leak to the browser.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via api.controlPlane/api.poolLanes frontend-v2/src/screens/ControlPlane.tsx:27-28; async arrival order through useAsync)
idempotency: SAFE — read-only display; only mutation is local UI state `fn` (:26); no store writes.

## failure behaviour
- `cp.error` rendered in `banner banner--bad`; rest of screen still renders — frontend-v2/src/screens/ControlPlane.tsx:68 [DERIVED].
- lanes drill-down: `lanes.loading` -> "loading lanes…" placeholder (:126); fetch skipped entirely when `fn === null` via `Promise.resolve(null)` (:28).
- missing numeric pipeline fields degrade to null and hide their span (`liveWorkers != null && ...`) instead of rendering garbage (:50-52).
- dormant stall records deliberately NOT cleared — banner: clearing them "would destroy the evidence the backlog classification depends on" (:63-64).
- FACTS lists no fallbacks or raised error codes for this unit.

## dumb-code flags
- Stall-state names (PENDING_ON_PREDECESSOR / PENDING_ADVANCE_BLOCKED / PENDING_OWNER_STAGE / RUN_SETTLED_NOT_PROMOTED) appear only in the comment (:16-17); code never branches on them. — frontend-v2/src/screens/ControlPlane.tsx:16-17 [DERIVED]
- Hardcoded display threshold ">3min since last move" duplicates a backend stall definition — frontend-v2/src/screens/ControlPlane.tsx:80 [INFERRED: wording mirrors backend classification].
- Pluralization ternary duplicated verbatim: `stallsDormant === 1 ? "" : "s"` (:57) and `stallsActive === 1 ? "" : "s"` (:60). — frontend-v2/src/screens/ControlPlane.tsx:57,60 [DERIVED]
- Inline magic styles: fontSize 11 + maxWidth 210 (:168), fontSize 11.5 (:146), fontSize 12 (:157), fontSize 16 (:167), padding "2px 8px" (:95). — [DERIVED]
- `laneCounts = pool?.lanes` collides in name with the `lanes` drill-down fetch; disambiguated only by a comment (:90). — frontend-v2/src/screens/ControlPlane.tsx:90 [DERIVED]

## refactor notes
- Do not re-add `/ready` or `/health/pipeline` calls: GAP-1 (closed 2026-09-12) makes `/control_plane` the only health fetch — frontend-v2/src/screens/ControlPlane.tsx:21-23. Blast radius: badge honesty for the whole screen.
- Every consumed member name is a literal (`stalls_active`, `stalls_dormant`, `queued_tickets`, `live_workers`, `blocked_workers`, `vnext_served`, `semantic_ready`, `basic_profile`, `processing_active`, `processing_stalled`, `limiter_refused`, `http_429`, `provider_requests`, `valid_maps_persisted`, `account_env`, `capacity.rpd`) — backend renames silently hide stats. — frontend-v2/src/screens/ControlPlane.tsx:31-39,72-81,110-121,131-140
- Keep `limiter_refused` (note "LOCAL refusal — zero HTTP, no provider request spent" :114) visually separate from `http_429` (note "a REAL provider request that was throttled" :118); merging breaks honesty rule 1 (:14-15).
- `parent_enrichment` is documented as "a legacy stage pin, not a fifth pool" (:156-158); adding it to FUNCTIONS contradicts that note.
- Prop/signature changes to ControlPlane propagate to frontend-v2/src/App.tsx (FACTS.importers).

## VERIFY
```verify
grep -Fq '"GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'api.controlPlane(corpusId, s)' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'api.poolLanes(fn, s)' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'no secret value is ever sent to the browser' frontend-v2/src/screens/ControlPlane.tsx
! grep -Fq 'fetch(' frontend-v2/src/screens/ControlPlane.tsx
test "$(grep -c -F 'useAsync(' frontend-v2/src/screens/ControlPlane.tsx)" -ge 2
```
