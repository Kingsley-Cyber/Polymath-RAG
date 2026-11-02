# unit: orchestrator/orchestrator/api/web_settings.py
anchor: orchestrator/orchestrator/api/web_settings.py:1-366

## purpose
FastAPI settings routes for the Polymath web UI: a friend's own API keys and copy-paste MCP connect prompts, the owner's friend admin (`/admin/friends*`), and the INVITE-SIGNUP invite code — orchestrator/orchestrator/api/web_settings.py:1-7 [DERIVED].
Identity is decided at the web boundary (`request.state.web_identity`); a DIRECT loopback caller is the owner; keys are principal keys in the registry that MCP Server A reads — orchestrator/orchestrator/api/web_settings.py:4-6 [DERIVED].
ONE-PROFILE: the owner gets one connect command (`scripts/connect_agents.sh`) and a key-free prompt, never web-made keys — orchestrator/orchestrator/api/web_settings.py:9-12 [DERIVED].

## public surface
Module imported by orchestrator/orchestrator/api/web_auth.py and orchestrator/orchestrator/main.py (FACTS.importers) [DERIVED].

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | APIRouter | 13 routes below | orchestrator/orchestrator/api/web_settings.py:38 | — |
| KeyBody | pydantic model | label: str = "" (max 60) | orchestrator/orchestrator/api/web_settings.py:47-48 | — |
| FriendBody | pydantic model | username (2..32), display_name (max 80), corpus_ids / adapter_ids: list[str] \| None | orchestrator/orchestrator/api/web_settings.py:51-55 | — |
| CorporaBody | pydantic model | corpus_ids: list[str] | orchestrator/orchestrator/api/web_settings.py:58-59 | — |
| mcp_url | def | () -> str | orchestrator/orchestrator/api/web_settings.py:83-84 | — |
| connector_url | def | (key: str, url: str \| None = None) -> str | orchestrator/orchestrator/api/web_settings.py:87-92 | — |
| connect_command | def | () -> str | orchestrator/orchestrator/api/web_settings.py:99-101 | — |
| library_list | def | (libraries: list[str]) -> str | orchestrator/orchestrator/api/web_settings.py:104-109 | — |
| usage_lines | def | (libraries: list[str], private: str \| None, *, owner: bool) -> str | orchestrator/orchestrator/api/web_settings.py:112-132 | — |
| owner_prompt | def | (libraries: list[str]) -> str | orchestrator/orchestrator/api/web_settings.py:135-140 | — |
| connect_prompt | def | (key, libraries, private, url=None, *, owner=False) -> str | orchestrator/orchestrator/api/web_settings.py:143-171 | — |
| friend_defaults | def | () -> tuple[list[str], list[str]] | orchestrator/orchestrator/api/web_settings.py:268-272 | web_auth /auth/register (same two lists per docstring) [INFERRED — docstring says both start from these lists] |

Routes (every handler returns `_no_store`):

| method | path | handler | anchor |
|---|---|---|---|
| GET | /keys | my_keys | orchestrator/orchestrator/api/web_settings.py:180 |
| POST | /keys | create_my_key | orchestrator/orchestrator/api/web_settings.py:191 |
| DELETE | /keys/{key_id} | revoke_my_key | orchestrator/orchestrator/api/web_settings.py:206 |
| GET | /keys/prompt | prompt_template | orchestrator/orchestrator/api/web_settings.py:217 |
| GET | /keys/owner | owner_key_for_copy | orchestrator/orchestrator/api/web_settings.py:236 |
| GET | /admin/friends | list_friends | orchestrator/orchestrator/api/web_settings.py:282 |
| POST | /admin/friends | add_friend | orchestrator/orchestrator/api/web_settings.py:289 |
| POST | /admin/friends/{username}/{action} | friend_action | orchestrator/orchestrator/api/web_settings.py:305 |
| PUT | /admin/friends/{username}/libraries | set_libraries | orchestrator/orchestrator/api/web_settings.py:321 |
| GET | /friends/invite | get_invite | orchestrator/orchestrator/api/web_settings.py:337 |
| POST | /friends/invite/rotate | rotate_invite | orchestrator/orchestrator/api/web_settings.py:344 |
| GET | /admin/friends/{username}/keys | friend_keys | orchestrator/orchestrator/api/web_settings.py:353 |
| DELETE | /admin/friends/{username}/keys/{key_id} | revoke_friend_key | orchestrator/orchestrator/api/web_settings.py:359 |

## contracts
**mcp_url()** — out: `os.environ.get("POLYMATH_PUBLIC_MCP_URL", "https://mcp.kingsleylab.xyz/mcp")` — orchestrator/orchestrator/api/web_settings.py:83-84 [DERIVED]

**connector_url(key, url=None)** — in: key; url defaults to mcp_url(). out: base with trailing "/" stripped, suffix `/mcp` replaced by `/k/{key}/mcp`. post: claude.ai cannot send a header, so the key rides in the path; `mcp_server.KeyInPath` moves it to Authorization — orchestrator/orchestrator/api/web_settings.py:88-92 [DERIVED]

**connect_command()** — out: `bash <shlex.quoted CONNECT_SCRIPT>`; CONNECT_SCRIPT = REPO_ROOT/scripts/connect_agents.sh, REPO_ROOT = `Path(__file__).resolve().parents[3]` — orchestrator/orchestrator/api/web_settings.py:95-101 [DERIVED]

**library_list(libraries)** — wildcard `*` → `"every library I share (list_corpora names them)"` (+ `", plus <named>"` if mixed); no wildcard → `", ".join(named)` or `"(none yet)"` — orchestrator/orchestrator/api/web_settings.py:104-109 [DERIVED]

**usage_lines(libraries, private, *, owner)** — out: 9-step "How to use it" block; owner variant says "my CJ account", friend says "Polymath's CJ account" and appends " Polymath's web reader is not shared, so research always runs on my machine." — orchestrator/orchestrator/api/web_settings.py:117-118, orchestrator/orchestrator/api/web_settings.py:123-132 [DERIVED]

**connect_prompt(key, libraries, private, url=None, *, owner=False)** — out: MCP URL, "Transport: Streamable HTTP", `Authorization: Bearer {key}`, connector link, setup lines for Claude Code / Codex / Gemini CLI / OpenCode / Claude.ai / others, usage_lines, then a keep-private warning differing owner vs friend — orchestrator/orchestrator/api/web_settings.py:149-171 [DERIVED]

**create_my_key (POST /keys)** — pre: caller is a friend; owner or no identity → 409 OWNER_USES_ENV_KEY. in: KeyBody.label. out: 201 `{key: raw, ..., shown_once: True, connector_url, prompt}` built from the friend's sorted corpus_ids + private corpus. post: KEY_LIMIT → 409, other AccountError → 400 — orchestrator/orchestrator/api/web_settings.py:191-202 [DERIVED]

**revoke_my_key (DELETE /keys/{key_id})** — pre: key_id owned by caller else 404 NOT_FOUND. out: `{"revoked": key_id}` — orchestrator/orchestrator/api/web_settings.py:206-213 [DERIVED]

**prompt_template (GET /keys/prompt)** — owner: owner_prompt + connect_command, `"key_included": False`, placeholder null; friend: connect_prompt with KEY_PLACEHOLDER `"<YOUR_KEY>"` — orchestrator/orchestrator/api/web_settings.py:217-232 [DERIVED]

**owner_key_for_copy (GET /keys/owner)** — pre: owner only (403 OWNER_ONLY belt-and-braces); `POLYMATH_MCP_API_KEY` non-empty else 404 OWNER_KEY_NOT_SET. out: main key in clear, mcp_url, connector_url, owner connect prompt; never cached — orchestrator/orchestrator/api/web_settings.py:236-252 [DERIVED]

**_shared_libraries()** — out: every corpus_id from `SELECT corpus_id FROM corpora ORDER BY corpus_id` minus `fr-`-prefixed — orchestrator/orchestrator/api/web_settings.py:256-260 [DERIVED]

**friend_defaults()** — out: `([ALL_LIBRARIES], _adapters())`; wildcard, not a snapshot — orchestrator/orchestrator/api/web_settings.py:268-272 [DERIVED]

**add_friend (POST /admin/friends)** — in: FriendBody; corpus_ids None → `["*"]`; any `fr-` entry → 400 PRIVATE_LIBRARY. out: 201 friend record + `first_password` = `secrets.token_urlsafe(12)`, `shown_once: True`. post: EXISTS → 409, else 400 — orchestrator/orchestrator/api/web_settings.py:289-301 [DERIVED]

**friend_action (POST /admin/friends/{username}/{action})** — action in {enable, disable, reset-password}; reset-password returns a new `secrets.token_urlsafe(12)` once; NOT_FOUND → 404; anything else → 404 UNKNOWN_ACTION — orchestrator/orchestrator/api/web_settings.py:305-317 [DERIVED]

**set_libraries (PUT /admin/friends/{username}/libraries)** — rejects `fr-` corpora (400 PRIVATE_LIBRARY); NOT_FOUND → 404 — orchestrator/orchestrator/api/web_settings.py:321-328 [DERIVED]

**get_invite / rotate_invite** — owner-only; `code` is null until the first rotate; rotate replaces the code (friends not yet signed up need the new one) — orchestrator/orchestrator/api/web_settings.py:331-349 [DERIVED]

**friend_keys / revoke_friend_key** — owner view/revoke of a friend's keys; revoke AccountError → 404; out `{"revoked": key_id}` — orchestrator/orchestrator/api/web_settings.py:353-365 [DERIVED]

## effect surface
- Postgres: reads `corpora` (`SELECT corpus_id FROM corpora ORDER BY corpus_id`); writes no table in this file — orchestrator/orchestrator/api/web_settings.py:259 [DERIVED]
- Principals registry file: path from `W.registry_path()`, 503 ACCOUNTS_NOT_CONFIGURED when `POLYMATH_MCP_PRINCIPALS_FILE` unset; all mutations delegated to `W.*(_path(), ...)` — orchestrator/orchestrator/api/web_settings.py:70-74, orchestrator/orchestrator/api/web_settings.py:196,212,298,313,326,348,362 [DERIVED]
- Env: `POLYMATH_PUBLIC_MCP_URL` = "https://mcp.kingsleylab.xyz/mcp" — orchestrator/orchestrator/api/web_settings.py:84; `POLYMATH_MCP_API_KEY` (no default; empty → 404) — orchestrator/orchestrator/api/web_settings.py:244-246; `POLYMATH_MCP_PRINCIPALS_FILE` (via W.registry_path()) — orchestrator/orchestrator/api/web_settings.py:73 [DERIVED]
- Subprocess / network: none; connect_command only builds a string, the script runs on the Mac — orchestrator/orchestrator/api/web_settings.py:100-101 [DERIVED]
- Prompt text embeds external constants: "https://github.com/Panniantong/Agent-Reach" and "agent-reach doctor --json" — orchestrator/orchestrator/api/web_settings.py:43-44,128 [DERIVED]
- No Qdrant access; polymath_deep_research / polymath_search / polymath_explore / polymath_answer / polymath_compare occur only as literals inside the prompt text — orchestrator/orchestrator/api/web_settings.py:121-125 [DERIVED]

## invariants
INVARIANT: ALL_LIBRARIES == "*" and is "the same token as polymath_shared.query_scope.ALL_LIBRARIES ... pinned by a test" — orchestrator/orchestrator/api/web_settings.py:40-42 [DERIVED]
  fails-if: wildcard grants stop resolving; friends with "every library" lose libraries added later.
INVARIANT: FriendBody corpus_ids None ⇒ stored as `["*"]`; any id starting "fr-" is filtered or rejected everywhere — orchestrator/orchestrator/api/web_settings.py:54, 260, 292-294, 323-324 [DERIVED]
  fails-if: one friend can reach another friend's private fr-* library.
INVARIANT: raw key text appears only in the create response (`shown_once: True`, 201) and owner_key_for_copy; the template route uses `"<YOUR_KEY>"` — orchestrator/orchestrator/api/web_settings.py:39, 201, 230, 251-252 [DERIVED]
  fails-if: key disclosed on a read route.
INVARIANT: all 13 handlers return `_no_store` ⇒ header `cache-control: no-store` on every response — orchestrator/orchestrator/api/web_settings.py:77-80 [DERIVED]
  fails-if: key-bearing 200s become cacheable.
INVARIANT: connector_url output ends with `/k/{key}/mcp` — orchestrator/orchestrator/api/web_settings.py:91-92 [DERIVED]
  fails-if: mcp_server.KeyInPath can no longer move the key into the Authorization header.
INVARIANT: owner or missing identity ⇒ no web-made keys (409 OWNER_USES_ENV_KEY); owner key comes only from env — orchestrator/orchestrator/api/web_settings.py:182, 193-194, 208-209, 244 [DERIVED]
  fails-if: owner accumulates registry keys that .env rotation does not revoke.
INVARIANT: friend active keys ≤ 3 ("a friend holds at most 3 active ones"; enforced as W.MAX_ACTIVE_KEYS, KEY_LIMIT → 409) — orchestrator/orchestrator/api/web_settings.py:5, 186, 197-198 [DERIVED]
  fails-if: unbounded key creation per friend.

## determinism & idempotency
determinism: NONDETERMINISTIC (random `secrets.token_urlsafe` — orchestrator/orchestrator/api/web_settings.py:296,312; env reads POLYMATH_PUBLIC_MCP_URL :84, POLYMATH_MCP_API_KEY :244; db read corpora :258-259)
idempotency: SAFE for GETs, enable/disable (:308-310), and revokes (repeat → 404, no mutation :210-211, :363-364). UNSAFE for add_friend (repeat username → 409 EXISTS :300), create_my_key (consumes one of max 3 :196), reset-password (new secret each call :312-314), rotate_invite (invalidates prior code :344-349).

## failure behaviour
- Two broad `except Exception` (`# noqa: BLE001`) swallow any `_shared_libraries()` failure and set `libraries = []`; caller still gets 200 and the prompt renders `"(none yet)"` — orchestrator/orchestrator/api/web_settings.py:222-225, 247-250, 109 [DERIVED]
- Error envelope: HTTPException detail `{"error_code", "message"}` via `_refuse` — orchestrator/orchestrator/api/web_settings.py:62-63 [DERIVED]
- AccountError mapping: KEY_LIMIT→409 else 400 (:197-198); EXISTS→409 else 400 (:299-300); NOT_FOUND→404 (:315-316, :327-328, :363-364) [DERIVED]
- Codes raised: ACCOUNTS_NOT_CONFIGURED 503 (:73); OWNER_USES_ENV_KEY 409 (:194, :209); NOT_FOUND 404 (:211); OWNER_ONLY 403 (:243, :278); PRIVATE_LIBRARY 400 (:294, :324); OWNER_KEY_NOT_SET 404 (:246); UNKNOWN_ACTION 404 (:317) [DERIVED]

## dumb-code flags
- Magic 12 duplicated: `secrets.token_urlsafe(12)` at :296 and :312 — orchestrator/orchestrator/api/web_settings.py:296,312 [DERIVED]
- Literal `"fr-"` repeated in three separate checks, not a named constant — orchestrator/orchestrator/api/web_settings.py:260,292,323 [DERIVED]
- ALL_LIBRARIES re-declared locally as `"*"` instead of imported; cross-module equality held only by a test — orchestrator/orchestrator/api/web_settings.py:40-42 [DERIVED]
- Identical fallback-to-`[]` blocks duplicated verbatim — orchestrator/orchestrator/api/web_settings.py:222-225 vs :247-250 [DERIVED]
- Hand-rolled suffix surgery `base[:-len('/mcp')] if base.endswith('/mcp')` instead of a string method — orchestrator/orchestrator/api/web_settings.py:92 [DERIVED]
- `ident is None or ident.is_owner`: a request with no `web_identity` takes the owner branch in all /keys* handlers, and `_require_owner` / owner_key_for_copy also pass on None — safety rests entirely on the boundary middleware — orchestrator/orchestrator/api/web_settings.py:182,193,208,221,242,277 [DERIVED]
- Field length magics: 60 (:48), 2..32 (:52), 80 (:53) — orchestrator/orchestrator/api/web_settings.py:48,52,53 [DERIVED]

## refactor notes
- The 13 route paths are the Settings page HTTP contract; importers are web_auth.py and main.py (FACTS.importers) — path or handler renames ripple there — orchestrator/orchestrator/api/web_settings.py (line out of range) [DERIVED]
- usage_lines restates the MCP playbook rules of polymath_shared.mcp_retrieval.playbook in prompt prose; behavior changes must touch both — orchestrator/orchestrator/api/web_settings.py:20-21,113-114 [DERIVED]
- connector_url and mcp_server.KeyInPath agree on `/k/<key>/mcp`; change them together — orchestrator/orchestrator/api/web_settings.py:88-92 [DERIVED]
- connect_command hardcodes REPO_ROOT `parents[3]` + scripts/connect_agents.sh; a repo layout move breaks the string — orchestrator/orchestrator/api/web_settings.py:95-96,101 [DERIVED]
- ALL_LIBRARIES must stay `"*"` and in sync with polymath_shared.query_scope (test-pinned) — orchestrator/orchestrator/api/web_settings.py:40-42 [DERIVED]
- web_accounts (W) surface used here: registry_path, read_registry, list_keys, create_key, revoke_key, list_friends, add_friend, set_friend_enabled, reset_friend_password, set_friend_corpora, invite_record, rotate_invite, principal_id_for, normalize_username, private_corpus_for, MAX_ACTIVE_KEYS, AccountError, WebIdentity — web_accounts signature changes break this file — orchestrator/orchestrator/api/web_settings.py:174-365 [DERIVED]

## VERIFY
```verify
grep -Fq 'ALL_LIBRARIES = "*"' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'KEY_PLACEHOLDER = "<YOUR_KEY>"' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'https://mcp.kingsleylab.xyz/mcp' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'OWNER_USES_ENV_KEY' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'secrets.token_urlsafe(12)' orchestrator/orchestrator/api/web_settings.py
grep -Fq 'SELECT corpus_id FROM corpora ORDER BY corpus_id' orchestrator/orchestrator/api/web_settings.py
grep -Fq '= "no-store"' orchestrator/orchestrator/api/web_settings.py
test "$(grep -c -F 'token_urlsafe' orchestrator/orchestrator/api/web_settings.py)" -ge 2
```
