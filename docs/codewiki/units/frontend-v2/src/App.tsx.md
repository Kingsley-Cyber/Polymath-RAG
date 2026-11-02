# unit: frontend-v2/src/App.tsx
anchor: frontend-v2/src/App.tsx:1-464

## purpose
Root component of frontend-v2: signs the caller in via `/auth/me`, gates owner-only screens for friends, resolves the active corpus from backend `/corpora` authority, holds chat sessions at app level, and renders the nav rail + topbar + workspace screens — frontend-v2/src/App.tsx:63-104,106-402 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| App | exported function component | () -> JSX.Element | frontend-v2/src/App.tsx:107 | frontend-v2/src/_small-modules |

Only `App` is exported; `Workspace`, `ThemeToggle`, `AccountMenu`, `useMediaQuery` are module-private — frontend-v2/src/App.tsx:106,405,413,451 [DERIVED].

## contracts
**App()** — frontend-v2/src/App.tsx:107
- in: no parameters — frontend-v2/src/App.tsx:107 [DERIVED]
- out: one of loading card / error banner / `Login` / `ChangePassword` / `Workspace` — frontend-v2/src/App.tsx:99-103 [DERIVED]
- pre: `/auth/me` reachable; `404` from it means "no logins on this backend" → `LEGACY_OWNER`, state `"ready"` — frontend-v2/src/App.tsx:75 [DERIVED]
- post: `signedIn` (state `"ready"` && `me !== null` && `!me.must_change_password`) triggers `returnToReport()` once — frontend-v2/src/App.tsx:90-91 [DERIVED]
- errors: non-401/404 `ApiError` → state `"error"`, message `e.detailMessage` else `String(e)` — frontend-v2/src/App.tsx:76-78 [DERIVED]

**Workspace corpus resolution** (internal contract other screens rely on)
- out: `corpusId` derived by priority (1) still-valid persisted/current id, (2) first `query_ready` corpus, (3) first corpus, (4) `""` — frontend-v2/src/App.tsx:228-239 [DERIVED]
- post: resolved id persisted to `localStorage` under `CORPUS_KEY` — frontend-v2/src/App.tsx:241-244 [DERIVED]

## effect surface
- network: `auth.me()` :69-75; `auth.logout()` :94; `api.corpora(s)` :210; `api.controlPlane(corpusId, s)` only when `corpusValid && owner` :255-258; `api.synthesizers(s)` :264; `api.capabilities(s)` :265 — frontend-v2/src/App.tsx:69-75,94,210,255-258,264-265 [DERIVED]
- localStorage keys: `"polymath-v2.nav-collapsed"` stored as `"1"`/`"0"` — frontend-v2/src/App.tsx:51,150,162; `"polymath-v2.corpus"` — frontend-v2/src/App.tsx:52,243 [DERIVED]
- persistence calls: `saveSessions(sessions)` on every sessions change :201; `stopStream(id)` on chat delete :191 — frontend-v2/src/App.tsx:201,191 [DERIVED]
- window/DOM: `AUTH_REQUIRED_EVENT` listener :82-86; Escape keydown closes drawer :142-147; keydown+mousedown close account menu :415-424; `matchMedia("(max-width: 759px)")` with live listener :123,455-461 — frontend-v2/src/App.tsx:82-86,123,142-147,415-424,455-461 [DERIVED]
- server flag (indirect): deployment kill switch `POLYMATH_CORPUS_EXPLORER` is read server-side; client only checks `caps.data.contracts["corpus-explorer"]` — frontend-v2/src/App.tsx:262-267 [DERIVED]
- Postgres/Qdrant: none in this file (no tables in FACTS, no direct DB access in SOURCE) — frontend-v2/src/App.tsx:1-464 [DERIVED]

## invariants
INVARIANT: OWNER_SCREENS == `{"overview", "control", "models"}` — hidden from non-owners — frontend-v2/src/App.tsx:49,108 [DERIVED]
  fails-if: friends reach owner-only data screens (control plane, LLM providers).
INVARIANT: CORPUS_SCREENS == `{"overview", "chat", "compare", "files", "control", "graph"}` render only when `corpusValid` — frontend-v2/src/App.tsx:58,359 [DERIVED]
  fails-if: a corpus-scoped request fires for unresolved `""` or a deleted id.
INVARIANT: `Chat` key == `activeChat.id` — frontend-v2/src/App.tsx:377 [DERIVED]
  fails-if: key change mid-stream discards the component receiving SSE — frontend-v2/src/App.tsx:222-224 [DERIVED].
INVARIANT: every turn mutation stamps `updatedAt: Date.now()` and recomputes `titleFor` — frontend-v2/src/App.tsx:203-207 [DERIVED]
  fails-if: sidebar titles/staleness order go stale.
INVARIANT: private library appears in `corpusList` only if missing, with `purpose: "private"`, `query_enabled: false` — frontend-v2/src/App.tsx:214-217 [DERIVED]
INVARIANT: `startChat` reuses a blank session (`turns.length === 0`) before creating one — frontend-v2/src/App.tsx:163-169 [DERIVED]
  fails-if: repeated "New chat" stacks blank sessions.
INVARIANT: control-plane probe runs only when `corpusValid && owner`; otherwise resolves `null` — frontend-v2/src/App.tsx:253-258 [DERIVED]
INVARIANT: `models` is the stable `NO_MODELS` reference while the catalog loads — frontend-v2/src/App.tsx:53,266 [DERIVED]
  fails-if: fresh `[]` per render re-runs effects keyed on `models`.
INVARIANT: NAV has 11 entries; `"rule"` is a divider with `label: ""`, `icon: null` — frontend-v2/src/App.tsx:32-44,288-289 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network calls :210,255-258,264-265; `Date.now()` :204; localStorage reads/writes :113,150,243; `matchMedia`/`window.innerWidth` :120,123)
idempotency: SAFE (localStorage writes are plain `setItem`; corpus-resolution effect guarded by `corpora.data` + `corpusValid` early returns :233-235; chat-creation effect guarded by `!activeChat` :224-226)

## failure behaviour
- `check()`: `401` → `me=null`, state `"signin"`; `404` → `LEGACY_OWNER`, state `"ready"`; anything else → error card with `e.detailMessage` / `String(e)` — frontend-v2/src/App.tsx:74-78 [DERIVED]
- `signOut()` swallows logout failure (`catch { /* the cookies are cleared either way */ }`) and still resets to signin — frontend-v2/src/App.tsx:93-97 [DERIVED]
- `AUTH_REQUIRED_EVENT` at any time forces sign-in state — frontend-v2/src/App.tsx:82-86 [DERIVED]
- localStorage errors swallowed with `/* private mode */` — frontend-v2/src/App.tsx:113,119,150,243 [DERIVED]
- missing `matchMedia` → `useMediaQuery` returns `false` (tests, old environments) — frontend-v2/src/App.tsx:452-457 [DERIVED]

## dumb-code flags
- FACTS symbol index places `App` at line 63; the export sits at line 107 — index/file line drift — frontend-v2/src/App.tsx:107 [DERIVED]
- magic widths `1100` (tablet rail default) :120 and `759px` (phone breakpoint) :123 defined in two separate places with no shared constant — frontend-v2/src/App.tsx:120,123 [DERIVED]
- divider encoded as fake screen id `"rule"` with empty label, special-cased in `nav.map` — frontend-v2/src/App.tsx:40,288-289 [DERIVED]
- collapsed state persisted as string literals `"1"`/`"0"` — frontend-v2/src/App.tsx:150,162 [DERIVED]
- inline status literals `401`/`404` in the auth check — frontend-v2/src/App.tsx:74-75 [DERIVED]
- magic `slice(0, 2)` for initials :427 and `size={14}` delete icon :318 — frontend-v2/src/App.tsx:427,318 [DERIVED]

## refactor notes
- Turn state must stay in App (via `updateTurns`); Chat.tsx only displays — a stream must land in its own chat after the user switches (unmounts the sender) — frontend-v2/src/App.tsx:196-207 [DERIVED]
- `Chat` keying by `activeChat.id` must not change — mid-stream key change discards the SSE receiver — frontend-v2/src/App.tsx:222-224,377 [DERIVED]
- Adding a screen requires editing 5 coupled places: `ScreenId` union :46, `NAV` :32-44, `OWNER_SCREENS` :49, `CORPUS_SCREENS` :58, render switch :374-395 — frontend-v2/src/App.tsx:46,32-44,49,58,374-395 [DERIVED]
- Renaming `COLLAPSE_KEY`/`CORPUS_KEY` breaks persisted rail/corpus on refresh — frontend-v2/src/App.tsx:51-52 [DERIVED]
- `OWNER_SCREENS` must match the server's owner-only web boundary (comment says server decides) — frontend-v2/src/App.tsx:48,49 [INFERRED: comment states server-side scoping; exact server set not in SOURCE]
- `onLibraryDeleted` contract with Files: refetch via `corporaNonce` and move to `remaining[0]` — frontend-v2/src/App.tsx:246-251 [DERIVED]

## VERIFY
```verify
grep -Fq 'const OWNER_SCREENS = new Set<ScreenId>(["overview", "control", "models"])' frontend-v2/src/App.tsx
grep -Fq 'window.innerWidth < 1100' frontend-v2/src/App.tsx
grep -Fq 'max-width: 759px' frontend-v2/src/App.tsx
grep -Fq 'polymath-v2.nav-collapsed' frontend-v2/src/App.tsx
grep -Fq 'e.status === 404' frontend-v2/src/App.tsx
test "$(grep -c -F 'useAsync(' frontend-v2/src/App.tsx)" -ge 4
! grep -Fq 'process.env' frontend-v2/src/App.tsx
```
