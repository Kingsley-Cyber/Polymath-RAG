# unit: mcp_server/polymath_mcp.py
anchor: mcp_server/polymath_mcp.py:1-530

## purpose
MCP server (stdio default, `--http [PORT]` optional) exposing the Polymath query product to agents as a thin HTTP client of the orchestrator API (`http://127.0.0.1:7200` default) — nothing re-implemented locally. [DERIVED] mcp_server/polymath_mcp.py:1-41, 497-525
Serves the REASONING-BOUNDARY-V1 tool surface (search/explore/answer + corpus management), the seven ADR-0018 cognitive-adapter proxies, product/supplier tools, and one governed-research prompt + guide resources. [DERIVED] mcp_server/polymath_mcp.py:8-33, 444-467

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_ListedMCPServer` | class | `MCPServer` subclass; overrides `list_tools()` | mcp_server/polymath_mcp.py:60-64 | — |
| `polymath_list_corpora` | tool | `() -> dict` | mcp_server/polymath_mcp.py:113-114 | — |
| `polymath_search` | tool | `(query: str, corpus_id: str, mode=MR.DEFAULT_MODE, max_evidence: int = 10) -> dict` | mcp_server/polymath_mcp.py:125-129 | — |
| `polymath_explore` | tool | `(query, corpus_id, corpus_explorer: bool = True, mode=MR.DEFAULT_MODE) -> dict` | mcp_server/polymath_mcp.py:138-143 | — |
| `polymath_answer` | tool | `(question, corpus_id, mode=MR.DEFAULT_MODE, reasoning="none", model=None, latent=None) -> dict` | mcp_server/polymath_mcp.py:147-158 | — |
| `polymath_compare` | tool | `(question, corpus_id, modes: list[str] | None = None) -> dict` | mcp_server/polymath_mcp.py:165-170 | — |
| `polymath_deep_research` | tool | `(question, corpus_id, depth=MR.DEFAULT_DEPTH, mode=MR.DEFAULT_MODE, model=None) -> dict` | mcp_server/polymath_mcp.py:178-197 | — |
| `polymath_models` | tool | `() -> dict` | mcp_server/polymath_mcp.py:202-206 | — |
| `product_search` | tool | `(message, corpus_id=None, geography=None, model=None, hypotheses=None, limit_per_hypothesis=None) -> dict` | mcp_server/polymath_mcp.py:211-217 | — |
| `supplier_parse` | tool | `(site: str, raw_text: str) -> dict` | mcp_server/polymath_mcp.py:221-222 | — |
| `polymath_query` | tool (deprecated, unlisted) | `(question, corpus_id, mode="HYBRID", latent=None) -> dict` | mcp_server/polymath_mcp.py:226-244 | — |
| `polymath_retrieve` | tool (deprecated, unlisted) | `(query, corpus_id, mode="HYBRID", latent=None) -> dict` | mcp_server/polymath_mcp.py:248-261 | — |
| `polymath_list_documents` | tool | `(corpus_id: str) -> dict` | mcp_server/polymath_mcp.py:265-268 | — |
| `polymath_upload_file` | tool | `(path: str, corpus_id: str) -> dict` | mcp_server/polymath_mcp.py:272-288 | — |
| `polymath_upload_text` | tool | `(text, corpus_id, source_name="agent_upload.md") -> dict` | mcp_server/polymath_mcp.py:292-306 | — |
| `polymath_readiness` | tool | `(corpus_id: str) -> dict` | mcp_server/polymath_mcp.py:310-314 | — |
| `polymath_delete_corpus` | tool | `(corpus_id: str, confirm: str) -> dict` | mcp_server/polymath_mcp.py:318-329 | — |
| `polymath_delete_document` | tool | `(doc_id: str, confirm: str) -> dict` | mcp_server/polymath_mcp.py:333-340 | — |
| `adapter_list/start/next/submit/status/result/cancel` | tools | proxies over `/adapter/*`; `adapter_submit(run_id, step_id, payload, agent_identity="connected-agent", model=None, kind=None)` | mcp_server/polymath_mcp.py:362-410 | — |
| `research_acquire` | tool | `(run_id, operation, target="", site=None, search_intent_id=None, limit=None) -> dict` | mcp_server/polymath_mcp.py:415-418 | — |
| `supplier_search/product/freight/warehouses` | tools | `supplier_search(query, source="cj", limit=10)`; `supplier_freight(variant_id, country, quantity=1, from_country="CN")` | mcp_server/polymath_mcp.py:424-441 | — |
| `run_governed_research` | prompt | `(adapter_id: str = "", seed: str = "") -> str` | mcp_server/polymath_mcp.py:465-467 | — |
| `main` | entry | `() -> None`; stdio or uvicorn on 127.0.0.1 | mcp_server/polymath_mcp.py:497-525 | — |

## contracts
`polymath_search` — mcp_server/polymath_mcp.py:125-129
- in: `query`, `corpus_id`, `mode`, `max_evidence=10`; pre: `MR.normalize_mode(mode)` non-None else returns `MR.mode_error(mode)`; out: `MR.shape_search(_post("/chat/evidence", MR.search_body(...)))` — evidence rows only, no plan/answer. [DERIVED]

`polymath_answer` — mcp_server/polymath_mcp.py:147-158
- pre: `mode == "ASK"` (case-insensitive strip) short-circuits to `_post("/ask", ...)`; invalid mode -> `MR.mode_error`; invalid `reasoning` -> `{"error": ..., "status": 422, "styles": list(MR.REASONING_STYLES)}`; post: `model = model or _app_default_model()`, body via `MR.answer_body(...)` to `/chat`. [DERIVED]

`polymath_deep_research` — mcp_server/polymath_mcp.py:178-197
- pre: valid mode and `MR.normalize_depth(depth)` else 422 error dict; out: SSE stream `POST /research/deep` with `Accept: text/event-stream`, timeout `httpx.Timeout(1800.0, connect=10.0)`, parsed by `MR.parse_sse` -> `MR.shape_deep(..., depth=d, mode=m)`. [DERIVED]

`polymath_delete_corpus` — mcp_server/polymath_mcp.py:318-329
- pre: `confirm` must equal `corpus_id` (enforced server-side per docstring); out: `httpx.delete(f"{BASE}/corpora/{corpus_id}", params={"confirm": confirm}, timeout=300)`; >=400 -> error dict, never raises. [DERIVED]

`polymath_delete_document` — mcp_server/polymath_mcp.py:333-340
- pre: `confirm` must equal `doc_id`; out: `httpx.delete(.../documents/{doc_id})` then `r.raise_for_status()` — raises on error, unlike `polymath_delete_corpus`. [DERIVED]

`polymath_upload_file` — mcp_server/polymath_mcp.py:272-288
- pre: `Path(path).expanduser()` must exist else `{"error": f"file not found: {path}"}`; out: multipart `POST /upload`, `timeout=300`, returns run id JSON. [DERIVED]

`adapter_submit` — mcp_server/polymath_mcp.py:377-390
- in: `payload`, `agent_identity`, `model`, `kind`; post: `"kind"` key included only when truthy (`**({"kind": kind} if kind else {})`); out: `AdapterRunStatusV1` via `_adapter("POST", f"/adapter/{run_id}/submit", ...)`. [DERIVED]

`_app_default_model` — mcp_server/polymath_mcp.py:100-108
- returns cached value from `_DEFAULT_MODEL.cached()`; else `_DEFAULT_MODEL.remember(_get("/synthesizers"))`; on `httpx.HTTPError` returns `None`. [DERIVED]

## effect surface
- network: `httpx.get` mcp_server/polymath_mcp.py:85; `httpx.post` :91, :280, :298; `httpx.delete` :322, :337; `httpx.request` :351; `httpx.stream("POST", .../research/deep)` :186-187 [DERIVED]
- orchestrator routes called: `/corpora`, `/chat/evidence`, `/chat`, `/compare`, `/research/deep`, `/synthesizers`, `/ask`, `/retrieve`, `/documents`, `/upload`, `/semantic_readiness`, `/product/search`, `/supplier/*`, `/adapter/*` [DERIVED]
- env: `POLYMATH_API = "http://127.0.0.1:7200"` mcp_server/polymath_mcp.py:58; `POLYMATH_MCP_API_KEY = ""` :476 and :511 [DERIVED]
- files: reads guide files `(_GUIDE_ROOT / rel).read_text()` :451; opens local upload file `p.open("rb")` :279 [DERIVED]
- Postgres/Qdrant: none — `tables_read`/`tables_written` empty, no direct DB access (all state via HTTP) [DERIVED]

## invariants
INVARIANT: listed tool set == all tools minus `MR.HIDDEN_TOOLS_B` — mcp_server/polymath_mcp.py:64 [DERIVED]
  fails-if: deprecated `polymath_query`/`polymath_retrieve` reappear in listings, breaking MCP-RETRIEVAL-MODES-V1 hiding contract.
INVARIANT: default API base == `"http://127.0.0.1:7200"` — mcp_server/polymath_mcp.py:58 [DERIVED]
  fails-if: server pointed at wrong orchestrator; every tool errors.
INVARIANT: HTTP fallback port == `7300` when `--http` arg missing/unparsable — mcp_server/polymath_mcp.py:498-509 [DERIVED]
  fails-if: connector URLs built for a different port stop reaching the server.
INVARIANT: `_get` timeout == 120, `_post` == 300, `_adapter` == 180, compare == 600, deep == `httpx.Timeout(1800.0, connect=10.0)` — mcp_server/polymath_mcp.py:85, 91, 170, 187, 351 [DERIVED]
  fails-if: long research runs or slow routes time out at the proxy instead of at the orchestrator.
INVARIANT: legacy mode alias `"VECTOR"` -> `"FAST"` in both deprecated tools — mcp_server/polymath_mcp.py:240, 257 [DERIVED]
  fails-if: old callers passing `mode="VECTOR"` get rejected by the orchestrator.
INVARIANT: with `POLYMATH_MCP_API_KEY` set, DNS-rebinding protection OFF; without it, `allowed_hosts` == `["127.0.0.1:{port}", "localhost:{port}"]` — mcp_server/polymath_mcp.py:511-521 [DERIVED]
  fails-if: keyed tunnel deployment gets 421s, or keyless server becomes tunnel-reachable.
INVARIANT: error bodies truncated to 400 chars (`r.text[:400]`) in every non-`_get` error path — mcp_server/polymath_mcp.py:96, 193, 287, 328, 356 [DERIVED]
  fails-if: longer diagnostics silently lost before the agent sees them.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: all behaviour is HTTP calls to `BASE`, mcp_server/polymath_mcp.py:85-351; env: `POLYMATH_API` :58, `POLYMATH_MCP_API_KEY` :476/:511) [DERIVED]
idempotency: UNSAFE (reads are safe, but `polymath_upload_file`/`polymath_upload_text` start a new ingestion run per call :272-306, and `polymath_delete_corpus`/`polymath_delete_document` are destructive :318-340; only `adapter_cancel` is documented idempotent :408-410) [DERIVED]

## failure behaviour
- `_post`: `status_code >= 400` returns `{"error": r.json().get("detail", r.text)}`; JSON-decode failure swallowed (`except Exception`) -> `{"error": r.text[:400]}` — caller sees an error dict, never an exception. mcp_server/polymath_mcp.py:90-97 [DERIVED]
- `polymath_delete_corpus`: identical swallow pattern, `{"error": ...}` on >=400. mcp_server/polymath_mcp.py:324-328 [DERIVED]
- `_adapter`: 4xx/5xx -> `{"error": detail, "status": code}` so 422 rejections / 409 not-terminal surface as data. mcp_server/polymath_mcp.py:349-357 [DERIVED]
- `polymath_deep_research`: >=400 reads body, `detail = r.json().get("detail")` with `except Exception` fallback `r.text[:400]`, returns `{"error": f"{d_.get('error_code') or r.status_code}: ...", "status": r.status_code}`. mcp_server/polymath_mcp.py:188-195 [DERIVED]
- `_get` paths (`list_corpora`, `list_documents`, `readiness`): `r.raise_for_status()` — exceptions propagate; `polymath_models` catches `httpx.HTTPError` -> `{"error": ...}[:300]`; `_app_default_model` catches -> `None`. mcp_server/polymath_mcp.py:86, 107-108, 203-206 [DERIVED]
- `polymath_delete_document`: `r.raise_for_status()` — raises, inconsistent with `polymath_delete_corpus`'s error-dict contract. mcp_server/polymath_mcp.py:339 [INFERRED] (contrast with :324-328)

## dumb-code flags
- Default mode `"HYBRID"` hardcoded in deprecated `polymath_query`/`polymath_retrieve` (:229, :250) while all live tools use `MR.DEFAULT_MODE` (:125, :139, :148, :178) — drift risk if the shared default changes. [DERIVED]
- `POLYMATH_MCP_API_KEY` env read twice (:476, :511). [DERIVED]
- `r.text[:400]` duplicated at 5 sites (:96, :193, :287, :328, :356). [DERIVED]
- Server version literal `"1.0.0"` (:72) unrelated to any shared version constant. [DERIVED]
- `"VECTOR" -> "FAST"` alias logic duplicated in the two deprecated tools (:240, :257). [DERIVED]
- `polymath_search` and `polymath_explore` both POST `/chat/evidence`, differing only in body builder + shaper (:129 vs :143). [DERIVED]

## refactor notes
- Tool names/params are the external MCP contract; the playbook served as `instructions` references `polymath_list_corpora`, `polymath_upload_text`, `polymath_upload_file` by name — renaming breaks agent instructions. mcp_server/polymath_mcp.py:74-78 [DERIVED]
- Adapter-tool parity with Server A is pinned by `tests/contracts/test_mcp_adapter_parity.py` and playbook by `tests/contracts/test_mcp_agent_playbook.py` — any name/param/description change must update those. mcp_server/polymath_mcp.py:26, 33 [DERIVED]
- `MR.HIDDEN_TOOLS_B` must keep containing the deprecated tool names or `_ListedMCPServer.list_tools` re-exposes them. mcp_server/polymath_mcp.py:60-64 [INFERRED] (hiding depends entirely on that shared list)
- Auth wrapper + `TransportSecuritySettings` choice (keyless => localhost-only hosts) is a deployment-critical pairing; changing one side strands tunnels or opens the keyless server. mcp_server/polymath_mcp.py:470-523 [DERIVED]

## VERIFY
```verify
grep -Fq 'http://127.0.0.1:7200' mcp_server/polymath_mcp.py
grep -Fq 'MR.HIDDEN_TOOLS_B' mcp_server/polymath_mcp.py
grep -Fq 'port = 7300' mcp_server/polymath_mcp.py
grep -Fq 'stateless_http=True' mcp_server/polymath_mcp.py
test "$(grep -c -F 'r.text[:400]' mcp_server/polymath_mcp.py)" -ge 4
! grep -Fq 'qdrant' mcp_server/polymath_mcp.py
```
