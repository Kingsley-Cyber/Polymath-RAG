# unit: mcp_server/polymath_mcp.py
anchor: mcp_server/polymath_mcp.py:1-494

## purpose
MCP server (stdio default, `--http [PORT]` optional) exposing the Polymath orchestrator as agent tools: corpus inventory/ingest/delete, evidence retrieval, grounded answers, the 7-tool cognitive-adapter run loop, Polymath-hosted web reads, and read-only CJ supplier lookups (mcp_server/polymath_mcp.py:1-36) [DERIVED]. A thin httpx client of the orchestrator HTTP API (`BASE`, default `http://127.0.0.1:7200`); nothing is re-implemented here (mcp_server/polymath_mcp.py:4-6, 52) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| polymath_list_corpora | tool | () -> dict | mcp_server/polymath_mcp.py:92-95 | — |
| polymath_search | tool | (query, corpus_id, max_evidence=10) -> dict | mcp_server/polymath_mcp.py:99-105 | — |
| polymath_explore | tool | (query, corpus_id, corpus_explorer=True, mode="HYBRID") -> dict | mcp_server/polymath_mcp.py:109-119 | — |
| polymath_answer | tool | (question, corpus_id, mode="HYBRID", latent=None) -> dict | mcp_server/polymath_mcp.py:123-137 | — |
| polymath_query | tool (deprecated) | (question, corpus_id, mode="HYBRID", latent=None) -> dict | mcp_server/polymath_mcp.py:141-159 | — |
| polymath_retrieve | tool (deprecated) | (query, corpus_id, mode="HYBRID", latent=None) -> dict | mcp_server/polymath_mcp.py:163-176 | — |
| polymath_list_documents | tool | (corpus_id) -> dict | mcp_server/polymath_mcp.py:180-183 | — |
| polymath_upload_file | tool | (path, corpus_id) -> dict | mcp_server/polymath_mcp.py:187-203 | — |
| polymath_upload_text | tool | (text, corpus_id, source_name="agent_upload.md") -> dict | mcp_server/polymath_mcp.py:207-221 | — |
| polymath_readiness | tool | (corpus_id) -> dict | mcp_server/polymath_mcp.py:225-229 | — |
| polymath_delete_corpus | tool | (corpus_id, confirm) -> dict | mcp_server/polymath_mcp.py:233-244 | — |
| polymath_delete_document | tool | (doc_id, confirm) -> dict | mcp_server/polymath_mcp.py:248-255 | — |
| adapter_list | tool | () -> dict | mcp_server/polymath_mcp.py:277-282 | — |
| adapter_start | tool | (adapter_id, input, request_options=None) -> dict | mcp_server/polymath_mcp.py:286-293 | — |
| adapter_next | tool | (run_id) -> dict | mcp_server/polymath_mcp.py:297-308 | — |
| adapter_submit | tool | (run_id, step_id, payload, agent_identity="connected-agent", model=None, kind=None) -> dict | mcp_server/polymath_mcp.py:312-324 | — |
| adapter_status | tool | (run_id) -> dict | mcp_server/polymath_mcp.py:328-330 | — |
| adapter_result | tool | (run_id) -> dict | mcp_server/polymath_mcp.py:334-338 | — |
| adapter_cancel | tool | (run_id) -> dict | mcp_server/polymath_mcp.py:342-344 | — |
| research_acquire | tool | (run_id, operation, target="", site=None, search_intent_id=None, limit=None) -> dict | mcp_server/polymath_mcp.py:349-366 | — |
| supplier_search | tool | (query, source="cj", limit=10) -> dict | mcp_server/polymath_mcp.py:372-380 | — |
| supplier_product | tool | (product_id) -> dict | mcp_server/polymath_mcp.py:384-389 | — |
| supplier_freight | tool | (variant_id, country, quantity=1, from_country="CN") -> dict | mcp_server/polymath_mcp.py:393-398 | — |
| supplier_warehouses | tool | () -> dict | mcp_server/polymath_mcp.py:402-405 | — |
| run_governed_research | prompt | (adapter_id="", seed="") -> str | mcp_server/polymath_mcp.py:429-431 | — |
| main | entrypoint | () -> None | mcp_server/polymath_mcp.py:461-489 | script run (mcp_server/polymath_mcp.py:31-33) |

Private helpers: `_get` (75-78), `_post` (81-88), `_adapter` (263-273), `_guide_resources` (414-415), `_guide_reader` (418-421), `_auth_wrapped` (434-458) [DERIVED].

## contracts

**polymath_search** — mcp_server/polymath_mcp.py:99-105
- in: `query: str`, `corpus_id: str`, `max_evidence: int = 10`
- out: `_post("/retrieve", {"query", "corpus_id", "evidence": True, "limit": max_evidence})` — `evidence` is hard-coded `True` (mcp_server/polymath_mcp.py:104-105) [DERIVED]
- post: 4xx/5xx returns `{"error": ...}` dict, never raises (via `_post`, 81-88)

**polymath_explore** — mcp_server/polymath_mcp.py:109-119
- in: `mode="HYBRID"`; literal `"VECTOR"` mapped to `"FAST"` before send (mcp_server/polymath_mcp.py:117)
- out: POST `/chat/evidence` body `{"message", "corpus_id", "mode", "corpus_explorer"}`; no answer key promised (`synthesis_performed=false`, docstring 113)

**polymath_answer** — mcp_server/polymath_mcp.py:123-137
- in: `mode: VECTOR|HYBRID|GRAPH|ASK`; `latent` optional, added to body only when not `None` (135-136)
- out: `ASK` → POST `/ask` `{"question","corpus_id"}`; else POST `/chat` with `mode` mapped `VECTOR`→`FAST` (130-137)
- caller contract: `verdict=insufficient_evidence` must be relayed, not filled (docstring 128-129; server instructions 69-70)

**polymath_upload_file** — mcp_server/polymath_mcp.py:187-203
- pre: `Path(path).expanduser().exists()`; else returns `{"error": f"file not found: {path}"}` without any HTTP call (191-193)
- out: multipart POST `{BASE}/upload`, timeout=300; >=400 → `{"error": r.text[:400]}` (195-202)

**polymath_delete_corpus / polymath_delete_document** — mcp_server/polymath_mcp.py:233-255
- pre (docstring): `confirm` must equal `corpus_id` / `doc_id` (236, 250-251); the proxy forwards it as a query param and never checks it locally [INFERRED: no comparison in body]
- out: DELETE `/corpora/{corpus_id}` / `/documents/{doc_id}` with `params={"confirm": ...}`, timeout=300 (237-238, 252-253)

**adapter_start / adapter_next / adapter_submit** — mcp_server/polymath_mcp.py:286-324
- adapter_start: POST `/adapter/start` `{"adapter_id", "input", "request_options": request_options or {}}`; empty dict substituted for `None` (293)
- adapter_next: GET `/adapter/{run_id}/next`; returns step or status per docstring (298-307)
- adapter_submit: POST `/adapter/{run_id}/submit`; `"kind"` key included only when `kind` truthy — `**({"kind": kind} if kind else {})` (323-324)

**research_acquire** — mcp_server/polymath_mcp.py:349-366
- in: `operation` (`catalog`|`web_search`|`comments`|`listings`), `target=""`, optional `site`, `search_intent_id`, `limit`
- out: POST `/adapter/{run_id}/acquire` with all five fields (365-366); `status HUMAN_ACTION_REQUIRED` demands user action, never bypassed (docstring 359-362)

**_auth_wrapped / main** — mcp_server/polymath_mcp.py:434-489
- pre: `POLYMATH_MCP_API_KEY` unset/empty → app returned unmodified (441-442)
- post: with key, every `http` scope must present `Authorization: Bearer <key>` or `X-API-Key: <key>`; mismatch → 401 `{"error": "unauthorized"}` (444-455)
- main: `--http [PORT]`, default port `7300` on `IndexError/ValueError` (462-466); `stateless_http=True` (486); with key: `TransportSecuritySettings(enable_dns_rebinding_protection=False)` (479); without key: `allowed_hosts` = `["127.0.0.1:{port}", "localhost:{port}"]` (483-485); binds `127.0.0.1` (487); else `server.run("stdio")` (489)

## effect surface

| kind | target | anchor |
|---|---|---|
| env | `POLYMATH_API` = `"http://127.0.0.1:7200"` | mcp_server/polymath_mcp.py:52 |
| env | `POLYMATH_MCP_API_KEY` = `""` (read twice: auth wrap + security branch) | mcp_server/polymath_mcp.py:440, 475 |
| network | httpx GET `/corpora`, `/documents`, `/semantic_readiness`, `/adapter/list`, `/adapter/{run_id}/next|status|result`, `/supplier/warehouses` | mcp_server/polymath_mcp.py:76, 95, 183, 229, 282, 308, 330, 338, 405 |
| network | httpx POST `/retrieve`, `/chat`, `/chat/evidence`, `/ask`, `/upload` (multipart), `/adapter/start`, `/adapter/{run_id}/submit|cancel|acquire`, `/supplier/search|product|freight` | mcp_server/polymath_mcp.py:82, 104, 118, 132, 136-137, 195, 213, 293, 322, 344, 365, 380, 389, 397 |
| network | httpx DELETE `/corpora/{corpus_id}`, `/documents/{doc_id}` | mcp_server/polymath_mcp.py:237, 252 |
| network | generic `httpx.request` for all `_adapter` calls | mcp_server/polymath_mcp.py:266 |
| files | repo `shared/` dir inserted into `sys.path` | mcp_server/polymath_mcp.py:47-49 |
| files | guide files under `_GUIDE_ROOT = parents[1]` read `.read_text(encoding="utf-8")` per request | mcp_server/polymath_mcp.py:411, 414-415 |
| files | user-supplied upload path opened `"rb"` | mcp_server/polymath_mcp.py:191-194 |
| db | none — `tables_read`/`tables_written` empty; FACTS `collections` entries (`polymath_search`/`polymath_explore`/`polymath_answer` at line 61) are tool names inside the server instructions string, not vector stores | mcp_server/polymath_mcp.py:61 [INFERRED] |
| subprocess | none | — |

## invariants

INVARIANT: request mode `"VECTOR"` sent to orchestrator as `"FAST"` — mcp_server/polymath_mcp.py:117, 133, 155, 172 [DERIVED]
  fails-if: orchestrator `/chat`, `/chat/evidence`, `/retrieve` receive raw `"VECTOR"` and misroute or reject.
INVARIANT: `_get` timeout `120` < `_adapter` timeout `180` < `_post` default/upload/delete timeout `300` (seconds) — mcp_server/polymath_mcp.py:76, 82, 266, 199, 218, 238, 253 [DERIVED]
  fails-if: long adapter runs or uploads exceed the proxy timeout and surface as transport errors.
INVARIANT: with `POLYMATH_MCP_API_KEY` set, every http request presents it via `Bearer` or `X-API-Key` else 401 — mcp_server/polymath_mcp.py:444-455 [DERIVED]
  fails-if: unauthorized remote caller reaches MCP tools through the tunnel.
INVARIANT: key set ⟺ `enable_dns_rebinding_protection=False`; key unset ⟺ `allowed_hosts` restricted to `127.0.0.1:{port}`/`localhost:{port}` — mcp_server/polymath_mcp.py:475-485 [DERIVED]
  fails-if: keyless server exposed off-host (rebinding/tunnel gets 421) or keyed server keeps pinning that rejects the tunnel hostname.
INVARIANT: `polymath_search` body always carries `"evidence": True` — mcp_server/polymath_mcp.py:104 [DERIVED]
  fails-if: tool silently becomes a full-answer call, breaking the evidence-only contract.
INVARIANT: adapter tool names/params identical to orchestrator MCP Server A (parity pinned by `tests/contracts/test_mcp_adapter_parity.py`) — mcp_server/polymath_mcp.py:23-26 [DERIVED]
  fails-if: parity contract test fails; stdio agents and HTTP Hermes drives diverge.

## determinism & idempotency

determinism: NONDETERMINISTIC (network: httpx.get/post/delete/request at mcp_server/polymath_mcp.py:76, 82, 195, 213, 237, 252, 266; per-request guide file reads at 414-415). No clock/random/uuid use in this unit [DERIVED].
idempotency: SAFE for all GET/POST-read tools; UNSAFE for `polymath_upload_file`/`polymath_upload_text` (duplicate ingestion), `polymath_delete_corpus`/`polymath_delete_document` (destructive, docstring 234, 249); `adapter_start` supports retry-safe `idempotency_key` via `request_options` (docstring 289); `adapter_cancel` documented terminal/idempotent (docstring 343) [DERIVED].

## failure behaviour

- `_post`: status >=400 → tries `r.json()["detail"]`; any `Exception` swallowed → `{"error": r.text[:400]}` (mcp_server/polymath_mcp.py:83-87). Caller sees an error dict, never an exception.
- `polymath_delete_corpus`: identical swallow pattern, `{"error": r.text[:400]}` fallback (mcp_server/polymath_mcp.py:239-243).
- `_adapter`: handled-assign — `detail = r.text[:400]` on parse failure; returns `{"error": detail, "status": r.status_code}` so 422 rejections and 409 not-terminal reach the agent (mcp_server/polymath_mcp.py:267-272).
- `_get` and `polymath_delete_document` instead call `r.raise_for_status()` → raise `httpx.HTTPStatusError` (mcp_server/polymath_mcp.py:77, 254) — inconsistent with the dict-return style above [INFERRED: mixed conventions visible side by side].
- `polymath_upload_file`/`polymath_upload_text`: >=400 → `{"error": r.text[:400]}` (mcp_server/polymath_mcp.py:201-202, 219-220); missing file → `{"error": "file not found: ..."}` (192-193).
- HTTP-mode auth failure: 401 JSONResponse `{"error": "unauthorized"}` (mcp_server/polymath_mcp.py:452-455).

## dumb-code flags

- VECTOR→FAST one-liner duplicated 4×: `m = "FAST" if ... == "VECTOR" else ...` (mcp_server/polymath_mcp.py:117, 133, 155, 172).
- `polymath_query` body is a verbatim copy of `polymath_answer` (152-159 vs 130-137); `polymath_retrieve` overlaps `polymath_search` (172-176 vs 104-105) — both kept only for existing callers (147-148, 169-170).
- Timeout literals `120`/`180`/`300` scattered with no named constant (mcp_server/polymath_mcp.py:76, 82, 199, 218, 238, 253, 266).
- Error-truncation literal `r.text[:400]` repeated 4× (mcp_server/polymath_mcp.py:87, 202, 220, 271).
- Magic default port `7300` on `--http` parse failure (mcp_server/polymath_mcp.py:466); host string `127.0.0.1` appears in `BASE` default, allowed_hosts build, and uvicorn bind (52, 483, 487).
- `polymath_delete_document` uses `raise_for_status()` while sibling `polymath_delete_corpus` returns error dicts (mcp_server/polymath_mcp.py:254 vs 239-243).
- Lazy `from starlette.responses import JSONResponse` inside the `guarded` closure (mcp_server/polymath_mcp.py:452).
- Defensive `_SHARED` sys.path insert commented "normally already on the path" — near-dead branch (mcp_server/polymath_mcp.py:47-49).
- `confirm` equality (`confirm must equal corpus_id`/`doc_id`) documented but never validated in this file (mcp_server/polymath_mcp.py:236, 250-251) [INFERRED: no local comparison exists].

## refactor notes

- The 7 adapter tool names/params and the supplier tool names/params are parity-pinned to orchestrator MCP Server A (`tests/contracts/test_mcp_adapter_parity.py`; "the same names, parameters and descriptions as Server A") — any signature change here must be mirrored there (mcp_server/polymath_mcp.py:23-28, 369-370).
- Deprecated `polymath_query`/`polymath_retrieve` have live external callers by design ("Kept for existing callers") — removal or behaviour change breaks them (mcp_server/polymath_mcp.py:147-148, 169-170).
- Mode vocabulary (`VECTOR`→`FAST`, `HYBRID`, `GRAPH`, `ASK`) is an orchestrator wire contract on `/chat`, `/chat/evidence`, `/retrieve` — renaming requires both sides (mcp_server/polymath_mcp.py:117, 130-133).
- Route change to any `/adapter/*`, `/supplier/*`, `/upload`, `/corpora*`, `/documents*` path breaks this client (mcp_server/polymath_mcp.py:95-405).
- `HG.RESOURCE_URIS`/`HG.FILES` drive registered `polymath://` resources and per-request reads from `_GUIDE_ROOT = parents[1]` — moving the guide files or the shared package changes resource URIs (mcp_server/polymath_mcp.py:411, 414-425).
- Security branch: keyed deployment deliberately disables DNS-rebinding protection (tunnel + 401 assumption); keyless deployment restricts hosts — flipping either requires rethinking the exposure model (mcp_server/polymath_mcp.py:475-485).
- `BASE` default port `7200` must match the orchestrator bind (mcp_server/polymath_mcp.py:52).

## VERIFY

```verify
grep -Fq 'http://127.0.0.1:7200' mcp_server/polymath_mcp.py
grep -Fq 'def polymath_search(query: str, corpus_id: str, max_evidence: int = 10) -> dict:' mcp_server/polymath_mcp.py
grep -Fq 'agent_upload.md' mcp_server/polymath_mcp.py
grep -Eq '"FAST" if mode.upper\(\) == "VECTOR"' mcp_server/polymath_mcp.py
grep -Fq 'stateless_http=True' mcp_server/polymath_mcp.py
test "$(grep -c -F 'r.text[:400]' mcp_server/polymath_mcp.py)" -ge 4
! grep -Fq 'qdrant' mcp_server/polymath_mcp.py
```
