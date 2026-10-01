# unit: frontend-v2/src/screens/Settings.tsx
anchor: frontend-v2/src/screens/Settings.tsx:1-352

## purpose
Settings screen for the Polymath web UI (frontend-v2), built around the ONE-PROFILE model: shows who is signed in, lets the owner connect Claude Code/Codex by copy-paste (connect command, main key, prompts), sets the website password, and picks appearance and deep-research options. Non-owner ("friend") accounts instead get a create/revoke API-key card. [DERIVED] — comments at frontend-v2/src/screens/Settings.tsx:53-54, 84-86, 237-238, 325-327.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| Settings | function component | ({ me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void }) -> JSX | frontend-v2/src/screens/Settings.tsx:328-351 | frontend-v2/src/App.tsx |

All other helpers (message, CardHead, ProfileCard, ConnectCard, OwnerKeyCard, ShownOnce, FriendKeysCard, OwnerPasswordCard, AccountPasswordCard, AppearanceCard) are module-private — no `export` keyword. [DERIVED] — frontend-v2/src/screens/Settings.tsx:14-323.

## contracts

### Settings — frontend-v2/src/screens/Settings.tsx:328-351
- in: `me: Me` (reads `display_name`, `username`, `local`, `is_owner`, `web_password_set`), `onMeChanged: (me: Me) => void`, `onSignOut: () => void` — frontend-v2/src/screens/Settings.tsx:328, 33-35, 329-330 [DERIVED]
- out: ProfileCard, then connect cards, then a password card (conditionally), then AppearanceCard, then DeepResearchSettings — frontend-v2/src/screens/Settings.tsx:344-347 [DERIVED]
- post: `ownerHere = me.local && me.is_owner`; owner gets `ConnectCard` + `OwnerKeyCard`, everyone else `FriendKeysCard`; password card renders FIRST while `ownerHere && !passwordSet` (`first = ownerHere && !passwordSet ? [password, connect] : [connect, password]`) and drops back after save sets `passwordSet` — frontend-v2/src/screens/Settings.tsx:330-337 [DERIVED]

### OwnerKeyCard — frontend-v2/src/screens/Settings.tsx:87-151
- out: main key masked as `"•".repeat(24)` until Show; copy buttons for key / prompt / server address / Claude connector URL — frontend-v2/src/screens/Settings.tsx:121, 129-147 [DERIVED]
- post: key fetched lazily — `load()` is called only from `copy()` and `toggle()`, never on mount — frontend-v2/src/screens/Settings.tsx:93-119 [DERIVED]

### FriendKeysCard — frontend-v2/src/screens/Settings.tsx:174-235
- in: none; loads via `auth.keys(s)` keyed by a `nonce` state — frontend-v2/src/screens/Settings.tsx:176-177 [DERIVED]
- post: create and revoke both bump `nonce` to refetch the list — frontend-v2/src/screens/Settings.tsx:190, 201 [DERIVED]

## effect surface
No Postgres tables, Qdrant collections, files, or subprocesses — FACTS `tables_read: []`, `tables_written: []` and the import list contains no db/storage client — frontend-v2/src/screens/Settings.tsx:1-12 [DERIVED].

| effect | detail | anchor |
| network | `auth.prompt(s)` | frontend-v2/src/screens/Settings.tsx:56 |
| network | `auth.ownerKey()` | frontend-v2/src/screens/Settings.tsx:97 |
| network | `auth.keys(s)` | frontend-v2/src/screens/Settings.tsx:177 |
| network | `auth.createKey(label.trim())` | frontend-v2/src/screens/Settings.tsx:188 |
| network | `auth.revokeKey(k.key_id)` | frontend-v2/src/screens/Settings.tsx:201 |
| network | `auth.setOwnerPassword(pw)` | frontend-v2/src/screens/Settings.tsx:249 |
| clipboard | `copyText({ key, prompt, url, connector }[what])` | frontend-v2/src/screens/Settings.tsx:110 |
| timer | `setTimeout(() => setCopied(""), 2000)` | frontend-v2/src/screens/Settings.tsx:113 |
| browser storage | `useAppearance` — mode/accent, "stored in this browser" | frontend-v2/src/screens/Settings.tsx:294-296 |
| env (server-side, named in UI string only) | `POLYMATH_MCP_API_KEY` in the server's `.env` | frontend-v2/src/screens/Settings.tsx:102 |

## invariants
INVARIANT: masked key length == 24 (`"•".repeat(24)`) — frontend-v2/src/screens/Settings.tsx:121 [DERIVED]
  fails-if: mask stops suggesting real key length; cosmetic only.
INVARIANT: copied-feedback timeout == 2000 ms — frontend-v2/src/screens/Settings.tsx:113 [DERIVED]
  fails-if: "Copied" label sticks or clears too early.
INVARIANT: create disabled iff `max != null && active.length >= max`, where active = keys with `!k.revoked_at` — frontend-v2/src/screens/Settings.tsx:214, 182 [DERIVED]
  fails-if: over-limit create reaches the server and surfaces `KEY_LIMIT` — frontend-v2/src/screens/Settings.tsx:192.
INVARIANT: label input `maxLength={60}` — frontend-v2/src/screens/Settings.tsx:212 [DERIVED]
INVARIANT: initials length <= 2, uppercase, fallback `"?"` — frontend-v2/src/screens/Settings.tsx:34 [DERIVED]
INVARIANT: owner key fetched only on first Show or Copy (`load()` reachable only from `copy()`/`toggle()`) — frontend-v2/src/screens/Settings.tsx:93-119 [DERIVED]
  fails-if: key leaves the server on page load, breaking the privacy contract at frontend-v2/src/screens/Settings.tsx:84-86.
INVARIANT: password card precedes connect cards iff `ownerHere && !passwordSet` — frontend-v2/src/screens/Settings.tsx:337 [DERIVED]
  fails-if: owner misses the mandatory password step ("nothing on the website works without it") — frontend-v2/src/screens/Settings.tsx:325-327.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `auth.*` — frontend-v2/src/screens/Settings.tsx:56, 97, 177, 188, 201, 249; clipboard — frontend-v2/src/screens/Settings.tsx:110; timer — frontend-v2/src/screens/Settings.tsx:113; browser-stored appearance — frontend-v2/src/screens/Settings.tsx:296)
idempotency: UNSAFE (`auth.createKey` mints a new key per submit — frontend-v2/src/screens/Settings.tsx:188; revoke is gated by a confirm dialog because "Agents using this key stop working at once" — frontend-v2/src/screens/Settings.tsx:199-200)

## failure behaviour
- `message(err)`: `ApiError` → `err.detailMessage`, else `String(err)` — frontend-v2/src/screens/Settings.tsx:14-16 [DERIVED]
- `err.code === "OWNER_KEY_NOT_SET"` → "The server has no main key yet (POLYMATH_MCP_API_KEY in its .env)." — frontend-v2/src/screens/Settings.tsx:101-102 [DERIVED]
- `err.code === "KEY_LIMIT"` → `` `You already have ${max} active keys: revoke one first.` `` — frontend-v2/src/screens/Settings.tsx:192 [DERIVED]
- Clipboard rejection → "The browser blocked copying: click Show, select the key and press ⌘C." — frontend-v2/src/screens/Settings.tsx:111 [DERIVED]
- All errors render as `banner banner--bad` with `role="alert"` — frontend-v2/src/screens/Settings.tsx:61, 127, 209, 276; success uses `banner banner--ok` with `role="status"` — frontend-v2/src/screens/Settings.tsx:275 [DERIVED]
- Revoke failure → `setError(message(err))`, list not refetched — frontend-v2/src/screens/Settings.tsx:201 [DERIVED]

## dumb-code flags
- Magic numbers: 24 (mask — frontend-v2/src/screens/Settings.tsx:121), 2000 ms (frontend-v2/src/screens/Settings.tsx:113), maxLength 60 (frontend-v2/src/screens/Settings.tsx:212), initials `slice(0, 2)` (frontend-v2/src/screens/Settings.tsx:34), `rows={12}` on the Secret prompt (frontend-v2/src/screens/Settings.tsx:198), icon sizes 18/15 hardcoded (frontend-v2/src/screens/Settings.tsx:21, 47).
- Duplicated literal: title "Website password" on both OwnerPasswordCard (frontend-v2/src/screens/Settings.tsx:263) and AccountPasswordCard (frontend-v2/src/screens/Settings.tsx:285).
- Foreign class reuse: revoke button uses `btn files__del`, a Files-screen class, inside Settings — frontend-v2/src/screens/Settings.tsx:227.
- Four near-identical copy buttons in OwnerKeyCard differing only in `what`/icon/label — frontend-v2/src/screens/Settings.tsx:133-146.
- Icon "plug" shared by ConnectCard, FriendKeysCard, and the connector button — frontend-v2/src/screens/Settings.tsx:59, 207, 145.
- Legacy branch: FriendKeysCard still served for "an account made before ONE-PROFILE" despite the ONE-PROFILE comments — frontend-v2/src/screens/Settings.tsx:173, 325.

## refactor notes
- `Settings` is the only export and App.tsx its only importer — prop-signature changes require updating frontend-v2/src/App.tsx — frontend-v2/src/screens/Settings.tsx:328, FACTS.importers.
- Binds the full auth client surface: `prompt`, `ownerKey`, `keys`, `createKey`, `revokeKey`, `setOwnerPassword`, `copyText`, `privateLibrary` plus types `ApiKey`/`CreatedKey`/`Me`/`OwnerKey` — frontend-v2/src/screens/Settings.tsx:6, 56, 97, 177, 188, 201, 249.
- Server error-code strings `"OWNER_KEY_NOT_SET"` and `"KEY_LIMIT"` are hard dependencies — frontend-v2/src/screens/Settings.tsx:101, 192.
- `ChangePassword` is imported from Login.tsx — moving it touches both screens — frontend-v2/src/screens/Settings.tsx:7.
- Card ordering and password-card selection depend on `Me.local`, `Me.is_owner`, `Me.web_password_set` semantics — frontend-v2/src/screens/Settings.tsx:329-337.
- OwnerKeyCard's lazy-fetch privacy contract must survive any refactor — frontend-v2/src/screens/Settings.tsx:84-86, 93-119.

## VERIFY
```verify
grep -Fq 'export function Settings' frontend-v2/src/screens/Settings.tsx
grep -Fq 'OWNER_KEY_NOT_SET' frontend-v2/src/screens/Settings.tsx
grep -Fq 'KEY_LIMIT' frontend-v2/src/screens/Settings.tsx
grep -Fq 'POLYMATH_MCP_API_KEY' frontend-v2/src/screens/Settings.tsx
grep -Fq '"•".repeat(24)' frontend-v2/src/screens/Settings.tsx
test "$(grep -c -F 'banner banner--bad' frontend-v2/src/screens/Settings.tsx)" -ge 4
! grep -Fq 'export default' frontend-v2/src/screens/Settings.tsx
```
