# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-104

Files: `appearance.ts` (1-104), `auth.ts` (1-126), `chatStore.ts` (1-88), `chunkid.ts` (1-26), `composerSettings.ts` (1-79), `useAsync.ts` (1-22). Unit-level importers (FACTS): `frontend-v2/src/App.tsx`, `frontend-v2/src/_small-modules`, `frontend-v2/src/lib/deep.ts`.

## purpose
Six small browser-side modules for the frontend-v2 React app: (1) appearance — Light/Dark/System plus one accent, stored per browser, applied pre-paint by `index.html` and owned afterwards by this module (`frontend-v2/src/lib/appearance.ts:3-4`); (2) `auth.ts` — the account/Settings API client for FRIENDS-ACCESS-V1 (`frontend-v2/src/lib/auth.ts:2-6`); (3) `chatStore.ts` — named chat sessions persisted in localStorage, "chatgpt style" (`frontend-v2/src/lib/chatStore.ts:1-2`); (4) `chunkid.ts` — one way to get a chunk id out of a receipt row (`frontend-v2/src/lib/chunkid.ts:1-5`); (5) `composerSettings.ts` — shared top-bar chat controls store (`frontend-v2/src/lib/composerSettings.ts:4-9`); (6) `useAsync.ts` — minimal fetch-on-mount hook with abort (`frontend-v2/src/lib/useAsync.ts:5`). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Mode` | type | `"light" \| "dark" \| "system"` | appearance.ts:6 | — |
| `Accent` | type | `"indigo" \| "teal" \| "amber" \| "rose"` | appearance.ts:7 | — |
| `Appearance` | interface | `{ mode: Mode; accent: Accent }` | appearance.ts:8 | — |
| `APPEARANCE_KEY` / `LEGACY_THEME_KEY` | const | `"polymath.appearance"` / `"polymath-v2.theme"` | appearance.ts:10-11 | — |
| `MODES` / `ACCENTS` | const | readonly `Mode[]` / readonly `Accent[]` | appearance.ts:12-13 | — |
| `DEFAULT_APPEARANCE` | const | `{ mode: "system", accent: "indigo" }` | appearance.ts:14 | — |
| `migrateLegacy` | function | `(id: string \| null \| undefined) -> Appearance` | appearance.ts:30 | — |
| `loadAppearance` | function | `() -> Appearance` | appearance.ts:44 | — |
| `resolveMode` | function | `(mode: Mode, dark?: boolean) -> "light" \| "dark"` | appearance.ts:59 | — |
| `applyAppearance` | function | `(a: Appearance, root?: HTMLElement) -> void` | appearance.ts:63 | — |
| `getAppearance` / `setAppearance` | function | `() -> Appearance` / `(next: Appearance) -> void` | appearance.ts:72-74 | — |
| `useAppearance` | function | `() -> [Appearance, (a: Appearance) => void]` | appearance.ts:90 | — |
| `initAppearance` | function | `() -> Appearance` | appearance.ts:96 | — |
| `Me` / `ApiKey` / `CreatedKey` / `MyKeys` / `ConnectPrompt` / `OwnerKey` | interface | auth DTOs | auth.ts:9,21,28,37,47,58 | — |
| `LEGACY_OWNER` | const | `Me` fallback | auth.ts:70 | — |
| `normalizeMe` | function | `(raw: unknown) -> Me` | auth.ts:74 | — |
| `auth` | const | 10 endpoint methods (see contracts) | auth.ts:80 | — |
| `privateLibrary` | function | `(me: Me) -> string \| null` | auth.ts:98 | — |
| `copyText` | function | `(text: string) -> Promise<boolean>` | auth.ts:103 | — |
| `ChatSession` | interface | `{ id, title, corpusId, createdAt, updatedAt, turns: Turn[] }` | chatStore.ts:23-30 | — |
| `INTERRUPTED` | const | error message string | chatStore.ts:33-34 | — |
| `newSessionId` | function | `() -> string` | chatStore.ts:37 | — |
| `emptySession` | function | `(corpusId: string) -> ChatSession` | chatStore.ts:41 | — |
| `titleFor` | function | `(s: ChatSession) -> string` | chatStore.ts:47 | — |
| `loadSessions` | function | `() -> ChatSession[]` | chatStore.ts:53 | — |
| `saveSessions` | function | `(sessions: ChatSession[]) -> void` | chatStore.ts:76 | — |
| `chunkIdOf` | function | `(row: Record<string, unknown> \| null \| undefined) -> string` | chunkid.ts:14 | — |
| `ComposerSettings` | interface | `{ mode: PublicMode; model: string; corpusExplore: boolean }` | composerSettings.ts:11 | — |
| `COMPOSER_SETTINGS_KEY` | const | `"polymath-v2.chat-settings"` | composerSettings.ts:13 | — |
| `DEFAULT_COMPOSER_SETTINGS` | const | `{ mode: "HYBRID", model: "", corpusExplore: false }` | composerSettings.ts:15 | — |
| `getComposerSettings` / `setComposerSettings` | function | `() -> ComposerSettings` / `(next: ComposerSettings) -> void` | composerSettings.ts:51,58 | — |
| `updateComposerSettings` | function | `(patch: Partial<ComposerSettings>) -> void` | composerSettings.ts:65 | — |
| `useComposerSettings` | function | `() -> [ComposerSettings, (patch: Partial<ComposerSettings>) => void]` | composerSettings.ts:77 | — |
| `Async` | interface | `<T> { data: T \| null; error: string \| null; loading: boolean }` | useAsync.ts:3 | — |
| `useAsync` | function | `<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[]) -> Async<T>` | useAsync.ts:6 | — |

## contracts
- `loadAppearance()` — in: none. out: a validated `Appearance`. pre: none (never throws: private mode, bad JSON). post: stored `APPEARANCE_KEY` JSON if valid → else `LEGACY_THEME_KEY` migrated → else `DEFAULT_APPEARANCE`. — frontend-v2/src/lib/appearance.ts:44-53 [DERIVED]
- `resolveMode(mode, dark = prefersDark())` — in: `Mode`, optional override of the OS probe. out: `"dark"` when `mode === "system"` and dark, else `"light"`/`mode` itself. — frontend-v2/src/lib/appearance.ts:59-61 [DERIVED]
- `setAppearance(next)` — post: `current` set, `APPEARANCE_KEY` written, `LEGACY_THEME_KEY` removed, `dataset.mode`/`dataset.accent` set on `document.documentElement`, all listeners called. — frontend-v2/src/lib/appearance.ts:74-80 [DERIVED]
- `initAppearance()` — post: migrates exactly once — only when `APPEARANCE_KEY` is absent AND `LEGACY_THEME_KEY` is present; otherwise re-applies without writing. — frontend-v2/src/lib/appearance.ts:96-104 [DERIVED]
- `normalizeMe(raw)` — in: unknown JSON. out: `Me`. post: returns `LEGACY_OWNER` (`username: "king"`, `principal_id: "prn_owner"`) unless `is_owner` is boolean AND `username` is string; `local` coerced via `Boolean`. — frontend-v2/src/lib/auth.ts:74-78 [DERIVED]
- `auth.*` — 10 http calls: `POST /auth/owner-password`, `GET /auth/me`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/password`, `GET /keys`, `POST /keys`, `DELETE /keys/{keyId}` (URL-encoded), `GET /keys/prompt`, `GET /keys/owner` (fetched only on Show/Copy click). — frontend-v2/src/lib/auth.ts:82-94 [DERIVED]
- `privateLibrary(me)` — out: `null` iff `me.is_owner`; else `` `fr-${me.username}` ``. — frontend-v2/src/lib/auth.ts:98-100 [DERIVED]
- `copyText(text)` — out: `Promise<boolean>`; `true` via `navigator.clipboard.writeText`, else hidden-textarea + `document.execCommand("copy")`, else `false`. — frontend-v2/src/lib/auth.ts:103-126 [DERIVED]
- `newSessionId()` — out: `` `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}` ``. — frontend-v2/src/lib/chatStore.ts:37-39 [DERIVED]
- `loadSessions()` — post: drops non-array payloads; keeps rows with string `id` and array `turns`; every unfinished turn becomes `done: true` with `error ?? INTERRUPTED`. — frontend-v2/src/lib/chatStore.ts:53-74 [DERIVED]
- `saveSessions(sessions)` — pre/post: drops sessions with `turns.length === 0`, sorts by `updatedAt` desc, keeps top `MAX_SESSIONS`. — frontend-v2/src/lib/chatStore.ts:76-88 [DERIVED]
- `titleFor(s)` — out: first turn's `question` trimmed; if longer than 42 chars → `q.slice(0, 41) + "…"`; no question → `"New chat"`. — frontend-v2/src/lib/chatStore.ts:47-51 [DERIVED]
- `chunkIdOf(row)` — out: `row.chunk_id` when a non-empty string; else locator `"chunk:<id>@<start>:<end>"` → id before `"@"` with `"chunk:"` prefix stripped (`"chunk:chunk_abc123@365:564"` → `"chunk_abc123"`); else `""`. — frontend-v2/src/lib/chunkid.ts:14-26 [DERIVED]
- `getComposerSettings()` — post: re-reads the raw stored string each call; snapshot reference changes only when the raw string changes (as `useSyncExternalStore` requires). — frontend-v2/src/lib/composerSettings.ts:43-56 [DERIVED]
- `setComposerSettings(next)` — post: value cleaned field-by-field, persisted (or memory-only in private mode), `cachedRaw` re-synced so a failed write is not read back over the new value. — frontend-v2/src/lib/composerSettings.ts:58-63 [DERIVED]
- `useAsync(fn, deps)` — post: sets `loading: true` on each deps change; success → `{data, error: null, loading: false}`; failure → `{data: null, error: message, loading: false}`; cleanup sets `live = false` and calls `ac.abort()`. — frontend-v2/src/lib/useAsync.ts:6-21 [DERIVED]

## effect surface
- localStorage keys (no Postgres tables, no Qdrant, no env flags — FACTS `tables_read`/`tables_written` empty):
  - `"polymath.appearance"` — read frontend-v2/src/lib/appearance.ts:48, written :77
  - `"polymath-v2.theme"` — read :51, removed :77
  - `"polymath-v2.chats"` — read frontend-v2/src/lib/chatStore.ts:55, written :84
  - `"polymath-v2.chat-settings"` — read frontend-v2/src/lib/composerSettings.ts:40, written :58
- Network (all via `http` from `./api`, frontend-v2/src/lib/auth.ts:7): the ten endpoints listed in contracts, frontend-v2/src/lib/auth.ts:82-94. [DERIVED]
- DOM: `document.documentElement.dataset.mode`/`.accent` (frontend-v2/src/lib/appearance.ts:63-66); `matchMedia("(prefers-color-scheme: dark)")` probe + change listener (:56, :86); `window` `storage` event (frontend-v2/src/lib/composerSettings.ts:71); hidden `<textarea>` + `document.execCommand("copy")` (frontend-v2/src/lib/auth.ts:113-122). [DERIVED]
- Imports (FACTS): `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts` (`Turn`), `frontend-v2/src/lib/contracts.ts` (`PUBLIC_MODES`, `PublicMode`). [DERIVED]

## invariants
INVARIANT: persisted session count <= `MAX_SESSIONS` = `50` — frontend-v2/src/lib/chatStore.ts:35,83 [DERIVED]
  fails-if: blank "New chat" rows evict real conversations on reload (rationale at :78-79).
INVARIANT: `LEGACY` covers exactly 10 palette keys — `""`, `obsidian`, `graphite`, `nord`, `espresso`, `solar`, `rose`, `slate`, `paper`, `champagne` — every value a pair from `MODES` x `ACCENTS` — frontend-v2/src/lib/appearance.ts:17-28 [DERIVED]
  fails-if: an unmapped legacy id silently becomes `DEFAULT_APPEARANCE` (frontend-v2/src/lib/appearance.ts:31).
INVARIANT: `privateLibrary(me) === null` iff `me.is_owner === true` — frontend-v2/src/lib/auth.ts:98-100 [DERIVED]
  fails-if: friends' private libraries (`fr-<username>`) would be computed for the owner, or lost for friends.
INVARIANT: `titleFor` output <= 42 chars (`slice(0, 41)` + `"…"`) — frontend-v2/src/lib/chatStore.ts:50-51 [DERIVED]
  fails-if: sidebar labels overflow their slot.
INVARIANT: every turn returned by `loadSessions()` has `done === true` — frontend-v2/src/lib/chatStore.ts:69 [DERIVED]
  fails-if: a stored thread reads as busy forever (no stream survives a page load, :65-66).
INVARIANT: `setAppearance` removes `LEGACY_THEME_KEY` on every write — frontend-v2/src/lib/appearance.ts:77 [DERIVED]
  fails-if: `initAppearance`'s migrate-once guard (:99) would re-trigger.
INVARIANT: `newSessionId` prefix is `"c_"` — frontend-v2/src/lib/chatStore.ts:38 [DERIVED]
  fails-if: id format consumers (none visible here) mis-parse.
INVARIANT: `chunkIdOf` output contains no `"@"` and no leading `"chunk:"` when derived from a locator — frontend-v2/src/lib/chunkid.ts:21-23 [DERIVED]
  fails-if: receipt sections keyed by `chunk_id` and by `locator` join to zero matches / duplicate rows (:8-12).
INVARIANT: `DEFAULT_APPEARANCE = { mode: "system", accent: "indigo" }` vs `DEFAULT_COMPOSER_SETTINGS = { mode: "HYBRID", model: "", corpusExplore: false }` — two unrelated "mode" defaults — frontend-v2/src/lib/appearance.ts:14, frontend-v2/src/lib/composerSettings.ts:15 [DERIVED]
  fails-if: nothing — intentional, but do not conflate the two `mode` fields in a refactor. [INFERRED: same field name, different domains]

## determinism & idempotency
determinism: NONDETERMINISTIC
- `Date.now()` / `Math.random()` — frontend-v2/src/lib/chatStore.ts:38,43
- localStorage reads — frontend-v2/src/lib/appearance.ts:48, frontend-v2/src/lib/chatStore.ts:55, frontend-v2/src/lib/composerSettings.ts:40
- `matchMedia` OS probe — frontend-v2/src/lib/appearance.ts:56
- network (`http.*`) — frontend-v2/src/lib/auth.ts:82-94
- cross-window `storage` events — frontend-v2/src/lib/composerSettings.ts:71
- `chunkid.ts` alone is pure/DETERMINISTIC — frontend-v2/src/lib/chunkid.ts:14-26

idempotency: SAFE for `setAppearance` (same-value rewrite, frontend-v2/src/lib/appearance.ts:74-80), `saveSessions` (pure filter/sort/slice rewrite, frontend-v2/src/lib/chatStore.ts:80-84), `initAppearance` (migrate-once guard, frontend-v2/src/lib/appearance.ts:99), `useAsync` (prior call aborted on re-run, frontend-v2/src/lib/useAsync.ts:18). UNSAFE for `newSessionId` (each call mints a fresh id, frontend-v2/src/lib/chatStore.ts:37-39).

## failure behaviour
- appearance: `storage()` catch → `null` (frontend-v2/src/lib/appearance.ts:39-41); `loadAppearance` bad-JSON catch → falls to legacy key → default (:47-52); `setAppearance` write catch → swallowed, value still applied in memory (:77). Caller never sees a throw.
- auth: `normalizeMe` malformed shape → `LEGACY_OWNER`, display-only (:76-77); `copyText` both paths fail → resolves `false` (:109-125).
- chatStore: `loadSessions` catch → `[]` (frontend-v2/src/lib/chatStore.ts:71-73); `saveSessions` catch → silent (private mode or the 5MB quota; "history is a convenience, never load-bearing", :85-87).
- composerSettings: `parse` catch → `DEFAULT_COMPOSER_SETTINGS` (:33-35); `readRaw` catch → `undefined` → in-memory `cached` (:40-42).
- useAsync: rejection → `error: e.message` state, unless `live === false` or aborted, then ignored (frontend-v2/src/lib/useAsync.ts:14-17).

## dumb-code flags
- localStorage key naming split: `"polymath.appearance"` (no v2) vs `"polymath-v2.theme"` / `"polymath-v2.chats"` / `"polymath-v2.chat-settings"` — frontend-v2/src/lib/appearance.ts:10-11, frontend-v2/src/lib/chatStore.ts:32, frontend-v2/src/lib/composerSettings.ts:13. [DERIVED]
- `storage()` helper duplicated verbatim in appearance.ts:39-41 and composerSettings.ts:17-19. [DERIVED]
- Twin tiny-store pattern (module `listeners` Set + `useSyncExternalStore`) duplicated: appearance.ts:69-92 vs composerSettings.ts:47-79 — but not identical: composerSettings listens to the window `storage` event (:71), appearance does not (only `matchMedia`, :86), so appearance changes do not sync across windows. [DERIVED]
- Magic numbers: `50` (frontend-v2/src/lib/chatStore.ts:35), `42`/`41` (:50), `slice(2, 8)` (:38).
- `loadSessions` injects the `INTERRUPTED` message into old unfinished turns on every load (in-memory copy) — persisted on the next `saveSessions` — frontend-v2/src/lib/chatStore.ts:69. [DERIVED]
- `LEGACY` palette collisions by design: `obsidian` ≡ `graphite` (dark/indigo), `espresso` ≡ `solar` (dark/amber), `paper` ≡ `champagne` (light/amber) — frontend-v2/src/lib/appearance.ts:19-27. [DERIVED]

## refactor notes
- `index.html` applies the stored choice before first paint (frontend-v2/src/lib/appearance.ts:3-4): renaming `APPEARANCE_KEY` or the `dataset.mode`/`dataset.accent` attributes requires updating index.html too. [DERIVED]
- `chunkIdOf` output is the join key for the Answer Review and Evidence Inspector; changing locator format `"chunk:<id>@<start>:<end>"` breaks both panels (frontend-v2/src/lib/chunkid.ts:4-13). [DERIVED]
- `Turn` shape (from `./chat`) is the persisted unit; a receipt schema change degrades stored turns' panels rather than corrupting the thread (frontend-v2/src/lib/chatStore.ts:12-15,21). [DERIVED]
- `auth` endpoint paths and DTO fields (`connector_url` shape `…/k/<key>/mcp`) are backend contracts (frontend-v2/src/lib/auth.ts:32-34,82-94). [DERIVED]
- Composer settings are written by `components/ChatControls` and read by `screens/Chat` at send time (frontend-v2/src/lib/composerSettings.ts:4-9); `PublicMode`/`PUBLIC_MODES` come from `./contracts` (:2). [DERIVED]
- Renaming any export breaks all three unit-level importers: `App.tsx`, `_small-modules`, `lib/deep.ts` (FACTS.importers). [DERIVED]

## VERIFY
```verify
grep -Fq 'MAX_SESSIONS = 50' frontend-v2/src/lib/chatStore.ts
grep -Fq 'APPEARANCE_KEY = "polymath.appearance"' frontend-v2/src/lib/appearance.ts
grep -Fq 'mode: "HYBRID", model: "", corpusExplore: false' frontend-v2/src/lib/composerSettings.ts
grep -Fq 'principal_id: "prn_owner"' frontend-v2/src/lib/auth.ts
grep -Fq 'loc.startsWith("chunk:")' frontend-v2/src/lib/chunkid.ts
test "$(grep -c -F 'catch' frontend-v2/src/lib/appearance.ts)" -ge 5
```
