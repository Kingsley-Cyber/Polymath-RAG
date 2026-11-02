# unit: frontend-v2/src/screens/_small-modules
anchor: frontend-v2/src/screens/Compare.tsx:1-134; frontend-v2/src/screens/Graph.tsx:1-118; frontend-v2/src/screens/Login.tsx:1-141; frontend-v2/src/screens/Overview.tsx:1-79; frontend-v2/src/screens/Reports.tsx:1-86

## purpose
Five React screen components for the frontend-v2 shell. Compare: one question run across retrieval modes, retrieval only, no synthesis (Compare.tsx:7-12). Graph: browse entities and source-attested relationships per corpus (Graph.tsx:8-13). Login/ChangePassword: single-profile sign-in and password change (Login.tsx:20-21, 71). Overview: readiness triad read from backend authority (Overview.tsx:7-9). Reports: list of product decision reports with a per-report detail panel (Reports.tsx:9-13). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| Compare | function component | ({ corpusId: string }) -> JSX | frontend-v2/src/screens/Compare.tsx:14 | App.tsx / Settings.tsx (unit-level FACTS.importers; per-file split unknown) |
| Graph | function component | ({ corpusId: string }) -> JSX | frontend-v2/src/screens/Graph.tsx:15 | App.tsx / Settings.tsx (unit-level FACTS.importers) |
| signInProblem | function | (err: unknown) -> string | frontend-v2/src/screens/Login.tsx:8 | Login.tsx:36 (same module) |
| Login | function component | ({ onSignedIn: (me: Me) => void }) -> JSX | frontend-v2/src/screens/Login.tsx:22 | App.tsx / Settings.tsx (unit-level FACTS.importers) |
| ChangePassword | function component | ({ me: Me; forced?: boolean; onChanged: (me: Me) => void; onSignOut?: () => void }) -> JSX | frontend-v2/src/screens/Login.tsx:72-77 | App.tsx / Settings.tsx (unit-level FACTS.importers) |
| Overview | function component | ({ corpusId: string }) -> JSX | frontend-v2/src/screens/Overview.tsx:11 | App.tsx / Settings.tsx (unit-level FACTS.importers) |
| Reports | function component | () -> JSX | frontend-v2/src/screens/Reports.tsx:14 | App.tsx / Settings.tsx (unit-level FACTS.importers) |

`ReportItem` (Reports.tsx:56) is module-private, not exported. [DERIVED]

## contracts

**Compare({ corpusId })** — Compare.tsx
- in: `corpusId: string`; user state `q` (question), `modes: string[]` default `[...PUBLIC_MODES]` (Compare.tsx:14-16).
- pre: `run()` returns early when `!q.trim() || !modes.length` (Compare.tsx:22).
- out: `api.compare({ message: q.trim(), corpus_id: corpusId, modes })` (Compare.tsx:25).
- post: per-arm table shows `latency_ms`, `union_size`, `evidence_count`, `selected_documents`, `selected_sections`, `degraded`, and "lanes fired" = `lane_sizes` entries with `v > 0` excluding `union` and `union_uncapped` (Compare.tsx:86-97).
- post: `shared` = documents present in every arm's `retrieval.documents` set (Compare.tsx:31-35).

**Graph({ corpusId })** — Graph.tsx
- in: `corpusId: string`; user `term` search, `picked: GraphEntity | null` (Graph.tsx:15-18).
- out: `api.graphEntities(corpusId, term, 25, s)`; relationships fetched only when `picked?.entity_id` via `api.graphRelationships(picked.entity_id, corpusId, 25, s)`, else `Promise.resolve(null)` (Graph.tsx:20-25).
- post: `dropped_unattested > 0` renders a count banner; each relationship renders `subject` / `predicate` / `object` / `direction` plus `sources` (chunk text sliced to 260 chars) (Graph.tsx:87-105).

**signInProblem(err)** — Login.tsx
- in: any thrown value; reads `err.code` when `err instanceof ApiError` (Login.tsx:9).
- out: mapped strings for codes `BAD_LOGIN`, `TOO_MANY_ATTEMPTS` ("Too many tries. Wait 15 minutes, then try again."), `OWNER_PASSWORD_NOT_SET`, `LOGIN_NOT_CONFIGURED`; default `Couldn't sign in: ${...detailMessage | String(err)}` (Login.tsx:10-17).

**Login({ onSignedIn })** — Login.tsx
- pre: submit button disabled while `busy || !username.trim() || !password` (Login.tsx:61).
- out: `auth.login(username.trim(), password)` then `onSignedIn(me)` (Login.tsx:33).
- post on failure: error text from `signInProblem(err)` and `setPassword("")` (Login.tsx:34-37).

**ChangePassword({ me, forced, onChanged, onSignOut })** — Login.tsx
- pre: submit disabled while `busy || !current || next.length === 0` (Login.tsx:121).
- out: `auth.changePassword(current, next)` then `onChanged(updated)` (Login.tsx:90-93).
- post: non-forced success banner "Password changed. Other devices are signed out."; `forced` renders the standalone `auth` layout with a Sign out button when `onSignOut` given (Login.tsx:111, 124-140).

**Overview({ corpusId })** — Overview.tsx
- out: `api.controlPlane(corpusId)`, `api.semanticReadiness(corpusId)`, `api.corpora()` (Overview.tsx:12-14).
- post: `ReadinessTriad` verdicts built only from `settled(cp, controlReady)`, `settled(sr, semanticReady)`, `settled(sr, vnextReady)`; `query_ready` appears only inside a `<details>` counter-example (Overview.tsx:30-34, 37-55).

**Reports()** — Reports.tsx
- out: `reportApi.list(s)` mapped through `reportRows`; rejection rethrown as `new Error(errorWords(e))` (Reports.tsx:16-19).
- post: `refresh` clears the `seen` map before bumping `nonce` (Reports.tsx:23); "Open report" link rendered only when `row.hasPage || status === "compiled"` (Reports.tsx:72); `ReportPanel` mounted only when the row is open (Reports.tsx:83).

## effect surface
- HTTP via `../lib/api`: `api.compare` (Compare.tsx:25); `api.graphEntities`, `api.graphRelationships` (Graph.tsx:20, 23); `api.controlPlane`, `api.semanticReadiness`, `api.corpora` (Overview.tsx:12-14); `reportApi.list` — GET `/product/reports` per comment (Reports.tsx:9, 17).
- Auth session via `../lib/auth`: `auth.login` (Login.tsx:33), `auth.changePassword` (Login.tsx:90).
- CSS side-effect import `"../styles/product.css"` (Reports.tsx:7).
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`); Qdrant, files, subprocesses, env flags: none in SOURCE.

## invariants
INVARIANT: default `modes` length == `PUBLIC_MODES` length (`[...PUBLIC_MODES]`) — Compare.tsx:16 [DERIVED]
  fails-if: comparison silently drops an arm mode the contract expects.
INVARIANT: `run()` fires only when `q.trim() != ""` and `modes.length > 0` — Compare.tsx:22 [DERIVED]
  fails-if: empty request sent to `api.compare`.
INVARIANT: lanes-fired display = `lane_sizes` entries with `v > 0` minus keys `union`, `union_uncapped` — Compare.tsx:86-87 [DERIVED]
  fails-if: aggregate lanes shown as if they were real retrieval lanes.
INVARIANT: entities page size == relationships page size == 25 — Graph.tsx:20, 23 [DERIVED]
  fails-if: paging contract with backend drifts per list.
INVARIANT: relationships rendered == source-attested only; withheld count == `dropped_unattested` — Graph.tsx:87-92 [DERIVED]
  fails-if: unattested facts displayed as canonical truth (violates the stated rule, Graph.tsx:10-13).
INVARIANT: Login submit disabled while `busy || !username.trim() || !password` — Login.tsx:61 [DERIVED]
  fails-if: empty credentials submitted to `/auth/login`.
INVARIANT: Overview readiness verdicts derive only from `controlPlane` + `semanticReadiness`, never `query_ready` — Overview.tsx:30-34, 47-53 [DERIVED]
  fails-if: a `true` `query_ready` masks semantic incompleteness (stated counter-example, Overview.tsx:50-52).
INVARIANT: Reports `refresh` order is `setSeen({})` then `setNonce(n + 1)` — Reports.tsx:23 [DERIVED]
  fails-if: stale panel status survives a list reload.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: Compare.tsx:25, Graph.tsx:20-25, Login.tsx:33/90, Overview.tsx:12-14, Reports.tsx:17; rendering itself is pure given state) [INFERRED — React components, only I/O is the api/auth calls]
idempotency: SAFE for all reads (Compare/Graph/Overview/Reports fetch only). `auth.changePassword` has server-side effect — success banner states other devices are signed out (Login.tsx:111). [DERIVED]

## failure behaviour
- Compare: `catch (e)` sets `err` to `e instanceof Error ? e.message : String(e)`; per-arm failures shown when `!arms.every((a) => a.ok)` as `{a.mode}: {a.error}` (Compare.tsx:26-27, 103-106).
- Graph: `ents.error` / `rels.error` rendered as `banner--bad`; no pick → relationships resolve `null` (Graph.tsx:52, 83, 22-24).
- Login: failure → `signInProblem(err)` message, password field cleared (Login.tsx:34-37).
- ChangePassword: `BAD_PASSWORD` → "The current password is wrong."; other `ApiError` → `detailMessage`; else `String(err)` (Login.tsx:94-97).
- Overview: single banner from `cp.error ?? sr.error` (Overview.tsx:17, 28).
- Reports: list rejection → `ErrorState` with `onRetry={refresh}` (Reports.tsx:17, 35-36).
- Error codes consumed: `BAD_LOGIN`, `TOO_MANY_ATTEMPTS`, `OWNER_PASSWORD_NOT_SET`, `LOGIN_NOT_CONFIGURED` (Login.tsx:11-15), `BAD_PASSWORD` (Login.tsx:96).

## dumb-code flags
- Magic slice lengths: `d.slice(0, 14)` (Compare.tsx:118), `s.doc_id.slice(0, 16)` (Graph.tsx:103), `s.text.slice(0, 260)` (Graph.tsx:104).
- Page-size literal `25` duplicated (Graph.tsx:20, 23).
- `.replace(/\s+/g, " ")` repeated 5× (Graph.tsx:64, 66, 80, 96, 98).
- Sentinel `-1` in `shared.length === (arms[0]?.retrieval?.documents?.length ?? -1)` (Compare.tsx:123).
- Lane-name literals `"union"` / `"union_uncapped"` hardcoded in the display filter (Compare.tsx:87).
- Pluralization ternary `` `${row.uploads.toLocaleString()} upload${row.uploads === 1 ? "" : "s"}` `` (Reports.tsx:62).
- Style inconsistency: `!password` (Login.tsx:61) vs `next.length === 0` (Login.tsx:121) — same check, two spellings.
- `sr.data.vnext?.pending?.length > 0` compares a possibly-`undefined` length; `undefined > 0` is `false`, so pending-absent falls through (Overview.tsx:70).

## refactor notes
- Exported prop shapes are the routing contract: `corpusId` (Compare/Graph/Overview), `onSignedIn` (Login), `me`/`forced`/`onChanged`/`onSignOut` (ChangePassword); importers are `frontend-v2/src/App.tsx` and `frontend-v2/src/screens/Settings.tsx` (FACTS.importers) — renaming breaks both.
- `signInProblem` code strings must stay in sync with backend `/auth/login` codes (Login.tsx:7-17).
- Compare consumes `CompareResponse` fields `arms[].mode`, `latency_ms`, `ok`, `error` and `retrieval.{documents, union_size, evidence_count, selected_documents, selected_sections, degraded, lane_sizes}` (Compare.tsx:31-35, 84-97) — contract change ripples into the table.
- Graph consumes `GraphEntity.{entity_id, normalized_surface, surface, core_type, mentions, documents}` (Graph.tsx:57-70) and relationship `{fact_id, subject, predicate, object, direction, sources[{chunk_id, source_name, doc_id, text}]}` (Graph.tsx:93-105).
- Overview depends on `controlReady`, `semanticReady`, `vnextReady`, `settled` from `../lib/readiness` (Overview.tsx:3, 30-34).
- Reports depends on `reportApi`, `reportRows`, `reportHref`, `reportStatus`, `errorWords`, `when`, `ReportRow` from `../lib/productReport` and `ReportPanel` (Reports.tsx:1-3); upload token lives in page memory only per ADR-0023 comment (Reports.tsx:12-13).
- No DB/env access in this unit (FACTS `tables_read: []`, `tables_written: []`) — refactors stay inside the React/api-client boundary.

## VERIFY
```verify
grep -Fq 'export function Compare({ corpusId }: { corpusId: string })' frontend-v2/src/screens/Compare.tsx
grep -Fq 'api.graphEntities(corpusId, term, 25, s)' frontend-v2/src/screens/Graph.tsx
grep -Fq 'case "OWNER_PASSWORD_NOT_SET":' frontend-v2/src/screens/Login.tsx
grep -Fq 'const err = cp.error ?? sr.error;' frontend-v2/src/screens/Overview.tsx
grep -Fq 'reportApi.list(s).then(reportRows, (e: unknown) => { throw new Error(errorWords(e)); })' frontend-v2/src/screens/Reports.tsx
grep -Fq 'function ReportItem({ row, status, open, onToggle, onStatus }:' frontend-v2/src/screens/Reports.tsx
! grep -Fq 'api.chat' frontend-v2/src/screens/Compare.tsx
```
