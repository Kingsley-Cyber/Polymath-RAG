# unit: orchestrator/orchestrator/mcp_server.py
anchor: orchestrator/orchestrator/mcp_server.py:1-853

## purpose
POLYMATH-MCP-V2: the v4 MCP server (streamable-http) that lets an agent (Hermes, the claude.ai connector) drive the whole document lifecycle — upload → status until queryable → ask — plus the canonical evidence surface (`polymath_search` / `polymath_explore` / `polymath_answer`), governed-research adapter runs, and owner-only supplier tools. Every tool is a thin, trimmed call to the orchestrator API on `127.0.0.1:7200`, so MCP cannot bypass the pipeline's gates. [DERIVED] (orchestrator/orchestrator/mcp_server.py:1-31)

Auth model: `Authorization: Bearer <key>` on every `/mcp`, or the key in the URL (`/k/<key>/mcp`, translated by `KeyInPath`). `$POLYMATH_MCP_API_KEY` is the OWNER (admin) key; other callers are PRINCIPALS from `mcp_principals.py` (default-deny scopes, 401/403/429). FAIL-CLOSED V2: no key configured → 503 on `/mcp` instead of running open. [DERIVED] (orchestrator/orchestrator/mcp_server.py:18-27)

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| list_corpora | def (tool) | () -> dict | orchestrator/orchestrator/mcp_server.py:171 | — |
| list_documents | def (tool) | (corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:183 | — |
| upload_document | def (tool) | (path, corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:193 | — |
| upload_text | def (tool) | (text, corpus_id, source_name="agent_upload.md") -> dict | orchestrator/orchestrator/mcp_server.py:226 | — |
| document_status | def (tool) | (corpus_id, source_name=None, run_id=None) -> dict | orchestrator/orchestrator/mcp_server.py:253 | — |
| corpus_status | def (tool) | (corpus_id) -> dict | orchestrator/orchestrator/mcp_server.py:269 | — |
| retrieve | def (tool, DEPRECATED) | (query, corpus_id, mode="HYBRID", limit=10, latent=None, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:291 | — |
| capabilities | def (tool) | () -> dict | orchestrator/orchestrator/mcp_server.py:323 | — |
| compile_plan | def (tool, DEPRECATED) | (signal, corpus_id, limit=24, explore=True, communities=None) -> dict | orchestrator/orchestrator/mcp_server.py:347 | — |
| retrieve_evidence | def (tool, DEPRECATED) | (query, corpus_id, limit=12, explore=False) -> dict | orchestrator/orchestrator/mcp_server.py:365 | — |
| ask | def (tool, DEPRECATED) | (question, corpus_id, mode="HYBRID", latent=None, evidence=False) -> dict | orchestrator/orchestrator/mcp_server.py:381 | — |
| polymath_search | def (tool) | (query, corpus_id, max_evidence=12) -> dict | orchestrator/orchestrator/mcp_server.py:407 | — |
| polymath_explore | def (tool) | (query, corpus_id, corpus_explorer=True, mode="HYBRID") -> dict | orchestrator/orchestrator/mcp_server.py:420 | — |
| polymath_answer | def (tool) | (question, corpus_id, mode="HYBRID", latent=None) -> dict | orchestrator/orchestrator/mcp_server.py:434 | — |
| recent_queries | def (tool) | (corpus_id, limit=20, since_h=24.0, kind=None) -> dict | orchestrator/orchestrator/mcp_server.py:457 | — |
| adapter_list | def (tool) | () -> dict | orchestrator/orchestrator/mcp_server.py:476 | — |
| adapter_start | def (tool) | (adapter_id, input, request_options=None) -> dict | orchestrator/orchestrator/mcp_server.py:489 | — |
| adapter_next | def (tool) | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:501 | — |
| adapter_submit | def (tool) | (run_id, step_id, payload, agent_identity="connected-agent", model=None, kind=None) -> dict | orchestrator/orchestrator/mcp_server.py:516 | — |
| adapter_status | def (tool) | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:532 | — |
| adapter_result | def (tool) | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:538 | — |
| adapter_cancel | def (tool) | (run_id) -> dict | orchestrator/orchestrator/mcp_server.py:546 | — |
| research_acquire | def (tool, owner-only) | (run_id, operation, target, site, search_intent_id, limit) -> dict | orchestrator/orchestrator/mcp_server.py:554 | — |
| supplier_search | def (tool, owner-only) | (query, source, limit) -> dict | orchestrator/orchestrator/mcp_server.py:578 | — |
| supplier_product | def (tool, owner-only) | (product_id) -> dict | orchestrator/orchestrator/mcp_server.py:590 | — |
| supplier_freight | def (tool, owner-only) | (variant_id, country, quantity, from_country) -> dict | orchestrator/orchestrator/mcp_server.py:599 | — |
| supplier_warehouses | def (tool, owner-only) | () -> dict | orchestrator/orchestrator/mcp_server.py:608 | — |
| run_governed_research | def (prompt) | (adapter_id, seed) -> guide | orchestrator/orchestrator/mcp_server.py:635 | — |
| KeyInPath | class | (__init__, __call__) | orchestrator/orchestrator/mcp_server.py:650 | — |
| build_app | def | () -> ASGI app | orchestrator/orchestrator/mcp_server.py:670 | — |
| main | def | () -> None | orchestrator/orchestrator/mcp_server.py:843 | — |

Imports of this unit (its own dependencies): `orchestrator.mcp_principals`, `polymath_shared.adapter.harness_guide`. No importer list in FACTS. [DERIVED] (orchestrator/orchestrator/mcp_server.py:53-54)

## contracts

**_orch(method, path, \*\*kw) — orchestrator/orchestrator/mcp_server.py:128-146**
- pre: `_PRINCIPAL.get()` must not be `NOBODY`, else returns `{"error": "NO_PRINCIPAL: this call carries no authenticated principal (fail closed)", "status": 401}` before any request. [DERIVED] (133-134)
- in: default `timeout=180`; non-admin principals get header `P.PRINCIPAL_HEADER = who.principal_id`; `User-Agent` from `_CALLER_AGENT`. [DERIVED] (129-137)
- post: HTTP >= 400 → `{"error": detail, "status": code}` where `detail = r.json().get("detail")` or `r.text[:400]`; else the parsed JSON. [DERIVED] (139-145)

**upload_document(path, corpus_id) — orchestrator/orchestrator/mcp_server.py:193-222**
- pre: caller must be local (loopback host, no edge headers) AND admin, else `REMOTE_PATH_UPLOAD_DISABLED` (status 403) returned before ANY filesystem access ("no existence oracle either"). [DERIVED] (201-202, 84-87)
- pre: `Path(path).expanduser().is_file()` else 404 `file not found: {path}`; suffix must be in `UPLOAD_EXTENSIONS` else 422. [DERIVED] (203-208)
- post: success → orchestrator `/upload` response plus `out["next"] = "document_status(corpus_id=..., source_name=...) until query_ready"`. Same bytes → existing run with `already_exists` true; content in another corpus → 409 `CROSS_CORPUS_CONTENT_COLLISION` (orchestrator-side, stated in docstring). [DERIVED] (195-198, 220-221)

**upload_text(text, corpus_id, source_name) — orchestrator/orchestrator/mcp_server.py:226-247**
- pre: `source_name` suffix in `UPLOAD_EXTENSIONS` else 422. [DERIVED] (231-233)
- post: posts to `/upload` as `text/markdown`, 600 s timeout, adds the same `next` key. [DERIVED] (234-246)

**polymath_search(query, corpus_id, max_evidence=12) — orchestrator/orchestrator/mcp_server.py:407-416**
- in: POST `/retrieve` with `{"query", "corpus_id", "limit": max_evidence, "evidence": True}` — q0-only rows, no planning, no answer. [DERIVED] (410-411)
- post: `{"evidence_rows": _trim_rows(...), "evidence_contract", "graph_facts": len(...)}`; `"error" in out` passes through unchanged. [DERIVED] (412-416)

**polymath_explore(query, corpus_id, corpus_explorer=True, mode="HYBRID") — orchestrator/orchestrator/mcp_server.py:420-430**
- in: POST `/chat/evidence` with `{"message", "corpus_id", "mode", "corpus_explorer"}`. [DERIVED] (427-429)
- post: versioned EvidencePacket (`synthesis_performed=false`, roles DIRECT/COMPLEMENTARY/DIVERGENT, CA4 grades) — NO Polymath answer; the response is returned untrimmed. [DERIVED] (422-430)

**polymath_answer(question, corpus_id, ...) — orchestrator/orchestrator/mcp_server.py:434-451**
- in: POST `/chat` with `{"message", "mode", "corpus_id"}` (+ optional `latent`). [DERIVED] (440-443)
- post: answer passed through; bulky evidence lists (`evidence`/`chunks`/`bundle`) trimmed to `[:12]` hits at 600 chars. `verdict=insufficient_evidence` means the corpus cannot support the question — relay it. [DERIVED] (444-451, 436-439)

**list_corpora() — orchestrator/orchestrator/mcp_server.py:171-179**
- post: non-admin principals see only corpora whose `corpus_id` is in `who.corpus_ids`. [DERIVED] (176-178)

**recent_queries(corpus_id, ...) — orchestrator/orchestrator/mcp_server.py:457-469**
- pre: blank `corpus_id` raises `ValueError("corpus_id is required")`. [DERIVED] (464-465)
- post: GET `/queries`; a principal's context narrows results to its OWN receipts. [DERIVED] (469)

**adapter_next(run_id) / adapter_submit(run_id, step_id, payload, ...) — orchestrator/orchestrator/mcp_server.py:501-528**
- post: next returns `{kind:"step", step: AdapterStepV1}` with sibling `evidence` rows capped at 60 rows x 600 chars, or `{kind:"status", ...}`. [DERIVED] (502-512)
- pre: submit for AGENT_REASON cites ONLY ids from `context.evidence_refs`; rejection returns errors and the step stays open. [DERIVED] (518-525)

## effect surface
| effect | detail | anchor |
|---|---|---|
| network | `httpx.AsyncClient` to `ORCH` (loopback orchestrator): `_orch` (180 s default), `/upload` from upload_document (600 s), `/upload` from upload_text (600 s) | orchestrator/orchestrator/mcp_server.py:138, 209, 234 |
| network | supplier/research tools proxy to orchestrator `/adapter/*`, research and CJ endpoints (owner-only) | orchestrator/orchestrator/mcp_server.py:554, 578, 590, 599, 608 |
| files | upload_document reads a HOST-local file (`p.open("rb")`, `p.is_file()` check) — local admin callers only | orchestrator/orchestrator/mcp_server.py:203-212 |
| env | `POLYMATH_ORCH_URL` = `'http://127.0.0.1:7200'`; `POLYMATH_MCP_PORT` = `'8930'`; `POLYMATH_MCP_API_KEY` = `''`; `POLYMATH_MCP_PUBLIC_HOST` = `'mcp.kingsleylab.xyz'` | orchestrator/orchestrator/mcp_server.py:58-61 |
| env | `$POLYMATH_MCP_PRINCIPALS_FILE` consumed by `mcp_principals.store_from_env(API_KEY)` (docstring + `_STORE = P.store_from_env(API_KEY)`) | orchestrator/orchestrator/mcp_server.py:20, 96 |
| db | no tables read/written directly (`tables_read`/`tables_written` empty in FACTS) — all persistence goes through the orchestrator HTTP API | orchestrator/orchestrator/mcp_server.py:128-146 |
| contextvars | `polymath_mcp_caller_is_local`, `polymath_mcp_principal`, `polymath_mcp_caller_agent` set per request (defaults: `False`, `NOBODY`, `"polymath-mcp"`) | orchestrator/orchestrator/mcp_server.py:83-95 |

## invariants
INVARIANT: `_trim_hit` cut length 1400 > `_trim_rows` cut length 1200 — orchestrator/orchestrator/mcp_server.py:149,336 [DERIVED]
  fails-if: evidence rows and raw hits silently get different max text lengths; consumers assuming one budget overflow context.
INVARIANT: ask/polymath_answer evidence lists capped at `val[:12]` entries, each hit trimmed to 600 chars — orchestrator/orchestrator/mcp_server.py:400,450 [DERIVED]
  fails-if: answer payloads grow unbounded; citation identity preserved but bodies exceed the agent's context budget.
INVARIANT: `UPLOAD_EXTENSIONS` has exactly 6 members `{".md", ".txt", ".html", ".pdf", ".epub", ".docx"}` and gates both upload tools — orchestrator/orchestrator/mcp_server.py:62,206,231 [DERIVED]
  fails-if: adding an extension in one place only makes upload_document and upload_text disagree on accepted types.
INVARIANT: `MAX_GATED_BODY = 2 * 1024 * 1024` bytes for the gated body — orchestrator/orchestrator/mcp_server.py:98 [DERIVED]
  fails-if: oversized uploads rejected by the gate; clients see an unexpected limit.
INVARIANT: orchestrator error text forwarded as detail is capped at `r.text[:400]` chars in all three handlers — orchestrator/orchestrator/mcp_server.py:144,217,242 [DERIVED]
  fails-if: error payloads of unbounded size leak to MCP clients.
INVARIANT: adapter_next readable evidence capped at 60 rows x 600 chars for exactly the ids in `step.context.evidence_refs` — orchestrator/orchestrator/mcp_server.py:507 [DERIVED]
  fails-if: step context exceeds the awaiting agent's budget or cites non-admitted evidence.
INVARIANT: `_is_local_caller` requires Host in `_LOOPBACK_HOSTS` AND none of `_EDGE_HEADERS` (`cf-connecting-ip`, `cf-ray`, `cdn-loop`, `x-forwarded-for`, `forwarded`) — orchestrator/orchestrator/mcp_server.py:101-103,81-82 [DERIVED]
  fails-if: a tunneled request mistaken for local gains host-filesystem access via upload_document.
INVARIANT: upload_document reaches the filesystem only after the local+admin gate; the 403 body is returned first — orchestrator/orchestrator/mcp_server.py:201-203 [DERIVED]
  fails-if: remote callers get a file-existence oracle on the Polymath host.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: `httpx.AsyncClient` calls at orchestrator/orchestrator/mcp_server.py:138,209,234; env: config read at :58-61; per-request contextvars/concurrency at :83-95)
idempotency: SAFE (read tools are pure proxies; `adapter_cancel` documented "terminal, idempotent; accepted work is kept" at :547; uploads are content-addressed — same bytes return the existing run with `already_exists` true per docstring :195-196, enforced orchestrator-side)

## failure behaviour
- Three identical `except Exception` handlers swallow JSON-parse failures on orchestrator error responses and assign `detail = r.text[:400]`; the caller sees `{"error": detail, "status": r.status_code}` — orchestrator/orchestrator/mcp_server.py:141-144, 214-217, 239-242 [DERIVED]
- `401` `NO_PRINCIPAL` returned by `_orch` when no gate ran (principal is the `NOBODY` sentinel) — orchestrator/orchestrator/mcp_server.py:93,133-134 [DERIVED]
- `403` `REMOTE_PATH_UPLOAD_DISABLED` for non-local/non-admin `upload_document`, before any filesystem access — orchestrator/orchestrator/mcp_server.py:84-87,201-202 [DERIVED]
- `404` `file not found: {path}` (upload_document) and `corpus {corpus_id!r} not found` (corpus_status, with `semantic_readiness` still attached) — orchestrator/orchestrator/mcp_server.py:204-205,282-284 [DERIVED]
- `422` unsupported extension (upload_document) / bad `source_name` (upload_text) — orchestrator/orchestrator/mcp_server.py:206-208,231-233 [DERIVED]
- `ValueError("corpus_id is required")` raised (not returned) by recent_queries on blank corpus_id — orchestrator/orchestrator/mcp_server.py:464-465 [DERIVED]
- Gate-level codes stated in the module docstring: 401 unknown/revoked key, 403 not permitted, 429 over rate, 503 fail-closed when no key is configured (V1 incident 2026-09-02: the V1 process booted keyless and the public mirror answered tools/call to anyone) — orchestrator/orchestrator/mcp_server.py:18-24 [DERIVED]
- `409 CROSS_CORPUS_CONTENT_COLLISION` on uploading bytes that already live in another corpus (orchestrator-enforced, documented here) — orchestrator/orchestrator/mcp_server.py:197-198 [DERIVED]

## dumb-code flags
- Three trim budgets with no shared constant: `1400` (`_trim_hit` default), `1200` (`_trim_rows`), `600` (ask/polymath_answer hits) — orchestrator/orchestrator/mcp_server.py:149,336,400 [DERIVED]
- The detail-extraction `try/except` block is copy-pasted three times — orchestrator/orchestrator/mcp_server.py:141-144,214-217,239-242 [DERIVED]
- `val[:12]` cap duplicated in ask and polymath_answer — orchestrator/orchestrator/mcp_server.py:400,450 [DERIVED]
- Timeout defaults disagree: `180` in `_orch` vs `600` on both upload paths — orchestrator/orchestrator/mcp_server.py:129,209,234 [DERIVED]
- Deprecated surface kept alongside the canonical one: `retrieve` (291), `compile_plan` (347), `retrieve_evidence` (365), `ask` (381) duplicate `polymath_search`/`polymath_explore`/`polymath_answer` — orchestrator/orchestrator/mcp_server.py:291,347,365,381,405 [DERIVED]
- `_ALLOWED_HOSTS` allows both bare `PUBLIC_HOST` and `PUBLIC_HOST:443` plus loopback variants; `allowed_origins` includes speculative `"https://claude.ai"`, `"https://claude.com"` ("not observed; an absent Origin already passes") — orchestrator/orchestrator/mcp_server.py:64-75 [DERIVED]

## refactor notes
- Every tool hardcodes its orchestrator route (`/corpora`, `/documents`, `/upload`, `/status`, `/semantic_readiness`, `/retrieve`, `/retrieve/plan`, `/chat`, `/chat/evidence`, `/queries`, `/capabilities`, `/adapter/*`) — renaming any orchestrator endpoint breaks this file — orchestrator/orchestrator/mcp_server.py:175,187,211,235,265,280,281,308,314,327,369,391,410,427,443,469,481,495,512,526 [DERIVED]
- `_TOOL_NAMES` at build time must enumerate the tool set the gate authorizes; adding an `@mcp.tool()` without updating it changes gate behaviour — orchestrator/orchestrator/mcp_server.py:832 [DERIVED]
- `_orch` forwards `P.PRINCIPAL_HEADER = who.principal_id` only for non-admin principals; `mcp_principals` and the orchestrator both depend on this contract — orchestrator/orchestrator/mcp_server.py:130-137 [DERIVED]
- `KeyInPath` must keep translating `/k/<key>/mcp` into the bearer header — the claude.ai connector cannot send headers — orchestrator/orchestrator/mcp_server.py:18-19,650 [DERIVED]
- Upload responses embed a `next` instruction string naming `document_status(corpus_id=..., source_name=...)`; changing tool names/params breaks documented agent workflows and the MCPServer instructions text — orchestrator/orchestrator/mcp_server.py:220-221,245-246,109-124 [DERIVED]
- Principal filtering happens in-tool (`who.corpus_ids` at :177-178, `who.adapter_ids` at :483-484) in addition to the gate's default-deny; moving scoping to one layer requires touching both — orchestrator/orchestrator/mcp_server.py:91-92,177-178,483-484 [DERIVED]

## VERIFY
```verify
grep -Fq 'UPLOAD_EXTENSIONS = {".md", ".txt", ".html", ".pdf", ".epub", ".docx"}' orchestrator/orchestrator/mcp_server.py
grep -Fq 'def _trim_hit(h: dict, max_chars: int = 1400)' orchestrator/orchestrator/mcp_server.py
grep -Fq 'len(r[k]) > 1200' orchestrator/orchestrator/mcp_server.py
grep -Fq 'MAX_GATED_BODY = 2 * 1024 * 1024' orchestrator/orchestrator/mcp_server.py
grep -Fq 'def polymath_explore(query: str, corpus_id: str, corpus_explorer: bool = True,' orchestrator/orchestrator/mcp_server.py
grep -Fq 'for h in val[:12]' orchestrator/orchestrator/mcp_server.py
! grep -Fq 'NO_PRINCIPAL: this call carries no authenticated principal (fail open)' orchestrator/orchestrator/mcp_server.py
```
