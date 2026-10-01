# unit: orchestrator/orchestrator/api/web_settings.py
anchor: orchestrator/orchestrator/api/web_settings.py:1-326

## purpose
Settings API routes for the Polymath web UI: a friend's own API keys and copy-paste connect prompt, the owner's friend admin (add/enable/disable/reset-password/library grants/key revocation), and the INVITE-SIGNUP invite code (read + rotate) — `orchestrator/orchestrator/api/web_settings.py:1-12` [DERIVED]. Identity is decided upstream at the web boundary via `request.state.web_identity`; a direct loopback caller is the owner — `orchestrator/orchestrator/api/web_settings.py:4-7` [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | var | `APIRouter()` | web_settings.py:29 | main.py (module importer) [INFERRED from FACTS.importers] |
| `KEY_PLACEHOLDER` | const | `= "<YOUR_KEY>"` | web_settings.py:30 | — |
| `KeyBody` | class | `label: str = Field(default="", max_length=60)` | web_settings.py:33-34 | — |
| `FriendBody` | class | `username, display_name, corpus_ids, adapter_ids` | web_settings.py:37-41 | — |
| `CorporaBody` | class | `corpus_ids: list[str]` | web_settings.py:44-45 | — |
| `mcp_url` | def | `() -> str` | web_settings.py:69-70 | — |
| `connect_command` | def | `() -> str` | web_settings.py:77-79 | — |
| `usage_lines` | def | `(libraries, private, *, owner) -> str` | web_settings.py:82-98 | — |
| `owner_prompt` | def | `(libraries) -> str` | web_settings.py:101-106 | — |
| `connect_prompt` | def | `(key, libraries, private, url=None, *, owner=False) -> str` | web_settings.py:109-134 | — |
| `friend_defaults` | def | `() -> tuple[list[str], list[str]]` | web_settings.py:229-232 | web_auth.py `/auth/register` [INFERRED from docstring] |
| `my_keys` | route | `GET /keys (request) -> JSONResponse` | web_settings.py:142-150 | — |
| `create_my_key` | route | `POST /keys (body: KeyBody, request) -> JSONResponse` | web_settings.py:153-165 | — |
| `revoke_my_key` | route | `DELETE /keys/{key_id} (key_id, request) -> JSONResponse` | web_settings.py:168-176 | — |
| `prompt_template` | route | `GET /keys/prompt (request) -> JSONResponse` | web_settings.py:179-194 | — |
| `owner_key_for_copy` | route | `GET /keys/owner (request) -> JSONResponse` | web_settings.py:197-213 | — |
| `list_friends` | route | `GET /admin/friends (request) -> JSONResponse` | web_settings.py:241-245 | — |
| `add_friend` | route | `POST /admin/friends (body: FriendBody, request) -> JSONResponse` | web_settings.py:248-261 | — |
| `friend_action` | route | `POST /admin/friends/{username}/{action} -> JSONResponse` | web_settings.py:264-277 | — |
| `set_libraries` | route | `PUT /admin/friends/{username}/libraries (body: CorporaBody, request) -> JSONResponse` | web_settings.py:280-288 | — |
| `get_invite` | route | `GET /friends/invite (request) -> JSONResponse` | web_settings.py:296-300 | — |
| `rotate_invite` | route | `POST /friends/invite/rotate (request) -> JSONResponse` | web_settings.py:303-309 | — |
| `friend_keys` | route | `GET /admin/friends/{username}/keys -> JSONResponse` | web_settings.py:312-315 | — |
| `revoke_friend_key` | route | `DELETE /admin/friends/{username}/keys/{key_id} -> JSONResponse` | web_settings.py:318-324 | — |

Importers of the module: `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/main.py` (FACTS.importers).

## contracts
**`my_keys` (GET /keys)** — web_settings.py:142-150
- in: `request` carrying `request.state.web_identity`
- out: owner → `{"is_owner": True, "keys": [], "max_active": None, "mcp_url": ..., "note": "your admin key is POLYMATH_MCP_API_KEY in the server's .env; it is never shown here"}`; friend → `is_owner: False`, `W.list_keys(doc, principal_id)`, `max_active: W.MAX_ACTIVE_KEYS`
- pre: identity already resolved by boundary
- post: response header `cache-control: no-store`

**`create_my_key` (POST /keys)** — web_settings.py:153-165
- in: `KeyBody.label` (default `""`, max 60)
- pre: caller is a friend; owner or missing identity → 409 `OWNER_USES_ENV_KEY`
- out: 201 `{"key": raw, ...key, "shown_once": True, "prompt": connect_prompt(raw, corpus_ids, private)}`; raw key returned ONCE
- post: key persisted via `W.create_key(_path(), principal_id, label)`; `W.AccountError` code `KEY_LIMIT` → 409, any other code → 400

**`revoke_my_key` (DELETE /keys/{key_id})** — web_settings.py:168-176
- pre: key_id must belong to caller, else 404 `NOT_FOUND` ("no such key"); owner → 409 `OWNER_USES_ENV_KEY`
- post: `W.revoke_key(_path(), principal_id, key_id)`; returns `{"revoked": key_id}`

**`prompt_template` (GET /keys/prompt)** — web_settings.py:179-194
- out owner: `{"prompt": owner_prompt(libraries), "connect_command": connect_command(), "key_included": False, "placeholder": None, "mcp_url": ...}` — no key in the answer
- out friend: `{"prompt": connect_prompt(KEY_PLACEHOLDER, corpus_ids, private), "placeholder": "<YOUR_KEY>", "mcp_url": ...}` — no `connect_command`/`key_included` fields (shape differs from owner branch) [DERIVED]

**`owner_key_for_copy` (GET /keys/owner)** — web_settings.py:197-213
- pre: owner only (non-owner identity → 403 `OWNER_ONLY`, "the boundary already refuses; belt and braces"); `POLYMATH_MCP_API_KEY` set, else 404 `OWNER_KEY_NOT_SET`
- out: `{"key": key, "mcp_url": ..., "prompt": connect_prompt(key, libraries, None, owner=True)}`; `no-store`

**`add_friend` (POST /admin/friends)** — web_settings.py:248-261
- in: `FriendBody` (`username` min 2 / max 32, `display_name` default `""` max 80, `corpus_ids`/`adapter_ids` `None` = all shared libraries / all adapters)
- pre: owner; any corpus_id starting `"fr-"` → 400 `PRIVATE_LIBRARY` ("another friend's private library cannot be shared")
- post: `W.add_friend(..., corpus_ids=libraries, adapter_ids=adapters)`; first password = `secrets.token_urlsafe(12)`; out 201 `{"friend": rec, "first_password": first, "shown_once": True}`; `EXISTS` → 409, other `W.AccountError` → 400

**`friend_action` (POST /admin/friends/{username}/{action})** — web_settings.py:264-277
- in: `action` ∈ `enable`, `disable`, `reset-password`; anything else → 404 `UNKNOWN_ACTION` ("use enable, disable or reset-password")
- post: reset-password mints `secrets.token_urlsafe(12)`, returns `{"reset": username, "first_password": ..., "shown_once": True}`; `NOT_FOUND` → 404, other `W.AccountError` → 400

**`set_libraries` (PUT /admin/friends/{username}/libraries)** — web_settings.py:280-288
- pre: owner; `"fr-"` prefix rejected 400 `PRIVATE_LIBRARY`
- post: `W.set_friend_corpora`; `W.AccountError` → 404 with the account error's code

**`get_invite` / `rotate_invite`** — web_settings.py:291-309
- out: `_invite_payload` = `{"code": rec.get("code") or None, "rotated_at": rec.get("rotated_at") or None}`; `code` is `null` until the first rotate — web_settings.py:291-293, 298 [DERIVED]
- post: rotate calls `W.rotate_invite(path)` then returns the payload from `W.read_registry(path)`; "Never cached, never logged"

**`friend_keys` / `revoke_friend_key`** — web_settings.py:312-324
- in: username resolved via `W.principal_id_for(username)`
- post: revoke maps `W.AccountError` → 404 with its code

**`_refuse` error envelope** — every refusal is `HTTPException(status_code=status, detail={"error_code": code, "message": message})` — web_settings.py:48-49 [DERIVED]

## effect surface
- Postgres: table `corpora` read (`SELECT corpus_id FROM corpora ORDER BY corpus_id`) — web_settings.py:219-221; no tables written by this module [DERIVED from FACTS.tables_written = []].
- File (registry): principals JSON at `W.registry_path()`; unset → 503 `ACCOUNTS_NOT_CONFIGURED` ("POLYMATH_MCP_PRINCIPALS_FILE is not set on this server") — web_settings.py:56-60. Written indirectly through `W.create_key`, `W.revoke_key`, `W.add_friend`, `W.set_friend_enabled`, `W.reset_friend_password`, `W.set_friend_corpora`, `W.rotate_invite`.
- File (path only, never executed here): `CONNECT_SCRIPT = REPO_ROOT / "scripts" / "connect_agents.sh"`, quoted with `shlex.quote` into a command string — web_settings.py:73-74, 77-79.
- Env: `POLYMATH_PUBLIC_MCP_URL` default `'https://mcp.kingsleylab.xyz/mcp'` — web_settings.py:70; `POLYMATH_MCP_API_KEY` default null (read for `/keys/owner`) — web_settings.py:206.
- Random: `secrets.token_urlsafe(12)` at web_settings.py:256 and web_settings.py:272.
- No outbound network calls or subprocess launches in this module; `polymath_search` / `polymath_explore` / `polymath_answer` occur only as tool-name literals inside `usage_lines` prompt text — web_settings.py:92-98 [DERIVED].

## invariants
INVARIANT: raw key exposure happens exactly once, at creation — create response sets `"shown_once": True` — web_settings.py:164 [DERIVED]
  fails-if: a friend cannot recover a lost key; must mint a new one (bounded by `W.MAX_ACTIVE_KEYS`).
INVARIANT: owner has no web-made keys — `create_my_key`/`revoke_my_key` refuse owner with 409 `OWNER_USES_ENV_KEY`; `my_keys` returns `"keys": []` for owner — web_settings.py:146-147, 156-157, 171-172 [DERIVED]
  fails-if: owner key would live in the registry file instead of `.env`, contradicting the module contract at web_settings.py:5-7.
INVARIANT: no corpus_id passed to a friend starts with `"fr-"` — filtered in `_shared_libraries` and rejected (400 `PRIVATE_LIBRARY`) in `add_friend` and `set_libraries` — web_settings.py:221, 252-254, 283-284 [DERIVED]
  fails-if: one friend gains read access to another friend's private library.
INVARIANT: first passwords are `secrets.token_urlsafe(12)` in both mint sites — web_settings.py:256, 272 [DERIVED]
  fails-if: unequal entropy or a guessable format across the two paths.
INVARIANT: every response passes through `_no_store` → header `cache-control: no-store` — web_settings.py:63-66 [DERIVED]
  fails-if: keys, invite codes, or prompts could sit in an intermediary cache (docstring promises "Never cached" at web_settings.py:298).
INVARIANT: `KEY_PLACEHOLDER == "<YOUR_KEY>"` and it is the only key value ever placed in `/keys/prompt` for a friend — web_settings.py:30, 193 [DERIVED]
  fails-if: a real key would leak through the prompt-template endpoint.
INVARIANT: `friend_defaults()` and the owner's Add friend start from the same `_shared_libraries()` + `_adapters()` lists — web_settings.py:229-232 [DERIVED]
  fails-if: self-signup grants a different default scope than the owner's manual add.
INVARIANT: owner's `my_keys` reports `"max_active": None` while friends report `W.MAX_ACTIVE_KEYS` — web_settings.py:146, 149 [DERIVED]
  fails-if: UI renders a key limit for the owner who cannot create keys here.

## determinism & idempotency
determinism: NONDETERMINISTIC (random: `secrets.token_urlsafe` at web_settings.py:256, 272; env: `POLYMATH_PUBLIC_MCP_URL` web_settings.py:70, `POLYMATH_MCP_API_KEY` web_settings.py:206; db: `corpora` read web_settings.py:219-221; file: `REGISTRY.get()` registry state)
idempotency: SAFE for revoke/enable/disable/set_libraries/get/list routes (pure reads or registry state transitions); UNSAFE for `create_my_key`, `add_friend`, `friend_action(reset-password)`, `rotate_invite` — each call mints a new secret or new code (web_settings.py:159, 256, 272, 307-308)

## failure behaviour
- `Exception` swallowed with `libraries = []` in `prompt_template` (owner branch) and `owner_key_for_copy` when `_shared_libraries()` fails — FACTS.fallbacks at web_settings.py:187, 211; comment: "the prompt still works without the list (list_corpora names them)". Caller still gets a 200 prompt whose library list reads `(none yet)` — web_settings.py:84 [DERIVED].
- `W.AccountError` re-raised as HTTP: `KEY_LIMIT`→409, `EXISTS`→409, `NOT_FOUND`→404, otherwise 400 — web_settings.py:160-161, 259-260, 275-276, 287-288, 323-324.
- Error codes raised by this module: `ACCOUNTS_NOT_CONFIGURED` 503 (web_settings.py:59), `OWNER_USES_ENV_KEY` 409 (157, 172), `NOT_FOUND` 404 (174), `OWNER_ONLY` 403 (205, 238), `OWNER_KEY_NOT_SET` 404 (208), `PRIVATE_LIBRARY` 400 (254, 284), `UNKNOWN_ACTION` 404 (277).

## dumb-code flags
- Magic number `12` in both `secrets.token_urlsafe(12)` calls — web_settings.py:256, 272.
- Duplicated belt-and-braces owner check: `owner_key_for_copy` inlines the same non-owner 403 `OWNER_ONLY` check that `_require_owner` performs — web_settings.py:203-205 vs 235-238.
- Duplicated `"fr-"` prefix logic in three places (`_shared_libraries` filter, `add_friend`, `set_libraries`) — web_settings.py:221, 252, 283; the literal `"fr-"` also appears in the docstring at web_settings.py:218.
- Asymmetric response shapes: friend branch of `prompt_template` omits `connect_command`/`key_included` that the owner branch returns — web_settings.py:189-190 vs 192-194.
- Bare `Exception` catch (noqa BLE001) duplicated verbatim in two functions — web_settings.py:186-188, 209-212.
- `_adapters` imports `polymath_shared.adapter.service` lazily inside the function, unlike all top-level imports — web_settings.py:224-226 [DERIVED].

## refactor notes
- Importers: `orchestrator/orchestrator/api/web_auth.py` and `orchestrator/orchestrator/main.py` mount this router / reuse `friend_defaults` — changing route paths or the `friend_defaults()` return shape breaks both — FACTS.importers, web_settings.py:229-232.
- Error envelope `{"error_code", "message"}` (web_settings.py:48-49) and every code literal (`OWNER_USES_ENV_KEY`, `PRIVATE_LIBRARY`, `ACCOUNTS_NOT_CONFIGURED`, `OWNER_KEY_NOT_SET`, `OWNER_ONLY`, `UNKNOWN_ACTION`, `KEY_LIMIT`, `EXISTS`, `NOT_FOUND`) is API surface; the web UI matches on these strings.
- `connect_prompt` output is embedded in three routes (`create_my_key`, `prompt_template`, `owner_key_for_copy`) and references `mcp_server/CONNECTORS.md` conventions; editing its text changes all three responses simultaneously — web_settings.py:109-134.
- `KEY_PLACEHOLDER` value `"<YOUR_KEY>"` is a UI contract — the Settings page substitutes it — web_settings.py:30, 193.
- The whole module delegates registry mutations to `web_accounts` (`W.create_key`, `W.revoke_key`, `W.add_friend`, `W.set_friend_enabled`, `W.reset_friend_password`, `W.set_friend_corpora`, `W.rotate_invite`, `W.read_registry`, `W.invite_record`, `W.principal_id_for`, `W.private_corpus_for`, `W.list_keys`, `W.list_friends`, `W.normalize_username`, `W.registry_path`, `W.MAX_ACTIVE_KEYS`, `W.AccountError`) — signature changes there land here — web_settings.py:25, 56-60, 149-175, 242-324.
- `_shared_libraries` reads table `corpora`; schema change to `corpora.corpus_id` breaks friend defaults and admin listings — web_settings.py:219-221.

## VERIFY
```verify
grep -Fq 'KEY_PLACEHOLDER = "<YOUR_KEY>"' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'https://mcp.kingsleylab.xyz/mcp' orchestrator/orchestrator/api/web_settings.py
grep -Eq 'secrets\.token_urlsafe\(12\)' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'OWNER_USES_ENV_KEY' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'cache-control' orchestrator/orchestrator/api/web_settings.py
! grep -Fq 'shown_once": False' orchestrator/orchestrator/api/web_settings.py
test "$(grep -c -F 'fr-' orchestrator/orchestrator/api/web_settings.py)" -ge 4
```
