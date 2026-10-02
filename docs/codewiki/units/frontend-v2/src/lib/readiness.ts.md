# unit: frontend-v2/src/lib/readiness.ts
anchor: frontend-v2/src/lib/readiness.ts:1-185

## purpose
Presentation-only verdict painters for the FRONTEND-V2 UI. They read backend verdicts (control plane, semantic, vNext, per-file status) and choose which of ready/blocked/degraded/unknown/working to paint, plus the backend's own blocker word — frontend-v2/src/lib/readiness.ts:4-6. The module decides nothing: "the backend owns that" — frontend-v2/src/lib/readiness.ts:4-5. It deliberately refuses the legacy `query_ready` boolean — frontend-v2/src/lib/readiness.ts:8-10.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ReadyState` | type | `"ready" \| "blocked" \| "degraded" \| "unknown" \| "working"` | readiness.ts:15 | App.tsx (sole importer) |
| `Verdict` | interface | `{ state: ReadyState; label: string; detail?: string }` | readiness.ts:17-22 | App.tsx (sole importer) |
| `controlReady` | function | `(cr: ControlPlane["control_ready"] \| null \| undefined) -> Verdict` | readiness.ts:34 | App.tsx (sole importer) |
| `semanticReady` | function | `(sr: SemanticReadiness \| null) -> Verdict` | readiness.ts:40 | App.tsx (sole importer) |
| `vnextReady` | function | `(sr: SemanticReadiness \| null) -> Verdict` | readiness.ts:53 | App.tsx (sole importer) |
| `docSearchable` | function | `(d: DocSummary \| null \| undefined) -> boolean` | readiness.ts:82 | App.tsx (sole importer) |
| `servesVnext` | function | `(d: DocSummary \| null \| undefined) -> boolean` | readiness.ts:89 | App.tsx (sole importer) |
| `servedWriter` | function | `(d: DocSummary \| null \| undefined) -> "vnext" \| "basic" \| null` | readiness.ts:96 | App.tsx (sole importer) |
| `stageWords` | function | `(stage: string) -> string` | readiness.ts:111 | App.tsx (sole importer) |
| `docStatus` | function | `(d: DocSummary) -> Verdict` | readiness.ts:124 | App.tsx (sole importer) |
| `docPmap` | function | `(d: DocSummary) -> Verdict` | readiness.ts:151 | App.tsx (sole importer) |
| `docProfile` | function | `(d: DocSummary) -> Verdict` | readiness.ts:162 | App.tsx (sole importer) |
| `CHECKING` | const | `Verdict = { state: "unknown", label: "CHECKING" }` | readiness.ts:180 | App.tsx (sole importer) |
| `settled` | function | `<T>(a: { data: T \| null; error: string \| null }, verdict: (d: T \| null) => Verdict) -> Verdict` | readiness.ts:182 | App.tsx (sole importer) |

Sole importer per FACTS.importers: `frontend-v2/src/App.tsx`. Only import: types from `./contracts` — readiness.ts:12.

## contracts

**controlReady** — readiness.ts:34-37
- in: `cr: ControlPlane["control_ready"] | null | undefined` (null while fetch in flight, readiness.ts:32)
- out: null/undefined → `{ state: "unknown", label: "UNKNOWN", detail: "/control_plane not reachable" }` — readiness.ts:35
- post: non-null → copies `cr.state`, `cr.label`, `cr.detail` verbatim; label is never paraphrased — readiness.ts:36, readiness.ts:19-20

**semanticReady** — readiness.ts:40-45
- in: `sr: SemanticReadiness | null`
- out: null → `{ state: "unknown", label: "UNKNOWN" }` — readiness.ts:41
- post: `sr.verdict === "SEMANTIC_COMPLETE"` → state `"ready"`; any other verdict → state `"blocked"`; label = the verdict string — readiness.ts:42-44

**vnextReady** — readiness.ts:53-77
- in: `sr: SemanticReadiness | null`
- out: null or no `sr.vnext` → `{ state: "unknown", label: "UNKNOWN" }` — readiness.ts:54
- post: `v.verdict === "VNEXT_COMPLETE"` plus `served !== null && docs > 0 && served < docs` → state `"ready"`, label `"SEARCHABLE · BASIC PROFILES"` — readiness.ts:63-69
- post: `VNEXT_COMPLETE` otherwise → `{ state: "ready", label: v.verdict }` — readiness.ts:70
- post: not complete but `p.unresolved === 0 && docs > 0 && v.profiled >= docs` → `"ready"`, label `"SEARCHABLE · BASIC PROFILES"` — readiness.ts:72-75
- post: everything else → `{ state: "blocked", label: v.verdict }` — readiness.ts:76

**docSearchable** — readiness.ts:82-84
- out: `!!d && (d.vnext_ready || (d.map_unresolved === 0 && d.profile_present))` — readiness.ts:83
- post: missing vNext profile alone is never "Blocked" (base profile is the default card since `POLYMATH_DOC_PROFILE_VNEXT=0`, 2026-09-17) — readiness.ts:79-81

**servesVnext** — readiness.ts:89-92
- out: `d.profile_served === undefined ? d.vnext_ready : d.vnext_ready && d.profile_served === "vnext"` — readiness.ts:91
- post: a written vNext card the selection guard refused does not count — readiness.ts:86-88

**servedWriter** — readiness.ts:96-100
- out: `d.profile_served !== undefined` → return it; else `d.profile_vnext ? "vnext" : d.profile_present ? "basic" : null` — readiness.ts:98-99

**stageWords** — readiness.ts:111-113
- post: known stage → `STAGE_WORDS` value (16 keys, readiness.ts:102-108); unknown stage → `stage.replace(/_/g, " ")` — readiness.ts:112

**docStatus** — readiness.ts:124-148, first match wins:
1. `!docSearchable(d)` → blocked `NOT SEARCHABLE`, detail = unresolved count and/or `"no profile"` — readiness.ts:125-130
2. `(d.work_failed ?? []).length` → degraded `NEEDS RETRY`, detail lists failed stages via `stageWords` — readiness.ts:131-136
3. `d.run_status === "degraded" || d.run_status === "failed"` → degraded, label `d.run_status.toUpperCase()` — readiness.ts:137-141
4. `d.run_status && d.run_status !== "query_ready"` → working `PROCESSING` — readiness.ts:142-145
5. else → ready `READY` — readiness.ts:146-147

**docPmap** — readiness.ts:151-157
- pre: `map_eligible` may be 0 → `{ state: "unknown", label: "—", detail: "no parents to map" }` — readiness.ts:152
- post: label = `${(d.map_active + d.map_excluded).toLocaleString()}/${d.map_eligible.toLocaleString()}`; state blocked iff `map_unresolved > 0` else ready — readiness.ts:153, readiness.ts:156

**docProfile** — readiness.ts:162-176, first match wins:
1. `!d.profile_present && w === null` → blocked `NONE` — readiness.ts:164
2. `d.profile_served === undefined` → unknown `VNEXT`/`BASIC` ("index was not read") — readiness.ts:165-168
3. `w === null` → degraded `NOT IN INDEX` — readiness.ts:169-172
4. else → ready `VNEXT · IN USE` / `BASIC · IN USE` — readiness.ts:173-175

**settled** — readiness.ts:182-184
- post: returns `CHECKING` only when `a.data == null && !a.error`; otherwise delegates to `verdict(a.data)` (which may receive null when error is set) — readiness.ts:183

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant/Neo4j/files/network/subprocesses/env flags: none. Type-only import from `frontend-v2/src/lib/contracts.ts` — readiness.ts:12.

## invariants
INVARIANT: ReadyState members = 5 (`"ready"`, `"blocked"`, `"degraded"`, `"unknown"`, `"working"`) — readiness.ts:15 [DERIVED]
  fails-if: a state added here without App.tsx support paints nothing.
INVARIANT: functions accepting `query_ready` as input = 0 — readiness.ts:8-10 [DERIVED]
  fails-if: the measured drift returns — cinema `query_ready = true` while SEMANTIC and VNEXT INCOMPLETE, 10,176 unresolved parents, 14/67 documents ready — readiness.ts:9-10.
INVARIANT: `docSearchable(d)` = `d.vnext_ready` OR (`d.map_unresolved` = 0 AND `d.profile_present` = true) — readiness.ts:83 [DERIVED]
  fails-if: a file with unresolved parents or no profile is painted searchable; retrieval then silently misses part of it.
INVARIANT: `"SEARCHABLE · BASIC PROFILES"` literal count >= 2 — readiness.ts:66, readiness.ts:73 [DERIVED]
  fails-if: editing one copy diverges the VNEXT_COMPLETE-partial branch from the parents-mapped fallback branch.
INVARIANT: `CHECKING` returned only when data = null AND error = null — readiness.ts:183 [DERIVED]
  fails-if: a failed fetch paints "Checking" forever instead of `UNKNOWN — /control_plane not reachable`.
INVARIANT: docPmap state = blocked iff `map_unresolved > 0` — readiness.ts:156 [DERIVED]
  fails-if: fully mapped files show red pMAP coverage.
INVARIANT: docStatus label priority NOT SEARCHABLE > NEEDS RETRY > run-status > PROCESSING > READY — readiness.ts:125-147 [DERIVED]
  fails-if: a searchable-but-failed file hides its retry need behind green (the pre-fix cinema behavior, readiness.ts:121-123).

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of arguments; no clock/random/uuid/network/db calls (only the type import, readiness.ts:12). Number text via `toLocaleString()` (e.g. readiness.ts:58, readiness.ts:153) varies with runtime locale — env-dependent formatting only, states do not.
idempotency: SAFE — no writes or side effects; repeated calls with equal inputs return equal verdicts.

## failure behaviour
No `try`/`catch`, no throws anywhere in the module. Every null/undefined input degrades to a verdict instead of raising:
- `controlReady(null/undefined)` → `unknown` `"/control_plane not reachable"` — readiness.ts:35
- `semanticReady(null)` / `vnextReady(null` or no `.vnext)` → `unknown` `UNKNOWN` — readiness.ts:41, readiness.ts:54
- `docSearchable(null)`, `servesVnext(null)` → `false` — readiness.ts:83, readiness.ts:90
- `servedWriter(null)` → `null` — readiness.ts:97
- `settled`: error set + data null skips `CHECKING` and calls `verdict(null)`, so the caller sees each function's unknown branch — readiness.ts:183

## dumb-code flags
- Duplicated literal `"SEARCHABLE · BASIC PROFILES"` at readiness.ts:66 and readiness.ts:73, with differently-built detail strings — easy to diverge on edit.
- Fallback chains: `v.vnext_profiles ?? docs` (readiness.ts:67), `served ?? v.vnext_profiles ?? 0` (readiness.ts:74), `v.documents ?? 0` (readiness.ts:61). Missing counts silently become 0; with `docs = 0` the ready branch at readiness.ts:72 is unreachable (`docs > 0` required), so a missing `documents` count paints `blocked` — [INFERRED] from the guards at readiness.ts:61 and readiness.ts:72.
- `STAGE_WORDS`: 16 magic keys; `doc_parent_map: "pMAP"` is the only abbreviation among plain-word labels — readiness.ts:102-108.
- Historical measurements hardcoded in comments only: 10,176 unresolved parents / 14/67 docs (readiness.ts:10); cinema 77 written / 0 used (readiness.ts:64).
- `"query_ready"` appears in logic exactly once, negated for the per-file PROCESSING check — readiness.ts:142 — while being refused as a corpus-level input at readiness.ts:8-10.

## refactor notes
- Sole importer is `frontend-v2/src/App.tsx` (FACTS.importers); label strings here are UI copy — `"NOT SEARCHABLE"`, `"NEEDS RETRY"`, `"PROCESSING"`, `"READY"`, `"CHECKING"`, `"SEARCHABLE · BASIC PROFILES"`, `"VNEXT · IN USE"`, `"BASIC · IN USE"` — renaming them changes what App.tsx renders — readiness.ts:129, readiness.ts:133, readiness.ts:143, readiness.ts:146, readiness.ts:180, readiness.ts:66, readiness.ts:173.
- All input shapes come from `contracts.ts` — readiness.ts:12. Fields consumed: `ControlPlane["control_ready"]{state,label,detail}`; `SemanticReadiness{verdict, vnext}` with `vnext{verdict, parents{mapped,eligible,unresolved}, documents, vnext_served, vnext_profiles, profiled}`; `DocSummary{vnext_ready, map_unresolved, map_eligible, map_active, map_excluded, profile_present, profile_served, profile_vnext, work_failed[{stage,note}], work_open, run_status}`. Renames in contracts.ts break every function — readiness.ts:34-184.
- Do not reintroduce `query_ready` as an input (measured lie, readiness.ts:8-11) and do not recompose `/ready` + `/health/pipeline` client-side — `/control_plane` returns one composed `control_ready` verdict (`shared/polymath_shared/pipeline_health.py::control_ready`); this module only paints it — readiness.ts:26-32.

## VERIFY
```verify
grep -Fq 'export type ReadyState = "ready" | "blocked" | "degraded" | "unknown" | "working"' frontend-v2/src/lib/readiness.ts
test "$(grep -c -F 'SEARCHABLE · BASIC PROFILES' frontend-v2/src/lib/readiness.ts)" -ge 2
grep -Fq 'return d.profile_served === undefined ? d.vnext_ready : d.vnext_ready && d.profile_served === "vnext";' frontend-v2/src/lib/readiness.ts
grep -Eq 'd\.run_status !== "query_ready"' frontend-v2/src/lib/readiness.ts
grep -Fq 'export const CHECKING: Verdict = { state: "unknown", label: "CHECKING" };' frontend-v2/src/lib/readiness.ts
test "$(grep -c -F 'toLocaleString' frontend-v2/src/lib/readiness.ts)" -ge 9
! grep -Fq 'fetch(' frontend-v2/src/lib/readiness.ts
```
