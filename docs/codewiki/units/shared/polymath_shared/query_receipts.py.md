# unit: shared/polymath_shared/query_receipts.py
anchor: shared/polymath_shared/query_receipts.py:1-286

## purpose
QUERY-RECEIPTS-V1: writes one durable row per served query into Postgres table `query_receipts` (migration 0047) after the response is composed — best effort, own short transaction, off the request's critical path (shared/polymath_shared/query_receipts.py:1-10) [DERIVED]. Readers: MCP tool `recent_queries`, `GET /queries`, `scripts/query_log.py` (shared/polymath_shared/query_receipts.py:8-9) [DERIVED]. Module is imported by 9 orchestrator API modules (ask, chat, corpus_plan, deep_research, product, product_report, retrieve, ui, _small-modules) [FACTS.importers] [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `summarize_response` | def | (kind: str, out: Any) -> dict | shared/polymath_shared/query_receipts.py:32-113 | — (module importers above) |
| `knowledge_scope_of` | def | (req: Any) -> dict \| None | shared/polymath_shared/query_receipts.py:116-126 | — |
| `record_query_receipt` | def | (tx_factory, *, kind, question, req, scope_corpora, scope_kind, wall_ms, out=None, error=None, client=None) -> str \| None | shared/polymath_shared/query_receipts.py:184-224 | /chat, /ask, /retrieve handlers (docstring 5-6) |
| `recent_queries` | def | (conn, *, corpus_id=None, kind=None, limit=20, since_h=24.0) -> list[dict] | shared/polymath_shared/query_receipts.py:250-259 | MCP `recent_queries`, `GET /queries`, `scripts/query_log.py` (docstring 8-9) |
| `query_summary` | def | (conn, *, corpus_id=None, kind=None, since_h=24.0) -> list[dict] | shared/polymath_shared/query_receipts.py:262-276 | readers of `query_receipts` (docstring 8-9) |
| `Timer` | class | `__enter__` -> self (sets `.t0`), `__exit__` sets `.ms` | shared/polymath_shared/query_receipts.py:279-285 | — |

Private helpers: `_head`, `_shrink_lists`, `_meta_json`, `_row`, `_where` (shared/polymath_shared/query_receipts.py:27-29,141-149,152-181,227-235,238-247) [DERIVED].

## contracts

**summarize_response(kind, out)** — pure, no IO (shared/polymath_shared/query_receipts.py:33) [DERIVED].
- in: `kind` str; `out` any (non-dict -> default summary) (shared/polymath_shared/query_receipts.py:36-37).
- out: dict with keys `status` ("ok" or "abstained"), `verdict`, `citations` (count), `claims` (count), `evidence` (count), `source_docs` (list), `meta` (whitelisted subset) (shared/polymath_shared/query_receipts.py:34-35,39-66) [DERIVED].
- post: meta keeps only the literal whitelist — `mode, latent, corpus_ids, plan, verdict, reranker, rerank_degraded, lanes, timings, admission, answerability, trace_id, funnel, chat_plan, synthesis_version, model, phase_ms, used_evidence, legend, degraded, prompt, carry, composition, route, deep_research, generation, retrieval_trace, latent_selection, wildcard, trace_ms, synthesis, gap_check, product_search, product_report` (shared/polymath_shared/query_receipts.py:39-66) [DERIVED].
- post: `kind == "ask"` branch returns early; status "abstained" when `grounded is False` or empty `objects`; verdict = `route` (shared/polymath_shared/query_receipts.py:90-105) [DERIVED].
- post: chat abstained when answer starts with "i don't have enough grounded evidence" / "i cannot answer" / "insufficient evidence" or verdict contains "insufficient" (shared/polymath_shared/query_receipts.py:108-111) [DERIVED].

**knowledge_scope_of(req)**
- in: any request object; reads `req.scope` via getattr (shared/polymath_shared/query_receipts.py:120-121).
- out: `parse_scope(raw).as_dict()`; `None` when scope absent/not Mapping/RetrievalScope; `{"invalid": True}` on `ScopeError` (shared/polymath_shared/query_receipts.py:123-126) [DERIVED].
- pre: scope read from the request only; a response can never widen it (shared/polymath_shared/query_receipts.py:117-119) [DERIVED].

**record_query_receipt(...)**
- in: `tx_factory` = `polymath_shared.db.tx`, a context manager yielding a connection (shared/polymath_shared/query_receipts.py:188-189) [DERIVED].
- pre: table `query_receipts` exists (migration 0047, shared/polymath_shared/query_receipts.py:6) [DERIVED].
- post: exactly one INSERT; `received_at = clock_timestamp()`; meta stored as `%s::jsonb` via `_meta_json` (shared/polymath_shared/query_receipts.py:204-216) [DERIVED].
- post: returns qid `"q_" + uuid4().hex[:24]` on success, `None` on any failure (shared/polymath_shared/query_receipts.py:191,220,223) [DERIVED].
- post: `principal_id` set from `principal_context.current()` when truthy (migration 0066); `client` column stays the software identity (shared/polymath_shared/query_receipts.py:217-219) [DERIVED].
- post: error path writes status "error" with all summary fields None (shared/polymath_shared/query_receipts.py:193-195) [DERIVED].

**recent_queries / query_summary**
- pre: conn is an open DB connection; filters scoped to `principal_context.current()` when set (a principal sees only its own receipts; no principal = legacy caller) (shared/polymath_shared/query_receipts.py:241-242,252,265) [DERIVED].
- out: rows ISO-formatted `received_at`; `p50_ms`, `p95_ms`, `avg_citations` rounded to 1 decimal (shared/polymath_shared/query_receipts.py:229-234) [DERIVED].
- post: query_summary groups by `(kind, COALESCE(mode, '-'))` with `percentile_cont` 0.5 / 0.95 and FILTER counts for abstained/error (shared/polymath_shared/query_receipts.py:267-275) [DERIVED].

## effect surface
- Postgres write: `INSERT INTO query_receipts (...)` (shared/polymath_shared/query_receipts.py:204-216); `UPDATE query_receipts SET principal_id=...` (shared/polymath_shared/query_receipts.py:219).
- Postgres read: `SELECT ... FROM query_receipts` in recent_queries (shared/polymath_shared/query_receipts.py:253-258) and query_summary (shared/polymath_shared/query_receipts.py:266-275); window via `now() - make_interval(secs => %s)` (shared/polymath_shared/query_receipts.py:239).
- Server clock: `clock_timestamp()` in INSERT (shared/polymath_shared/query_receipts.py:209).
- Logging: `log.warning(..., extra={"error_code": "QUERY_RECEIPT_FAILED"})` (shared/polymath_shared/query_receipts.py:222).
- Qdrant / files / network / subprocess / env flags: none in source [DERIVED].

## invariants
INVARIANT: every non-final return of `_meta_json` satisfies `len(txt) <= META_MAX_CHARS` (64_000) — shared/polymath_shared/query_receipts.py:158-181 [DERIVED]
  fails-if: oversized invalid JSON reaches the INSERT and the receipt is silently dropped (the JSON-SAFE-META-V1 bug, 152-156).
INVARIANT: `source_docs` length ≤ 32 — shared/polymath_shared/query_receipts.py:77,98 [DERIVED]
  fails-if: unbounded doc-id arrays bloat every receipt row.
INVARIANT: question persisted only as sha256 hexdigest + `_head(question)` (200 chars), never full text — shared/polymath_shared/query_receipts.py:27-29,213-214 [DERIVED]
  fails-if: raw question text lands in the durable table.
INVARIANT: a shrunk list keeps exactly LIST_MAX_ITEMS = 8 head items plus `{"truncated": True, "held": len(obj)}` — shared/polymath_shared/query_receipts.py:143-145 [DERIVED]
  fails-if: forensics cannot tell truncation from absence.
INVARIANT: DROP_ORDER ends with `"legend", "used_evidence", "chat_plan"` (forensic core dropped last) — shared/polymath_shared/query_receipts.py:130-138 [DERIVED]
  fails-if: plan/evidence vanish first from large receipts (the WILDCARD 32 KB incident, 130-132).
INVARIANT: funnel drop retains keys `"version"`, `"counts"`, `"lane_counts"` — shared/polymath_shared/query_receipts.py:175-177 [DERIVED]
  fails-if: counts a forensic reads first are lost (referenced test_chat_funnel, 175).
INVARIANT: `record_query_receipt` returns a str or None and never raises — shared/polymath_shared/query_receipts.py:191,221-223 [DERIVED]
  fails-if: a receipt failure breaks a served query, violating the module contract (7-8).

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid.uuid4 at shared/polymath_shared/query_receipts.py:191; time.perf_counter at 281,284; DB clock_timestamp() at 209; ambient `principal_context.current()` at 217,252,265)
idempotency: UNSAFE (each call INSERTs a fresh row with a fresh qid at 191,204 — replay duplicates receipts)

## failure behaviour
- Single broad handler `except Exception` around the whole write: swallowed — `log.warning` with `error_code: QUERY_RECEIPT_FAILED`, caller receives `None`; request unaffected (shared/polymath_shared/query_receipts.py:221-223) [FACTS.fallbacks, DERIVED].
- Error receipts: `error` param -> status "error", all counters None, `_head(error, 500)` stored (shared/polymath_shared/query_receipts.py:193-195,216) [DERIVED].
- No exception is raised anywhere in the unit (no `raise` in source) [DERIVED].

## dumb-code flags
- Dead tuple member: `if kind in ("chat", "ask")` at 108 — the `"ask"` case already returned at 90-105, so it is unreachable for ask (shared/polymath_shared/query_receipts.py:90-108) [DERIVED].
- Magic truncation lengths scattered: `_head` default 200 (27), client 120 (210), error 500 (216), source_docs 32 (77,98), uuid hex 24 (191) [DERIVED].
- `FUNNEL_MAX_CHARS = 8_000` equals the retired slice size `[:8000]` described in the docstring (134 vs 153-154) — same number, new meaning [DERIVED].
- `"verdict"` has two sources: whitelisted in meta (41) and read again top-level `out.get("verdict")` (106) [DERIVED].
- Key names duplicated across constants: `"latent"`, `"latent_selection"`, `"retrieval_trace"`, `"wildcard"` appear in both SHRINK_LISTS_IN and DROP_ORDER (136-137) [DERIVED].
- `mode` read from `req` then re-derived from `summ["meta"]` (199-202) [DERIVED].

## refactor notes
- Signature changes to `record_query_receipt`, `recent_queries`, `query_summary` ripple through all 9 importers under `orchestrator/orchestrator/api/` (FACTS.importers) [DERIVED].
- INSERT column list is coupled to the `query_receipts` schema (migration 0047, docstring line 6; principal_id migration 0066 at 217-219) [DERIVED].
- The meta whitelist (39-66) is the persistence contract for every named feature reading its key back from receipts (funnel, chat_plan, generation, retrieval_trace, product_search, product_report, …) — removing a key deletes it from all future receipts [DERIVED].
- DROP_ORDER / SHRINK_LISTS_IN ordering is the documented RECEIPT-SHRINK-ORDER policy (live 2026-09-27) with test_chat_funnel as a referenced consumer (130-133,175) — reorder only with that test [DERIVED].
- `_meta_json` must never slice a JSON string (JSON-SAFE-META-V1, 152-156) — any refactor reintroducing text slicing regresses the silent-drop bug [DERIVED].
- Callers depend on the None-return-never-raise behaviour (221-223); converting to raised exceptions breaks every handler [INFERRED — docstring "failures logged and swallowed" plus 9 importers].

## VERIFY
```verify
grep -Fq 'META_MAX_CHARS = 64_000' shared/polymath_shared/query_receipts.py
grep -Fq 'qid = "q_" + uuid.uuid4().hex[:24]' shared/polymath_shared/query_receipts.py
grep -Fq 'extra={"error_code": "QUERY_RECEIPT_FAILED"}' shared/polymath_shared/query_receipts.py
grep -Eq 'DROP_ORDER = \("funnel", "prompt", "carry"' shared/polymath_shared/query_receipts.py
test "$(grep -c -F 'truncated' shared/polymath_shared/query_receipts.py)" -ge 4
! grep -Fq 'raise ' shared/polymath_shared/query_receipts.py
```
