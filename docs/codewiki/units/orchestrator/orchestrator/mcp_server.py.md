# unit: orchestrator/orchestrator/mcp_server.py
anchor: orchestrator/orchestrator/mcp_server.py:1-922

## purpose
POLYMATH-MCP-V2: the v4 MCP server (streamable-http) that lets an agent (Hermes, the claude.ai connector) drive the whole document lifecycle — upload → status until queryable → ask — plus the canonical search/explore/answer surface. Every tool is a thin, trimmed call to the orchestrator API on 127.0.0.1:7200, so MCP cannot bypass the pipeline's gates. — mcp_server.py:1-6 [DERIVED]
Auth is a fail-closed bearer gate (503 with no key configured; owner key = admin, every other caller a scoped principal). — mcp_server.py:30-36, 103-105 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| build_app | def | () -> ASGI app (FastMCP streamable-http + bearer gate) | mcp_server.py:737-896 | main (mcp_server.py:912-917) |
| main | def | () -> None (server entry) | mcp_server.py:912-917 | — |
| list_corpora | MCP tool | () -> dict | mcp_server.py:221-230 | MCP clients (Hermes, claude.ai connector) |
| list_documents | MCP tool | (corpus_id) -> dict | mcp_server.py:234-238 | MCP clients |
| upload_document | MCP tool | (path, corpus_id) -> dict | mcp_server.py:244-273 | local admin callers only |
| upload_text | MCP tool | (text, corpus_id, source_name='agent_upload.md') -> dict | mcp_server.py:277-301 | MCP clients |
| document_status | MCP tool | (corpus_id, source_name, run_id) -> dict | mcp_server.py:307-319 | MCP clients |
| corpus_status | MCP tool | (corpus_id) -> dict | mcp_server.py:323-339 | MCP clients |
| capabilities | MCP tool | () -> dict | mcp_server.py:377-381 | MCP clients |
| polymath_search | MCP tool | (query, corpus_id, mode=MR.DEFAULT_MODE, max_evidence=12) -> dict | mcp_server.py:457-462 | MCP clients |
| polymath_explore | MCP tool | (query, corpus_id, corpus_explorer=True, mode=MR.DEFAULT_MODE) -> dict | mcp_server.py:471-477 | MCP clients |
| polymath_answer | MCP tool | (question, corpus_id, mode=MR.DEFAULT_MODE, reasoning='none', model=None, latent=None) -> dict | mcp_server.py:491-509 | MCP clients |
| polymath_compare | MCP tool | (question, corpus_id, modes=None) -> dict | mcp_server.py:517-523 | MCP clients |
| polymath_deep_research | MCP tool | (question, corpus_id, depth=MR.DEFAULT_DEPTH, mode=MR.DEFAULT_MODE, model=None) -> dict | mcp_server.py:532-541 | MCP clients |
| polymath_models | MCP tool | () -> dict | mcp_server.py:546-547 | MCP clients |
| product_search | MCP tool | (message, corpus_id, geography, model, hypotheses, limit_per_hypothesis) -> dict | mcp_server.py:554-561 | MCP clients |
| supplier_parse | MCP tool | (site, raw_text) -> dict | mcp_server.py:565-566 | MCP clients |
| recent_queries | MCP tool | (corpus_id, limit, since_h, kind) -> dict | mcp_server.py:572-584 | MCP clients |
| adapter_list / adapter_start / adapter_next / adapter_submit / adapter_status / adapter_result / adapter_cancel | MCP tools | per FACTS args | mcp_server.py:591-644 | MCP clients |
| research_acquire / supplier_search / supplier_product / supplier_freight / supplier_warehouses | MCP tools | per FACTS args | mcp_server.py:650-678 | MCP clients |
| run_governed_research | MCP tool | (adapter_id, seed) -> guide + entry point | mcp_server.py:702-704 | MCP clients |
| retrieve / compile_plan / retrieve_evidence / ask | MCP tools (DEPRECATED, callable but never listed) | per FACTS args | mcp_server.py:345, 390, 408, 424 | old callers only |
| KeyInPath | class | (__init__, __call__) — URL key -> bearer header | mcp_server.py:717-734 | build_app |
| _ListedMCPServer | class | (MCPServer subclass; list_tools filters MR.HIDDEN_TOOLS_A) | mcp_server.py:119-124 | mcp instance |

## contracts

**_orch(method, path, \*\*kw) -> dict** — mcp_server.py:155-168
- in: `timeout` kw popped, default `180`. pre: `_trusted_headers()` must return headers; `None` -> returns `dict(NO_PRINCIPAL)` without any request. — mcp_server.py:156-159 [DERIVED]
- out: `r.json()` on status < 400; else `{"error": detail, "status": r.status_code}` with detail from `r.json().get("detail")` or `r.text[:400]`. — mcp_server.py:162-167 [DERIVED]

**_trusted_headers(extra=None) -> Optional[dict]** — mcp_server.py:141-152
- pre: `_PRINCIPAL.get()` must not be `NOBODY` (identity check `who is NOBODY`), else `None` (fail closed). — mcp_server.py:146-148 [DERIVED]
- out: headers with `User-Agent = _CALLER_AGENT.get()`; adds `P.PRINCIPAL_HEADER = who.principal_id` only when `not who.is_admin`. — mcp_server.py:149-151 [DERIVED]

**_orch_events(path, body, timeout=1800.0) -> list[tuple[str, dict]]** — mcp_server.py:171-190
- SSE POST with `Accept: text/event-stream`; pre-stream refusal (status >= 400) returns one `("error", {"error_code": ..., "message": ...})` frame; frames parsed by `MR.parse_sse`. — mcp_server.py:174-189 [DERIVED]

**upload_document(path, corpus_id) -> dict** — mcp_server.py:244-273
- pre: `_CALLER_IS_LOCAL.get() and _PRINCIPAL.get().is_admin`, else `REMOTE_PATH_UPLOAD_DISABLED` (status 403) returned BEFORE any filesystem access ("no existence oracle either"). — mcp_server.py:252-253 [DERIVED]
- pre: `p.is_file()` else 404; suffix in `UPLOAD_EXTENSIONS` else 422. — mcp_server.py:255-259 [DERIVED]
- post: multipart POST to `/upload`; response gains `out["next"]` = document_status polling hint. — mcp_server.py:262-272 [DERIVED]

**upload_text(text, corpus_id, source_name) -> dict** — mcp_server.py:277-301
- pre: `Path(source_name).suffix.lower() in UPLOAD_EXTENSIONS` else 422; principal required (F15: upload stamped with the principal). — mcp_server.py:282-287 [DERIVED]
- post: body is `text.encode("utf-8")` posted as `text/markdown`; adds `out["next"]`. — mcp_server.py:289-300 [DERIVED]

**polymath_search(query, corpus_id, mode, max_evidence=12) -> dict** — mcp_server.py:457-462
- pre: `MR.normalize_mode(mode)` non-None, else `MR.mode_error(mode)`. post: POST `/chat/evidence` with `MR.search_body(...)`, shaped by `MR.shape_search(out, max_evidence)`. — mcp_server.py:458-462 [DERIVED]

**polymath_explore(query, corpus_id, corpus_explorer=True, mode) -> dict** — mcp_server.py:471-477
- same mode validation; POST `/chat/evidence` with `MR.explore_body(...)`, shaped by `MR.shape_explore(out)`. — mcp_server.py:473-477 [DERIVED]

**polymath_answer(question, corpus_id, mode, reasoning='none', model=None, latent=None) -> dict** — mcp_server.py:491-509
- pre: reasoning normalized via `MR.normalize_reasoning`; unknown -> `{"error": ..., "status": 422, "styles": list(MR.REASONING_STYLES)}`. — mcp_server.py:497-499 [DERIVED]
- `model = model or await _app_default_model()` (cached catalog lookup of `/synthesizers`, TTL `MR.DEFAULT_MODEL_TTL_S`). — mcp_server.py:483-487, 500 [DERIVED]
- post: `evidence`/`chunks`/`bundle` slimmed to first 12 items at `_trim_hit(h, 600)`. — mcp_server.py:505-508 [DERIVED]

**polymath_compare(question, corpus_id, modes=None) -> dict** — mcp_server.py:517-523
- modes default to all of `MR.RETRIEVAL_MODES`; any unnormalizable mode -> `MR.mode_error`; dedup via `list(dict.fromkeys(normal))`; POST `/compare` with `timeout=600`. — mcp_server.py:518-522 [DERIVED]

**list_corpora() -> dict** — mcp_server.py:221-230
- post: for non-admin without `ALL_LIBRARIES` grant, `out["corpora"]` filtered to `c.get("corpus_id") in who.corpus_ids` (defence in depth; orchestrator already scopes). — mcp_server.py:227-229 [DERIVED]

## effect surface
- Network: `httpx.AsyncClient` to `ORCH` at mcp_server.py:160, 178, 260, 288 [DERIVED]. Routes called: `GET /corpora` (222, 327, 487 via `/synthesizers`), `GET /documents` (238), `POST /upload` (262, 289), `GET /status` (319), `GET /semantic_readiness` (334), `POST /retrieve` (362, 416), `POST /retrieve/plan` (399), `POST /chat` (434, 501), `GET /capabilities` (381), `POST /chat/evidence` (461, 476), `POST /compare` (522). [DERIVED]
- Env: `POLYMATH_ORCH_URL = 'http://127.0.0.1:7200'` (71), `POLYMATH_MCP_PORT = '8930'` (72), `POLYMATH_MCP_API_KEY = ''` (73), `POLYMATH_MCP_PUBLIC_HOST = 'mcp.kingsleylab.xyz'` (74); principals file via `mcp_principals` (`$POLYMATH_MCP_PRINCIPALS_FILE`, docstring line 32). [DERIVED]
- Files: reads caller-supplied local upload path (`Path(path).expanduser()`, `p.open("rb")`) — mcp_server.py:254, 261-263 [DERIVED]
- Postgres/Qdrant: none read or written directly (FACTS `tables_read`/`tables_written` empty). [DERIVED]
- Cross-process context: contextvars `polymath_mcp_caller_is_local` (96), `polymath_mcp_principal` (107), `polymath_mcp_caller_agent` (108). [DERIVED]
- Side channel: every orchestrator call stamps run ownership / query receipts via the principal header — mcp_server.py:104-105, 149-151 [DERIVED]

## invariants
INVARIANT: hit text cut `max_chars` = 1400 — mcp_server.py:193 [DERIVED]
  fails-if: agent-visible hits silently grow/shrink; D-02 `truncated`/`full_length` contract breaks.
INVARIANT: contract-row cut (1200, `MR.trim_rows`) < hit cut (1400, `_trim_hit`) < answer evidence cut (600, `_trim_hit(h, 600)`) — mcp_server.py:384-386, 193, 443, 507 [DERIVED]
  fails-if: rows outgrow hits; consumers assuming the ladder see inconsistent truncation.
INVARIANT: evidence/chunks/bundle cap = 12 items in both `ask` and `polymath_answer`; `max_evidence` default = 12 — mcp_server.py:443-444, 507-508, 457 [DERIVED]
  fails-if: MCP responses bloat past the intended slim contract.
INVARIANT: upload_document gate = `_CALLER_IS_LOCAL.get() and _PRINCIPAL.get().is_admin`, evaluated before `Path(path)` — mcp_server.py:252-254 [DERIVED]
  fails-if: remote caller gains a host filesystem existence oracle.
INVARIANT: `_ALLOWED_HOSTS` has exactly 4 entries (loopback×2, PUBLIC_HOST, PUBLIC_HOST:443); `_EDGE_HEADERS` has 5 — mcp_server.py:77-78, 95 [DERIVED]
  fails-if: DNS-rebinding allowlist (v33 gotcha) or edge detection drifts.
INVARIANT: default timeouts 180 (`_orch`) < 600 (`/compare`, uploads) < 1800.0 (`_orch_events`) — mcp_server.py:156, 260, 288, 522, 171 [DERIVED]
  fails-if: SSE/deep-research streams time out early, or short calls hang for 30 minutes.
INVARIANT: `_PRINCIPAL` default = `NOBODY` (`prn_nobody`); no gate => no principal => NOBODY — mcp_server.py:106-107, 103 [DERIVED]
  fails-if: an unauthenticated request is served instead of 401 NO_PRINCIPAL.
INVARIANT: `ALL_LIBRARIES = "*"` equals `polymath_shared.query_scope.ALL_LIBRARIES` (pinned by a test) — mcp_server.py:214-215 [DERIVED]
  fails-if: wildcard grant check diverges from the shared token.

## determinism & idempotency
determinism: NONDETERMINISTIC (network — `httpx.AsyncClient` calls at mcp_server.py:160, 178, 260, 288; env-driven config at mcp_server.py:71-74; cached `_DEFAULT_MODEL` with TTL at mcp_server.py:480-487). [DERIVED]
idempotency: SAFE for uploads (content-addressed `run_id`; same bytes return the existing run with `already_exists` true — mcp_server.py:246-248) and for `adapter_cancel` (terminal, idempotent — mcp_server.py:642); every query call is repeatable but stamps query receipts server-side, so repeats are observable — mcp_server.py:104-105 [DERIVED]

## failure behaviour
- Four broad `except Exception` handlers (all "handled: assign"): on non-JSON error bodies, `detail = r.text[:400]` (or `raw[:400].decode("utf-8", "replace")` in `_orch_events`) — mcp_server.py:165-166, 184-185, 267-268, 295-296. Caller sees `{"error": detail, "status": r.status_code}`; nothing re-raised. [DERIVED]
- Literal error returns: `NO_PRINCIPAL` 401 (138), `REMOTE_PATH_UPLOAD_DISABLED` 403 (97-100), `file not found` 404 (256), `corpus ... not found` 404 (337), unsupported extension 422 (258-259), `unknown reasoning style` 422 with `styles` list (499). [DERIVED]
- Upstream refusal codes pass through, e.g. 409 `CROSS_CORPUS_CONTENT_COLLISION` from `/upload` — mcp_server.py:249 [DERIVED]
- `_orch_events` converts a pre-stream refusal into a single `("error", {...})` frame instead of raising — mcp_server.py:176, 187 [DERIVED]

## dumb-code flags
- Three truncation sizes implemented twice locally plus once shared: `_trim_hit` default 1400 (193), `_trim_rows` -> `MR.trim_rows` 1200 (384-386), inline `_trim_hit(h, 600)` in both `ask` and `polymath_answer` (443, 507) — duplicated 600-trim block is copy-paste. [DERIVED]
- Magic timeouts scattered: `180` (156), `600` used for both uploads (260, 288) and `/compare` (522), `1800.0` (171). [DERIVED]
- `_CALLER_AGENT` default `"polymath-mcp"` hardcoded at mcp_server.py:108. [DERIVED]
- `NO_PRINCIPAL` message string duplicated: dict literal at 138 and again inside the `_orch_events` frame at 176. [DERIVED]
- `ALL_LIBRARIES = "*"` re-declared locally instead of importing the shared constant (comment says a test pins the equality) — mcp_server.py:214-215. [DERIVED]

## refactor notes
- All tool descriptions, the playbook, mode names and shaping live in `polymath_shared.mcp_retrieval` (MR), shared with Server B; editing text here desyncs the two servers — mcp_server.py:27-28, 66, 127-135, 448-449. [DERIVED]
- Deprecated tools (`retrieve`, `compile_plan`, `retrieve_evidence`, `ask`) must stay CALLABLE while `_ListedMCPServer.list_tools` filters `MR.HIDDEN_TOOLS_A`; removing them breaks old callers — mcp_server.py:119-124, 26. [DERIVED]
- `REMOTE_PATH_UPLOAD_DISABLED` check ordering is a security property (no existence oracle): it must run before `Path(path)` — mcp_server.py:252-254. [DERIVED]
- `_trusted_headers` returning `None` is the fail-closed sentinel; every new orchestrator call site must handle it or the F15 principal-stamping guarantee (a friend's upload ran as the owner) regresses — mcp_server.py:141-152. [DERIVED]
- `NOBODY` is compared by identity (`who is NOBODY`), so re-creating the principal object per request breaks the gate — mcp_server.py:106-107, 147. [DERIVED]
- `build_app` wires the fail-closed bearer gate, `KeyInPath`, and `MAX_GATED_BODY = 2 * 1024 * 1024`; tool additions bypass nothing because every tool funnels through `_orch`/`_trusted_headers` — mcp_server.py:111, 737-896. [INFERRED — gate scope stated in docstring 30-36; body beyond excerpt.]

## VERIFY
```verify
grep -Fq 'max_chars: int = 1400' orchestrator/orchestrator/mcp_server.py
grep -Fq 'timeout: float = 1800.0' orchestrator/orchestrator/mcp_server.py
grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail closed)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'POLYMATH_MCP_PORT", "8930"' orchestrator/orchestrator/mcp_server.py
test "$(grep -c -F 'httpx.AsyncClient' orchestrator/orchestrator/mcp_server.py)" -ge 4
! grep -Fq 'max_chars: int = 1200' orchestrator/orchestrator/mcp_server.py
```
