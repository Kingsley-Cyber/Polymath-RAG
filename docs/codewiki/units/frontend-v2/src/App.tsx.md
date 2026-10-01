# unit: frontend-v2/src/App.tsx
anchor: frontend-v2/src/App.tsx:1-443

## purpose
Root React component of the Polymath web frontend. Implements the FRIENDS-ACCESS-V1 sign-in gate (`/auth/me` → Login / forced password change / Workspace) and the Workspace shell: nav rail + phone drawer, corpus (library) resolution from `/corpora`, app-level chat session ownership, and screen routing. [DERIVED] — App at frontend-v2/src/App.tsx:60-96, Workspace at frontend-v2/src/App.tsx:98-381.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `App` | function | `App() -> JSX.Element` | frontend-v2/src/App.tsx:60 | frontend-v2/src/_small-modules |

Internal (not exported): `Workspace` (98), `ThemeToggle` (384), `AccountMenu` (392), `useMediaQuery` (430), `NAV` (30-41), `ScreenId` (43), `OWNER_SCREENS` (46), `CORPUS_SCREENS` (55), `NO_MODELS` (50). [DERIVED]

## contracts

### App
- in: none — frontend-v2/src/App.tsx:60 [DERIVED]
- out: one of loading card (91), error banner (92), `<Login>` (93), `<ChangePassword>` (94), `<Workspace>` (95) [DERIVED]
- pre: none [DERIVED]
- post: `auth.me()` success → `state="ready"` with `me` set (68-69); 401 → `state="signin"`, `me=null` (71); 404 → `me=LEGACY_OWNER`, `state="ready"` (72); other → `state="error"` with `e.detailMessage` or `String(e)` (73-75) [DERIVED]
- global: `AUTH_REQUIRED_EVENT` window event forces `state="signin"` (80-82) [DERIVED]

### Workspace (internal)
- in: `{ me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void }` — frontend-v2/src/App.tsx:98 [DERIVED]
- out: shell JSX (nav + topbar + main) — frontend-v2/src/App.tsx:251-380 [DERIVED]
- pre: `me` non-null (only rendered from App:95) [DERIVED]
- post: `corpusId` ∈ `corpusList` or `""`; resolution priority: (1) persisted/current id if still valid, (2) first `query_ready` corpus, (3) first corpus, (4) `""` — frontend-v2/src/App.tsx:214-220 [DERIVED]
- post: sessions persisted on every change via `saveSessions(sessions)` (138) [DERIVED]

### useMediaQuery (internal)
- in: `query: string` → out: live-updating `boolean`; `matchMedia` missing/throwing → `false` — frontend-v2/src/App.tsx:430-441 [DERIVED]

### updateTurns / startChat / deleteChat (internal)
- `updateTurns(id, fn)`: applies `fn` to one chat's turns and rewrites `updatedAt: Date.now()` and `title: titleFor(...)` — frontend-v2/src/App.tsx:180-188 [DERIVED]
- `startChat()`: reuses an existing blank session (`turns.length === 0`) before creating `emptySession(corpusId)` — frontend-v2/src/App.tsx:143-156 [DERIVED]
- `deleteChat(id)`: calls `stopStream(id)` before removing the session — frontend-v2/src/App.tsx:171-175 [DERIVED]

## effect surface
- Network: `auth.me()` (68), `auth.logout()` (86), `api.corpora` (191), `api.controlPlane(corpusId, …)` only when `corpusValid && owner` (237), `api.synthesizers` (245), `api.capabilities` (246) [DERIVED]
- localStorage: read `"polymath-v2.nav-collapsed"` (109), `"polymath-v2.corpus"` (105); write same keys (131, 224) [DERIVED]
- window listeners: `AUTH_REQUIRED_EVENT` (81-83), Escape-closes-drawer keydown (125-128), keydown+mousedown closes account menu (396-404), `matchMedia` change (438-440) [DERIVED]
- Postgres tables / Qdrant collections / subprocesses: none (FACTS `tables_read`/`tables_written` empty) [DERIVED]
- Env flags: none read directly; server-side kill switch `POLYMATH_CORPUS_EXPLORER` mentioned only in comment (244), surfaced as capability key `"corpus-explorer"` (248) [DERIVED]

## invariants
INVARIANT: `OWNER_SCREENS = {"overview","control","models"}` ⊆ NAV ids — frontend-v2/src/App.tsx:30-41,46 [DERIVED]
  fails-if: an owner-only screen added to one set but not NAV yields a dead/missing nav entry.
INVARIANT: friend default screen `"chat"` ∉ OWNER_SCREENS — frontend-v2/src/App.tsx:101 vs 46 [DERIVED]
  fails-if: friends land on a hidden screen; `owner &&` guards at 355/370/372 render nothing.
INVARIANT: `CORPUS_SCREENS.has(screen) && !corpusValid` → placeholder, never a corpus-scoped request for `""` or a stale id — frontend-v2/src/App.tsx:340-353 vs 55, comment 234-235 [DERIVED]
  fails-if: transient 404 on cold load (the bug the guard exists for).
INVARIANT: control-plane probe fires only when `corpusValid && owner` — frontend-v2/src/App.tsx:237 [DERIVED]
  fails-if: probe against unresolved corpus reintroduces the cold-load 404.
INVARIANT: `<Chat>` mounts only with `activeChat != null` and is keyed `key={activeChat.id}` — frontend-v2/src/App.tsx:356-358 [DERIVED]
  fails-if: creating the session after the first pending turn changes the key mid-stream and discards the SSE receiver (comment 203-204).
INVARIANT: `models = synths.data ?? NO_MODELS` keeps one array identity while loading so effects keyed on it do not re-run — frontend-v2/src/App.tsx:50,247 [DERIVED]
INVARIANT: `startChat` reuses a blank session (`turns.length === 0`) — frontend-v2/src/App.tsx:145-150 [DERIVED]
  fails-if: stacked blank "New chat" entries in the sidebar.
INVARIANT: `phone = matchMedia("(max-width: 759px)")`; drawer never shows the icon-only rail — frontend-v2/src/App.tsx:114-115 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network: `auth.me`/`api.*` at 68/191/237/245/246; clock: `Date.now()` at 185; env/UI: `window.innerWidth < 1100` at 112, `matchMedia` at 115/436; storage: localStorage at 105/109/131/224) [DERIVED]
idempotency: SAFE — renders are pure; effect writes are idempotent localStorage `setItem` of already-resolved values (131, 224); corpus effect only sets when `!corpusValid` (215-219); `deleteChat` side effect `stopStream(id)` is the one destructive call (172) [INFERRED — set-if-changed pattern makes repeated runs converge]

## failure behaviour
- `check()`: 401 → sign-in screen; 404 → `LEGACY_OWNER` fallback (backend without logins); other `ApiError` → `e.detailMessage`, else `String(e)`, shown in a `banner--bad` error card — frontend-v2/src/App.tsx:71-75,92 [DERIVED]
- `signOut()` swallows logout errors (`catch { /* the cookies are cleared either way */ }`), then always shows sign-in — frontend-v2/src/App.tsx:85-89 [DERIVED]
- localStorage access wrapped in try/catch ("private mode"): reads return `""`/default, writes dropped — frontend-v2/src/App.tsx:104-106,109-112,131,224 [DERIVED]
- `corpora` error counts as loaded (`corpora.data != null || corpora.error != null`), so the placeholder shows "No libraries yet" vs "Loading your libraries…" — frontend-v2/src/App.tsx:200,344-349 [DERIVED]
- `matchMedia` missing/throwing → `useMediaQuery` returns `false` (e.g. some tests) — frontend-v2/src/App.tsx:431-436 [DERIVED]

## dumb-code flags
- Two different width thresholds: collapse default `window.innerWidth < 1100` vs phone `"(max-width: 759px)"` — frontend-v2/src/App.tsx:112,115 [DERIVED]
- `"rule"` sentinel NAV entry with `label: ""`, `icon: null`, special-cased in the render loop — frontend-v2/src/App.tsx:37,269-270 [DERIVED]
- Magic numbers: icon `size={14}` (299), initials `slice(0, 2)` (406) [DERIVED]
- Duplicated localStorage try/catch blocks in four places (104-106, 109-112, 131, 224) [DERIVED]
- 404 → `LEGACY_OWNER` legacy-backend branch embedded in the main auth check — frontend-v2/src/App.tsx:72 [DERIVED]
- Capability probe uses string cast `(caps.data?.contracts ?? {}) as Record<string, unknown>` with key `"corpus-explorer"` — frontend-v2/src/App.tsx:248 [DERIVED]

## refactor notes
- `ScreenId` union, NAV ids, `OWNER_SCREENS`, `CORPUS_SCREENS`, default screens (`owner ? "overview" : "chat"`) and the render switch at 355-374 are one coupled set; changing any id requires touching all — frontend-v2/src/App.tsx:43,46,55,101,355-374 [DERIVED]
- Chat contract: App owns turns (`updateTurns`, comment 177-179) and keys Chat by `activeChat.id` (358); changing keying or moving turn ownership breaks streams that outlive the Chat component [DERIVED]
- localStorage keys `"polymath-v2.nav-collapsed"` / `"polymath-v2.corpus"` are persisted user state; renaming orphans stored prefs and corpus re-resolution priority 1 — frontend-v2/src/App.tsx:48-49,222-225 [DERIVED]
- `deleteChat` must keep calling `stopStream(id)` (registry lives in `./lib/chat`) — frontend-v2/src/App.tsx:15,172 [DERIVED]
- `corpusExploreAvailable` gates the per-request flag; removing the capability check sends the flag when the server kill switch is off — frontend-v2/src/App.tsx:243-248 [DERIVED]
- Blast radius of `App` itself: importer `frontend-v2/src/_small-modules` (FACTS.importers) [DERIVED]

## VERIFY
```verify
grep -Fq 'polymath-v2.corpus' frontend-v2/src/App.tsx
grep -Fq 'window.innerWidth < 1100' frontend-v2/src/App.tsx
grep -Fq '(max-width: 759px)' frontend-v2/src/App.tsx
grep -Fq 'OWNER_SCREENS = new Set<ScreenId>(["overview", "control", "models"])' frontend-v2/src/App.tsx
grep -Fq 'e.status === 404' frontend-v2/src/App.tsx
test "$(grep -c -F 'useAppearance' frontend-v2/src/App.tsx)" -ge 3
! grep -Fq 'sessionStorage' frontend-v2/src/App.tsx
```
