# unit: frontend-v2/src/lib/readiness.ts
anchor: frontend-v2/src/lib/readiness.ts:1-187

## purpose
Pure presentational module: converts backend readiness verdicts (control plane, semantic corpus, vNext searchability, per-file status) into `Verdict { state, label, detail }` objects for the UI. The backend owns readiness decisions; these functions only paint ready/blocked/degraded/unknown/working and echo the backend's own words verbatim. Sole importer is `frontend-v2/src/App.tsx`. The legacy `query_ready` boolean is deliberately not accepted by any function here. — frontend-v2/src/lib/readiness.ts:4-10 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ReadyState` | type | union `"ready" \| "blocked" \| "degraded" \| "unknown" \| "working"` | frontend-v2/src/lib/readiness.ts:15 | frontend-v2/src/App.tsx |
| `Verdict` | interface | `{ state: ReadyState; label: string; detail?: string }` | frontend-v2/src/lib/readiness.ts:17-22 | frontend-v2/src/App.tsx |
| `controlReady` | function | `(cr: ControlPlane["control_ready"] \| null \| undefined) -> Verdict` | frontend-v2/src/lib/readiness.ts:34-37 | frontend-v2/src/App.tsx |
| `semanticReady` | function | `(sr: SemanticReadiness \| null) -> Verdict` | frontend-v2/src/lib/readiness.ts:40-45 | frontend-v2/src/App.tsx |
| `vnextReady` | function | `(sr: SemanticReadiness \| null) -> Verdict` | frontend-v2/src/lib/readiness.ts:53-77 | frontend-v2/src/App.tsx |
| `docSearchable` | function | `(d: DocSummary \| null \| undefined) -> boolean` | frontend-v2/src/lib/readiness.ts:82-84 | frontend-v2/src/App.tsx |
| `servesVnext` | function | `(d: DocSummary \| null \| undefined) -> boolean` | frontend-v2/src/lib/readiness.ts:89-92 | frontend-v2/src/App.tsx |
| `servedWriter` | function | `(d: DocSummary \| null \| undefined) -> "vnext" \| "basic" \| null` | frontend-v2/src/lib/readiness.ts:96-100 | frontend-v2/src/App.tsx |
| `stageWords` | function | `(stage: string) -> string` | frontend-v2/src/lib/readiness.ts:111-113 | frontend-v2/src/App.tsx |
| `docStatus` | function | `(d: DocSummary) -> Verdict` | frontend-v2/src/lib/readiness.ts:124-148 | frontend-v2/src/App.tsx |
| `docPmap` | function | `(d: DocSummary) -> Verdict` | frontend-v2/src/lib/readiness.ts:153-159 | frontend-v2/src/App.tsx |
| `docProfile` | function | `(d: DocSummary) -> Verdict` | frontend-v2/src/lib/readiness.ts:164-178 | frontend-v2/src/App.tsx |
| `CHECKING` | const | `Verdict` = `{ state: "unknown", label: "CHECKING" }` | frontend-v2/src/lib/readiness.ts:182 | frontend-v2/src/App.tsx |
| `settled` | function | `<T>(a: { data: T \| null; error: string \| null }, verdict: (d: T \| null) => Verdict) -> Verdict` | frontend-v2/src/lib/readiness.ts:184-186 | frontend-v2/src/App.tsx |

## contracts

**controlReady** — frontend-v2/src/lib/readiness.ts:34-37
- in: composed `control_ready` object from `/control_plane`, or `null`/`undefined` while fetch is in flight (frontend-v2/src/lib/readiness.ts:32).
- out: falsy input → `{ state: "unknown", label: "UNKNOWN", detail: "/control_plane not reachable" }` (:35); else echoes `cr.state`, `cr.label`, `cr.detail` verbatim (:36).
- post: never composes `/ready` + `/health/pipeline` itself — that arithmetic lives in `shared/polymath_shared/pipeline_health.py::control_ready` (frontend-v2/src/lib/readiness.ts:27-32).

**semanticReady** — frontend-v2/src/lib/readiness.ts:40-45
- in: `SemanticReadiness | null`.
- out: `null` → `{ state: "unknown", label: "UNKNOWN" }` (:41); `sr.verdict === "SEMANTIC_COMPLETE"` → state `"ready"` (:42-43); any other verdict → state `"blocked"`, label = `sr.verdict` (:44).

**vnextReady** — frontend-v2/src/lib/readiness.ts:53-77
- in: `SemanticReadiness | null`; reads `sr.vnext.parents.{mapped,eligible,unresolved}`, `sr.vnext.documents`, `vnext_served`, `vnext_profiles`, `verdict` (:54-62).
- out: no `vnext` → `{ state: "unknown", label: "UNKNOWN" }` (:54); `VNEXT_COMPLETE` + `served !== null && docs > 0 && served < docs` → ready, label `"SEARCHABLE · BASIC PROFILES"` (:63-69); `VNEXT_COMPLETE` otherwise → ready with `v.verdict` (:70); non-complete but `p.unresolved === 0 && docs > 0 && profiled >= docs` → ready `"SEARCHABLE · BASIC PROFILES"` (:72-74); else blocked with `v.verdict` (:76).

**docSearchable** — frontend-v2/src/lib/readiness.ts:82-84
- out: `true` iff `d` truthy AND (`d.vnext_ready` OR (`d.map_unresolved === 0` AND `d.profile_present`)) (:83).
- post: missing vNext profile alone never blocks, since base profile is fleet default since 2026-09-17 (:79-81).

**servesVnext** — frontend-v2/src/lib/readiness.ts:89-92
- out: `d.profile_served === undefined` → `d.vnext_ready`; else `d.vnext_ready && d.profile_served === "vnext"` (:91). A written-but-unserved vNext card does not count (:86-88).

**servedWriter** — frontend-v2/src/lib/readiness.ts:96-100
- out: `d.profile_served !== undefined` → return it; else `d.profile_vnext ? "vnext" : d.profile_present ? "basic" : null` (:98-99).

**stageWords** — frontend-v2/src/lib/readiness.ts:111-113
- in: backend stage name, e.g. `"project_neo4j"`.
- out: `STAGE_WORDS[stage] ?? stage.replace(/_/g, " ")` (:112); table has 16 entries (`intake` … `doc_parent_map`) (:102-108).

**docStatus** — frontend-v2/src/lib/readiness.ts:124-148 — fixed ladder, first match wins:
1. `!docSearchable(d)` → blocked `"NOT SEARCHABLE"`, detail from `why[]` (`unresolved parents` / `no profile`) (:125-129).
2. `work_failed` non-empty → degraded `"NEEDS RETRY"`, detail lists failed stages via `stageWords` + `" · the file is searchable meanwhile"` (:131-135).
3. `run_status === "degraded" || run_status === "failed"` → degraded, label `d.run_status.toUpperCase()` (:137-140).
4. `run_status && run_status !== "query_ready"` → working `"PROCESSING"` (:142-144).
5. else → ready `"READY"` (:146-147).

**docPmap** — frontend-v2/src/lib/readiness.ts:153-159
- out: `!d.map_eligible` → unknown `"—"` "no parents to map" (:154); label `max(0, map_eligible − map_unresolved)/map_eligible` (:155); state blocked iff `map_unresolved > 0` (:158).
- post: label shows covered, not mapped + excluded — excluded parents sit outside the eligible set (:150-152).

**docProfile** — frontend-v2/src/lib/readiness.ts:164-178
- out ladder: `!profile_present && w === null` → blocked `"NONE"` (:166); `profile_served === undefined` → unknown `VNEXT`/`BASIC` (:167-169); `w === null` → degraded `"NOT IN INDEX"` (:171-173); else ready `"VNEXT · IN USE"` / `"BASIC · IN USE"` (:175-177).

**settled** — frontend-v2/src/lib/readiness.ts:184-186
- out: `a.data == null && !a.error` → `CHECKING`; else `verdict(a.data)` (:185).

## effect surface
- No Postgres tables read/written, no Qdrant collections, no network calls, no subprocesses, no env flags (FACTS: `tables_read: []`, `tables_written: []`, `constants: []`). — frontend-v2/src/lib/readiness.ts:1-98 [DERIVED]
- Single type-only import: `import type { ControlPlane, DocSummary, SemanticReadiness } from "./contracts"` (FACTS.imports). — frontend-v2/src/lib/readiness.ts:12 [DERIVED]

## invariants
INVARIANT: `docSearchable` true cases == `vnext_ready || (map_unresolved === 0 && profile_present)` — frontend-v2/src/lib/readiness.ts:83 [DERIVED]
  fails-if: per-file red/green flips; a profiled file with 0 unresolved parents would wrongly read NOT SEARCHABLE in `docStatus`.
INVARIANT: vnextReady green-branch guard == `served !== null && docs > 0 && served < docs` — frontend-v2/src/lib/readiness.ts:65 [DERIVED]
  fails-if: libraries whose search serves fewer vNext cards than written would show `VNEXT_COMPLETE` instead of `SEARCHABLE · BASIC PROFILES`.
INVARIANT: vnextReady non-complete green condition == `p.unresolved === 0 && docs > 0 && profiled >= docs` — frontend-v2/src/lib/readiness.ts:72 [DERIVED]
  fails-if: a working basic-profile library (vNext writing off since 2026-09-17) reads blocked/amber (:48-52).
INVARIANT: docPmap numerator == `Math.max(0, d.map_eligible - d.map_unresolved)` — frontend-v2/src/lib/readiness.ts:155 [DERIVED]
  fails-if: negative coverage displays (the live "8/7" class of confusion, :150-152).
INVARIANT: `STAGE_WORDS` entries == 16 (`intake`…`doc_parent_map`) — frontend-v2/src/lib/readiness.ts:102-108 [DERIVED]
  fails-if: a renamed backend stage falls through to `replace(/_/g, " ")` and its plain-word rendering silently changes.
INVARIANT: settled CHECKING condition == `a.data == null && !a.error` — frontend-v2/src/lib/readiness.ts:185 [DERIVED]
  fails-if: in-flight loads show "UNKNOWN — /control_plane not reachable" instead of "CHECKING" (:180-181).

## determinism & idempotency
determinism: DETERMINISTIC (pure functions of their arguments; no clock/random/uuid/network/db/env access anywhere in the unit) — frontend-v2/src/lib/readiness.ts:1-187 [DERIVED]
idempotency: SAFE (no side effects; same input always yields the same `Verdict`) — frontend-v2/src/lib/readiness.ts:1-187 [DERIVED]

## failure behaviour
- Null/undefined inputs degrade to `state: "unknown"` verdicts, never throws: `controlReady` (:35), `semanticReady` (:41), `vnextReady` (:54), `docSearchable`/`servesVnext` → `false` (:83, :90), `servedWriter` → `null` (:97).
- Missing optional fields fall back via `??` chains: `v.documents ?? 0` (:61), `v.vnext_profiles ?? docs` (:67), `served ?? v.vnext_profiles ?? 0` (:74).
- Older backend (no `profile_served`): written state stands — `servedWriter` falls back to latest-card writer (:98-99), `docProfile` shows grey unknown (:167-169).
- Older backend (no run fields): a searchable file still reads Ready in `docStatus` (:122-123).
- No try/catch, no error codes raised; `settled` distinguishes "loading" from "unreachable" only via the caller-supplied `error` string (:184-186).

## dumb-code flags
- Duplicated literal `"SEARCHABLE · BASIC PROFILES"` in two branches of `vnextReady` — frontend-v2/src/lib/readiness.ts:66 and :73 [DERIVED].
- Same displayed count uses two different fallback chains: `(v.vnext_profiles ?? docs)` at :67 vs `(served ?? v.vnext_profiles ?? 0)` at :74 — frontend-v2/src/lib/readiness.ts:67,74 [DERIVED].
- Header comment bans the legacy `query_ready` boolean (:8-10) while `docStatus` compares the string `d.run_status !== "query_ready"` at :142 — same word, different field — frontend-v2/src/lib/readiness.ts:8-10,142 [INFERRED: confusion risk for readers, not a bug].
- Label built by `d.run_status.toUpperCase()` passes the backend string straight into UI text — frontend-v2/src/lib/readiness.ts:139 [DERIVED].
- `stageWords` silently space-joins unknown stage names, so typos in stage keys are invisible — frontend-v2/src/lib/readiness.ts:112 [INFERRED: no validation branch exists].

## refactor notes
- Only importer is `frontend-v2/src/App.tsx` (FACTS.importers) — label/state changes ripple there, but every label string is pinned by owner decisions recorded in comments: FILES-STATUS-TRUTH-V1 (:48-52, :115-123), FILES-READY-LABEL (:79-81), SERVED-PROFILE-LABEL (:64, :86-88). — frontend-v2/src/lib/readiness.ts:48-123 [DERIVED]
- `docStatus` check order encodes the action priority red → amber → blue → green (:116-123); reordering the ladder changes file colors. — frontend-v2/src/lib/readiness.ts:124-148 [DERIVED]
- `vnextReady`'s two green branches (:65, :72) implement the "basic profile is the default card" policy; altering the guards changes library-level readiness painting. — frontend-v2/src/lib/readiness.ts:63-75 [DERIVED]
- `servesVnext`/`servedWriter` fallback semantics when `profile_served === undefined` support older backends — removing them breaks the pre-index-read display. — frontend-v2/src/lib/readiness.ts:91,98-99 [DERIVED]
- Adding/removing a `ReadyState` member changes every consumer's switch surface; `Verdict.label` is shown verbatim by contract ("the UI never paraphrases a verdict"). — frontend-v2/src/lib/readiness.ts:15,19-20 [DERIVED]

## VERIFY
```verify
grep -Fq 'export type ReadyState = "ready" | "blocked" | "degraded" | "unknown" | "working";' frontend-v2/src/lib/readiness.ts
grep -Fq 'SEARCHABLE · BASIC PROFILES' frontend-v2/src/lib/readiness.ts
test "$(grep -c -F 'SEARCHABLE · BASIC PROFILES' frontend-v2/src/lib/readiness.ts)" -ge 2
grep -Fq 'return STAGE_WORDS[stage] ?? stage.replace(/_/g, " ");' frontend-v2/src/lib/readiness.ts
grep -Fq 'export const CHECKING: Verdict = { state: "unknown", label: "CHECKING" };' frontend-v2/src/lib/readiness.ts
! grep -Fq 'localStorage' frontend-v2/src/lib/readiness.ts
```
