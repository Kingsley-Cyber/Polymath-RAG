# flow: mcp-call
An MCP tool call to Server A (HTTP :8930): the key check (principals), scope, the tool, the call into the orchestrator, the answer.

Server A is one process serving the loopback listener AND the public hostname through the tunnel; the gate decides per request which surface a call came from. `orchestrator/orchestrator/mcp_server.py:77-80` [DERIVED]

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Listener + ASGI stack built by `build_app()`: FastMCP streamable-http + FAIL-CLOSED bearer gate + open `/health`; PORT from `POLYMATH_MCP_PORT` (default `8930`) | mcp_server.py:59, 670-672 [DERIVED] | HTTP request on :8930 -> ASGI scope | — |
| 2 | `KeyInPath` (the OUTERMOST layer): path `/k/<key>/mcp` matched by `_KEY_PATH` -> key moved into `Authorization: Bearer`, path rewritten to `/mcp` in place (uvicorn's access log reads the same dict, never the key); a key segment further down a path is rewritten to `/k/redacted` | mcp_server.py:640-647, 650-667 [DERIVED] | `/k/<key>/mcp` -> `/mcp` + bearer header | stray key segment dropped (that path is a 404 anyway) |
| 3 | `/health` is open: reports `service: polymath-mcp`, `auth: "configured"`/`"MISSING"`, tool names | mcp_server.py:681-684 [DERIVED] | GET /health -> JSON status | — |
| 4 | BearerGate fail-closed check: `API_KEY` empty -> 503 `"MCP bearer key not configured (POLYMATH_MCP_API_KEY); refusing to serve"` | mcp_server.py:698-700 [DERIVED] | request -> 503 JSON | total refusal by design (V2; 2026-09-02: V1 booted keyless and the public mirror answered tools/call to anyone, mcp_server.py:22-24) |
| 5 | Bearer authenticated to ONE principal: `POLYMATH_MCP_API_KEY` = OWNER (admin); every other caller is a principal from `$POLYMATH_MCP_PRINCIPALS_FILE` — raw bearer `pmk_<key_id>_<secret>` matched by `BEARER_RE`, secret compared as sha256 via `hash_key`, never stored | mcp_server.py:21-23, 93-96; mcp_principals.py:5-8, 11, 37, 101-102 [DERIVED] | bearer -> `Principal` | 401 no / unknown / revoked / expired key (mcp_server.py:687) |
| 6 | Rate limit: `_LIMITER = P.RateLimiter()`; a principal may carry `rate_per_minute` | mcp_server.py:97; mcp_principals.py:79 [DERIVED] | principal -> allow/deny | 429 over the principal's rate (mcp_server.py:687) |
| 7 | `authorize(p, tool, arguments)` judges the tools/call BEFORE the MCP layer sees it: admin -> ALLOW; else TOOL_POLICY (any-of action scopes, resource kind); tool with no policy -> deny `tool_not_permitted` | mcp_server.py:90-92; mcp_principals.py:54-68, 105-113 [DERIVED] | (principal, tool, args) -> `Decision` | 403 action scope, corpus, adapter, another principal's run, anything without a policy (mcp_server.py:687-688) |
| 8 | Request context set: `_PRINCIPAL` (default NOBODY), `_CALLER_AGENT` (default `"polymath-mcp"`), `_CALLER_IS_LOCAL` from `_is_local_caller` = Host in `_LOOPBACK_HOSTS` AND none of `_EDGE_HEADERS` present; default False | mcp_server.py:81-86, 93-95, 101-103 [DERIVED] | headers -> contextvars | lost context counts as NOT local -> local-only tools refuse (fail closed, mcp_server.py:79-83) |
| 9 | MCP transport: `mcp.streamable_http_app(stateless_http=True, transport_security=_SECURITY)` — DNS-rebinding allowlist `_ALLOWED_HOSTS` + origins incl. `https://claude.ai`, `https://claude.com` | mcp_server.py:64-75, 678-679 [DERIVED] | scope -> MCP session | disallowed Host/Origin rejected (the v33 gotcha, mcp_server.py:67) |
| 10 | Tool dispatch: every tool is a thin, trimmed call to the orchestrator API on 127.0.0.1:7200, so MCP cannot bypass the pipeline's own gates | mcp_server.py:4-9 [DERIVED] | tools/call name+args -> tool coroutine | — |
| 11 | Tool-local gate (upload_document only): requires `_CALLER_IS_LOCAL` AND `is_admin`, else returns `REMOTE_PATH_UPLOAD_DISABLED` (403) before ANY filesystem access — no existence oracle | mcp_server.py:84-87, 200-202 [DERIVED] | path -> 403 or file handle | 404 file not found; 422 unsupported extension (mcp_server.py:204-208) |
| 12 | `_orch()` builds the loopback call: NOBODY -> 401 `NO_PRINCIPAL`; `User-Agent` = caller agent; non-admin gets header `x-polymath-principal: <principal_id>`; timeout default 180 | mcp_server.py:128-146; mcp_principals.py:39 [DERIVED] | method+path+json -> orchestrator request | 401 NO_PRINCIPAL (fail closed, mcp_server.py:133-134) |
| 13 | Orchestrator HTTP round trip to `ORCH` (default `http://127.0.0.1:7200`); uploads post to `/upload` with timeout 600 | mcp_server.py:58, 141-146, 209-212, 234-237 [DERIVED] | request -> JSON | status >= 400 -> `{"error": detail, "status": code}` (mcp_server.py:143-145) |
| 14 | Response shaping: `_trim_hit` cuts text at 1400 chars; `_trim_rows` cuts `text`/`text_clean` at 1200; `ask`/`polymath_answer` slim `evidence`/`chunks`/`bundle` to first 12 rows at 600 chars | mcp_server.py:149-165, 330-343, 397-401, 447-451 [DERIVED] | orchestrator JSON -> slim tool result | silent truncation, self-labeled (see failure 8) |
| 15 | Principal-scoped filtering in-tool: `list_corpora` keeps only `who.corpus_ids`; `adapter_list` keeps only `who.adapter_ids`; `recent_queries` narrows to the principal's OWN receipts | mcp_server.py:176-178, 469, 482-484 [DERIVED] | result list -> filtered list | silent row removal (never an error) |
| 16 | Tool result returned to the MCP client as a JSON dict; error paths carry `{"error", "status"}` | mcp_server.py:145, 313-318 [DERIVED] | slim result -> MCP response | — |

## state written

| state | what | anchor |
|---|---|---|
| `adapter_runs.owner_principal_id` | run ownership persisted by the adapter runtime from the trusted forwarded principal context (`adapter_start` forwards it) | mcp_server.py:496; mcp_principals.py:16-18 [DERIVED] |
| Query receipts (QUERY-RECEIPTS-V1) | every served `/chat`, `/ask` or `/retrieve`: `wall_ms`, mode, status ok/abstained/error, citation count, error text; the receipt's `client` is the caller's own User-Agent | mcp_server.py:134-135, 459-466 [DERIVED] |
| Hypotheses from `adapter_submit` | AGENT_REASON hypotheses become durable state with lineage | mcp_server.py:519-520 [DERIVED] |
| `POLYMATH_MCP_PRINCIPALS_FILE` | ONE JSON file outside the repository, re-read when it changes, so a revocation needs no fleet bounce (read-path state, machine-local like `.env`) | mcp_principals.py:12-13 [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PORT` | `8930` | listener port of Server A | mcp_server.py:59 |
| `POLYMATH_MCP_API_KEY` | `""` | OWNER admin bearer; empty -> /mcp answers 503 (fail closed) | mcp_server.py:60, 698-700 |
| `POLYMATH_ORCH_URL` | `http://127.0.0.1:7200` | base URL every tool calls | mcp_server.py:58 |
| `POLYMATH_MCP_PUBLIC_HOST` | `mcp.kingsleylab.xyz` | public Host/Origins allowed through the tunnel | mcp_server.py:61, 64-75 |
| `POLYMATH_MCP_PRINCIPALS_FILE` | path outside the repo | principals store; re-read on change | mcp_server.py:20; mcp_principals.py:12-13 |
| `mode` (retrieve / ask / polymath_answer / polymath_explore) | `HYBRID` | lane selection: FAST / HYBRID / GRAPH / EXPLORE | mcp_server.py:291, 381, 421, 434 |
| `latent` (retrieve / ask / polymath_answer) | `None` | `latent=false` disables the cross-domain latent lane for that call (HYBRID/GRAPH run it by default) | mcp_server.py:292-300, 382-390, 434-442 |
| `corpus_explorer` (polymath_explore) | `True` | runs the concept-activation explorer | mcp_server.py:420-426 |

## failure modes

1. Every /mcp call returns 503 -> `POLYMATH_MCP_API_KEY` unset (V2 fail-closed; measured 2026-09-02: V1 booted without the key and the public mirror answered tools/call to anyone) -> mcp_server.py:22-24, 698-700.
2. 401 -> bearer missing / unknown / revoked / expired; a `pmk_<key_id>_<secret>` form that fails `BEARER_RE` or whose sha256 is not in the store -> mcp_server.py:687; mcp_principals.py:5-8, 37.
3. 403 -> principal lacks the action scope, corpus / adapter / run / write permission, or the tool has no TOOL_POLICY entry (admin-only) -> mcp_principals.py:56-68, 111-113; mcp_server.py:687-688.
4. 403 `REMOTE_PATH_UPLOAD_DISABLED` -> upload_document from a remote or non-admin caller; refused before any filesystem access -> mcp_server.py:84-87, 200-202.
5. 429 -> principal over its `rate_per_minute` -> mcp_server.py:687; mcp_principals.py:79.
6. 401 `NO_PRINCIPAL` -> a tool body ran without the gate having set a principal (contextvar left at NOBODY); nothing goes out under `prn_nobody` -> mcp_server.py:93-94, 133-134.
7. 20 s answers that abstain -> the pre-V2 unscoped all-corpora retrieve/ask path (scoped path answered the same question in 3 s with 16 citations); `corpus_id` is now REQUIRED -> mcp_server.py:25-27.
8. Silent evidence truncation -> `_trim_hit` 1400 chars, `_trim_rows` 1200 chars, chat evidence 600 chars x 12 rows; a cut row self-reports `truncated: true` + `full_length` (D-02) -> mcp_server.py:149-165, 330-343, 397-401.
9. Silent list filtering -> non-admin `list_corpora` / `adapter_list` drop rows outside the principal's allowlists -> mcp_server.py:176-178, 482-484.
10. `verdict=insufficient_evidence` from polymath_answer -> the corpus cannot support the question; relay it, do not fill the gap -> mcp_server.py:437-442.
11. 409 from adapter_result -> the run is still running or awaiting a step -> mcp_server.py:540-542.
12. `HUMAN_ACTION_REQUIRED` from research_acquire -> the site showed a sign-in or human check; stop and ask the user, never work around it -> mcp_server.py:564-567.

## invariants

- INVARIANT fail-closed-no-key: with no key configured the server answers 503 on /mcp instead of running open. (mcp_server.py:22-24, 698-700)
- INVARIANT nobody-refused: no gate -> principal NOBODY -> `_orch` returns 401 NO_PRINCIPAL; nothing is served under `prn_nobody`. (mcp_server.py:93-94, 133-134)
- INVARIANT thin-tools: every tool is a thin, trimmed call to the orchestrator API; MCP can never bypass the pipeline's own gates. (mcp_server.py:8-9)
- INVARIANT corpus-id-required: retrieve/ask REQUIRE corpus_id. (mcp_server.py:25-27)
- INVARIANT default-deny: a tool absent from TOOL_POLICY is admin-only. (mcp_principals.py:54-55, 111-113)
- INVARIANT secret-hash-only: a principal's raw secret is never stored, logged or printed; only its sha256 via `hash_key`. (mcp_principals.py:5-8, 101-102)
- INVARIANT key-never-logged: the key-in-path is rewritten in place to /mcp before uvicorn's access log; stray key segments become `/k/redacted`. (mcp_server.py:659-666)
- INVARIANT truncation-labeled: a cut hit/row always carries `truncated: true` + `full_length` (D-02). (mcp_server.py:150-151, 331-332)
- INVARIANT reason-is-machine-code: `Decision.reason` is a stable machine code and never carries resource details. (mcp_principals.py:90)
- INVARIANT identity-is-not-authorization: `agent_identity` and a receipt's `client` name the acting SOFTWARE and never carry authorization; run ownership is `adapter_runs.owner_principal_id`. (mcp_principals.py:16-18)
- INVARIANT local-defaults-refused: caller-locality defaults to NOT local; upload_document additionally requires admin. (mcp_server.py:79-83, 101-103, 200-202)

## VERIFY
```verify
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail closed)' orchestrator/orchestrator/mcp_server.py
grep -Eq '^_KEY_PATH = ' orchestrator/orchestrator/mcp_server.py
grep -Fq 'stateless_http=True' orchestrator/orchestrator/mcp_server.py
grep -Fq 'PRINCIPAL_HEADER = "x-polymath-principal"' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'DEFAULT DENY' orchestrator/orchestrator/mcp_principals.py
```
