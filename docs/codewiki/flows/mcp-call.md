# flow: mcp-call
An MCP tool call to Server A (HTTP :8930): the key check (principals), scope, the tool, the call into the orchestrator, the answer.

## hops
| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Client POSTs a tools/call to `/mcp`; auth is `Authorization: Bearer <key>`, or the key in the URL `/k/<key>/mcp` (KeyInPath turns it into the same header — claude.ai's connector cannot send a header) | orchestrator/orchestrator/mcp_server.py:30-31,41-42,71-74 [DERIVED] | HTTP request -> MCP transport | missing/invalid bearer (hop 4) |
| 2 | Transport allowlist (DNS-rebinding guard, "the v33 gotcha"): Host must be `127.0.0.1:8930` / `localhost:8930` / PUBLIC_HOST / `PUBLIC_HOST:443`; Origin limited to `https://{PUBLIC_HOST}`, loopback http, `https://claude.ai`, `https://claude.com` | orchestrator/orchestrator/mcp_server.py:80-88 [DERIVED] | Host/Origin headers -> admission | other Host/Origin rejected |
| 3 | Fail-closed boot: with no key configured (`POLYMATH_MCP_API_KEY` = "") the server answers 503 on /mcp instead of running open (V1 measured 2026-09-02 booted keyless and answered tools/call to anyone) | orchestrator/orchestrator/mcp_server.py:34-36,73 [DERIVED] | boot config -> 503 | the 503 IS the failure mode |
| 4 | Gate authenticates the bearer to ONE principal per request, before the MCP layer sees it: raw bearer `pmk_<key_id>_<secret>` resolved via `_STORE = P.store_from_env(API_KEY)`; `POLYMATH_MCP_API_KEY` = built-in OWNER principal (`prn_owner`, admin); all other principals from the JSON file; keys stored as sha256 of the bearer, secret never stored | orchestrator/orchestrator/mcp_server.py:103-109; orchestrator/orchestrator/mcp_principals.py:5-13,51-52 [DERIVED] | bearer -> P.Principal | 401 unknown/revoked key |
| 5 | Rate limit: `_LIMITER = P.RateLimiter()` against the principal's optional requests-per-minute | orchestrator/orchestrator/mcp_server.py:33,110; orchestrator/orchestrator/mcp_principals.py:7-8 [DERIVED] | principal -> allow/deny | 429 over its rate |
| 6 | Tool authorization via `TOOL_POLICY`: tool -> (any-of action scopes, resource kind); a tool with NO policy row is admin-only (DEFAULT DENY) | orchestrator/orchestrator/mcp_principals.py:78-98,9-10 [DERIVED] | tool name + scopes -> permit | 403 not permitted |
| 7 | Resource check: CORPUS tools need a corpus_id the principal may use; `*` wildcard = every library existing at request time, never another person's private library (`query_scope.grant_allows`); `corpus_optional` (product_search) may omit corpus_id, a named one is still checked; adapter.cancel only ever reaches a run the principal owns; every query tool REQUIRES corpus_id (V2) | orchestrator/orchestrator/mcp_server.py:37-39; orchestrator/orchestrator/mcp_principals.py:21-26,66-67,79-82 [DERIVED] | corpus_id/adapter_id/run_id -> permit | 403 outside grant |
| 8 | Per-request contextvars set: `_PRINCIPAL` (default NOBODY, `prn_nobody`), `_CALLER_AGENT` (caller User-Agent, default `polymath-mcp`), `_CALLER_IS_LOCAL` from `_is_local_caller` = loopback Host AND none of `cf-connecting-ip`, `cf-ray`, `cdn-loop`, `x-forwarded-for`, `forwarded`; default is NOT local (fail closed) | orchestrator/orchestrator/mcp_server.py:90-116 [DERIVED] | headers -> contextvars | lost context refuses host tools |
| 9 | Discovery: `list_tools` filters out `MR.HIDDEN_TOOLS_A` — deprecated `retrieve` / `retrieve_evidence` / `compile_plan` / `ask` stay callable but are never listed | orchestrator/orchestrator/mcp_server.py:26,119-124 [DERIVED] | tools/list -> filtered list | old callers still reach deprecated tools |
| 10 | Tool body runs. `polymath_search`: `MR.normalize_mode(mode)`; None -> `MR.mode_error`; else `_orch("POST", "/chat/evidence", json=MR.search_body(query, corpus_id, m))` | orchestrator/orchestrator/mcp_server.py:452-462 [DERIVED] | query, corpus_id, mode -> /chat/evidence body | 422 unknown mode |
| 11 | Ingest example `upload_document`: caller must be local AND admin, else `REMOTE_PATH_UPLOAD_DISABLED` 403 returned BEFORE any filesystem access (no existence oracle); extension must be in `{.md, .txt, .html, .pdf, .epub, .docx}`; file streamed to POST /upload; run_id is content-addressed (same bytes -> existing run, `already_exists` true) | orchestrator/orchestrator/mcp_server.py:75,243-273 [DERIVED] | path, corpus_id -> run_id | 404 not found; 422 extension; 409 CROSS_CORPUS_CONTENT_COLLISION |
| 12 | `upload_text` stamps the principal (F15: it used to send no trusted headers, so a friend's upload ran as the owner) | orchestrator/orchestrator/mcp_server.py:276-301 [DERIVED] | text, corpus_id, source_name -> run_id | 422 bad source_name extension |
| 13 | `_trusted_headers` builds the trusted loopback context: returns None when principal is NOBODY; non-admin gets `x-polymath-principal`; User-Agent = caller agent (becomes receipt.client) | orchestrator/orchestrator/mcp_server.py:138,141-152 [DERIVED] | principal -> headers or None | NO_PRINCIPAL `{"status": 401}` |
| 14 | `_orch` sends the httpx request to ORCH (default `http://127.0.0.1:7200`), timeout default 180; response >= 400 -> `{"error": detail, "status": code}` (detail from JSON `detail` or `r.text[:400]`) | orchestrator/orchestrator/mcp_server.py:155-168 [DERIVED] | method/path/json -> orchestrator JSON | orchestrator error passthrough |
| 15 | Streaming variant (`polymath_deep_research`): `_orch_events` POSTs `/research/deep` with `Accept: text/event-stream`, timeout 1800.0, collects frames via `MR.parse_sse`; refusal before the stream -> one `("error", {...})` frame | orchestrator/orchestrator/mcp_server.py:171-190,526-541 [DERIVED] | `MR.deep_body` -> SSE frames | error_code from detail or `HTTP_<status>` |
| 16 | Model default (`polymath_answer` / `product_search` with model=None): `_app_default_model` reads GET `/synthesizers` for the row marked `default`, cached at most `MR.DEFAULT_MODEL_TTL_S`; None = nothing sent | orchestrator/orchestrator/mcp_server.py:480-487,500,557 [DERIVED] | /synthesizers -> model id | catalog unavailable: model omitted |
| 17 | Answer shaping: `MR.shape_search(out, max_evidence)`; `_trim_hit` cuts text at 1400 chars and stamps `truncated: true` + `full_length`; `_trim_rows` cuts at 1200 (D-02); `polymath_answer` slims evidence/chunks/bundle to 12 hits at 600 chars | orchestrator/orchestrator/mcp_server.py:193-209,384-386,457,504-508 [DERIVED] | orchestrator JSON -> slim MCP result | — |
| 18 | Return; `adapter_start` stamps the forwarded principal as `adapter_runs.owner_principal_id` — ownership persisted and enforced by the adapter runtime, not by the gate | orchestrator/orchestrator/mcp_server.py:599-602; orchestrator/orchestrator/mcp_principals.py:28-29 [DERIVED] | principal context -> run owner column | — |

## state written
- `POLYMATH_MCP_PRINCIPALS_FILE`: ONE JSON file outside the repository, machine-local; re-read when it changes, so a revocation needs no fleet bounce. orchestrator/orchestrator/mcp_principals.py:12-13 [DERIVED]
- Principal KEYS: sha256 of the raw bearer per key (key_id, created/revoked); the secret is never stored, logged or printed. orchestrator/orchestrator/mcp_principals.py:5-8 [DERIVED]
- `adapter_runs.owner_principal_id`: persisted and enforced by the adapter runtime from the trusted principal context the gate forwards. orchestrator/orchestrator/mcp_principals.py:28-29; orchestrator/orchestrator/mcp_server.py:601 [DERIVED]
- Query receipts: `receipt.client` = the caller's own User-Agent; a principal's context narrows `recent_queries` (GET /queries) to its OWN receipts. orchestrator/orchestrator/mcp_server.py:143-145,584 [DERIVED]
- In-process default-model cache refreshed at most every `MR.DEFAULT_MODEL_TTL_S`. orchestrator/orchestrator/mcp_server.py:484-487 [DERIVED]
- No Postgres/Qdrant write occurs inside Server A in the shown SOURCE; the only named durable column written downstream is `adapter_runs.owner_principal_id`. [INFERRED] (no DB write appears in the shown Server A code)

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PORT` | `8930` | listener port; builds `_ALLOWED_HOSTS` and `_LOOPBACK_HOSTS` | orchestrator/orchestrator/mcp_server.py:41,72,77-78,94 [DERIVED] |
| `POLYMATH_MCP_API_KEY` | `""` | OWNER (admin) bearer; seeds `P.store_from_env(API_KEY)`; unset -> 503 fail-closed | orchestrator/orchestrator/mcp_server.py:41,73,109,34-36 [DERIVED] |
| `POLYMATH_ORCH_URL` | `http://127.0.0.1:7200` | base URL of every `_orch` / `_orch_events` call | orchestrator/orchestrator/mcp_server.py:42,71 [DERIVED] |
| `POLYMATH_MCP_PUBLIC_HOST` | `mcp.kingsleylab.xyz` | public host allowlisted bare, with `:443`, and as https origin | orchestrator/orchestrator/mcp_server.py:43,74,77-88 [DERIVED] |
| `POLYMATH_MCP_PRINCIPALS_FILE` | not shown in SOURCE | location of the principals JSON file; file re-read on change | orchestrator/orchestrator/mcp_principals.py:12 [DERIVED] |

## failure modes
1. 503 on /mcp -> no `POLYMATH_MCP_API_KEY` configured; V2 refuses to run open (V1 measured open 2026-09-02) -> orchestrator/orchestrator/mcp_server.py:34-36
2. 401 -> bearer matches no enabled principal (unknown or revoked key) -> orchestrator/orchestrator/mcp_server.py:32-33
3. Tool answers NO_PRINCIPAL (401) with no orchestrator call made -> gate never set a principal; `_trusted_headers` returned None (fail closed) -> orchestrator/orchestrator/mcp_server.py:138,146-148,158-159
4. 403 not permitted -> tool outside the principal's scopes or resource outside its grant; a tool absent from TOOL_POLICY is admin-only -> orchestrator/orchestrator/mcp_principals.py:9-10,78-79; orchestrator/orchestrator/mcp_server.py:33
5. 403 REMOTE_PATH_UPLOAD_DISABLED -> upload_document from a non-local or non-admin caller; returned before ANY filesystem access, so the caller gets no file-existence oracle -> orchestrator/orchestrator/mcp_server.py:97-100,252-253
6. 429 -> principal over its optional requests-per-minute -> orchestrator/orchestrator/mcp_server.py:33; orchestrator/orchestrator/mcp_principals.py:7-8
7. Silent owner-context fallback (FIXED, FRIEND-JOURNEY F15): upload_text used to send no trusted headers so a friend's upload ran as the owner; now every orchestrator call from a tool carries them -> orchestrator/orchestrator/mcp_server.py:143-148,285-287
8. 409 CROSS_CORPUS_CONTENT_COLLISION on upload -> same content bytes already live in ANOTHER corpus (content belongs to one corpus) -> orchestrator/orchestrator/mcp_server.py:248-250
9. 422 unknown mode / depth / reasoning style -> `MR.normalize_mode` / `MR.normalize_depth` / `MR.normalize_reasoning` returned None; the tool answers with the allowed lists -> orchestrator/orchestrator/mcp_server.py:458-460,495-499,536-539
10. Every orchestrator error comes back as `{"error": detail, "status": code}` -> any response >= 400; a non-JSON body degrades to `r.text[:400]` -> orchestrator/orchestrator/mcp_server.py:163-167
11. Deep research returns a single error frame -> refusal before the SSE stream starts; error_code taken from the detail or `HTTP_<status>` -> orchestrator/orchestrator/mcp_server.py:182-190
12. adapter_result 409 -> run still running or awaiting the caller -> orchestrator/orchestrator/mcp_server.py:637-638
13. Deprecated tools silently reachable -> retrieve / retrieve_evidence / compile_plan / ask are hidden from listing only, still callable; polymath_search used to reach the frozen LEGACY route through them -> orchestrator/orchestrator/mcp_server.py:26,119-124
14. research_acquire refused for principals -> deliberately owner-only: the host browser holds the owner's sign-ins and the orchestrator refuses any principal too -> orchestrator/orchestrator/mcp_server.py:647-648

## invariants
- INVARIANT: every orchestrator call carries `_trusted_headers` output or refuses with NO_PRINCIPAL; nothing is sent under NOBODY. orchestrator/orchestrator/mcp_server.py:141-168 [DERIVED]
- INVARIANT: the bearer secret is never stored, logged or printed; only sha256 of the raw bearer is kept. orchestrator/orchestrator/mcp_principals.py:5-8 [DERIVED]
- INVARIANT: default deny — a tool with no TOOL_POLICY row is admin-only. orchestrator/orchestrator/mcp_principals.py:9-10,78-79 [DERIVED]
- INVARIANT: every query tool REQUIRES corpus_id (V2). orchestrator/orchestrator/mcp_server.py:37-39 [DERIVED]
- INVARIANT: MCP tools are thin, trimmed proxies to the orchestrator API; MCP can never bypass the pipeline's own gates. orchestrator/orchestrator/mcp_server.py:5-9 [DERIVED]
- INVARIANT: a wildcard `*` corpus grant never returns another person's private library. orchestrator/orchestrator/mcp_principals.py:21-23 [DERIVED]
- INVARIANT: `agent_identity` and a receipt's client name the SOFTWARE acting and never carry authorization. orchestrator/orchestrator/mcp_principals.py:29-30 [DERIVED]
- INVARIANT: `_CALLER_IS_LOCAL` defaults False — a lost context is refused, never served as owner-local. orchestrator/orchestrator/mcp_server.py:92-96 [DERIVED]
- INVARIANT: a trimmed hit declares itself (`truncated: true` + `full_length`); a hit that fits keeps exactly its old keys. orchestrator/orchestrator/mcp_server.py:194-195,210-212 [DERIVED]

## VERIFY
```verify
grep -Fq 'os.environ.get("POLYMATH_MCP_PORT", "8930")' orchestrator/orchestrator/mcp_server.py
grep -Fq 'PRINCIPAL_HEADER = "x-polymath-principal"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'default=NOBODY' orchestrator/orchestrator/mcp_server.py
grep -Fq 'FRIEND_SCOPES = tuple(sorted({*FRIEND_PROFILE, UPLOAD_TEXT, HISTORY_READ, ADAPTER_CANCEL, KNOWLEDGE_RESEARCH}))' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'pmk_' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'NO_PRINCIPAL' orchestrator/orchestrator/mcp_server.py)" -ge 2
```
