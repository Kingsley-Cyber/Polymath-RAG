# unit: mcp_server/polymath_mcp.py
anchor: mcp_server/polymath_mcp.py:1-560

## purpose
MCP server (`POLYMATH-MCP-V1`) exposing the Polymath query product as tools over the orchestrator HTTP API (`BASE`, default `http://127.0.0.1:7200`); it re-implements nothing, it proxies [DERIVED] (mcp_server/polymath_mcp.py:1-6, 53). Serves stdio clients (Claude Code / Claude Desktop / local agents) by default and streamable HTTP via `--http` for remote connectors [DERIVED] (mcp_server/polymath_mcp.py:30-35, 527-555). Tool groups: retrieval (search/explore/answer/compare/deep_research + deprecated query/retrieve), corpus management, the seven `adapter_*` governed-research proxies (ADR-0018), `research_acquire`, four read-only `supplier_*` tools, and the harness guide prompt/resources [DERIVED] (mcp_server/polymath_mcp.py:8-28, 324-471).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_ListedMCPServer` | class | `(MCPServer)`, overrides `list_tools` | mcp_server/polymath_mcp.py:55-59 | `server` instance :62 |
| `polymath_list_corpora` | tool | `() -> dict` | mcp_server/polymath_mcp.py:103-106 | MCP clients |
| `polymath_search` | tool | `(query, corpus_id, mode=MR.DEFAULT_MODE, max_evidence=10) -> dict` | mcp_server/polymath_mcp.py:117-121 | MCP clients |
| `polymath_explore` | tool | `(query, corpus_id, corpus_explorer=True, mode=MR.DEFAULT_MODE) -> dict` | mcp_server/polymath_mcp.py:130-135 | MCP clients |
| `polymath_answer` | tool | `(question, corpus_id, mode=MR.DEFAULT_MODE, reasoning="none", model=None, latent=None) -> dict` | mcp_server/polymath_mcp.py:145-155 | MCP clients |
| `polymath_compare` | tool | `(question, corpus_id, modes=None) -> dict` | mcp_server/polymath_mcp.py:162-167 | MCP clients |
| `polymath_deep_research` | tool | `(question, corpus_id, depth=MR.DEFAULT_DEPTH, mode=MR.DEFAULT_MODE, model=None) -> dict` | mcp_server/polymath_mcp.py:175-194 | MCP clients |
| `polymath_models` | tool | `() -> dict` | mcp_server/polymath_mcp.py:199-203 | MCP clients |
| `polymath_query` | tool (deprecated) | `(question, corpus_id, mode="HYBRID", latent=None) -> dict` | mcp_server/polymath_mcp.py:207-225 | old callers only |
| `polymath_retrieve` | tool (deprecated) | `(query, corpus_id, mode="HYBRID", latent=None) -> dict` | mcp_server/polymath_mcp.py:229-242 | old callers only |
| `polymath_list_documents` | tool | `(corpus_id) -> dict` | mcp_server/polymath_mcp.py:246-249 | MCP clients |
| `polymath_upload_file` | tool | `(path, corpus_id) -> dict` | mcp_server/polymath_mcp.py:253-269 | MCP clients |
| `polymath_upload_text` | tool | `(text, corpus_id, source_name="agent_upload.md") -> dict` | mcp_server/polymath_mcp.py:273-287 | MCP clients |
| `polymath_readiness` | tool | `(corpus_id) -> dict` | mcp_server/polymath_mcp.py:291-295 | MCP clients |
| `polymath_delete_corpus` | tool | `(corpus_id, confirm) -> dict` | mcp_server/polymath_mcp.py:299-310 | MCP clients |
| `polymath_delete_document` | tool | `(doc_id, confirm) -> dict` | mcp_server/polymath_mcp.py:314-321 | MCP clients |
| `adapter_list` | tool | `() -> dict` | mcp_server/polymath_mcp.py:343-348 | MCP clients |
| `adapter_start` | tool | `(adapter_id, input, request_options=None) -> dict` | mcp_server/polymath_mcp.py:352-359 | MCP clients |
| `adapter_next` | tool | `(run_id) -> dict` | mcp_server/polymath_mcp.py:363-374 | MCP clients |
| `adapter_submit` | tool | `(run_id, step_id, payload, agent_identity="connected-agent", model=None, kind=None) -> dict` | mcp_server/polymath_mcp.py:378-390 | MCP clients |
| `adapter_status` | tool | `(run_id) -> dict` | mcp_server/polymath_mcp.py:394-396 | MCP clients |
| `adapter_result` | tool | `(run_id) -> dict` | mcp_server/polymath_mcp.py:400-404 | MCP clients |
| `adapter_cancel` | tool | `(run_id) -> dict` | mcp_server/polymath_mcp.py:408-410 | MCP clients |
| `research_acquire` | tool | `(run_id, operation, target="", site=None, search_intent_id=None, limit=None) -> dict` | mcp_server/polymath_mcp.py:415-432 | MCP clients |
| `supplier_search` | tool | `(query, source="cj", limit=10) -> dict` | mcp_server/polymath_mcp.py:438-446 | MCP clients (owner key) |
| `supplier_product` | tool | `(product_id) -> dict` | mcp_server/polymath_mcp.py:450-455 | MCP clients (owner key) |
| `supplier_freight` | tool | `(variant_id, country, quantity=1, from_country="CN") -> dict` | mcp_server/polymath_mcp.py:459-464 | MCP clients (owner key) |
| `supplier_warehouses` | tool | `() -> dict` | mcp_server/polymath_mcp.py:468-471 | MCP clients (owner key) |
| `run_governed_research` | prompt | `(adapter_id="", seed="") -> str` | mcp_server/polymath_mcp.py:494-497 | MCP clients |
| `main` | def | `() -> None` | mcp_server/polymath_mcp.py:527-555 | `__main__` :559 |

No FACTS.importers data; external callers are MCP clients only.

## contracts

**`polymath_search`** (mcp_server/polymath_mcp.py:117-121)
- in: original query, one `corpus_id`, `mode` normalized by `MR.normalize_mode`; bad mode -> `MR.mode_error(mode)` [DERIVED] :118-120
- out: `MR.shape_search(_post("/chat/evidence", MR.search_body(query, corpus_id, m)), max_evidence)` — contract evidence rows, no plan/answer [DERIVED] :121

**`polymath_explore`** (mcp_server/polymath_mcp.py:130-135)
- in: `corpus_explorer: bool = True`; mode normalized, bad -> `MR.mode_error` [DERIVED] :131-134
- out: `MR.shape_explore(_post("/chat/evidence", MR.explore_body(...)))` — EvidencePacket, no Polymath answer [DERIVED] :135

**`polymath_answer`** (mcp_server/polymath_mcp.py:145-155)
- pre: `mode == "ASK"` (case-insensitive strip/upper) routes to `_post("/ask", {"question", "corpus_id"})` [DERIVED] :147-148
- pre: unknown reasoning style -> `{"error": ..., "status": 422, "styles": list(MR.REASONING_STYLES)}` [DERIVED] :152-154
- out: `_post("/chat", MR.answer_body(..., reasoning=style, model=model, latent=latent))` [DERIVED] :155

**`polymath_compare`** (mcp_server/polymath_mcp.py:162-167)
- pre: every entry in `modes` (default all `MR.RETRIEVAL_MODES`) must normalize; first bad one -> `MR.mode_error(wanted[normal.index(None)])`; dedup via `dict.fromkeys` [DERIVED] :163-166
- out: `MR.shape_compare(_post("/compare", ..., timeout=600))` [DERIVED] :167

**`polymath_deep_research`** (mcp_server/polymath_mcp.py:175-194)
- pre: mode and depth normalized; unknown depth -> `{"error": ..., "status": 422, "depths": dict(MR.DEPTHS)}` [DERIVED] :177-182
- out: SSE stream `POST /research/deep` with `Accept: text/event-stream`, `httpx.Timeout(1800.0, connect=10.0)`, parsed by `MR.parse_sse` then `MR.shape_deep(..., depth=d, mode=m)` [DERIVED] :183-194
- on HTTP >= 400: returns `{"error": "<error_code or status>: <message>", "status": r.status_code}` [DERIVED] :185-192

**`polymath_delete_corpus` / `polymath_delete_document`** (mcp_server/polymath_mcp.py:299-321)
- pre (from docstrings): `confirm` must equal `corpus_id` / `doc_id` [DERIVED] :300-302, 316-317
- out: delete returns error dict on >= 400; delete-document instead calls `r.raise_for_status()` and raises [DERIVED] :305-309 vs :320

**`adapter_start`** (mcp_server/polymath_mcp.py:352-359)
- in: `input` must satisfy the adapter's `input_schema` (at least `seed` and `corpus_ids`); `request_options` may carry `idempotency_key`, `agent_identity`, `corpus_ids` (required for non-admin key), `retrieval_mode`, `deadline_s` [DERIVED] :353-356
- out: `POST /adapter/start` with `{"adapter_id", "input", "request_options": request_options or {}}` -> AdapterRunRefV1 [DERIVED] :359

**`adapter_submit`** (mcp_server/polymath_mcp.py:378-390)
- pre: AGENT_REASON -> `kind="reasoning"` (default), cite only ids from `context.evidence_refs`; HARNESS_ACTION -> `kind="receipt"` with a `HarnessResearchReceiptV1` [DERIVED] :380-386
- out: `AdapterRunStatusV1`; rejection returns errors and the step stays open [DERIVED] :386-387, 390

**`_adapter`** (mcp_server/polymath_mcp.py:329-339)
- in: any method/path/payload, `httpx.request(..., timeout=180)` [DERIVED] :332
- out: status >= 400 -> `{"error": detail, "status": r.status_code}`; else `r.json()` [DERIVED] :333-339

**`_auth_wrapped`** (mcp_server/polymath_mcp.py:500-524)
- pre: `POLYMATH_MCP_API_KEY` unset/blank -> returns app unchanged (local-trusted) [DERIVED] :506-508
- post: with key, HTTP requests must present it as `Authorization: Bearer <key>` or `X-API-Key: <key>`, else `401 {"error": "unauthorized"}` [DERIVED] :510-521

## effect surface
- Postgres tables: none read/written directly (`tables_read`/`tables_written` empty) [DERIVED] (FACTS).
- Qdrant collections: none directly [DERIVED] (FACTS, collections list is mode-description usage only).
- Network — all to `BASE` (default `http://127.0.0.1:7200`, mcp_server/polymath_mcp.py:53):

| route | method | caller / timeout | anchor |
|---|---|---|---|
| `/corpora` | GET | `_get`, 120 | :87, 106 |
| `/chat/evidence` | POST | `_post`, 300 | :93, 121, 135 |
| `/chat` | POST | `_post`, 300 | :155, 223 |
| `/ask` | POST | `_post`, 300 | :148, 220 |
| `/compare` | POST | `_post`, 600 | :167 |
| `/research/deep` | POST (SSE) | `httpx.stream`, `Timeout(1800.0, connect=10.0)` | :183-184 |
| `/synthesizers` | GET | `_get`, 120 | :201 |
| `/retrieve` | POST | `_post`, 300 | :240 |
| `/documents` | GET | `_get`, 120 | :249 |
| `/upload` | POST (multipart) | direct, 300 | :261-266, 279-284 |
| `/semantic_readiness` | GET | `_get`, 120 | :295 |
| `/corpora/{corpus_id}` | DELETE | direct, 300 | :303-304 |
| `/documents/{doc_id}` | DELETE | direct, 300 | :318-319 |
| `/adapter/list`, `/adapter/start`, `/adapter/{run_id}/next|submit|status|result|cancel|acquire` | GET/POST | `_adapter`, 180 | :348, 359, 374, 388, 396, 404, 410, 431-432 |
| `/supplier/search|product|freight`, `/supplier/warehouses` | POST/GET | `_adapter`, 180 | :446, 455, 463, 471 |

- Files: guide files under repo root (`_GUIDE_ROOT = Path(__file__).resolve().parents[1]`) read per request via `HG.FILES` :477-481; uploaded local file opened `rb` :257-266; guide resources registered under `HG.RESOURCE_URIS` (incl. `polymath://adapter/guide`) :490-491, 81.
- Env: `POLYMATH_API` = `'http://127.0.0.1:7200'` :53; `POLYMATH_MCP_API_KEY` = `''` :506, :541.
- Subprocesses: none.

## invariants
INVARIANT: tools listed ⊆ tools registered — `list_tools` removes names in `MR.HIDDEN_TOOLS_B` (deprecated stay callable, never listed) — mcp_server/polymath_mcp.py:55-59 [DERIVED]
  fails-if: old callers' tool names vanish from registration entirely; or hidden tools leak into listings.
INVARIANT: all tool HTTP traffic origin == `BASE` (single orchestrator) — mcp_server/polymath_mcp.py:53, 87, 93, 183, 261, 279, 303, 318, 332 [DERIVED]
  fails-if: a hardcoded `127.0.0.1:7200` elsewhere ignores `POLYMATH_API`.
INVARIANT: bearer/x-api-key check active iff `POLYMATH_MCP_API_KEY` non-blank — mcp_server/polymath_mcp.py:506-521 [DERIVED]
  fails-if: key set but wrapper bypassed -> unauthenticated remote access; key unset with wrapper on -> 401 for local stdio/HTTP.
INVARIANT: `_adapter` status >= 400 -> dict with both `"error"` and `"status"` keys — mcp_server/polymath_mcp.py:333-338 [DERIVED]
  fails-if: agents see transport exceptions instead of 422/409 semantics pinned by parity tests.
INVARIANT: destructive deletes gated by `confirm == corpus_id` / `confirm == doc_id` — mcp_server/polymath_mcp.py:300-302, 316-317 [DERIVED]
  fails-if: corpus or document (vectors, graph, facts, summaries) deleted without intent.
INVARIANT: `--http` with no parseable port -> port `7300`; no `--http` -> stdio — mcp_server/polymath_mcp.py:528-532, 554-555 [DERIVED]
  fails-if: port drift between launcher scripts and the server.
INVARIANT: with key set, `enable_dns_rebinding_protection=False`; without key, hosts pinned to `127.0.0.1:{port}` and `localhost:{port}` — mcp_server/polymath_mcp.py:541-551 [DERIVED]
  fails-if: keyless mode reachable via tunnel/DNS-rebind (421 gate defeated), or keyed mode blocked by host pinning behind a dynamic tunnel hostname.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: httpx calls at :87, :93, :183-184, :261, :279, :303, :318, :332; env: `POLYMATH_API` :53, `POLYMATH_MCP_API_KEY` :506/:541; per-request disk reads of guide files :480-481) [DERIVED]
idempotency: SAFE for reads/uploads-to-same-corpus? no — UNSAFE overall: `polymath_delete_corpus`/`polymath_delete_document` are destructive :299-321; `adapter_start` retries safe only when `request_options.idempotency_key` is passed ("a retry never starts a second run") :355; `adapter_cancel` documented terminal/idempotent :409 [DERIVED]

## failure behaviour
- `_post`: on status >= 400 returns `{"error": r.json().get("detail", r.text)}`; JSON decode failure swallowed -> `{"error": r.text[:400]}` — caller sees an error dict, never an exception for 4xx/5xx bodies :94-98 [DERIVED] (FACTS fallbacks line 97).
- `polymath_delete_corpus`: identical swallow pattern -> `{"error": r.text[:400]}` :305-309 [DERIVED] (FACTS line 308).
- `_adapter`: non-JSON error body handled by assign `detail = r.text[:400]`, still returns `{"error", "status"}` :334-338 [DERIVED] (FACTS line 336).
- `polymath_deep_research`: same handled-assign inside the >= 400 branch :187-192 [DERIVED] (FACTS line 189).
- `polymath_models`: catches `httpx.HTTPError` -> `{"error": f"{type(exc).__name__}: {exc}"[:300]}` :200-203 [DERIVED].
- `_get` and `polymath_delete_document` raise instead: `r.raise_for_status()` :88, :320 [DERIVED].
- `polymath_upload_file`: missing file -> `{"error": f"file not found: {path}"}`; >= 400 -> `{"error": r.text[:400]}` :258-259, 267-268 [DERIVED].
- HTTP 401 from `_auth_wrapped` guard; HTTP 409 semantics surfaced by `_adapter` as status, not exception :517-520, 330-331 [DERIVED].

## dumb-code flags
- `"VECTOR" -> "FAST"` mapping duplicated verbatim in `polymath_query` (`"FAST" if mode == "VECTOR"`) and `polymath_retrieve` (`"FAST" if mode.upper() == "VECTOR"`) — one misses `.upper()` on the first operand path :221 vs :238 [DERIVED].
- Error-text truncation inconsistent: `r.text[:400]` at :98, :190, :268, :286, :309, :337 vs `[:300]` at :203 [DERIVED].
- Timeout magic numbers scattered with no shared constant: `120` :87, `300` :93/:266/:284/:304/:319, `600` :167, `1800.0`/`10.0` :184, `180` :332 [DERIVED].
- Deprecated tools hardcode `mode: str = "HYBRID"` (:210, :231) while current tools use `MR.DEFAULT_MODE` (:117, :131, :146, :176) — defaults can diverge [DERIVED].
- Delete error handling inconsistent: corpus returns error dict, document raises :305-309 vs :320 [DERIVED].
- Fallback port `7300` magic number :530 [DERIVED].
- Comment claims "MCP 2026-07-28 stateless core" — dated spec reference embedded in code :535-536 [DERIVED].

## refactor notes
- `adapter_*` names, parameters and semantics are parity-pinned against Server A by `tests/contracts/test_mcp_adapter_parity.py` — any signature change must update both servers and that test :23-28, 324-327 [DERIVED].
- `supplier_*` tools must keep "the same names, parameters and descriptions as Server A" — blast radius spans both MCP servers :435-436; `research_acquire` likewise :413 [DERIVED].
- Deprecated `polymath_query`/`polymath_retrieve` must remain callable (only unlisted) — the hide list lives in `polymath_shared.mcp_retrieval.HIDDEN_TOOLS_B`, not here :55-59, 213-215, 235-237 [DERIVED].
- `{"error": ..., "status": ...}` dict shape from `_post`/`_adapter` is the de-facto agent-facing error contract; converting to raised exceptions breaks every caller :94-98, 333-338 [DERIVED].
- Guide prompt/resources read files per request relative to `_GUIDE_ROOT` (repo parent of this file) — moving the file or `HG.FILES` layout breaks `polymath://adapter/guide` :475-491 [DERIVED].
- Dropping `_auth_wrapped` or the keyless host-pinning branch changes remote-connector and DNS-rebinding posture respectively :500-551 [DERIVED].

## VERIFY
```verify
grep -Fq 'BASE = os.environ.get("POLYMATH_API", "http://127.0.0.1:7200")' mcp_server/polymath_mcp.py
grep -Fq 'if t.name not in MR.HIDDEN_TOOLS_B' mcp_server/polymath_mcp.py
grep -Fq 'port = 7300' mcp_server/polymath_mcp.py
grep -Fq 'timeout=httpx.Timeout(1800.0, connect=10.0)' mcp_server/polymath_mcp.py
grep -Fq 'm = "FAST" if mode.upper() == "VECTOR" else mode.upper()' mcp_server/polymath_mcp.py
grep -Fq 'enable_dns_rebinding_protection=False' mcp_server/polymath_mcp.py
test "$(grep -c -F 'r.text[:400]' mcp_server/polymath_mcp.py)" -ge 5
```
