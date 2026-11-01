# unit: orchestrator/orchestrator/api/chat.py
anchor: orchestrator/orchestrator/api/chat.py:1-293

## purpose
One-shot JSON transport for the chat runtime: `POST /chat` maps a `ChatRequest` onto the runtime's `StreamChatRequest`, runs one `run_chat` turn (the same generator `/chat/stream` streams) and returns the answer frame as a single JSON object; MCP `ask` posts here and inherits the whole pipeline (orchestrator/orchestrator/api/chat.py:1-14 [DERIVED]). `POST /chat/evidence` runs the same turn forced evidence-only and returns a versioned `EvidencePacket` with `synthesis_performed=false` — no synthesis LLM, no reviewer — for external agents that do their own final reasoning (orchestrator/orchestrator/api/chat.py:267-271 [DERIVED]).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ChatRequest` | class | pydantic `BaseModel`, 19 request fields | chat.py:44-77 | request body of both routes |
| `chat` | route handler | `(req: ChatRequest, request: Request) -> dict` — POST `/chat` | chat.py:191-220 | orchestrator/orchestrator/main.py (FACTS.importers); MCP `ask` (chat.py:7) |
| `chat_evidence` | route handler | `(req: ChatRequest, request: Request) -> dict` — POST `/chat/evidence` | chat.py:266-293 | orchestrator/orchestrator/main.py (FACTS.importers); external agents (chat.py:270-271) |
| `stream_request` | function | `(req: ChatRequest) -> StreamChatRequest` | chat.py:85-124 | `_chat_impl:132`, `_evidence_impl:227` |
| `resolve_chat_mode` | function | `(requested: str \| None) -> str` | chat.py:141-150 | `stream_request:114` |
| `attach_evidence_rows` | function | `(out: dict, req: ChatRequest) -> dict` | chat.py:153-188 | `_chat_impl:134` |
| `attach_packet_rows` | function | `(out: dict, req: ChatRequest) -> dict` | chat.py:237-263 | `_evidence_impl:233` |
| `_chat_impl` | function | `(req, *, receipt=None) -> dict` (sync, threadpool) | chat.py:127-135 | `chat:208` |
| `_evidence_impl` | function | `(req, *, receipt=None, client: str = "") -> dict` (sync, threadpool) | chat.py:223-234 | `chat_evidence:280` |

## contracts

**`chat` (POST /chat)** — chat.py:191-220
- in: `ChatRequest` body; `client` = `request.headers.get("user-agent", "")` (chat.py:200).
- out: the answer frame as one dict — answer / citations / claims / meta, `contracts/answer/v2`; `meta.mode` is the EXECUTED mode (chat.py:16-19).
- pre: rejected-before-runtime requests (empty message, unknown mode or synthesizer) never reach the runtime writer (chat.py:196-198); explicit unknown mode → 422 `unknown_mode` (chat.py:94); LEGACY has no runtime path (chat.py:95, 151).
- post: every `/chat` call leaves exactly one receipt row, kind `chat`, with the caller's user agent; best effort, off the critical path (chat.py:193-199, 203-204).
- failure: assembly failures stay loud (502) (chat.py:20).

**`stream_request`** — chat.py:85-124
- maps field by field per CHAT-REQUEST-MAP-V1 (docstring table chat.py:88-108); `mode` None/"" → `resolve_chat_mode(None)` = HYBRID (chat.py:114); `synthesizer` None → `CHAT_DEFAULT_SYNTHESIZER` (chat.py:116); `evidence` is NOT mapped — it is a response add-on applied after the turn (chat.py:106-108, 133-134).
- comment warning: `corpus_explorer` / `evidence_only` "miss the mapping below and they drop" (chat.py:69-70, 120-121).

**`resolve_chat_mode`** — chat.py:141-150
- returns `validate_mode(requested or MODE_HYBRID)`; `/retrieve` keeps `retrieval_modes.DEFAULT_MODE` for its own frozen evaluations; the runtime is the one mode validator for both routes (chat.py:145-151).

**`attach_evidence_rows`** — chat.py:153-188
- in: `out` dict + `req`; builds rows from `citations[].locators` chunk ids (regex `^chunk:([A-Za-z0-9_]+)`, chat.py:138, 164-166) and `source_document_ids` (chat.py:167-169), deduped, citations sorted by `citation_id`.
- post: identical on every answer path (FAST/HYBRID/GRAPH), never a second retrieval (chat.py:156-157); sets `evidence_contract = "retrieve-evidence-rows-v1"` (chat.py:179); `meta.setdefault("mode", "UNKNOWN")` and `meta["requested_mode"] = req.mode` (chat.py:186-187).

**`_evidence_impl` / `chat_evidence`** — chat.py:223-234, 266-293
- forces `sreq.evidence_only = True` (chat.py:228); pipeline short-circuits before synthesis and returns the EvidencePacket (chat.py:224-225).
- a governed run's own call (user agent startswith `ADAPTER_CLIENTS`) that names no `product` gets `product = False` (chat.py:229-230, 82-85).
- post: same one-receipt guarantee via `_sink`, kind `chat` (chat.py:275-276, 196-199).

**`attach_packet_rows`** — chat.py:237-263
- rows from the packet's own `evidence_packet.evidence` chunk_ids in packet order, each re-tagged with its `utility_role` and `ca4_grade`; then the turn's graph facts with attesting chunks; built from ids the turn already chose, never a second retrieval (chat.py:238-244, 256-257).

## effect surface
- Postgres: no tables named in this file (FACTS.tables_read/tables_written empty). `tx()` connections opened at chat.py:172 and chat.py:250 and handed to `build_evidence_rows`; receipt rows written via `record_query_receipt(tx, kind="chat", ...)` at chat.py:204, 215-218, 276, 287-290.
- Env flag: `POLYMATH_CHAT_COMPILER` — default when `ChatRequest.compiler` is None (per comment, chat.py:65; enforcement lives in the runtime, not this file).
- Qdrant / files / subprocess / direct network: none visible in this file.
- Constants written: `CHAT_DEFAULT_SYNTHESIZER = "deterministic-template-v3"` (chat.py:41); `ADAPTER_CLIENTS = ("polymath-adapter-step/", "opportunity-research/")` (chat.py:82).

## invariants
INVARIANT: default /chat synthesizer == `"deterministic-template-v3"` (`req.synthesizer or CHAT_DEFAULT_SYNTHESIZER`) — chat.py:41,116 [DERIVED]
  fails-if: MCP `ask` / TRAIL silently lose the deterministic claims/citations contract they read (chat.py:38-39).
INVARIANT: default /chat mode == HYBRID (`validate_mode(requested or MODE_HYBRID)`) — chat.py:114,149-150 [DERIVED]
  fails-if: no-mode requests fall back to the frozen LEGACY path (12,732 claims, 437 KB triple dump, 30–50 s) mislabeled HYBRID (chat.py:143-146).
INVARIANT: evidence-rows limit == `max(12, len(chunk_ids))` on both attach paths — chat.py:178,255 [DERIVED]
  fails-if: fewer than 12 rows returned even when the answer cites fewer chunks; the two paths disagree if only one changes.
INVARIANT: every `/chat` and `/chat/evidence` POST writes exactly one receipt row — chat.py:197-199,210,282 [DERIVED]
  fails-if: runtime-rejected requests leave no trace (`if not receipted` fallback covers them, chat.py:210,282).
INVARIANT: `/chat/evidence` always sets `evidence_only = True` before `run_chat` — chat.py:228 [DERIVED]
  fails-if: a synthesis LLM runs on the evidence-boundary route, breaking `synthesis_performed=false`.
INVARIANT: user agent prefix in `ADAPTER_CLIENTS` + `product is None` → `product = False` — chat.py:82,229-230 [DERIVED]
  fails-if: a governed run's internal evidence call triggers product mode (PRODUCT-SEARCH-E2E) against the rule at chat.py:80-85.
INVARIANT: evidence add-on failure leaves the answer/packet standing (`evidence_rows = []` + `evidence_rows_error`, error string truncated to 200 chars) — chat.py:180-182,260-262 [DERIVED]
  fails-if: a rows-build error would 5xx an otherwise valid answer if the swallow were removed.
INVARIANT: identical request → identical compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list and synthesis contract on both transports — chat.py:10-14 [DERIVED, docstring contract]

## determinism & idempotency
determinism: NONDETERMINISTIC — `time.perf_counter` for `wall_ms` at chat.py:217 and chat.py:289 (FACTS.nondeterminism); user-agent header is an input (chat.py:200,272); DB reads via `tx()` at chat.py:172,250. Answer body itself is contractually identical across the two transports for the same request (chat.py:10-14 [DERIVED]).
idempotency: UNSAFE — each POST writes a receipt row (`record_query_receipt`, chat.py:204,215,276,287); retries duplicate receipts even though the answer repeats.

## failure behaviour
- `attach_evidence_rows` / `attach_packet_rows`: broad `except Exception` swallows the rows-build error; caller sees the answer/packet with `evidence_rows = []` and `evidence_rows_error = f"{type(exc).__name__}: {exc}"[:200]` — chat.py:180-182, 260-262 [DERIVED].
- `chat` / `chat_evidence`: broad `except Exception` — if the runtime wrote no receipt yet, record an error receipt (`error=f"{type(exc).__name__}: {detail ...}"`), then **re-raise unchanged** — chat.py:209-220, 281-292 [DERIVED].
- Error codes: 422 `unknown_mode` for an explicit bad mode (chat.py:94); 502 on assembly failures, kept loud (chat.py:20) [DERIVED, docstring].

## dumb-code flags
- Magic floor `12` in `limit=max(12, len(chunk_ids))`, duplicated on both attach paths — chat.py:178,255.
- Fabricated `rerank_score`: `float(len(chunk_ids) - i)` (position-as-score), identical expression twice; `selected_documents` rerank_score hardcoded `0.0` — chat.py:175-176,253-254.
- Duplicated literals: `"retrieve-evidence-rows-v1"` (chat.py:179,259); the `[:200]` error-string pattern (chat.py:182,262); the whole fallback-receipt block and `_sink` closure copy-pasted between `chat` and `chat_evidence` (chat.py:203-219 vs 275-291).
- Defensive `getattr(req, "corpus_explorer", False)` / `getattr(req, "scope", None)` / `getattr(req, "product", None)` on a pydantic model whose fields exist at chat.py:71-77 — dead defensiveness at chat.py:120-122.
- `"UNKNOWN"` fallback literal for `meta.mode` — chat.py:186.
- Comment/`FACTS` mismatch: FACTS.constants records `ADAPTER_CLIENTS` as a list; source line 82 is a tuple `("polymath-adapter-step/", "opportunity-research/")` — chat.py:82.

## refactor notes
- `CHAT_DEFAULT_SYNTHESIZER` and the HYBRID default change behaviour for every MCP `ask` and `/chat` caller that omits `synthesizer`/`mode` (chat.py:41,116,149-150); MCP `ask` / TRAIL consume `claims` and `citations` from this contract (chat.py:38-39).
- `stream_request` is the CHAT-REQUEST-MAP-V1 contract; renaming or dropping a mapping silently changes runtime turns for API/MCP callers (chat.py:85-124, 59-61, 69-70).
- `ADAPTER_CLIENTS` prefixes and the `startswith` guard suppress product mode for governed runs; renaming those user agents breaks the guard (chat.py:80-85,229-230).
- Route paths `/chat` and `/chat/evidence` are public API (router imported by orchestrator/orchestrator/main.py per FACTS.importers; MCP `ask` at chat.py:7; external agents at chat.py:270-271).
- `evidence_contract = "retrieve-evidence-rows-v1"` and the `contracts/answer/v2` shape are consumed by external callers; changing either breaks them (chat.py:16-19,179,259).

## VERIFY
```verify
grep -Fq 'CHAT_DEFAULT_SYNTHESIZER = "deterministic-template-v3"' orchestrator/orchestrator/api/chat.py
grep -Fq 'ADAPTER_CLIENTS = ("polymath-adapter-step/", "opportunity-research/")' orchestrator/orchestrator/api/chat.py
grep -Fq 'validate_mode(requested or MODE_HYBRID)' orchestrator/orchestrator/api/chat.py
grep -Fq 'sreq.evidence_only = True' orchestrator/orchestrator/api/chat.py
grep -Fq '@router.post("/chat/evidence")' orchestrator/orchestrator/api/chat.py
grep -Fq 'limit=max(12, len(chunk_ids))' orchestrator/orchestrator/api/chat.py
grep -Fq 'record_query_receipt(tx, kind="chat"' orchestrator/orchestrator/api/chat.py
! grep -Fq 'def build_evidence_rows' orchestrator/orchestrator/api/chat.py
```
