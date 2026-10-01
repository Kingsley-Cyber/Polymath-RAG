# flow: mcp-call

An agent sends one MCP `tools/call` to Server A — the single public door on `:8930`. The BearerGate authenticates the key to a principal, authorizes the call against `TOOL_POLICY`, then the tool body makes one thin HTTP call into the orchestrator on `127.0.0.1:7200` and returns a trimmed answer. Every step fails closed.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Client POSTs `/mcp` (streamable-http); ONE process serves the loopback listener AND the public host `mcp.kingsleylab.xyz` through the tunnel; `BearerGate.__call__` passes non-http scopes straight through | orchestrator/orchestrator/mcp_server.py:73-76, 651-662 | ASGI scope (headers, method) -> gate path | Host/origin outside the DNS-rebinding allowlist `_SECURITY` (`allowed_hosts`, `allowed_origins`) mcp_server.py:63-71 |
| 2 | Fail-closed key check: empty `POLYMATH_MCP_API_KEY` (`""`) -> 503 `{"error": "MCP bearer key not configured (POLYMATH_MCP_API_KEY); refusing to serve"}` | mcp_server.py:59, 663-666 | env `API_KEY` -> 503 JSON | keyless boot; V1 once booted keyless and the public mirror answered tools/call to anyone (measured 2026-09-02) mcp_server.py:21-23 |
| 3 | Bearer authentication: `_STORE.authenticate(auth[7:] if auth.startswith("Bearer ") else "")`; store = principals JSON, raw bearer `pmk_<key_id>_<secret>`, secret checked via sha256 (`hash_key`) | mcp_server.py:667-672; orchestrator/orchestrator/mcp_principals.py:5-13, 101-102 | raw bearer -> `Principal` | 401 `unauthorized` — no / unknown / revoked / expired key mcp_server.py:670-672, 19-20 |
| 4 | Request context pinned: `_CALLER_IS_LOCAL` = host in `_LOOPBACK_HOSTS` AND no `_EDGE_HEADERS` header; `_PRINCIPAL` = who; `_CALLER_AGENT` = User-Agent cut to 120 chars or `"polymath-mcp"` | mcp_server.py:673-675, 97-99, 77-91 | headers -> contextvars | lost context defaults to NOT local and `NOBODY` — fail closed mcp_server.py:76-79, 89-90 |
| 5 | Admin branch: `who.is_admin` (the OWNER key = `POLYMATH_MCP_API_KEY`) -> straight to the MCP app, body untouched | mcp_server.py:676-678; mcp_principals.py:11, 84 | `Principal` -> app | none on this branch |
| 6 | Principal rate limit: `_LIMITER.allow(who)` | mcp_server.py:679-683 | `Principal` -> allow / (ok, retry_after) | 429 `{"error": "rate limit exceeded", "status": 429}` + `Retry-After` mcp_server.py:681-682 |
| 7 | Non-POST requests pass to the app unjudged | mcp_server.py:684-686 | method != POST -> app | — |
| 8 | Gated body read, cap `MAX_GATED_BODY = 2 * 1024 * 1024` | mcp_server.py:687-690, 94 | `receive()` -> bytes | 413 `{"error": "request body too large", "status": 413}` mcp_server.py:689 |
| 9 | JSON parse of the body | mcp_server.py:691-698 | bytes -> msg | `ValueError` -> msg None (the MCP app answers the protocol error itself); `RecursionError` -> 400 jsonrpc `-32700` "Parse error: nested too deeply" — never passed on unjudged mcp_server.py:693-698 |
| 10 | `_judge(who, msg)`: static `authorize()` against `TOOL_POLICY` (any-of scopes, then resource kind); RUN ownership asked of the adapter runtime; a non-admin request is read ONCE, judged, replayed | mcp_server.py:700, 651-655; mcp_principals.py:105-118, 54-68 | (Principal, msg) -> allow / 403 | 403 `tool_not_permitted` (tool absent from `TOOL_POLICY` = admin-only), `insufficient_scope`, `corpus_not_allowed`, another principal's run mcp_server.py:652-653; mcp_principals.py:111-118 |
| 11 | Allowed call replayed into `mcp.streamable_http_app(stateless_http=True, transport_security=_SECURITY)`, which dispatches the tool coroutine | mcp_server.py:643-644, 654-655 | msg -> tool call | protocol errors answered by the MCP app mcp_server.py:694 |
| 12 | `upload_document` pre-gate: not `_CALLER_IS_LOCAL` or not `is_admin` -> `dict(REMOTE_PATH_UPLOAD_DISABLED)` (403) BEFORE any filesystem access — no existence oracle | mcp_server.py:196-199, 80-83 | (path, corpus_id) -> 403 dict | 403 `REMOTE_PATH_UPLOAD_DISABLED: … Send the content instead: upload_text(text, corpus_id, source_name).` mcp_server.py:81-83 |
| 13 | Tool calls `_orch()`: `who is NOBODY` -> 401 `NO_PRINCIPAL`; headers = `User-Agent` + `x-polymath-principal` (non-admin only) | mcp_server.py:124-133; mcp_principals.py:39 | (method, path, json) -> orch headers | 401 `NO_PRINCIPAL: this call carries no authenticated principal (fail closed)` when no gate ran mcp_server.py:128-130 |
| 14 | Upstream HTTP: `httpx.AsyncClient` to `f"{ORCH}{path}"`, `ORCH` default `http://127.0.0.1:7200`, timeout default 180 | mcp_server.py:57, 125, 134-135 | orch request -> response | orchestrator down / slow; timeout applies [INFERRED: httpx timeout governs the hop] |
| 15 | Answer handling: `r.status_code >= 400` -> `{"error": detail, "status": code}` (detail = `r.json().get("detail")`, non-JSON falls back to `r.text[:400]`); else `r.json()` | mcp_server.py:136-142 | response -> dict | error dict becomes the tool result; non-JSON error text silently cut to 400 chars mcp_server.py:139-141 |
| 16 | Per-tool orchestrator endpoints: `polymath_search` POST `/retrieve` (`evidence: true`); `polymath_explore` POST `/chat/evidence`; `polymath_answer`/`ask` POST `/chat`; `document_status` GET `/status`; `adapter_*` GET/POST `/adapter/...`; `supplier_*` `/supplier/...` | mcp_server.py:403-447, 249-264, 469-544, 570-607 | tool args -> orch path+body | per-tool orch errors, e.g. `adapter_result` 409 while the run is running or awaiting mcp_server.py:533-538 |
| 17 | Owner-only tools: `research_acquire` and `supplier_*` are deliberately NOT in `TOOL_POLICY` (host browser holds the owner's sign-ins; orchestrator refuses any principal too) | mcp_server.py:547-548, 570-572; mcp_principals.py:54-56 | tool call -> deny | 403 `tool_not_permitted` for every non-admin |
| 18 | Outbound trim/filter: evidence rows cut at 1200 chars (`_trim_rows`), hits at 1400 (`_trim_hit`), `ask`/`polymath_answer` evidence at 600 chars and first 12; `list_corpora` filtered to `who.corpus_ids`, `adapter_list` to `who.adapter_ids` for non-admins | mcp_server.py:145-161, 326-339, 392-397, 442-446, 166-175, 471-481 | orch dict -> slim tool result | every cut is flagged `truncated: true` + `full_length` (D-02), but the caller never sees past the cap mcp_server.py:146-147, 327-328 |
| 19 | Tool dict returns through the streamable-http response to the caller | mcp_server.py:636-644 | dict -> MCP result | [INFERRED: FastMCP serializes the returned dict] |

## state written

- `adapter_runs.owner_principal_id` — run ownership is the runtime's: the forwarded principal context becomes the durable owner, persisted and enforced by the adapter runtime. mcp_principals.py:16-18; mcp_server.py:492-493
- QUERY-RECEIPTS-V1 — every served `/chat`, `/ask` or `/retrieve` recorded (wall_ms, mode, status ok/abstained/error, citation count, error text); `receipt.client` = the caller's own User-Agent forwarded by `_orch`; readable back via `recent_queries` GET `/queries`, narrowed to the principal's OWN receipts. mcp_server.py:126-127, 452-465
- `POLYMATH_MCP_PRINCIPALS_FILE` — ONE JSON file outside the repository, machine-local like `.env`; re-read when it changes so a revocation needs no fleet bounce. mcp_principals.py:12-13
- Request-scoped contextvars (`_CALLER_IS_LOCAL`, `_PRINCIPAL`, `_CALLER_AGENT`) — per request, not durable. mcp_server.py:79, 90-91, 673-675
- Server A itself writes no pipeline state: every tool is a thin, trimmed call into the orchestrator, so MCP can never bypass the pipeline's own gates. mcp_server.py:4-9

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_API_KEY` | `""` | set = the built-in OWNER (admin) bearer, passes the gate untouched; empty = 503 on every `/mcp` (fail closed) | mcp_server.py:59, 663-666, 676-678; mcp_principals.py:11 |
| `POLYMATH_MCP_PORT` | `8930` | listener port; also builds `_LOOPBACK_HOSTS` and `allowed_hosts` | mcp_server.py:58, 63-64, 77 |
| `POLYMATH_ORCH_URL` | `http://127.0.0.1:7200` | upstream orchestrator base for every tool call | mcp_server.py:57, 134-135 |
| `POLYMATH_MCP_PUBLIC_HOST` | `mcp.kingsleylab.xyz` | public Host plus `https://` origin allowed by `TransportSecuritySettings` | mcp_server.py:60, 63-71 |
| `POLYMATH_MCP_PRINCIPALS_FILE` | (no default shown) | the principals JSON store behind `_STORE = P.store_from_env(API_KEY)`; file change = live policy change | mcp_server.py:92; mcp_principals.py:12-13 |

## failure modes

1. Every `/mcp` call answers 503 "refusing to serve" -> `POLYMATH_MCP_API_KEY` empty (fail-closed V2) -> look at mcp_server.py:663-666; the open `/health` shows `"auth": "MISSING"` in that state mcp_server.py:646-649. Pre-V2 incident: the keyless public mirror answered tools/call to anyone (2026-09-02) mcp_server.py:21-23.
2. 401 `unauthorized` -> bearer missing the `Bearer ` prefix, or unknown/revoked/expired key -> mcp_server.py:667-672, 19-20; key lifecycle in mcp_principals.py:5-13.
3. Tool returns `{"error": "NO_PRINCIPAL: …", "status": 401}` -> the tool ran with no gate context (`who is NOBODY`, id `"prn_nobody"`) -> mcp_server.py:128-130, 89-90.
4. 429 `rate limit exceeded` with `Retry-After` -> principal over its `rate_per_minute` -> mcp_server.py:679-683; mcp_principals.py:9, 79.
5. 413 `request body too large` -> gated body over `2 * 1024 * 1024` -> mcp_server.py:687-690, 94.
6. 400 jsonrpc `-32700` "Parse error: nested too deeply" -> body nests past what the gate can judge; never passed on unjudged -> mcp_server.py:695-698.
7. 403 `tool_not_permitted` -> tool absent from `TOOL_POLICY` (default deny): `research_acquire`, `supplier_*`, `upload_document` are owner-only -> mcp_principals.py:54-56, 111-113; mcp_server.py:547-548, 570-572, 67.
8. 403 `insufficient_scope` / `corpus_not_allowed` -> principal lacks the action scope, or `corpus_id` not in its `corpus_ids`; a `friend`-profile principal has no `upload.text`/`history.read`/`admin` -> mcp_principals.py:114-118, 49-51, 66-67.
9. 403 `REMOTE_PATH_UPLOAD_DISABLED` -> `upload_document` from a remote or non-admin caller; refused before ANY filesystem access, so it is also not a file-existence oracle -> mcp_server.py:196-199, 80-83.
10. Tool result is `{"error": ..., "status": ...}` -> orchestrator returned >= 400; non-JSON detail silently becomes `r.text[:400]` -> mcp_server.py:136-141.
11. Silent-size answers: hits cut at 1400, evidence rows at 1200, `ask`/`polymath_answer` evidence at 600 and first 12 — always flagged `truncated: true` + `full_length`, but the full text never reaches the caller -> mcp_server.py:145-161, 326-339, 392-397, 442-446.
12. Deprecated `retrieve`/`ask` without a corpus: `corpus_id` is a required parameter; the V1 unscoped all-corpora path took 20 s and abstained where the scoped path answered in 3 s with 16 citations -> mcp_server.py:24-26, 287, 377.
13. `corpus_status` returns 404 `corpus … not found` -> no row matched `corpus_id` OR `name` (both are accepted); `semantic_readiness` is still attached -> mcp_server.py:269-281.
14. `adapter_result` returns 409 -> the run is still running or awaiting a step; fetch status instead -> mcp_server.py:533-538.

## invariants

- INVARIANT every `/mcp` request is bearer-authenticated; with no key configured the surface answers 503 instead of running open. mcp_server.py:18-23, 663-666
- INVARIANT the gate authenticates the bearer to ONE principal per request and authorizes every tools/call BEFORE the MCP layer sees it; a non-admin body is read ONCE, judged, replayed. mcp_server.py:86-88, 654-655
- INVARIANT no gate -> no principal -> NOBODY -> nothing leaves `_orch` (401). mcp_server.py:88-90, 128-130
- INVARIANT default deny: a tool with no policy in `TOOL_POLICY` is admin-only. mcp_principals.py:9-10, 54-56
- INVARIANT the raw bearer secret is never stored, logged or printed; only its sha256, and the `key_id` is loggable. mcp_principals.py:7-8, 101-102
- INVARIANT the owner key stays the trusted-local caller: `x-polymath-principal` is attached only for non-admin principals, on the loopback Server A -> orchestrator hop. mcp_server.py:131-133; mcp_principals.py:11, 39
- INVARIANT MCP can never bypass the pipeline's own gates: every tool is a thin, trimmed call to `127.0.0.1:7200`. mcp_server.py:4-9
- INVARIANT a cut text always says so: `truncated: true` + `full_length` (D-02); a hit that fits keeps exactly its old keys. mcp_server.py:146-147, 327-328
- INVARIANT `Decision.reason` is a stable machine code and never carries resource details. mcp_principals.py:89-90
- INVARIANT content belongs to one corpus: bytes already living in ANOTHER corpus are refused with 409 `CROSS_CORPUS_CONTENT_COLLISION`. mcp_server.py:194-196

## VERIFY

```verify
grep -Fq 'refusing to serve' orchestrator/orchestrator/mcp_server.py
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail closed)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'x-polymath-principal' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'tool_not_permitted' orchestrator/orchestrator/mcp_principals.py
grep -Eq '^BEARER_RE = re.compile' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'truncated' orchestrator/orchestrator/mcp_server.py)" -ge 3
! grep -Fq 'sqlite' orchestrator/orchestrator/mcp_principals.py
```
