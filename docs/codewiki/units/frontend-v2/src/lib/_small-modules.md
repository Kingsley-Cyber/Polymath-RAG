# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-105

Seven small client modules of the `frontend-v2` React app: appearance theming, auth/API-key client, chat-session persistence, receipt chunk-id normalization, shared composer settings, readiness-verdict presentation, and a fetch-on-mount hook. Unit-level importers per FACTS: `frontend-v2/src/App.tsx`, `frontend-v2/src/_small-modules`, `frontend-v2/src/lib/deep.ts` — per-symbol attribution is not available, so "used by" below is either the unit importers or "—". [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `useAppearance` | function | `() -> [Appearance, (a: Appearance) => void]` | frontend-v2/src/lib/appearance.ts:90-92 | unit importers |
| `initAppearance` | function | `() -> Appearance` | frontend-v2/src/lib/appearance.ts:96-104 | unit importers |
| `loadAppearance` | function | `() -> Appearance` | frontend-v2/src/lib/appearance.ts:44-53 | unit importers |
| `setAppearance` | function | `(next: Appearance) -> void` | frontend-v2/src/lib/appearance.ts:74-80 | unit importers |
| `resolveMode` | function | `(mode: Mode, dark = prefersDark()) -> "light" \| "dark"` | frontend-v2/src/lib/appearance.ts:59-61 | unit importers |
| `migrateLegacy` | function | `(id: string \| null \| undefined) -> Appearance` | frontend-v2/src/lib/appearance.ts:30-32 | unit importers |
| `applyAppearance` | function | `(a: Appearance, root = document.documentElement) -> void` | frontend-v2/src/lib/appearance.ts:63-66 | unit importers |
| `auth` | const | object of endpoint methods (see effect surface) | frontend-v2/src/lib/auth.ts:75-90 | unit importers |
| `normalizeMe` | function | `(raw: unknown) -> Me` | frontend-v2/src/lib/auth.ts:69-73 | unit importers |
| `privateLibrary` | function | `(me: Me) -> string \| null` | frontend-v2/src/lib/auth.ts:93-95 | unit importers |
| `copyText` | function | `async (text: string) -> Promise<boolean>` | frontend-v2/src/lib/auth.ts:98-121 | unit importers |
| `loadSessions` | function | `() -> ChatSession[]` | frontend-v2/src/lib/chatStore.ts:49-70 | unit importers |
| `saveSessions` | function | `(sessions: ChatSession[]) -> void` | frontend-v2/src/lib/chatStore.ts:72-84 | unit importers |
| `newSessionId` | function | `() -> string` | frontend-v2/src/lib/chatStore.ts:33-35 | unit importers |
| `emptySession` | function | `(corpusId: string) -> ChatSession` | frontend-v2/src/lib/chatStore.ts:37-40 | unit importers |
| `titleFor` | function | `(s: ChatSession) -> string` | frontend-v2/src/lib/chatStore.ts:43-47 | unit importers |
| `chunkIdOf` | function | `(row: Record<string, unknown> \| null \| undefined) -> string` | frontend-v2/src/lib/chunkid.ts:14-26 | unit importers |
| `useComposerSettings` | function | `() -> [ComposerSettings, (patch: Partial<ComposerSettings>) => void]` | frontend-v2/src/lib/composerSettings.ts:77-79 | unit importers |
| `getComposerSettings` | function | `() -> ComposerSettings` | frontend-v2/src/lib/composerSettings.ts:51-56 | unit importers |
| `setComposerSettings` | function | `(next: ComposerSettings) -> void` | frontend-v2/src/lib/composerSettings.ts:58-63 | unit importers |
| `controlReady` | function | `(cr: ControlPlane["control_ready"] \| null \| undefined) -> Verdict` | frontend-v2/src/lib/readiness.ts:33-36 | unit importers |
| `semanticReady` | function | `(sr: SemanticReadiness \| null) -> Verdict` | frontend-v2/src/lib/readiness.ts:39-44 | unit importers |
| `vnextReady` | function | `(sr: SemanticReadiness \| null) -> Verdict` | frontend-v2/src/lib/readiness.ts:47-57 | unit importers |
| `docSearchable` | function | `(d: DocSummary \| null \| undefined) -> boolean` | frontend-v2/src/lib/readiness.ts:62-64 | unit importers |
| `docVnext` | function | `(d: DocSummary) -> Verdict` | frontend-v2/src/lib/readiness.ts:68-77 | unit importers |
| `settled` | function | `<T>(a: {data, error}, verdict: (d) -> Verdict) -> Verdict` | frontend-v2/src/lib/readiness.ts:84-86 | unit importers |
| `useAsync` | function | `<T>(fn: (signal) -> Promise<T>, deps: unknown[]) -> Async<T>` | frontend-v2/src/lib/useAsync.ts:6-21 | unit importers |
| Types/values | — | `Mode`, `Accent`, `Appearance`, `DEFAULT_APPEARANCE`, `APPEARANCE_KEY`, `LEGACY_THEME_KEY`, `MODES`, `ACCENTS`; `Me`, `ApiKey`, `CreatedKey`, `MyKeys`, `ConnectPrompt`, `OwnerKey`, `LEGACY_OWNER`; `ChatSession`, `INTERRUPTED`; `ComposerSettings`, `COMPOSER_SETTINGS_KEY`, `DEFAULT_COMPOSER_SETTINGS`; `ReadyState`, `Verdict`, `CHECKING`; `Async` | frontend-v2/src/lib/appearance.ts:6-14, frontend-v2/src/lib/auth.ts:9-67, frontend-v2/src/lib/chatStore.ts:19-31, frontend-v2/src/lib/composerSettings.ts:11-15, frontend-v2/src/lib/readiness.ts:14-21, frontend-v2/src/lib/useAsync.ts:3 | unit importers |

## contracts

`loadAppearance()` — in: none; out: `Appearance`. Pre: localStorage may be missing/private. Post: never throws; returns stored value if `valid`, else migrated `LEGACY_THEME_KEY` value, else `DEFAULT_APPEARANCE = { mode: "system", accent: "indigo" }`. [DERIVED] frontend-v2/src/lib/appearance.ts:44-53,14
- `valid` = mode in `MODES` (`["light","dark","system"]`) and accent in `ACCENTS` (`["indigo","teal","amber","rose"]`). [DERIVED] frontend-v2/src/lib/appearance.ts:34-37,12-13

`setAppearance(next)` — post: writes `APPEARANCE_KEY`, removes `LEGACY_THEME_KEY`, applies dataset attrs, notifies listeners; write failure swallowed. [DERIVED] frontend-v2/src/lib/appearance.ts:74-80

`resolveMode(mode, dark)` — `"system"` → `dark ? "dark" : "light"`; else mode unchanged. [DERIVED] frontend-v2/src/lib/appearance.ts:59-61

`migrateLegacy(id)` — LEGACY map of 10 keys (`""`, `obsidian`, `graphite`, `nord`, `espresso`, `solar`, `rose`, `slate`, `paper`, `champagne`) → nearest `{mode, accent}`; unknown/null → `DEFAULT_APPEARANCE`. [DERIVED] frontend-v2/src/lib/appearance.ts:17-32

`normalizeMe(raw)` — in: unknown JSON; out: `Me`. Post: non-object, non-boolean `is_owner`, or non-string `username` → `LEGACY_OWNER` (`username: "king"`, `is_owner: true`, `principal_id: "prn_owner"`, `local: true`); else spread over `LEGACY_OWNER` with `local: Boolean(m.local)`. [DERIVED] frontend-v2/src/lib/auth.ts:69-73,65-67

`privateLibrary(me)` — owner → `null`; friend → `` `fr-${me.username}` ``. [DERIVED] frontend-v2/src/lib/auth.ts:93-95

`copyText(text)` — try `navigator.clipboard.writeText`; on absence/throw, hidden-textarea + `document.execCommand("copy")`; returns `false` if both fail. [DERIVED] frontend-v2/src/lib/auth.ts:98-121

`loadSessions()` — post: `[]` on missing/unparsable/non-array; rows kept only if `typeof s.id === "string" && Array.isArray(s.turns)`; every turn with `done !== true` is rewritten to `{...t, done: true, error: t.error ?? INTERRUPTED}`. [DERIVED] frontend-v2/src/lib/chatStore.ts:49-70

`saveSessions(sessions)` — post: drops sessions with `turns.length === 0`, sorts by `updatedAt` descending, keeps first `MAX_SESSIONS` (`50`), writes JSON under `"polymath-v2.chats"`; failure swallowed. [DERIVED] frontend-v2/src/lib/chatStore.ts:72-84,28,31

`titleFor(s)` — first turn's trimmed question; `> 42` chars → `` `${q.slice(0, 41)}…` ``; empty → `"New chat"`. [DERIVED] frontend-v2/src/lib/chatStore.ts:43-47

`chunkIdOf(row)` — non-empty string `row.chunk_id` returned as-is; else `locator` parsed as `"chunk:<id>@<start>:<end>"` → `<id>` (leading `"chunk:"` stripped, cut at first `"@"`); else `""`. [DERIVED] frontend-v2/src/lib/chunkid.ts:14-26

`getComposerSettings()` — re-reads the stored string each call; reparses only when the raw string changed (stable reference for `useSyncExternalStore`); no storage → session-cached value. Post: every field individually defaulted by `clean` (`mode` must be in `PUBLIC_MODES`, `model` string, `corpusExplore === true`). [DERIVED] frontend-v2/src/lib/composerSettings.ts:21-31,51-56

`controlReady(cr)` — `null`/undefined → `{state:"unknown", label:"UNKNOWN", detail:"/control_plane not reachable"}`; else passes through `cr.state/label/detail` verbatim. [DERIVED] frontend-v2/src/lib/readiness.ts:33-36

`semanticReady(sr)` — `null` → unknown; `"SEMANTIC_COMPLETE"` → ready; any other verdict → blocked (label = backend's verdict string). [DERIVED] frontend-v2/src/lib/readiness.ts:39-44

`vnextReady(sr)` — `sr?.vnext` missing → unknown; `"VNEXT_COMPLETE"` → ready, else blocked; detail = `"<mapped>/<eligible> parents mapped"` plus `" · <unresolved> unresolved"` when unresolved > 0. [DERIVED] frontend-v2/src/lib/readiness.ts:47-57

`docSearchable(d)` — `!!d && (d.vnext_ready || (d.map_unresolved === 0 && d.profile_present))`. [DERIVED] frontend-v2/src/lib/readiness.ts:62-64

`docVnext(d)` — `vnext_ready` → `READY`; searchable → `degraded`, label `"READY · BASIC PROFILE"`; else `blocked` with detail from `"<n> unresolved parents"` / `"no profile"`. [DERIVED] frontend-v2/src/lib/readiness.ts:68-77

`settled(a, verdict)` — `a.data == null && !a.error` → `CHECKING`; else `verdict(a.data)`. [DERIVED] frontend-v2/src/lib/readiness.ts:84-86,82

`useAsync(fn, deps)` — sets `loading:true, error:null` on dep change; resolves to `{data, error:null, loading:false}` or `{data:null, error: message, loading:false}`; aborted/unmounted results discarded; cleanup aborts the controller. [DERIVED] frontend-v2/src/useAsync placeholder — frontend-v2/src/lib/useAsync.ts:6-21

## effect surface

- localStorage keys read/written: `"polymath.appearance"` (rw, appearance.ts:10,48,77), `"polymath-v2.theme"` (read + removed on save, appearance.ts:11,51-52,77), `"polymath-v2.chats"` (rw, chatStore.ts:28,51,80), `"polymath-v2.chat-settings"` (rw, composerSettings.ts:13,42,60). [DERIVED]
- DOM writes: `document.documentElement.dataset.mode` / `.dataset.accent` (appearance.ts:63-66); temporary hidden `<textarea>` appended to `document.body` (auth.ts:108-116). [DERIVED]
- `matchMedia("(prefers-color-scheme: dark)")` reads + change listener (appearance.ts:55-57,85-87); `window` `"storage"` event listener for cross-window sync (composerSettings.ts:71-72); `navigator.clipboard.writeText` (auth.ts:100-101). [DERIVED]
- Network via `http` from `./api`: POST `/auth/owner-password` (auth.ts:77), GET `/auth/me` (78), POST `/auth/login` (79), POST `/auth/logout` (80), POST `/auth/password` (82), GET `/keys` (84), POST `/keys` (85), DELETE `/keys/{keyId}` (86), GET `/keys/prompt` (87), GET `/keys/owner` (89). [DERIVED]
- No Postgres tables, Qdrant collections, subprocesses, or env flags: `tables_read`/`tables_written`/`constants` are empty in FACTS. [DERIVED]

## invariants

INVARIANT: persisted chat count ≤ `MAX_SESSIONS = 50` — frontend-v2/src/lib/chatStore.ts:79,31 [DERIVED]
  fails-if: reload mints a new blank "New chat" each time and blanks evict real conversations (stated at chatStore.ts:74-76).
INVARIANT: every `Turn` in a loaded session has `done === true` — frontend-v2/src/lib/chatStore.ts:63-65 [DERIVED]
  fails-if: an unfinished turn would render its chat as busy forever after reload (comment, chatStore.ts:61-63).
INVARIANT: sidebar title length ≤ 42 chars (`slice(0, 41)` + `"…"`) — frontend-v2/src/lib/chatStore.ts:46 [DERIVED]
  fails-if: long first questions blow out the sidebar label layout.
INVARIANT: whenever `setAppearance` writes `APPEARANCE_KEY` it also removes `LEGACY_THEME_KEY` — frontend-v2/src/lib/appearance.ts:77 [DERIVED]
  fails-if: stale legacy key keeps winning/interfering on next `loadAppearance` fallback path.
INVARIANT: `docSearchable(d)` ⇔ `d.vnext_ready || (d.map_unresolved === 0 && d.profile_present)` — frontend-v2/src/lib/readiness.ts:63 [DERIVED]
  fails-if: a file with a base profile only is painted "Blocked" (the FILES-READY-LABEL complaint, readiness.ts:59-61).
INVARIANT: owner `privateLibrary` = `null`, friend = `fr-<username>` — frontend-v2/src/lib/auth.ts:94 [DERIVED]
  fails-if: friend uploads land outside the server-created private library.
INVARIANT: `chunkIdOf` returns `""` only when neither a string `chunk_id` nor a string `locator` exists — frontend-v2/src/lib/chunkid.ts:15-25 [DERIVED]
  fails-if: receipt sections keyed by `locator` stop merging with sections keyed by `chunk_id` (the 0/5 UNSUPPORTED bug, chunkid.ts:7-13).
INVARIANT: `normalizeMe` output always has boolean `is_owner`, string `username`, boolean `local` — frontend-v2/src/lib/auth.ts:70-72 [DERIVED]
  fails-if: malformed `/auth/me` bodies crash Settings rendering.

## determinism & idempotency

determinism: NONDETERMINISTIC (localStorage reads appearance.ts:45-52, chatStore.ts:51, composerSettings.ts:39-43; `matchMedia` appearance.ts:56; `Date.now()` + `Math.random()` in `newSessionId` chatStore.ts:34; network in auth.ts:77-89 and useAsync.ts:12-17; cross-window `storage` events composerSettings.ts:71). Pure/deterministic subset: `migrateLegacy`, `resolveMode` (given `dark`), `titleFor`, `chunkIdOf`, all readiness.ts functions, `clean`/`parse`. [DERIVED]
idempotency: SAFE — `setAppearance`, `initAppearance`, `applyAppearance`, `saveSessions`, `setComposerSettings` re-apply/re-write the same state. UNSAFE — `newSessionId` (fresh id each call, chatStore.ts:33-35) and `auth.createKey` (POST `/keys`, auth.ts:85) mint new values per call. [INFERRED — from call shapes]

## failure behaviour

- All localStorage access is guarded: `storage()` returns `null` on throw (appearance.ts:39-41, composerSettings.ts:17-19); reads/writes inside `try { } catch` fall back to defaults or drop silently (appearance.ts:47-52,77; chatStore.ts:67-69,81-83; composerSettings.ts:35,42,60). Caller sees defaults, never an exception. [DERIVED]
- `loadSessions` returns `[]` on any parse failure; individual malformed rows filtered out, not the whole list (chatStore.ts:54-59,67-69). [DERIVED]
- `copyText` degrades: clipboard API → textarea + `execCommand("copy")` → `false` (auth.ts:99-120). [DERIVED]
- `useAsync` puts `e.message` (or `String(e)`) into `error`; errors after abort/unmount are ignored (useAsync.ts:14-17). [DERIVED]
- `normalizeMe` maps malformed/404-era `/auth/me` payloads to `LEGACY_OWNER` — display-only; the server enforces rules itself (auth.ts:63-73). [DERIVED]
- Readiness: unreachable backend → `unknown`/"UNKNOWN" (readiness.ts:34,40,48); in-flight data → `CHECKING`, never an error verdict (readiness.ts:80-86). [DERIVED]

## dumb-code flags

- Storage-key namespace split: `"polymath.appearance"` (appearance.ts:10) vs `"polymath-v2.chats"` (chatStore.ts:28) and `"polymath-v2.chat-settings"` (composerSettings.ts:13). [DERIVED]
- Redundant map entry: `LEGACY[""] = DEFAULT_APPEARANCE` (appearance.ts:19) duplicates the `|| DEFAULT_APPEARANCE` fallback in `migrateLegacy` (appearance.ts:31-32). [DERIVED]
- `INTERRUPTED` is a full UI sentence persisted into stored turns as `error` data (chatStore.ts:29-30,65) — copy change rewrites stored history semantics. [DERIVED]
- FACTS.imports lists `"frontend-v2/src/lib/contracts.ts"` twice (material lines 330-332). [DERIVED]
- FACTS.api_calls records the delete route as `"/keys/"` because the path is a template literal `` `/keys/${u(keyId)}` `` (auth.ts:86). [DERIVED]
- Magic numbers: `42`/`41` title truncation (chatStore.ts:46), `50` session cap (chatStore.ts:31), `slice(2, 8)` id suffix (chatStore.ts:34). [DERIVED]

## refactor notes

- Renaming any storage key orphans persisted user state: `APPEARANCE_KEY`, `LEGACY_THEME_KEY`, `"polymath-v2.chats"`, `COMPOSER_SETTINGS_KEY` (appearance.ts:10-11, chatStore.ts:28, composerSettings.ts:13); a migration path like `migrateLegacy` would be needed. [INFERRED — same pattern as appearance.ts:17-32]
- `Turn` shape comes from `./chat`; only redraw fields are persisted, so a receipt schema change degrades stored turns' panels by design (chatStore.ts:12-16). Changing `Turn` affects every stored thread. [DERIVED]
- `chunkIdOf` is the single join point for receipt sections; changing the `"chunk:<id>@<start>:<end>"` locator format or the bare `chunk_id` field re-breaks section merging (chunkid.ts:4-13). [DERIVED]
- readiness.ts intentionally composes nothing: verdicts must keep coming pre-composed from `/control_plane` etc. — recomposing in the UI is the drift GAP-1 closed (readiness.ts:24-31). `ControlPlane`, `SemanticReadiness`, `DocSummary` come from `./contracts`. [DERIVED]
- `DEFAULT_COMPOSER_SETTINGS.mode = "HYBRID"` must remain a member of `PUBLIC_MODES` or `clean` silently resets it (composerSettings.ts:15,21,27). [DERIVED]
- The 10 `auth` endpoints must stay in lockstep with backend routes; FACTS.importers (`App.tsx`, `_small-modules`, `lib/deep.ts`) are the blast radius for any signature change here. [DERIVED]
- `LEGACY_OWNER` fallback means a broken `/auth/me` paints the visitor as owner; display-only today — removing that guard changes visible behavior on old backends (auth.ts:63-72). [DERIVED]

## VERIFY

```verify
grep -Fq 'polymath.appearance' frontend-v2/src/lib/appearance.ts
grep -Fq 'const MAX_SESSIONS = 50' frontend-v2/src/lib/chatStore.ts
grep -Fq 'polymath-v2.chat-settings' frontend-v2/src/lib/composerSettings.ts
grep -Fq 'd.vnext_ready || (d.map_unresolved === 0 && d.profile_present)' frontend-v2/src/lib/readiness.ts
grep -Fq 'chunk:chunk_abc123@365:564' frontend-v2/src/lib/chunkid.ts
grep -Fq 'prn_owner' frontend-v2/src/lib/auth.ts
test "$(grep -c -F 'http.post' frontend-v2/src/lib/auth.ts)" -ge 5
```
