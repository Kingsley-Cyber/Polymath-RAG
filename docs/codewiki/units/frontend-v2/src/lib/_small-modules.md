# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-105

Seven leaf helper modules for the frontend-v2 React app: an appearance store (mode + accent, per browser), the auth/keys API client, chat-session persistence, chunk-id extraction from receipts, a composer-settings store, readiness-verdict painting, and a fetch-on-mount hook. [DERIVED] The unit is imported by `frontend-v2/src/App.tsx`, `frontend-v2/src/_small-modules`, and `frontend-v2/src/lib/deep.ts` (FACTS.importers); it depends on `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/contracts.ts` (FACTS.imports). [DERIVED]

## public surface

Unit-level importers (FACTS.importers): `App.tsx`, `_small-modules`, `lib/deep.ts`; per-symbol callers are not in FACTS, so the column reads "unit¹".

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Mode | type | `"light" \| "dark" \| "system"` | appearance.ts:6 | unit¹ |
| Accent | type | `"indigo" \| "teal" \| "amber" \| "rose"` | appearance.ts:7 | unit¹ |
| Appearance | interface | `{ mode: Mode; accent: Accent }` | appearance.ts:8 | unit¹ |
| APPEARANCE_KEY | const | `= "polymath.appearance"` | appearance.ts:10 | unit¹ |
| LEGACY_THEME_KEY | const | `= "polymath-v2.theme"` | appearance.ts:11 | unit¹ |
| MODES | const | `readonly Mode[]` (3 entries) | appearance.ts:12 | unit¹ |
| ACCENTS | const | `readonly Accent[]` (4 entries) | appearance.ts:13 | unit¹ |
| DEFAULT_APPEARANCE | const | `{ mode: "system", accent: "indigo" }` | appearance.ts:14 | unit¹ |
| migrateLegacy | function | `(id: string \| null \| undefined) -> Appearance` | appearance.ts:30 | unit¹ |
| loadAppearance | function | `() -> Appearance` | appearance.ts:44 | unit¹ |
| resolveMode | function | `(mode: Mode, dark = prefersDark()) -> "light" \| "dark"` | appearance.ts:59 | unit¹ |
| applyAppearance | function | `(a: Appearance, root: HTMLElement = document.documentElement) -> void` | appearance.ts:63 | unit¹ |
| getAppearance / setAppearance | function | `() -> Appearance` / `(next: Appearance) -> void` | appearance.ts:72,74 | unit¹ |
| useAppearance | function | `() -> [Appearance, (a: Appearance) => void]` | appearance.ts:90 | unit¹ |
| initAppearance | function | `() -> Appearance` | appearance.ts:96 | unit¹ |
| Me | interface | username, display_name, is_owner, must_change_password, principal_id, local, `web_password_set?` | auth.ts:9-19 | unit¹ |
| ApiKey / CreatedKey / MyKeys | interface | key metadata / + `key, prompt, shown_once` / + is_owner, max_active, mcp_url, `note?` | auth.ts:21-40 | unit¹ |
| ConnectPrompt / OwnerKey | interface | prompt, placeholder, mcp_url, `key_included?`, `connect_command?` / key, mcp_url, prompt | auth.ts:44-57 | unit¹ |
| LEGACY_OWNER | const | `Me` fallback, `principal_id: "prn_owner"` | auth.ts:63-65 | unit¹ |
| normalizeMe | function | `(raw: unknown) -> Me` | auth.ts:67 | unit¹ |
| auth | const | object of 10 endpoint methods | auth.ts:73-88 | unit¹ |
| privateLibrary | function | `(me: Me) -> string \| null` | auth.ts:91 | unit¹ |
| copyText | function | `(text: string) -> Promise<boolean>` | auth.ts:96 | unit¹ |
| ChatSession | interface | id, title, corpusId, createdAt, updatedAt, turns | chatStore.ts:19-26 | unit¹ |
| INTERRUPTED | const | error copy for unfinished turns | chatStore.ts:29-30 | unit¹ |
| newSessionId | function | `() -> string` (`c_<ms36>_<rand>`) | chatStore.ts:33 | unit¹ |
| emptySession / titleFor | function | `(corpusId: string) -> ChatSession` / `(s: ChatSession) -> string` | chatStore.ts:37,43 | unit¹ |
| loadSessions / saveSessions | function | `() -> ChatSession[]` / `(sessions: ChatSession[]) -> void` | chatStore.ts:49,72 | unit¹ |
| chunkIdOf | function | `(row: Record<string, unknown> \| null \| undefined) -> string` | chunkid.ts:14 | unit¹ |
| ComposerSettings | interface | `{ mode: PublicMode; model: string; corpusExplore: boolean }` | composerSettings.ts:11 | unit¹ |
| COMPOSER_SETTINGS_KEY | const | `= "polymath-v2.chat-settings"` | composerSettings.ts:13 | unit¹ |
| DEFAULT_COMPOSER_SETTINGS | const | `{ mode: "HYBRID", model: "", corpusExplore: false }` | composerSettings.ts:15 | unit¹ |
| getComposerSettings / setComposerSettings | function | `() -> ComposerSettings` / `(next) -> void` | composerSettings.ts:51,58 | unit¹ |
| updateComposerSettings | function | `(patch: Partial<ComposerSettings>) -> void` | composerSettings.ts:65 | unit¹ |
| useComposerSettings | function | `() -> [ComposerSettings, (patch) => void]` | composerSettings.ts:77 | unit¹ |
| ReadyState / Verdict | type / interface | `"ready" \| "blocked" \| "degraded" \| "unknown"` / `{ state, label, detail? }` | readiness.ts:14,16-21 | unit¹ |
| controlReady / semanticReady / vnextReady | function | `(sr-or-cr \| null) -> Verdict` | readiness.ts:33,39,47 | unit¹ |
| docSearchable / docVnext | function | `(d: DocSummary \| null \| undefined) -> boolean` / `(d: DocSummary) -> Verdict` | readiness.ts:62,68 | unit¹ |
| CHECKING / settled | const / function | `{ state: "unknown", label: "CHECKING" }` / `(a, verdict) -> Verdict` | readiness.ts:82,84 | unit¹ |
| Async / useAsync | interface / function | `{ data, error, loading }` / `<T>(fn, deps) -> Async<T>` | useAsync.ts:3,6 | unit¹ |

## contracts

**loadAppearance** — appearance.ts:44-53
- in: none; reads `localStorage["polymath.appearance"]` (appearance.ts:48)
- out: valid stored `{mode, accent}` (appearance.ts:49), else legacy `polymath-v2.theme` migrated (appearance.ts:51-52), else `DEFAULT_APPEARANCE`
- post: never throws — JSON.parse guarded by catch (appearance.ts:44-53), missing `localStorage` returns `DEFAULT_APPEARANCE` (appearance.ts:45-46)

**setAppearance** — appearance.ts:74-80
- in: full `Appearance`
- post: writes `APPEARANCE_KEY` JSON, removes `LEGACY_THEME_KEY` (appearance.ts:77), sets `root.dataset.mode`/`root.dataset.accent` via `applyAppearance` (appearance.ts:78), notifies listeners (appearance.ts:79)

**migrateLegacy** — appearance.ts:17-32
- in: legacy theme id, one of `""`, obsidian, graphite, nord, espresso, solar, rose, slate, paper, champagne (appearance.ts:17-29)
- out: nearest `{mode, accent}`; unknown/null id -> `DEFAULT_APPEARANCE` (appearance.ts:31-32)

**normalizeMe** — auth.ts:67-71
- in: raw `/auth/me` body
- out: `Me`; if `is_owner` is not boolean or `username` not string -> `LEGACY_OWNER` (auth.ts:69); otherwise `{ ...LEGACY_OWNER, ...m, local: Boolean(m.local) }` (auth.ts:70)

**privateLibrary** — auth.ts:91-93
- in: `Me`
- out: `null` iff `me.is_owner`, else `` `fr-${me.username}` `` (auth.ts:92)

**copyText** — auth.ts:96-119
- out: `true` if `navigator.clipboard.writeText` succeeds (auth.ts:98-100), else hidden-textarea + `document.execCommand("copy")` result (auth.ts:105-116), else `false`; never throws

**loadSessions** — chatStore.ts:49-70
- out: rows with string `id` and array `turns` only (chatStore.ts:57-60); every turn with `done` falsy rewritten to `done: true, error: t.error ?? INTERRUPTED` (chatStore.ts:63-65); any parse failure -> `[]` (chatStore.ts:68-69)

**saveSessions** — chatStore.ts:72-84
- pre: sessions with `turns.length > 0` only (blank "New chat" never persisted, chatStore.ts:74-77)
- post: sorted by `updatedAt` desc, sliced to `MAX_SESSIONS = 50`, written to `localStorage["polymath-v2.chats"]` (chatStore.ts:76-80); quota/private-mode errors swallowed (chatStore.ts:81-83)

**chunkIdOf** — chunkid.ts:14-26
- in: receipt row
- out: `row.chunk_id` when a nonempty string (chunkid.ts:17-18); else locator `"chunk:<id>@<start>:<end>"` parsed to the `<id>` before `@` (chunkid.ts:20-24); else `""`

**getComposerSettings** — composerSettings.ts:51-56
- out: parsed stored string, re-parsed only when the raw string changed (stable reference for `useSyncExternalStore`, composerSettings.ts:45-48); no storage -> in-memory `cached` for the session

**docSearchable / docVnext** — readiness.ts:62-77
- `docSearchable` = `d.vnext_ready || (d.map_unresolved === 0 && d.profile_present)` (readiness.ts:63)
- `docVnext`: `vnext_ready` -> `READY`; else searchable -> `{ state: "degraded", label: "READY · BASIC PROFILE" }`; else `BLOCKED` with `"<n> unresolved parents · no profile"` detail (readiness.ts:69-76)

**settled** — readiness.ts:84-86
- out: `CHECKING` iff `data == null && !error`, else `verdict(a.data)`

**useAsync** — useAsync.ts:6-21
- post: one `AbortController` per effect run (useAsync.ts:9), aborted errors ignored (useAsync.ts:15), catch converts to `e.message` or `String(e)` (useAsync.ts:16)

## effect surface

- Postgres: `tables_read = []`, `tables_written = []` (FACTS) [DERIVED]
- localStorage keys written/read: `"polymath.appearance"` (appearance.ts:10,77), `"polymath-v2.theme"` read + removed (appearance.ts:11,51-52,77), `"polymath-v2.chats"` (chatStore.ts:28,80), `"polymath-v2.chat-settings"` (composerSettings.ts:13,60)
- DOM: `document.documentElement.dataset.mode/accent` (appearance.ts:63-66); hidden textarea appended/removed for copy fallback (auth.ts:106-114); `matchMedia("(prefers-color-scheme: dark)")` listener (appearance.ts:86); `window` `"storage"` listener (composerSettings.ts:71-72)
- HTTP (all via `http` from `./api`, auth.ts:7): POST `/auth/owner-password`, GET `/auth/me`, POST `/auth/login`, POST `/auth/logout`, POST `/auth/password`, GET `/keys`, POST `/keys`, DELETE `/keys/`, GET `/keys/prompt`, GET `/keys/owner` (auth.ts:75-87; FACTS.api_calls)
- No env flags, Qdrant collections, or subprocesses appear in SOURCE/FACTS

## invariants

INVARIANT: persisted session count ≤ `MAX_SESSIONS = 50` — chatStore.ts:31,79 [DERIVED]
  fails-if: blank or stale chats evict real conversations (the filter at chatStore.ts:77 is what keeps blanks out)
INVARIANT: `DEFAULT_APPEARANCE` = `{ mode: "system", accent: "indigo" }` and equals `LEGACY[""]` — appearance.ts:14,18 [DERIVED]
  fails-if: the "" legacy id and the no-preference default diverge on migration
INVARIANT: `MODES` length = 3, `ACCENTS` length = 4; `valid()` requires membership in both — appearance.ts:12-13,34-37 [DERIVED]
  fails-if: a stored mode/accent outside the lists is silently replaced by the default
INVARIANT: `DEFAULT_COMPOSER_SETTINGS.model = ""` means "backend default, nothing picked" — composerSettings.ts:14-15 [DERIVED]
  fails-if: treating `""` as a real model id sends an invalid model
INVARIANT: `docSearchable(d)` ⇔ `d.vnext_ready || (d.map_unresolved === 0 && d.profile_present)` — readiness.ts:63 [DERIVED]
  fails-if: files with only the base profile get labelled Blocked despite being searchable
INVARIANT: `privateLibrary(me) = null` iff `me.is_owner = true`, else `fr-<username>` — auth.ts:91-93 [DERIVED]
  fails-if: friend uploads route to the wrong corpus id
INVARIANT: `titleFor` truncates at 42 chars via `q.slice(0, 41)` + `"…"` — chatStore.ts:46 [DERIVED]
INVARIANT: `settled` returns `CHECKING` iff `data == null && error == null` — readiness.ts:85-86 [DERIVED]
  fails-if: loading state painted as "UNKNOWN — /control_plane not reachable" (readiness.ts:80-81)
INVARIANT: unfinished persisted turns always get `done: true` and an error (`INTERRUPTED` default) — chatStore.ts:63-65 [DERIVED]
  fails-if: a reloaded thread reads as busy forever (chatStore.ts:61-62)

## determinism & idempotency

determinism: NONDETERMINISTIC — `Date.now()` + `Math.random()` in `newSessionId` (chatStore.ts:34), OS theme via `matchMedia` (appearance.ts:56,86), network in the 10 auth endpoints (auth.ts:75-87), cross-window `storage` events (composerSettings.ts:71). Pure given inputs: `migrateLegacy`, `resolveMode`, `chunkIdOf`, `titleFor`, `clean`/`parse`, all readiness painters. [DERIVED]
idempotency: SAFE for stores (single-key last-write-wins: appearance.ts:77, chatStore.ts:80, composerSettings.ts:60); UNSAFE for `auth.createKey` (POST `/keys` mints a new key per call, auth.ts:83). [DERIVED]

## failure behaviour

- `storage()` returns null on any throw — appearance.ts:39-41, composerSettings.ts:17-19; callers then use defaults or session memory. [DERIVED]
- `loadAppearance` catch -> falls through to the legacy key (appearance.ts:50-52); `setAppearance` catch swallows write failure ("private mode", appearance.ts:77). [DERIVED]
- `loadSessions` catch -> `[]` (chatStore.ts:68-69); `saveSessions` catch -> silent, "history is a convenience, never load-bearing" (chatStore.ts:81-83). [DERIVED]
- `parse` catch -> `DEFAULT_COMPOSER_SETTINGS` (composerSettings.ts:35); per-field `clean` fallback so one malformed field keeps the others (composerSettings.ts:23-31). [DERIVED]
- `copyText` -> `false` after both clipboard and execCommand fail (auth.ts:109-118); never rejects. [DERIVED]
- `useAsync` catch -> `error: string` state; aborted errors dropped (useAsync.ts:14-17). [DERIVED]
- `normalizeMe` on invalid shape -> `LEGACY_OWNER`, so a backend without logins renders as owner "king" — display only (auth.ts:61-70). [DERIVED]
- No error codes raised in this unit; all handlers swallow. [DERIVED]

## dumb-code flags

- `storage()` body duplicated verbatim in appearance.ts:39-41 and composerSettings.ts:17-19. [DERIVED]
- FACTS.imports lists `frontend-v2/src/lib/contracts.ts` twice. [DERIVED]
- LEGACY value collisions: `obsidian` == `graphite` -> `{ mode: "dark", accent: "indigo" }` (appearance.ts:19-20); `espresso` == `solar` -> dark/amber (appearance.ts:23-24); `paper` == `champagne` -> light/amber (appearance.ts:27-28). [DERIVED]
- `LEGACY[""] = DEFAULT_APPEARANCE` (appearance.ts:18) is redundant with the `|| DEFAULT_APPEARANCE` fallback (appearance.ts:31-32). [DERIVED]
- Magic truncation pair 42/41 in `titleFor` (chatStore.ts:46). [DERIVED]
- Media-query literal `"(prefers-color-scheme: dark)"` appears twice (appearance.ts:56,86). [DERIVED]
- Sentinel `model: ""` for "backend's default model" (composerSettings.ts:14-15). [DERIVED]
- Hand-rolled store pattern (module `current`/`cached` + `listeners` Set + `subscribe`) duplicated between appearance.ts:69-92 and composerSettings.ts:47-78. [DERIVED]
- `eslint-disable-next-line react-hooks/exhaustive-deps` with `deps` passed straight into `useEffect` (useAsync.ts:19-21). [DERIVED]

## refactor notes

- `index.html` applies the stored appearance before first paint (appearance.ts:3-5): renaming `APPEARANCE_KEY` or changing its JSON shape desyncs first paint until the next `initAppearance`. [DERIVED]
- `setAppearance` deletes `LEGACY_THEME_KEY` (appearance.ts:77); dropping that removal re-triggers legacy migration on every load (`initAppearance` checks both keys, appearance.ts:99). [DERIVED]
- `chunkIdOf` exists because receipts name chunks two ways (`chunk_id` vs `locator`); removing either branch silently zeroes Evidence/Answer-Review joins again (chunkid.ts:4-13). [DERIVED]
- readiness.ts must only paint backend verdicts — GAP-1 was UI-side composition of `/ready` + `/health/pipeline` (readiness.ts:23-31); reintroducing arithmetic here recreates the drift. [DERIVED]
- readiness.ts deliberately never reads the legacy `query_ready` boolean (readiness.ts:8-10). [DERIVED]
- `LEGACY_OWNER` fallback keeps backends without `/auth/me` (404 window) rendering as owner (auth.ts:61-70); removing it breaks those. [DERIVED]
- Only redraw fields are persisted per turn; receipt schema changes degrade stored turns' panels, by design (chatStore.ts:12-15) — do not cache derived receipt data. [DERIVED]
- The `INTERRUPTED` string is written into stored turns (chatStore.ts:63-65); rewording it leaves old copies in localStorage. [DERIVED]
- Cross-window sync of composer settings rides the `"storage"` listener (composerSettings.ts:71-72) — removing it breaks the "another window" behavior. [DERIVED]
- Blast radius: all exports feed `App.tsx`, `_small-modules`, and `lib/deep.ts` (FACTS.importers); the unit itself imports `api.ts`, `chat.ts`, `contracts.ts` (FACTS.imports). [DERIVED]

## VERIFY

```verify
grep -Fq 'APPEARANCE_KEY = "polymath.appearance"' frontend-v2/src/lib/appearance.ts
grep -Fq 'const MAX_SESSIONS = 50;' frontend-v2/src/lib/chatStore.ts
grep -Fq 'mode: "HYBRID", model: "", corpusExplore: false' frontend-v2/src/lib/composerSettings.ts
grep -Fq 'd.vnext_ready || (d.map_unresolved === 0 && d.profile_present)' frontend-v2/src/lib/readiness.ts
grep -Fq 'principal_id: "prn_owner"' frontend-v2/src/lib/auth.ts
test "$(grep -c -F 'http.' frontend-v2/src/lib/auth.ts)" -ge 10
! grep -Fq 'Math.random' frontend-v2/src/lib/composerSettings.ts
```
