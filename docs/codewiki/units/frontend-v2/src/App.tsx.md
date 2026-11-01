# unit: frontend-v2/src/App.tsx
anchor: frontend-v2/src/App.tsx:1-455

## purpose
Root React component of frontend-v2. Implements the sign-in gate (`/auth/me` → Login / forced password change / Workspace) and the Workspace shell: nav rail, "New chat", recent-chat list, top bar with library (corpus) selector, and ten screens. Resolves the active corpus from backend `/corpora` before any corpus-scoped screen mounts (FRONTEND-V2-CORPUS-RESOLUTION). — frontend-v2/src/App.tsx:57-60, frontend-v2/src/App.tsx:98 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `App` | function component (exported) | `() -> JSX.Element` | frontend-v2/src/App.tsx:60 | frontend-v2/src/_small-modules |
| `Workspace` | function (module-private) | `({ me, onMeChanged, onSignOut }) -> JSX.Element` | frontend-v2/src/App.tsx:98 | — (App only) |
| `ThemeToggle` | function (module-private) | `() -> JSX.Element` | frontend-v2/src/App.tsx:396 | — (Workspace only) |
| `AccountMenu` | function (module-private) | `({ me, onSettings, onSignOut }) -> JSX.Element` | frontend-v2/src/App.tsx:404 | — (Workspace only) |
| `useMediaQuery` | hook (module-private) | `(query: string) -> boolean` | frontend-v2/src/App.tsx:442 | — (Workspace only) |

## contracts

### `App()` — frontend-v2/src/App.tsx:60-96
- in: no props. — frontend-v2/src/App.tsx:60 [DERIVED]
- pre: `auth.me()` endpoint reachable; `AUTH_REQUIRED_EVENT` imported from `./lib/api`. — frontend-v2/src/App.tsx:4, frontend-v2/src/App.tsx:68 [DERIVED]
- out: exactly one of — Loading card, error card, `<Login>`, `<ChangePassword me={me} forced>`, `<Workspace me={me}>`. — frontend-v2/src/App.tsx:91-95 [DERIVED]
- post: `ApiError` 401 → `me=null`, state `"signin"`; `ApiError` 404 → `me=LEGACY_OWNER`, state `"ready"` (backend without logins); other `ApiError` → error card with `e.detailMessage`; non-ApiError → `String(e)`. — frontend-v2/src/App.tsx:71-74 [DERIVED]
- event: window `AUTH_REQUIRED_EVENT` forces `me=null`, state `"signin"`. — frontend-v2/src/App.tsx:79-83 [DERIVED]

### `Workspace` corpus gate — frontend-v2/src/App.tsx:351-364
- pre: any screen in `CORPUS_SCREENS` renders only when `corpusValid` (`corpusId !== "" && corpusList.some(c => c.corpus_id === corpusId)`); otherwise an empty/loading screen is shown. — frontend-v2/src/App.tsx:212, frontend-v2/src/App.tsx:351 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| network | `auth.me()` (via `check`) | frontend-v2/src/App.tsx:68 |
| network | `auth.logout()` (signOut) | frontend-v2/src/App.tsx:86 |
| network | `api.corpora(s)`, re-run keyed on `corporaNonce` | frontend-v2/src/App.tsx:202 |
| network | `api.controlPlane(corpusId, s)` — only when `corpusValid && owner`, else resolves `null` | frontend-v2/src/App.tsx:248 |
| network | `api.synthesizers(s)`, `api.capabilities(s)` — run once (`[]` deps) | frontend-v2/src/App.tsx:256-257 |
| localStorage | key `"polymath-v2.nav-collapsed"` — read :109, write `"1"`/`"0"` :142 | frontend-v2/src/App.tsx:48, frontend-v2/src/App.tsx:109, frontend-v2/src/App.tsx:142 |
| localStorage | key `"polymath-v2.corpus"` — read :105, write :235 | frontend-v2/src/App.tsx:49, frontend-v2/src/App.tsx:105, frontend-v2/src/App.tsx:235 |
| window events | `AUTH_REQUIRED_EVENT` :81; `keydown` Escape closes drawer :136; AccountMenu `keydown`+`mousedown` close :412-414; `matchMedia("(max-width: 759px)")` :115 | frontend-v2/src/App.tsx:81, frontend-v2/src/App.tsx:136, frontend-v2/src/App.tsx:412-414, frontend-v2/src/App.tsx:115 |
| env flags | none read directly; server flag `POLYMATH_CORPUS_EXPLORER` surfaces as `caps.data.contracts["corpus-explorer"]` | frontend-v2/src/App.tsx:254, frontend-v2/src/App.tsx:259 |
| DB/Qdrant/files | none (FACTS `tables_read`/`tables_written` empty) | — |

## invariants
INVARIANT: `OWNER_SCREENS` == `{"overview", "control", "models"}`; nav for non-owners is `NAV` minus exactly these — frontend-v2/src/App.tsx:46, frontend-v2/src/App.tsx:100 [DERIVED]
  fails-if: friends see owner-only screens (control plane, LLM providers) the server would reject.
INVARIANT: default screen = `owner ? "overview" : "chat"` — frontend-v2/src/App.tsx:101 [DERIVED]
  fails-if: friends land on `"overview"`, an OWNER_SCREEN with no mounted component (line 366 requires `owner`).
INVARIANT: `CORPUS_SCREENS` == `{"overview","chat","compare","files","control","graph"}` (6 ids); each mounts only when `corpusValid` — frontend-v2/src/App.tsx:55, frontend-v2/src/App.tsx:351 [DERIVED]
  fails-if: corpus-scoped request fires for unresolved `""` or a deleted/stale id.
INVARIANT: corpus resolution priority = valid persisted id > first `query_ready` corpus > `corpusList[0]` > `""` — frontend-v2/src/App.tsx:225-231 [DERIVED]
  fails-if: a hardcoded corpus name would override backend authority (comment explicitly forbids this, lines 220-224).
INVARIANT: `startChat` reuses an existing blank session (`turns.length === 0`) before creating `emptySession(corpusId)` — frontend-v2/src/App.tsx:156-165 [DERIVED]
  fails-if: stacked blank "New chat" entries in the sidebar.
INVARIANT: `<Chat key={activeChat.id} ...>`; creating the session after the first pending turn changed the key mid-stream and discarded the SSE receiver — frontend-v2/src/App.tsx:369, frontend-v2/src/App.tsx:214-217 [DERIVED]
  fails-if: in-flight stream is dropped when the key changes under it.
INVARIANT: `models = synths.data ?? NO_MODELS` where `NO_MODELS` is one stable `[]` reference — frontend-v2/src/App.tsx:50, frontend-v2/src/App.tsx:258 [DERIVED]
  fails-if: a fresh `[]` per render re-runs effects keyed on `models`.
INVARIANT: `updateTurns` sets `updatedAt: Date.now()` and `title: titleFor(...)` on the touched chat only — frontend-v2/src/App.tsx:191-199 [DERIVED]
  fails-if: stream answers written by an unmounted Chat land in the wrong chat or lose their title.
INVARIANT: missing private library is synthesized as `{ corpus_id: mine, purpose: "private", query_enabled: false, documents: 0, query_ready: false, name: mine }` — frontend-v2/src/App.tsx:207-209 [DERIVED]
  fails-if: owner's private library disappears from the selector when not yet indexed server-side.
INVARIANT: collapsed-rail default `window.innerWidth < 1100` (no stored value); phone drawer breakpoint `"(max-width: 759px)"` — frontend-v2/src/App.tsx:112, frontend-v2/src/App.tsx:115 [DERIVED]
  fails-if: tablets lose the icon rail, or phones show the icon-only rail instead of the drawer.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `auth.me`/`api.*` — frontend-v2/src/App.tsx:68, frontend-v2/src/App.tsx:202, frontend-v2/src/App.tsx:248, frontend-v2/src/App.tsx:256-257; `Date.now()` — frontend-v2/src/App.tsx:198; localStorage reads — frontend-v2/src/App.tsx:105, frontend-v2/src/App.tsx:109; `matchMedia`/`innerWidth` — frontend-v2/src/App.tsx:112, frontend-v2/src/App.tsx:115)
idempotency: SAFE (render is a pure function of state; localStorage writes wrapped in try/catch; `startChat` reuses the existing blank session; logout failure swallowed — frontend-v2/src/App.tsx:85-89, frontend-v2/src/App.tsx:156-161) [INFERRED — from the guarded effect patterns shown]

## failure behaviour
- `ApiError` 401 from `/auth/me` → sign-in screen, not an error. — frontend-v2/src/App.tsx:71 [DERIVED]
- `ApiError` 404 → `LEGACY_OWNER` + `"ready"` (backend without logins). — frontend-v2/src/App.tsx:72 [DERIVED]
- Other `ApiError` → error card with `e.detailMessage`; non-ApiError → `String(e)`. — frontend-v2/src/App.tsx:73-74 [DERIVED]
- `auth.logout()` throw swallowed (`/* the cookies are cleared either way */`); caller still lands on sign-in. — frontend-v2/src/App.tsx:86 [DERIVED]
- localStorage throws swallowed as "private mode" on all four access sites. — frontend-v2/src/App.tsx:105, frontend-v2/src/App.tsx:111, frontend-v2/src/App.tsx:142, frontend-v2/src/App.tsx:235 [DERIVED]
- `matchMedia` missing/throwing → `phone=false` / hook returns `false`. — frontend-v2/src/App.tsx:444, frontend-v2/src/App.tsx:448 [DERIVED]
- `corpora` failure → `corporaLoaded` via `corpora.error != null`; corpus gate shows "No libraries yet" vs "Loading your libraries…". — frontend-v2/src/App.tsx:211, frontend-v2/src/App.tsx:355-360 [DERIVED]
- Control-plane probe degrades to `Promise.resolve(null)` when `!corpusValid || !owner` (avoids the transient 404 on cold load). — frontend-v2/src/App.tsx:245-250 [DERIVED]

## dumb-code flags
- `"rule"` sits in the `ScreenId` union and `NAV` but is a separator, not a screen; rendered as `<div className="nav__rule" key="rule" />`. — frontend-v2/src/App.tsx:37, frontend-v2/src/App.tsx:43, frontend-v2/src/App.tsx:280-281 [DERIVED]
- Two unrelated magic breakpoints: `1100` (default collapsed rail) vs `759` (phone drawer). — frontend-v2/src/App.tsx:112, frontend-v2/src/App.tsx:115 [DERIVED]
- Icon size literal `14` and initials `slice(0, 2)` hardcoded inline. — frontend-v2/src/App.tsx:310, frontend-v2/src/App.tsx:418 [DERIVED]
- localStorage try/catch boilerplate duplicated 4×. — frontend-v2/src/App.tsx:105, frontend-v2/src/App.tsx:111, frontend-v2/src/App.tsx:142, frontend-v2/src/App.tsx:235 [DERIVED]
- Synthetic private-library entry reuses `mine` as both `corpus_id` and `name`. — frontend-v2/src/App.tsx:209 [DERIVED]
- `title` and `aria-label` receive the same expression twice on nav buttons and the collapse toggle. — frontend-v2/src/App.tsx:275-276, frontend-v2/src/App.tsx:287-289, frontend-v2/src/App.tsx:311-312 [DERIVED]

## refactor notes
- Adding/removing a screen must update four coupled places: `NAV`, `ScreenId`, `OWNER_SCREENS`, `CORPUS_SCREENS`. — frontend-v2/src/App.tsx:30-55 [DERIVED]
- Chat-turn ownership: App owns turns keyed by chat id; `Chat.tsx` only displays and writes through `onUpdateTurns` functional updates so streams survive Chat unmount. Renaming this contract breaks streaming answers. — frontend-v2/src/App.tsx:188-199, frontend-v2/src/App.tsx:367-379 [DERIVED]
- Do not create the chat session after the first pending turn (key change discards the SSE-receiving component). — frontend-v2/src/App.tsx:214-217, frontend-v2/src/App.tsx:369 [DERIVED]
- `deleteChat` must call `stopStream(id)` before dropping the session. — frontend-v2/src/App.tsx:183 [DERIVED]
- localStorage key strings `"polymath-v2.nav-collapsed"` / `"polymath-v2.corpus"` are persisted user state; renaming orphans stored choices. — frontend-v2/src/App.tsx:48-49 [DERIVED]
- Only known importer: `frontend-v2/src/_small-modules` (FACTS.importers); `App` is the sole export. — frontend-v2/src/App.tsx:60 [DERIVED]
- `NO_MODELS` must stay a module-level constant; inlining `[]` re-triggers consumers keyed on `models`. — frontend-v2/src/App.tsx:50, frontend-v2/src/App.tsx:258 [DERIVED]

## VERIFY
```verify
grep -Fq 'export function App() {' frontend-v2/src/App.tsx
grep -Fq 'const COLLAPSE_KEY = "polymath-v2.nav-collapsed";' frontend-v2/src/App.tsx
grep -Fq 'const CORPUS_KEY = "polymath-v2.corpus";' frontend-v2/src/App.tsx
grep -Fq 'window.innerWidth < 1100' frontend-v2/src/App.tsx
grep -Eq '\(max-width: 759px\)' frontend-v2/src/App.tsx
test "$(grep -c -F 'corpusId' frontend-v2/src/App.tsx)" -ge 10
! grep -Fq 'corpusId = "main"' frontend-v2/src/App.tsx
```
