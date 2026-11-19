# unit: orchestrator/orchestrator/api/chat.py
anchor: orchestrator/orchestrator/api/chat.py:1-325

## purpose
- POST `/chat`: one-shot JSON transport of CHAT-RUNTIME-V1. Maps `ChatRequest` onto the runtime's `StreamChatRequest`, drains the SAME generator `/chat/stream` streams, returns the answer frame as one JSON object. MCP `ask` posts here. — chat.py:1-14 [DERIVED]
- POST `/chat/evidence`: the evidence boundary. Runs the FULL retrieval/planning pipeline, returns a versioned EvidencePacket with `synthesis_performed=false` — no synthesis LLM, no reviewer. — chat.py:299-303 [DERIVED]
- The unit owns mapping, receipts and evidence-row add-ons only; retrieval, compiler and synthesis live in the runtime. — chat.py:3-5 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `router` | APIRouter | mounts POST `/chat`, POST `/chat/evidence` | chat.py:37, 192, 298 | orchestrator/orchestrator/main.py |
| `ChatRequest` | class (BaseModel) | 20 request fields -> pydantic model | chat.py:45-78 | — |
| `stream_request` | def | `(req: ChatRequest) -> StreamChatRequest` | chat.py:86-125 | — (this unit) |
| `resolve_chat_mode` | def | `(requested: str \| None) -> str` | chat.py:142-151 | — (this unit) |
| `chat` | async def / route | `(req, request) -> dict` — POST `/chat` | chat.py:192-221 | main.py via router |
| `chat_evidence` | async def / route | `(req, request) -> dict` — POST `/chat/evidence` | chat.py:298-324 | main.py via router |
| `attach_evidence_rows` | def | `(out: dict, req) -> dict` | chat.py:154-189 | — (this unit) |
| `attach_packet_rows` | def | `(out: dict, req) -> dict` | chat.py:266-295 | — (this unit) |
| `attach_judge_scores` | def | `(rows: list[dict], scores) -> dict \| None` | chat.py:238-263 | — (this unit) |

Routes (FACTS.routes): POST `/chat` -> `chat` (chat.py:193); POST `/chat/evidence` -> `chat_evidence` (chat.py:299).

## contracts

**stream_request — chat.py:86-125**
- in: `ChatRequest`; field table in docstring chat.py:88-109.
- out: `mode=(req.mode or resolve_chat_mode(None))` (chat.py:115); `synthesizer=(req.synthesizer or CHAT_DEFAULT_SYNTHESIZER)` (chat.py:117); `history`/`carry_context`/`reasoning_blend` copied as `list(... or [])` (chat.py:118-120).
- post: `evidence` is NOT a runtime input — response add-on only (chat.py:107-109, 134-135).
- post: `corpus_explorer`/`evidence_only`/`scope`/`product` copied via `getattr` with defaults `False`/`False`/`None`/`None` (chat.py:121-124).

**resolve_chat_mode — chat.py:142-151**
- out: `validate_mode(requested or MODE_HYBRID)` — default HYBRID (chat.py:151).
- post: explicit modes pass through; the runtime is the single validator (FAST/VECTOR, HYBRID, GRAPH, WILDCARD, ASK -> 422 `unknown_mode`; LEGACY has no runtime path) (chat.py:93-96, 147-149).

**chat (POST /chat) — chat.py:192-221**
- in: `ChatRequest` body; `user-agent` header becomes the receipt's `client` (chat.py:201).
- out: the drained answer of `run_chat(stream_request(req), route="chat", receipt=receipt)` (chat.py:133); `evidence: true` appends rows (chat.py:134-135).
- post: `meta.mode` is the EXECUTED mode (CHAT-MODE-TRUTH-V1) (chat.py:19, 185-187).
- post: assembly failures stay loud (502) per module docstring (chat.py:20).

**chat_evidence (POST /chat/evidence) — chat.py:224-235, 298-324**
- post: `sreq.evidence_only = True` — pipeline short-circuits before synthesis (chat.py:229, 225-227).
- post: `sreq.product = False` when `product` is None and client user agent `startswith(ADAPTER_CLIENTS)` (chat.py:230-231).
- out: versioned EvidencePacket, `synthesis_performed=false` (chat.py:301-302).

**attach_evidence_rows — chat.py:154-189**
- in: `citations[].locators` matched by `_LOC_CHUNK = re.compile(r"^chunk:([A-Za-z0-9_]+)")` (chat.py:139, 165); `source_document_ids` (chat.py:168).
- out: `evidence_rows` via `build_evidence_rows`, `limit=max(12, len(chunk_ids))`, `explore=False` (chat.py:174-179); `evidence_contract = "retrieve-evidence-rows-v1"` (chat.py:180); `meta.setdefault("mode", "UNKNOWN")`, `meta["requested_mode"] = req.mode` (chat.py:187-188).
- post: built from ids the answer already cites — never a second retrieval (chat.py:157-158).

**attach_packet_rows — chat.py:266-295**
- in: `evidence_packet.evidence` chunk_ids in packet order (chat.py:273-274); `graph_facts` with `fact_id` (chat.py:276).
- out: rows gain `utility_role`/`ca4_grade` when present (chat.py:286); `evidence_relevance` added when judge scores exist (chat.py:287-289); same `evidence_contract` string (chat.py:291).

**attach_judge_scores — chat.py:238-263**
- in: `scores` dict keyed by row id; only rows with `kind == "chunk"` scored (chat.py:252); bool and non-finite values skipped (chat.py:253-254).
- out: `None` when `scores` is not a dict (chat.py:247-248); else `{"rule": "rerank_score > 0", "judged", "relevant", "max_rerank_score", "verdict"}` with `verdict` one of `not_judged` / `relevant_evidence` / `no_relevant_evidence` (chat.py:261-263).
- post: scored rows get `rerank_score = round(score, 4)` and `relevant = score > 0` (chat.py:256-257).

## effect surface
- Query receipts: `record_query_receipt(tx, kind="chat", client=...)` — one row per `/chat` and `/chat/evidence` call, success path via `_sink` (chat.py:205, 308) and rejected-before-runtime calls in the except path (chat.py:216-220, 319-323). Store table not named in FACTS (`tables_read: []`, `tables_written: []`).
- DB connections: `with tx() as conn` to build evidence rows (chat.py:173, 279); reads happen inside `orchestrator.api.evidence_rows.build_evidence_rows`, not here.
- No direct network, subprocess or Qdrant access in this file; side effects live in `run_chat` (chat.py:133, 232) and `build_evidence_rows` (chat.py:174, 280).
- Env flag, documented only: `compiler: None -> POLYMATH_CHAT_COMPILER` (comment chat.py:66); the read happens in the runtime.
- Clocks: `time.perf_counter` at chat.py:218 and chat.py:321 (FACTS.nondeterminism).

## invariants
- INVARIANT: `/chat` default synthesizer == `"deterministic-template-v3"` (`CHAT_DEFAULT_SYNTHESIZER`) — chat.py:42, 117 [DERIVED]
  fails-if: MCP `ask` / TRAIL, which read `claims` and `citations` from the deterministic JSON contract, get a different answer shape (chat.py:39-41).
- INVARIANT: `/chat` default mode == `MODE_HYBRID`, not LEGACY — chat.py:115, 150-151 [DERIVED]
  fails-if: no-mode requests rerun the frozen LEGACY path (12,732 claims, 437 KB triple dump, 30-50 s) mislabeled HYBRID (chat.py:144-146).
- INVARIANT: evidence-rows limit == `max(12, len(chunk_ids))` on BOTH add-on paths — chat.py:179, 284 [DERIVED]
  fails-if: `/chat` and `/chat/evidence` return different row counts for the same chosen ids.
- INVARIANT: `evidence_contract` == `"retrieve-evidence-rows-v1"` on both paths — chat.py:180, 291 [DERIVED]
  fails-if: `polymath_search`, which consumes these rows (chat.py:269), rejects the packet.
- INVARIANT: `verdict` ∈ {`not_judged`, `relevant_evidence`, `no_relevant_evidence`} and rule string == `"rerank_score > 0"` — chat.py:261-263 [DERIVED]
  fails-if: callers switching on `verdict` misclassify the turn.
- INVARIANT: exactly one receipt row per call — `_sink` records on success; except path records only `if not receipted`, then re-raises — chat.py:205, 211, 221 and 308, 314, 324 [DERIVED]
  fails-if: rejected requests leave zero rows or runtime-written plus handler-written rows double-count.
- INVARIANT: adapter clients get `product = False` only when `product is None` — chat.py:230-231 [DERIVED]
  fails-if: a governed run's own evidence call runs product mode; an explicit `product=True` still overrides.
- INVARIANT: evidence-row add-on failure never fails the answer — `except Exception` -> `evidence_rows = []` + error string truncated to 200 chars — chat.py:181-183, 292-294 [DERIVED]
  fails-if: a rows bug turns a valid answer into a 5xx.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock — `time.perf_counter` feeds receipt `wall_ms` at chat.py:218 and chat.py:321; FACTS.nondeterminism). The mapping itself is pure; docstring claims an identical request yields the identical plan, evidence ids, executed mode and synthesis contract on both routes (chat.py:10-12) [DERIVED].
idempotency: UNSAFE — every POST writes one query-receipt row (`record_query_receipt`, chat.py:205, 216, 308, 319); retries add rows. The answer path itself has no write in this file.

## failure behaviour
- `attach_evidence_rows` / `attach_packet_rows`: broad `except Exception` swallowed (FACTS.fallbacks chat.py:181, 292). Caller sees the answer/packet with `evidence_rows: []` and `evidence_rows_error = f"{type(exc).__name__}: {exc}"[:200]` (chat.py:182-183, 293-294).
- `chat` / `chat_evidence`: `except Exception` — best-effort receipt, then `raise` unchanged (FACTS.fallbacks chat.py:210, 313; raise at chat.py:221, 324). A request the runtime rejected before running (empty message, unknown mode or synthesizer) is receipted here (chat.py:197-200).
- Documented status codes: assembly failures stay loud (502) (chat.py:20); unknown mode -> 422 `unknown_mode`, raised by the runtime not here (chat.py:95-96).

## dumb-code flags
- Magic number `12` in `limit=max(12, len(chunk_ids))`, duplicated — chat.py:179, 284 [DERIVED]
- Fabricated scores: `rerank_score` for child evidence is `float(len(chunk_ids) - i)` — packet position, not a judge score; `selected_documents` rows get `rerank_score: 0.0` — chat.py:176-177, 282 [DERIVED]
- Duplicated ~20-line receipt/except block between the two handlers — chat.py:201-221 vs 304-324 [DERIVED]
- Defensive `getattr` on fields already declared on the pydantic model (`corpus_explorer`, `evidence_only`, `scope`, `product`): defaults can never fire — chat.py:121-124 vs 72-78 [INFERRED: fields are declared, so getattr fallbacks are dead]
- `str(client).startswith(ADAPTER_CLIENTS)` is a prefix match: any user agent starting `polymath-adapter-step/` matches — chat.py:230, 83 [INFERRED: prefix semantics visible; over-broad client names would be caught]
- `meta.setdefault("mode", "UNKNOWN")` — string fallback, not an enum — chat.py:187 [DERIVED]
- FACTS renders `ADAPTER_CLIENTS` as a JSON list; SOURCE shows a tuple `("polymath-adapter-step/", "opportunity-research/")` — trust SOURCE — chat.py:83 [DERIVED]

## refactor notes
- Only importer is `orchestrator/orchestrator/main.py` (FACTS.importers) — it mounts `router`; the two POST paths are the external contract.
- `stream_request` is the CHAT-REQUEST-MAP-V1 field table; MCP `ask` inherits it (chat.py:7-8). A new `StreamChatRequest` field without a mapping line is silently dropped — the code comment says so: "miss the mapping below and they drop" (chat.py:72).
- Changing `CHAT_DEFAULT_SYNTHESIZER` changes every `/chat` call that names no synthesizer; MCP `ask` / TRAIL read `claims` and `citations` from the deterministic contract (chat.py:39-42, 117).
- `attach_evidence_rows` only sees locators matching `^chunk:([A-Za-z0-9_]+)`; other locator formats are silently dropped (chat.py:139, 163-167).
- The two receipt/except blocks must change together (chat.py:201-221, 304-324); they differ only in `_chat_impl` vs `_evidence_impl` and the `client` argument (chat.py:209 vs 312).
- `attach_judge_scores` implements the sign rule CA4's `grade_evidence` uses (`rerank_score > 0`) — changing the rule desynchronizes the two (chat.py:243, 262).

## VERIFY
```verify
grep -Fq 'CHAT_DEFAULT_SYNTHESIZER = "deterministic-template-v3"' orchestrator/orchestrator/api/chat.py
grep -Fq 'ADAPTER_CLIENTS = ("polymath-adapter-step/", "opportunity-research/")' orchestrator/orchestrator/api/chat.py
grep -Fq 'return validate_mode(requested or MODE_HYBRID)' orchestrator/orchestrator/api/chat.py
grep -Fq 'sreq.evidence_only = True' orchestrator/orchestrator/api/chat.py
grep -Fq '"retrieve-evidence-rows-v1"' orchestrator/orchestrator/api/chat.py
grep -Fq '(time.perf_counter() - t.t0) * 1000.0' orchestrator/orchestrator/api/chat.py
grep -Fq 'limit=max(12, len(chunk_ids)), explore=False' orchestrator/orchestrator/api/chat.py
```
