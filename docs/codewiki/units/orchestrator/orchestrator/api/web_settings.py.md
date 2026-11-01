# unit: orchestrator/orchestrator/api/web_settings.py
anchor: orchestrator/orchestrator/api/web_settings.py:1-361

## purpose
FastAPI Settings router: a friend's principal API keys (list / create / revoke), the copy-paste connect prompts (owner's ONE-PROFILE key-free command, friend's key-bearing prompt, owner's main-key reveal), and the owner's friend admin + invite code. Identity is decided at the web boundary via `request.state.web_identity`; a DIRECT loopback caller is the owner (web_settings.py:1-7, 585-591). [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | module-level, 13 routes (table below) | web_settings.py:35 | orchestrator/orchestrator/main.py, orchestrator/orchestrator/api/web_auth.py (FACTS.importers) |
| `KeyBody` | class | `label: str = Field(default="", max_length=60)` | web_settings.py:44-45 | — |
| `FriendBody` | class | `username` (2–32), `display_name` (max 80), `corpus_ids: list[str] | None`, `adapter_ids: list[str] | None` | web_settings.py:48-52 | — |
| `CorporaBody` | class | `corpus_ids: list[str]` | web_settings.py:55-56 | — |
| `mcp_url` | def | `() -> str` | web_settings.py:80-81 | — |
| `connector_url` | def | `(key: str, url: str | None = None) -> str` | web_settings.py:84-89 | — |
| `connect_command` | def | `() -> str` | web_settings.py:96-98 | — |
| `library_list` | def | `(libraries: list[str]) -> str` | web_settings.py:101-106 | — |
| `usage_lines` | def | `(libraries: list[str], private: str | None, *, owner: bool) -> str` | web_settings.py:109-128 | — |
| `owner_prompt` | def | `(libraries: list[str]) -> str` | web_settings.py:131-136 | — |
| `connect_prompt` | def | `(key: str, libraries: list[str], private: str | None, url: str | None = None, *, owner: bool = False) -> str` | web_settings.py:139-167 | — |
| `friend_defaults` | def | `() -> tuple[list[str], list[str]]` | web_settings.py:264-268 | web_auth `/auth/register` per docstring (web_settings.py:265-266) [INFERRED] |

Routes (all handlers return `_no_store`, web_settings.py:74-77):

| method | path | handler | anchor |
|---|---|---|---|
| GET | `/keys` | `my_keys` | web_settings.py:176 |
| POST | `/keys` | `create_my_key` | web_settings.py:187 |
| DELETE | `/keys/{key_id}` | `revoke_my_key` | web_settings.py:202 |
| GET | `/keys/prompt` | `prompt_template` | web_settings.py:213 |
| GET | `/keys/owner` | `owner_key_for_copy` | web_settings.py:232 |
| GET | `/admin/friends` | `list_friends` | web_settings.py:278 |
| POST | `/admin/friends` | `add_friend` | web_settings.py:285 |
| POST | `/admin/friends/{username}/{action}` | `friend_action` | web_settings.py:301 |
| PUT | `/admin/friends/{username}/libraries` | `set_libraries` | web_settings.py:317 |
| GET | `/friends/invite` | `get_invite` | web_settings.py:333 |
| POST | `/friends/invite/rotate` | `rotate_invite` | web_settings.py:340 |
| GET | `/admin/friends/{username}/keys` | `friend_keys` | web_settings.py:349 |
| DELETE | `/admin/friends/{username}/keys/{key_id}` | `revoke_friend_key` | web_settings.py:355 |

## contracts

`connector_url(key, url=None)` — web_settings.py:84-89
- in: raw key string; optional base URL, default `mcp_url()`.
- out: base with trailing `/mcp` stripped, then `/k/{key}/mcp` appended; key rides in the path because claude.ai cannot send a header (`mcp_server.KeyInPath` moves it to Authorization).
- post: result always ends with `/k/<key>/mcp` (web_settings.py:89).

`create_my_key(body, request)` — web_settings.py:187-198
- pre: caller is a friend (`ident` not None and not `is_owner`); owner/anonymous → 409 `OWNER_USES_ENV_KEY` (web_settings.py:189-190).
- in: `label` max 60 chars (web_settings.py:45).
- out: 201 JSON with `"key": raw`, `"shown_once": True`, `connector_url(raw)`, and `connect_prompt(raw, ...)` prefilled (web_settings.py:197-198).
- post: raw key returned exactly once, never again (web_settings.py:5-6).

`owner_key_for_copy(request)` — web_settings.py:232-248
- pre: owner only (boundary enforces; belt-and-braces 403 `OWNER_ONLY` at web_settings.py:238-239); `POLYMATH_MCP_API_KEY` non-empty else 404 `OWNER_KEY_NOT_SET` (web_settings.py:241-242).
- out: `key`, `mcp_url()`, `connector_url(key)`, `connect_prompt(..., owner=True)` (web_settings.py:247-248).

`add_friend(body, request)` — web_settings.py:285-297
- pre: owner (web_settings.py:286); no `corpus_ids` entry starting `fr-` else 400 `PRIVATE_LIBRARY` (web_settings.py:288-290).
- in: `corpus_ids=None` → stored as `["*"]` (ALL_LIBRARIES) (web_settings.py:287); `adapter_ids=None` → all adapters (web_settings.py:291).
- out: 201 with friend record and `first_password` = `secrets.token_urlsafe(12)`, `"shown_once": True` (web_settings.py:292, 297).

`_shared_libraries()` — web_settings.py:252-256
- out: `SELECT corpus_id FROM corpora ORDER BY corpus_id`, minus any `fr-*` id; i.e. every library a friend may be given.

`get_invite` / `rotate_invite` — web_settings.py:333-345
- pre: owner only (web_settings.py:335, 342).
- out: `{"code": ..., "rotated_at": ...}`; `code` is null until the first rotate (web_settings.py:328-329, 334).

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | table `corpora`, column `corpus_id` | web_settings.py:254-255 |
| Postgres write | none in this file (FACTS.tables_written empty) | — |
| registry file | reads/writes go through `W.*` (`web_accounts`) against `POLYMATH_MCP_PRINCIPALS_FILE` via `_path()`; unset → 503 | web_settings.py:67-71 |
| file path built (not executed) | `REPO_ROOT/scripts/connect_agents.sh`, `REPO_ROOT = Path(__file__).resolve().parents[3]` | web_settings.py:92-93 |
| env | `POLYMATH_PUBLIC_MCP_URL` = `'https://mcp.kingsleylab.xyz/mcp'` | web_settings.py:81 |
| env | `POLYMATH_MCP_API_KEY` = unset/null | web_settings.py:240 |
| network | none made here; URLs only appear inside prompt strings | web_settings.py:150-162 |
| collection names | `polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare`, `polymath_deep_research` occur only as literals in prompt text, not as calls | web_settings.py:118-122 |

## invariants

INVARIANT: `ALL_LIBRARIES` literal `"*"` == `polymath_shared.query_scope.ALL_LIBRARIES` — web_settings.py:37-39 [DERIVED]
  fails-if: scope resolution in web_scope/web_accounts stops treating stored `["*"]` as every library; later-added libraries no longer reach friends (F3).
INVARIANT: raw-key exposure count per created key == 1 (`"shown_once": True` on create-key, add-friend first_password, reset-password; owner key is the env key, never a web-made one) — web_settings.py:197, 297, 310, 5-6 [DERIVED]
  fails-if: a raw key shown twice breaks the returned-once guarantee the Settings UI relies on.
INVARIANT: every route response header `cache-control` == `no-store` (all 13 handlers return `_no_store`) — web_settings.py:74-77 [DERIVED]
  fails-if: key-bearing JSON (create-key, `/keys/owner`) becomes cacheable.
INVARIANT: owner web-made key count == 0 (`my_keys` owner branch returns `"keys": []`; create refuses 409) — web_settings.py:178-180, 189-190 [DERIVED]
  fails-if: owner keys split between `.env` and the registry; the OWNER-KEY-VISIBLE copy flow breaks.
INVARIANT: libraries offered to friends ∩ ids starting `fr-` == ∅ — web_settings.py:256, 288-290, 319-320 [DERIVED]
  fails-if: one friend's private library leaks to another.
INVARIANT: connector URL suffix == `"/k/<key>/mcp"` — web_settings.py:89 [DERIVED]
  fails-if: `mcp_server.KeyInPath` no longer finds the key in the path; claude.ai connectors stop authenticating.
INVARIANT: friend active keys ≤ `W.MAX_ACTIVE_KEYS` (value defined in web_accounts, surfaced as `"max_active"`) — web_settings.py:182, 281, 192-194 [INFERRED: create raises `KEY_LIMIT` via `W.create_key`]

## determinism & idempotency
determinism: NONDETERMINISTIC (random `secrets.token_urlsafe` web_settings.py:292, 308; env `POLYMATH_PUBLIC_MCP_URL` web_settings.py:81, `POLYMATH_MCP_API_KEY` web_settings.py:240; db read of `corpora` web_settings.py:254-255)
idempotency: UNSAFE — `add_friend` creates a record and returns a one-time `first_password` (repeat → 409 `EXISTS`, web_settings.py:296); `rotate_invite` produces a new code each call (web_settings.py:340-345); `reset-password` issues a fresh password (web_settings.py:307-310). Reads and enable/disable are stateless/set-once.

## failure behaviour
- Two broad `except Exception` handlers (web_settings.py:220, 245): a `_shared_libraries()` failure is swallowed and `libraries = []`; the caller still gets a full prompt, just without the library list (`list_corpora` names them instead) — web_settings.py:218-221, 243-246.
- `W.AccountError` mapping: `KEY_LIMIT` / `EXISTS` → 409, other codes → 400 (web_settings.py:194, 296); `NOT_FOUND` → 404 (web_settings.py:312, 324, 360).
- Error codes raised here: `ACCOUNTS_NOT_CONFIGURED` 503 (web_settings.py:70), `OWNER_USES_ENV_KEY` 409 (web_settings.py:190, 205), `NOT_FOUND` 404 (web_settings.py:207), `OWNER_ONLY` 403 (web_settings.py:239, 274), `OWNER_KEY_NOT_SET` 404 (web_settings.py:242), `PRIVATE_LIBRARY` 400 (web_settings.py:290, 320), `UNKNOWN_ACTION` 404 (web_settings.py:313).

## dumb-code flags
- Magic number `12` in `secrets.token_urlsafe(12)` duplicated at web_settings.py:292 and 308.
- `"fr-"` prefix literal repeated three times: web_settings.py:256, 288, 319.
- Redundant owner checks — comments admit "the boundary already refuses; belt and braces" at web_settings.py:238-239 and 272-274.
- `REGISTRY.get() or {}` re-derived in seven handlers (web_settings.py:181, 195, 206, 225, 280-281, 336, 351).
- Repo depth hardcoded as `parents[3]` for `CONNECT_SCRIPT` (web_settings.py:92-93); moving the file breaks the path silently.
- `prompt_template` uses an `if/else` that assigns `text` in the `else` then shares one return — a fall-through branch readers can misread (web_settings.py:217-228).
- FACTS lists five "collections" that are only prompt-string literals, not data sinks — do not treat them as Qdrant usage (web_settings.py:118-122).

## refactor notes
- `ALL_LIBRARIES = "*"` is pinned equal to `polymath_shared.query_scope.ALL_LIBRARIES` by a test; changing either requires both plus the test (web_settings.py:37-39).
- `connector_url`'s `/k/<key>/mcp` shape is coupled to `mcp_server.KeyInPath`; rename the path segment in both or auth breaks (web_settings.py:85-89).
- `usage_lines` duplicates the MCP servers' playbook rules (`polymath_shared.mcp_retrieval.playbook`) as prose — text edits must stay in sync on both sides (web_settings.py:110-111, 14-16 of the docstring).
- `connect_prompt` setup commands follow `mcp_server/CONNECTORS.md` and are documented as safe-to-rerun (old entry replaced) — keep that property when editing (web_settings.py:141-142, 155-158).
- Router is imported by `orchestrator/main.py` and `api/web_auth.py` (FACTS.importers); `friend_defaults` is the shared default for Add-friend and `/auth/register` (web_settings.py:265-266).
- `_shared_libraries` reads the live `corpora` table; the wildcard `["*"]` default means friend permissions are resolved per request, never snapshotted (web_settings.py:264-268, 17-18 of the docstring).

## VERIFY
```verify
grep -Fq 'ALL_LIBRARIES = "*"' orchestrator/orchestrator/api/web_settings.py
grep -Fq '/k/{key}/mcp' orchestrator/orchestrator/api/web_settings.py
grep -Eq 'token_urlsafe\(12\)' orchestrator/orchestrator/api/web_settings.py
test "$(grep -c -F 'OWNER_USES_ENV_KEY' orchestrator/orchestrator/api/web_settings.py)" -ge 2
grep -Fq 'cache-control' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'SELECT corpus_id FROM corpora ORDER BY corpus_id' orchestrator/orchestrator/api/web_settings.py
! grep -Fq 'shown_once": False' orchestrator/orchestrator/api/web_settings.py
```
