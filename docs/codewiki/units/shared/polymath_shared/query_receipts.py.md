# unit: shared/polymath_shared/query_receipts.py
anchor: shared/polymath_shared/query_receipts.py:1-279

## purpose
QUERY-RECEIPTS-V1: writes one durable row per served query (`/chat`, `/ask`, `/retrieve`) into the `query_receipts` table (migration 0047), after the response is composed — best effort, own short transaction, never on the request's critical path, failures logged and swallowed. shared/polymath_shared/query_receipts.py:1-9 [DERIVED]
Read side serves the MCP tool `recent_queries`, `GET /queries`, and `scripts/query_log.py`. shared/polymath_shared/query_receipts.py:9 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `summarize_response` | def | `(kind: str, out: Any) -> dict` | shared/polymath_shared/query_receipts.py:32-107 | api/* (note) |
| `knowledge_scope_of` | def | `(req: Any) -> dict \| None` | shared/polymath_shared/query_receipts.py:110-120 | api/* (note) |
| `record_query_receipt` | def | `(tx_factory, *, kind, question, req, scope_corpora, scope_kind, wall_ms, out=None, error=None, client=None) -> str \| None` | shared/polymath_shared/query_receipts.py:178-218 | api/* (note) |
| `recent_queries` | def | `(conn, *, corpus_id=None, kind=None, limit=20, since_h=24.0) -> list[dict]` | shared/polymath_shared/query_receipts.py:244-253 | api/* (note) |
| `query_summary` | def | `(conn, *, corpus_id=None, kind=None, since_h=24.0) -> list[dict]` | shared/polymath_shared/query_receipts.py:256-270 | api/* (note) |
| `Timer` | class | `with Timer() as t -> t.ms (float)`; methods `__enter__`, `__exit__` | shared/polymath_shared/query_receipts.py:273-279 | api/* (note) |

Module imported by: `orchestrator/orchestrator/api/_small-modules`, `ask.py`, `chat.py`, `deep_research.py`, `retrieve.py`, `ui.py` (FACTS.importers). Symbol-level attribution not in FACTS.
Private helpers: `_head` (27-29), `_shrink_lists` (135-143), `_meta_json` (146-175), `_row` (221-229), `_where` (232-241).

## contracts

**`summarize_response(kind, out)`** — pure, no side effects. shared/polymath_shared/query_receipts.py:33 [DERIVED]
- in: `kind: str`, `out: Any` (handler response). Non-dict `out` → all-default result. shared/polymath_shared/query_receipts.py:36-37
- out default: `{"status": "ok", "verdict": None, "citations": None, "claims": None, "evidence": None, "source_docs": [], "meta": {}}`. shared/polymath_shared/query_receipts.py:34-35
- post: `citations` = length of a list `citations`; `source_docs` = sorted union of `source_document_ids` + `human_locators`, capped `[:32]`. shared/polymath_shared/query_receipts.py:62-71
- post: `evidence` = length of the first list found among `("evidence", "hits", "selected_children", "child_dense_lane")`; `source_docs` fallback from `source_name`/`doc_id`/`document_id`. shared/polymath_shared/query_receipts.py:75-83
- post: `kind == "ask"` — `objects`→evidence, `cited_document_ids`→citations+source_docs, `route`/`grounded`/`latency_ms` copied to meta, `verdict = str(out.get("route"))`, returns early. shared/polymath_shared/query_receipts.py:84-99
- post: `status = "abstained"` when `grounded is False` or empty `objects` (ask), or answer starts with `("i don't have enough grounded evidence", "i cannot answer", "insufficient evidence")` or `"insufficient" in verdict.lower()` (chat). shared/polymath_shared/query_receipts.py:96-105
- post: `meta` keeps only a 32-key whitelist (`mode, latent, corpus_ids, plan, verdict, reranker, rerank_degraded, lanes, timings, admission, answerability, trace_id, funnel, chat_plan, synthesis_version, model, phase_ms, used_evidence, legend, degraded, prompt, carry, composition, route, deep_research, generation, retrieval_trace, latent_selection, wildcard, trace_ms, synthesis, gap_check`). shared/polymath_shared/query_receipts.py:39-60

**`knowledge_scope_of(req)`**
- pre: `req.scope` must be `Mapping` or `RetrievalScope`, else `None` (= no scope sent). shared/polymath_shared/query_receipts.py:114-116
- out: `parse_scope(raw).as_dict()`; `ScopeError` → `{"invalid": True}` (the 422 case). shared/polymath_shared/query_receipts.py:117-120
- post: reads the request only — a response can never set or widen the scope. shared/polymath_shared/query_receipts.py:111-112

**`record_query_receipt(...)`**
- in: `tx_factory` = `polymath_shared.db.tx` context manager yielding a connection. shared/polymath_shared/query_receipts.py:182-183
- pre: `error is None` → summarize `out`; `error` set → fixed skeleton `status="error"`. shared/polymath_shared/query_receipts.py:187-189
- post: INSERT with `query_id = "q_" + uuid4().hex[:24]`, `clock_timestamp()`, `question_sha256` = sha256 of question, `question_head = _head(question)` (200 chars), `wall_ms = int(round(wall_ms))`, `client` head 120, `error` head 500, meta via `_meta_json`. shared/polymath_shared/query_receipts.py:185, 199-210
- post: if `principal_context.current()` truthy → `UPDATE query_receipts SET principal_id=...` (migration 0066; `client` stays the SOFTWARE identity). shared/polymath_shared/query_receipts.py:211-213
- out: `qid` on success, `None` on any exception; never raises. shared/polymath_shared/query_receipts.py:214-218

**`recent_queries(conn, ...)`** — rows ordered `received_at DESC`, `LIMIT %s`; scoped to `principal_id` when `principal_context.current()` is set; `received_at` returned as isoformat string. shared/polymath_shared/query_receipts.py:246-253, 223-225

**`query_summary(conn, ...)`** — per `(kind, COALESCE(mode, '-'))`: `n, p50_ms, p95_ms, max_ms, abstained, errors, avg_citations`; `p50_ms/p95_ms/avg_citations` rounded to 1 decimal. shared/polymath_shared/query_receipts.py:258-270, 226-228

## effect surface
- Postgres table `query_receipts`: written (INSERT shared/polymath_shared/query_receipts.py:199-203; UPDATE principal_id :213), read (:248-252, :260-269). Matches FACTS `tables_read`/`tables_written`.
- Ambient context read: `principal_context.current()` (:211, :246, :259).
- Lazy import inside `_meta_json`: `from polymath_shared.funnel import compact` (:156).
- SQL is Postgres dialect: `clock_timestamp()`, `make_interval(secs => %s)`, `= ANY(corpus_ids)`, `percentile_cont` (:203, :233, :238, :262-263).
- No files, network, Qdrant, subprocess, or env flags read.

## invariants
INVARIANT: `_meta_json` output is valid JSON, structurally shrunk, never text-sliced — `META_MAX_CHARS = 64_000` — shared/polymath_shared/query_receipts.py:123, 146-175 [DERIVED]
  fails-if: invalid JSON meta → INSERT fails → receipt silently dropped (the old `json.dumps(meta)[:8000]` bug, :147-149)
INVARIANT: `qid` length = 2 + 24 = 26 chars, prefix `"q_"` — shared/polymath_shared/query_receipts.py:185 [DERIVED]
  fails-if: the principal UPDATE at :213 cannot target the row
INVARIANT: `len(source_docs) <= 32` — shared/polymath_shared/query_receipts.py:71, 92 [DERIVED]
  fails-if: oversized array written to the column
INVARIANT: `DROP_ORDER[0] == "funnel"` and `DROP_ORDER[-1] == "chat_plan"` (forensic core — legend, used_evidence, chat_plan — dropped last) — shared/polymath_shared/query_receipts.py:124-132 [DERIVED]
  fails-if: plan/legend/used evidence lost before diagnostic bulk; forensics unreadable (:124-127)
INVARIANT: funnel drop keeps keys `("version", "counts", "lane_counts")` — shared/polymath_shared/query_receipts.py:170 [DERIVED]
  fails-if: counts that `test_chat_funnel` reads first disappear (:169)
INVARIANT: `record_query_receipt` never raises; returns `str | None` — shared/polymath_shared/query_receipts.py:215-218 [DERIVED]
  fails-if: a receipt failure would fail the served query, violating the module contract (:183-184)
INVARIANT: `Timer.__exit__` returns `False` — shared/polymath_shared/query_receipts.py:278 [DERIVED]
  fails-if: returning True would swallow handler exceptions
INVARIANT: full question text never persisted — only sha256 hex + `_head(question)` (200 chars) — shared/polymath_shared/query_receipts.py:207-208, 27 [DERIVED]
  fails-if: raw question leakage into receipts

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid4 :185; `time.perf_counter` :275, :278; `clock_timestamp()` :203; DB reads :248-252, :260-269; ambient `principal_context` :211, :246, :259). `summarize_response`, `knowledge_scope_of`, `_meta_json`, `_shrink_lists` are pure [INFERRED: no clock/uuid/db/env reads inside their bodies].
idempotency: UNSAFE — `record_query_receipt` INSERTs a fresh row with a fresh uuid per call (:185, :199-203); a retried request writes a second receipt. Reads (`recent_queries`, `query_summary`) are SAFE.

## failure behaviour
- Broad `except Exception` in `record_query_receipt`: logs `log.warning("query receipt not written: %s", ...)` with `extra={"error_code": "QUERY_RECEIPT_FAILED"}` and returns `None` — caller sees `None` qid, the served response is unaffected. shared/polymath_shared/query_receipts.py:215-218, 183-184
- `ScopeError` in `knowledge_scope_of` → `{"invalid": True}`, never raised. shared/polymath_shared/query_receipts.py:118-120
- `_meta_json` over budget after all shrink stages → `{"truncated": True, "keys": sorted(m)}` — receipt still written, meta reduced to key names. shared/polymath_shared/query_receipts.py:175
- No error codes raised by this module [INFERRED: the single broad handler plus pure helpers leave no other exit].

## dumb-code flags
- Dead branch: `"ask"` in `if kind in ("chat", "ask")` (:102) is unreachable — the ask path already returned at :99. [DERIVED]
- Magic numbers: `200` default head (:27), `120` client head (:204), `500` error head (:210), `32` source_docs cap (:71, :92), 24-char uuid slice (:185), `3600.0` hours→secs (:234).
- Duplicated literal sets: 12 key names appear in both the meta whitelist (:39-60) and `DROP_ORDER` (:131-132); `SHRINK_LISTS_IN` (:130) repeats 4 of them; `"latent"` is additionally a column (:200).
- `verdict` means different things per kind: ask → `str(out.get("route"))` (:98); others → `meta.verdict` or `out.verdict` (:100, :106).
- INSERT then a separate UPDATE for `principal_id` (:199-213) instead of one INSERT — two statements in one transaction.
- `"retrieve"` kind gets no dedicated branch in `summarize_response` — only `"ask"` (:84) and `"chat"` (:102) are special-cased; /retrieve relies on the generic evidence extraction (:75-83). [DERIVED]

## refactor notes
- Blast radius: imported by `orchestrator/orchestrator/api/{_small-modules, ask.py, chat.py, deep_research.py, retrieve.py, ui.py}` (FACTS.importers) — signature changes to `record_query_receipt`, `recent_queries`, `query_summary`, `Timer` touch all six.
- INSERT column list (:200-202) + principal UPDATE (:213) encode migrations 0047 and 0066; must stay in sync with readers `recent_queries` (:248-250), `query_summary` (:261-267), `GET /queries`, `scripts/query_log.py` (:9).
- Meta whitelist (:39-60): a handler meta key not listed is silently absent from receipts; a listed key missing from `DROP_ORDER` can never be dropped when over budget.
- `DROP_ORDER` ordering is deliberate (:124-127, :169) — do not reorder without updating forensic readers.
- `kind` dispatch (:84, :102): a new endpoint kind falls through to the generic path; abstention detection exists only for chat/ask.
- `_where` principal semantics: no `principal_context` = legacy caller sees every receipt (:235-236); tightening changes legacy visibility.
- `client` = software identity, `principal_id` = actor (migration 0066) — do not merge (:212).

## VERIFY
```verify
grep -Fq 'META_MAX_CHARS = 64_000' shared/polymath_shared/query_receipts.py
grep -Fq 'qid = "q_" + uuid.uuid4().hex[:24]' shared/polymath_shared/query_receipts.py
grep -Fq 'UPDATE query_receipts SET principal_id=%s WHERE query_id=%s' shared/polymath_shared/query_receipts.py
grep -Fq 'extra={"error_code": "QUERY_RECEIPT_FAILED"}' shared/polymath_shared/query_receipts.py
! grep -Fq 'time.time()' shared/polymath_shared/query_receipts.py
test "$(grep -c -F 'truncated' shared/polymath_shared/query_receipts.py)" -ge 4
```
