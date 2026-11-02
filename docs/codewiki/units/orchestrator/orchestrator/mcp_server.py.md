# unit: orchestrator/orchestrator/mcp_server.py
anchor: orchestrator/orchestrator/mcp_server.py:1-987

## purpose
POLYMATH-MCP-V2: the v4 MCP server (streamable-http). An agent (Hermes, the claude.ai connector) drives the whole document lifecycle through it: upload → status until queryable → search/explore/answer. Every tool is a thin, trimmed HTTP call to the orchestrator API (default `http://127.0.0.1:7200`), so MCP can never bypass the pipeline's gates — orchestrator/orchestrator/mcp_server.py:1-6 [DERIVED].
Auth is fail-closed: bearer key or `/k/<key>/mcp` path key, per-principal scopes; no key configured → 503 on `/mcp`; every query tool requires `corpus_id` — orchestrator/orchestrator/mcp_server.py:34-43 [DERIVED].

## public surface
Callers named in the module docstring: Hermes, the claude.ai connector (orchestrator/orchestrator/mcp_server.py:2-3). No FACTS importers, so "used by" is "—".

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| list_corpora | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:222-234 | — |
| list_documents | mcp tool | (corpus_id: str) -> dict | orchestrator/orchestrator/mcp_server.py:237-242 | — |
| upload_document | mcp tool | (path: str, corpus_id: str) -> dict | orchestrator/orchestrator/mcp_server.py:248-277 | — |
| upload_text | mcp tool | (text, corpus_id, source_name="agent_upload.md") -> dict | orchestrator/orchestrator/mcp_server.py:281-305 | — |
| document_status | mcp tool | (corpus_id, source_name=None, run_id=None) -> dict | orchestrator/orchestrator/mcp_server.py:310-323 | — |
| corpus_status | mcp tool | (corpus_id: str) -> dict | orchestrator/orchestrator/mcp_server.py:326-343 | — |
| retrieve | mcp tool (hidden, deprecated) | (query, corpus_id, mode="HYBRID", limit=10, latent=None, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:348-377 | — |
| capabilities | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:380-385 | — |
| compile_plan | mcp tool (hidden, deprecated) | (signal, corpus_id, limit=24, explore=True, communities=None) -> dict | orchestrator/orchestrator/mcp_server.py:393-408 | — |
| retrieve_evidence | mcp tool (hidden, deprecated) | (query, corpus_id, limit=12, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:411-424 | — |
| ask | mcp tool (hidden, deprecated) | (question, corpus_id, mode="HYBRID", latent=None, evidence=False) -> dict | orchestrator/orchestrator/mcp_server.py:427-449 | — |
| polymath_search | mcp tool | (query, corpus_id, mode=MR.DEFAULT_MODE, max_evidence=12) -> dict | orchestrator/orchestrator/mcp_server.py:461-466 | — |
| polymath_explore | mcp tool | (query, corpus_id, corpus_explorer=True, mode=MR.DEFAULT_MODE) -> dict | orchestrator/orchestrator/mcp_server.py:475-481 | — |
| polymath_answer | mcp tool | (question, corpus_id, mode=MR.DEFAULT_MODE, reasoning="none", model=None, latent=None) -> dict | orchestrator/orchestrator/mcp_server.py:495-513 | — |
| polymath_compare | mcp tool | (question, corpus_id, modes) -> dict | orchestrator/orchestrator/mcp_server.py:521-527 | — |
| polymath_deep_research | mcp tool | (question, corpus_id, depth, mode, model) -> dict | orchestrator/orchestrator/mcp_server.py:536-545 | — |
| polymath_models | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:550-551 | — |
| product_search | mcp tool | (message, corpus_id, geography, model, hypotheses, limit_per_hypothesis) -> dict | orchestrator/orchestrator/mcp_server.py:558-565 | — |
| supplier_parse | mcp tool | (site, raw_text) -> dict | orchestrator/orchestrator/mcp_server.py:569-570 | — |
| product_report_start | mcp tool | (message, corpus_id, products, channels, ship_to, max_products) -> dict | orchestrator/orchestrator/mcp_server.py:595-604 | — |
| product_report_status | mcp tool | (report_id) -> dict | orchestrator/orchestrator/mcp_server.py:608-616 | — |
| product_report_compile | mcp tool | (report_id, verdicts) -> dict | orchestrator/orchestrator/mcp_server.py:620-625 | — |
| product_report_list | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:629-630 | — |
| recent_queries | mcp tool | (corpus_id, limit, since_h, kind) -> dict | orchestrator/orchestrator/mcp_server.py:636-648 | — |
| adapter_list | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:655-660 | — |
| adapter_start | mcp tool | (adapter_id, input, request_options) -> dict | orchestrator/orchestrator/mcp_server.py:664-666 | — |
| adapter_next | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:670-671 | — |
| adapter_submit | mcp tool | (run_id, step_id, payload, agent_identity, model, kind) -> dict | orchestrator/orchestrator/mcp_server.py:675-688 | — |
| adapter_status | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:692-694 | — |
| adapter_result | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:698-702 | — |
| adapter_cancel | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:706-708 | — |
| research_acquire | mcp tool | (run_id, operation, target, site, search_intent_id, limit) -> dict | orchestrator/orchestrator/mcp_server.py:714-717 | — |
| supplier_search | mcp tool | (query, source, limit) -> dict | orchestrator/orchestrator/mcp_server.py:725-726 | — |
| supplier_product | mcp tool | (product_id) -> dict | orchestrator/orchestrator/mcp_server.py:730-731 | — |
| supplier_freight | mcp tool | (variant_id, country, quantity, from_country) -> dict | orchestrator/orchestrator/mcp_server.py:735-737 | — |
| supplier_warehouses | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:741-742 | — |
| run_governed_research | def | (adapter_id, seed) -> dict | orchestrator/orchestrator/mcp_server.py:766-768 | — |
| _ListedMCPServer | class(MCPServer) | list_tools() filters MR.HIDDEN_TOOLS_A | orchestrator/orchestrator/mcp_server.py:123-128 | — |
| KeyInPath | class | __init__, __call__ | orchestrator/orchestrator/mcp_server.py:781-798 | — |
| build_app | def | () -> ASGI app (FastMCP streamable-http + fail-closed bearer gate) | orchestrator/orchestrator/mcp_server.py:801-960 | — |
| main | def | () -> None | orchestrator/orchestrator/mcp_server.py:977-982 | — |

`run_governed_research` is absent from FACTS.mcp_tools while every other tool there is listed — it may be registered outside the visible source [INFERRED: static tool list omits it].

## contracts

**upload_document(path, corpus_id)** — orchestrator/orchestrator/mcp_server.py:248-277
- pre: `_CALLER_IS_LOCAL.get()` AND `_PRINCIPAL.get().is_admin`, else returns `REMOTE_PATH_UPLOAD_DISABLED` (403) *before any filesystem access* — orchestrator/orchestrator/mcp_server.py:256-257 [DERIVED]
- pre: file exists (else 404 `file not found`); suffix in `UPLOAD_EXTENSIONS` (else 422) — orchestrator/orchestrator/mcp_server.py:259-263 [DERIVED]
- effect: multipart POST `{ORCH}/upload`, timeout 600 — orchestrator/orchestrator/mcp_server.py:264-267 [DERIVED]
- post: `out["next"]` = `document_status(corpus_id=..., source_name=...) until query_ready`; run_id is content-addressed (same bytes → existing run, `already_exists` true; content in another corpus → 409 `CROSS_CORPUS_CONTENT_COLLISION`) — orchestrator/orchestrator/mcp_server.py:275-276, 249-254 [DERIVED]

**upload_text(text, corpus_id, source_name="agent_upload.md")** — orchestrator/orchestrator/mcp_server.py:281-305
- pre: `source_name` suffix in `UPLOAD_EXTENSIONS` (else 422 `source_name needs one of ...`); a principal must be set (else `NO_PRINCIPAL`) — orchestrator/orchestrator/mcp_server.py:286-291 [DERIVED]
- effect: POST `{ORCH}/upload` stamped with `_trusted_headers()` (F15: upload runs as the principal, not the owner) — orchestrator/orchestrator/mcp_server.py:289-295 [DERIVED]
- post: `out["next"]` guidance added — orchestrator/orchestrator/mcp_server.py:303-304 [DERIVED]

**list_corpora()** — orchestrator/orchestrator/mcp_server.py:225-234
- effect: GET `/corpora` — orchestrator/orchestrator/mcp_server.py:226 [DERIVED]
- post: non-admin without `"*"` in `who.corpus_ids` gets `out["corpora"]` filtered to its own ids (defence in depth) — orchestrator/orchestrator/mcp_server.py:231-233 [DERIVED]

**polymath_search(query, corpus_id, mode=MR.DEFAULT_MODE, max_evidence=12)** — orchestrator/orchestrator/mcp_server.py:461-466
- pre: `MR.normalize_mode(mode)` non-None, else `MR.mode_error(mode)` — orchestrator/orchestrator/mcp_server.py:462-464 [DERIVED]
- effect: POST `/chat/evidence` with `MR.search_body(query, corpus_id, m)`; no planning, no answer — orchestrator/orchestrator/mcp_server.py:465, 456-460 [DERIVED]
- out: `MR.shape_search(out, max_evidence)` — orchestrator/orchestrator/mcp_server.py:466 [DERIVED]

**polymath_explore(query, corpus_id, corpus_explorer=True, mode=MR.DEFAULT_MODE)** — orchestrator/orchestrator/mcp_server.py:475-481
- pre: mode normalized, else `MR.mode_error(mode)` — orchestrator/orchestrator/mcp_server.py:477-479 [DERIVED]
- effect: POST `/chat/evidence` with `MR.explore_body(query, corpus_id, m, corpus_explorer)` — orchestrator/orchestrator/mcp_server.py:480 [DERIVED]
- out: `MR.shape_explore(out)` — versioned EvidencePacket, roles DIRECT/COMPLEMENTARY/DIVERGENT, CA4 grades, no Polymath answer — orchestrator/orchestrator/mcp_server.py:481, 469-474 [DERIVED]

**polymath_answer(question, corpus_id, mode, reasoning="none", model=None, latent=None)** — orchestrator/orchestrator/mcp_server.py:495-513
- pre: mode normalized; `reasoning` in `MR.REASONING_STYLES`, else `{"error": ..., "status": 422, "styles": list(MR.REASONING_STYLES)}` — orchestrator/orchestrator/mcp_server.py:498-503 [DERIVED]
- in: `model=None` resolves via `_app_default_model()` (GET `/synthesizers`, cached `MR.DEFAULT_MODEL_TTL_S`) — orchestrator/orchestrator/mcp_server.py:504, 487-491 [DERIVED]
- out: `slim = dict(out)`; lists under `("evidence", "chunks", "bundle")` trimmed — orchestrator/orchestrator/mcp_server.py:506-511 [DERIVED]

**adapter_cancel(run_id)** — orchestrator/orchestrator/mcp_server.py:706-708
- post: terminal, idempotent; accepted work kept; returns AdapterRunStatusV1 — doc in FACTS, orchestrator/orchestrator/mcp_server.py:706-708 [DERIVED]

**corpus_status(corpus_id)** — orchestrator/orchestrator/mcp_server.py:327-343
- effect: GET `/corpora` + GET `/semantic_readiness` — orchestrator/orchestrator/mcp_server.py:331, 338-339 [DERIVED]
- out: `{"corpus": row, "semantic_readiness": readiness}`; missing corpus → `{"error": ..., "status": 404, "semantic_readiness": ...}` — orchestrator/orchestrator/mcp_server.py:340-343 [DERIVED]

## effect surface
- Network (httpx.AsyncClient to `ORCH`): orchestrator/orchestrator/mcp_server.py:164, 182, 264, 292 [DERIVED]
  - routes: `/corpora` (226, 331), `/documents` (242), `/upload` (266, 293), `/status` (323), `/semantic_readiness` (338-339), `/retrieve` (366, 418), `/retrieve/plan` (403), `/chat` (438, 505), `/chat/evidence` (465, 480), `/capabilities` (385), `/synthesizers` (491), `POST /product/search`, `POST /supplier/parse`, `POST /product/report/start`, `GET /product/report/{id}/status`, `POST /product/report/{id}/compile`, `GET /product/reports` (docstring 21-28)
- Env: `POLYMATH_ORCH_URL='http://127.0.0.1:7200'` (75), `POLYMATH_MCP_PORT='8930'` (76), `POLYMATH_MCP_API_KEY=''` (77), `POLYMATH_MCP_PUBLIC_HOST='mcp.kingsleylab.xyz'` (78); principals file via `P.store_from_env(API_KEY)` (113; `$POLYMATH_MCP_PRINCIPALS_FILE` named at docstring line 36) — orchestrator/orchestrator/mcp_server.py:75-78,113 [DERIVED]
- Files: reads a host-local file in `upload_document` (`Path(path).expanduser()`, `p.open("rb")`) — orchestrator/orchestrator/mcp_server.py:258-265 [DERIVED]
- Postgres: no tables read/written in this unit (FACTS `tables_read`/`tables_written` empty); all persistence happens behind the orchestrator HTTP API [INFERRED: every tool proxies `_orch`]

## invariants
INVARIANT: `_PRINCIPAL` default == `NOBODY` (`principal_id="prn_nobody"`) and `_trusted_headers` returns None for NOBODY — orchestrator/orchestrator/mcp_server.py:110-111, 150-152 [DERIVED]
  fails-if: an unauthenticated request would act as a real principal (fail-closed gate broken).
INVARIANT: `_CALLER_IS_LOCAL` default == False — orchestrator/orchestrator/mcp_server.py:100 [DERIVED]
  fails-if: lost host context grants host-filesystem access instead of refusing.
INVARIANT: `_is_local_caller` == (host in `_LOOPBACK_HOSTS`) AND (none of `_EDGE_HEADERS` present) — orchestrator/orchestrator/mcp_server.py:118-120 [DERIVED]
  fails-if: a tunneled request with a loopback Host header counts as local.
INVARIANT: upload_document requires `_CALLER_IS_LOCAL` AND `is_admin`, checked before any filesystem access — orchestrator/orchestrator/mcp_server.py:256-257 [DERIVED]
  fails-if: remote caller gains a host-path existence oracle / file upload.
INVARIANT: trim cut points: `_trim_hit` = 1400 chars, `_trim_rows` = 1200 chars, `ask` evidence = 600 chars / first 12 items — orchestrator/orchestrator/mcp_server.py:197, 389, 447-448 [DERIVED]
  fails-if: token budgets drift between tools.
INVARIANT: timeouts: `_orch` default 180 < uploads 600 < `_orch_events` default 1800.0 — orchestrator/orchestrator/mcp_server.py:160, 264, 292, 175 [DERIVED]
  fails-if: long SSE runs or slow uploads get cut at the wrong boundary.
INVARIANT: `UPLOAD_EXTENSIONS` == `{".md", ".txt", ".html", ".pdf", ".epub", ".docx"}`, enforced by both upload tools — orchestrator/orchestrator/mcp_server.py:79, 261-263, 286-288 [DERIVED]
  fails-if: one upload path accepts a type the other rejects.
INVARIANT: `list_tools` output excludes every name in `MR.HIDDEN_TOOLS_A`; deprecated tools (`retrieve`, `compile_plan`, `retrieve_evidence`, `ask`) stay callable — orchestrator/orchestrator/mcp_server.py:127-128, docstring line 30 [DERIVED]
  fails-if: old callers break (removal) or new agents adopt deprecated tools (unhidden).
INVARIANT: non-admin without `ALL_LIBRARIES = "*"` sees only corpora whose `corpus_id` is in `who.corpus_ids` — orchestrator/orchestrator/mcp_server.py:219, 231-233 [DERIVED]
  fails-if: principal sees another principal's private library.
INVARIANT: `MAX_GATED_BODY` == 2 * 1024 * 1024 bytes — orchestrator/orchestrator/mcp_server.py:115 [DERIVED]
  fails-if: gate rejects legitimate bodies or admits oversized ones.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `httpx.AsyncClient` at 164/182/264/292; env reads at import 75-78; per-request contextvars 100-112; `_DEFAULT_MODEL` cached with `MR.DEFAULT_MODEL_TTL_S` 484-491) [DERIVED]
idempotency: SAFE (uploads are content-addressed — same bytes return the existing run with `already_exists` true, docstring 249-251; `adapter_cancel` documented idempotent, 706-708; reads are stateless proxies) [DERIVED]

## failure behaviour
- `except Exception` around `r.json().get("detail")` in `_orch` (167-170), `upload_document` (268-272), `upload_text` (296-300): swallows JSON-parse failure, `detail` falls back to `r.text[:400]`; caller sees `{"error": detail, "status": r.status_code}` (171) [DERIVED]
- `_orch_events` variant: `json.loads(raw)` → `raw[:400].decode("utf-8", "replace")`; >=400 becomes one `("error", {"error_code": ... or f"HTTP_{r.status_code}", ...})` frame (184-191) [DERIVED]
- No principal: `_orch` returns `dict(NO_PRINCIPAL)` (161-163); `_orch_events` returns an `("error", {"error_code": "NO_PRINCIPAL", ...})` frame (178-180) [DERIVED]
- Codes: 401 `NO_PRINCIPAL` (142); 401 unknown/revoked key, 403 not permitted, 429 over rate (docstring 36-37); 503 on `/mcp` with no key configured — FAIL-CLOSED V2 (docstring 38-40); 403 `REMOTE_PATH_UPLOAD_DISABLED` (101-104); 404 file not found (260); 404 corpus not found (341); 422 unsupported extension (262-263); 422 bad `source_name` (287); 422 unknown reasoning style (501-503); 409 `CROSS_CORPUS_CONTENT_COLLISION` (docstring 253) [DERIVED]

## dumb-code flags
- Three different "slim" cut sizes: 1400 (197) vs 1200 via `MR.trim_rows` (389) vs 600 + 12 items in `ask` (447-448) [DERIVED]
- Deprecated `retrieve`/`ask` hard-code `mode: str = "HYBRID"` (349, 428) while canonical tools use `MR.DEFAULT_MODE` (461, 475, 495) — defaults can disagree if `MR.DEFAULT_MODE` changes [DERIVED]
- Error-detail parse block duplicated verbatim three times (`detail = r.json().get("detail")` / except → `r.text[:400]`) at 167-170, 268-272, 296-300; a fourth variant at 186-189 [DERIVED]
- `_orch_events` re-types the NO_PRINCIPAL message string inline (180) instead of reusing the `NO_PRINCIPAL` dict (142) — duplicated literal [DERIVED]
- `f"127.0.0.1:{PORT}"` / `f"localhost:{PORT}"` built twice: in `_ALLOWED_HOSTS` (81) and again in `_LOOPBACK_HOSTS` (98) [DERIVED]
- `sorted(UPLOAD_EXTENSIONS)` recomputed inside two error strings (263, 287) [DERIVED]
- Magic numbers: 180 (160), 1800.0 (175), 600 (264, 292), 400-char error cut (170, 272, 299), 12 items (448) [DERIVED]

## refactor notes
- Shared contract text lives in `polymath_shared.mcp_retrieval` (`MR.playbook`, `MR.HIDDEN_TOOLS_A`, `MR.RETRIEVAL_MODES`, `MR.DEFAULT_MODE`, `MR.trim_rows`, `MR.search_body`/`explore_body`/`answer_body`, `MR.shape_search`/`shape_explore`, `MR.DefaultModel`) and is shared with Server B — the playbook/descriptions must not fork — orchestrator/orchestrator/mcp_server.py:69-70, docstring 31-32 [DERIVED]
- Deprecated tools must stay callable for existing callers; hide-only via `MR.HIDDEN_TOOLS_A` — orchestrator/orchestrator/mcp_server.py:123-128, 348-449 [DERIVED]
- Every new orchestrator call must go through `_orch`/`_orch_events` so `_trusted_headers` stamps the principal (F15: uploads/queries otherwise run as the owner) — orchestrator/orchestrator/mcp_server.py:145-156 [DERIVED]
- `build_app` hard-codes `_TOOL_NAMES` (963) and references `polymath_*` names again near 973 (FACTS constants/collections) — renaming any tool requires updating those lists — orchestrator/orchestrator/mcp_server.py:963, 973 [DERIVED]
- `KeyInPath` (`/k/<key>/mcp`) exists because the claude.ai connector cannot send headers; removing it breaks that connector — orchestrator/orchestrator/mcp_server.py:34-36, 781-798 [DERIVED]
- `ORCH`/`PORT`/`API_KEY`/`PUBLIC_HOST` are read once at import — env changes require a process restart — orchestrator/orchestrator/mcp_server.py:75-78 [DERIVED]

## VERIFY
```verify
grep -Fq 'UPLOAD_EXTENSIONS = {".md", ".txt", ".html", ".pdf", ".epub", ".docx"}' orchestrator/orchestrator/mcp_server.py
grep -Fq '{"error": "NO_PRINCIPAL: this call carries no authenticated principal (fail closed)", "status": 401}' orchestrator/orchestrator/mcp_server.py
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'def _trim_hit(h: dict, max_chars: int = 1400) -> dict:' orchestrator/orchestrator/mcp_server.py
grep -Fq 'os.environ.get("POLYMATH_MCP_PORT", "8930")' orchestrator/orchestrator/mcp_server.py
test "$(grep -c -F 'r.text[:400]' orchestrator/orchestrator/mcp_server.py)" -ge 3
! grep -Fq 'POLYMATH_MCP_PORT", "9999"' orchestrator/orchestrator/mcp_server.py
```
