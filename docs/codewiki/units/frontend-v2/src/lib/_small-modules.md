# unit: frontend-v2/src/lib/_small-modules
anchor: frontend-v2/src/lib/appearance.ts:1-105 · frontend-v2/src/lib/auth.ts:1-121 · frontend-v2/src/lib/chatStore.ts:1-84 · frontend-v2/src/lib/chunkid.ts:1-26 · frontend-v2/src/lib/composerSettings.ts:1-79 · frontend-v2/src/lib/readiness.ts:1-122 · frontend-v2/src/lib/useAsync.ts:1-22

## purpose
Seven small frontend-v2 lib modules: browser-local appearance theming (frontend-v2/src/lib/appearance.ts:3-4), the auth/Settings API client (frontend-v2/src/lib/auth.ts:2-6), localStorage chat history (frontend-v2/src/lib/chatStore.ts:1-16), receipt chunk-id normalization (frontend-v2/src/lib/chunkid.ts:1-13), shared composer settings store (frontend-v2/src/lib/composerSettings.ts:4-9), backend-verdict presentation for readiness (frontend-v2/src/lib/readiness.ts:1-11), and a minimal fetch-on-mount hook (frontend-v2/src/lib/useAsync.ts:5-6). Unit imported by `frontend-v2/src/App.tsx` and `frontend-v2/src/lib/deep.ts` (FACTS.importers). [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| loadAppearance | function | () -> Appearance | frontend-v2/src/lib/appearance.ts:44 | — |
| setAppearance | function | (next: Appearance) -> void | frontend-v2/src/lib/appearance.ts:74 | — |
| initAppearance | function | () -> Appearance | frontend-v2/src/lib/appearance.ts:96 | — |
| useAppearance | function | () -> [Appearance, (a: Appearance) => void] | frontend-v2/src/lib/appearance.ts:90 | — |
| migrateLegacy | function | (id: string \| null \| undefined) -> Appearance | frontend-v2/src/lib/appearance.ts:30 | — |
| resolveMode | function | (mode: Mode, dark?: boolean) -> "light" \| "dark" | frontend-v2/src/lib/appearance.ts:59 | — |
| applyAppearance | function | (a: Appearance, root?: HTMLElement) -> void | frontend-v2/src/lib/appearance.ts:63 | — |
| auth | const | object of endpoint fns | frontend-v2/src/lib/auth.ts:75 | — |
| normalizeMe | function | (raw: unknown) -> Me | frontend-v2/src/lib/auth.ts:69 | — |
| privateLibrary | function | (me: Me) -> string \| null | frontend-v2/src/lib/auth.ts:93 | — |
| copyText | function | (text: string) -> Promise<boolean> | frontend-v2/src/lib/auth.ts:98 | — |
| loadSessions | function | () -> ChatSession[] | frontend-v2/src/lib/chatStore.ts:49 | — |
| saveSessions | function | (sessions: ChatSession[]) -> void | frontend-v2/src/lib/chatStore.ts:72 | — |
| newSessionId | function | () -> string | frontend-v2/src/lib/chatStore.ts:33 | — |
| emptySession | function | (corpusId: string) -> ChatSession | frontend-v2/src/lib/chatStore.ts:37 | — |
| titleFor | function | (s: ChatSession) -> string | frontend-v2/src/lib/chatStore.ts:43 | — |
| chunkIdOf | function | (row: Record<string, unknown> \| null \| undefined) -> string | frontend-v2/src/lib/chunkid.ts:14 | — |
| getComposerSettings | function | () -> ComposerSettings | frontend-v2/src/lib/composerSettings.ts:51 | — |
| setComposerSettings | function | (next: ComposerSettings) -> void | frontend-v2/src/lib/composerSettings.ts:58 | — |
| updateComposerSettings | function | (patch: Partial<ComposerSettings>) -> void | frontend-v2/src/lib/composerSettings.ts:65 | — |
| useComposerSettings | function | () -> [ComposerSettings, (patch) => void] | frontend-v2/src/lib/composerSettings.ts:77 | — |
| controlReady | function | (cr: ControlPlane["control_ready"] \| null) -> Verdict | frontend-v2/src/lib/readiness.ts:33 | — |
| semanticReady | function | (sr: SemanticReadiness \| null) -> Verdict | frontend-v2/src/lib/readiness.ts:39 | — |
| vnextReady | function | (sr: SemanticReadiness \| null) -> Verdict | frontend-v2/src/lib/readiness.ts:50 | — |
| docSearchable | function | (d: DocSummary \| null) -> boolean | frontend-v2/src/lib/readiness.ts:79 | — |
| servesVnext | function | (d: DocSummary \| null) -> boolean | frontend-v2/src/lib/readiness.ts:86 | — |
| servedWriter | function | (d: DocSummary \| null) -> "vnext" \| "basic" \| null | frontend-v2/src/lib/readiness.ts:93 | — |
| docVnext | function | (d: DocSummary) -> Verdict | frontend-v2/src/lib/readiness.ts:101 | — |
| settled | function | (a: {data,error}, verdict: (d) -> Verdict) -> Verdict | frontend-v2/src/lib/readiness.ts:120 | — |
| useAsync | function | (fn: (signal) => Promise<T>, deps: unknown[]) -> Async<T> | frontend-v2/src/lib/useAsync.ts:6 | — |
| CHECKING | const | Verdict = { state: "unknown", label: "CHECKING" } | frontend-v2/src/lib/readiness.ts:118 | — |
| LEGACY_OWNER | const | Me | frontend-v2/src/lib/auth.ts:65 | — |
| INTERRUPTED | const | string | frontend-v2/src/lib/chatStore.ts:29 | — |
| DEFAULT_APPEARANCE | const | { mode: "system", accent: "indigo" } | frontend-v2/src/lib/appearance.ts:14 | — |
| DEFAULT_COMPOSER_SETTINGS | const | { mode: "HYBRID", model: "", corpusExplore: false } | frontend-v2/src/lib/composerSettings.ts:15 | — |

## contracts
**loadAppearance** — frontend-v2/src/lib/appearance.ts:44-53
- in: none; reads localStorage key `"polymath.appearance"` (frontend-v2/src/lib/appearance.ts:48)
- out: valid `{mode, accent}` from that key, else `migrateLegacy(s.getItem("polymath-v2.theme"))`, else `DEFAULT_APPEARANCE`
- pre: none — `storage()` returns null when `localStorage` is undefined or throws (frontend-v2/src/lib/appearance.ts:39-41)
- post: never throws (JSON.parse wrapped, frontend-v2/src/lib/appearance.ts:47-50)

**setAppearance** — frontend-v2/src/lib/appearance.ts:74-80
- in: `Appearance`
- out: void; writes JSON to `"polymath.appearance"`, removes `"polymath-v2.theme"` (frontend-v2/src/lib/appearance.ts:77)
- post: sets `root.dataset.mode` (resolved light/dark) and `root.dataset.accent` on `document.documentElement` (frontend-v2/src/lib/appearance.ts:63-65); notifies listeners

**initAppearance** — frontend-v2/src/lib/appearance.ts:96-104
- migrates once only when `"polymath.appearance"` is absent AND `"polymath-v2.theme"` is present (frontend-v2/src/lib/appearance.ts:99)

**auth.me** — frontend-v2/src/lib/auth.ts:78
- GET `/auth/me` -> `normalizeMe`; raw without boolean `is_owner` or string `username` returns `LEGACY_OWNER` (`username: "king"`, `principal_id: "prn_owner"`, frontend-v2/src/lib/auth.ts:65-71). Older backends where `/auth/me` 404s behave as owner (frontend-v2/src/lib/auth.ts:63-64)

**loadSessions** — frontend-v2/src/lib/chatStore.ts:49-70
- in: none; out: `ChatSession[]` from `"polymath-v2.chats"`
- post: rows without string `id` or array `turns` dropped (frontend-v2/src/lib/chatStore.ts:58-60); every turn not `done` gets `done: true, error: t.error ?? INTERRUPTED` (frontend-v2/src/lib/chatStore.ts:63-66)

**saveSessions** — frontend-v2/src/lib/chatStore.ts:72-84
- in: sessions; post: empty sessions (`turns.length === 0`) dropped, sorted `updatedAt` desc, sliced to `MAX_SESSIONS`, one `setItem` (frontend-v2/src/lib/chatStore.ts:76-80)

**chunkIdOf** — frontend-v2/src/lib/chunkid.ts:14-26
- in: receipt row; out: string `row.chunk_id` if non-empty, else locator `"chunk:<id>@<start>:<end>"` -> `<id>` (example `"chunk:chunk_abc123@365:564"` -> `"chunk_abc123"`, frontend-v2/src/lib/chunkid.ts:20), else `""`

**getComposerSettings / setComposerSettings** — frontend-v2/src/lib/composerSettings.ts:51-63
- each field cleaned independently; malformed field falls back to its default, others kept (frontend-v2/src/lib/composerSettings.ts:24-31)
- snapshot re-parsed only when the stored string changes (frontend-v2/src/lib/composerSettings.ts:53-54) — same reference otherwise, as `useSyncExternalStore` requires
- `subscribe` also listens to the window `storage` event for `COMPOSER_SETTINGS_KEY` (cross-window, frontend-v2/src/lib/composerSettings.ts:71)

**vnextReady** — frontend-v2/src/lib/readiness.ts:50-74
- `VNEXT_COMPLETE` + `served < docs` -> `{state: "degraded", label: "SEARCHABLE · BASIC PROFILES"}` (frontend-v2/src/lib/readiness.ts:62-66)
- unresolved === 0 && profiled >= docs -> same degraded label (frontend-v2/src/lib/readiness.ts:69-72); else blocked with the backend's own verdict label

**docVnext** — frontend-v2/src/lib/readiness.ts:101-113
- `servesVnext` -> `READY`; else `docSearchable` -> `READY · BASIC PROFILE`; else `BLOCKED` with reasons `"<n> unresolved parents` · `no profile"` (frontend-v2/src/lib/readiness.ts:109-112)

**useAsync** — frontend-v2/src/lib/useAsync.ts:6-22
- refetches when `deps` change; AbortController per effect; errors after unmount or abort ignored (frontend-v2/src/lib/useAsync.ts:15-16,19)

## effect surface
- localStorage keys: `"polymath.appearance"` (write frontend-v2/src/lib/appearance.ts:77), `"polymath-v2.theme"` (read frontend-v2/src/lib/appearance.ts:51, remove :77), `"polymath-v2.chats"` (read frontend-v2/src/lib/chatStore.ts:51, write :80), `"polymath-v2.chat-settings"` (read frontend-v2/src/lib/composerSettings.ts:42, write :60)
- HTTP via `./api` `http`: POST `/auth/owner-password`, GET `/auth/me`, POST `/auth/login`, POST `/auth/logout`, POST `/auth/password`, GET `/keys`, POST `/keys`, DELETE `/keys/{keyId}`, GET `/keys/prompt`, GET `/keys/owner` (frontend-v2/src/lib/auth.ts:77-89)
- DOM: `document.documentElement.dataset.mode`/`.accent` (frontend-v2/src/lib/appearance.ts:64-65); hidden `<textarea>` + `document.execCommand("copy")` fallback (frontend-v2/src/lib/auth.ts:107-115); `navigator.clipboard.writeText` (frontend-v2/src/lib/auth.ts:100)
- Browser events: `matchMedia("(prefers-color-scheme: dark)")` query + change listener (frontend-v2/src/lib/appearance.ts:56,86); window `storage` listener (frontend-v2/src/lib/composerSettings.ts:71-72)
- Postgres tables read/written: none; Qdrant: none; subprocesses: none; env flags: none (FACTS `tables_read`/`tables_written`/`constants` empty)

## invariants
INVARIANT: sessions persisted ≤ `MAX_SESSIONS` = 50 — frontend-v2/src/lib/chatStore.ts:31,79 [DERIVED]
  fails-if: oldest real conversations silently evicted on every save.
INVARIANT: sidebar title length ≤ 42 chars (`q.length > 42 ? q.slice(0, 41) + "…"`) — frontend-v2/src/lib/chatStore.ts:46 [DERIVED]
  fails-if: longer first questions overflow the sidebar label.
INVARIANT: `LEGACY` map has 10 keys (`""` + 9 palette names), so any stored legacy theme resolves — frontend-v2/src/lib/appearance.ts:17-28 [DERIVED]
  fails-if: unknown legacy id silently becomes `{mode: "system", accent: "indigo"}`.
INVARIANT: `"polymath.appearance"` ≠ `"polymath-v2.theme"` — one write, one remove per `setAppearance` — frontend-v2/src/lib/appearance.ts:10-11,77 [DERIVED]
  fails-if: equal keys would delete the value just written.
INVARIANT: composer defaults = `{ mode: "HYBRID", model: "", corpusExplore: false }` — frontend-v2/src/lib/composerSettings.ts:15 [DERIVED]
  fails-if: a backend default-model change leaves `""` meaning "nothing picked" stale.
INVARIANT: `chunkIdOf` output contains no `"chunk:"` prefix and no `"@"` — frontend-v2/src/lib/chunkid.ts:21-23 [DERIVED]
  fails-if: joining receipt sections on chunk_id returns zero matches (the 2026-09-11 0/5 UNSUPPORTED bug, frontend-v2/src/lib/chunkid.ts:8-11).
INVARIANT: no function in readiness.ts reads a `query_ready` field — frontend-v2/src/lib/readiness.ts:8-11 [DERIVED]
  fails-if: reintroducing it paints "ready" while SEMANTIC/VNEXT are incomplete (measured 2026-09-10 case, frontend-v2/src/lib/readiness.ts:9-11).
INVARIANT: `getComposerSettings` returns the same object reference while the stored string is unchanged — frontend-v2/src/lib/composerSettings.ts:47-56 [DERIVED]
  fails-if: `useSyncExternalStore` re-renders every check (infinite-loop risk with `getSnapshot`).

## determinism & idempotency
determinism: NONDETERMINISTIC (`Date.now()` + `Math.random()` in session ids, frontend-v2/src/lib/chatStore.ts:34; `matchMedia` system scheme, frontend-v2/src/lib/appearance.ts:56; HTTP calls, frontend-v2/src/lib/auth.ts:77-90; localStorage reads/writes, all modules; cross-window `storage` events, frontend-v2/src/lib/composerSettings.ts:71). Pure/deterministic: `migrateLegacy`, `resolveMode`, `titleFor`, `chunkIdOf`, all readiness.ts verdict functions.
idempotency: SAFE — `setAppearance`, `saveSessions`, `setComposerSettings` overwrite one key with the cleaned value; `initAppearance` migrates only when the new key is absent (frontend-v2/src/lib/appearance.ts:99); `loadSessions` mutates only its in-memory copy.

## failure behaviour
- `storage()` catches and returns null when `localStorage` is missing/throws (private mode) — appearance and composerSettings then serve in-memory/session values (frontend-v2/src/lib/appearance.ts:39-41, frontend-v2/src/lib/composerSettings.ts:17-19).
- `loadAppearance` swallows JSON.parse errors, falls through to the legacy key (frontend-v2/src/lib/appearance.ts:47-50); `setAppearance` swallows write errors (frontend-v2/src/lib/appearance.ts:77).
- `loadSessions` catch -> `[]` (whole history unreadable = empty list, frontend-v2/src/lib/chatStore.ts:67-69); `saveSessions` catch swallowed — "history is a convenience, never load-bearing" (frontend-v2/src/lib/chatStore.ts:81-83).
- `copyText`: clipboard failure falls back to textarea + `execCommand("copy")`; final failure returns `false` (frontend-v2/src/lib/auth.ts:103-120).
- `useAsync`: catch sets `{data: null, error: message, loading: false}`; errors after unmount/abort dropped (frontend-v2/src/lib/useAsync.ts:14-17).
- No error codes raised from this unit; HTTP status handling lives in `./api` (imported, frontend-v2/src/lib/auth.ts:7).

## dumb-code flags
- Storage-key prefix split: `"polymath.appearance"` vs the `"polymath-v2."` family (`"polymath-v2.theme"`, `"polymath-v2.chats"`, `"polymath-v2.chat-settings"`) — frontend-v2/src/lib/appearance.ts:10, frontend-v2/src/lib/chatStore.ts:28, frontend-v2/src/lib/composerSettings.ts:13 [DERIVED]
- Magic numbers `42`/`41` in `titleFor` — frontend-v2/src/lib/chatStore.ts:46 [DERIVED]
- `MAX_SESSIONS = 50` unexplained constant — frontend-v2/src/lib/chatStore.ts:31 [DERIVED]
- `storage()` helper duplicated verbatim in two modules — frontend-v2/src/lib/appearance.ts:39-41 and frontend-v2/src/lib/composerSettings.ts:17-19 [DERIVED]
- Comment says "ten palettes" but one of the 10 `LEGACY` keys is `""` (never-chosen default), so 9 are real palettes — frontend-v2/src/lib/appearance.ts:16-28 [DERIVED]
- `servedWriter` duplicates the `profile_served`/`profile_vnext` fallback ladder already in `servesVnext` — frontend-v2/src/lib/readiness.ts:86-97 [DERIVED]

## refactor notes
- Renaming `APPEARANCE_KEY` or `LEGACY_THEME_KEY` orphans every stored user preference; `index.html` reads the stored choice before first paint (frontend-v2/src/lib/appearance.ts:3-4,10-11).
- Changing the locator format `"chunk:<id>@<start>:<end>"` breaks `chunkIdOf` and every receipt-section join built on it (frontend-v2/src/lib/chunkid.ts:4-7,19-23).
- Readiness label strings are user-facing contracts: `"SEARCHABLE · BASIC PROFILES"` (frontend-v2/src/lib/readiness.ts:63,70), `"READY · BASIC PROFILE"` (:104), `"BLOCKED"` (:112) — screens and owner expectations cite them verbatim (frontend-v2/src/lib/readiness.ts:46-49,83-85).
- `LEGACY_OWNER` shape must stay a valid `Me`; `normalizeMe` spreads it as the base (frontend-v2/src/lib/auth.ts:69-73).
- `useAppearance`/`useComposerSettings` depend on stable snapshot references — any refactor to re-parse per call breaks `useSyncExternalStore` (frontend-v2/src/lib/appearance.ts:90-92, frontend-v2/src/lib/composerSettings.ts:45-56).
- `loadSessions` depends on the `Turn` shape from `./chat` (`done`, `error`, `question`) — receipt schema changes degrade stored turns, by design (frontend-v2/src/lib/chatStore.ts:12-17,63-66).
- auth endpoint set mirrors the server routes one-to-one (frontend-v2/src/lib/auth.ts:77-89); adding/removing one here requires the backend route.

## VERIFY
```verify
grep -Fq 'polymath.appearance' frontend-v2/src/lib/appearance.ts
grep -Fq 'MAX_SESSIONS = 50' frontend-v2/src/lib/chatStore.ts
grep -Fq 'mode: "HYBRID", model: "", corpusExplore: false' frontend-v2/src/lib/composerSettings.ts
grep -Fq '/auth/owner-password' frontend-v2/src/lib/auth.ts
grep -Eq 'chunk:.*@' frontend-v2/src/lib/chunkid.ts
test "$(grep -c -F 'polymath-v2.' frontend-v2/src/lib/chatStore.ts)" -ge 3
! grep -Fq 'localStorage' frontend-v2/src/lib/readiness.ts
```
