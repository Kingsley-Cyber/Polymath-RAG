# unit: orchestrator/orchestrator/mcp_server.py
anchor: orchestrator/orchestrator/mcp_server.py:1-816

## purpose
POLYMATH-MCP-V2: the v4 MCP server (streamable-http) that lets an agent (Hermes, the claude.ai connector) drive the whole document lifecycle — upload → status until queryable → ask — over King's corpora. Every tool is a thin, trimmed HTTP call to the orchestrator on 127.0.0.1:7200 so MCP cannot bypass pipeline gates. Bearer auth is fail-closed with per-principal scopes. [DERIVED] (orchestrator/orchestrator/mcp_server.py:1-30, 104-120)

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| list_corpora | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:167-175 | — |
| list_documents | mcp tool | (corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:179-183 | — |
| upload_document | mcp tool | (path, corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:189-218 | — |
| upload_text | mcp tool | (text, corpus_id, source_name="agent_upload.md") -> dict | orchestrator/orchestrator/mcp_server.py:222-243 | — |
| document_status | mcp tool | (corpus_id, source_name=None, run_id=None) -> dict | orchestrator/orchestrator/mcp_server.py:249-261 | — |
| corpus_status | mcp tool | (corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:265-281 | — |
| retrieve | mcp tool (DEPRECATED) | (query, corpus_id, mode="HYBRID", limit=10, latent=None, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:287-315 | — |
| capabilities | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:319-323 | — |
| compile_plan | mcp tool (DEPRECATED) | (signal, corpus_id, limit=24, explore=True, communities=None) -> dict | orchestrator/orchestrator/mcp_server.py:343-357 | — |
| retrieve_evidence | mcp tool (DEPRECATED) | (query, corpus_id, limit=12, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:361-373 | — |
| ask | mcp tool (DEPRECATED) | (question, corpus_id, mode="HYBRID", latent=None, evidence=False) -> dict | orchestrator/orchestrator/mcp_server.py:377-398 | — |
| polymath_search | mcp tool | (query, corpus_id, max_evidence=12) -> dict | orchestrator/orchestrator/mcp_server.py:403-412 | — |
| polymath_explore | mcp tool | (query, corpus_id, corpus_explorer=True, mode="HYBRID") -> dict | orchestrator/orchestrator/mcp_server.py:416-426 | — |
| polymath_answer | mcp tool | (question, corpus_id, mode="HYBRID", latent=None) -> dict | orchestrator/orchestrator/mcp_server.py:430-447 | — |
| recent_queries | mcp tool | (corpus_id, limit=20, since_h=24.0, kind=None) -> dict | orchestrator/orchestrator/mcp_server.py:453-465 | — |
| adapter_list | mcp tool | () -> dict | orchestrator/orchestrator/mcp_server.py:472-481 | — |
| adapter_start | mcp tool | (adapter_id, input, request_options=None) -> dict | orchestrator/orchestrator/mcp_server.py:485-493 | — |
| adapter_next | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:497-508 | — |
| adapter_submit | mcp tool | (run_id, step_id, payload, agent_identity="connected-agent", model=None, kind=None) -> dict | orchestrator/orchestrator/mcp_server.py:512-524 | — |
| adapter_status | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:528-530 | — |
| adapter_result | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:534-538 | — |
| adapter_cancel | mcp tool | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:542-544 | — |
| research_acquire | mcp tool (owner only) | (run_id, operation, target="", site=None, search_intent_id=None, limit=None) -> dict | orchestrator/orchestrator/mcp_server.py:550-567 | — |
| supplier_search | mcp tool (owner only) | (query, source, limit) -> dict | orchestrator/orchestrator/mcp_server.py:574-582 | — |
| supplier_product | mcp tool (owner only) | (product_id) -> dict | orchestrator/orchestrator/mcp_server.py:586-591 | — |
| supplier_freight | mcp tool (owner only) | (variant_id, country, quantity, from_country) -> dict | orchestrator/orchestrator/mcp_server.py:595-600 | — |
| supplier_warehouses | mcp tool (owner only) | () -> dict | orchestrator/orchestrator/mcp_server.py:604-607 | — |
| run_governed_research | mcp tool | (adapter_id=None, seed=None) -> dict | orchestrator/orchestrator/mcp_server.py:631-633 | — |
| build_app | function | () -> ASGI app | orchestrator/orchestrator/mcp_server.py:636-792 | — |
| main | function | () -> None | orchestrator/orchestrator/mcp_server.py:806-811 | — |

## contracts

**_orch(method, path, **kw) -> dict** (orchestrator/orchestrator/mcp_server.py:124-142)
- pre: `_PRINCIPAL.get()` must not be `NOBODY`, else returns `{"error": "NO_PRINCIPAL: ...", "status": 401}` before any HTTP call — line 129-130.
- in: `timeout = kw.pop("timeout", 180)` — line 125; `User-Agent` from `_CALLER_AGENT` — line 131.
- pre→headers: non-admin principals get `P.PRINCIPAL_HEADER: who.principal_id` — line 132-133.
- out: orchestrator JSON on <400; on >=400 `{"error": detail, "status": r.status_code}` — line 141.

**upload_document(path, corpus_id) -> dict** (orchestrator/orchestrator/mcp_server.py:189-218)
- pre: `_CALLER_IS_LOCAL.get()` AND `_PRINCIPAL.get().is_admin`, else `dict(REMOTE_PATH_UPLOAD_DISABLED)` before ANY filesystem access (no existence oracle) — line 197-198.
- pre: file must exist (404 — line 200-201); suffix must be in `UPLOAD_EXTENSIONS` (422 — line 202-204).
- post: same bytes return the existing run with `already_exists` true; content already in ANOTHER corpus refused `409 CROSS_CORPUS_CONTENT_COLLISION` — line 192-195.
- out: run JSON plus a `next` hint naming `document_status(...)` — line 216-217.

**upload_text(text, corpus_id, source_name) -> dict** (orchestrator/orchestrator/mcp_server.py:222-243)
- pre: `source_name` suffix in `UPLOAD_EXTENSIONS`, else 422 — line 227-229.
- out: run JSON plus `next` hint — line 241-242.

**polymath_search(query, corpus_id, max_evidence=12) -> dict** (orchestrator/orchestrator/mcp_server.py:403-412)
- in: `POST /retrieve` with `{"query", "corpus_id", "limit": max_evidence, "evidence": True}` — line 406-407.
- out: `{"evidence_rows": _trim_rows(...), "evidence_contract": ..., "graph_facts": <int count>}` — line 410-412. q0-only; no planning, no answer — line 404-405.

**polymath_explore(query, corpus_id, corpus_explorer=True, mode="HYBRID") -> dict** (orchestrator/orchestrator/mcp_server.py:416-426)
- in: `POST /chat/evidence` with message/corpus_id/mode/corpus_explorer — line 423-425.
- out: versioned EvidencePacket, `synthesis_performed=false` (no Polymath answer) — line 418-422.

**polymath_answer / ask(question, corpus_id, ...) -> dict** (orchestrator/orchestrator/mcp_server.py:377-398, 430-447)
- in: `POST /chat` — line 387, 439.
- out: full answer dict but `evidence` / `chunks` / `bundle` lists trimmed to first 12 items at 600 chars — line 393-397, 443-446.
- post: `verdict=insufficient_evidence` must be relayed, not filled — line 434-435.

**adapter_next(run_id) -> dict** (orchestrator/orchestrator/mcp_server.py:497-508)
- out: `{kind:"step", step, evidence, receipts, coverage}` or `{kind:"status", status}`; evidence sibling capped at 60 rows × 600 chars, only ids in `step.context.evidence_refs` — line 503-507.

**adapter_submit(run_id, step_id, payload, ...) -> dict** (orchestrator/orchestrator/mcp_server.py:512-524)
- in: kind="reasoning" (default, AGENT_REASON) or kind="receipt" (HARNESS_ACTION, HarnessResearchReceiptV1) — line 514-520.
- post: rejection returns errors and the step stays open for resubmission — line 521-522.

**_trim_hit(h, max_chars=1400) -> dict** (orchestrator/orchestrator/mcp_server.py:145-161)
- post (D-02): cut hit gets `truncated: true` + `full_length`; a fitting hit keeps exactly its old keys (None values dropped) — line 146-147, 159-161.

**_trim_rows(rows) -> list** (orchestrator/orchestrator/mcp_server.py:326-339)
- post (D-02): `text` / `text_clean` cut at 1200 chars; cut row gets `truncated: true` + `full_length` — line 327-337.

**recent_queries(corpus_id, ...) -> dict** (orchestrator/orchestrator/mcp_server.py:453-465)
- pre: non-blank `corpus_id`, else `raise ValueError("corpus_id is required")` — line 460-461.
- out: `GET /queries`; principal context narrows to its OWN receipts — line 465.

**build_app() -> ASGI app** (orchestrator/orchestrator/mcp_server.py:636-792)
- FastMCP streamable-http + FAIL-CLOSED bearer gate — line 636.

## effect surface
| effect | detail | anchor |
|---|---|---|
| network | `httpx.AsyncClient` to `ORCH` (default `http://127.0.0.1:7200`), timeout 180 default | orchestrator/orchestrator/mcp_server.py:134-135, 125 |
| network | `httpx.AsyncClient(timeout=600)` POST `/upload` (file bytes) | orchestrator/orchestrator/mcp_server.py:205-208 |
| network | `httpx.AsyncClient(timeout=600)` POST `/upload` (text bytes, `text/markdown`) | orchestrator/orchestrator/mcp_server.py:230-233 |
| files | reads HOST-local upload path: `Path(path).expanduser()`, `p.open("rb")` — local callers only | orchestrator/orchestrator/mcp_server.py:199, 206 |
| env | `POLYMATH_ORCH_URL` = `http://127.0.0.1:7200` | orchestrator/orchestrator/mcp_server.py:57 |
| env | `POLYMATH_MCP_PORT` = `8930` | orchestrator/orchestrator/mcp_server.py:58 |
| env | `POLYMATH_MCP_API_KEY` = `''` (empty = fail-closed 503) | orchestrator/orchestrator/mcp_server.py:59, 21-22 |
| env | `POLYMATH_MCP_PUBLIC_HOST` = `mcp.kingsleylab.xyz` | orchestrator/orchestrator/mcp_server.py:60 |
| contextvars | `polymath_mcp_caller_is_local` (default False), `polymath_mcp_principal` (default NOBODY), `polymath_mcp_caller_agent` (default "polymath-mcp") | orchestrator/orchestrator/mcp_server.py:79, 90, 91 |
| tables | none read/written (FACTS: `tables_read: []`, `tables_written: []`) | — |

## invariants
INVARIANT: `_PRINCIPAL == NOBODY` implies `_orch` returns 401 before any HTTP request — orchestrator/orchestrator/mcp_server.py:129-130 [DERIVED]
  fails-if: an unauthenticated context would issue trusted loopback calls under the sentinel id.
INVARIANT: upload_document authorization check (line 197-198) executes before `Path(path)` access (line 199) — orchestrator/orchestrator/mcp_server.py:197-199 [DERIVED]
  fails-if: remote callers gain a host file-existence oracle.
INVARIANT: `_trim_hit` cut (1400) > `_trim_rows` cut (1200) > answer-list cut (600) — orchestrator/orchestrator/mcp_server.py:145, 332-334, 396-397 [DERIVED]
  fails-if: mixed payload sizes; consumers assuming one global trim width mis-parse.
INVARIANT: ask/polymath_answer evidence lists capped at 12 items — orchestrator/orchestrator/mcp_server.py:397, 446 [DERIVED]
  fails-if: unbounded chat payloads to MCP clients.
INVARIANT: `MAX_GATED_BODY == 2 * 1024 * 1024` — orchestrator/orchestrator/mcp_server.py:94 [DERIVED]
  fails-if: oversized gated requests bypass or break the bearer gate.
INVARIANT: `_ALLOWED_HOSTS` == {`127.0.0.1:PORT`, `localhost:PORT`, `PUBLIC_HOST`, `PUBLIC_HOST:443`} — orchestrator/orchestrator/mcp_server.py:63-64 [DERIVED]
  fails-if: DNS-rebinding protection (v33 gotcha) rejects legitimate hosts or admits others.
INVARIANT: adapter_next evidence ≤ 60 rows × 600 chars — orchestrator/orchestrator/mcp_server.py:503-505 [DERIVED]
  fails-if: step payloads exceed MCP message budgets.
INVARIANT: `_is_local_caller` requires loopback Host AND absence of all `_EDGE_HEADERS` — orchestrator/orchestrator/mcp_server.py:97-99, 77-78 [DERIVED]
  fails-if: a tunnelled request spoofing loopback Host but carrying `cf-connecting-ip` would be misclassified; the AND prevents that.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: httpx.AsyncClient at orchestrator/orchestrator/mcp_server.py:134, 205, 230; env: lines 57-60; per-request concurrency state in contextvars: 79, 90, 91)
idempotency: SAFE for read tools; upload_document is content-addressed (same bytes → existing run, `already_exists` true — orchestrator/orchestrator/mcp_server.py:192-194); adapter_cancel is terminal and idempotent (orchestrator/orchestrator/mcp_server.py:542-543); adapter_start retries deduped via `request_options.idempotency_key` (orchestrator/orchestrator/mcp_server.py:488)

## failure behaviour
- Three `except Exception` handlers (orchestrator/orchestrator/mcp_server.py:139, 212, 237): swallow JSON-decode failures on error responses; `detail` falls back to `r.text[:400]`; caller sees `{"error": detail, "status": <code>}` — lines 136-141, 209-214, 234-239. [DERIVED]
- 401 `NO_PRINCIPAL` when no gate ran — orchestrator/orchestrator/mcp_server.py:130. [DERIVED]
- 401 unknown/revoked key, 403 not permitted, 429 over principal rate — orchestrator/orchestrator/mcp_server.py:20. [DERIVED]
- 503 on /mcp when no key configured (fail-closed, V2) — orchestrator/orchestrator/mcp_server.py:21-22. [DERIVED]
- 403 `REMOTE_PATH_UPLOAD_DISABLED` for remote/non-admin upload_document — orchestrator/orchestrator/mcp_server.py:80-83, 198. [DERIVED]
- 404 file not found; 422 unsupported extension / bad source_name — orchestrator/orchestrator/mcp_server.py:201, 203-204, 228-229. [DERIVED]
- 409 `CROSS_CORPUS_CONTENT_COLLISION` (upload, orchestrator-side) — orchestrator/orchestrator/mcp_server.py:194; 409 from adapter_result while running — orchestrator/orchestrator/mcp_server.py:537. [DERIVED]

## dumb-code flags
- Triplicated error-detail parser (`r.json().get("detail")` → `r.text[:400]`): identical blocks at orchestrator/orchestrator/mcp_server.py:136-141, 209-214, 234-239. [DERIVED]
- Magic trim constants: 1400, 1200, 600, 12 items, 60 rows — orchestrator/orchestrator/mcp_server.py:145, 332-334, 396-397, 503-505. [DERIVED]
- Four deprecated tools (retrieve, compile_plan, retrieve_evidence, ask) kept beside canonical polymath_* trio — orchestrator/orchestrator/mcp_server.py:287, 343, 361, 377. [DERIVED]
- `retrieve` meta whitelist hard-codes `("latent", "mode", "corpus_ids", "plan")` — orchestrator/orchestrator/mcp_server.py:313-314. [DERIVED]
- Default `source_name="agent_upload.md"` baked into the signature — orchestrator/orchestrator/mcp_server.py:223. [DERIVED]

## refactor notes
- `_TOOL_NAMES` (orchestrator/orchestrator/mcp_server.py:795) and the lines referencing polymath_search/explore/answer at :802 must stay in sync with every `@mcp.tool()` registration above; adding a tool without updating it desyncs the gate's tool list. [INFERRED — a named list adjacent to tool names implies registry use]
- D-02 truncation keys `truncated` / `full_length` are an external caller contract in `_trim_hit` and `_trim_rows` — changing cut sizes or key names silently changes agent-visible payloads — orchestrator/orchestrator/mcp_server.py:146-147, 327-337. [DERIVED]
- `P.PRINCIPAL_HEADER` forwarding (orchestrator/orchestrator/mcp_server.py:132-133) is consumed by the orchestrator as `adapter_runs.owner_principal_id`; renaming breaks run ownership and receipt attribution — orchestrator/orchestrator/mcp_server.py:492. [DERIVED]
- `REMOTE_PATH_UPLOAD_DISABLED` shape (`error` + `status: 403`) is returned verbatim to remote callers — orchestrator/orchestrator/mcp_server.py:80-83, 198. [DERIVED]
- Deleting the deprecated tools (retrieve, compile_plan, retrieve_evidence, ask) breaks "existing callers" they are explicitly kept for — orchestrator/orchestrator/mcp_server.py:290, 345, 362, 380. [DERIVED]
- `research_acquire` and `supplier_*` are intentionally owner-only and outside principals' TOOL_POLICY; widening them exposes the owner's browser sign-ins and CJ quota — orchestrator/orchestrator/mcp_server.py:547-548, 573-574. [DERIVED]

## VERIFY
```verify
grep -Fq 'POLYMATH-MCP-V2 — the v4 MCP server (streamable-http)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'def _trim_hit(h: dict, max_chars: int = 1400)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'r[k] = r[k][:1200]' orchestrator/orchestrator/mcp_server.py
grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail closed)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'mcp.kingsleylab.xyz' orchestrator/orchestrator/mcp_server.py
test "$(grep -c -F 'REMOTE_PATH_UPLOAD_DISABLED' orchestrator/orchestrator/mcp_server.py)" -ge 2
grep -Fq 'val[:12]' orchestrator/orchestrator/mcp_server.py
```
