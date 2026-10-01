# unit: orchestrator/orchestrator/api/chat.py
anchor: orchestrator/orchestrator/api/chat.py:1-248

## purpose
One-shot JSON transport of CHAT-RUNTIME-V1: maps `ChatRequest` onto the runtime's `StreamChatRequest` and drains the same `run_chat` generator `/chat/stream` streams, returning the answer frame as one JSON object (orchestrator/orchestrator/api/chat.py:1-7). `/chat/evidence` runs the same turn forced evidence-only — full retrieval/planning, no synthesis LLM — for external agents that do their own reasoning (orchestrator/orchestrator/api/chat.py:222-225). Callers: MCP `ask` posts here (orchestrator/orchestrator/api/chat.py:7); module imported by `orchestrator/orchestrator/main.py` [DERIVED: FACTS.importers].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ChatRequest` | class (pydantic `BaseModel`) | fields: `message, corpus_id, corpus_ids, workspace, all_authorized, mode, latent, utility, retrieval, evidence, synthesizer, history, carry_context, compiler, reasoning, reasoning_blend, corpus_explorer, evidence_only, scope` | orchestrator/orchestrator/api/chat.py:44-74 | request body of both routes |
| `stream_request` | def | `(req: ChatRequest) -> StreamChatRequest` | orchestrator/orchestrator/api/chat.py:77-114 | internal (`_chat_impl`:122, `_evidence_impl`:216) |
| `resolve_chat_mode` | def | `(requested: str | None) -> str` | orchestrator/orchestrator/api/chat.py:131-140 | internal (`stream_request`:105) |
| `attach_evidence_rows` | def | `(out: dict, req: ChatRequest) -> dict` | orchestrator/orchestrator/api/chat.py:143-178 | internal (`_chat_impl`:124) |
| `chat` | route `POST /chat` | `async (req: ChatRequest, request: Request) -> dict` | orchestrator/orchestrator/api/chat.py:182 | main.py router; MCP `ask` |
| `chat_evidence` | route `POST /chat/evidence` | `async (req: ChatRequest, request: Request) -> dict` | orchestrator/orchestrator/api/chat.py:222 | main.py router; external agents |

## contracts

**`stream_request` (CHAT-REQUEST-MAP-V1, orchestrator/orchestrator/api/chat.py:77-114)**
- in: any `ChatRequest`; out: `StreamChatRequest` with the field table at orchestrator/orchestrator/api/chat.py:80-99.
- pre: `mode` None/"" → `resolve_chat_mode(None)` = HYBRID (orchestrator/orchestrator/api/chat.py:105, 140).
- post: `synthesizer` None → `CHAT_DEFAULT_SYNTHESIZER` = `"deterministic-template-v3"` (orchestrator/orchestrator/api/chat.py:107); explicit modes pass through unvalidated here — the runtime is the sole validator (orchestrator/orchestrator/api/chat.py:85-87, 136-138).
- `evidence` is NOT mapped: response add-on applied after the turn (orchestrator/orchestrator/api/chat.py:97-99).

**`resolve_chat_mode` (orchestrator/orchestrator/api/chat.py:131-140)**
- in: `requested: str | None`; out: `validate_mode(requested or MODE_HYBRID)` (orchestrator/orchestrator/api/chat.py:140).

**`attach_evidence_rows` (CHAT-EVIDENCE-ROWS-V1, orchestrator/orchestrator/api/chat.py:143-178)**
- in: `out` dict carrying `citations[].locators` / `source_document_ids`; builds rows from the answer's own citations, never a second retrieval (orchestrator/orchestrator/api/chat.py:145-147).
- post: `out["evidence_contract"] = "retrieve-evidence-rows-v1"` on success (orchestrator/orchestrator/api/chat.py:169); `meta["requested_mode"] = req.mode` and `meta.setdefault("mode", "UNKNOWN")` (orchestrator/orchestrator/api/chat.py:176-177).

**`chat` (QUERY-RECEIPTS-V1, orchestrator/orchestrator/api/chat.py:182-210)**
- post: exactly one receipt row per call, `kind="chat"`, `client` = User-Agent header; runtime rejections before its own writer get a fallback receipt here (orchestrator/orchestrator/api/chat.py:186-194, 199-209).

**`chat_evidence` (REASONING-BOUNDARY-V1, orchestrator/orchestrator/api/chat.py:222-247)**
- post: forces `sreq.evidence_only = True` and runs `run_chat(sreq, route="chat/evidence", ...)`; returns versioned EvidencePacket with `synthesis_performed=false` — no synthesis LLM, no reviewer (orchestrator/orchestrator/api/chat.py:216-218, 223-225).

## effect surface
- Postgres via `tx()`: read connection for `build_evidence_rows(conn, ...)` inside `with tx() as conn` (orchestrator/orchestrator/api/chat.py:162-168); receipt writes via `record_query_receipt(tx, ...)` (orchestrator/orchestrator/api/chat.py:194, 205, 231, 242). No table names appear in this file [DERIVED: FACTS `tables_read: []`, `tables_written: []`].
- Env: none read in this file; comment states `compiler` None → `POLYMATH_CHAT_COMPILER`, resolved by the runtime (orchestrator/orchestrator/api/chat.py:65).
- Qdrant / network / subprocess / files: none in this unit.

## invariants

INVARIANT: identical request → identical compiled plan, retrieval decision, evidence ids, carry admission, executed mode, degraded list, synthesis contract on `/chat` and `/chat/stream` — orchestrator/orchestrator/api/chat.py:10-12 [DERIVED]
  fails-if: `stream_request` mapping drops or renames a runtime field; the two transports diverge.
INVARIANT: default synthesizer == `CHAT_DEFAULT_SYNTHESIZER` == `"deterministic-template-v3"` at definition (line 41) and at use `req.synthesizer or CHAT_DEFAULT_SYNTHESIZER` (line 107) — orchestrator/orchestrator/api/chat.py:41,107 [DERIVED]
  fails-if: a None synthesizer falls through to the stream's UI LLM; `claims`/`citations` contract for MCP `ask` breaks (orchestrator/orchestrator/api/chat.py:38-40).
INVARIANT: default `/chat` mode is `MODE_HYBRID` (`validate_mode(requested or MODE_HYBRID)`); `/retrieve` keeps `retrieval_modes.DEFAULT_MODE` — orchestrator/orchestrator/api/chat.py:140,134-135 [DERIVED]
  fails-if: no-mode `/chat` regresses to the frozen LEGACY path (12,732 claims, 437 KB triple dump, 30–50 s) mislabeled HYBRID (orchestrator/orchestrator/api/chat.py:133-135).
INVARIANT: chunk rerank_score = `float(len(chunk_ids) - i)` where `i` is first-occurrence index → strictly descending, first chunk scores `len(chunk_ids)` — orchestrator/orchestrator/api/chat.py:165 [DERIVED]
  fails-if: evidence-row ordering contract changes downstream.
INVARIANT: evidence limit = `max(12, len(chunk_ids))` — orchestrator/orchestrator/api/chat.py:168 [DERIVED]
INVARIANT: chunk ids extracted only from locators matching `^chunk:([A-Za-z0-9_]+)`, deduped by first occurrence — orchestrator/orchestrator/api/chat.py:128,153-156 [DERIVED]
  fails-if: locator format change silently empties `evidence_rows`.
INVARIANT: `evidence_rows_error` string length ≤ 200 (`[:200]`) — orchestrator/orchestrator/api/chat.py:172 [DERIVED]
INVARIANT: exactly one receipt row per `/chat` call, `kind="chat"` — orchestrator/orchestrator/api/chat.py:188,194 [DERIVED]
  fails-if: double-write if the fallback fires after the runtime already receipted; guarded by `if not receipted` (orchestrator/orchestrator/api/chat.py:200,237).

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` for receipt `wall_ms` — orchestrator/orchestrator/api/chat.py:207,244; db receipt writes via `tx` — orchestrator/orchestrator/api/chat.py:194,231). Answer payload itself is contractually identical for identical requests (orchestrator/orchestrator/api/chat.py:10-12).
idempotency: UNSAFE — every POST writes one receipt row (orchestrator/orchestrator/api/chat.py:188,194,231); `attach_evidence_rows` opens a fresh DB read per call (orchestrator/orchestrator/api/chat.py:162).

## failure behaviour
- `except Exception` at orchestrator/orchestrator/api/chat.py:170 — evidence-row build failure swallowed: caller sees `evidence_rows=[]` plus `evidence_rows_error` (`"<Type>: <msg>"[:200]`); HTTP success, answer already stands (orchestrator/orchestrator/api/chat.py:170-172).
- `except Exception` at orchestrator/orchestrator/api/chat.py:199 and 236 — if the runtime never receipted (`not receipted`), a fallback receipt with `error=f"{type(exc).__name__}: ..."` is recorded, then `raise` re-raises unchanged (orchestrator/orchestrator/api/chat.py:199-210, 236-247).
- Assembly failures stay loud as 502 (orchestrator/orchestrator/api/chat.py:20).

## dumb-code flags
- Magic `12` in `max(12, len(chunk_ids))` (orchestrator/orchestrator/api/chat.py:168); magic `200` truncation (orchestrator/orchestrator/api/chat.py:172); magic `0.0` rerank score for documents (orchestrator/orchestrator/api/chat.py:166); `"UNKNOWN"` mode sentinel (orchestrator/orchestrator/api/chat.py:176).
- Fabricated rerank scores derived from list position, not real retrieval scores (orchestrator/orchestrator/api/chat.py:165).
- Near-duplicate fallback-receipt blocks: `chat` 199-210 vs `chat_evidence` 236-247 — `scope_corpora`/`scope_kind`/`wall_ms` logic copied verbatim (orchestrator/orchestrator/api/chat.py:202-209,239-246).
- Dead defensive `getattr(req, "corpus_explorer", False)` / `evidence_only` / `scope` on a pydantic model whose fields are declared at lines 71-74 — the default branch can never trigger (orchestrator/orchestrator/api/chat.py:111-113,71-74) [INFERRED: pydantic always sets declared fields].
- Local import of `MODE_HYBRID, validate_mode` inside `resolve_chat_mode` while sibling `polymath_shared` imports sit at module top (orchestrator/orchestrator/api/chat.py:139 vs 31-32).
- `/chat/evidence` reuses receipt `kind="chat"`, distinguishable only via `route="chat/evidence"` (orchestrator/orchestrator/api/chat.py:218,231).

## refactor notes
- `orchestrator/orchestrator/main.py` imports this module [DERIVED: FACTS.importers]; `POST /chat` and `POST /chat/evidence` are external API — renaming paths breaks MCP `ask` and external agents (orchestrator/orchestrator/api/chat.py:7,96-104,222-226).
- MCP `ask` / TRAIL read `claims` and `citations` from the default-synthesizer JSON (`contracts/answer/v2`) — do not change that shape (orchestrator/orchestrator/api/chat.py:16-18,38-40).
- `meta.mode` is the EXECUTED mode (CHAT-MODE-TRUTH-V1) stamped by `run_chat`; never relabel (orchestrator/orchestrator/api/chat.py:19,174-175).
- Locator format `chunk:<id>` is the parse contract feeding `attach_evidence_rows` (orchestrator/orchestrator/api/chat.py:128,153-155).
- `evidence_contract = "retrieve-evidence-rows-v1"` is a versioned contract string; bump on any row-shape change (orchestrator/orchestrator/api/chat.py:169).
- Changing `resolve_chat_mode` must not pull `/retrieve` off `retrieval_modes.DEFAULT_MODE` — that default is frozen for `/retrieve`'s own evaluations (orchestrator/orchestrator/api/chat.py:134-136).

## VERIFY
```verify
grep -Fq 'CHAT_DEFAULT_SYNTHESIZER = "deterministic-template-v3"' orchestrator/orchestrator/api/chat.py
grep -Fq 'validate_mode(requested or MODE_HYBRID)' orchestrator/orchestrator/api/chat.py
grep -Fq 'sreq.evidence_only = True' orchestrator/orchestrator/api/chat.py
grep -Fq 'max(12, len(chunk_ids))' orchestrator/orchestrator/api/chat.py
grep -Eq 'evidence_rows_error.*\[:200\]' orchestrator/orchestrator/api/chat.py
test "$(grep -c -F 'kind="chat"' orchestrator/orchestrator/api/chat.py)" -ge 2
```
