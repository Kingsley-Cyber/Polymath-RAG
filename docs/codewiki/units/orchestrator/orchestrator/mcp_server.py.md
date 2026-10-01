# unit: orchestrator/orchestrator/mcp_server.py
anchor: orchestrator/orchestrator/mcp_server.py:1-846

## purpose
POLYMATH-MCP-V2: the v4 MCP server (streamable-http) that lets an agent (Hermes, the claude.ai connector) drive the whole document lifecycle — upload → status until queryable → ask — plus governed adapter research and owner-only supplier tools. Every tool is a thin, trimmed call to the orchestrator API on `http://127.0.0.1:7200`, so MCP cannot bypass the pipeline's gates. orchestrator/orchestrator/mcp_server.py:1-31,759-764 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| list_corpora | mcp tool | () -> dict | :171-179 | — |
| list_documents | mcp tool | (corpus_id) -> dict | :183-187 | — |
| upload_document | mcp tool | (path, corpus_id) -> dict | :193-222 | — |
| upload_text | mcp tool | (text, corpus_id, source_name="agent_upload.md") -> dict | :226-247 | — |
| document_status | mcp tool | (corpus_id, source_name?, run_id?) -> dict | :253-265 | — |
| corpus_status | mcp tool | (corpus_id) -> dict | :269-285 | — |
| retrieve | mcp tool (DEPRECATED) | (query, corpus_id, mode="HYBRID", limit=10, latent?, explore=False) -> dict | :291-319 | — |
| capabilities | mcp tool | () -> dict | :323-327 | — |
| compile_plan | mcp tool (DEPRECATED) | (signal, corpus_id, limit=24, explore=True, communities?) -> dict | :347-361 | — |
| retrieve_evidence | mcp tool (DEPRECATED) | (query, corpus_id, limit=12, explore=False) -> dict | :365-377 | — |
| ask | mcp tool (DEPRECATED) | (question, corpus_id, mode="HYBRID", latent?, evidence=False) -> dict | :381-402 | — |
| polymath_search | mcp tool | (query, corpus_id, max_evidence=12) -> dict | :407-416 | — |
| polymath_explore | mcp tool | (query, corpus_id, corpus_explorer=True, mode="HYBRID") -> dict | :420-430 | — |
| polymath_answer | mcp tool | (question, corpus_id, mode="HYBRID", latent?) -> dict | :434-451 | — |
| recent_queries | mcp tool | (corpus_id, limit=20, since_h=24.0, kind?) -> dict | :457-469 | — |
| adapter_list | mcp tool | () -> dict | :476-485 | — |
| adapter_start | mcp tool | (adapter_id, input, request_options?) -> dict | :489-497 | — |
| adapter_next | mcp tool | (run_id) -> dict | :501-512 | — |
| adapter_submit | mcp tool | (run_id, step_id, payload, agent_identity="connected-agent", model?, kind?) -> dict | :516-528 | — |
| adapter_status | mcp tool | (run_id) -> dict | :532-534 | — |
| adapter_result | mcp tool | (run_id) -> dict | :538-542 | — |
| adapter_cancel | mcp tool | (run_id) -> dict | :546-548 | — |
| research_acquire | mcp tool (owner key only) | (run_id, operation, target, site, search_intent_id?, limit?) -> dict | :554-571 | — |
| supplier_search | mcp tool (owner key only) | (query, source, limit) -> dict | :578-586 | — |
| supplier_product | mcp tool (owner key only) | (product_id) -> dict | :590-595 | — |
| supplier_freight | mcp tool (owner key only) | (variant_id, country, quantity, from_country) -> dict | :599-604 | — |
| supplier_warehouses | mcp tool (owner key only) | () -> dict | :608-611 | — |
| run_governed_research | mcp prompt | (adapter_id?, seed?) -> dict | :635-637 | — |
| KeyInPath | class | methods `__init__`, `__call__` | :647-660 | — |
| build_app | def | () -> ASGI app (FastMCP streamable-http + fail-closed bearer gate) | :663-822 | — |
| main | def | () -> None (entrypoint) | :836-841 | — |
| _orch | helper | (method, path, **kw) -> Any | :128-146 | internal |
| _trim_hit | helper | (h, max_chars=1400) -> dict | :149-165 | internal |
| _trim_rows | helper | (rows) -> list | :330-343 | internal |
| _is_local_caller | helper | (headers) -> bool | :101-103 | internal |

## contracts
- `_orch(method, path, **kw)` — pre: `_PRINCIPAL.get()` is not `NOBODY`, else returns `{"error": "NO_PRINCIPAL: ...", "status": 401}`; non-admin principals get header `P.PRINCIPAL_HEADER` = `principal_id` (:130-137). in: `timeout` default `180` (:129). out: parsed JSON, or `{"error": detail, "status": r.status_code}` for any `>= 400` (:140-145). orchestrator/orchestrator/mcp_server.py:128-146 [DERIVED]
- `upload_document(path, corpus_id)` — pre: `_CALLER_IS_LOCAL.get()` AND `_PRINCIPAL.get().is_admin`, else `REMOTE_PATH_UPLOAD_DISABLED` (status 403) returned BEFORE any filesystem access (:201-202); file exists else 404 (:204-205); suffix in `UPLOAD_EXTENSIONS` else 422 (:206-208). post: response JSON plus `out["next"]` polling hint (:219-220). orchestrator/orchestrator/mcp_server.py:193-222 [DERIVED]
- `upload_text(text, corpus_id, source_name)` — pre: `source_name` suffix in `UPLOAD_EXTENSIONS` else `{"error": "source_name needs one of ...", "status": 422}` (:231-232). post: same `out["next"]` hint (:245-246). orchestrator/orchestrator/mcp_server.py:226-247 [DERIVED]
- `polymath_search(query, corpus_id, max_evidence=12)` — POST `/retrieve` with `{"query", "corpus_id", "limit": max_evidence, "evidence": True}`; out: `{"evidence_rows": _trim_rows(...), "evidence_contract": ..., "graph_facts": len(...)}` (:410-416). q0-only: no planning, no Corpus Explore, no answer (:408-409). orchestrator/orchestrator/mcp_server.py:407-416 [DERIVED]
- `polymath_explore(query, corpus_id, corpus_explorer=True, mode="HYBRID")` — POST `/chat/evidence`; returns orchestrator JSON unchanged (:427-430); EvidencePacket with NO Polymath answer, `synthesis_performed=false` (:422-424). orchestrator/orchestrator/mcp_server.py:420-430 [DERIVED]
- `polymath_answer(question, corpus_id, mode="HYBRID", latent?)` — POST `/chat`; post: `evidence`/`chunks`/`bundle` lists cut to first 12 items, each `_trim_hit(h, 600)` (:446-450); `verdict=insufficient_evidence` must be relayed, not filled (:437-438). orchestrator/orchestrator/mcp_server.py:434-451 [DERIVED]
- `adapter_start(adapter_id, input, request_options?)` — pre: `input` satisfies the adapter `input_schema`; `corpus_ids` REQUIRED in `request_options` for a non-admin key; `idempotency_key` makes retries not start a second run (:490-493). orchestrator/orchestrator/mcp_server.py:489-497 [DERIVED]
- `adapter_result(run_id)` — 409 while the run is still running or awaiting a step (:539). orchestrator/orchestrator/mcp_server.py:538-542 [DERIVED]
- `recent_queries(corpus_id, limit=20, since_h=24.0, kind?)` — pre: `corpus_id` non-empty, else `raise ValueError("corpus_id is required")` (:464-465); a principal's context narrows results to its OWN receipts (:469). orchestrator/orchestrator/mcp_server.py:457-469 [DERIVED]
- `build_app()` — ASGI app: FastMCP streamable-http + FAIL-CLOSED bearer gate (:663-664); no key configured ⇒ 503 on `/mcp` instead of running open (:22-24). orchestrator/orchestrator/mcp_server.py:663-822 [DERIVED]
- `KeyInPath` — turns a key in the URL (`/k/<key>/mcp`) into the same `Authorization: Bearer` header, for claude.ai's connector that cannot send a header (:18-19, :647-660). orchestrator/orchestrator/mcp_server.py:647-660 [DERIVED]
- `_trim_hit` / `_trim_rows` — D-02: a cut hit/row carries `truncated: true` + `full_length`; a hit that fits keeps exactly its old keys (:150-151, :331-332). orchestrator/orchestrator/mcp_server.py:149-165,330-343 [DERIVED]

## effect surface
- Network: `httpx.AsyncClient` to `ORCH` at :138 (`_orch`, timeout default `180`), :209 (`upload_document`, timeout `600`), :234 (`upload_text`, timeout `600`). orchestrator/orchestrator/mcp_server.py:129,138,209,234 [DERIVED]
- Files: reads a caller-supplied local path `p.open("rb")` for upload, gated to local+admin callers (:210, :201-202). orchestrator/orchestrator/mcp_server.py:209-212 [DERIVED]
- Env: `POLYMATH_ORCH_URL` = `'http://127.0.0.1:7200'` (:58), `POLYMATH_MCP_PORT` = `'8930'` (:59), `POLYMATH_MCP_API_KEY` = `''` (:60), `POLYMATH_MCP_PUBLIC_HOST` = `'mcp.kingsleylab.xyz'` (:61). orchestrator/orchestrator/mcp_server.py:58-61 [DERIVED]
- Postgres tables: none read/written in this unit (FACTS `tables_read`/`tables_written` empty); persistence lives behind the orchestrator API. [DERIVED]
- Qdrant collections: none; FACTS "collections" are `contextvars.ContextVar` names (`polymath_mcp_caller_is_local`, `polymath_mcp_principal`, `polymath_mcp_caller_agent`). orchestrator/orchestrator/mcp_server.py:83-95 [DERIVED]
- Imports from other units: `orchestrator.mcp_principals` (as `P`), `polymath_shared.adapter.harness_guide` (as `HG`). orchestrator/orchestrator/mcp_server.py:53-54 [DERIVED]

## invariants
- INVARIANT: upload path tools require `_CALLER_IS_LOCAL.get()` AND `_PRINCIPAL.get().is_admin` — :201 [DERIVED]
  fails-if: a remote or non-admin caller could make the server read (existence-oracle) host filesystem paths.
- INVARIANT: `_PRINCIPAL == NOBODY` ⇒ `_orch` returns status `401`, sends nothing upstream — :133-134 [DERIVED]
  fails-if: an unauthenticated call would reach the trusted loopback orchestrator under the sentinel principal.
- INVARIANT: `P.PRINCIPAL_HEADER` is attached iff `not who.is_admin` — :136-137 [DERIVED]
  fails-if: orchestrator would mis-attribute run ownership / query receipts between owner and principals.
- INVARIANT: `MAX_GATED_BODY == 2 * 1024 * 1024` (2 MiB) — :98 [DERIVED]
  fails-if: oversized gated requests bypass or break the bearer gate in `build_app`.
- INVARIANT: `_is_local_caller` ⇔ host in `_LOOPBACK_HOSTS` AND none of `_EDGE_HEADERS` present — :101-103 [DERIVED]
  fails-if: a tunnel-forwarded request with a spoofed loopback Host would count as local; default is already False (fail closed, :80-83).
- INVARIANT: text-cut thresholds are `_trim_hit` `1400`, `_trim_rows` `1200`, ask/answer evidence `600`, adapter_next evidence `60 rows x 600 chars` — :149, :336-338, :400/:450, :508 [DERIVED]
  fails-if: MCP payloads exceed the client/context budget or D-02 `truncated`/`full_length` markers disagree with actual lengths.
- INVARIANT: `ask`/`polymath_answer` cap evidence lists at `val[:12]` — :400, :450 [DERIVED]
  fails-if: unbounded evidence bodies blow the tool-response size for chat callers.
- INVARIANT: `UPLOAD_EXTENSIONS == {".md", ".txt", ".html", ".pdf", ".epub", ".docx"}` enforced in both `upload_document` (:206) and `upload_text` (:231) — :62 [DERIVED]
  fails-if: the two upload tools accept different file types.
- INVARIANT: `corpus_id` is a required parameter (no default) on `retrieve` (:291), `ask` (:381), `polymath_search` (:407), `polymath_explore` (:420), `polymath_answer` (:434) — per the V2 scope rule (:25-27) [DERIVED]
  fails-if: the unscoped all-corpora path returns (20 s, abstained) instead of the scoped path (3 s, 16 citations).
- INVARIANT: non-admin `list_corpora` filters to `who.corpus_ids` (:177-178); non-admin `adapter_list` filters to `who.adapter_ids` (:483-484) [DERIVED]
  fails-if: principals see corpora/adapters outside their granted scopes.
- INVARIANT: `_ALLOWED_HOSTS` = loopback host:port pairs + `PUBLIC_HOST` + `PUBLIC_HOST:443`; origins include `https://claude.ai` and `https://claude.com` — :64-65, :70-75 [DERIVED]
  fails-if: DNS-rebinding attack or claude.ai connector origin rejected.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: `httpx.AsyncClient` :138, :209, :234; env: :58-61; per-request `contextvars` :83-95; rate limiting via `P.RateLimiter()` :97) [DERIVED]
idempotency: SAFE for read tools (thin proxies). Writes delegate to the orchestrator: uploads are content-addressed (same bytes return the existing run, `already_exists` true, :194-196); `adapter_start` supports `idempotency_key` (:493); `adapter_cancel` is documented terminal + idempotent (:547). orchestrator/orchestrator/mcp_server.py:194-196,493,547 [DERIVED]

## failure behaviour
- Three broad `except Exception` handlers (:143, :216, :241) swallow JSON-parse failures on orchestrator error responses and assign `detail = r.text[:400]`; the caller then sees `{"error": detail, "status": <http code>}` (:140-145, :213-218, :238-243). orchestrator/orchestrator/mcp_server.py:143,216,241 [DERIVED]
- Typed error returns: `401` `NO_PRINCIPAL` (:134); `403` `REMOTE_PATH_UPLOAD_DISABLED` (:84-87); `404` file not found (:205); `422` unsupported extension / bad `source_name` (:207-208, :232); `409` `CROSS_CORPUS_CONTENT_COLLISION` on upload (:198) and `adapter_result` while running (:539); `429` over principal rate (:21); `503` fail-closed when no key configured (:22-24). orchestrator/orchestrator/mcp_server.py:21-24,84-87,134,198,205,232,539 [DERIVED]
- `recent_queries` raises `ValueError("corpus_id is required")` instead of returning an error dict (:464-465). orchestrator/orchestrator/mcp_server.py:464-465 [DERIVED]
- `corpus_status` returns `{"error": "corpus ... not found", "status": 404, "semantic_readiness": ...}` rather than raising (:282-284). orchestrator/orchestrator/mcp_server.py:282-284 [DERIVED]

## dumb-code flags
- Magic truncation constants `1400` (:149), `1200` (:336/:338), `600` (:400, :450), `60 rows x 600 chars` (:508) — no shared named constant. orchestrator/orchestrator/mcp_server.py:149,336,400,450,508 [DERIVED]
- Triplicated error-parse block with identical shape (`r.json().get("detail")` → `r.text[:400]`): :140-145, :213-218, :238-243. orchestrator/orchestrator/mcp_server.py:140-145,213-218,238-243 [DERIVED]
- `REMOTE_PATH_UPLOAD_DISABLED` is also returned to a LOCAL non-admin caller (:201-202), but the message says "a remote caller has no host paths" — misdescribes that case. orchestrator/orchestrator/mcp_server.py:84-87,201-202 [INFERRED] (condition is `not local OR not admin`; message only covers the remote case)
- Module docstring tool list (:9-16) names `retrieve`/`ask` while the canonical surface is `polymath_search`/`polymath_explore`/`polymath_answer` (:405) — doc drift with four DEPRECATED tools kept in the file. orchestrator/orchestrator/mcp_server.py:9-16,291,347,365,381,405 [INFERRED] (docstring predates the canonical rename)
- `_ALLOWED_HOSTS` lists `PUBLIC_HOST` twice — bare and as `f"{PUBLIC_HOST}:443"` (:64-65). orchestrator/orchestrator/mcp_server.py:64-65 [DERIVED]

## refactor notes
- Renaming any `@mcp.tool` function changes the MCP tool surface and must be reflected in `_TOOL_NAMES` (:825); external holders of the surface: Hermes and the claude.ai connector (:3-4, :18-19). orchestrator/orchestrator/mcp_server.py:18-19,825 [DERIVED]
- Removing `retrieve` (:291), `compile_plan` (:347), `retrieve_evidence` (:365) or `ask` (:381) breaks existing callers — each docstring says "Kept for existing callers". orchestrator/orchestrator/mcp_server.py:294,349,366,384 [DERIVED]
- The forwarded `P.PRINCIPAL_HEADER` becomes `adapter_runs.owner_principal_id` in the orchestrator runtime (:496) — changing the header or the forwarding rule breaks run ownership and query-receipt attribution. orchestrator/orchestrator/mcp_server.py:130-137,496 [DERIVED]
- `REMOTE_PATH_UPLOAD_DISABLED` error text instructs callers to switch to `upload_text` (:85-86) — treat the string as agent-facing API text. orchestrator/orchestrator/mcp_server.py:84-87 [DERIVED]
- `TransportSecuritySettings` allowed hosts/origins gate the claude.ai connector; removing `https://claude.ai`/`https://claude.com` risks rejecting the connector's Origin (:70-75). orchestrator/orchestrator/mcp_server.py:64-75 [DERIVED]
- The loopback/edge-header local-caller gate (:79-103) is the HOSTED-SURFACE ISOLATION contract; loosening `_EDGE_HEADERS` or the default-False contextvar reopens the host-filesystem oracle. orchestrator/orchestrator/mcp_server.py:77-103 [DERIVED]

## VERIFY
```verify
grep -Fq 'POLYMATH-MCP-V2 — the v4 MCP server' orchestrator/orchestrator/mcp_server.py
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'def _trim_hit(h: dict, max_chars: int = 1400)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'r[k] = r[k][:1200]' orchestrator/orchestrator/mcp_server.py
grep -Fq 'principal_id="prn_nobody"' orchestrator/orchestrator/mcp_server.py
test "$(grep -c -F 'REMOTE_PATH_UPLOAD_DISABLED' orchestrator/orchestrator/mcp_server.py)" -ge 2
test "$(grep -c -F 'async def polymath_' orchestrator/orchestrator/mcp_server.py)" -ge 3
! grep -Fq 'POLYMATH-MCP-V1' orchestrator/orchestrator/mcp_server.py
```
