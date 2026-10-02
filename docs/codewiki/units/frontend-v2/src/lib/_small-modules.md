# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-105

Covers: appearance.ts (1-104), auth.ts (1-121), chatStore.ts (1-84), chunkid.ts (1-26), composerSettings.ts (1-79), useAsync.ts (1-22).

## purpose
Six small frontend-v2 client modules: per-browser theme mode/accent store (appearance.ts), the account/Settings API client (auth.ts), chat-session persistence in localStorage (chatStore.ts), receipt chunk-id extraction (chunkid.ts), a shared chat-controls settings store (composerSettings.ts), and a fetch-on-mount React hook (useAsync.ts). [DERIVED]

Unit imported by: `frontend-v2/src/App.tsx`, `frontend-v2/src/_small-modules`, `frontend-v2/src/lib/deep.ts` (FACTS.importers). Unit imports: `./api`, `./chat` (type `Turn`), `./contracts` (`PUBLIC_MODES`, `PublicMode`) — FACTS.imports, auth.ts:7, chatStore.ts:17, composerSettings.ts:2.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Mode / Accent / Appearance | type/iface | — | appearance.ts:6-8 | — |
| APPEARANCE_KEY / LEGACY_THEME_KEY / MODES / ACCENTS / DEFAULT_APPEARANCE | const | — | appearance.ts:10-14 | — |
| migrateLegacy | function | (id: string \| null \| undefined) -> Appearance | appearance.ts:30-32 | — |
| loadAppearance | function | () -> Appearance | appearance.ts:44-53 | initAppearance (appearance.ts:100) |
| resolveMode | function | (mode: Mode, dark?: boolean) -> "light" \| "dark" | appearance.ts:59-61 | applyAppearance (appearance.ts:64) |
| applyAppearance | function | (a: Appearance, root?: HTMLElement) -> void | appearance.ts:63-66 | setAppearance (appearance.ts:78) |
| getAppearance / setAppearance | function | () -> Appearance / (next: Appearance) -> void | appearance.ts:72, 74-80 | useAppearance |
| useAppearance | function | () -> [Appearance, (a: Appearance) => void] | appearance.ts:90-92 | Settings screen + top-bar toggle (comment appearance.ts:3-4) |
| initAppearance | function | () -> Appearance | appearance.ts:96-104 | start-up (comment appearance.ts:94) |
| Me / ApiKey / CreatedKey / MyKeys / ConnectPrompt / OwnerKey | interface | — | auth.ts:9-59 | — |
| LEGACY_OWNER | const | Me | auth.ts:65-67 | normalizeMe |
| normalizeMe | function | (raw: unknown) -> Me | auth.ts:69-73 | auth.me (auth.ts:78) |
| auth | const | 10 endpoint methods (see effect surface) | auth.ts:75-90 | screens (comment auth.ts:4-5) |
| privateLibrary | function | (me: Me) -> string \| null | auth.ts:93-95 | — |
| copyText | function | (text: string) -> Promise<boolean> | auth.ts:98-121 | — |
| ChatSession | interface | — | chatStore.ts:19-26 | — |
| INTERRUPTED | const | string | chatStore.ts:29-30 | loadSessions |
| newSessionId | function | () -> string | chatStore.ts:33-35 | emptySession |
| emptySession | function | (corpusId: string) -> ChatSession | chatStore.ts:37-40 | — |
| titleFor | function | (s: ChatSession) -> string | chatStore.ts:43-47 | — |
| loadSessions / saveSessions | function | () -> ChatSession[] / (sessions: ChatSession[]) -> void | chatStore.ts:49-70, 72-84 | — |
| chunkIdOf | function | (row: Record<string, unknown> \| null \| undefined) -> string | chunkid.ts:14-26 | receipt consumers (bug history chunkid.ts:4-13) |
| ComposerSettings | interface | { mode: PublicMode; model: string; corpusExplore: boolean } | composerSettings.ts:11 | — |
| COMPOSER_SETTINGS_KEY / DEFAULT_COMPOSER_SETTINGS | const | — | composerSettings.ts:13, 15 | — |
| getComposerSettings / setComposerSettings / updateComposerSettings | function | () -> ComposerSettings / (next) -> void / (patch: Partial<...>) -> void | composerSettings.ts:51-56, 58-63, 65-67 | useComposerSettings |
| useComposerSettings | function | () -> [ComposerSettings, (patch) => void] | composerSettings.ts:77-79 | components/ChatControls + screens/Chat (comment composerSettings.ts:4-6) |
| Async | interface | { data: T \| null; error: string \| null; loading: boolean } | useAsync.ts:3 | useAsync |
| useAsync | function | \<T\>(fn: (signal: AbortSignal) => Promise\<T\>, deps: unknown[]) -> Async\<T\> | useAsync.ts:6-22 | — |

## contracts

**loadAppearance() — appearance.ts:44-53**
- in: none (reads localStorage); pre: none, safe with storage unavailable.
- out: `Appearance`; post: valid stored JSON under `APPEARANCE_KEY` wins, else `LEGACY_THEME_KEY` migrated, else `DEFAULT_APPEARANCE` = `{ mode: "system", accent: "indigo" }` (appearance.ts:14). Never throws.

**setAppearance(next) — appearance.ts:74-80**
- post: writes JSON to `"polymath.appearance"`, removes `"polymath-v2.theme"`, sets `documentElement.dataset.mode/.accent`, fires listeners.

**initAppearance() — appearance.ts:96-104**
- post: migrates once when `APPEARANCE_KEY` absent and `LEGACY_THEME_KEY` present (appearance.ts:99-101); otherwise loads and applies without persisting.

**resolveMode(mode, dark = prefersDark()) — appearance.ts:59-61**
- post: `"system"` → `dark ? "dark" : "light"`; `"light"`/`"dark"` pass through.

**normalizeMe(raw) — auth.ts:69-73**
- post: raw lacking boolean `is_owner` or string `username` → `LEGACY_OWNER` (`username: "king"`, `is_owner: true`, `local: true`); else `{ ...LEGACY_OWNER, ...m, local: Boolean(m.local) }`.

**auth.ownerKey() — auth.ts:89**
- pre: called only on Show/Copy click, never on page load (comment auth.ts:88).

**privateLibrary(me) — auth.ts:93-95**
- post: `me.is_owner` → `null`; else `` `fr-${me.username}` ``.

**chunkIdOf(row) — chunkid.ts:14-26**
- post: non-empty string `chunk_id` returned as-is; else `locator` with `"chunk:"` prefix stripped and cut at first `"@"` (example comment: `"chunk:chunk_abc123@365:564"` → `"chunk_abc123"`); else `""`.

**loadSessions() — chatStore.ts:49-70**
- post: rows without string `id` or array `turns` dropped; every turn with falsy `done` becomes `{ ...t, done: true, error: t.error ?? INTERRUPTED }` (chatStore.ts:64-65); storage is not written back.

**saveSessions(sessions) — chatStore.ts:72-84**
- post: only sessions with `turns.length > 0` persisted, sorted `updatedAt` desc, capped at `MAX_SESSIONS = 50`.

**getComposerSettings() — composerSettings.ts:51-56**
- post: same object reference while the stored string is unchanged (required by `useSyncExternalStore`, comment composerSettings.ts:45-46); malformed fields fall back per-field via `clean` (composerSettings.ts:24-31).

**useAsync(fn, deps) — useAsync.ts:6-22**
- post: cleanup sets `live = false` and aborts; late resolutions and aborted errors dropped (useAsync.ts:13-18).

## effect surface
- Network (via `http` from `./api`, auth.ts:7): POST `/auth/owner-password` auth.ts:77; GET `/auth/me` auth.ts:78; POST `/auth/login` auth.ts:79; POST `/auth/logout` auth.ts:80; POST `/auth/password` auth.ts:82; GET `/keys` auth.ts:84; POST `/keys` auth.ts:85; DELETE `/keys/${keyId}` auth.ts:86; GET `/keys/prompt` auth.ts:87; GET `/keys/owner` auth.ts:89. [DERIVED]
- localStorage: `"polymath.appearance"` read appearance.ts:48 / written appearance.ts:77; `"polymath-v2.theme"` read appearance.ts:51,99 / removed appearance.ts:77; `"polymath-v2.chats"` read chatStore.ts:51 / written chatStore.ts:80; `"polymath-v2.chat-settings"` read composerSettings.ts:42 / written composerSettings.ts:60. [DERIVED]
- DOM/browser: `document.documentElement.dataset.mode/.accent` appearance.ts:63-66; `matchMedia("(prefers-color-scheme: dark)")` appearance.ts:56,86; window `"storage"` listener composerSettings.ts:71-72; `navigator.clipboard.writeText` + hidden textarea + `document.execCommand("copy")` auth.ts:100-116. [DERIVED]
- Postgres: none (FACTS.tables_read=[], tables_written=[]). Qdrant/subprocess/env flags: none visible.

## invariants
INVARIANT: persisted chat session count ≤ `MAX_SESSIONS = 50` — chatStore.ts:31,79 [DERIVED]
  fails-if: quota overflow; `saveSessions` swallows the write and history is silently lost (chatStore.ts:81-83).
INVARIANT: `titleFor` output ≤ 42 chars (`q.length > 42` → `q.slice(0, 41)` + `"…"`) — chatStore.ts:46 [DERIVED]
  fails-if: sidebar labels exceed the intended one-line size.
INVARIANT: every `LEGACY` value's `mode` ∈ `MODES` and `accent` ∈ `ACCENTS` (10 entries: `""` + 9 palettes) — appearance.ts:17-28 vs 12-13 [DERIVED]
  fails-if: `loadAppearance`'s legacy path (appearance.ts:51-52) bypasses `valid()` and can emit an appearance `valid()` would reject.
INVARIANT: `LEGACY[""]` = `DEFAULT_APPEARANCE` = `{ mode: "system", accent: "indigo" }` — appearance.ts:14,18 [DERIVED]
  fails-if: the never-chosen default diverges between the two paths.
INVARIANT: `normalizeMe` result `.local` is always boolean (`Boolean(m.local)`) — auth.ts:72 [DERIVED]
  fails-if: `Me.local: boolean` consumers get `undefined`.
INVARIANT: `privateLibrary(me)` ≠ null iff `me.is_owner = false` — auth.ts:93-95 [DERIVED]
  fails-if: an owner gets a phantom `fr-*` library id, or a friend's library id is lost.
INVARIANT: `getComposerSettings` returns the same reference while the stored string is unchanged — composerSettings.ts:51-56 [DERIVED]
  fails-if: `useSyncExternalStore` re-render loop (the stated reason for the cache, composerSettings.ts:45-46).
INVARIANT: `chunkIdOf` on a locator row = text before first `"@"` after `"chunk:"` strip — chunkid.ts:19-24 [DERIVED]
  fails-if: chunk_id/locator joins go back to zero matches and one chunk renders as two rows (recorded bug, chunkid.ts:6-13).
INVARIANT: session id = `` `c_${Date.now().toString(36)}_${6 random base36 chars}` `` — chatStore.ts:34 [DERIVED]
  fails-if: id collisions merge or overwrite distinct sessions.

## determinism & idempotency
determinism: NONDETERMINISTIC (`Date.now()` + `Math.random()` in newSessionId chatStore.ts:34; `Date.now()` timestamps chatStore.ts:38-39; `prefers-color-scheme` query appearance.ts:56,86; localStorage availability appearance.ts:40, composerSettings.ts:18; cross-window storage events composerSettings.ts:71; network in auth.ts:77-89 and copyText auth.ts:100-116). Pure otherwise: `resolveMode` (given `dark`), `migrateLegacy`, `valid`, `chunkIdOf`, `titleFor`, `normalizeMe`, `clean`. [DERIVED]
idempotency: SAFE — `setAppearance` rewrites the same value; `initAppearance` migration fires at most once because `APPEARANCE_KEY` then exists (appearance.ts:99-101); `loadSessions` never writes storage; `saveSessions` is a pure filter/sort/slice then write. [DERIVED]

## failure behaviour
- localStorage unavailable/private mode: appearance falls to `DEFAULT_APPEARANCE` or keeps the value in memory (appearance.ts:39-41,46,77); chatStore returns `[]` on read failure (chatStore.ts:67-68) and silently skips the save ("private mode, or the 5MB quota", chatStore.ts:81-82); composerSettings keeps the session-memory value (composerSettings.ts:18,60-61). [DERIVED]
- Bad JSON: `loadAppearance` falls through to the legacy key (appearance.ts:50); `parse` returns defaults (composerSettings.ts:35); `loadSessions` returns `[]` (chatStore.ts:67-68). [DERIVED]
- `matchMedia` unavailable: `prefersDark()` → `false` (appearance.ts:56); system-change listener not attached (appearance.ts:86). [DERIVED]
- `/auth/me` 404 or malformed body: `normalizeMe` → `LEGACY_OWNER`, so the UI displays owner identity (auth.ts:63-72). [DERIVED]
- Clipboard: `copyText` falls back to a hidden textarea + `execCommand("copy")`, else resolves `false` (auth.ts:107-120). [DERIVED]
- `useAsync`: non-abort rejections become `state.error` (`e.message` or `String(e)`); post-abort results dropped (useAsync.ts:14-17). [DERIVED]

## dumb-code flags
- Key-prefix drift: new key `"polymath.appearance"` (appearance.ts:10) vs the `"polymath-v2."` prefix on `"polymath-v2.theme"` (appearance.ts:11), `"polymath-v2.chats"` (chatStore.ts:28), `"polymath-v2.chat-settings"` (composerSettings.ts:13). [DERIVED]
- `storage()` helper duplicated verbatim in appearance.ts:39-41 and composerSettings.ts:17-19. [DERIVED]
- Cross-window asymmetry: composerSettings re-reads on the window `"storage"` event (composerSettings.ts:71) but appearance's `subscribe` only adds a `matchMedia` listener (appearance.ts:82-88) — a theme change made in another window does not propagate here. [INFERRED: from the listeners each `subscribe` registers.]
- Magic numbers: `42`/`41` truncation (chatStore.ts:46); `slice(2, 8)` (chatStore.ts:34); `MAX_SESSIONS = 50` (chatStore.ts:31). [DERIVED]
- `LEGACY[""] = DEFAULT_APPEARANCE` duplicates `migrateLegacy`'s fallback branch (appearance.ts:18,31). [DERIVED]
- `INTERRUPTED` is a full user-facing English sentence persisted into stored turns (chatStore.ts:29-30,64-65). [DERIVED]

## refactor notes
- Renaming any localStorage key string orphans persisted user state; the existing precedent is the one-time legacy-theme migration (appearance.ts:11,44-53,96-104). [DERIVED]
- `chunkIdOf` encodes the receipt locator grammar `"chunk:<id>@<start>:<end>"` — a backend receipt contract; a receipt schema change re-opens the zero-match join bug (chunkid.ts:4-23). [DERIVED]
- The 10 auth routes are a server contract (auth.ts:77-89); `LEGACY_OWNER` means a 404 `/auth/me` displays owner privileges — display only, per the comment (auth.ts:63-64). [DERIVED]
- Snapshot identity is contractual for both stores: return a fresh object per call and `useSyncExternalStore` loops (composerSettings.ts:45-56; `current` held module-level appearance.ts:69). [DERIVED]
- Stored `Turn` receipts are kept raw by design: schema drift degrades panels, not the thread (chatStore.ts:12-15). Changing `Turn` (in `./chat`, chatStore.ts:17) affects every stored session. [DERIVED]
- Blast radius: importers `App.tsx`, `_small-modules`, `lib/deep.ts` (FACTS.importers); internal deps `api.ts`, `chat.ts`, `contracts.ts` (FACTS.imports). [DERIVED]

## VERIFY
```verify
grep -Fq 'const APPEARANCE_KEY = "polymath.appearance"' frontend-v2/src/lib/appearance.ts
grep -Fq 'DEFAULT_APPEARANCE: Appearance = { mode: "system", accent: "indigo" }' frontend-v2/src/lib/appearance.ts
grep -Fq 'const MAX_SESSIONS = 50' frontend-v2/src/lib/chatStore.ts
grep -Fq 'mode: "HYBRID", model: "", corpusExplore: false' frontend-v2/src/lib/composerSettings.ts
grep -Fq 'username: "king", display_name: "King", is_owner: true' frontend-v2/src/lib/auth.ts
grep -Fq 'startsWith("chunk:")' frontend-v2/src/lib/chunkid.ts
test "$(grep -c -F 'http.post' frontend-v2/src/lib/auth.ts)" -ge 4
```
