# unit: mcp_server/polymath_mcp.py
anchor: mcp_server/polymath_mcp.py:1-583

## purpose
MCP server (POLYMATH-MCP-V1) exposing the Polymath query product to agents over stdio (default) or streamable HTTP (`--http [PORT]`). It is a thin HTTP client of the orchestrator API (`http://127.0.0.1:7200` default) — nothing is re-implemented; agents get the same fail-closed, evidence-first product as the web UI. — mcp_server/polymath_mcp.py:1-45 [DERIVED], mcp_server/polymath_mcp.py:550-578 [DERIVED]

## public surface
No FACTS importers; consumers are MCP clients (stdio/HTTP transports, mcp_server/polymath_mcp.py:40-45 [DERIVED]).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_ListedMCPServer` | class | `MCPServer` subclass; overrides `list_tools()` | mcp_server/polymath_mcp.py:65-69 | — |
| `polymath_list_corpora` | tool | `() -> dict` | mcp_server/polymath_mcp.py:116-119 | — |
| `polymath_search` | tool | `(query: str, corpus_id: str, mode = MR.DEFAULT_MODE, max_evidence: int = 10) -> dict` | mcp_server/polymath_mcp.py:125-134 | — |
| `polymath_explore` | tool | `(query: str, corpus_id: str, corpus_explorer: bool = True, mode = MR.DEFAULT_MODE) -> dict` | mcp_server/polymath_mcp.py:137-148 | — |
| `polymath_answer` | tool | `(question: str, corpus_id: str, mode = MR.DEFAULT_MODE, reasoning: str = "none", model: str \| None = None, latent: bool \| None = None) -> dict` | mcp_server/polymath_mcp.py:151-163 | — |
| `polymath_compare` | tool | `(question: str, corpus_id: str, modes: list[str] \| None = None) -> dict` | mcp_server/polymath_mcp.py:166-175 | — |
| `polymath_deep_research` | tool | `(question: str, corpus_id: str, depth = MR.DEFAULT_DEPTH, mode = MR.DEFAULT_MODE, model: str \| None = None) -> dict` | mcp_server/polymath_mcp.py:178-202 | — |
| `polymath_models` | tool | `() -> dict` | mcp_server/polymath_mcp.py:205-211 | — |
| `product_search` | tool | `(message: str, corpus_id=None, geography=None, model=None, hypotheses=None, limit_per_hypothesis=None) -> dict` | mcp_server/polymath_mcp.py:214-222 | — |
| `supplier_parse` | tool | `(site: str, raw_text: str) -> dict` | mcp_server/polymath_mcp.py:225-227 | — |
| `product_report_start` | tool | `(message=None, corpus_id=None, products=None, channels=None, ship_to: str = "US", max_products = MR.REPORT_DEFAULT_PRODUCTS) -> dict` | mcp_server/polymath_mcp.py:240-250 | — |
| `product_report_status` | tool | `(report_id: str) -> dict` | mcp_server/polymath_mcp.py:253-261 | — |
| `product_report_compile` | tool | `(report_id: str, verdicts: Optional[dict[str, str]] = None) -> dict` | mcp_server/polymath_mcp.py:264-270 | — |
| `product_report_list` | tool | `() -> dict` | mcp_server/polymath_mcp.py:273-275 | — |
| `polymath_query` | tool (deprecated, hidden) | `(question: str, corpus_id: str, mode: str = "HYBRID", latent: bool \| None = None) -> dict` | mcp_server/polymath_mcp.py:278-297 | — |
| `polymath_retrieve` | tool (deprecated, hidden) | `(query: str, corpus_id: str, mode: str = "HYBRID", latent: bool \| None = None) -> dict` | mcp_server/polymath_mcp.py:300-314 | — |
| `polymath_list_documents` | tool | `(corpus_id: str) -> dict` | mcp_server/polymath_mcp.py:317-321 | — |
| `polymath_upload_file` | tool | `(path: str, corpus_id: str) -> dict` | mcp_server/polymath_mcp.py:324-341 | — |
| `polymath_upload_text` | tool | `(text: str, corpus_id: str, source_name: str = "agent_upload.md") -> dict` | mcp_server/polymath_mcp.py:344-359 | — |
| `polymath_readiness` | tool | `(corpus_id: str) -> dict` | mcp_server/polymath_mcp.py:362-367 | — |
| `polymath_delete_corpus` | tool | `(corpus_id: str, confirm: str) -> dict` | mcp_server/polymath_mcp.py:370-382 | — |
| `polymath_delete_document` | tool | `(doc_id: str, confirm: str) -> dict` | mcp_server/polymath_mcp.py:385-393 | — |
| `adapter_list` | tool | `() -> dict` | mcp_server/polymath_mcp.py:414-416 | — |
| `adapter_start` | tool | `(adapter_id: str, input: dict, request_options: Optional[dict] = None) -> dict` | mcp_server/polymath_mcp.py:419-421 | — |
| `adapter_next` | tool | `(run_id: str) -> dict` | mcp_server/polymath_mcp.py:424-426 | — |
| `adapter_submit` | tool | `(run_id, step_id, payload: dict, agent_identity: str = "connected-agent", model=None, kind=None) -> dict` | mcp_server/polymath_mcp.py:429-443 | — |
| `adapter_status` | tool | `(run_id: str) -> dict` | mcp_server/polymath_mcp.py:446-449 | — |
| `adapter_result` | tool | `(run_id: str) -> dict` | mcp_server/polymath_mcp.py:452-457 | — |
| `adapter_cancel` | tool | `(run_id: str) -> dict` | mcp_server/polymath_mcp.py:460-463 | — |
| `research_acquire` | tool | `(run_id, operation: str, target: str = "", site=None, search_intent_id=None, limit=None) -> dict` | mcp_server/polymath_mcp.py:466-471 | — |
| `supplier_search` | tool | `(query: str, source: str = "cj", limit: int = 10) -> dict` | mcp_server/polymath_mcp.py:476-478 | — |
| `supplier_product` | tool | `(product_id: str) -> dict` | mcp_server/polymath_mcp.py:481-483 | — |
| `supplier_freight` | tool | `(variant_id: str, country: str, quantity: int = 1, from_country: str = "CN") -> dict` | mcp_server/polymath_mcp.py:486-489 | — |
| `supplier_warehouses` | tool | `() -> dict` | mcp_server/polymath_mcp.py:492-494 | — |
| `run_governed_research` | prompt | `(adapter_id: str = "", seed: str = "") -> str` | mcp_server/polymath_mcp.py:517-520 | — |
| guide resources | resource | one per `HG.RESOURCE_URIS`, files read per request | mcp_server/polymath_mcp.py:513-514 | — |
| `main` | entrypoint | `() -> None` (stdio or `--http [PORT]`) | mcp_server/polymath_mcp.py:550-578 | — |

## contracts
- `_get(path)` — in: path + params; out: `r.json()`; pre: HTTP 2xx else `raise_for_status()` raises; timeout `120`. — mcp_server/polymath_mcp.py:89-92 [DERIVED]
- `_post(path, payload, timeout=300)` — out: `r.json()`, or on status >= 400 a dict `{"error": detail}` (JSON detail else `r.text[:400]`); never raises on HTTP errors. — mcp_server/polymath_mcp.py:95-102 [DERIVED]
- `_adapter(method, path, payload, timeout=180, headers)` — out: `r.json()` or exactly `{"error": detail, "status": r.status_code}` on >= 400, so agent sees 422 rejections / 409 not-terminal instead of a transport error. — mcp_server/polymath_mcp.py:401-411 [DERIVED]
- `polymath_search` — pre: `MR.normalize_mode(mode)` non-None else `MR.mode_error`; post: `MR.shape_search(_post("/chat/evidence", MR.search_body(query, corpus_id, m)), max_evidence)`; evidence rows only, no plan/answer. — mcp_server/polymath_mcp.py:126-134 [DERIVED]
- `polymath_explore` — post: `MR.shape_explore(_post("/chat/evidence", MR.explore_body(query, corpus_id, m, corpus_explorer)))`; EvidencePacket, no Polymath answer. — mcp_server/polymath_mcp.py:137-148 [DERIVED]
- `polymath_answer` — pre: `str(mode).strip().upper() == "ASK"` short-circuits to `_post("/ask", {"question", "corpus_id"})` before mode validation; unknown reasoning returns `{"error": ..., "status": 422, "styles": list(MR.REASONING_STYLES)}`; post: `_post("/chat", MR.answer_body(...))` with `model = model or _app_default_model()`. — mcp_server/polymath_mcp.py:151-163 [DERIVED]
- `polymath_compare` — modes default to all `MR.RETRIEVAL_MODES`, deduped via `list(dict.fromkeys(normal))`; POST `/compare` with `timeout=600`. — mcp_server/polymath_mcp.py:166-175 [DERIVED]
- `polymath_deep_research` — SSE stream POST `/research/deep`, header `Accept: text/event-stream`, `httpx.Timeout(1800.0, connect=10.0)`; unknown depth returns `{"error": ..., "status": 422, "depths": dict(MR.DEPTHS)}`; post: `MR.shape_deep(MR.parse_sse(lines), depth=d, mode=m)`. — mcp_server/polymath_mcp.py:178-202 [DERIVED]
- `polymath_query` (deprecated) — mode default `"HYBRID"`; `"ASK"` → POST `/ask`; `"VECTOR"` → `"FAST"`; else POST `/chat` with optional `latent`. — mcp_server/polymath_mcp.py:278-297 [DERIVED]
- `polymath_retrieve` (deprecated) — mode default `"HYBRID"`; `"VECTOR"` → `"FAST"`; POST `/retrieve`. — mcp_server/polymath_mcp.py:300-314 [DERIVED]
- `polymath_upload_file` / `polymath_upload_text` — POST multipart to `{BASE}/upload`, `timeout=300`; pre for file: `Path(path).expanduser()` exists else `{"error": f"file not found: {path}"}`; >= 400 → `{"error": r.text[:400]}`. — mcp_server/polymath_mcp.py:324-341, mcp_server/polymath_mcp.py:344-359 [DERIVED]
- `polymath_delete_corpus` / `polymath_delete_document` — DELETE `/corpora/{corpus_id}` / `/documents/{doc_id}` with `params={"confirm": confirm}`; pre: `confirm` must equal the id. delete_corpus returns `{"error": detail}` on >= 400; delete_document uses `r.raise_for_status()` (raises). — mcp_server/polymath_mcp.py:370-393 [DERIVED]
- `product_report_start` — post: remembers per-report upload token via `_REPORT_TOKENS.remember(rid, out, rid)`; `product_report_status` sends `_REPORT_TOKENS.headers(rid)` and re-remembers from the response. — mcp_server/polymath_mcp.py:246-260 [DERIVED]
- `run_governed_research` — out: `HG.prompt_text(adapter_id, seed)`. — mcp_server/polymath_mcp.py:517-520 [DERIVED]
- `main` — `--http [PORT]` (fallback `7300`) runs `streamable_http_app(stateless_http=True, transport_security=security)` under uvicorn on `127.0.0.1`; no arg → `server.run("stdio")`. — mcp_server/polymath_mcp.py:550-578 [DERIVED]

## effect surface
- Network (all via httpx to `BASE`): GET `/corpora` (119), POST `/chat/evidence` (134, 148), POST `/chat` (163, 297), POST `/ask` (155, 292), POST `/compare` (175), stream POST `/research/deep` (191-192), GET `/synthesizers` (111, 209), POST `/product/search` (220), POST `/supplier/parse` (227), report routes via `MR.REPORT_*` paths (246, 258, 269, 275), POST `/retrieve` (314), GET `/documents` (321), POST `/upload` (333, 351), GET `/semantic_readiness` (367), DELETE `/corpora/{id}` (375), DELETE `/documents/{id}` (390), `/adapter/*` (416, 421, 426, 441, 449, 457, 463, 470), `/supplier/*` (477, 482, 487, 493). — all [DERIVED]
- Env flags: `POLYMATH_API = "http://127.0.0.1:7200"` — mcp_server/polymath_mcp.py:63 [DERIVED]; `POLYMATH_MCP_API_KEY = ""` (read twice) — mcp_server/polymath_mcp.py:529, mcp_server/polymath_mcp.py:564 [DERIVED]
- Files: guide files read per request from repo root via `HG.FILES` — mcp_server/polymath_mcp.py:500-504 [DERIVED]; local upload file opened for bytes — mcp_server/polymath_mcp.py:329-338 [DERIVED]
- DB tables: none read/written directly (FACTS `tables_read`/`tables_written` empty). — FACTS [DERIVED]
- Subprocess: none; uvicorn imported in-process for `--http` — mcp_server/polymath_mcp.py:556, mcp_server/polymath_mcp.py:576 [DERIVED]

## invariants
INVARIANT: tools named in `MR.HIDDEN_TOOLS_B` are callable but excluded from `list_tools` — mcp_server/polymath_mcp.py:65-69 [DERIVED]
  fails-if: unregistered → old callers of `polymath_query`/`polymath_retrieve` break; listed → new agents use the deprecated surface.
INVARIANT: deprecated mode `"VECTOR"` maps to `"FAST"` in both `polymath_query` (293) and `polymath_retrieve` (310) — mcp_server/polymath_mcp.py:293,310 [DERIVED]
  fails-if: legacy VECTOR callers get mode errors.
INVARIANT: `polymath_answer` checks `ASK` before `MR.normalize_mode`; `polymath_query` checks `mode == "ASK"` — mcp_server/polymath_mcp.py:154-155,290-292 [DERIVED]
  fails-if: ASK falls into mode normalization and 422s.
INVARIANT: `_post` never raises on HTTP >= 400; always returns a dict containing `"error"` — mcp_server/polymath_mcp.py:97-101 [DERIVED]
  fails-if: agents receive transport exceptions instead of structured errors.
INVARIANT: `_adapter` >= 400 returns exactly `{"error": detail, "status": r.status_code}` — mcp_server/polymath_mcp.py:405-410 [DERIVED]
  fails-if: agent rejection-handling (422 fix-and-resubmit loop) breaks.
INVARIANT: with `POLYMATH_MCP_API_KEY` set → `enable_dns_rebinding_protection=False`; unset → `allowed_hosts == [f"127.0.0.1:{port}", f"localhost:{port}"]` — mcp_server/polymath_mcp.py:564-574 [DERIVED]
  fails-if: keyless server behind a tunnel gets 421; keyed server pinned to localhost rejects the tunnel hostname.
INVARIANT: delete `confirm` must equal the deleted id (`corpus_id` / `doc_id`) — mcp_server/polymath_mcp.py:371-374,386-388 [DERIVED]
  fails-if: accidental destructive delete of the wrong corpus/document.
INVARIANT: report tokens cached in memory keyed by report_id, sent as headers on every status call and refreshed from each response — mcp_server/polymath_mcp.py:237,249,258-260 [DERIVED]
  fails-if: status/compile calls lose auth after process restart (memory-only cache).
INVARIANT: default write model resolved through shared cache `_DEFAULT_MODEL` (`MR.DefaultModel()`); `httpx.HTTPError` → `None` — mcp_server/polymath_mcp.py:86,105-113 [DERIVED]
  fails-if: every answer/report call re-fetches `/synthesizers` or crashes offline.
INVARIANT: timeouts — `_get` 120 (90), `_post` default 300 (96), uploads 300 (337, 354), deletes 300 (376, 391), compare 600 (175), product_search 600 (222), deep research `1800.0`/connect `10.0` (192), `_adapter` default 180 (401) — mcp_server/polymath_mcp.py:90,96,175,192,222,337,354,376,391,401 [DERIVED]
  fails-if: long research runs truncated or short calls hang.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: every tool is an httpx call to `BASE` — 90, 96, 191, 333, 351, 375, 390, 404; env: `POLYMATH_API` 63, `POLYMATH_MCP_API_KEY` 529/564; filesystem: guide files read per request 503-504) [DERIVED]
idempotency: SAFE for read/answer tools (list/search/explore/answer/compare/models/status); UNSAFE for `polymath_delete_corpus` / `polymath_delete_document` (destructive, confirm-gated — 370-393) and uploads (re-ingesting the same file creates new ingestion runs — 324-359); `adapter_cancel` documented "terminal, idempotent" — mcp_server/polymath_mcp.py:460-463 [DERIVED]

## failure behaviour
- `_post`: >= 400 → best-effort JSON detail; `except Exception` SWALLOWED → `{"error": r.text[:400]}` (caller sees an error dict, never an exception) — mcp_server/polymath_mcp.py:98-101 [DERIVED]
- `polymath_delete_corpus`: same swallow at `{"error": r.text[:400]}` — mcp_server/polymath_mcp.py:380-381 [DERIVED]
- `polymath_deep_research`: >= 400 → read body, `except Exception` handled → `detail = r.text[:400]`; returns `{"error": f"{d_.get(error_code) or r.status_code}: ...", "status": r.status_code}` — mcp_server/polymath_mcp.py:193-200 [DERIVED]
- `_adapter`: >= 400 → `detail = r.text[:400]` on parse failure; returns `{"error": detail, "status": code}` — mcp_server/polymath_mcp.py:406-410 [DERIVED]
- `_get` / `polymath_delete_document`: `raise_for_status()` — `httpx.HTTPStatusError` propagates to the caller — mcp_server/polymath_mcp.py:91,392 [DERIVED]
- `_app_default_model`: `httpx.HTTPError` → `None` (answer proceeds with model=None) — mcp_server/polymath_mcp.py:110-112 [DERIVED]
- `polymath_models`: `httpx.HTTPError` → `{"error": f"{type(exc).__name__}: {exc}"[:300]}` — mcp_server/polymath_mcp.py:208-211 [DERIVED]
- `polymath_upload_file`: missing path → `{"error": f"file not found: {path}"}`; >= 400 → `{"error": r.text[:400]}` — mcp_server/polymath_mcp.py:330-340 [DERIVED]
- Validation errors: unknown mode → `MR.mode_error` (133, 147, 158, 175, 187); unknown reasoning → `{"error": ..., "status": 422, "styles": ...}` (159-161); unknown depth → `{"error": ..., "status": 422, "depths": ...}` (188-190) [DERIVED]
- HTTP mode auth: missing/wrong key → `JSONResponse({"error": "unauthorized"}, status_code=401)` — mcp_server/polymath_mcp.py:533-543 [DERIVED]

## dumb-code flags
- `r.text[:400]` literal duplicated 5×: 101, 198, 340, 381, 409 — no shared truncation helper. [DERIVED]
- Timeout values scattered as magic numbers: `120` (90), `300` (96, 337, 354, 376, 391), `600` (175, 222), `1800.0`/`10.0` (192), `180` (401). [DERIVED]
- Deprecated tools hardcode `mode: str = "HYBRID"` (282, 304) while new tools use `MR.DEFAULT_MODE` (130, 143, 152, 183) — same concept, two sources of truth. [DERIVED]
- `"VECTOR"`→`"FAST"` remap duplicated inline (293, 310), outside `MR`. [DERIVED]
- Port fallback `7300` hardcoded (555). [DERIVED]
- `POLYMATH_MCP_API_KEY` read from env in two separate places (529, 564). [DERIVED]
- `UPLOAD_BASE = "local"` magic string consumed by `MR.report_start_body` / `MR.report_status_path` (234, 244-245, 258); comment admits `--http` remote agents still get the local URL — use Server A for other machines (232-233). [DERIVED]
- ASK special-case implemented twice with different matching (`str(mode).strip().upper()` at 154 vs `mode.upper()` at 290). [DERIVED]

## refactor notes
- Tool names, parameters and descriptions are parity-pinned by `tests/contracts/test_mcp_adapter_parity.py` and `tests/contracts/test_mcp_agent_playbook.py` — any rename/re-sign breaks the contracts. — mcp_server/polymath_mcp.py:23-33 [DERIVED]
- All descriptive text comes from one shared copy (`polymath_shared/mcp_retrieval.py` as `MR`, `polymath_shared.adapter.harness_guide` as `HG`) — edit there, not here. — mcp_server/polymath_mcp.py:60-61,116-129 [DERIVED]
- Deprecated tools must stay registered-but-hidden (`MR.HIDDEN_TOOLS_B` filter) — old callers still call them. — mcp_server/polymath_mcp.py:65-69,14-15 [DERIVED]
- `_adapter` error shape `{"error": ..., "status": ...}` is what agent loops parse for 422 fix-and-resubmit; changing keys breaks rejection handling. — mcp_server/polymath_mcp.py:401-411,432-440 [DERIVED]
- Auth and transport security are coupled: key presence flips `enable_dns_rebinding_protection` and allowed hosts — changing one without the other either exposes a keyless server or blocks tunnels (421). — mcp_server/polymath_mcp.py:529-531,564-574 [DERIVED]
- Report token cache is memory-only, one user per stdio process — moving to multi-user HTTP mode invalidates the keyed-by-report assumption. — mcp_server/polymath_mcp.py:234-237 [DERIVED]

## VERIFY
```verify
grep -Fq 'http://127.0.0.1:7200' mcp_server/polymath_mcp.py
grep -Fq 'UPLOAD_BASE = "local"' mcp_server/polymath_mcp.py
grep -Fq 't.name not in MR.HIDDEN_TOOLS_B' mcp_server/polymath_mcp.py
grep -Fq 'stateless_http=True' mcp_server/polymath_mcp.py
grep -Fq 'httpx.Timeout(1800.0, connect=10.0)' mcp_server/polymath_mcp.py
test "$(grep -c -F 'POLYMATH_MCP_API_KEY' mcp_server/polymath_mcp.py)" -ge 3
test "$(grep -c -F 'r.text[:400]' mcp_server/polymath_mcp.py)" -ge 5
! grep -Fq 'enable_dns_rebinding_protection=True' mcp_server/polymath_mcp.py
```
