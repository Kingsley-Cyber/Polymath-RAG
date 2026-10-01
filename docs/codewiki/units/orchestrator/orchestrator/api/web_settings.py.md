# unit: orchestrator/orchestrator/api/web_settings.py
anchor: orchestrator/orchestrator/api/web_settings.py:1-333

## purpose
FastAPI router for the Settings page: principal API keys (list/create/revoke; raw key returned once), the copy-paste MCP connect prompt, the owner's one-command connect (ONE-PROFILE), owner-only friend admin, and the INVITE-SIGNUP code (read/rotate). Caller identity was already decided at the web boundary (`request.state.web_identity`); a DIRECT loopback caller is the owner; `/admin/*` and `/friends/invite*` are owner-only at the boundary. [DERIVED — orchestrator/orchestrator/api/web_settings.py:1-12]

## public surface

Module importers (FACTS.importers): `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/main.py`.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | 13 routes below | web_settings.py:29 | main.py mounts it [INFERRED: only non-API importer] |
| `mcp_url` | def | () -> str | web_settings.py:69-70 | — |
| `connector_url` | def | (key: str) -> str | web_settings.py:73-77 | — |
| `connect_command` | def | () -> str | web_settings.py:84-86 | — |
| `usage_lines` | def | (libraries: list[str], private: str \| None, *, owner: bool) -> str | web_settings.py:89-105 | — |
| `owner_prompt` | def | (libraries: list[str]) -> str | web_settings.py:108-113 | — |
| `connect_prompt` | def | (key: str, libraries: list[str], private: str \| None, url: str \| None = None, *, owner: bool = False) -> str | web_settings.py:116-141 | — |
| `friend_defaults` | def | () -> tuple[list[str], list[str]] | web_settings.py:237-240 | web_auth.py [INFERRED: docstring says /auth/register starts from the same two lists, web_settings.py:238-239] |
| `KEY_PLACEHOLDER` | constant | `"<YOUR_KEY>"` | web_settings.py:30 | — |
| `KeyBody` / `FriendBody` / `CorporaBody` | pydantic models | request bodies | web_settings.py:33-34, 37-41, 44-45 | routes below |

Routes:

| method | path | handler | anchor |
|---|---|---|---|
| GET | `/keys` | my_keys | web_settings.py:150 |
| POST | `/keys` | create_my_key | web_settings.py:161 |
| DELETE | `/keys/{key_id}` | revoke_my_key | web_settings.py:176 |
| GET | `/keys/prompt` | prompt_template | web_settings.py:187 |
| GET | `/keys/owner` | owner_key_for_copy | web_settings.py:205 |
| GET | `/admin/friends` | list_friends | web_settings.py:250 |
| POST | `/admin/friends` | add_friend | web_settings.py:257 |
| POST | `/admin/friends/{username}/{action}` | friend_action | web_settings.py:273 |
| PUT | `/admin/friends/{username}/libraries` | set_libraries | web_settings.py:289 |
| GET | `/friends/invite` | get_invite | web_settings.py:305 |
| POST | `/friends/invite/rotate` | rotate_invite | web_settings.py:312 |
| GET | `/admin/friends/{username}/keys` | friend_keys | web_settings.py:321 |
| DELETE | `/admin/friends/{username}/keys/{key_id}` | revoke_friend_key | web_settings.py:327 |

## contracts

- `mcp_url` — out: `os.environ.get("POLYMATH_PUBLIC_MCP_URL", "https://mcp.kingsleylab.xyz/mcp")`. web_settings.py:69-70
- `connector_url(key)` — out: `mcp_url().rstrip("/")`, one trailing `/mcp` removed if present, then `/k/{key}/mcp` appended; with the default URL → `https://mcp.kingsleylab.xyz/k/<key>/mcp`. Counterpart: MCP Server A `mcp_server.KeyInPath` moves the key into the Authorization header. web_settings.py:73-77
- `connect_command()` — out: `bash ` + shlex.quote of `REPO_ROOT/scripts/connect_agents.sh` (`REPO_ROOT = Path(__file__).resolve().parents[3]`); carries no secret. web_settings.py:80-86
- `GET /keys` — owner or no identity → `{"is_owner": True, "keys": [], "max_active": None, "note": ...}`; friend → `W.list_keys(...)`, `max_active: W.MAX_ACTIVE_KEYS`. web_settings.py:150-157
- `POST /keys` — in: `label` (default `""`, max_length 60). pre: friend identity (owner/None → 409 `OWNER_USES_ENV_KEY`); registry path set (else 503 `ACCOUNTS_NOT_CONFIGURED`). out 201: `{"key": raw, ..., "shown_once": True, "prompt": connect_prompt(raw, sorted(corpus_ids), private)}`. `W.AccountError` → 409 iff code == `"KEY_LIMIT"` else 400. post: raw key never shown again. web_settings.py:161-172, 56-60
- `DELETE /keys/{key_id}` — owner → 409 `OWNER_USES_ENV_KEY`; key_id not among own keys → 404 `NOT_FOUND`; else `{"revoked": key_id}`. web_settings.py:176-183
- `GET /keys/prompt` — owner/None → `owner_prompt(libraries)` + `connect_command`, `"key_included": False`; friend → `connect_prompt(KEY_PLACEHOLDER, sorted(corpus_ids), private)`, `"placeholder": "<YOUR_KEY>"`. web_settings.py:187-201
- `GET /keys/owner` — pre: owner (403 `OWNER_ONLY` belt-and-braces); `POLYMATH_MCP_API_KEY` empty → 404 `OWNER_KEY_NOT_SET`. out: `key`, `mcp_url`, `connector_url`, `connect_prompt(..., owner=True)`, no-store. web_settings.py:205-221
- `POST /admin/friends` — in: FriendBody (username 2–32 chars; `corpus_ids`/`adapter_ids` `None` = every shared library / every adapter). any `"fr-"` corpus → 400 `PRIVATE_LIBRARY`. out 201: friend record + `first_password` = `secrets.token_urlsafe(12)`, `"shown_once": True`. AccountError → 409 iff `"EXISTS"` else 400. web_settings.py:256-269
- `POST /admin/friends/{username}/{action}` — action ∈ `enable`, `disable`, `reset-password`; else 404 `UNKNOWN_ACTION`; reset-password returns fresh `secrets.token_urlsafe(12)`; AccountError → 404 iff `"NOT_FOUND"` else 400. web_settings.py:272-285
- `PUT /admin/friends/{username}/libraries` — any `"fr-"` corpus → 400 `PRIVATE_LIBRARY`; any AccountError → 404 with exc.code. web_settings.py:288-296
- `GET /friends/invite` / `POST /friends/invite/rotate` — out: `{"code": rec.get("code") or None, "rotated_at": ...}`; code is null until the first rotate; rotate issues a replacement (friends not yet signed up need the new one). web_settings.py:299-317
- `GET/DELETE /admin/friends/{username}/keys[/{key_id}]` — owner-only; list via `W.principal_id_for(username)`; revoke AccountError → 404. web_settings.py:320-333
- `_shared_libraries()` — `SELECT corpus_id FROM corpora ORDER BY corpus_id` inside `tx()`, minus every id starting `"fr-"`. `friend_defaults()` = `(_shared_libraries(), _adapters())`; `_adapters()` = sorted `adapter_id` from `polymath_shared.adapter.service.list_adapters()`. web_settings.py:225-240

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | table `corpora`, column `corpus_id` | web_settings.py:227-228 |
| Postgres write | none (FACTS.tables_written = []) | — |
| Registry file | principals JSON via `W.registry_path()`; unset → 503 naming `POLYMATH_MCP_PRINCIPALS_FILE`; mutated only through W.* helpers (create_key, revoke_key, add_friend, set_friend_enabled, reset_friend_password, set_friend_corpora, rotate_invite) | web_settings.py:56-60, 166, 182, 265, 276-281, 294, 316 |
| env | `POLYMATH_PUBLIC_MCP_URL` = `'https://mcp.kingsleylab.xyz/mcp'`; `POLYMATH_MCP_API_KEY` = null | web_settings.py:70, 213 |
| files | path built for `scripts/connect_agents.sh`; never executed here — string only | web_settings.py:80-86 |
| randomness | `secrets.token_urlsafe(12)` ×2 | web_settings.py:264, 280 |
| collections | `polymath_search`, `polymath_explore`, `polymath_answer` appear only as tool names in prompt copy; no vector-store access in this unit | web_settings.py:101 |
| network | none initiated; URLs returned as strings | web_settings.py:70, 77 |
| cache header | every response `cache-control: no-store` via `_no_store` | web_settings.py:63-66 |

## invariants

INVARIANT: raw key/password exposure == the create/reset response only — `"shown_once": True` at web_settings.py:171, 268, 281; docstring "returned ONCE ... never again" web_settings.py:5-6 [DERIVED]
  fails-if: a raw secret surfaces in any GET → unrecoverable from this UI (owner must change `.env`).
INVARIANT: every corpus_id starting `"fr-"` is excluded from sharing — filter web_settings.py:229, add-time check web_settings.py:260, update-time check web_settings.py:291 [DERIVED]
  fails-if: one friend is granted another friend's private library.
INVARIANT: owner + POST /keys == 409 `OWNER_USES_ENV_KEY` — web_settings.py:163-164, 178-179 [DERIVED]
  fails-if: a registry-grown owner key competes with the `.env` admin key (web_settings.py:5-7).
INVARIANT: active-key limit surfaced as `W.MAX_ACTIVE_KEYS` (web_settings.py:156, 252) == the "at most 3 active ones" the docstring states (web_settings.py:5); the literal `3` lives only in prose [DERIVED]
  fails-if: docstring/UI copy drifts if `W.MAX_ACTIVE_KEYS` changes.
INVARIANT: every route response carries `cache-control: no-store` — web_settings.py:63-66 used by all handler returns [DERIVED]
  fails-if: invite code (web_settings.py:305-308) or owner key (web_settings.py:220) cached by an intermediary.
INVARIANT: `connector_url(x)` == mcp_url minus one trailing `/mcp`, plus `/k/{x}/mcp` — web_settings.py:76-77 [DERIVED]
  fails-if: MCP Server A `KeyInPath` (web_settings.py:74-75) can no longer extract the key.
INVARIANT: prompt corpus lists are `sorted(...)` — web_settings.py:171, 200 [DERIVED]
  fails-if: prompt text flaps between calls (cosmetic).

## determinism & idempotency

determinism: NONDETERMINISTIC (random `secrets.token_urlsafe(12)` web_settings.py:264, 280; env `POLYMATH_PUBLIC_MCP_URL` web_settings.py:70 and `POLYMATH_MCP_API_KEY` web_settings.py:213; db read of `corpora` web_settings.py:227-228)
idempotency: UNSAFE (POST /keys mints a new key per call; repeated POST /admin/friends → 409 `EXISTS` web_settings.py:267-268; rotate_invite replaces the code every call web_settings.py:316; DELETEs converge but repeats get 404 — web_settings.py:180-181, 331-332; enable/disable converge via `W.set_friend_enabled` web_settings.py:276-278)

## failure behaviour

- `except Exception` ×2 (web_settings.py:194, 218): `_shared_libraries()` failure swallowed → `libraries = []`; caller still gets a prompt, so "no libraries" and "DB down" become indistinguishable [swallow DERIVED; indistinguishability INFERRED].
- `W.AccountError` status mapping differs by handler: 409 iff `KEY_LIMIT`/`EXISTS` else 400 at web_settings.py:167-168, 267-268, 283-284; flat 404 with exc.code at web_settings.py:295-296, 331-332.
- Error shape: `HTTPException(status_code, detail={"error_code": code, "message": message})`. web_settings.py:48-49
- Codes raised: 503 `ACCOUNTS_NOT_CONFIGURED` (59); 409 `OWNER_USES_ENV_KEY` (164, 179); 403 `OWNER_ONLY` (212, 246); 404 `OWNER_KEY_NOT_SET` (215); 404 `NOT_FOUND` (181); 400 `PRIVATE_LIBRARY` (262, 292); 404 `UNKNOWN_ACTION` (285). web_settings.py:59-285

## dumb-code flags

- Literal `"fr-"` repeated in three places, no shared constant — web_settings.py:229, 260, 291.
- Docstring "at most 3 active ones" vs code constant `W.MAX_ACTIVE_KEYS` — web_settings.py:5 vs 156, 252.
- Duplicated swallow blocks (`except Exception` → `libraries = []`, identical comment) — web_settings.py:192-195, 216-219.
- Owner belt-and-braces check duplicated: inline in owner_key_for_copy vs `_require_owner` — web_settings.py:210-212 vs 243-246.
- Magic sizes: `max_length=60` (34), `min_length=2` / `max_length=32` (38), `max_length=80` (39), `token_urlsafe(12)` (264, 280).
- `connector_url` strips only one trailing `/mcp` — web_settings.py:76.
- `prompt_template`: `text` bound only in the `else` branch, returned at web_settings.py:201 after the owner path returned at 196 — a third identity class would raise NameError [INFERRED].

## refactor notes

- Route paths, error codes, and response keys (`shown_once`, `first_password`, `placeholder`, `connector_url`, `key_included`) are the Settings frontend contract — web_settings.py:148-333.
- `KEY_PLACEHOLDER` value `"<YOUR_KEY>"` is handed to clients (web_settings.py:200-201, 30); changing it breaks clients that substitute the placeholder [INFERRED].
- `/k/{key}/mcp` must stay in lockstep with MCP Server A `mcp_server.KeyInPath` — web_settings.py:74-75, 77.
- Prompt copy (usage_lines/owner_prompt/connect_prompt) gets pasted into agent harness configs; edits propagate to every friend's setup instructions — web_settings.py:99-141.
- W.* surface used (web_accounts): `registry_path`, `WebIdentity`, `list_keys`, `create_key`, `revoke_key`, `AccountError`, `MAX_ACTIVE_KEYS`, `private_corpus_for`, `list_friends`, `add_friend`, `set_friend_enabled`, `reset_friend_password`, `normalize_username`, `set_friend_corpora`, `invite_record`, `rotate_invite`, `read_registry`, `principal_id_for` — web_settings.py:52-57, 155-156, 166-167, 182, 252, 265-267, 276-281, 294-295, 300, 316-317, 322-323, 329-331; signature changes there ripple through this file.
- Importers `web_auth.py` and `main.py` (FACTS.importers) must be updated if `friend_defaults` or `router` move — web_settings.py:29, 237-240.

## VERIFY

```verify
grep -Fq 'KEY_PLACEHOLDER = "<YOUR_KEY>"' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'https://mcp.kingsleylab.xyz/mcp' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'cache-control' orchestrator/orchestrator/api/web_settings.py
grep -Eq 'secrets\.token_urlsafe\(12\)' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'OWNER_USES_ENV_KEY' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'startswith("fr-")' orchestrator/orchestrator/api/web_settings.py
grep -Fq '/k/{key}/mcp' orchestrator/orchestrator/api/web_settings.py
! grep -Fq 'print(' orchestrator/orchestrator/api/web_settings.py
```
