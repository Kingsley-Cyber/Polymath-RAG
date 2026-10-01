# unit: frontend-v2/src/screens/_small-modules
anchor: frontend-v2/src/screens/Compare.tsx:1-134 · frontend-v2/src/screens/Graph.tsx:1-118 · frontend-v2/src/screens/Login.tsx:1-141 · frontend-v2/src/screens/Overview.tsx:1-79

## purpose
Four UI screens for the Polymath web shell: Compare (one question across retrieval modes, F6), Graph (source-attested entity/relationship browse, F9), Login/ChangePassword (single-profile auth, ONE-PROFILE), Overview (readiness triad landing, F1) — frontend-v2/src/screens/Compare.tsx:6-13, Graph.tsx:8-13, Login.tsx:20-21, Overview.tsx:7-9 [DERIVED]. Consumers: `frontend-v2/src/App.tsx` and `frontend-v2/src/screens/Settings.tsx` (FACTS.importers) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Compare` | function component | `({ corpusId }: { corpusId: string })` -> JSX | Compare.tsx:14 | App.tsx, Settings.tsx (unit importers) |
| `Graph` | function component | `({ corpusId }: { corpusId: string })` -> JSX | Graph.tsx:15 | App.tsx, Settings.tsx (unit importers) |
| `signInProblem` | function | `(err: unknown)` -> string | Login.tsx:8 | Login (internal) |
| `Login` | function component | `({ onSignedIn }: { onSignedIn: (me: Me) => void })` -> JSX | Login.tsx:22 | App.tsx, Settings.tsx (unit importers) |
| `ChangePassword` | function component | `({ me, forced?, onChanged, onSignOut }: { me: Me; forced?: boolean; onChanged: (me: Me) => void; onSignOut?: () => void })` -> JSX | Login.tsx:72-77 | App.tsx, Settings.tsx (unit importers) |
| `Overview` | function component | `({ corpusId }: { corpusId: string })` -> JSX | Overview.tsx:11 | App.tsx, Settings.tsx (unit importers) |

FACTS lists importers per unit only; per-symbol attribution is not available.

## contracts

**Compare** (COMPARE-RETRIEVAL-V1)
- in: `corpusId: string`; state `q`, `modes` initialized to `[...PUBLIC_MODES]` — Compare.tsx:15-16 [DERIVED]
- out: one `api.compare({ message: q.trim(), corpus_id: corpusId, modes })` call; all arms run inside that single request, retrieval only, no synthesis — Compare.tsx:25, 9-11 [DERIVED]
- pre: `run()` returns early if `!q.trim() || !modes.length` — Compare.tsx:22 [DERIVED]
- post: on success `res: CompareResponse | null` set; on failure `err` set; `busy` cleared in `finally` — Compare.tsx:23-28 [DERIVED]

**Graph** (GRAPH-BROWSE-V1)
- in: `corpusId: string`; search term applied only on Enter/Search — Graph.tsx:16-17, 41-45 [DERIVED]
- out: entities via `api.graphEntities(corpusId, term, 25, s)`; relationships via `api.graphRelationships(picked.entity_id, corpusId, 25, s)` — Graph.tsx:20, 23 [DERIVED]
- pre: relationship fetch only when `picked?.entity_id` truthy, else `Promise.resolve(null)` — Graph.tsx:22-25 [DERIVED]
- post: a relationship is rendered only when backend Postgres `evidence` ties its fact to a chunk in this corpus; unattested ones are withheld and surfaced as `dropped_unattested` count — Graph.tsx:10-13, 87-92 [DERIVED]

**signInProblem**
- in: `err: unknown`; code read via `err instanceof ApiError ? err.code : null` — Login.tsx:9 [DERIVED]
- out: mapped strings for `"BAD_LOGIN"`, `"TOO_MANY_ATTEMPTS"` ("Wait 15 minutes"), `"OWNER_PASSWORD_NOT_SET"`, `"LOGIN_NOT_CONFIGURED"`; default `` `Couldn't sign in: ${...}` `` — Login.tsx:11-16 [DERIVED]

**Login**
- in: `onSignedIn: (me: Me) => void` — Login.tsx:22 [DERIVED]
- pre: submit disabled while `busy || !username.trim() || !password` — Login.tsx:61 [DERIVED]
- post: success → `onSignedIn(await auth.login(username.trim(), password))` (username trimmed, password not); failure → `signInProblem` message + password field cleared — Login.tsx:33-36 [DERIVED]

**ChangePassword**
- in: `me`, `forced?`, `onChanged`, `onSignOut?` — Login.tsx:72-77 [DERIVED]
- pre: submit disabled while `busy || !current || next.length === 0` — Login.tsx:121 [DERIVED]
- post: success → done banner "Password changed. Other devices are signed out." + `onChanged(updated)`; `"BAD_PASSWORD"` → "The current password is wrong." — Login.tsx:90-97, 111 [DERIVED]

**Overview**
- in: `corpusId: string` — Overview.tsx:11 [DERIVED]
- out: three parallel fetches `api.controlPlane`, `api.semanticReadiness`, `api.corpora`; triad verdicts via `settled(cp, (d) => controlReady(d?.control_ready))`, `settled(sr, semanticReady)`, `settled(sr, vnextReady)` — Overview.tsx:12-14, 30-34 [DERIVED]
- post: legacy `query_ready`/`query_enabled`/`documents` shown only inside a collapsible counter-example `<details>`; never used as a readiness signal — Overview.tsx:37-53 [DERIVED]

## effect surface
- Network (via `../lib/api`, `../lib/auth`): `api.compare` Compare.tsx:25; `api.graphEntities` Graph.tsx:20; `api.graphRelationships` Graph.tsx:23; `auth.login` Login.tsx:33; `auth.changePassword` Login.tsx:90; `api.controlPlane`/`api.semanticReadiness`/`api.corpora` Overview.tsx:12-14 [DERIVED]
- Postgres: none read/written directly (FACTS `tables_read: []`, `tables_written: []`); Graph.tsx:11 documents that attestation happens server-side against Postgres `evidence` [DERIVED]
- No files, subprocesses, or env flags in these files [DERIVED]

## invariants

INVARIANT: modes initial value == `[...PUBLIC_MODES]` (all public modes pre-checked) — Compare.tsx:16 [DERIVED]
  fails-if: compare silently starts with a partial/empty arm set, changing the benchmark baseline.
INVARIANT: "Lanes fired" counts only `lane_sizes` entries with `v > 0` and `k` not in `{"union", "union_uncapped"}` — Compare.tsx:86-87 [DERIVED]
  fails-if: union rows pollute the per-lane display with double-counted sizes.
INVARIANT: entity page size == relationship page size == `25` — Graph.tsx:20, 23 [DERIVED]
  fails-if: lists paginate differently than the backend default callers expect.
INVARIANT: entity row is clickable iff `e.entity_id` truthy — Graph.tsx:61-66 [DERIVED]
  fails-if: picking an entity without `entity_id` fires a relationship fetch keyed on `undefined`.
INVARIANT: username is sent as `username.trim()`, password untrimmed — Login.tsx:33 [DERIVED]
  fails-if: usernames with stray spaces authenticate differently across screens.
INVARIANT: overlap banner fires iff `shared.length === (arms[0]?.retrieval?.documents?.length ?? -1) && arms.length > 1` — Compare.tsx:123 [DERIVED]
  fails-if: banner claims "same documents" without full-set equality across all arms (see dumb-code flags).

## determinism & idempotency
determinism: NONDETERMINISTIC (network — Compare.tsx:25, Graph.tsx:20/23, Login.tsx:33/90, Overview.tsx:12-14; async settle order drives loading/error state). No clock/random/uuid/env reads in these files [DERIVED].
idempotency: SAFE — Compare/Graph/Overview only fetch; Login/ChangePassword submits are user-triggered and re-runnable, but each successful `auth.changePassword` signs out other devices (Login.tsx:111) [DERIVED].

## failure behaviour
- Compare: whole-request failure → `err` banner with `e instanceof Error ? e.message : String(e)`, `busy` reset in `finally` — Compare.tsx:26-28 [DERIVED]. Per-arm failure: arms with `!a.ok` listed with `a.error` under the table; other arms still rendered — Compare.tsx:103-107 [DERIVED]. Missing numeric fields render as `"—"` via `??` fallbacks — Compare.tsx:92-96 [DERIVED].
- Graph: `ents.error`/`rels.error` rendered as `banner--bad`; no picked entity → no relationship fetch (`Promise.resolve(null)`) — Graph.tsx:22-25, 52, 83 [DERIVED].
- Login/ChangePassword: consume codes `BAD_LOGIN`, `TOO_MANY_ATTEMPTS`, `OWNER_PASSWORD_NOT_SET`, `LOGIN_NOT_CONFIGURED`, `BAD_PASSWORD`; unknown `ApiError` → `detailMessage`, else `String(err)` — Login.tsx:11-16, 95-97 [DERIVED]. No error codes raised by these files.
- Overview: `err = cp.error ?? sr.error` shown as one banner; `corpora` error is never surfaced — Overview.tsx:17, 28 [DERIVED].

## dumb-code flags
- Magic truncations: `d.slice(0, 14)` Compare.tsx:118, `doc_id.slice(0, 16)` Graph.tsx:103, `s.text.slice(0, 260)` Graph.tsx:104 — unexplained, and `…` is appended even when text is shorter than 260 — Graph.tsx:104 [DERIVED].
- Duplicated literal `25` (page size) — Graph.tsx:20, 23 [DERIVED].
- Empty-string checks styled inconsistently: `!password` (Login.tsx:61) vs `next.length === 0` (Login.tsx:121) — same semantics, two forms [DERIVED].
- Predicate pill is always `pill pill--unknown` regardless of predicate type — Graph.tsx:98 [DERIVED].
- Overlap banner compares only against `arms[0]` document count; an arm with extra unique documents beyond arm 0 still triggers "Every arm selected the same documents" — Compare.tsx:123 [INFERRED: `shared` is the intersection, so equality with arm 0's count only proves arm 0 ⊆ every arm, not set equality of all arms].
- `Overview` swallows `corpora` failure silently: `err` covers only `cp.error ?? sr.error`, so the details card just disappears — Overview.tsx:14, 17 [INFERRED: no render path shows `corpora.error`].

## refactor notes
- Error-code strings are the wire contract with `/auth/login` and change-password: changing the switch/default in `signInProblem` or the `BAD_PASSWORD` branch desynchronizes UI messages from server codes — Login.tsx:10-17, 95-97 [DERIVED].
- `PUBLIC_MODES` (from `../lib/contracts`) controls both the default arm set and the checkbox list; renaming/removing modes changes Compare's initial state and UI at once — Compare.tsx:3, 16, 57 [DERIVED].
- Readiness helper names (`settled`, `controlReady`, `semanticReady`, `vnextReady` from `../lib/readiness`) and `ReadinessTriad` props are wired positionally in Overview; signature changes break the triad — Overview.tsx:3-4, 30-34 [DERIVED].
- Component prop shapes (`corpusId`, `onSignedIn`, `forced`, `onChanged`, `onSignOut`) are the blast radius for App.tsx and Settings.tsx — Login.tsx:22, 72-77; FACTS.importers [DERIVED].
- Backend field drift (`lane_sizes` keys `union`/`union_uncapped`, `dropped_unattested`, `latency_ms`, `ok`, `error`, `vnext.pending`) degrades to `"—"`/hidden banners rather than errors — Compare.tsx:86-96, Graph.tsx:87-92, Overview.tsx:70-73 [INFERRED: `??` fallbacks hide missing fields].

## VERIFY
```verify
grep -Fq 'api.compare({ message: q.trim(), corpus_id: corpusId, modes })' frontend-v2/src/screens/Compare.tsx
grep -Fq 'k !== "union" && k !== "union_uncapped"' frontend-v2/src/screens/Compare.tsx
grep -Fq 'api.graphRelationships(picked.entity_id, corpusId, 25, s)' frontend-v2/src/screens/Graph.tsx
grep -Fq 'dropped_unattested' frontend-v2/src/screens/Graph.tsx
grep -Fq 'case "OWNER_PASSWORD_NOT_SET":' frontend-v2/src/screens/Login.tsx
grep -Fq 'V2 never uses it as a readiness signal' frontend-v2/src/screens/Overview.tsx
! grep -Fq 'queryReady' frontend-v2/src/screens/Overview.tsx
test "$(grep -c -F 'PasswordInput' frontend-v2/src/screens/Login.tsx)" -ge 4
```
