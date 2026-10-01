# flow: mcp-call

An MCP tool call to Server A, the ONE public door (streamable-http on `POLYMATH_MCP_PORT`, default 8930). Every tool is a thin, trimmed call to the orchestrator API on `127.0.0.1:7200`, so MCP can never bypass the pipeline's own gates — orchestrator/orchestrator/mcp_server.py:4-9 [DERIVED]. Server A also serves the loopback listener for Hermes and the public hostname through the tunnel — orchestrator/orchestrator/mcp_server.py:84-86 [DERIVED].

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Request reaches `/mcp`; transport-security allowlist: `Host` must be in `_ALLOWED_HOSTS` (loopback + `PUBLIC_HOST`), `Origin` in `allowed_origins` — the DNS-rebinding gate ("the v33 gotcha") | orchestrator/orchestrator/mcp_server.py:66,71-82 [DERIVED] | HTTP request (Host, Origin) -> admitted request | non-allowlisted Host/Origin refused |
| 2 | Key in path: `/k/<key>/mcp` -> KeyInPath turns the URL key into the `Authorization: Bearer` header (claude.ai's connector cannot send a header) | orchestrator/orchestrator/mcp_server.py:24-28 [DERIVED] | URL path key -> Bearer header | — |
| 3 | Fail-closed key gate: with no key configured the server answers 503 on `/mcp` instead of running open (V2) | orchestrator/orchestrator/mcp_server.py:28-30,67 [DERIVED] | empty `POLYMATH_MCP_API_KEY` -> 503 | 503 on every call until a key exists |
| 4 | Bearer authenticated to ONE principal per request, before the MCP layer sees the tools/call: `POLYMATH_MCP_API_KEY` = built-in OWNER (admin, `prn_owner`); any other bearer `pmk_<key_id>_<secret>` is matched in `_STORE = P.store_from_env(API_KEY)`, backed by the `POLYMATH_MCP_PRINCIPALS_FILE` JSON (re-read when it changes) | orchestrator/orchestrator/mcp_server.py:97-103; orchestrator/orchestrator/mcp_principals.py:5-13,37-38 [DERIVED] | raw bearer -> `P.Principal` | 401 unknown or revoked key |
| 5 | Rate limit: `_LIMITER = P.RateLimiter()` enforces the principal's requests-per-minute | orchestrator/orchestrator/mcp_server.py:104 [DERIVED] | principal -> allowed / throttled | 429 over its rate |
| 6 | tools/call authorized against `TOOL_POLICY` (tool -> any-of action scopes + resource kind: `corpus`, `corpus_filter`, `adapter_filter`, `start`, `run`, `write_corpus`, `none`); a tool NOT in the policy is admin-only | orchestrator/orchestrator/mcp_server.py:29-30; orchestrator/orchestrator/mcp_principals.py:57-71 [DERIVED] | (tool, principal) -> permit / deny | 403 not permitted |
| 7 | Per-request context set: `_PRINCIPAL` (default `NOBODY`), `_CALLER_AGENT` (caller's User-Agent), `_CALLER_IS_LOCAL` = Host in `_LOOPBACK_HOSTS` AND none of `_EDGE_HEADERS` present; default is NOT local, so a lost context refuses | orchestrator/orchestrator/mcp_server.py:88-105,108-110 [DERIVED] | request headers -> contextvars | fail closed on missing context |
| 8 | MCP dispatch; `_ListedMCPServer.list_tools` filters out `MR.HIDDEN_TOOLS_A`, so deprecated tools stay callable but are never listed | orchestrator/orchestrator/mcp_server.py:113-118 [DERIVED] | tools/call -> Python tool fn | — |
| 9 | Tool argument validation: `MR.normalize_mode` (query tools; modes FAST \| HYBRID \| GRAPH \| WILDCARD \| GNN), `MR.normalize_reasoning` (`polymath_answer`), `MR.normalize_depth` (`polymath_deep_research`) | orchestrator/orchestrator/mcp_server.py:443-445,477-479,516-518 [DERIVED] | mode/reasoning/depth string -> canonical value | `MR.mode_error(mode)`; 422 with `styles`; 422 with `depths` |
| 10 | Ingest gates: `upload_document` requires `_CALLER_IS_LOCAL` AND admin BEFORE any filesystem access ("no existence oracle either"); both upload tools check the extension against `UPLOAD_EXTENSIONS` | orchestrator/orchestrator/mcp_server.py:69,240-250,270-272 [DERIVED] | path / `source_name` -> checked | 403 `REMOTE_PATH_UPLOAD_DISABLED`; 404 file not found; 422 unsupported extension |
| 11 | Orchestrator call prep in `_orch` / `_orch_events`: `NOBODY` -> `{"error": "NO_PRINCIPAL: ...", "status": 401}`; headers carry `User-Agent` = caller agent; a non-admin gets `P.PRINCIPAL_HEADER` (`x-polymath-principal`) | orchestrator/orchestrator/mcp_server.py:142-150,163-171; orchestrator/orchestrator/mcp_principals.py:39 [DERIVED] | contextvars -> trusted loopback headers | 401 `NO_PRINCIPAL` (fail closed) |
| 12 | Loopback HTTP to `ORCH` (default `http://127.0.0.1:7200`): `_orch` timeout 180; `polymath_compare` 600; uploads 600; `_orch_events` 1800 with `connect=10.0` | orchestrator/orchestrator/mcp_server.py:65,142-152,166,173-174,248-251,501 [DERIVED] | route path + JSON body -> orchestrator JSON | network error, timeout, status >= 400 |
| 13 | Error mapping: status >= 400 -> `{"error": detail, "status": N}`; `detail` from the JSON `detail` field else first 400 chars of the body | orchestrator/orchestrator/mcp_server.py:153-159,176-182 [DERIVED] | 4xx/5xx response -> error dict | every orchestrator refusal surfaces here (e.g. 409 `CROSS_CORPUS_CONTENT_COLLISION`) |
| 14 | Orchestrator-side stamps: the forwarded principal context becomes `adapter_runs.owner_principal_id` on `adapter_start`; query receipts (QUERY-RECEIPTS-V1) record the principal and `client` (the User-Agent) | orchestrator/orchestrator/mcp_server.py:97-99,144-145,544,571-572; orchestrator/orchestrator/mcp_principals.py:16-18 [DERIVED] | principal context -> persisted owner + receipt | — |
| 15 | In-tool result filtering for non-admins: `list_corpora` keeps only `who.corpus_ids`; `adapter_list` only `who.adapter_ids` | orchestrator/orchestrator/mcp_server.py:215-217,556-558 [DERIVED] | full list -> principal-scoped list | silent: out-of-scope items just disappear |
| 16 | `polymath_deep_research` only: POST `/research/deep` as SSE, frames collected by `_orch_events`; a refusal before the stream starts comes back as one `("error", {...})` frame; shaped by `MR.shape_deep` | orchestrator/orchestrator/mcp_server.py:163-165,176-185,519-520 [DERIVED] | `MR.deep_body(...)` -> frames -> result | single error frame instead of a stream |
| 17 | Answer shaping/trimming: `MR.shape_search` / `shape_explore` / `shape_compare` / `shape_models`; `_trim_hit` cuts text at 1400 chars (`truncated: true` + `full_length`); `MR.trim_rows` cuts `text`/`text_clean` at 1200 (D-02); `ask`/`polymath_answer` trim `evidence`/`chunks`/`bundle` to the first 12 items at 600 chars | orchestrator/orchestrator/mcp_server.py:188-204,369-371,425-431,483-487 [DERIVED] | orchestrator JSON -> slim tools/call result | silent data loss past the caps |

## state written

- `adapter_runs.owner_principal_id` — persisted and enforced by the adapter runtime from the trusted principal context the gate forwards (run ownership is the runtime's, not the tool's) — orchestrator/orchestrator/mcp_server.py:571-572; orchestrator/orchestrator/mcp_principals.py:16-18 [DERIVED]
- Query receipts (QUERY-RECEIPTS-V1) — the principal stamps what it creates; receipt `client` = the caller's User-Agent; read back via `recent_queries` (GET `/queries`), where a principal's context narrows results to its OWN receipts — orchestrator/orchestrator/mcp_server.py:97-99,144-145,532-544 [DERIVED]
- Ingestion runs — POST `/upload` returns a content-addressed `run_id`; the same bytes return the existing run with `already_exists` true — orchestrator/orchestrator/mcp_server.py:235-251,265-286 [DERIVED]
- `POLYMATH_MCP_PRINCIPALS_FILE` — one JSON file outside the repository; READ and re-read when it changes (revocation needs no fleet bounce); this flow never writes it — orchestrator/orchestrator/mcp_principals.py:12-13 [DERIVED]
- No direct Postgres/Qdrant writes on this path — every tool is "a thin, trimmed call to the orchestrator API", so persistence stays behind the pipeline's gates — orchestrator/orchestrator/mcp_server.py:5-6 [INFERRED: stated design; no store clients appear in this file]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PORT` | `8930` | listener port; also composed into `_ALLOWED_HOSTS` and `_LOOPBACK_HOSTS` | orchestrator/orchestrator/mcp_server.py:66,71-72,88 |
| `POLYMATH_MCP_API_KEY` | `""` | OWNER/admin bearer; empty -> 503 fail-closed on `/mcp`; seeds `_STORE` | orchestrator/orchestrator/mcp_server.py:67,28-30,103 |
| `POLYMATH_ORCH_URL` | `http://127.0.0.1:7200` | base URL of every orchestrator call | orchestrator/orchestrator/mcp_server.py:65 |
| `POLYMATH_MCP_PUBLIC_HOST` | `mcp.kingsleylab.xyz` | public Host entries in the allowlist and `allowed_origins` | orchestrator/orchestrator/mcp_server.py:68,71-82 |
| `POLYMATH_MCP_PRINCIPALS_FILE` | not shown | the JSON principal store, re-read on change | orchestrator/orchestrator/mcp_server.py:26; orchestrator/orchestrator/mcp_principals.py:12-13 |

## failure modes

1. Every `/mcp` call returns 503 -> no `POLYMATH_MCP_API_KEY` configured; V2 fails closed instead of running open -> orchestrator/orchestrator/mcp_server.py:28-30,67.
2. 401 -> bearer unknown or revoked (matches no principal key) -> orchestrator/orchestrator/mcp_server.py:30; orchestrator/orchestrator/mcp_principals.py:5-8.
3. 403 not permitted -> tool denied: no matching action scope, resource (corpus/adapter/run) not allowed, or an admin-only tool called by a principal -> orchestrator/orchestrator/mcp_server.py:30; orchestrator/orchestrator/mcp_principals.py:9-10,57-58.
4. 429 -> principal over its requests-per-minute (`_LIMITER = P.RateLimiter()`) -> orchestrator/orchestrator/mcp_server.py:30,104.
5. `{"error": "NO_PRINCIPAL: ...", "status": 401}` -> `_orch`/`_orch_events` ran under the `NOBODY` sentinel: no gate ran for the call (lost context) -> orchestrator/orchestrator/mcp_server.py:100-101,146-147,167-168.
6. 403 `REMOTE_PATH_UPLOAD_DISABLED` -> `upload_document` from a caller that is not loopback+admin; refused before ANY filesystem access -> orchestrator/orchestrator/mcp_server.py:91-94,240-241.
7. 404 `file not found` / 422 `unsupported extension` / 422 `source_name needs one of ...` -> local pre-checks in `upload_document` / `upload_text` -> orchestrator/orchestrator/mcp_server.py:242-247,270-272.
8. 409 `CROSS_CORPUS_CONTENT_COLLISION` -> same content bytes already ingested into ANOTHER corpus (content belongs to one corpus) -> orchestrator/orchestrator/mcp_server.py:236-238.
9. `MR.mode_error(mode)` / 422 `unknown reasoning style` (with `styles`) / 422 `unknown depth` (with `depths`) -> normalization rejected the argument -> orchestrator/orchestrator/mcp_server.py:443-445,477-479,516-518.
10. Error dict `{"error": detail, "status": N}` -> any orchestrator route answered >= 400; `detail` is the JSON `detail` or the first 400 chars of the body -> orchestrator/orchestrator/mcp_server.py:153-159.
11. Deep research returns a single error frame -> refusal arrived before the SSE stream started -> orchestrator/orchestrator/mcp_server.py:181-185.
12. `research_acquire` / `supplier_*` called with a principal key -> owner-only by design (not in `TOOL_POLICY` on purpose; the orchestrator refuses a principal too) -> orchestrator/orchestrator/mcp_server.py:626-627,649-651; orchestrator/orchestrator/mcp_principals.py:57-58.
13. `corpus_status` 404 `corpus ... not found` -> `corpus_id` matched neither `corpus_id` nor `name` in `/corpora` -> orchestrator/orchestrator/mcp_server.py:313-322.
14. SILENT trimming -> `_trim_hit` cuts at 1400 chars (marked `truncated: true` + `full_length`), `MR.trim_rows` at 1200, but `ask`/`polymath_answer` keep only the FIRST 12 items of `evidence`/`chunks`/`bundle` at 600 chars with no overflow marker -> orchestrator/orchestrator/mcp_server.py:188-204,369-371,425-431,483-487.

## invariants

- INVARIANT fail-closed: with no key configured, `/mcp` answers 503 — never open — orchestrator/orchestrator/mcp_server.py:28-30.
- INVARIANT no principal, no call: `_orch` refuses under `NOBODY` before any request leaves — orchestrator/orchestrator/mcp_server.py:100-101,146-147.
- INVARIANT `x-polymath-principal` is trusted loopback-only context (Server A -> orchestrator), sent only for non-admin principals; the owner key stays the legacy/trusted-local caller — orchestrator/orchestrator/mcp_server.py:149-150; orchestrator/orchestrator/mcp_principals.py:11,39.
- INVARIANT default deny: a tool absent from `TOOL_POLICY` is admin-only — orchestrator/orchestrator/mcp_principals.py:57-58.
- INVARIANT a non-admin principal sees only its `corpus_ids` (corpora) and `adapter_ids` (adapters) — orchestrator/orchestrator/mcp_server.py:215-217,556-558.
- INVARIANT `agent_identity` and a receipt's `client` name the SOFTWARE acting and never carry authorization — orchestrator/orchestrator/mcp_principals.py:16-18.
- INVARIANT a cut hit always says so: `truncated: true` + `full_length`; a hit that fits keeps exactly its old keys — orchestrator/orchestrator/mcp_server.py:188-204.
- INVARIANT every query tool REQUIRES `corpus_id` (V2 scope fix; the unscoped path took 20 s and abstained where the scoped path answered in 3 s with 16 citations) — orchestrator/orchestrator/mcp_server.py:31-33.

## VERIFY

```verify
grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail closed)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'REMOTE_PATH_UPLOAD_DISABLED' orchestrator/orchestrator/mcp_server.py
grep -Fq 'http://127.0.0.1:7200' orchestrator/orchestrator/mcp_server.py
grep -Fq 'cf-connecting-ip' orchestrator/orchestrator/mcp_server.py
grep -Fq 'x-polymath-principal' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'polymath_mcp_principals.v1' orchestrator/orchestrator/mcp_principals.py
test "$(grep -c -F 'KNOWLEDGE_SEARCH' orchestrator/orchestrator/mcp_principals.py)" -ge 4
```
