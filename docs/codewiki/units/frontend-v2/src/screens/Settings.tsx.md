# unit: frontend-v2/src/screens/Settings.tsx
anchor: frontend-v2/src/screens/Settings.tsx:1-348

## purpose
Settings screen for the frontend-v2 web app. Renders profile, agent-connect instructions/API keys, website password, appearance and deep-research cards, with layout chosen by `me.local` / `me.is_owner` (owner on server vs owner on website vs friend account) — frontend-v2/src/screens/Settings.tsx:324-347. [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| Settings | function (only export) | `({ me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void })` -> JSX | frontend-v2/src/screens/Settings.tsx:324 | frontend-v2/src/App.tsx |

All other components (`CardHead`, `ProfileCard`, `ConnectCard`, `OwnerKeyCard`, `ShownOnce`, `FriendKeysCard`, `OwnerPasswordCard`, `AccountPasswordCard`, `AppearanceCard`, `message`) are module-local — frontend-v2/src/screens/Settings.tsx:14-319. [DERIVED]

## contracts

**Settings** — frontend-v2/src/screens/Settings.tsx:324-347
- in: `me: Me`; callbacks `onMeChanged: (me: Me) => void`, `onSignOut: () => void` — :324
- out: `<div className="screen settings">` with `ProfileCard`, `{first}`, `AppearanceCard`, `DeepResearchSettings` — :335-345
- pre: `ownerHere = me.local && me.is_owner` — :326; connect = owner ? `ConnectCard`+`OwnerKeyCard` : `FriendKeysCard` — :327-329; password = ownerHere ? `OwnerPasswordCard` : (`!me.local` ? `AccountPasswordCard` : `null`) — :330-332
- post: order is `[password, connect]` when `ownerHere && !passwordSet`, else `[connect, password]` — :333; `OwnerPasswordCard.onSaved` sets `passwordSet` true and reorders — :331, :325

**OwnerKeyCard** — frontend-v2/src/screens/Settings.tsx:87-147
- fetches `auth.ownerKey()` lazily; cached: `if (data) return data` — :94-98; never fetched on page load — :88-91, :116-119
- out: masked value `shown && data ? data.key : masked` — :129

**FriendKeysCard** — frontend-v2/src/screens/Settings.tsx:170-231
- in: none; lists `auth.keys(s)` keyed by `nonce` — :173, :172
- create sends `label.trim()`, max `maxLength={60}` — :184, :208; revoke requires confirm dialog — :195

**OwnerPasswordCard** — frontend-v2/src/screens/Settings.tsx:235-275
- submits `auth.setOwnerPassword(pw)`, disabled when `busy || pw.length === 0` — :245, :267

## effect surface
- Network (all via `../lib/auth`): `auth.prompt(s)` :56; `auth.ownerKey()` :97; `auth.keys(s)` :173; `auth.createKey(label.trim())` :184; `auth.revokeKey(k.key_id)` :197; `auth.setOwnerPassword(pw)` :245.
- Clipboard: `copyText(...)` for key/prompt/mcp_url — :110.
- Browser-local appearance state via `useAppearance()` — :292.
- Postgres tables: none (FACTS.tables_read/tables_written empty). Env: none read here; `"POLYMATH_MCP_API_KEY in its .env"` appears only inside an error-message string — :102.

## invariants
INVARIANT: masked key display length == 24 — `"•".repeat(24)` :121 vs real key length (unknown); fails-if: masked width leaks/implies wrong key length. [DERIVED]
INVARIANT: `copied` resets after 2000 ms — `setTimeout(() => setCopied(""), 2000)` :113; fails-if: stuck "Copied" label. [DERIVED]
INVARIANT: label input max == 60 chars — `maxLength={60}` :208; fails-if: longer labels reach `auth.createKey` truncated or rejected elsewhere. [DERIVED]
INVARIANT: create disabled when `max != null && active.length >= max` — :210 with `active = keys.filter(k => !k.revoked_at)` :178 and `max = keys.data?.max_active ?? null` :179; fails-if: KEY_LIMIT error at :188. [DERIVED]
INVARIANT: initials length <= 2 — `.slice(0, 2).toUpperCase() || "?"` :34; fails-if: avatar overflow for 3+ word names. [DERIVED]
INVARIANT: `ownerKey` fetched at most once per mount — cache check :94; fails-if: repeated network calls / error flicker per button press. [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network :56, :97, :173, :184, :197, :245; timer :113)
idempotency: UNSAFE (`auth.createKey` mints a new key per call :184; `auth.revokeKey` is one-way :197; copy/show/render paths are SAFE — load is cached :94)

## failure behaviour
- `ApiError.code === "OWNER_KEY_NOT_SET"` → message `"The server has no main key yet (POLYMATH_MCP_API_KEY in its .env)."` — :101-102
- `ApiError.code === "KEY_LIMIT"` → `` `You already have ${max} active keys: revoke one first.` `` — :188
- clipboard blocked → `"The browser blocked copying: click Show, select the key and press ⌘C."` — :111
- generic: `message(err)` = `err instanceof ApiError ? err.detailMessage : String(err)` — :14-16; all swallowed into `setError`/banner, callers never see throws — :61, :127, :197, :205, :250/:272
- success path shown as `banner banner--ok` with `role="status"` — :271; errors as `banner banner--bad` with `role="alert"` — :61, :127, :205, :272

## dumb-code flags
- Magic numbers: `24` mask :121, `2000` ms :113, `60` maxLength :208, `rows={12}` :162.
- Username `"King"` hardcoded in two UI strings — :247, :260 (also in comment :233) while the account itself is data (`me.username` :281).
- Three near-identical copy buttons (key/prompt/url) duplicated in OwnerKeyCard — :133-135, :138-139, :141-142.
- `ACCENT_LABEL`/`MODE_LABEL` literal records (`indigo/teal/amber/rose`, `light/dark/system`) duplicate the type domain from `../lib/appearance` — :287-288; adding an Accent there requires editing here.
- `pill--ready`/`pill--degraded` classes reused to mean set/not-set — :261.

## refactor notes
- `Settings` signature is consumed by `frontend-v2/src/App.tsx` (FACTS.importers) — changing props/:324 ripples into App.tsx.
- `ChangePassword` is imported from `./Login` :39 — moving it touches both screens (used at :282).
- Error-code strings `"OWNER_KEY_NOT_SET"` :101 and `"KEY_LIMIT"` :188 are a contract with the server/`ApiError`; changing one side silently degrades to the generic `message(err)` — :14-16.
- Data shapes assumed: `OwnerKey { key, prompt, mcp_url }` :110/:129; `CreatedKey { key, prompt, label }` :157-162; `ApiKey { key_id, label, created_at, revoked_at }` :218-224; `Me { local, is_owner, username, display_name, web_password_set }` :34/:74/:325-326.
- Design-marker comments (ONE-PROFILE, OWNER-KEY-VISIBLE, dated 2026-09-28/2026-09-30) document owner decisions tied to this layout — :53-54, :84-86, :321-323.

## VERIFY
```verify
grep -Fq 'export function Settings' frontend-v2/src/screens/Settings.tsx
grep -Fq 'OWNER_KEY_NOT_SET' frontend-v2/src/screens/Settings.tsx
grep -Fq 'KEY_LIMIT' frontend-v2/src/screens/Settings.tsx
grep -Fq '"•".repeat(24)' frontend-v2/src/screens/Settings.tsx
grep -Fq 'setTimeout(() => setCopied(""), 2000)' frontend-v2/src/screens/Settings.tsx
! grep -Fq 'useEffect' frontend-v2/src/screens/Settings.tsx
test "$(grep -c -F 'auth.' frontend-v2/src/screens/Settings.tsx)" -ge 6
```
