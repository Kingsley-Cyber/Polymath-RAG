# unit: orchestrator/orchestrator/api/web_settings.py
anchor: orchestrator/orchestrator/api/web_settings.py:1-366

## purpose
FastAPI settings router for the Polymath web app: a signed-in friend's own MCP keys and copy-paste connect prompts, and the owner's friend admin (list/add/enable/disable/reset-password/set-libraries/manage friend keys) plus the INVITE-SIGNUP invite code (read/rotate) — web_settings.py:1-7, routes web_settings.py:371-462 [DERIVED].
Identity comes from `request.state.web_identity` set at the web boundary; `/admin/*` and `/friends/invite*` are owner-only there (a direct loopback caller is the owner) — web_settings.py:4-7 [DERIVED].

## public surface
Module imported by `orchestrator/orchestrator/api/web_auth.py` and `orchestrator/orchestrator/main.py` (FACTS.importers); per-symbol consumers are not in FACTS.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | APIRouter | `router = APIRouter()`; 13 routes below | web_settings.py:38 | — |
| KEY_PLACEHOLDER | const | `"<YOUR_KEY>"` | web_settings.py:39 | — |
| ALL_LIBRARIES | const | `"*"` | web_settings.py:42 | — |
| AGENT_REACH_REPO | const | `"https://github.com/Panniantong/Agent-Reach"` | web_settings.py:43 | — |
| AGENT_REACH_VERIFY | const | `"agent-reach doctor --json"` | web_settings.py:44 | — |
| KeyBody | pydantic model | `label: str = Field(default="", max_length=60)` | web_settings.py:47-48 | — |
| FriendBody | pydantic model | `username` 2–32; `display_name` "" max 80; `corpus_ids list[str] \| None = None`; `adapter_ids list[str] \| None = None` | web_settings.py:51-55 | — |
| CorporaBody | pydantic model | `corpus_ids: list[str]` | web_settings.py:58-59 | — |
| mcp_url | def | `() -> str` | web_settings.py:83-84 | — |
| connector_url | def | `(key: str, url: str \| None = None) -> str` | web_settings.py:87-92 | — |
| connect_command | def | `() -> str` | web_settings.py:99-101 | — |
| library_list | def | `(libraries: list[str]) -> str` | web_settings.py:104-109 | — |
| usage_lines | def | `(libraries: list[str], private: str \| None, *, owner: bool) -> str` | web_settings.py:112-132 | — |
| owner_prompt | def | `(libraries: list[str]) -> str` | web_settings.py:135-140 | — |
| connect_prompt | def | `(key: str, libraries: list[str], private: str \| None, url: str \| None = None, *, owner: bool = False) -> str` | web_settings.py:143-171 | — |
| friend_defaults | def | `() -> tuple[list[str], list[str]]` | web_settings.py:268-272 | web_auth.py [INFERRED] (:270 says web_auth `/auth/register` starts from the same two lists) |
| my_keys | route | GET `/keys` `(request) -> JSONResponse` | web_settings.py:179-187 | — |
| create_my_key | route | POST `/keys` `(body: KeyBody, request)` | web_settings.py:190-202 | — |
| revoke_my_key | route | DELETE `/keys/{key_id}` | web_settings.py:205-213 | — |
| prompt_template | route | GET `/keys/prompt` | web_settings.py:216-232 | — |
| owner_key_for_copy | route | GET `/keys/owner` | web_settings.py:235-252 | — |
| list_friends | route | GET `/admin/friends` | web_settings.py:281-285 | — |
| add_friend | route | POST `/admin/friends` `(body: FriendBody, request)` | web_settings.py:288-301 | — |
| friend_action | route | POST `/admin/friends/{username}/{action}` | web_settings.py:304-317 | — |
| set_libraries | route | PUT `/admin/friends/{username}/libraries` | web_settings.py:320-328 | — |
| get_invite | route | GET `/friends/invite` | web_settings.py:336-340 | — |
| rotate_invite | route | POST `/friends/invite/rotate` | web_settings.py:343-349 | — |
| friend_keys | route | GET `/admin/friends/{username}/keys` | web_settings.py:352-355 | — |
| revoke_friend_key | route | DELETE `/admin/friends/{username}/keys/{key_id}` | web_settings.py:358-365 | — |

## contracts
- **mcp_url()** — out: `os.environ.get("POLYMATH_PUBLIC_MCP_URL", "https://mcp.kingsleylab.xyz/mcp")` — web_settings.py:84 [DERIVED].
- **connector_url(key, url=None)** — in: `url` defaults to `mcp_url()` — web_settings.py:91. post: output always ends `/k/{key}/mcp`; a base ending `/mcp` has that suffix stripped first — web_settings.py:92 [DERIVED].
- **connect_command()** — out: `bash <shlex-quoted path>` to `REPO_ROOT/scripts/connect_agents.sh`, `REPO_ROOT = Path(__file__).resolve().parents[3]` — web_settings.py:95-96, web_settings.py:101 [DERIVED].
- **library_list(libraries)** — with `"*"` present: `"every library I share (list_corpora names them)"` plus `", plus <named>"`; empty list → `"(none yet)"` — web_settings.py:106-109 [DERIVED].
- **connect_prompt(...)** — out: prompt containing `Authorization: Bearer {key}`, the connector link, per-harness setup lines (Claude Code, Codex, Gemini CLI, OpenCode, Claude.ai, other), `usage_lines`, and a care line that differs when `owner=True` — web_settings.py:151-171. post: every key, a friend's too, gets the connector link (F7) — web_settings.py:148 [DERIVED].
- **create_my_key** — pre: caller is a friend; owner/None → 409 `OWNER_USES_ENV_KEY` — web_settings.py:192-194. post: 201 with `{"key": raw, ..., "shown_once": True, "connector_url": ..., "prompt": ...}`; raw key returned once — web_settings.py:201-202. errors: `KEY_LIMIT`→409, other `AccountError`→400 — web_settings.py:197-198; no principals file → 503 via `_path()` — web_settings.py:73, web_settings.py:196 [DERIVED].
- **revoke_my_key** — pre: `key_id` in caller's own list else 404 `NOT_FOUND` — web_settings.py:210-211. out: `{"revoked": key_id}` — web_settings.py:213 [DERIVED].
- **prompt_template** — owner: key-free `owner_prompt` + `connect_command`, `"key_included": False` — web_settings.py:221-227. friend: `connect_prompt` with `KEY_PLACEHOLDER` `"<YOUR_KEY>"` — web_settings.py:229-232 [DERIVED].
- **owner_key_for_copy** — pre: owner (belt-and-braces 403 `OWNER_ONLY`) and `POLYMATH_MCP_API_KEY` set else 404 `OWNER_KEY_NOT_SET` — web_settings.py:241-246. out: `key`, `mcp_url`, `connector_url`, `connect_prompt(..., owner=True)` — web_settings.py:251-252 [DERIVED].
- **_shared_libraries / friend_defaults** — out: every `corpus_id` from `corpora` minus `fr-*`; defaults `(["*"], _adapters())` — web_settings.py:258-260, web_settings.py:272 [DERIVED].
- **add_friend** — pre: owner; `corpus_ids=None` → `["*"]` — web_settings.py:291; any `fr-` id → 400 `PRIVATE_LIBRARY` — web_settings.py:292-294. post: 201 with friend record, `first_password` = `secrets.token_urlsafe(12)`, `"shown_once": True` — web_settings.py:296, web_settings.py:301. errors: `EXISTS`→409 else 400 — web_settings.py:299-300 [DERIVED].
- **friend_action** — actions `enable`, `disable`, `reset-password`; anything else → 404 `UNKNOWN_ACTION` — web_settings.py:308-317. reset-password out: new `first_password` (`token_urlsafe(12)`), `"shown_once": True` — web_settings.py:312-314 [DERIVED].
- **set_libraries** — pre: no `fr-` ids else 400 `PRIVATE_LIBRARY` — web_settings.py:323-324. out: friend record; `NOT_FOUND`→404 — web_settings.py:326-328 [DERIVED].
- **get_invite / rotate_invite** — out: `{"code": ..., "rotated_at": ...}`, `code` null until the first rotate — web_settings.py:331-333, web_settings.py:338. rotate writes a new code and returns the fresh payload — web_settings.py:347-349 [DERIVED].
- **revoke_friend_key** — pre: owner. errors: `AccountError`→404 — web_settings.py:362-364 [DERIVED].

## effect surface
- Postgres read: `SELECT corpus_id FROM corpora ORDER BY corpus_id` — web_settings.py:258-259. No table writes in this unit (FACTS `tables_written: []`).
- Principals registry file (env `POLYMATH_MCP_PRINCIPALS_FILE`; unset → 503): written via `W.create_key` :196, `W.revoke_key` :212/:362, `W.add_friend` :298, `W.set_friend_enabled` :309, `W.reset_friend_password` :313, `W.set_friend_corpora` :326, `W.rotate_invite` :347; read `REGISTRY.get()` :185, :269, :284, :339, :355 — web_settings.py:70-74 [DERIVED].
- File path referenced (never opened here): `scripts/connect_agents.sh` — web_settings.py:96.
- Env: `POLYMATH_PUBLIC_MCP_URL` = `'https://mcp.kingsleylab.xyz/mcp'` — web_settings.py:84; `POLYMATH_MCP_API_KEY` (default unset) — web_settings.py:244.
- Random: `secrets.token_urlsafe(12)` — web_settings.py:296, web_settings.py:312.
- Prompt-string literals naming tools/modes: `polymath_deep_research` :121-122; `polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare` :125 (FACTS.collections).
- No network call or subprocess is executed in this unit; `connect_command` only builds a string — web_settings.py:101 [DERIVED].

## invariants
INVARIANT: stored "every library" == `["*"]` (`ALL_LIBRARIES`), resolved per request, not a snapshot — web_settings.py:291, web_settings.py:272, web_settings.py:270-271 [DERIVED]
  fails-if: libraries the owner adds after granting never reach the friend (F3 broken).
INVARIANT: `fr-` corpora excluded at all 3 grant/list paths — web_settings.py:260, web_settings.py:292, web_settings.py:323 [DERIVED]
  fails-if: one friend can be granted another friend's private `fr-*` library.
INVARIANT: raw key exposure count == 1 (create response, `"shown_once": True`, status 201) — web_settings.py:201-202; owner `GET /keys` returns `"keys": []` and never the admin key — web_settings.py:183-184 [DERIVED]
  fails-if: secret disclosed through listing or caching.
INVARIANT: docstring "at most 3 active ones" (:5) must equal `W.MAX_ACTIVE_KEYS`, reported identically at :186 and :284 — web_settings.py:5, web_settings.py:186, web_settings.py:284 [DERIVED]
  fails-if: UI-advertised key limit drifts from the enforced one.
INVARIANT: every JSON response carries `cache-control: no-store` (`_no_store` used at every return) — web_settings.py:77-80 [DERIVED]
  fails-if: invite code (`:338` "Never cached, never logged") or owner key cached by browser/proxy.
INVARIANT: `connector_url` output suffix == `/k/{key}/mcp` when base ends with `/mcp` — web_settings.py:91-92; server side moves the key into the Authorization header (`mcp_server.KeyInPath`) — web_settings.py:88-89 [DERIVED]
  fails-if: claude.ai connector URLs stop authenticating.
INVARIANT: both generated first passwords use `token_urlsafe(12)` — web_settings.py:296, web_settings.py:312 [DERIVED]
  fails-if: add-friend and reset-password produce different password formats/entropy.
INVARIANT: `prompt_template` for a friend returns `KEY_PLACEHOLDER` = `"<YOUR_KEY>"`, never a stored key — web_settings.py:39, web_settings.py:229-232 [DERIVED]
  fails-if: someone else's key disclosed in the template.

## determinism & idempotency
determinism: NONDETERMINISTIC (random `secrets.token_urlsafe` :296, :312; env `POLYMATH_PUBLIC_MCP_URL` :84, `POLYMATH_MCP_API_KEY` :244; db read `corpora` :258-259; registry file `REGISTRY.get()` :185)
idempotency: UNSAFE (POST `/keys` mints a new key per call :196-202; POST `/friends/invite/rotate` replaces the code :347-348; repeated POST `/admin/friends` → 409 `EXISTS` :300; `reset-password` returns a new password each call :312-314; both DELETE routes 404 on repeat :211, :364)

## failure behaviour
- Broad `except Exception` at :224 and :249 (FACTS.fallbacks): `_shared_libraries()` failure is swallowed → `libraries = []`; caller still gets a 200 prompt whose wildcard wording ("list_corpora names them", :108) covers the missing list — web_settings.py:223-225, web_settings.py:248-250 [DERIVED].
- `W.AccountError` → status mapping: `KEY_LIMIT`→409 else 400 (:197-198); `EXISTS`→409 else 400 (:299-300); `NOT_FOUND`→404 (:316, :328, :364) [DERIVED].
- Error codes raised: 503 `ACCOUNTS_NOT_CONFIGURED` (:73), 409 `OWNER_USES_ENV_KEY` (:194, :209), 404 `NOT_FOUND` (:211), 403 `OWNER_ONLY` (:243, :278), 404 `OWNER_KEY_NOT_SET` (:246), 400 `PRIVATE_LIBRARY` (:294, :324), 404 `UNKNOWN_ACTION` (:317) [DERIVED].

## dumb-code flags
- Magic numbers: `token_urlsafe(12)` twice (:296, :312); Field limits `60` (:48), `2`/`32` (:52), `80` (:53) [DERIVED].
- Duplicated literal `"fr-"` in 3 separate checks (:260, :292, :323) — a prefix rename needs 3 edits [DERIVED].
- Duplicated `AccountError`→status mapping pattern (:197-198 vs :299-300) [DERIVED].
- Duplicated belt-and-braces owner check with identical comment (:242 vs :276-278) [DERIVED].
- `ALL_LIBRARIES = "*"` duplicates `polymath_shared.query_scope.ALL_LIBRARIES`; equality held only by an external test — web_settings.py:40-41 [DERIVED].
- Hardcoded deployment fallback `https://mcp.kingsleylab.xyz/mcp` — web_settings.py:84 [DERIVED].
- `"shown_once": True` repeated at :201, :301, :314 [DERIVED].
- No dead branches visible.

## refactor notes
- `ALL_LIBRARIES` must stay byte-equal to `polymath_shared.query_scope.ALL_LIBRARIES` (web_settings.py:40-41); web_scope/web_accounts resolve the wildcard, so a change breaks per-request library resolution.
- `/k/<key>/mcp` URL shape must match `mcp_server.KeyInPath` (web_settings.py:88-89); changing it breaks claude.ai connector links built at :92 and returned at :201, :231, :251.
- `usage_lines` mirrors the MCP servers' playbook (`polymath_shared.mcp_retrieval.playbook`) — web_settings.py:20-21, web_settings.py:113-114; edit both together or agents receive conflicting rules.
- Route paths are the Settings web UI contract (FACTS.routes); module has two importers (`web_auth.py`, `main.py`), so renames hit more than this file.
- `connect_command` output depends on `scripts/connect_agents.sh` under `REPO_ROOT` — web_settings.py:95-96; moving the script silently breaks the owner's ONE-PROFILE flow (:100-101, :226).
- `friend_defaults` feeds both `add_friend` and web_auth's `/auth/register` defaults — web_settings.py:269-271; changing it moves both.

## VERIFY
```verify
grep -Fq 'ALL_LIBRARIES = "*"' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'https://mcp.kingsleylab.xyz/mcp' orchestrator/orchestrator/api/web_settings.py
grep -Fq '/k/{key}/mcp' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'OWNER_USES_ENV_KEY' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'secrets.token_urlsafe(12)' orchestrator/orchestrator/api/web_settings.py
test "$(grep -c -F 'fr-' orchestrator/orchestrator/api/web_settings.py)" -ge 3
! grep -Fq 'print(' orchestrator/orchestrator/api/web_settings.py
```
