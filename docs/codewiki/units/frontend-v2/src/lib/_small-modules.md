# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-105

## purpose
Shared client library for the frontend-v2 React app: browser-persisted appearance store (light/dark/system + accent), the auth/Settings HTTP client, the localStorage chat-session store, a receipt chunk-id parser, the composer settings store, and a fetch-on-mount hook. [DERIVED]
Unit-level importers (FACTS): `frontend-v2/src/App.tsx`, `frontend-v2/src/_small-modules`, `frontend-v2/src/lib/deep.ts`. Unit imports: `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/contracts.ts`. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `migrateLegacy` | function | (id: string \| null \| undefined) -> Appearance | frontend-v2/src/lib/appearance.ts:30-32 | — |
| `loadAppearance` | function | () -> Appearance | frontend-v2/src/lib/appearance.ts:43-53 | — |
| `resolveMode` | function | (mode: Mode, dark?: boolean) -> "light" \| "dark" | frontend-v2/src/lib/appearance.ts:59-61 | — |
| `applyAppearance` | function | (a: Appearance, root?: HTMLElement) -> void | frontend-v2/src/lib/appearance.ts:63-66 | — |
| `getAppearance` / `setAppearance` | function | () -> Appearance / (next: Appearance) -> void | frontend-v2/src/lib/appearance.ts:72 / 74-80 | — |
| `useAppearance` | function | () -> [Appearance, (a: Appearance) => void] | frontend-v2/src/lib/appearance.ts:90-92 | — |
| `initAppearance` | function | () -> Appearance | frontend-v2/src/lib/appearance.ts:96-104 | — |
| `DEFAULT_APPEARANCE` | const | `{ mode: "system", accent: "indigo" }` | frontend-v2/src/lib/appearance.ts:14 | — |
| `APPEARANCE_KEY` / `LEGACY_THEME_KEY` | const | `"polymath.appearance"` / `"polymath-v2.theme"` | frontend-v2/src/lib/appearance.ts:10-11 | — |
| `normalizeMe` | function | (raw: unknown) -> Me | frontend-v2/src/lib/auth.ts:74-78 | — |
| `auth` | const | object of 10 endpoint methods (see effect surface) | frontend-v2/src/lib/auth.ts:80-95 | — |
| `LEGACY_OWNER` | const | Me literal, username `"king"`, principal_id `"prn_owner"` | frontend-v2/src/lib/auth.ts:70-72 | — |
| `privateLibrary` | function | (me: Me) -> string \| null | frontend-v2/src/lib/auth.ts:98-100 | — |
| `copyText` | function | (text: string) -> Promise\<boolean\> | frontend-v2/src/lib/auth.ts:103-126 | — |
| `newSessionId` | function | () -> string | frontend-v2/src/lib/chatStore.ts:40-42 | — |
| `emptySession` | function | (corpusId: string) -> ChatSession | frontend-v2/src/lib/chatStore.ts:44-47 | — |
| `titleFor` | function | (s: ChatSession) -> string | frontend-v2/src/lib/chatStore.ts:50-54 | — |
| `loadSessions` / `saveSessions` | function | () -> ChatSession[] / (sessions: ChatSession[]) -> void | frontend-v2/src/lib/chatStore.ts:56-77 / 79-91 | — |
| `INTERRUPTED` | const | error string for unfinished turns | frontend-v2/src/lib/chatStore.ts:36-37 | — |
| `chunkIdOf` | function | (row: Record\<string, unknown\> \| null \| undefined) -> string | frontend-v2/src/lib/chunkid.ts:14-26 | — |
| `getComposerSettings` / `setComposerSettings` / `updateComposerSettings` | function | () -> ComposerSettings / (next) -> void / (patch: Partial) -> void | frontend-v2/src/lib/composerSettings.ts:51-56 / 58-63 / 65-67 | — |
| `useComposerSettings` | function | () -> [ComposerSettings, (patch) => void] | frontend-v2/src/lib/composerSettings.ts:76-79 | — |
| `DEFAULT_COMPOSER_SETTINGS` | const | `{ mode: "HYBRID", model: "", corpusExplore: false }` | frontend-v2/src/lib/composerSettings.ts:15 | — |
| `useAsync` | function | \<T\>(fn: (signal: AbortSignal) => Promise\<T\>, deps: unknown[]) -> Async\<T\> | frontend-v2/src/lib/useAsync.ts:6-21 | — |

## contracts

**loadAppearance()** — frontend-v2/src/lib/appearance.ts:43-53
- out: valid stored `{ mode, accent }` under `APPEARANCE_KEY`, else `migrateLegacy(LEGACY_THEME_KEY)`, else `DEFAULT_APPEARANCE` [DERIVED]
- post: never throws (JSON.parse and storage access both guarded) [DERIVED]

**migrateLegacy(id)** — frontend-v2/src/lib/appearance.ts:30-32
- in: legacy palette id from the 10-key `LEGACY` map (`""`, `obsidian`, `graphite`, `nord`, `espresso`, `solar`, `rose`, `slate`, `paper`, `champagne`) [DERIVED]
- out: unknown/null id -> `DEFAULT_APPEARANCE` [DERIVED]

**setAppearance(next)** — frontend-v2/src/lib/appearance.ts:74-80
- post: writes `APPEARANCE_KEY`, removes `LEGACY_THEME_KEY`, sets `root.dataset.mode` + `root.dataset.accent`, notifies listeners [DERIVED]

**initAppearance()** — frontend-v2/src/lib/appearance.ts:96-104
- pre: one-time migration only when `APPEARANCE_KEY == null && LEGACY_THEME_KEY != null` [DERIVED]
- post: returns current applied Appearance [DERIVED]

**normalizeMe(raw)** — frontend-v2/src/lib/auth.ts:74-78
- in: raw `/auth/me` payload
- out: `LEGACY_OWNER` when `is_owner`/`username` missing or wrong type; else `{ ...LEGACY_OWNER, ...m, local: Boolean(m.local) }` [DERIVED]

**privateLibrary(me)** — frontend-v2/src/lib/auth.ts:98-100
- out: `null` for owner, else `fr-${me.username}` [DERIVED]

**chunkIdOf(row)** — frontend-v2/src/lib/chunkid.ts:14-26
- in: receipt row with `chunk_id` (direct) or `locator` = `"chunk:<id>@<start>:<end>"`
- out: the id; `locator` form strips `"chunk:"` prefix and cuts at first `"@"`; `""` for null/missing [DERIVED]

**loadSessions()** — frontend-v2/src/lib/chatStore.ts:56-77
- post: every returned turn has `done: true`; unfinished ones get `error: t.error ?? INTERRUPTED` [DERIVED]
- out: `[]` on parse failure or non-array [DERIVED]

**saveSessions(sessions)** — frontend-v2/src/lib/chatStore.ts:79-91
- pre: drops sessions with `turns.length === 0`, sorts by `updatedAt` desc, keeps first `MAX_SESSIONS` [DERIVED]

**getComposerSettings()** — frontend-v2/src/lib/composerSettings.ts:51-56
- out: parse of stored string when it changed; `cached` (session value) when storage unreadable (`readRaw() === undefined`) [DERIVED]
- post: never throws; malformed fields fall back per-field via `clean` [DERIVED]

**useAsync(fn, deps)** — frontend-v2/src/lib/useAsync.ts:6-21
- post: aborts via AbortController on unmount/deps change; results after `live = false` or `ac.signal.aborted` are discarded [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| network POST | `/auth/owner-password`, `/auth/login`, `/auth/logout`, `/auth/password` | frontend-v2/src/lib/auth.ts:82-87 |
| network GET | `/auth/me`, `/keys`, `/keys/prompt`, `/keys/owner` | frontend-v2/src/lib/auth.ts:83-94 |
| network POST/DELETE | `/keys` (create), `/keys/${keyId}` (revoke) | frontend-v2/src/lib/auth.ts:90-91 |
| localStorage | `"polymath.appearance"` (write), `"polymath-v2.theme"` (read then delete) | frontend-v2/src/lib/appearance.ts:10-11,77 |
| localStorage | `"polymath-v2.chats"` (read/write) | frontend-v2/src/lib/chatStore.ts:35 |
| localStorage | `"polymath-v2.chat-settings"` (read/write) | frontend-v2/src/lib/composerSettings.ts:13 |
| DOM | `document.documentElement.dataset.mode/.accent`; hidden `<textarea>` + `document.execCommand("copy")` fallback | frontend-v2/src/lib/appearance.ts:63-66; auth.ts:113-121 |
| browser API | `matchMedia("(prefers-color-scheme: dark)")` change listener; `window` `storage` event listener | frontend-v2/src/lib/appearance.ts:86; composerSettings.ts:71-73 |
| Postgres / env flags | none (FACTS: `tables_read: []`, `tables_written: []`, `constants: []`) | — |

## invariants
INVARIANT: `MAX_SESSIONS = 50` — frontend-v2/src/lib/chatStore.ts:38 [DERIVED]
  fails-if: >50 non-empty sessions persisted; oldest by `updatedAt` silently evicted on save.
INVARIANT: LEGACY map has exactly 10 keys, all mapping to a `{mode, accent}` pair; `""` -> `DEFAULT_APPEARANCE` — frontend-v2/src/lib/appearance.ts:17-28 [DERIVED]
  fails-if: a pre-refresh palette id returns `DEFAULT_APPEARANCE` instead of its nearest mode/accent.
INVARIANT: `DEFAULT_APPEARANCE = { mode: "system", accent: "indigo" }`; `DEFAULT_COMPOSER_SETTINGS = { mode: "HYBRID", model: "", corpusExplore: false }` — frontend-v2/src/lib/appearance.ts:14; composerSettings.ts:15 [DERIVED]
  fails-if: a malformed/missing stored value resolves differently than the documented pre-refresh defaults.
INVARIANT: `MODES.length = 3`, `ACCENTS.length = 4`; `valid()` requires membership in both — frontend-v2/src/lib/appearance.ts:12-13,34-37 [DERIVED]
  fails-if: a stored unknown mode/accent falls through to the legacy key / default.
INVARIANT: every turn from `loadSessions()` has `done: true` — frontend-v2/src/lib/chatStore.ts:70-73 [DERIVED]
  fails-if: a reloaded thread renders as busy forever (the documented reason for the rewrite).
INVARIANT: `privateLibrary(owner) = null`; friend -> `fr-${username}` — frontend-v2/src/lib/auth.ts:98-100 [DERIVED]
INVARIANT: `LEGACY_OWNER = { username: "king", is_owner: true, principal_id: "prn_owner", local: true, must_change_password: false }` — frontend-v2/src/lib/auth.ts:70-72 [DERIVED]
  fails-if: a login-less backend (404 `/auth/me`) is displayed as a non-owner.
INVARIANT: `titleFor` truncates at 42 chars (`slice(0, 41)` + `"…"`) — frontend-v2/src/lib/chatStore.ts:53-54 [DERIVED]
INVARIANT: `setAppearance` removes `LEGACY_THEME_KEY` on every write — frontend-v2/src/lib/appearance.ts:77 [DERIVED]
  fails-if: stale legacy key re-migrates over a newer stored choice.

## determinism & idempotency
determinism: `chunkIdOf`, `migrateLegacy`, `resolveMode`, `normalizeMe`, `titleFor`, `clean` — DETERMINISTIC (pure data → data, chunkid.ts:14-26, appearance.ts:30-32). All storage/network paths — NONDETERMINISTIC (localStorage + `matchMedia` appearance.ts:39-41,55-57; network auth.ts:80-95; `Date.now()` + `Math.random()` in `newSessionId` chatStore.ts:41; async fetch timing useAsync.ts:12-17). [DERIVED]
idempotency: `setAppearance`/`initAppearance`/`setComposerSettings` SAFE (re-apply same value, one key overwritten). `saveSessions` SAFE but truncating (overwrite + `slice(0, MAX_SESSIONS)`). `auth.createKey` UNSAFE — each POST `/keys` returns a fresh `CreatedKey` with a new `key` [INFERRED: creation endpoint returns a one-time secret]. `copyText` SAFE.

## failure behaviour
- `storage()` returns null on throw; `loadAppearance` then returns `DEFAULT_APPEARANCE` — caller sees the default, no error — frontend-v2/src/lib/appearance.ts:39-41,45-46. [DERIVED]
- `JSON.parse` failure on `APPEARANCE_KEY` is swallowed, falls through to legacy key — appearance.ts:48-50. [DERIVED]
- `setAppearance` write failure (private mode) swallowed; value still applied in memory — appearance.ts:77. [DERIVED]
- `loadSessions` catch -> `[]`; `saveSessions` catch -> silent drop (comment: "private mode, or the 5MB quota — history is a convenience, never load-bearing") — chatStore.ts:74-76,88-90. [DERIVED]
- `copyText`: clipboard try/catch falls through to textarea + `execCommand("copy")`; final catch -> `false` — auth.ts:104-125. [DERIVED]
- `useAsync` catch -> `{ data: null, error: message, loading: false }`; aborted/unmounted results discarded — useAsync.ts:14-17. [DERIVED]
- `normalizeMe` on a 404-shaped/legacy backend -> `LEGACY_OWNER` (display only; server enforces rules) — auth.ts:68-72,74-78. [DERIVED]

## dumb-code flags
- localStorage key prefix split: `"polymath.appearance"` (no `-v2`) vs `"polymath-v2.theme"`, `"polymath-v2.chats"`, `"polymath-v2.chat-settings"` — appearance.ts:10-11, chatStore.ts:35, composerSettings.ts:13. [DERIVED]
- `storage()` helper duplicated verbatim in appearance.ts:39-41 and composerSettings.ts:17-19. [DERIVED]
- `LEGACY[""]` maps to `DEFAULT_APPEARANCE`, identical to the `|| DEFAULT_APPEARANCE` fallback in `migrateLegacy` — redundant entry — appearance.ts:18,31. [INFERRED: both branches return the same object]
- Magic numbers: `42`/`41` truncation (chatStore.ts:53-54), `50` (chatStore.ts:38), `slice(2, 8)` = 6 random chars (chatStore.ts:41). [DERIVED]
- `useAsync` disables `react-hooks/exhaustive-deps` and runs `fn` on raw `deps` — stale-closure risk is delegated to callers — useAsync.ts:19-20. [DERIVED]
- `document.execCommand("copy")` legacy fallback path — auth.ts:120. [DERIVED]

## refactor notes
- `APPEARANCE_KEY` is read by `index.html` before first paint (module comment) — renaming it breaks pre-paint application — appearance.ts:3-4,94-95. [DERIVED]
- Legacy migration is one-shot: `initAppearance` migrates only when `APPEARANCE_KEY` absent and `LEGACY_THEME_KEY` present; `setAppearance` then deletes the legacy key — removing either step orphans pre-refresh users — appearance.ts:96-102,77. [DERIVED]
- `COMPOSER_SETTINGS_KEY` is a cross-window contract: `subscribe` listens to `storage` events, another window's write re-renders — composerSettings.ts:71-73. [DERIVED]
- `chatStore` persists only redraw fields of `Turn` (from `./chat`); a receipt schema change degrades stored turns' panels by design — changing `Turn` changes stored-thread behavior — chatStore.ts:12-15. [DERIVED]
- `INTERRUPTED` is user-visible error copy — chatStore.ts:36-37. [DERIVED]
- Export renames ripple to `frontend-v2/src/App.tsx`, `frontend-v2/src/_small-modules`, `frontend-v2/src/lib/deep.ts` (FACTS.importers); the unit itself depends on `api.ts`, `chat.ts`, `contracts.ts` (FACTS.imports — `http` from api.ts:7, `Turn` from chat.ts:24, `PUBLIC_MODES` from contracts.ts:2). [DERIVED]

## VERIFY
```verify
grep -Fq 'MAX_SESSIONS = 50' frontend-v2/src/lib/chatStore.ts
grep -Fq 'polymath.appearance' frontend-v2/src/lib/appearance.ts
grep -Eq 'DEFAULT_COMPOSER_SETTINGS.*HYBRID' frontend-v2/src/lib/composerSettings.ts
grep -Fq '/auth/owner-password' frontend-v2/src/lib/auth.ts
grep -Fq 'chunk:' frontend-v2/src/lib/chunkid.ts
test "$(grep -c -F 'http.post' frontend-v2/src/lib/auth.ts)" -ge 4
! grep -Fq 'sessionStorage' frontend-v2/src/lib/chatStore.ts
```
