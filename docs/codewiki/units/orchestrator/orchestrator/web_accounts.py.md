# unit: orchestrator/orchestrator/web_accounts.py
anchor: orchestrator/orchestrator/web_accounts.py:1-502

## purpose
Accounts and sessions for the public web UI (rag.kingsleylab.xyz), FRIENDS-ACCESS-V1, owner decision 2026-09-26 — orchestrator/orchestrator/web_accounts.py:1-6 [DERIVED]. One identity store: the per-friend principal registry of `mcp_principals.py`; a friend login is a `web` credential on the friend's principal, the owner's is `owner_web` — web_accounts.py:3-4,37 [DERIVED]. Hashes/verifies passwords (scrypt), signs/reads session cookies (HMAC-SHA256), throttles guesses; the request boundary lives in `web_boundary.py` — web_accounts.py:5-6,8-12 [DERIVED].
Importers (FACTS): `orchestrator/orchestrator/_small-modules`, `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/api/web_settings.py`.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| AccountError | class | (code: str, message: str) -> ValueError subclass | web_accounts.py:52-57 | — |
| password_problem | def | (password) -> str \| None | web_accounts.py:61-65 | — |
| hash_password | def | (password) -> str | web_accounts.py:68-72 | — |
| verify_password | def | (password, stored) -> bool | web_accounts.py:75-84 | — |
| registry_path | def | () -> Path \| None | web_accounts.py:88-90 | — |
| update_registry | def | (path, change: Callable) -> Any | web_accounts.py:105-110 | — |
| read_registry | def | (path) -> dict | web_accounts.py:113-114 | — |
| normalize_username | def | (username) -> str | web_accounts.py:117-121 | — |
| principal_id_for | def | (username) -> str | web_accounts.py:124-128 | — |
| private_corpus_for | def | (username) -> str | web_accounts.py:131-132 | — |
| set_owner_password | def | (path, password, display_name="King") -> None | web_accounts.py:160-167 | — |
| add_friend | def | (path, username, password, *, display_name="", corpus_ids=(), adapter_ids=(), must_change=True) -> dict | web_accounts.py:170-186 | — |
| set_friend_enabled | def | (path, username, enabled) -> None | web_accounts.py:202-209 | — |
| reset_friend_password | def | (path, username, password) -> None | web_accounts.py:212-219 | — |
| set_friend_corpora | def | (path, username, corpus_ids) -> dict | web_accounts.py:222-230 | — |
| public_record | def | (rec) -> dict | web_accounts.py:233-240 | — |
| list_friends | def | (doc) -> list[dict] | web_accounts.py:243-244 | — |
| new_invite_code | def | () -> str | web_accounts.py:248-250 | — |
| invite_record / invite_code | def | (doc) -> dict \| None / str \| None | web_accounts.py:253-255,258-260 | — |
| rotate_invite | def | (path) -> str | web_accounts.py:263-270 | — |
| register_friend | def | (path, username, password, code, *, corpus_ids=(), adapter_ids=()) -> dict | web_accounts.py:288-308 | — |
| WebIdentity | dataclass | frozen; principal_id, username, display_name, is_owner, session_version, must_change_password=False | web_accounts.py:312-319 | — |
| identity_for | def | (doc, username) -> WebIdentity \| None | web_accounts.py:340-344 | — |
| authenticate_password | def | (doc, username, password) -> WebIdentity \| None | web_accounts.py:347-353 | — |
| change_password | def | (path, principal_id, old, new) -> None | web_accounts.py:356-370 | — |
| session_secret | def | () -> bytes \| None | web_accounts.py:374-376 | — |
| make_session | def | (secret, ident, now=None, ttl_s=SESSION_TTL_S) -> (cookie, csrf) | web_accounts.py:379-384 | — |
| read_session | def | (secret, cookie, now=None) -> dict \| None | web_accounts.py:387-397 | — |
| resolve_session | def | (doc, payload) -> WebIdentity \| None | web_accounts.py:400-411 | — |
| csrf_ok | def | (payload, header_value) -> bool | web_accounts.py:414-416 | — |
| LoginThrottle | class | (limit=5, window_s=900); allowed/failed/succeeded | web_accounts.py:420-448 | — |
| create_key | def | (path, principal_id, label="") -> (raw bearer, public record) | web_accounts.py:452-466 | — |
| revoke_key | def | (path, principal_id, key_id) -> None | web_accounts.py:469-476 | — |
| list_keys | def | (doc, principal_id) -> list[dict] | web_accounts.py:479-481 | — |
| public_key | def | (key) -> dict | web_accounts.py:484-486 | — |

## contracts
- `add_friend` — pre: username matches `USERNAME_RE = ^[a-z0-9][a-z0-9_-]{1,31}$` (web_accounts.py:39) and != `OWNER_USERNAME` else `BAD_USERNAME` (web_accounts.py:174-176); not already taken else `EXISTS` with `f"{name} already has an account"` (web_accounts.py:180-181). post: appends `_friend_record` — profile `"friend"`, `enabled: True`, `scopes: list(FRIEND_SCOPES)`, `corpus_ids` sorted union of arg + `fr-<name>`, `writable_corpus_ids: [fr-<name>]`, `keys: []`, `web = _new_web(...)`; returns `public_record(rec)` (no hash) — web_accounts.py:193-199,184-185 [DERIVED].
- `register_friend` — check order under the registry lock: code exists (`INVITES_OFF`), constant-time code match via `secrets.compare_digest` (`INVITE_INVALID`, checked before username so a stranger learns nothing about names), username (`USERNAME_INVALID`/`USERNAME_TAKEN`), password (`WEAK_PASSWORD`); builds the same record as `add_friend` with `must_change=False`; returns record without hash — web_accounts.py:288-308,294-307 [DERIVED].
- `authenticate_password` — in: `(doc, username, password)`. Unknown/inactive user: runs `verify_password(str(password), _DUMMY_HASH)` (same work, no timing oracle) and returns None; known: returns `WebIdentity` iff `verify_password` passes — web_accounts.py:347-353,350 [DERIVED].
- `make_session`/`read_session` — cookie = `_b64(json).` + `_b64(HMAC-SHA256(secret, body))`, payload keys `"p"` (principal id), `"v"` (session version), `"e"` (unix expiry), `"c"` (csrf); read rejects bad signature and `e <= now` — web_accounts.py:379-384,387-397 [DERIVED]. pre: `session_secret()` returns None when env value is < 32 chars — web_accounts.py:374-376 [DERIVED].
- `resolve_session` — post: identity only if account still active AND `found[0].session_version != payload.get("v")` fails — web_accounts.py:400-411,409 [DERIVED].
- `change_password` — pre: old password verifies else `BAD_PASSWORD`; `old == new` else `WEAK_PASSWORD` "the new password must differ from the current one"; post: new scrypt hash, `session_version` + 1, `must_change_password=False` — web_accounts.py:356-370,363-369 [DERIVED].
- `create_key` — pre: account exists (`NOT_FOUND`), active keys < `MAX_ACTIVE_KEYS` else `KEY_LIMIT` `f"at most {MAX_ACTIVE_KEYS} active keys: revoke one first"`; post: returns raw bearer once, stores only the record from `P.new_bearer()` — web_accounts.py:452-466,457-465 [DERIVED].
- `rotate_invite` — first code or replacement; old code refused afterwards; `created_at` preserved, `rotated_at` set; returns new code — web_accounts.py:263-270 [DERIVED].

## effect surface
- env: `POLYMATH_WEB_SESSION_SECRET` = `''` (web_accounts.py:374-376); `POLYMATH_MCP_PRINCIPALS_FILE` = `''` (web_accounts.py:88-90).
- files: registry JSON read/written via `P.read_registry`/`P.write_registry` under exclusive `fcntl.flock` (web_accounts.py:98,105-110); sidecar lock file `.{name}.lock` created `0o600` next to the registry (web_accounts.py:95-101).
- cookie/header names: `polymath_session`, `polymath_csrf`, `x-polymath-csrf` (web_accounts.py:47) — set/read by the boundary, not here.
- tables read/written: none (FACTS `tables_read`/`tables_written` empty). Network/subprocess: none visible in SOURCE.
- imports: `orchestrator`, `orchestrator.mcp_principals` (FACTS.imports; web_accounts.py:37).

## invariants
INVARIANT: MIN_PASSWORD = 1 and `password_problem` refuses only a non-str/empty password — web_accounts.py:41,63-64 [DERIVED]
  fails-if: empty passwords become storable; owner rule of 2026-09-27 violated.
INVARIANT: every password mutation or disable bumps `session_version` by 1 (set_owner_password 165, set_friend_enabled 208, reset_friend_password 217, change_password 369) and `resolve_session` requires version equality — web_accounts.py:409 [DERIVED]
  fails-if: old cookies keep working after a reset/disable.
INVARIANT: scrypt params fixed `_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}`, salt 16 bytes, stored format `scrypt${n}${r}${p}${s}${d}` — web_accounts.py:49,69-71 [DERIVED]
  fails-if: stored hashes unparseable by `verify_password` (returns False, all logins dead).
INVARIANT: MAX_ACTIVE_KEYS = 3 and `create_key` refuses when active keys >= 3 — web_accounts.py:46,458-460 [DERIVED]
  fails-if: unbounded bearer keys per friend.
INVARIANT: private corpus `"fr-" + username` is always in `corpus_ids` and the sole `writable_corpus_ids` entry — web_accounts.py:197-198,227-228 [DERIVED]
  fails-if: friend loses their private library or gains write to shared corpora.
INVARIANT: `public_record` output keys are exactly principal_id, username, name, enabled, corpus_ids, writable_corpus_ids, adapter_ids, must_change_password, created_at, active_keys — never `password_hash` — web_accounts.py:233-240 [DERIVED]
  fails-if: hash leaks to owner admin UI / friend Settings.
INVARIANT: throttle = 5 failures per key (username, address) per 900 s — web_accounts.py:12,423 [DERIVED]
  fails-if: online guessing becomes feasible (MIN_PASSWORD is 1, throttle is the guard).
INVARIANT: SESSION_TTL_S = 7 * 24 * 3600 and `read_session` rejects `e <= now` — web_accounts.py:48,395 [DERIVED]
  fails-if: expired cookies accepted.
INVARIANT: invite space = 3 groups x 4 chars from 31-char alphabet (31^12 ≈ 2^59 codes) — web_accounts.py:42-43 [DERIVED]
  fails-if: codes brute-forceable within the (absent) invite-specific throttle.
INVARIANT: `_DUMMY_HASH` verified for unknown users so unknown/known timing matches — web_accounts.py:350,502 [DERIVED]
  fails-if: username enumeration via response timing.
INVARIANT: `session_secret()` returns None iff env secret length < 32 — web_accounts.py:374-376 [DERIVED]
  fails-if: short secret silently disables session signing at the boundary. [INFERRED: make_session needs a `secret: bytes`, None is never a valid key]

## determinism & idempotency
determinism: NONDETERMINISTIC — random: `secrets.token_bytes` web_accounts.py:69, `secrets.token_urlsafe` web_accounts.py:381,502, `secrets.choice` web_accounts.py:250; clock: `datetime.now` web_accounts.py:149,333, `time.time` web_accounts.py:382,395,435,440; concurrency: `fcntl.flock` web_accounts.py:98, `threading.Lock` web_accounts.py:426.
idempotency: UNSAFE — `rotate_invite` invalidates the previous code on every call (web_accounts.py:263-270); `add_friend`/`register_friend` append a principal (second call hits `EXISTS`/`USERNAME_TAKEN`); `create_key` adds a new key each call; registry is read-modify-write under the file lock (web_accounts.py:105-110).

## failure behaviour
- `AccountError(code, message)`: `code` stable, message safe to show, never carries a secret — web_accounts.py:52-58 [DERIVED]. Codes raised: `BAD_USERNAME` (120,127,176), `WEAK_PASSWORD` (155,371), `EXISTS` (181), `NOT_FOUND` (206,221,462,474), `USERNAME_INVALID` (279), `USERNAME_TAKEN` (281,285,304), `INVITES_OFF` (299), `INVITE_INVALID` (301), `BAD_PASSWORD` (369), `KEY_LIMIT` (465).
- `verify_password` swallows `ValueError`/`TypeError` from a malformed stored hash and returns False — web_accounts.py:82-83 [DERIVED].
- `read_session` returns None on split/signature/expiry failure — web_accounts.py:393-396 [DERIVED]; `_identity` returns None for inactive friends (`P._active` check) — web_accounts.py:333-334 [DERIVED].
- `authenticate_password` returns None (after dummy verify) rather than raising — web_accounts.py:349-351 [DERIVED].

## dumb-code flags
- `OWNER_USERNAME = "king"` (web_accounts.py:44) duplicated as default `display_name: str = "King"` (web_accounts.py:160) — two literals for one person.
- `MIN_PASSWORD = 1` makes `len(password) < MIN_PASSWORD` an empty-string check dressed as a policy constant — web_accounts.py:41,63 [DERIVED].
- `_DUMMY_HASH = hash_password(secrets.token_urlsafe(18))` runs scrypt at import time: import cost + module-level nondeterminism even if never used — web_accounts.py:502 [DERIVED].
- `CSRF_COOKIE = "polymath_csrf"` defined at web_accounts.py:47 but never referenced elsewhere in this file — only `CSRF_HEADER` is checked via `csrf_ok` (web_accounts.py:414-416). [DERIVED]
- `register_friend` lowercases/strips the typed code (web_accounts.py:294) though `INVITE_ALPHABET` cannot produce uppercase — harmless double normalization. [INFERRED: normalization for hand-typed codes]

## refactor notes
- Error-code strings are a UI contract (`code` is stable — web_accounts.py:53); renaming any of the 10 codes breaks `api/web_auth.py` / `api/web_settings.py` and `_small-modules` (FACTS.importers).
- `_friend_record` is "the one shape of a friend" shared by owner Add-friend and self sign-up (web_accounts.py:193-194,305) — any field change must touch both paths plus `mcp_principals` consumers of the registry.
- Stored-hash format `scrypt$n$r$p$s$d` (web_accounts.py:71) is the parse contract of `verify_password` (web_accounts.py:76-81); changing it orphans existing hashes.
- Session payload keys `"p"`,`"v"`,`"e"`,`"c"` and cookie names `polymath_session`/`polymath_csrf`/header `x-polymath-csrf` (web_accounts.py:47,387) are consumed by `web_boundary.py` (web_accounts.py:5-6) — format change logs everyone out.
- Hard dependency on `mcp_principals` symbols: `P.OWNER_ID`, `P.PRINCIPAL_ID_RE`, `P.read_registry`/`write_registry`, `P._active`, `P.new_bearer`, `P.FRIEND_PROFILE`, `P.UPLOAD_TEXT`, `P.HISTORY_READ`, `P.ADAPTER_CANCEL` (web_accounts.py:37,45,126,333,461) — drift there breaks validation here.
- Password policy line cites the owner's 2026-09-27 decision (web_accounts.py:41); raising `MIN_PASSWORD` contradicts a dated owner rule, not just a default.
- `P._active` is a private-name cross-module call (web_accounts.py:333) — rename in `mcp_principals` breaks this file silently.

## VERIFY
```verify
grep -Fq 'MAX_ACTIVE_KEYS = 3' orchestrator/orchestrator/web_accounts.py
grep -Fq 'OWNER_USERNAME = "king"' orchestrator/orchestrator/web_accounts.py
grep -Fq 'INVITE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"' orchestrator/orchestrator/web_accounts.py
grep -Fq 'SESSION_TTL_S = 7 * 24 * 3600' orchestrator/orchestrator/web_accounts.py
grep -Eq '\^\[a-z0-9\]\[a-z0-9_-\]\{1,31\}\$' orchestrator/orchestrator/web_accounts.py
test "$(grep -c -F 'AccountError(' orchestrator/orchestrator/web_accounts.py)" -ge 10
! grep -Fq 'print(' orchestrator/orchestrator/web_accounts.py
```
