# unit: orchestrator/orchestrator/mcp_server.py
anchor: orchestrator/orchestrator/mcp_server.py:1-929

## purpose
POLYMATH-MCP-V2 — the v4 MCP server (streamable-http). An agent (Hermes, the claude.ai connector) drives the whole document lifecycle: upload → status until queryable → ask (orchestrator/orchestrator/mcp_server.py:1-6) [DERIVED].
Every tool is a thin, trimmed HTTP call to the orchestrator API on `127.0.0.1:7200`, so MCP cannot bypass the pipeline's gates (orchestrator/orchestrator/mcp_server.py:5-6) [DERIVED].
Auth is fail-closed: bearer key (header or `/k/<key>/mcp` path), and with no key configured the server answers `503` on `/mcp` instead of running open (orchestrator/orchestrator/mcp_server.py:24-30) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| list_corpora | tool | () -> dict | orchestrator/orchestrator/mcp_server.py:210-218 | — |
| list_documents | tool | (corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:222-226 | — |
| upload_document | tool | (path, corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:232-261 | — |
| upload_text | tool | (text, corpus_id, source_name="agent_upload.md") -> dict | orchestrator/orchestrator/mcp_server.py:265-286 | — |
| document_status | tool | (corpus_id, source_name=None, run_id=None) -> dict | orchestrator/orchestrator/mcp_server.py:292-304 | — |
| corpus_status | tool | (corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:308-324 | — |
| retrieve | tool (deprecated) | (query, corpus_id, mode="HYBRID", limit=10, latent=None, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:330-358 | — |
| capabilities | tool | () -> dict | orchestrator/orchestrator/mcp_server.py:362-366 | — |
| compile_plan | tool (deprecated) | (signal, corpus_id, limit=24, explore=True, communities=None) -> dict | orchestrator/orchestrator/mcp_server.py:375-389 | — |
| retrieve_evidence | tool (deprecated) | (query, corpus_id, limit=12, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:393-405 | — |
| ask | tool (deprecated) | (question, corpus_id, mode="HYBRID", latent=None, evidence=False) -> dict | orchestrator/orchestrator/mcp_server.py:409-430 | — |
| polymath_search | tool | (query, corpus_id, mode=MR.DEFAULT_MODE, max_evidence=12) -> dict | orchestrator/orchestrator/mcp_server.py:442-447 | — |
| polymath_explore | tool | (query, corpus_id, corpus_explorer=True, mode=MR.DEFAULT_MODE) -> dict | orchestrator/orchestrator/mcp_server.py:456-462 | — |
| polymath_answer | tool | (question, corpus_id, mode=MR.DEFAULT_MODE, reasoning="none", model=None, latent=None) -> dict | orchestrator/orchestrator/mcp_server.py:471-488 | — |
| polymath_compare | tool | (question, corpus_id, modes=None) -> dict | orchestrator/orchestrator/mcp_server.py:496-502 | — |
| polymath_deep_research | tool | (question, corpus_id, depth, mode, model) -> dict | orchestrator/orchestrator/mcp_server.py:511-520 | — |
| polymath_models | tool | () -> dict | orchestrator/orchestrator/mcp_server.py:525-526 | — |
| recent_queries | tool | (corpus_id, limit, since_h, kind) -> dict | orchestrator/orchestrator/mcp_server.py:532-544 | — |
| adapter_list / adapter_start / adapter_next / adapter_submit / adapter_status / adapter_result / adapter_cancel | tools | COGNITIVE-ADAPTER-V1 lifecycle (start(run_id ref) -> next(step) -> submit -> status/result/cancel) | orchestrator/orchestrator/mcp_server.py:551-623 | — |
| research_acquire | tool | (run_id, operation, target, site, search_intent_id, limit) -> dict | orchestrator/orchestrator/mcp_server.py:629-646 | — |
| supplier_search / supplier_product / supplier_freight / supplier_warehouses | tools (owner key only) | CJ dropship read-only lookups | orchestrator/orchestrator/mcp_server.py:653-686 | — |
| run_governed_research | tool | (adapter_id, seed) -> dict | orchestrator/orchestrator/mcp_server.py:710-712 | — |
| KeyInPath | class | (__init__, __call__) | orchestrator/orchestrator/mcp_server.py:725-742 | — |
| build_app | def | () -> ASGI app | orchestrator/orchestrator/mcp_server.py:745-904 | — |
| main | def | () -> None | orchestrator/orchestrator/mcp_server.py:919-924 | — |

## contracts

**_orch(method, path, **kw) -> dict** (orchestrator/orchestrator/mcp_server.py:142-160)
- in: `timeout` popped with default `180`; headers merged over `{"User-Agent": _CALLER_AGENT.get()}` (143, 149).
- pre: `_PRINCIPAL.get()` must not be `NOBODY`, else `{"error": "NO_PRINCIPAL: this call carries no authenticated principal (fail closed)", "status": 401}` (146-148).
- post: non-admin requests get `headers[P.PRINCIPAL_HEADER] = who.principal_id` (150-151).
- out: orchestrator JSON when status < 400; on >= 400 `{"error": detail, "status": code}` where detail is `r.json()["detail"]` else `r.text[:400]` (153-159).

**_orch_events(path, body, timeout=1800.0) -> list[tuple[str, dict]]** (orchestrator/orchestrator/mcp_server.py:163-185)
- in: POST body to a `text/event-stream` route (169, 173-174); connect timeout `10.0` (173).
- pre: principal != NOBODY else single `("error", {"error_code": "NO_PRINCIPAL", ...})` frame (166-168).
- out: frames parsed by `MR.parse_sse`; pre-stream refusal >= 400 becomes one `("error", {error_code: ... or "HTTP_<code>"})` frame (175-184).

**_trim_hit(h, max_chars=1400) -> dict** (orchestrator/orchestrator/mcp_server.py:188-204)
- out: keys `text, source_name, heading_path, doc_id, chunk_id, score, tier, arrival`; if cut, adds `truncated: True` and `full_length` = pre-cut length; keys with value `None` dropped (193-204).

**list_corpora() -> dict** (orchestrator/orchestrator/mcp_server.py:210-218)
- in/out: `GET /corpora` (214).
- post: non-admin principal sees only corpora with `corpus_id` in `who.corpus_ids` (215-217).

**upload_document(path, corpus_id) -> dict** (orchestrator/orchestrator/mcp_server.py:232-261)
- pre: `_CALLER_IS_LOCAL.get()` AND `_PRINCIPAL.get().is_admin`, else `REMOTE_PATH_UPLOAD_DISABLED` (`"status": 403`) returned BEFORE any filesystem access — "no existence oracle either" (240-241, 91-94).
- checks: `Path(path).expanduser().is_file()` else 404 `"file not found: {path}"` (242-244); suffix in `UPLOAD_EXTENSIONS` else 422 (245-247).
- out: multipart `POST {ORCH}/upload` (248-251); success adds `out["next"] = "document_status(...) until query_ready"` (259-260); run_id is content-addressed — same bytes return the existing run with `already_exists` true; content in another corpus → 409 `CROSS_CORPUS_CONTENT_COLLISION` (234-238).

**upload_text(text, corpus_id, source_name="agent_upload.md") -> dict** (orchestrator/orchestrator/mcp_server.py:265-286)
- pre: `source_name` suffix in `UPLOAD_EXTENSIONS` else 422 (270-272).
- out: `POST {ORCH}/upload` with `(source_name, text.encode("utf-8"), "text/markdown")` (273-276); same `next` hint (284-285).

**document_status(corpus_id, source_name=None, run_id=None) -> dict** (orchestrator/orchestrator/mcp_server.py:292-304)
- out: `GET /status` with `corpus_id` plus optional `run_id`/`source_name` (299-304).

**corpus_status(corpus_id) -> dict** (orchestrator/orchestrator/mcp_server.py:308-324)
- out: `GET /corpora` row matched by `corpus_id` OR `name` (312-317) plus `GET /semantic_readiness` (319-320); no match → `{"error": ..., "status": 404, "semantic_readiness": ...}` (321-323).

**polymath_search(query, corpus_id, mode=MR.DEFAULT_MODE, max_evidence=12) -> dict** (orchestrator/orchestrator/mcp_server.py:442-447)
- pre: `MR.normalize_mode(mode)` not None else `MR.mode_error(mode)` (443-445).
- out: `POST /chat/evidence` with `MR.search_body(query, corpus_id, m)` → `MR.shape_search(out, max_evidence)` (446-447).

**polymath_explore(query, corpus_id, corpus_explorer=True, mode=MR.DEFAULT_MODE) -> dict** (orchestrator/orchestrator/mcp_server.py:456-462)
- out: `POST /chat/evidence` with `MR.explore_body(...)` → `MR.shape_explore(out)` (461-462).

**polymath_answer(question, corpus_id, mode, reasoning="none", model=None, latent=None) -> dict** (orchestrator/orchestrator/mcp_server.py:471-488)
- pre: valid mode (474-476); `MR.normalize_reasoning(reasoning)` else `{"error": "unknown reasoning style ...", "status": 422, "styles": [...]}` (477-479).
- out: `POST /chat` with `MR.answer_body(...)`; lists `evidence`/`chunks`/`bundle` cut to first 12 items at 600 chars via `_trim_hit(h, 600)` (480-487).

**polymath_compare(question, corpus_id, modes=None) -> dict** (orchestrator/orchestrator/mcp_server.py:496-502)
- pre: every mode normalizes or `MR.mode_error` (497-500).
- out: `POST /compare` with `MR.compare_body(question, corpus_id, list(dict.fromkeys(normal)))`, `timeout=600` → `MR.shape_compare(out)` (501-502).

## effect surface

| effect | detail | anchor |
|---|---|---|
| network | `httpx.AsyncClient` to `ORCH` (default `http://127.0.0.1:7200`) | orchestrator/orchestrator/mcp_server.py:152, 173, 248, 273 |
| network routes | `GET /corpora` (214, 312), `GET /documents` (226), `POST /upload` (250, 274), `GET /status` (304), `GET /semantic_readiness` (319-320), `POST /retrieve` (347, 401), `POST /retrieve/plan` (384), `POST /chat` (419, 480), `POST /chat/evidence` (446, 461), `POST /compare` (501), `GET /capabilities` (366) | orchestrator/orchestrator/mcp_server.py:214-501 |
| files | upload_document reads caller-supplied host path: `Path(path).expanduser()`, `p.open("rb")` | orchestrator/orchestrator/mcp_server.py:242-250 |
| files | `import tempfile` present; no use visible in shown lines 1-509 | orchestrator/orchestrator/mcp_server.py:47 |
| env | `POLYMATH_ORCH_URL = "http://127.0.0.1:7200"` | orchestrator/orchestrator/mcp_server.py:65 |
| env | `POLYMATH_MCP_PORT = "8930"` | orchestrator/orchestrator/mcp_server.py:66 |
| env | `POLYMATH_MCP_API_KEY = ""` | orchestrator/orchestrator/mcp_server.py:67 |
| env | `POLYMATH_MCP_PUBLIC_HOST = "mcp.kingsleylab.xyz"` | orchestrator/orchestrator/mcp_server.py:68 |
| env | `$POLYMATH_MCP_PRINCIPALS_FILE` (consumed by mcp_principals per docstring) | orchestrator/orchestrator/mcp_server.py:26 |
| DB / Qdrant | none in this unit — all persistence flows through the orchestrator HTTP API ("thin, trimmed call to the orchestrator API") | orchestrator/orchestrator/mcp_server.py:5-6 |

## invariants
INVARIANT: upload_document reachability == `_CALLER_IS_LOCAL.get() and _PRINCIPAL.get().is_admin`, else 403 before any fs access — orchestrator/orchestrator/mcp_server.py:240-241 [DERIVED]
  fails-if: a remote/edge caller gains a host-file existence oracle or file upload.
INVARIANT: outgoing `_orch`/`_orch_events` principal != `NOBODY` (`prn_nobody`), else 401 `NO_PRINCIPAL` — orchestrator/orchestrator/mcp_server.py:100, 146-148, 166-168 [DERIVED]
  fails-if: an unauthenticated call is attributed to the sentinel principal.
INVARIANT: `_CALLER_IS_LOCAL` default == False (contextvar) — orchestrator/orchestrator/mcp_server.py:88-90 [DERIVED]
  fails-if: a lost request context is treated as local and serves host paths.
INVARIANT: non-admin outgoing headers carry `P.PRINCIPAL_HEADER` = `who.principal_id` — orchestrator/orchestrator/mcp_server.py:150-151, 170-171 [DERIVED]
  fails-if: orchestrator attributes a principal's actions to the owner key.
INVARIANT: list_corpora result for non-admin ⊆ `who.corpus_ids` — orchestrator/orchestrator/mcp_server.py:215-217 [DERIVED]
  fails-if: a principal sees corpora outside its scopes.
INVARIANT: upload_text `source_name` suffix ∈ `UPLOAD_EXTENSIONS` == `{".md", ".txt", ".html", ".pdf", ".epub", ".docx"}` — orchestrator/orchestrator/mcp_server.py:69, 270-272 [DERIVED]
  fails-if: ingestion of file types the pipeline cannot parse.
INVARIANT: `_trim_hit` text length ≤ `max_chars` (default 1400), `truncated: True` iff cut — orchestrator/orchestrator/mcp_server.py:188-204 [DERIVED]
  fails-if: agents silently lose text with no truncation marker.
INVARIANT: every query tool takes `corpus_id` (V2 scope rule; docstring: unscoped path 20 s + abstain vs scoped 3 s + 16 citations) — orchestrator/orchestrator/mcp_server.py:31-33, 442, 456, 471, 496 [DERIVED]
  fails-if: reintroduces the slow, abstaining all-corpora path.

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `httpx.AsyncClient` at orchestrator/orchestrator/mcp_server.py:152, 173, 248, 273; env-sourced config at :65-68; per-request contextvars at :90-102).
idempotency: SAFE for reads (pure proxies, e.g. polymath_search :446-447); upload_document is content-addressed — same bytes return the existing run, `already_exists` true (:234-236); adapter_cancel documented "terminal, idempotent" (:621-623). adapter_start durability/idempotency not visible in the shown material.

## failure behaviour
- Broad `except Exception: detail = r.text[:400]` (or `raw[:400]`) at :157, :179, :255, :280 — only the JSON-detail parse is swallowed; caller still sees `{"error": detail, "status": >=400}` (:153-159, :252-257, :277-282) [DERIVED].
- `_orch_events` pre-stream refusal >= 400 → single `("error", {error_code: d.get("error_code") or "HTTP_<code>"})` frame (:175-182) [DERIVED].
- No key configured → `503` on `/mcp` (fail-closed, V2) (:28-30) [DERIVED].
- Principal gate outcomes per docstring: `401` unknown/revoked key, `403` not permitted, `429` over rate (:27) [DERIVED].
- upload_document error codes: 403 `REMOTE_PATH_UPLOAD_DISABLED` (:91-94, :240-241), 404 file not found (:243-244), 422 unsupported extension (:245-247); cross-corpus duplicate → 409 `CROSS_CORPUS_CONTENT_COLLISION` (:238-239) [DERIVED].
- polymath_answer: 422 `unknown reasoning style` with `styles` list (:477-479); invalid modes → `MR.mode_error(mode)` (:443-445, 458-460, 474-476, 498-500) [DERIVED].

## dumb-code flags
- Three different trim budgets under the same D-02 rule: `_trim_hit` default `1400` (:188), `_trim_rows`/`MR.trim_rows` at 1,200 characters (:369-371), evidence lists in ask/polymath_answer at `600` (:428, :487) [DERIVED].
- The >=400 detail-extraction block is copy-pasted 4×: :154-159, :175-182, :252-257, :277-282 [DERIVED].
- Mode vocabulary mismatch: docstring lists `FAST | HYBRID | GRAPH | WILDCARD | GNN` (:21) while deprecated tools speak `FAST | HYBRID | GRAPH | EXPLORE` (:335, :341-342, :400) [DERIVED].
- Timeout ladder: `_orch` default `180` (:143), uploads `600` (:248, :273), compare `600` (:501), SSE `1800.0` with `connect=10.0` (:163, :173) — magic numbers, no shared constant [DERIVED].
- `MAX_GATED_BODY = 2 * 1024 * 1024` (2 MiB) bare literal (:105) [DERIVED].
- Sentinel literal `"prn_nobody"` shared implicitly with mcp_principals (:100) [DERIVED].
- `import re` (:44) and `import tempfile` (:47) have no visible use in lines 1-509; any use lives in 510-929 — check before removing [INFERRED: usage absent from the shown source range].
- Tool-name literals split across two sites: `_TOOL_NAMES` at :907 starts `["polymath_compare", "polymath_deep_research", "polymath_models", "adapter_list", ...]` while `polymath_search`/`polymath_explore`/`polymath_answer` literals appear at :915 — partitioning rationale not visible in shown source [INFERRED: two disjoint literal groups].

## refactor notes
- Orchestrator route contract: renaming `/corpora`, `/documents`, `/upload`, `/status`, `/semantic_readiness`, `/retrieve`, `/retrieve/plan`, `/chat`, `/chat/evidence`, `/compare`, `/capabilities` breaks this file — anchors :214, :226, :250, :274, :304, :319, :347, :384, :401, :419, :446, :461, :480, :501, :366 [DERIVED].
- Shared-module coupling: `polymath_shared.mcp_retrieval` (`MR.normalize_mode/mode_error/search_body/explore_body/answer_body/compare_body/shape_search/shape_explore/shape_compare/trim_rows/parse_sse/HIDDEN_TOOLS_A/RETRIEVAL_MODES/DEFAULT_MODE/REASONING_STYLES/DEPTHS`) at :60, :118, :184, :370-371, :434, :443-502; `mcp_principals` (`P.Principal/PRINCIPAL_HEADER/store_from_env/RateLimiter`) at :59, :100-104, :150-151, :170-171; `polymath_shared.adapter.harness_guide` at :61 [DERIVED].
- Do NOT reorder upload_document: the local+admin check at :240-241 must stay before `Path(path)` at :242 — the ordering is the "no existence oracle" guarantee [DERIVED].
- Deprecation contract: deprecated tools (`retrieve`, `compile_plan`, `retrieve_evidence`, `ask`) stay callable but unlisted via `_ListedMCPServer.list_tools` filtering `MR.HIDDEN_TOOLS_A` (:113-118) — removing that filter re-exposes them to agents [DERIVED].
- `REMOTE_PATH_UPLOAD_DISABLED` error string (:91-94) is a wire contract remote agents match on [DERIVED].
- Auth surface: bearer header or `/k/<key>/mcp` with `KeyInPath` rewriting to the same header (:24-25, :725-742) — KeyInPath must keep producing the identical header [DERIVED].
- `build_app` wires the FAIL-CLOSED bearer gate + principals + rate limiter (:745-904, :100-105); `_TOOL_NAMES` at :907 sits just past its end and is likely consumed by it — verify before moving [INFERRED: adjacency and naming].

## VERIFY
```verify
grep -Fq 'prn_nobody' orchestrator/orchestrator/mcp_server.py
grep -Fq 'max_chars: int = 1400' orchestrator/orchestrator/mcp_server.py
grep -Fq 'timeout: float = 1800.0' orchestrator/orchestrator/mcp_server.py
grep -Fq 'text/event-stream' orchestrator/orchestrator/mcp_server.py
grep -Fq 'CROSS_CORPUS_CONTENT_COLLISION' orchestrator/orchestrator/mcp_server.py
grep -Fq 'agent_upload.md' orchestrator/orchestrator/mcp_server.py
test "$(grep -c -F 'httpx.AsyncClient' orchestrator/orchestrator/mcp_server.py)" -ge 4
```
