# unit: frontend-v2/src/screens/ControlPlane.tsx
anchor: frontend-v2/src/screens/ControlPlane.tsx:1-172

## purpose
F10 screen (FRONTEND-V2-PLAN §9): corpus health console asking "Is the machinery healthy?" — frontend-v2/src/screens/ControlPlane.tsx:10,45 [DERIVED]
One `api.controlPlane` fetch drives a readiness pill, live/queued/blocked counters, a corpus summary card, four function-pool cards, and an on-demand lane drill-down — frontend-v2/src/screens/ControlPlane.tsx:27-28 [DERIVED]
Enforces two display honesty rules: local `limiter_refused` stays distinct from a real HTTP 429; dormant stalls are not shown as current pipeline failures — frontend-v2/src/screens/ControlPlane.tsx:12-19 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| ControlPlane | exported function component | ({ corpusId }: { corpusId: string }) -> JSX | frontend-v2/src/screens/ControlPlane.tsx:25 | frontend-v2/src/App.tsx |
| Stat | module-private function component (not exported) | ({ label, value, note?, bad? }) -> JSX | frontend-v2/src/screens/ControlPlane.tsx:163 | — (local helper) |

## contracts
ControlPlane — frontend-v2/src/screens/ControlPlane.tsx:25
- in: `corpusId: string` (only prop) — frontend-v2/src/screens/ControlPlane.tsx:25
- state: `fn: string | null`, initial `null` (selected pool for lane drill-down) — frontend-v2/src/screens/ControlPlane.tsx:26
- post: health data from exactly one fetch `api.controlPlane(corpusId, s)` with deps `[corpusId]` — frontend-v2/src/screens/ControlPlane.tsx:27
- post: lanes fetched via `api.poolLanes(fn, s)` with deps `[fn]` only when `fn` truthy, else `Promise.resolve(null)` — frontend-v2/src/screens/ControlPlane.tsx:28
- post: readiness = `settled(cp, (d) => controlReady(d?.control_ready))`, semantics delegated to `../lib/readiness` — frontend-v2/src/screens/ControlPlane.tsx:4,30

Stat — frontend-v2/src/screens/ControlPlane.tsx:163
- in: `label: string; value: number; note?: string; bad?: boolean` — frontend-v2/src/screens/ControlPlane.tsx:163
- post: value colored `var(--bad)` iff `bad` — frontend-v2/src/screens/ControlPlane.tsx:167

## effect surface
- network: `api.controlPlane(corpusId, s)` — frontend-v2/src/screens/ControlPlane.tsx:27; GAP-1 comment declares `/control_plane` the ONLY health call (replaced `/ready` + `/health/pipeline`) — frontend-v2/src/screens/ControlPlane.tsx:21-23
- network: `api.poolLanes(fn, s)` (on demand) — frontend-v2/src/screens/ControlPlane.tsx:28
- Postgres: none (FACTS tables_read = [], tables_written = [])
- env: none read client-side; only env NAMES from payload `l.account_env` — frontend-v2/src/screens/ControlPlane.tsx:135,146
- local UI state: `useState<string | null>(null)` — frontend-v2/src/screens/ControlPlane.tsx:26

## invariants
INVARIANT: pool cards rendered = 4 = |`["GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"]`| — frontend-v2/src/screens/ControlPlane.tsx:7,87 [DERIVED]
  fails-if: a new backend pool gets no card; `parent_enrichment` is deliberately pinned as not a fifth pool — frontend-v2/src/screens/ControlPlane.tsx:157
INVARIANT: `api.poolLanes` fires iff `fn !== null` — frontend-v2/src/screens/ControlPlane.tsx:28 [DERIVED]
  fails-if: fetch would run with `null` fn.
INVARIANT: `limiter_refused` note = "LOCAL refusal — zero HTTP, no provider request spent" and `http_429` note = "a REAL provider request that was throttled" are always separate stats — frontend-v2/src/screens/ControlPlane.tsx:112-119 [DERIVED]
  fails-if: merging them violates honesty rule 1 — frontend-v2/src/screens/ControlPlane.tsx:14-15
INVARIANT: dormant banner renders iff `stallsDormant != null && stallsDormant > 0`; records are not cleared — frontend-v2/src/screens/ControlPlane.tsx:55,63-64 [DERIVED]
  fails-if: clearing to force green destroys backlog-classification evidence — frontend-v2/src/screens/ControlPlane.tsx:63-64
INVARIANT: `basic_profile ?? 0` is the only summary fallback; `documents`, `semantic_ready`, `blocked`, `processing_active`, `processing_stalled` have none — frontend-v2/src/screens/ControlPlane.tsx:74-78 [DERIVED]
  fails-if: absent field renders blank while absent `basic_profile` renders 0 — inconsistent display.
INVARIANT: pipeline counters render only when `typeof p.X === "number"`, else hidden — frontend-v2/src/screens/ControlPlane.tsx:32-37 [DERIVED]
  fails-if: non-numeric values silently hide live/queued/blocked counters.
INVARIANT: lane table prints `l.account_env` names only, never secret values — frontend-v2/src/screens/ControlPlane.tsx:135,146 [DERIVED]
  fails-if: secret exfiltration to the browser.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `api.controlPlane` / `api.poolLanes` — frontend-v2/src/screens/ControlPlane.tsx:27-28; render depends on server state)
idempotency: SAFE (read-only fetches plus local `setFn` toggle — frontend-v2/src/screens/ControlPlane.tsx:26,97) [INFERRED — no mutating API call appears in SOURCE]

## failure behaviour
- `cp.error` rendered as `banner banner--bad` — frontend-v2/src/screens/ControlPlane.tsx:68
- `lanes.loading` shows "loading lanes…" placeholder — frontend-v2/src/screens/ControlPlane.tsx:126
- lane table renders only when `lanes.data` present — frontend-v2/src/screens/ControlPlane.tsx:127
- missing pipeline fields default to `null` (hidden) via typeof guards; `pools` falls back `?? {}`; pool stats fall back `?? 0` — frontend-v2/src/screens/ControlPlane.tsx:31-39,101-104
- no error codes raised here; error text originates in `useAsync`/api layer (not visible in this file)

## dumb-code flags
- Threshold literal `>3min since last move` hardcoded as UI copy; the actual stall classification is not computed here — frontend-v2/src/screens/ControlPlane.tsx:80 [INFERRED — screen only displays the note]
- Inconsistent defaulting: pool stats use `?? 0` but summary stats (except `basic_profile`) do not — frontend-v2/src/screens/ControlPlane.tsx:74-78 vs 101-104
- Duplicated pluralization `=== 1 ? "" : "s"` twice in one banner — frontend-v2/src/screens/ControlPlane.tsx:57,60
- Repeated inline magic styles: `marginBottom: 14` (three times), `fontSize: 12`, `fontSize: 11`, `fontSize: 11.5`, `maxWidth: 210` — frontend-v2/src/screens/ControlPlane.tsx:56,68,71,95,146,156,168
- Dormant-stall state names (`PENDING_ON_PREDECESSOR`, `PENDING_ADVANCE_BLOCKED`, `PENDING_OWNER_STAGE`, `RUN_SETTLED_NOT_PROMOTED`) exist only in a comment, referenced by no code — frontend-v2/src/screens/ControlPlane.tsx:16-17
- Static footer about `parent_enrichment` is dead copy, driven by no data — frontend-v2/src/screens/ControlPlane.tsx:157

## refactor notes
- Single-health-call contract (GAP-1, closed 2026-09-12): re-adding `/ready` or `/health/pipeline` fetches regresses the gap; both strings still appear in the comment, so absence-greps must exclude comments — frontend-v2/src/screens/ControlPlane.tsx:21-23
- Prop shape `{ corpusId: string }`; sole importer is frontend-v2/src/App.tsx (FACTS.importers) — changing it breaks App — frontend-v2/src/screens/ControlPlane.tsx:25
- Backend payload fields consumed verbatim: `control_ready`, `control_ready.pipeline.{causes,stalls_active,stalls_dormant,queued_tickets,live_workers,blocked_workers}`, `pools[f].{queued,processing,retry,failed,lanes.{active,total},provider.{limiter_refused,http_429,provider_requests,valid_maps_persisted}}`, `summary.{documents,semantic_ready,basic_profile,blocked,processing_active,processing_stalled}`, `contract` — frontend-v2/src/screens/ControlPlane.tsx:31-39,72-81,89-121. Renames fail silently (guards render null), not loudly.
- `poolLanes` response shape consumed: `models[].model` + `models[].lanes[].{lane, account_env, role, reachability, capacity.rpd}`; `"active"` is the only reachability value styled positive — frontend-v2/src/screens/ControlPlane.tsx:129-140
- Readiness semantics live in `../lib/readiness` (`controlReady`, `settled`); fetching in `../lib/useAsync` — frontend-v2/src/screens/ControlPlane.tsx:2-4

## VERIFY
```verify
grep -Fq 'const FUNCTIONS = ["GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"] as const;' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'api.controlPlane(corpusId, s)' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'api.poolLanes(fn, s)' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'LOCAL refusal — zero HTTP, no provider request spent' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'no secret value is ever sent to the browser' frontend-v2/src/screens/ControlPlane.tsx
test "$(grep -c -F 'useAsync(' frontend-v2/src/screens/ControlPlane.tsx)" -ge 2
! grep -Fq 'fetch(' frontend-v2/src/screens/ControlPlane.tsx
```
