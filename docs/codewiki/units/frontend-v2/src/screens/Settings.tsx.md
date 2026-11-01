# unit: frontend-v2/src/screens/Settings.tsx
anchor: frontend-v2/src/screens/Settings.tsx:1-387

## purpose
Settings screen of the frontend-v2 web UI. Renders identity, agent-connect/API-key cards, website password management, appearance and deep-research cards, with different cards for the owner on the server (`me.local && me.is_owner`), website users, and friend accounts — frontend-v2/src/screens/Settings.tsx:363-386 [DERIVED]. Card-set decisions documented in owner comments ONE-PROFILE, OWNER-KEY-VISIBLE, CLAUDE-CONNECTOR-URL — frontend-v2/src/screens/Settings.tsx:53-54,96-98,116-117,360-362 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
| Settings | function component | `({ me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void })` -> JSX | frontend-v2/src/screens/Settings.tsx:363 | frontend-v2/src/App.tsx |

Only export in the file; all other components are module-private — frontend-v2/src/screens/Settings.tsx:14-358 [DERIVED].

## contracts
**Settings** — frontend-v2/src/screens/Settings.tsx:363-386
- in: `me: Me` (fields read: `display_name`, `username`, `local`, `is_owner`, `web_password_set`), callbacks `onMeChanged`, `onSignOut` — frontend-v2/src/screens/Settings.tsx:33-35,42,364-365 [DERIVED]
- pre: none checked in-unit; `me` assumed populated by parent — frontend-v2/src/screens/Settings.tsx:363 [INFERRED] (no null guard visible)
- post: `ownerHere = me.local && me.is_owner` selects `OwnerPasswordCard` vs `AccountPasswordCard` vs none — frontend-v2/src/screens/Settings.tsx:365,369-371 [DERIVED]; `me.is_owner` selects `ConnectCard`+`OwnerKeyCard` vs `FriendKeysCard` — frontend-v2/src/screens/Settings.tsx:366-368 [DERIVED]
- post: when `ownerHere && !passwordSet` the password card renders before connect cards, else after — frontend-v2/src/screens/Settings.tsx:372 [DERIVED]

Internal components that call `auth.*` (blast radius, see refactor notes): ConnectCard → `auth.prompt(s)` — frontend-v2/src/screens/Settings.tsx:56; OwnerKeyCard → `auth.ownerKey()` — frontend-v2/src/screens/Settings.tsx:109; FriendKeysCard → `auth.keys(s)`, `auth.createKey(label.trim())`, `auth.revokeKey(k.key_id)` — frontend-v2/src/screens/Settings.tsx:212,223,236; OwnerPasswordCard → `auth.setOwnerPassword(pw)` — frontend-v2/src/screens/Settings.tsx:284 [DERIVED].

## effect surface
- Postgres tables read/written: none in this unit (FACTS `tables_read`/`tables_written` empty) — frontend-v2/src/screens/Settings.tsx:27-28 [DERIVED]
- Network: `auth.prompt` :56, `auth.ownerKey` :109, `auth.keys` :212, `auth.createKey` :223, `auth.revokeKey` :236, `auth.setOwnerPassword` :284 — frontend-v2/src/screens/Settings.tsx:56,109,212,223,236,284 [DERIVED]
- Clipboard: `copyText(...)` — frontend-v2/src/screens/Settings.tsx:122,172 [DERIVED]
- Browser storage: appearance mode/accent "stored in this browser" via `useAppearance` (mechanism in `../lib/appearance`, not visible here) — frontend-v2/src/screens/Settings.tsx:329-331 [INFERRED]
- Env flags: none read; error text names server env `POLYMATH_MCP_API_KEY` — frontend-v2/src/screens/Settings.tsx:114 [DERIVED]
- Timers: two `setTimeout(..., 2000)` copy-feedback resets — frontend-v2/src/screens/Settings.tsx:125,176 [DERIVED]

## invariants
INVARIANT: masked key placeholder length == 24 (`"•".repeat(24)`) — frontend-v2/src/screens/Settings.tsx:133 [DERIVED]
  fails-if: masked box length stops matching whatever the real key display expects (cosmetic only).
INVARIANT: copy feedback timeout == 2000 ms in OwnerKeyCard and == 2000 ms in ShownOnce — frontend-v2/src/screens/Settings.tsx:125,176 [DERIVED]
  fails-if: the two cards show "Copied" for different durations.
INVARIANT: create button disabled iff `max != null && active.length >= max` — frontend-v2/src/screens/Settings.tsx:249 [DERIVED]
  fails-if: user hits server `KEY_LIMIT` error path — frontend-v2/src/screens/Settings.tsx:227 instead of a disabled button.
INVARIANT: active keys == `(keys.data?.keys ?? []).filter((k) => !k.revoked_at)` — frontend-v2/src/screens/Settings.tsx:217 [DERIVED]
  fails-if: limit check counts revoked keys, blocking creation incorrectly.
INVARIANT: owner-key network fetches on mount == 0 (`load()` only via Show/Copy; guarded by `if (data) return data`) — frontend-v2/src/screens/Settings.tsx:105-117 [DERIVED], requirement comment :96-98
  fails-if: key material fetched on page load, violating the stated owner requirement.
INVARIANT: initials = first char per word, `slice(0, 2)`, uppercased, fallback `"?"` — frontend-v2/src/screens/Settings.tsx:34 [DERIVED]
  fails-if: empty-name avatar renders empty instead of `"?"`.
INVARIANT: key label input `maxLength={60}` — frontend-v2/src/screens/Settings.tsx:247 [DERIVED]
  fails-if: server-side label length rules (not visible) reject longer input.
INVARIANT: card order — `ownerHere && !passwordSet ? [password, connect] : [connect, password]` — frontend-v2/src/screens/Settings.tsx:372 [DERIVED]
  fails-if: unset website password no longer surfaces first for the owner on the server.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `auth.*` :56,:109,:212,:223,:236,:284; clipboard :122,:172; `setTimeout` :125,:176; `useAsync` fetch state :56,:212) — frontend-v2/src/screens/Settings.tsx:56,109,125,172,176,212,223,236,284 [DERIVED]
idempotency: UNSAFE (`auth.createKey` at :223 creates a new key on every click; `auth.revokeKey` :236 and `auth.setOwnerPassword` :284 mutate server state; reads at :56,:109,:212 and renders are safe) — frontend-v2/src/screens/Settings.tsx:223,236,284 [DERIVED]

## failure behaviour
- `message(err)`: `ApiError` → `err.detailMessage`, else `String(err)` — frontend-v2/src/screens/Settings.tsx:14-16 [DERIVED]
- error code `OWNER_KEY_NOT_SET` → "The server has no main key yet (POLYMATH_MCP_API_KEY in its .env)." — frontend-v2/src/screens/Settings.tsx:113-114 [DERIVED]
- error code `KEY_LIMIT` → "You already have ${max} active keys: revoke one first." — frontend-v2/src/screens/Settings.tsx:227 [DERIVED]
- clipboard blocked → "The browser blocked copying: click Show, select the key and press ⌘C." / "The browser blocked copying: select the URL and press ⌘C." — frontend-v2/src/screens/Settings.tsx:123,196 [DERIVED]
- all errors surfaced as `banner banner--bad` with `role="alert"`; save success as `banner--ok` `role="status"` — frontend-v2/src/screens/Settings.tsx:61,139,244,310-311 [DERIVED]
- nothing is swallowed silently; every catch path sets a displayed message — frontend-v2/src/screens/Settings.tsx:107-116,226-230,288-290 [DERIVED]

## dumb-code flags
- Magic number `24` in `"•".repeat(24)` with no tie to real key length — frontend-v2/src/screens/Settings.tsx:133 [DERIVED]
- Duplicated `2000` ms timers — frontend-v2/src/screens/Settings.tsx:125,176 [DERIVED]
- Two near-duplicate "The browser blocked copying" strings with different manual-copy advice — frontend-v2/src/screens/Settings.tsx:123,196 [DERIVED]
- Duplicated `copied === "key" ? "Copied" : "Copy key"` label pattern (aria-label and text, twice each) — frontend-v2/src/screens/Settings.tsx:145-146,177-178 [DERIVED]
- Hardcoded icon sizes `18` and `15` with no shared constant — frontend-v2/src/screens/Settings.tsx:21,79,90-91,123,142-143 [DERIVED]
- `ShownOnce` banner asserts the key "is shown only now" — closing the box discards it; no persistence — frontend-v2/src/screens/Settings.tsx:181-183,203 [DERIVED]

## refactor notes
- `Settings` prop signature is the App contract; changing `me`/`onMeChanged`/`onSignOut` breaks `frontend-v2/src/App.tsx` — frontend-v2/src/screens/Settings.tsx:363 [DERIVED], importer per FACTS.importers
- `../lib/auth` API surface consumed: `auth.prompt`, `auth.ownerKey`, `auth.keys`, `auth.createKey`, `auth.revokeKey`, `auth.setOwnerPassword`, `copyText`, `privateLibrary` — frontend-v2/src/screens/Settings.tsx:35,56,109,122,212,223,236,284 [DERIVED]
- Data field names consumed: `OwnerKey` {`key`,`prompt`,`mcp_url`,`connector_url`} :122; `CreatedKey` {`key`,`prompt`,`connector_url`,`label`} :167,185-186,201; `ApiKey` {`key_id`,`label`,`created_at`,`revoked_at`} :234,258-262; `Me` {`display_name`,`username`,`local`,`is_owner`,`web_password_set`} :33-35,42,364-365 — frontend-v2/src/screens/Settings.tsx:122,167,234,364 [DERIVED]
- Server error codes matched literally (`OWNER_KEY_NOT_SET`, `KEY_LIMIT`); renaming either degrades UX to the generic `message(err)` string — frontend-v2/src/screens/Settings.tsx:113,227 [DERIVED]
- The lazy-load guard `if (data) return data` must stay in `OwnerKeyCard.load()` or the key is fetched on page load — frontend-v2/src/screens/Settings.tsx:106 [DERIVED]
- CSS class contract: `settings__*`, `card`, `banner--bad|ok|info`, `btn--primary`, `seg`, `swatch`, `keyrow`, `steps`, `pill--ready|degraded` used throughout — frontend-v2/src/screens/Settings.tsx:20-26,58,139,190-196,239,300,333-355 [DERIVED]
- `MODES`/`ACCENTS` and label maps must stay in sync with `../lib/appearance` — frontend-v2/src/screens/Settings.tsx:3,326-327 [DERIVED]

## VERIFY
```verify
grep -Fq 'export function Settings({ me, onMeChanged, onSignOut }' frontend-v2/src/screens/Settings.tsx
grep -Fq 'OWNER_KEY_NOT_SET' frontend-v2/src/screens/Settings.tsx
grep -Fq 'const masked = "•".repeat(24);' frontend-v2/src/screens/Settings.tsx
grep -Fq 'me.local && me.is_owner' frontend-v2/src/screens/Settings.tsx
test "$(grep -c -F 'The browser blocked copying' frontend-v2/src/screens/Settings.tsx)" -ge 2
test "$(grep -c -F 'setTimeout' frontend-v2/src/screens/Settings.tsx)" -ge 2
! grep -Fq 'useEffect' frontend-v2/src/screens/Settings.tsx
```
