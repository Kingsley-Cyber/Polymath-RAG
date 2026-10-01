# unit: orchestrator/orchestrator/api/web_settings.py
anchor: orchestrator/orchestrator/api/web_settings.py:1-335

## purpose
FastAPI settings router (FRIENDS-ACCESS-V1 F3 + INVITE-SIGNUP): a friend's own API keys and copy-paste connect prompt, and the owner's friend admin (list/add/enable/disable/reset-password/set-libraries/revoke-keys, invite code read/rotate) — `orchestrator/orchestrator/api/web_settings.py:1-7` [DERIVED]. Identity is decided upstream at the web boundary via `request.state.web_identity`; a DIRECT loopback caller is the owner — `orchestrator/orchestrator/api/web_settings.py:4-7` [DERIVED]. ONE-PROFILE: the owner gets one connect command (`scripts/connect_agents.sh`) and a key-free prompt instead of web-made keys — `orchestrator/orchestrator/api/web_settings.py:9-12` [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | var | `APIRouter()` | web_settings.py:29 | orchestrator/orchestrator/main.py (module importer; mounts routes) [INFERRED] |
| `KEY_PLACEHOLDER` | const | `= "<YOUR_KEY>"` | web_settings.py:30 | — |
| `KeyBody` | class | `label: str = Field(default="", max_length=60)` | web_settings.py:33-34 | — |
| `FriendBody` | class | `username (2..32), display_name (≤80), corpus_ids: list[str] \| None, adapter_ids: list[str] \| None` | web_settings.py:37-41 | — |
| `CorporaBody` | class | `corpus_ids: list[str]` | web_settings.py:44-45 | — |
| `mcp_url` | def | `() -> str` | web_settings.py:69-70 | — |
| `connector_url` | def | `(key: str) -> str` | web_settings.py:73-77 | — |
| `connect_command` | def | `() -> str` | web_settings.py:84-86 | — |
| `usage_lines` | def | `(libraries: list[str], private: str \| None, *, owner: bool) -> str` | web_settings.py:89-107 | — |
| `owner_prompt` | def | `(libraries: list[str]) -> str` | web_settings.py:110-115 | — |
| `connect_prompt` | def | `(key: str, libraries: list[str], private: str \| None, url: str \| None = None, *, owner: bool = False) -> str` | web_settings.py:118-143 | — |
| `friend_defaults` | def | `() -> tuple[list[str], list[str]]` | web_settings.py:239-242 | orchestrator/orchestrator/api/web_auth.py (module importer; `/auth/register` starts from the same lists per docstring web_settings.py:240-241) [INFERRED] |
| `my_keys` / `create_my_key` / `revoke_my_key` / `prompt_template` / `owner_key_for_copy` | route | GET/POST `/keys`, DELETE `/keys/{key_id}`, GET `/keys/prompt`, GET `/keys/owner` | web_settings.py:151, 162, 177, 188, 206 | — |
| `list_friends` / `add_friend` / `friend_action` / `set_libraries` | route | GET/POST `/admin/friends`, POST `/admin/friends/{username}/{action}`, PUT `/admin/friends/{username}/libraries` | web_settings.py:251, 258, 274, 290 | — |
| `get_invite` / `rotate_invite` | route | GET `/friends/invite`, POST `/friends/invite/rotate` | web_settings.py:306, 313 | — |
| `friend_keys` / `revoke_friend_key` | route | GET `/admin/friends/{username}/keys`, DELETE `/admin/friends/{username}/keys/{key_id}` | web_settings.py:322, 328 | — |

Module importers (FACTS): `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/main.py`.

## contracts

**`mcp_url`** — web_settings.py:69-70
- in: env `POLYMATH_PUBLIC_MCP_URL`, default `"https://mcp.kingsleylab.xyz/mcp"`; out: `str`.
- post: value used verbatim as the MCP server URL in every prompt — web_settings.py:122, 128.

**`connector_url(key)`** — web_settings.py:73-77
- in: `key: str`; out: `f"{base}/k/{key}/mcp"` where `base = mcp_url().rstrip("/")` minus a trailing `"/mcp"` suffix when present.
- pre: assumes MCP Server A `mcp_server.KeyInPath` relocates the path key into the Authorization header before anything else sees the request — web_settings.py:74-75.

**`connect_prompt(key, libraries, private, url=None, *, owner=False)`** — web_settings.py:118-143
- in: `url` defaults to `mcp_url()` (web_settings.py:122); out: text containing `Authorization: Bearer {key}` (web_settings.py:130), harness setup lines for Claude Code / Codex / Gemini CLI / OpenCode (web_settings.py:133-136), `usage_lines(...)` and a keep-private warning differing by `owner` (web_settings.py:123-124, 141, 143).

**`create_my_key(body: KeyBody, request)`** — web_settings.py:162-174
- pre: caller is a signed-in friend (`ident is None or ident.is_owner` → `409 OWNER_USES_ENV_KEY`, web_settings.py:164-166).
- out: `201` `{key: raw, **key, shown_once: True, prompt: connect_prompt(raw, ...)}` — raw key returned ONCE, never again — web_settings.py:173-174.
- post: `W.AccountError` with code `KEY_LIMIT` → `409`, any other code → `400` — web_settings.py:168-170.

**`revoke_my_key(key_id, request)`** — web_settings.py:177-185
- pre: `key_id` must appear in `W.list_keys(...)` for the caller, else `404 NOT_FOUND "no such key"` — web_settings.py:182-183.

**`prompt_template(request)`** — web_settings.py:188-203
- out owner/None: `{prompt: owner_prompt(libraries), connect_command, key_included: False, placeholder: None, mcp_url}` — no key ever in the answer — web_settings.py:198-199.
- out friend: prompt built with `KEY_PLACEHOLDER` — web_settings.py:202-203.

**`owner_key_for_copy(request)`** — web_settings.py:206-223
- pre: owner only (non-owner → `403 OWNER_ONLY`, belt and braces, web_settings.py:213-214); `POLYMATH_MCP_API_KEY` non-empty else `404 OWNER_KEY_NOT_SET` — web_settings.py:215-217.
- out: `{key, mcp_url, connector_url, prompt: connect_prompt(key, ..., owner=True)}`, `no-store` — web_settings.py:222-223.

**`_shared_libraries()`** — web_settings.py:227-231
- out: `SELECT corpus_id FROM corpora ORDER BY corpus_id`, every `corpus_id` not starting with `"fr-"` — web_settings.py:229-231.

**`add_friend(body: FriendBody, request)`** — web_settings.py:258-271
- in: `corpus_ids is None` → all shared libraries; `adapter_ids is None` → all adapters — web_settings.py:261, 265.
- pre: no corpus starting `"fr-"` else `400 PRIVATE_LIBRARY "another friend's private library cannot be shared"` — web_settings.py:262-264.
- out: `201 {friend, first_password: secrets.token_urlsafe(12), shown_once: True}`; `EXISTS` → `409`, else `400` — web_settings.py:266, 268-270, 271.

**`friend_action(username, action, request)`** — web_settings.py:274-287
- in: `action` ∈ `enable | disable | reset-password`; anything else → `404 UNKNOWN_ACTION "use enable, disable or reset-password"` — web_settings.py:278-284, 287.
- out (reset): `first_password = secrets.token_urlsafe(12)`, `shown_once: True` — web_settings.py:282-284.

**`set_libraries(username, body: CorporaBody, request)`** — web_settings.py:290-298
- pre: no `"fr-"` corpus else `400 PRIVATE_LIBRARY`; `W.AccountError` → `404` with the account code — web_settings.py:293-294, 297-298.

**`get_invite` / `rotate_invite`** — web_settings.py:306-319
- pre: `_require_owner`; out: `{code, rotated_at}` where `code` is `null` until the first rotate — web_settings.py:302-303, 308, 310.

**`_path()`** — web_settings.py:56-60
- post: raises `503 ACCOUNTS_NOT_CONFIGURED` when `W.registry_path()` is `None` (`POLYMATH_MCP_PRINCIPALS_FILE` unset).

## effect surface
- Postgres: reads table `corpora` (`SELECT corpus_id FROM corpora ORDER BY corpus_id`) — web_settings.py:229-230; tables written: none (FACTS `tables_written: []`).
- Principal registry file: all writes go through `W.create_key / W.revoke_key / W.add_friend / W.set_friend_enabled / W.reset_friend_password / W.set_friend_corpora / W.rotate_invite` on the path from `W.registry_path()` — web_settings.py:168, 184, 268, 279, 283, 296, 318.
- Env: `POLYMATH_PUBLIC_MCP_URL` = `"https://mcp.kingsleylab.xyz/mcp"` (web_settings.py:70); `POLYMATH_MCP_API_KEY` = null default (web_settings.py:215); `POLYMATH_MCP_PRINCIPALS_FILE` presence checked indirectly (web_settings.py:59).
- Filesystem: references `REPO_ROOT / "scripts" / "connect_agents.sh"` in the returned command string only; no subprocess is executed — web_settings.py:80-81, 86.
- Qdrant: none. Collection names `polymath_deep_research`, `polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare` appear only as prose inside `usage_lines` — web_settings.py:99-101.
- Network: none directly (in-process `polymath_shared.adapter.service.list_adapters`, web_settings.py:234-236).

## invariants
INVARIANT: `KEY_PLACEHOLDER` == `"<YOUR_KEY>"` — web_settings.py:30 [DERIVED]
  fails-if: friend prompt template no longer matches the frontend's substitution target.
INVARIANT: every JSON response header `cache-control` == `"no-store"` — web_settings.py:63-66 [DERIVED]
  fails-if: keys/invite codes land in any cache.
INVARIANT: owner's `my_keys` response == `{is_owner: True, keys: [], max_active: None}` — web_settings.py:154-156 [DERIVED]
  fails-if: owner is shown web-made keys that do not exist.
INVARIANT: friend `max_active` == `W.MAX_ACTIVE_KEYS` in both `my_keys` and `list_friends` — web_settings.py:158, 255 [DERIVED]
  fails-if: UI limit display disagrees with enforcement in `W.create_key`.
INVARIANT: `secrets.token_urlsafe` arg == `12` at both password sites — web_settings.py:266, 282 [DERIVED]
  fails-if: divergent first-password entropy between add-friend and reset-password.
INVARIANT: `_shared_libraries()` excludes every `corpus_id` starting `"fr-"` — web_settings.py:231 [DERIVED]
  fails-if: one friend's private library is offered to another.
INVARIANT: `connector_url(key)` output ends with `"/k/{key}/mcp"` — web_settings.py:76-77 [DERIVED]
  fails-if: Server A `KeyInPath` no longer finds the key in the path.
INVARIANT: tool names in prompts == `polymath_search, polymath_explore, polymath_answer, polymath_compare, polymath_deep_research` — web_settings.py:99-101 [DERIVED]
  fails-if: prompt references a tool name that no longer exists on the MCP server.

## determinism & idempotency
determinism: NONDETERMINISTIC (random `secrets.token_urlsafe` web_settings.py:266, 282; env `POLYMATH_PUBLIC_MCP_URL` web_settings.py:70 and `POLYMATH_MCP_API_KEY` web_settings.py:215; db read of `corpora` web_settings.py:229-231; registry file state via `REGISTRY.get()` web_settings.py:157, 171, 182, 201, 254)
idempotency: UNSAFE — `rotate_invite` yields a new code on every call (web_settings.py:314-318) and `reset-password` yields a new password each call (web_settings.py:282-284); `add_friend` on an existing username returns `409 EXISTS` rather than duplicating (web_settings.py:268-270) [INFERRED from the `EXISTS` code path]; GET endpoints and revocations are repeatable.

## failure behaviour
- Broad `except Exception` → `libraries = []` in `prompt_template` (owner branch) web_settings.py:194-197 and `owner_key_for_copy` web_settings.py:218-221: any DB failure listing libraries is swallowed; the caller still receives a full prompt — the `noqa: BLE001` comments note `list_corpora` names the libraries anyway (web_settings.py:196, 220).
- `W.AccountError` surfaced as HTTP via `_refuse`: `KEY_LIMIT`/`EXISTS` → `409`, other codes → `400` (web_settings.py:168-170, 268-270, 285-286) or `404` (web_settings.py:297-298, 333-334).
- Error codes raised here: `ACCOUNTS_NOT_CONFIGURED` 503 (web_settings.py:59), `OWNER_USES_ENV_KEY` 409 (web_settings.py:166, 181), `NOT_FOUND` 404 (web_settings.py:183), `OWNER_ONLY` 403 (web_settings.py:214, 248), `OWNER_KEY_NOT_SET` 404 (web_settings.py:217), `PRIVATE_LIBRARY` 400 (web_settings.py:264, 294), `UNKNOWN_ACTION` 404 (web_settings.py:287).

## dumb-code flags
- Magic number `12` in `secrets.token_urlsafe(12)`, duplicated — web_settings.py:266, 282.
- Two structurally identical `try: _shared_libraries() except Exception: libraries = []` blocks — web_settings.py:194-197 vs 218-221.
- Duplicated `"fr-"` guard: `add_friend` web_settings.py:262-264 vs `set_libraries` web_settings.py:293-294.
- Duplicated owner belt-and-braces check: `owner_key_for_copy` web_settings.py:213-214 vs `_require_owner` web_settings.py:245-248, same comment "the boundary already refuses; belt and braces".
- `connector_url` string surgery `base[:-len('/mcp')] if base.endswith('/mcp') else base` — a public URL not ending in `/mcp` silently yields `"<base>/k/<key>/mcp"` — web_settings.py:76-77.
- `friend_defaults()` returns fresh lists on each call; no caching, so adapter/library lists can drift between two calls in one flow — web_settings.py:239-242 [INFERRED: two DB/service reads are not transactional].

## refactor notes
- Route paths/methods are the public API: `main.py` mounts this router (FACTS importer); renaming `/keys`, `/admin/friends`, `/friends/invite` breaks the Settings UI and any scripts.
- `friend_defaults()` output feeds both the owner's Add friend and web_auth `/auth/register` (web_settings.py:240-241; web_auth.py is an importer) — changing defaults changes what new friends can see.
- `connector_url` is coupled to Server A `mcp_server.KeyInPath` and the `/k/<key>/mcp` path convention — web_settings.py:74-75, 77.
- `KEY_PLACEHOLDER` is the contract for the friend prompt substitution in the UI — web_settings.py:30, 202.
- The `"fr-"` prefix convention is shared with `W.private_corpus_for(username)` (web_settings.py:172, 202); renaming the prefix requires changing `corpora` row naming and web_accounts together.
- `usage_lines` embeds tool names and mode names (`FAST`, `HYBRID`, `GRAPH`, `WILDCARD`, `GNN`) that must track the MCP server's tool descriptions — web_settings.py:101-107.

## VERIFY
```verify
grep -Fq 'KEY_PLACEHOLDER = "<YOUR_KEY>"' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'secrets.token_urlsafe(12)' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'SELECT corpus_id FROM corpora ORDER BY corpus_id' orchestrator/orchestrator/api/web_settings.py
grep -Eq 'POLYMATH_PUBLIC_MCP_URL.*mcp.kingsleylab.xyz/mcp' orchestrator/orchestrator/api/web_settings.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/web_settings.py
test "$(grep -c -F 'except Exception' orchestrator/orchestrator/api/web_settings.py)" -ge 2
```
