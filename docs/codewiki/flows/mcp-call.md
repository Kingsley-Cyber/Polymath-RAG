# flow: mcp-call
An MCP tool call to Server A (HTTP :8930): the key check (principals), scope, the tool, the call into the orchestrator, the answer.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | MCP client POSTs a tools/call to the streamable-http app (`stateless_http=True`), port `8930` | orchestrator/orchestrator/mcp_server.py:59,671-672 [DERIVED] | JSON-RPC tools/call + bearer key -> gate chain | wrong port / no listener |
| 2 | KeyInPath (outermost layer): path `/k/<key>/mcp` matched by `_KEY_PATH` -> path+raw_path rewritten in place to `/mcp`, existing `authorization` headers stripped, `Bearer <key>` injected, so the access log never sees the key | orchestrator/orchestrator/mcp_server.py:641-644,651-660 [DERIVED] | `/k/<key>/mcp` -> `/mcp` + Authorization header | key shorter than 16 chars fails the regex |
| 3 | DNS-rebinding allowlist: `allowed_hosts` = `127.0.0.1:8930`, `localhost:8930`, `PUBLIC_HOST`, `PUBLIC_HOST:443`; origins include `https://claude.ai`, `https://claude.com` | orchestrator/orchestrator/mcp_server.py:64-75 [DERIVED] | Host/Origin headers -> pass to MCP app | other Host/Origin refused by the transport layer [INFERRED: allowlist is handed to `streamable_http_app`] |
| 4 | BearerGate: `API_KEY` empty -> 503 `MCP bearer key not configured...` (FAIL-CLOSED V2) | orchestrator/orchestrator/mcp_server.py:691-694 [DERIVED] | request -> 503 | server runs with no key configured |
| 5 | BearerGate authenticates: `Bearer ` prefix stripped, `_STORE.authenticate(...)` (principals file re-read when it changes) | orchestrator/orchestrator/mcp_server.py:695-700,96; orchestrator/orchestrator/mcp_principals.py:12-13 [DERIVED] | raw bearer -> `Principal` or None | None -> 401 `unauthorized` (unknown/revoked/expired key) |
| 6 | Rate limit: over the principal's `requests-per-minute` -> 429 | orchestrator/orchestrator/mcp_server.py:97,680-681; orchestrator/orchestrator/mcp_principals.py:79 [DERIVED] | principal -> allow/429 | 429 |
| 7 | `authorize()`: admin -> ALLOW; tool not in `TOOL_POLICY` -> 403 `tool_not_permitted`; scope miss -> 403 `insufficient_scope`. Non-admin request is read ONCE, judged, replayed (body cap `MAX_GATED_BODY = 2 * 1024 * 1024`) | orchestrator/orchestrator/mcp_principals.py:54-68,105-116; orchestrator/orchestrator/mcp_server.py:98,682-683 [DERIVED] | (Principal, tool, arguments) -> `Decision` | 403 tool_not_permitted / 403 insufficient_scope |
| 8 | Context bound: `_PRINCIPAL` (default `NOBODY` = `prn_nobody`), `_CALLER_AGENT` (caller User-Agent), `_CALLER_IS_LOCAL` (default False) | orchestrator/orchestrator/mcp_server.py:83-98 [DERIVED] | principal -> contextvars | lost context = NOBODY = refuses later |
| 9 | Locality decided: Host in `_LOOPBACK_HOSTS` AND none of `_EDGE_HEADERS` (`cf-connecting-ip`, `cf-ray`, `cdn-loop`, `x-forwarded-for`, `forwarded`) present | orchestrator/orchestrator/mcp_server.py:81-87,101-103 [DERIVED] | request headers -> bool | default NOT local: refuses instead of serving |
| 10 | Tool function runs; e.g. `polymath_search(query, corpus_id, max_evidence=12)` builds body `{query, corpus_id, limit, evidence: True}` -> `_orch("POST", "/retrieve", ...)` | orchestrator/orchestrator/mcp_server.py:406-411 [DERIVED] | tool args -> orchestrator HTTP body | corpus_id required on retrieve/ask |
| 11 | `upload_document` only: not (`_CALLER_IS_LOCAL` AND `is_admin`) -> 403 `REMOTE_PATH_UPLOAD_DISABLED`, returned BEFORE any filesystem access (no existence oracle) | orchestrator/orchestrator/mcp_server.py:201-205 [DERIVED] | (path, corpus_id) -> 403 dict or file upload | 403 for every remote/non-admin caller |
| 12 | `_orch` guard: `who is NOBODY` -> `{"error": "NO_PRINCIPAL: ...", "status": 401}`; nothing leaves the process | orchestrator/orchestrator/mcp_server.py:132-134 [DERIVED] | contextvar -> refusal | tool ran with no gate context |
| 13 | `_orch` forwards trusted context: `User-Agent` = `_CALLER_AGENT`; non-admin also gets `x-polymath-principal: <principal_id>` (loopback-only trusted header) | orchestrator/orchestrator/mcp_server.py:130-137; orchestrator/orchestrator/mcp_principals.py:39 [DERIVED] | principal -> orchestrator headers | header only meaningful on loopback |
| 14 | httpx request to `POLYMATH_ORCH_URL`; timeout default 180 s (uploads 600 s) | orchestrator/orchestrator/mcp_server.py:58,128-142,209,234 [DERIVED] | method+path+json -> orchestrator response | timeout / connection refused |
| 15 | Orchestrator status >= 400 -> `{"error": detail (JSON detail else text[:400]), "status": code}` | orchestrator/orchestrator/mcp_server.py:143-148 [DERIVED] | HTTP error -> error dict | surfaced as tool result |
| 16 | Orchestrator stamps ownership from the forwarded principal: `adapter_runs.owner_principal_id`, query receipts (`client` = User-Agent) | orchestrator/orchestrator/mcp_server.py:91-92,130-131,495-496; orchestrator/orchestrator/mcp_principals.py:16-18 [DERIVED] | header -> persisted owner/receipts | none on this hop |
| 17 | Response trimmed: contract rows cut at 1200 chars (`_trim_rows`), hits at 1400 (`_trim_hit`), chat evidence at 600 + first 12; a cut always carries `truncated: true` + `full_length` | orchestrator/orchestrator/mcp_server.py:149-168,330-343,397-401,447-450 [DERIVED] | full rows -> slim rows | truncation is marked, never silent |
| 18 | Non-admin result filtering: `list_corpora` keeps only `who.corpus_ids`; `adapter_list` keeps only `who.adapter_ids` | orchestrator/orchestrator/mcp_server.py:176-181,482-485 [DERIVED] | full list -> filtered list | permitted corpora silently absent |
| 19 | Answer dict returned to the MCP client, e.g. `{evidence_rows, evidence_contract, graph_facts}` | orchestrator/orchestrator/mcp_server.py:413-416 [DERIVED] | slim dict -> client | verdict=insufficient_evidence on polymath_answer |

## state written

| state | what | anchor |
|---|---|---|
| `adapter_runs.owner_principal_id` | run ownership persisted by the adapter runtime from the trusted principal context the gate forwards | orchestrator/orchestrator/mcp_server.py:495-496; orchestrator/orchestrator/mcp_principals.py:16-18 [DERIVED] |
| query receipts (QUERY-RECEIPTS-V1) | every served `/chat`, `/ask`, `/retrieve`: `wall_ms`, mode, status ok/abstained/error, citation count, error text; a principal's context narrows reads to its OWN receipts | orchestrator/orchestrator/mcp_server.py:91-92,459-469 [DERIVED] |
| receipt `client` | the caller's own User-Agent (the SOFTWARE acting, never authorization) | orchestrator/orchestrator/mcp_server.py:130-131; orchestrator/orchestrator/mcp_principals.py:17-18 [DERIVED] |
| principals JSON file | not written on this path, only re-read when it changes (revocation needs no bounce) | orchestrator/orchestrator/mcp_principals.py:12-13 [DERIVED] |
| Server A durable writes | none: every tool is a thin, trimmed call to the orchestrator, so all writes happen orchestrator-side | orchestrator/orchestrator/mcp_server.py:4-6 [INFERRED: thin-call architecture, no write code on this surface] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PORT` | `8930` | listener port | orchestrator/orchestrator/mcp_server.py:59 |
| `POLYMATH_ORCH_URL` | `http://127.0.0.1:7200` | where every tool forwards | orchestrator/orchestrator/mcp_server.py:58 |
| `POLYMATH_MCP_API_KEY` | `""` | OWNER (admin) bearer; empty -> 503 on /mcp, fail closed | orchestrator/orchestrator/mcp_server.py:60,691-694 |
| `POLYMATH_MCP_PUBLIC_HOST` | `mcp.kingsleylab.xyz` | public host in allowed_hosts/origins | orchestrator/orchestrator/mcp_server.py:61,64-75 |
| `POLYMATH_MCP_PRINCIPALS_FILE` | not shown | JSON principals store, re-read on change | orchestrator/orchestrator/mcp_principals.py:12-13; orchestrator/orchestrator/mcp_server.py:20 |

## failure modes

1. Every /mcp call -> 503 `MCP bearer key not configured (POLYMATH_MCP_API_KEY); refusing to serve` -> key unset; fail-closed V2 (V1 had booted open and answered anyone). `/health` shows `"auth": "MISSING"`. -> orchestrator/orchestrator/mcp_server.py:22-24,674-677,691-694 [DERIVED]
2. 401 `unauthorized` -> bearer unknown/revoked/expired; `_STORE.authenticate` returned None. Revoke via the principals file (re-read live). -> orchestrator/orchestrator/mcp_server.py:695-700; orchestrator/orchestrator/mcp_principals.py:12-13 [DERIVED]
3. 403 `REMOTE_PATH_UPLOAD_DISABLED: upload_document reads a path on the Polymath HOST...` -> caller not loopback-and-admin; check runs before ANY filesystem access. -> orchestrator/orchestrator/mcp_server.py:84-87,201-205 [DERIVED]
4. 403 `tool_not_permitted` -> tool absent from `TOOL_POLICY` (admin-only by default deny). -> orchestrator/orchestrator/mcp_principals.py:54,111-113 [DERIVED]
5. 403 `insufficient_scope` -> principal lacks the tool's action scope. -> orchestrator/orchestrator/mcp_principals.py:114-116 [DERIVED]
6. 429 -> principal over its `rate_per_minute`. -> orchestrator/orchestrator/mcp_server.py:680-681; orchestrator/orchestrator/mcp_principals.py:79 [DERIVED]
7. Tool result `{"error": "NO_PRINCIPAL: this call carries no authenticated principal (fail closed)", "status": 401}` -> tool executed with no gate context (`who is NOBODY`). -> orchestrator/orchestrator/mcp_server.py:133-134 [DERIVED]
8. Tool result `{"error": <detail>, "status": <code>}` -> orchestrator answered >= 400; detail is the JSON detail else `r.text[:400]`. -> orchestrator/orchestrator/mcp_server.py:143-148 [DERIVED]
9. Upload refused -> 409 `CROSS_CORPUS_CONTENT_COLLISION` -> same content already lives in another corpus. -> orchestrator/orchestrator/mcp_server.py:197-199 [DERIVED]
10. Silent filter: a non-admin sees fewer/no corpora in `list_corpora` (kept only if in `who.corpus_ids`) — a "missing" corpus may be merely unpermitted. -> orchestrator/orchestrator/mcp_server.py:176-181 [DERIVED]
11. Marked truncation: rows cut at 1200, hits at 1400, chat evidence at 600 chars (first 12); `truncated: true` + `full_length` say so; a hit that fits keeps exactly its old keys. -> orchestrator/orchestrator/mcp_server.py:150-151,330-343,397-401 [DERIVED]
12. `corpus_status` -> 404 `corpus ... not found` -> corpus_id matched neither `corpus_id` nor `name` (`semantic_readiness` still returned). -> orchestrator/orchestrator/mcp_server.py:276-284 [DERIVED]
13. `polymath_answer` -> `verdict=insufficient_evidence` -> the corpus cannot support the question; relay it, do not fill the gap. -> orchestrator/orchestrator/mcp_server.py:439-441 [DERIVED]

## invariants

- INVARIANT: every tool is a thin, trimmed call to the orchestrator API — MCP can never bypass the pipeline's own gates. — orchestrator/orchestrator/mcp_server.py:4-6 [DERIVED]
- INVARIANT: no key configured -> the server refuses (503) instead of running open. — orchestrator/orchestrator/mcp_server.py:22-24,691-694 [DERIVED]
- INVARIANT: no gate -> no principal -> NOBODY (`prn_nobody`) -> `_orch` answers 401 before anything leaves. — orchestrator/orchestrator/mcp_server.py:92-94,133-134 [DERIVED]
- INVARIANT: default deny — a tool with no policy is admin-only. — orchestrator/orchestrator/mcp_principals.py:9-10,111-113 [DERIVED]
- INVARIANT: the pre-existing owner key is the built-in OWNER principal (admin); Hermes on loopback is unchanged. — orchestrator/orchestrator/mcp_principals.py:11 [DERIVED]
- INVARIANT: a raw bearer is `pmk_<key_id>_<secret>`; the secret is never stored, logged or printed — only its sha256. — orchestrator/orchestrator/mcp_principals.py:6-8,37,101-102 [DERIVED]
- INVARIANT: key-in-path is rewritten in place — the access log and every layer below see `/mcp`, never the key. — orchestrator/orchestrator/mcp_server.py:641-643,656-659 [DERIVED]
- INVARIANT: retrieve/ask REQUIRE `corpus_id` — the unscoped all-corpora path is gone (20 s abstain vs 3 s with 16 citations). — orchestrator/orchestrator/mcp_server.py:25-27 [DERIVED]
- INVARIANT: a cut text/row always says so — `truncated: true` + `full_length`; a hit that fits keeps exactly its old keys (D-02). — orchestrator/orchestrator/mcp_server.py:150-151,163-164,331-332,339-341 [DERIVED]
- INVARIANT: `agent_identity`/User-Agent is the SOFTWARE acting, never authorization; non-admin identity travels only via the loopback-only `x-polymath-principal` header. — orchestrator/orchestrator/mcp_principals.py:17-18,39; orchestrator/orchestrator/mcp_server.py:130-137 [DERIVED]
- INVARIANT: locality defaults to NOT local — a lost context refuses (fail closed) instead of serving. — orchestrator/orchestrator/mcp_server.py:77-83,101-103 [DERIVED]

## VERIFY

```verify
grep -Fq 'POLYMATH_MCP_API_KEY' orchestrator/orchestrator/mcp_server.py
grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail closed)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'class KeyInPath' orchestrator/orchestrator/mcp_server.py
grep -Fq 'x-polymath-principal' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'tool_not_permitted' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'truncated' orchestrator/orchestrator/mcp_server.py)" -ge 4
```
