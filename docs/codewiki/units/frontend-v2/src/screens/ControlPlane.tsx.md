# unit: frontend-v2/src/screens/ControlPlane.tsx
anchor: frontend-v2/src/screens/ControlPlane.tsx:1-171

## purpose
Operator health screen "Control Plane" (F10, FRONTEND-V2-PLAN §9): one `api.controlPlane(corpusId)` fetch renders a readiness Pill, corpus summary stats, and one card per function pool with an optional lane drill-down (`api.poolLanes`) — frontend-v2/src/screens/ControlPlane.tsx:9-24, 27-28 [DERIVED].
It enforces two display honesty rules: local `limiter_refused` (zero HTTP) stays visually distinct from a real `http_429` that cost a provider request, and dormant stalls (nothing live behind them) are shown per the backend's active/dormant split (GAP-6) instead of being re-derived — frontend-v2/src/screens/ControlPlane.tsx:14-19 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ControlPlane` | function component | `({ corpusId }: { corpusId: string }) -> JSX.Element` | frontend-v2/src/screens/ControlPlane.tsx:25 | frontend-v2/src/App.tsx |

`Stat` (frontend-v2/src/screens/ControlPlane.tsx:162-170) is a module-private helper, not exported [DERIVED].

## contracts
`ControlPlane({ corpusId })`
- in: `corpusId: string` prop — frontend-v2/src/screens/ControlPlane.tsx:25 [DERIVED]
- in (fetches): `api.controlPlane(corpusId, signal)`, deps `[corpusId]` — frontend-v2/src/screens/ControlPlane.tsx:27; `api.poolLanes(fn, signal)` only when `fn != null`, else `Promise.resolve(null)`, deps `[fn]` — frontend-v2/src/screens/ControlPlane.tsx:28 [DERIVED]
- out: JSX only; no callbacks or return value consumed by callers [DERIVED]
- pre: none enforced — all payload access is optional-chained/`??`-guarded; a partial payload still renders — frontend-v2/src/screens/ControlPlane.tsx:31-39, 100-103 [DERIVED]
- post: readiness Pill computed as `settled(cp, (d) => controlReady(d?.control_ready))` — frontend-v2/src/screens/ControlPlane.tsx:30 [DERIVED]
- payload shape consumed: `cp.data.contract`, `cp.data.summary.{documents, semantic_ready, blocked, processing_active, processing_stalled}` (frontend-v2/src/screens/ControlPlane.tsx:72, 74-80); `cp.data.control_ready.pipeline.{causes?, stalls_active?, stalls_dormant?, queued_tickets?, live_workers?, blocked_workers?}` (frontend-v2/src/screens/ControlPlane.tsx:31-37); `cp.data.pools[f].{queued, processing, retry, failed, lanes:{active,total}, provider:{limiter_refused, http_429, provider_requests, valid_maps_persisted}}` (frontend-v2/src/screens/ControlPlane.tsx:39, 86-120) [DERIVED]

## effect surface
- Network: `api.controlPlane(corpusId, s)` — the ONLY health call since GAP-1 (closed 2026-09-12), replacing separate `/ready` + `/health/pipeline` fetches — frontend-v2/src/screens/ControlPlane.tsx:21-23, 27 [DERIVED]; `api.poolLanes(fn, s)` drill-down — frontend-v2/src/screens/ControlPlane.tsx:28 [DERIVED]. Endpoint URLs live in `frontend-v2/src/lib/api.ts` (FACTS.imports), not in this file.
- Postgres: none (FACTS `tables_read` / `tables_written` empty) [DERIVED]
- Qdrant / files / subprocesses / env flags: none read; lanes table shows env NAMES only (`l.account_env`), "no secret value is ever sent to the browser" — frontend-v2/src/screens/ControlPlane.tsx:134, 145-147 [DERIVED]
- Local React state: `fn: string | null` (selected pool for lane drill-down) — frontend-v2/src/screens/ControlPlane.tsx:26 [DERIVED]

## invariants
INVARIANT: pool cards rendered == len(`FUNCTIONS`) == 4 (`"GRAPH_EXTRACTION"`, `"DOCUMENT_PROFILE"`, `"PMAP"`, `"CHAT"`) — frontend-v2/src/screens/ControlPlane.tsx:7, 86 [DERIVED]
  fails-if: a new backend pool is invisible here; `parent_enrichment` must never be added (footer warns it is "a legacy stage pin, not a fifth pool") — frontend-v2/src/screens/ControlPlane.tsx:155-157
INVARIANT: open lane drill-downs <= 1 — toggle is `fn === f ? null : f` — frontend-v2/src/screens/ControlPlane.tsx:26, 95 [DERIVED]
  fails-if: array state would allow concurrent `api.poolLanes` fetches and stacked tables
INVARIANT: pipeline numerics (`stalls_active`, `stalls_dormant`, `queued_tickets`, `live_workers`, `blocked_workers`) are `null` unless `typeof p.X === "number"` — frontend-v2/src/screens/ControlPlane.tsx:33-37 [DERIVED]
  fails-if: backend sends numeric strings → counters silently disappear from the header row (contrast: pool stats default to `0`, frontend-v2/src/screens/ControlPlane.tsx:100-103)
INVARIANT: dormant banner shown iff `stallsDormant != null && stallsDormant > 0`; active stalls listed inside it iff `stallsActive > 0` with `causes.join(" · ")` — frontend-v2/src/screens/ControlPlane.tsx:55-62 [DERIVED]
  fails-if: banner hidden means the "records not cleared, evidence preserved" explanation is lost even when active stalls exist
INVARIANT: `http_429 > 0` marks Stat bad; `limiter_refused > 0` does NOT (no `bad` prop) — frontend-v2/src/screens/ControlPlane.tsx:111-118 [DERIVED]
  fails-if: coloring both red destroys honesty rule #1 (frontend-v2/src/screens/ControlPlane.tsx:14-15)
INVARIANT: lanes Stat bad iff `laneCounts.active === 0`; note shown iff `active !== total`, displaying `${laneCounts.total - laneCounts.active} not active` — frontend-v2/src/screens/ControlPlane.tsx:104-107 [DERIVED]
INVARIANT: `processing_stalled > 0` marks processing Stat bad with note `stalled (>3min since last move)` — frontend-v2/src/screens/ControlPlane.tsx:77-80 [DERIVED]
  fails-if: the 3-minute window is a display string here, not computed — drift with the backend's real stall threshold goes unnoticed

## determinism & idempotency
determinism: NONDETERMINISTIC (network: `api.controlPlane` / `api.poolLanes` — frontend-v2/src/screens/ControlPlane.tsx:27-28; rendered output depends on fetched server state) [DERIVED]. No clock/random/uuid/db/file use; `">3min"` and `"—"` are literal strings — frontend-v2/src/screens/ControlPlane.tsx:79, 139 [DERIVED]
idempotency: SAFE (render-only plus read fetches; sole mutation is local `setFn` toggle — frontend-v2/src/screens/ControlPlane.tsx:26, 94-97; no table writes per FACTS) [DERIVED]

## failure behaviour
- `cp.error` rendered as a red `banner banner--bad`; screen keeps rendering below it — frontend-v2/src/screens/ControlPlane.tsx:68 [DERIVED]
- Missing data degrades to defaults: `pools ?? {}` (frontend-v2/src/screens/ControlPlane.tsx:39), `pool?.queued ?? 0` etc. (frontend-v2/src/screens/ControlPlane.tsx:100-103), `p.causes ?? []` (frontend-v2/src/screens/ControlPlane.tsx:32), `l.capacity.rpd ?? "—"` (frontend-v2/src/screens/ControlPlane.tsx:139) [DERIVED]
- Loading/error states for the drill-down: `lanes.loading` shows `loading lanes…`; there is no `lanes.error` branch — frontend-v2/src/screens/ControlPlane.tsx:125-149 [INFERRED: a failed `api.poolLanes` leaves the drill-down area silently blank]
- Pill pending/error styling delegated to `settled` / `controlReady` from `frontend-v2/src/lib/readiness.ts` — frontend-v2/src/screens/ControlPlane.tsx:3, 30 [DERIVED]

## dumb-code flags
- Two missing-data conventions in one screen: pipeline numerics -> `null` (frontend-v2/src/screens/ControlPlane.tsx:33-37) vs pool numerics -> `0` (frontend-v2/src/screens/ControlPlane.tsx:100-103) [DERIVED]
- Magic text `">3min"` duplicates a backend threshold as a display string — frontend-v2/src/screens/ControlPlane.tsx:79 [DERIVED]
- Duplicated pluralization ternaries `=== 1 ? "" : "s"` — frontend-v2/src/screens/ControlPlane.tsx:57, 60 [DERIVED]
- `FUNCTIONS` hardcodes backend pool names; in-code comment acknowledges the trap — frontend-v2/src/screens/ControlPlane.tsx:7, 155-157 [DERIVED]
- Naming hazard flagged in-code: `laneCounts = pool?.lanes` vs `lanes` the fetch — frontend-v2/src/screens/ControlPlane.tsx:89 [DERIVED]
- Layout assumption: `grid grid--2` fixes 2 columns for exactly 4 cards — frontend-v2/src/screens/ControlPlane.tsx:85 [DERIVED]

## refactor notes
- Renaming `ControlPlane` or its `corpusId` prop breaks `frontend-v2/src/App.tsx` (FACTS.importers) — frontend-v2/src/screens/ControlPlane.tsx:25 [DERIVED]
- Splitting health back into `/ready` + `/health/pipeline` fetches reopens GAP-1; keep `api.controlPlane` as the single call — frontend-v2/src/screens/ControlPlane.tsx:21-23, 27 [DERIVED]
- `control_ready` payload is a hard contract: pipeline keys (`causes`, `stalls_active`, `stalls_dormant`, `queued_tickets`, `live_workers`, `blocked_workers`) and pools/provider keys consumed at frontend-v2/src/screens/ControlPlane.tsx:31-37, 86-120 [DERIVED]
- Adding `parent_enrichment` to `FUNCTIONS` is explicitly wrong — frontend-v2/src/screens/ControlPlane.tsx:155-157 [DERIVED]
- `Stat` props `{ label, value, note?, bad? }` with `value: number`; promoting it to a shared component must keep that shape — frontend-v2/src/screens/ControlPlane.tsx:162-170 [DERIVED]

## VERIFY
```verify
grep -Fq 'const FUNCTIONS = ["GRAPH_EXTRACTION", "DOCUMENT_PROFILE", "PMAP", "CHAT"] as const' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'api.controlPlane(corpusId, s)' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'api.poolLanes(fn, s)' frontend-v2/src/screens/ControlPlane.tsx
! grep -Fq 'api.ready' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'stallsDormant != null && stallsDormant > 0' frontend-v2/src/screens/ControlPlane.tsx
grep -Fq 'l.capacity.rpd ?? "—"' frontend-v2/src/screens/ControlPlane.tsx
test "$(grep -c -F '<Stat label=' frontend-v2/src/screens/ControlPlane.tsx)" -ge 13
```
