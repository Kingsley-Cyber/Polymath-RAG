# unit: orchestrator/orchestrator/web_accounts.py
anchor: orchestrator/orchestrator/web_accounts.py:1-586

## purpose
Logins for the public web UI `rag.kingsleylab.xyz` (FRIENDS-ACCESS-V1, owner 2026-09-26): one identity store — the per-friend principal registry of `mcp_principals.py` — plus scrypt password hashing, HMAC-signed session cookies, login throttling, invite-code sign-up, and friend corpus grants (wildcard `["*"]` + private library `fr-<username>`, F6) — orchestrator/orchestrator/web_accounts.py:1-23 [DERIVED]. Nothing here trusts a request; the web boundary that uses it lives in `web_boundary.py` — orchestrator/orchestrator/web_accounts.py:5-6 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| AccountError | class | (code: str, message: str) -> ValueError with `.code` | orchestrator/orchestrator/web_accounts.py:65-70 | — |
| password_problem | def | (password: str) -> str \| None | orchestrator/orchestrator/web_accounts.py:74-78 | — |
| hash_password | def | (password: str) -> str `scrypt$...` | orchestrator/orchestrator/web_accounts.py:81-86 | — |
| verify_password | def | (password: str, stored: str \| None) -> bool | orchestrator/orchestrator/web_accounts.py:88-97 | — |
| registry_path | def | () -> Path \| None | orchestrator/orchestrator/web_accounts.py:101-103 | — |
| update_registry | def | (path: Path, change: Callable) -> Any | orchestrator/orchestrator/web_accounts.py:118-123 | — |
| read_registry | def | (path: Path) -> dict | orchestrator/orchestrator/web_accounts.py:126-127 | — |
| normalize_username | def | (username: str) -> str | orchestrator/orchestrator/web_accounts.py:130-134 | — |
| principal_id_for | def | (username: str) -> str `prn_<name>` | orchestrator/orchestrator/web_accounts.py:137-141 | — |
| private_corpus_for | def | (username: str) -> str `fr-<name>` | orchestrator/orchestrator/web_accounts.py:144-145 | — |
| set_owner_password | def | (path, password, display_name="King") -> None | orchestrator/orchestrator/web_accounts.py:185-192 | — |
| add_friend | def | (path, username, password, *, display_name="", corpus_ids=(), adapter_ids=(), must_change=True) -> dict | orchestrator/orchestrator/web_accounts.py:195-214 | — |
| set_friend_enabled | def | (path, username, enabled) -> None | orchestrator/orchestrator/web_accounts.py:230-237 | — |
| reset_friend_password | def | (path, username, password) -> None | orchestrator/orchestrator/web_accounts.py:240-247 | — |
| set_friend_corpora | def | (path, username, corpus_ids) -> dict | orchestrator/orchestrator/web_accounts.py:250-260 | — |
| set_friend_all_libraries | def | (path, username) -> dict | orchestrator/orchestrator/web_accounts.py:263-265 | — |
| public_record | def | (rec) -> dict (never a hash) | orchestrator/orchestrator/web_accounts.py:268-278 | — |
| private_library_autocreate | def | () -> bool | orchestrator/orchestrator/web_accounts.py:286-288 | — |
| ensure_private_library | def | (corpus_id: str) -> bool | orchestrator/orchestrator/web_accounts.py:291-311 | — |
| list_friends | def | (doc) -> list[dict] | orchestrator/orchestrator/web_accounts.py:325-326 | — |
| new_invite_code | def | () -> str | orchestrator/orchestrator/web_accounts.py:330-332 | — |
| invite_code | def | (doc) -> str \| None | orchestrator/orchestrator/web_accounts.py:340-342 | — |
| rotate_invite | def | (path) -> str | orchestrator/orchestrator/web_accounts.py:345-352 | — |
| register_friend | def | (path, username, password, code, *, corpus_ids=(), adapter_ids=()) -> dict | orchestrator/orchestrator/web_accounts.py:370-392 | — |
| WebIdentity | dataclass | principal_id, username, display_name, is_owner, session_version, must_change_password=False | orchestrator/orchestrator/web_accounts.py:396-403 | — |
| identity_for | def | (doc, username) -> WebIdentity \| None | orchestrator/orchestrator/web_accounts.py:424-428 | — |
| authenticate_password | def | (doc, username, password) -> WebIdentity \| None | orchestrator/orchestrator/web_accounts.py:431-437 | — |
| change_password | def | (path, principal_id, old, new) -> None | orchestrator/orchestrator/web_accounts.py:440-454 | — |
| session_secret | def | () -> bytes \| None | orchestrator/orchestrator/web_accounts.py:458-460 | — |
| make_session | def | (secret, ident, now=None, ttl_s=SESSION_TTL_S) -> (cookie, csrf) | orchestrator/orchestrator/web_accounts.py:463-468 | — |
| read_session | def | (secret, cookie, now=None) -> dict \| None | orchestrator/orchestrator/web_accounts.py:471-481 | — |
| resolve_session | def | (doc, payload) -> WebIdentity \| None | orchestrator/orchestrator/web_accounts.py:484-495 | — |
| csrf_ok | def | (payload, header_value) -> bool | orchestrator/orchestrator/web_accounts.py:498-500 | — |
| LoginThrottle | class | (limit=5, window_s=900); allowed/failed/succeeded | orchestrator/orchestrator/web_accounts.py:504-532 | — |
| create_key | def | (path, principal_id, label="") -> (raw bearer, public key) | orchestrator/orchestrator/web_accounts.py:536-550 | — |
| revoke_key | def | (path, principal_id, key_id) -> None | orchestrator/orchestrator/web_accounts.py:553-560 | — |
| list_keys | def | (doc, principal_id) -> list[dict] | orchestrator/orchestrator/web_accounts.py:563-565 | — |
| public_key | def | (key) -> dict | orchestrator/orchestrator/web_accounts.py:568-570 | — |

Module imported by (FACTS.importers, symbol-level mapping not in FACTS): `orchestrator/orchestrator/_small-modules`, `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/api/web_settings.py`, `orchestrator/orchestrator/web_scope.py`.

## contracts
**add_friend** — orchestrator/orchestrator/web_accounts.py:195-214
- in: username normalized by `USERNAME_RE`; name `king` refused `BAD_USERNAME` — orchestrator/orchestrator/web_accounts.py:199-202.
- out: `public_record(rec)` — no password hash — orchestrator/orchestrator/web_accounts.py:210.
- post: `_create_private_library(private_corpus_for(name))` runs after the registry write, best effort — orchestrator/orchestrator/web_accounts.py:213.
- pre/error: raises `EXISTS` when `_taken(doc, name, pid)` — orchestrator/orchestrator/web_accounts.py:206-207.

**register_friend** — orchestrator/orchestrator/web_accounts.py:370-392
- under the registry lock, in order: `INVITES_OFF` (no code) — orchestrator/orchestrator/web_accounts.py:380-381; `INVITE_INVALID` via `secrets.compare_digest`, checked before the username — orchestrator/orchestrator/web_accounts.py:382-383; `USERNAME_INVALID` / `USERNAME_TAKEN` — orchestrator/orchestrator/web_accounts.py:384-385; `WEAK_PASSWORD` via `_new_web` — orchestrator/orchestrator/web_accounts.py:387,177-180.
- out: same record as `add_friend` but `must_change=False`; private library created only for a sign-up that passed every check — orchestrator/orchestrator/web_accounts.py:387,390-391.

**_grant(corpus_ids, private)** — orchestrator/orchestrator/web_accounts.py:148-157
- a foreign private library raises `PRIVATE_LIBRARY` — orchestrator/orchestrator/web_accounts.py:152-154.
- `QS.ALL_LIBRARIES` present -> exactly `["*", private]`; else sorted union always including `private` — orchestrator/orchestrator/web_accounts.py:155-157.

**authenticate_password** — orchestrator/orchestrator/web_accounts.py:431-437
- unknown user: `verify_password(str(password), _DUMMY_HASH)` then `None` (no timing oracle) — orchestrator/orchestrator/web_accounts.py:434.
- compare is constant time: `hmac.compare_digest(got, want)` — orchestrator/orchestrator/web_accounts.py:97.

**make_session / read_session** — orchestrator/orchestrator/web_accounts.py:463-481
- payload keys `{"p": principal_id, "v": session_version, "e": expiry, "c": csrf}`; cookie = `f"{body}.{sig}"` — orchestrator/orchestrator/web_accounts.py:465-467.
- read: signature checked with `hmac.compare_digest`; `int(payload.get("e") or 0) <= now` -> None — orchestrator/orchestrator/web_accounts.py:473-479.

**resolve_session** — orchestrator/orchestrator/web_accounts.py:484-495
- post: returns identity only if `found[0].session_version != payload.get("v")` is false — orchestrator/orchestrator/web_accounts.py:493.

**change_password** — orchestrator/orchestrator/web_accounts.py:440-454
- `BAD_PASSWORD` when the old password fails; `WEAK_PASSWORD` when `old == new`; bumps `session_version` by 1 — orchestrator/orchestrator/web_accounts.py:447-453.

**ensure_private_library** — orchestrator/orchestrator/web_accounts.py:291-311
- pre: id must be `fr-<username>` else `BAD_LIBRARY` — orchestrator/orchestrator/web_accounts.py:296-298.
- out: `False` when autocreate off; `True` = row exists — orchestrator/orchestrator/web_accounts.py:299-300,310.
- post: `INSERT INTO corpora ... ON CONFLICT (corpus_id) DO NOTHING`; raises on DB failure — orchestrator/orchestrator/web_accounts.py:307-310,294-295.

**create_key** — orchestrator/orchestrator/web_accounts.py:536-550
- `KEY_LIMIT` when active keys >= `MAX_ACTIVE_KEYS` (3); raw bearer from `P.new_bearer()`; label truncated `[:60]`; raw shown once, never stored — orchestrator/orchestrator/web_accounts.py:543-549.

**LoginThrottle** — orchestrator/orchestrator/web_accounts.py:504-532
- `allowed(keys)` true while every key's live failure deque is `< limit` (5) in `window_s` (900); `succeeded` drops the keys — orchestrator/orchestrator/web_accounts.py:507,521,529-532.

## effect surface
- Postgres: writes `corpora` via `INSERT INTO corpora (corpus_id, name, config_hash, embedding_contract_id, purpose, query_enabled)` — orchestrator/orchestrator/web_accounts.py:307-310 (FACTS `tables_written: ["corpora"]`, `tables_read: []`).
- Files: the principals registry via `POLYMATH_MCP_PRINCIPALS_FILE` — orchestrator/orchestrator/web_accounts.py:102-103; sidecar lock file `.{path.name}.lock` under `fcntl.flock(LOCK_EX)` — orchestrator/orchestrator/web_accounts.py:109-111.
- Cookies / header names: `"polymath_session"`, `"polymath_csrf"`, `"x-polymath-csrf"` — orchestrator/orchestrator/web_accounts.py:60.
- Env flags: `POLYMATH_MCP_PRINCIPALS_FILE` = `''` — orchestrator/orchestrator/web_accounts.py:102; `POLYMATH_WEB_SESSION_SECRET` = `''` — orchestrator/orchestrator/web_accounts.py:459; `POLYMATH_PRIVATE_LIBRARY_AUTOCREATE` = `'1'` — orchestrator/orchestrator/web_accounts.py:288.
- Qdrant / network / subprocess: none appear in FACTS or SOURCE.

## invariants
INVARIANT: SESSION_TTL_S = 7 * 24 * 3600 (604800 s) — orchestrator/orchestrator/web_accounts.py:61 [DERIVED]
  fails-if: session lifetime silently stops being one week.
INVARIANT: scrypt n=2**14, r=8, p=1, dklen=32 with a 16-byte random salt; params re-read from the stored string on verify — orchestrator/orchestrator/web_accounts.py:62,82,90-94 [DERIVED]
  fails-if: hashes written with other params fail verification or weaken.
INVARIANT: session_secret() -> None when secret length < 32 — orchestrator/orchestrator/web_accounts.py:459-460 [DERIVED]
  fails-if: short secret silently disables signed sessions at the boundary.
INVARIANT: allowed() == (live failures per key < 5 within 900 s) — orchestrator/orchestrator/web_accounts.py:507,521 [DERIVED]
  fails-if: brute-force lockout regresses (docstring promise: 5 per username/address in 15 min — orchestrator/orchestrator/web_accounts.py:12).
INVARIANT: active keys per principal <= MAX_ACTIVE_KEYS = 3 — orchestrator/orchestrator/web_accounts.py:59,543-544 [DERIVED]
  fails-if: KEY_LIMIT never fires.
INVARIANT: invite code = INVITE_GROUPS(3) x INVITE_GROUP_LEN(4) over the 31-char INVITE_ALPHABET — orchestrator/orchestrator/web_accounts.py:55-56 [DERIVED]
  fails-if: codes become guessable or unreadable aloud.
INVARIANT: USERNAME_RE = `^[a-z0-9][a-z0-9_-]{1,31}$` governs both sign-up and the owner's Add friend — orchestrator/orchestrator/web_accounts.py:52 [DERIVED]
  fails-if: the two paths accept different names.
INVARIANT: payload["v"] == the account's current session_version or resolve_session -> None — orchestrator/orchestrator/web_accounts.py:493 [DERIVED]
  fails-if: a password change / reset / disable no longer kills earlier cookies (docstring promise — orchestrator/orchestrator/web_accounts.py:9-11).
INVARIANT: `_grant` output always contains the friend's own private library, never another friend's — orchestrator/orchestrator/web_accounts.py:152-157 [DERIVED]
  fails-if: friend loses their write target, or cross-friend leakage.
INVARIANT: private corpus id = `QS.PRIVATE_LIBRARY_PREFIX + username` (i.e. `fr-<username>`); principal id = `"prn_" + username`, != P.OWNER_ID — orchestrator/orchestrator/web_accounts.py:138-145,296-298 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (random: `secrets.token_bytes` orchestrator/orchestrator/web_accounts.py:82 salt, `secrets.token_urlsafe` :465 CSRF and :586 dummy hash at import; clock: `datetime.now` :174,:417, `time.time` :466,:479,:519,:524; db INSERT :307) [DERIVED]
idempotency: SAFE (registry writes are read-modify-write under an exclusive flock orchestrator/orchestrator/web_accounts.py:111,:118-123; `ensure_private_library` is `ON CONFLICT (corpus_id) DO NOTHING` :308) — `rotate_invite` deliberately issues a fresh code each call :345-352 [DERIVED]

## failure behaviour
- `Exception` swallowed -> `log.warning("private library not created at friend creation", extra={"event": "web_accounts.private_library_failed", "error_code": type(exc).__name__})` — no secret, no name; the caller still sees a created account, repair left to `web_scope.ensure_own_private_library` or `scripts/web_accounts.py ensure-libraries` — orchestrator/orchestrator/web_accounts.py:314-322 [DERIVED].
- `verify_password` returns `False` on malformed/missing stored hash (`ValueError`, `TypeError`) — orchestrator/orchestrator/web_accounts.py:88-96.
- `read_session` returns `None` on bad signature, malformed cookie, or expiry — orchestrator/orchestrator/web_accounts.py:472-479.
- AccountError codes raised: `BAD_USERNAME` :133,:140,:201, `WEAK_PASSWORD` :179,:449, `PRIVATE_LIBRARY` :154, `EXISTS` :206, `NOT_FOUND` :233,:243,:530,:547, `USERNAME_INVALID`/`USERNAME_TAKEN` :356-367, `INVITES_OFF`/`INVITE_INVALID` :380-383, `BAD_PASSWORD` :448, `BAD_LIBRARY` :298, `KEY_LIMIT` :544 [DERIVED].

## dumb-code flags
- `MIN_PASSWORD = 1` — "any non-empty password" is the only rule; the throttle is the guard — orchestrator/orchestrator/web_accounts.py:54,76-77 [DERIVED].
- `INVITE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"` (31 chars, no 0/o/1/l/i); comment claims `31^12 ≈ 2^59` — orchestrator/orchestrator/web_accounts.py:55-56 [DERIVED].
- `PRIVATE_LIBRARY_CONFIG_HASH = "web-private-library-v1"` — placeholder: `corpora.config_hash is NOT NULL; nothing reads it` — orchestrator/orchestrator/web_accounts.py:282-283 [DERIVED].
- `_DUMMY_HASH = hash_password(secrets.token_urlsafe(18))` at module import — importing the module runs one scrypt — orchestrator/orchestrator/web_accounts.py:586,82 [DERIVED].
- `CSRF_COOKIE = "polymath_csrf"` is defined while the CSRF token also rides inside the signed session — orchestrator/orchestrator/web_accounts.py:60,463-465 [DERIVED].
- Username lowercasing duplicated: `str(username or "").strip().lower()` in `_identity` vs `normalize_username` — a bad shape returns `None` here instead of `AccountError` — orchestrator/orchestrator/web_accounts.py:407-408,130-131,413-416 [INFERRED: two normalization paths can drift].
- Display-name default `"King"` hard-coded in `set_owner_password` — orchestrator/orchestrator/web_accounts.py:185 [DERIVED].

## refactor notes
- Blast radius: imported by `api/web_auth.py`, `api/web_settings.py`, `web_scope.py`, `_small-modules` (FACTS.importers); the web boundary itself is `web_boundary.py` — orchestrator/orchestrator/web_accounts.py:5-6 [DERIVED]. Signature changes hit all of them.
- The friend record shape is the single shape for owner-add and self-signup; it is coupled to `mcp_principals` (`P.read_registry`/`P.write_registry`, `P.OWNER_ID`, `P.PRINCIPAL_ID_RE`, `P._active`, `P.new_bearer`, `FRIEND_SCOPES`) — orchestrator/orchestrator/web_accounts.py:47-48,58,119-122,138-140,417,545 and :221-227 [DERIVED].
- Wildcard `["*"]` (QS.ALL_LIBRARIES) is resolved per request by `web_scope`; `set_friend_all_libraries` depends on the token — orchestrator/orchestrator/web_accounts.py:18-20,263-265 [DERIVED].
- `POLYMATH_PRIVATE_LIBRARY_AUTOCREATE=0` is the test-session fence (`tests/conftest.py`); removing it makes a test registry write libraries into the live database — orchestrator/orchestrator/web_accounts.py:22-23,286-288 [DERIVED].
- Session payload keys `p/v/e/c` and the `body.sig` cookie format: changing them invalidates every existing cookie (version bump already does per account) — orchestrator/orchestrator/web_accounts.py:465-467,493 [DERIVED].
- `ensure_private_library` reads `get_settings().stores.embedding_contract_id` at insert time — settings schema is part of the contract — orchestrator/orchestrator/web_accounts.py:309 [DERIVED].

## VERIFY
```verify
grep -Fq 'OWNER_USERNAME = "king"' orchestrator/orchestrator/web_accounts.py
grep -Fq 'SESSION_TTL_S = 7 * 24 * 3600' orchestrator/orchestrator/web_accounts.py
grep -Fq 'ON CONFLICT (corpus_id) DO NOTHING' orchestrator/orchestrator/web_accounts.py
grep -Fq 'def __init__(self, limit: int = 5, window_s: int = 900) -> None:' orchestrator/orchestrator/web_accounts.py
test "$(grep -c -F 'session_version' orchestrator/orchestrator/web_accounts.py)" -ge 8
! grep -Fq 'md5' orchestrator/orchestrator/web_accounts.py
```
