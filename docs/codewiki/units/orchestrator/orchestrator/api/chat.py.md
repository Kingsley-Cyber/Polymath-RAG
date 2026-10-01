# unit: orchestrator/orchestrator/api/chat.py
anchor: orchestrator/orchestrator/api/chat.py:1-279

## purpose
One-shot JSON transport for the chat runtime: `POST /chat` runs one runtime turn (`run_chat`, the same generator `/chat/stream` streams) and returns the answer frame as one JSON object; `POST /chat/evidence` runs the same turn forced evidence-only. [DERIVED] — orchestrator/orchestrator/api/chat.py:1-21, 122, 218
No retrieval, compiler or synthesis logic of its own — it maps `ChatRequest` onto `StreamChatRequest` and defers to the runtime. MCP `ask` posts here and inherits everything (compiler, CHAT-RETRIEVAL-V2, CARRY-V2, SYNTHESIS-V2). [DERIVED] — orchestrator/orchestrator/api/chat.py:3-9

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | module var | `APIRouter()` | orchestrator/orchestrator/api/chat.py:36 | orchestrator/orchestrator/main.py (FACTS.importers) |
| `ChatRequest` | class | BaseModel: `message`, `corpus_id`, `corpus_ids`, `workspace`, `all_authorized`, `mode`, `latent`, `utility`, `retrieval`, `evidence=False`, `synthesizer`, `history`, `carry_context`, `compiler`, `reasoning`, `reasoning_blend`, `corpus_explorer=False`, `evidence_only=False`, `scope` | orchestrator/orchestrator/api/chat.py:44-74 | `chat`, `chat_evidence` |
| `stream_request` | def | `(req: ChatRequest) -> StreamChatRequest` | orchestrator/orchestrator/api/chat.py:77-114 | `_chat_impl`:122, `_evidence_impl`:216 |
| `resolve_chat_mode` | def | `(requested: str | None) -> str` | orchestrator/orchestrator/api/chat.py:131-140 | `stream_request`:105 |
| `attach_evidence_rows` | def | `(out: dict, req: ChatRequest) -> dict` | orchestrator/orchestrator/api/chat.py:143-178 | `_chat_impl`:124 |
| `chat` | route | `POST /chat (req, request) -> dict` | orchestrator/orchestrator/api/chat.py:181-210 | main.py |
| `_evidence_impl` | def | `(req: ChatRequest, *, receipt=None) -> dict` | orchestrator/orchestrator/api/chat.py:213-221 | `chat_evidence`:267 |
| `attach_packet_rows` | def | `(out: dict, req: ChatRequest) -> dict` | orchestrator/orchestrator/api/chat.py:224-250 | `_evidence_impl`:220 |
| `chat_evidence` | route | `POST /chat/evidence (req, request) -> dict` | orchestrator/orchestrator/api/chat.py:253-279 | main.py |
| `CHAT_DEFAULT_SYNTHESIZER` | const | `= "deterministic-template-v3"` | orchestrator/orchestrator/api/chat.py:41 | `stream_request`:107 |

## contracts

**stream_request** — orchestrator/orchestrator/api/chat.py:77-114
- in: full `ChatRequest`; out: `StreamChatRequest` field-by-field (CHAT-REQUEST-MAP-V1). [DERIVED] — :78-99
- `mode=(req.mode or resolve_chat_mode(None))` — None/"" becomes HYBRID; explicit modes pass through, runtime is the sole validator (FAST/VECTOR, HYBRID, GRAPH, WILDCARD, ASK valid; anything else → 422 `unknown_mode`; LEGACY has no runtime path). [DERIVED] — :105, 85-87
- `synthesizer=(req.synthesizer or CHAT_DEFAULT_SYNTHESIZER)`. [DERIVED] — :107
- post: `evidence` is NOT mapped — response-only add-on applied after the turn, never a second retrieval. [DERIVED] — :97-99, 123-124

**resolve_chat_mode** — orchestrator/orchestrator/api/chat.py:131-140
- out: `validate_mode(requested or MODE_HYBRID)`; `/retrieve` keeps `retrieval_modes.DEFAULT_MODE` for itself. [DERIVED] — :140, 135-136

**chat (POST /chat)** — orchestrator/orchestrator/api/chat.py:181-210
- in: `ChatRequest` body + `user-agent` header. [DERIVED] — :190
- effect: body runs `run_chat(stream_request(req), route="chat", receipt=_sink)` in a worker thread; `evidence: true` appends rows after. [DERIVED] — :122-124, 198
- post: exactly one receipt row per call — runtime `_sink` (kind `chat`, client = user agent) or the fallback receipt; pre-runtime rejections (empty message, unknown mode/synthesizer) are receipted by the handler. [DERIVED] — :193-194, 199-209, 186-189

**attach_evidence_rows** — orchestrator/orchestrator/api/chat.py:143-178
- pre: chunk ids from `citations[].locators` matching `^chunk:([A-Za-z0-9_]+)`, deduped in citation_id order; doc ids from `source_document_ids`. [DERIVED] — :128, 150-159
- out: `evidence_rows` via `build_evidence_rows(conn, ..., limit=max(12, len(chunk_ids)), explore=False)`, `evidence_contract = "retrieve-evidence-rows-v1"`, `meta.setdefault("mode", "UNKNOWN")`, `meta["requested_mode"] = req.mode`. [DERIVED] — :162-169, 176-177
- post: rows built only from ids the answer already cites — identical on FAST/HYBRID/GRAPH, never a second retrieval. [DERIVED] — :144-147

**_evidence_impl / chat_evidence (POST /chat/evidence)** — orchestrator/orchestrator/api/chat.py:213-221, 253-279
- pre: same `stream_request` mapping, then `sreq.evidence_only = True`, `run_chat(sreq, route="chat/evidence", ...)`. [DERIVED] — :216-218
- out: full retrieval/planning pipeline (compiler → Corpus Explore → retrieval → C4/C5 → CA4), versioned EvidencePacket with `synthesis_performed=false` — no synthesis LLM, no reviewer; Polymath owns retrieval planning, caller owns the answer. [DERIVED] — :255-258

**attach_packet_rows** — orchestrator/orchestrator/api/chat.py:224-250
- pre: `evidence_packet.evidence[].chunk_id` (+ `utility_role`, `ca4_grade`) and `graph_facts[].fact_id`. [DERIVED] — :231-234
- out: rows in packet order with graded fields re-attached per chunk id; `evidence_contract = "retrieve-evidence-rows-v1"`. [DERIVED] — :237-246

## effect surface
- DB via `tx()`: read conn for `build_evidence_rows` — orchestrator/orchestrator/api/chat.py:162, 237; receipt writes via `record_query_receipt(tx, kind="chat", ...)` — :194, 205, 263, 274. FACTS records `tables_read: []`, `tables_written: []` (no table-level access tracked).
- Threads: `run_in_threadpool` for both bodies. [DERIVED] — :198, 267
- Env: none read in this file; `compiler=None` defers to `POLYMATH_CHAT_COMPILER` in the runtime (comment only). — :65
- Network/Qdrant/subprocess/files: none in this file.

## invariants
INVARIANT: default /chat synthesizer == `"deterministic-template-v3"` — orchestrator/orchestrator/api/chat.py:41, 107 [DERIVED]
  fails-if: MCP `ask` / TRAIL consumers of `claims` and `citations` (comment :38-40) get LLM output instead of the grounded deterministic contract.
INVARIANT: mode when `req.mode` is None/"" == `MODE_HYBRID` — orchestrator/orchestrator/api/chat.py:105, 140 [DERIVED]
  fails-if: modeless /chat reruns the frozen LEGACY path (12,732 claims, 437 KB triple dump, 30–50 s) mislabeled HYBRID (:133-135).
INVARIANT: evidence-rows limit == `max(12, len(chunk_ids))` with `explore=False` — orchestrator/orchestrator/api/chat.py:168, 242 [DERIVED]
  fails-if: sparse citations return fewer than 12 rows, or explore-mode rows leak into the chat add-on.
INVARIANT: child_evidence rerank_score at position i == `float(len(chunk_ids) - i)` — orchestrator/orchestrator/api/chat.py:165, 240 [DERIVED]
  fails-if: citation/packet order stops being reflected in descending synthetic scores.
INVARIANT: `len(evidence_rows_error)` <= 200 — orchestrator/orchestrator/api/chat.py:172, 249 [DERIVED]
  fails-if: unbounded exception text leaks into the JSON response.
INVARIANT: chunk ids deduped preserving first-occurrence order — orchestrator/orchestrator/api/chat.py:155-156, 232 [DERIVED]
  fails-if: duplicate rows or reordered evidence in the add-on.
INVARIANT: exactly one receipt row per /chat-family call (runtime sink XOR fallback) — orchestrator/orchestrator/api/chat.py:194+200, 263+269 [DERIVED]
  fails-if: pre-runtime rejections leave zero receipts, or double-write on retry.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.perf_counter()` at :207, :276 — receipt `wall_ms` only; db: receipt writes and evidence-row reads :162, :237, :194). The turn itself is documented deterministic: identical request → identical plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list, synthesis contract on both routes (:10-14). [DERIVED]
idempotency: UNSAFE (every call appends a query-receipt row via `_sink` :194/:263 or the fallback :205/:274; retries add rows though answers repeat)

## failure behaviour
- `attach_evidence_rows`: any `Exception` swallowed → `evidence_rows=[]` + `evidence_rows_error`; the answer already stands. [DERIVED] — orchestrator/orchestrator/api/chat.py:170-172
- `attach_packet_rows`: same swallow pattern; the packet already stands. [DERIVED] — orchestrator/orchestrator/api/chat.py:247-249
- `chat` / `chat_evidence`: any `Exception` from the impl → fallback receipt written only `if not receipted`, then re-raised unchanged; caller sees the original error (runtime 422 `unknown_mode` per :86-87; assembly failures stay loud, 502, per :20). [DERIVED] — :199-210, 268-279

## dumb-code flags
- Magic `12` duplicated in `limit=max(12, len(chunk_ids))` — orchestrator/orchestrator/api/chat.py:168, 242
- Duplicated literal `"retrieve-evidence-rows-v1"` written at :169 and :246 — must move together.
- Rerank scores are fabricated positions (`float(len(chunk_ids) - i)`, `0.0` for docs), not real rerank values — :165-166, 240-241
- Defensive `getattr(req, "corpus_explorer", False)` / `evidence_only` / `scope` on a Pydantic model that defines those fields at :71-74 — the defaults are dead branches. [INFERRED: ChatRequest always has the fields, so getattr never falls back] — :111-113
- Receipt-fallback block copy-pasted verbatim between `chat` (:199-210) and `chat_evidence` (:268-279), differing only in the impl call.
- Truncation magic `[:200]` on error strings — :172, 249

## refactor notes
- `stream_request` is the CHAT-REQUEST-MAP-V1 field table: any new `StreamChatRequest` field must be mirrored here or it silently drops ("miss the mapping below and they drop") — blast radius is every /chat and MCP `ask` caller. — orchestrator/orchestrator/api/chat.py:66, 101-114
- Do not unify the default mode with `/retrieve`: `/chat` uses `MODE_HYBRID`, `/retrieve` keeps `retrieval_modes.DEFAULT_MODE` for frozen evaluations — changing the /chat default resurrects the LEGACY regression. — :133-136
- Route paths `/chat` and `/chat/evidence` are the MCP `ask` and `polymath_search` entries (:7-8, :227); renaming breaks external agents (Claude Code/Hermes per :257).
- LEGACY has no runtime path (:87, :137-138) — any mode-list change must keep `validate_mode` and this docstring in sync.
- `evidence` stays a response add-on, not a runtime input (:97-99) — moving it into `StreamChatRequest` changes the never-a-second-retrieval guarantee.

## VERIFY
```verify
grep -Fq 'CHAT_DEFAULT_SYNTHESIZER = "deterministic-template-v3"' orchestrator/orchestrator/api/chat.py
grep -Fq 'return validate_mode(requested or MODE_HYBRID)' orchestrator/orchestrator/api/chat.py
grep -Fq 'mode=(req.mode or resolve_chat_mode(None)),' orchestrator/orchestrator/api/chat.py
grep -Fq 'sreq.evidence_only = True' orchestrator/orchestrator/api/chat.py
grep -Fq 'meta.setdefault("mode", "UNKNOWN")' orchestrator/orchestrator/api/chat.py
test "$(grep -c -F 'explore=False' orchestrator/orchestrator/api/chat.py)" -ge 2
test "$(grep -c -F 'out["evidence_contract"] = "retrieve-evidence-rows-v1"' orchestrator/orchestrator/api/chat.py)" -ge 2
test "$(grep -c -F 't.t0' orchestrator/orchestrator/api/chat.py)" -ge 2
```
