# unit: shared/polymath_shared/query_receipts.py
anchor: shared/polymath_shared/query_receipts.py:1-283

## purpose
QUERY-RECEIPTS-V1: one durable `query_receipts` row per served /chat, /ask, /retrieve query, written after the response is composed in its own short transaction, never on the request's critical path — failures logged and swallowed (migration 0047). — shared/polymath_shared/query_receipts.py:1-9 [DERIVED]
Read side feeds the MCP tool `recent_queries`, `GET /queries` and `scripts/query_log.py`. — shared/polymath_shared/query_receipts.py:9 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `summarize_response` | def | (kind: str, out: Any) -> dict | shared/polymath_shared/query_receipts.py:32-110 | module importers below |
| `knowledge_scope_of` | def | (req: Any) -> dict \| None | shared/polymath_shared/query_receipts.py:113-123 | module importers below |
| `record_query_receipt` | def | (tx_factory, *, kind, question, req, scope_corpora, scope_kind, wall_ms, out=None, error=None, client=None) -> str \| None | shared/polymath_shared/query_receipts.py:181-221 | module importers below |
| `recent_queries` | def | (conn, *, corpus_id=None, kind=None, limit=20, since_h=24.0) -> list[dict] | shared/polymath_shared/query_receipts.py:247-256 | module importers below |
| `query_summary` | def | (conn, *, corpus_id=None, kind=None, since_h=24.0) -> list[dict] | shared/polymath_shared/query_receipts.py:259-273 | module importers below |
| `Timer` | class | `__enter__` -> self; `__exit__(*exc)` -> False; sets `.ms` (float ms) | shared/polymath_shared/query_receipts.py:276-282 | module importers below |

Module importers (FACTS.importers, per-module not per-symbol): orchestrator/orchestrator/api/{_small-modules, ask.py, chat.py, corpus_plan.py, deep_research.py, retrieve.py, ui.py} — shared/polymath_shared/query_receipts.py:178-186 of FACTS [DERIVED]

## contracts

`summarize_response` (pure; docstring "pure") — shared/polymath_shared/query_receipts.py:32-33 [DERIVED]
- in: `kind` string; `out` = handler response. Non-dict `out` -> default dict `{"status": "ok", "verdict": None, "citations": None, "claims": None, "evidence": None, "source_docs": [], "meta": {}}`. — :34-37 [DERIVED]
- out: meta keeps ONLY the whitelisted keys (`mode, latent, corpus_ids, plan, verdict, reranker, rerank_degraded, lanes, timings, admission, answerability, trace_id, funnel, chat_plan, synthesis_version, model, phase_ms, used_evidence, legend, degraded, prompt, carry, composition, route, deep_research, generation, retrieval_trace, latent_selection, wildcard, trace_ms, synthesis, gap_check, product_search`). — :39-63 [DERIVED]
- `citations` = len of `citations` list; `source_docs` = sorted union of `source_document_ids` + `human_locators`, capped `[:32]`. — :64-74 [DERIVED]
- `evidence` = len of the FIRST present list among `("evidence", "hits", "selected_children", "child_dense_lane")` (break on first). — :78-86 [DERIVED]
- kind == "ask": evidence=len(objects), citations=len(cited_document_ids), copies `route/grounded/latency_ms` into meta, `status="abstained"` if `grounded is False` or objects list empty, verdict=str(route), then returns. — :87-102 [DERIVED]
- chat/ask abstention: answer startswith `"i don't have enough grounded evidence"` / `"i cannot answer"` / `"insufficient evidence"` (lowercased) or verdict contains `"insufficient"` -> `status="abstained"`. — :103-109 [DERIVED]

`knowledge_scope_of`
- reads `req.scope` only; returns None when absent or not `Mapping`/`RetrievalScope`; `parse_scope(raw).as_dict()` on success; `{"invalid": True}` on `ScopeError` (handler already refused with 422). — shared/polymath_shared/query_receipts.py:114-123 [DERIVED]

`record_query_receipt`
- `tx_factory` = polymath_shared.db.tx context manager yielding a connection. — shared/polymath_shared/query_receipts.py:185-186 [DERIVED]
- generates `qid = "q_" + uuid.uuid4().hex[:24]`; INSERT into `query_receipts` (query_id, kind, received_at=clock_timestamp(), client, corpus_ids, scope, mode, latent, question_sha256, question_head, wall_ms, status, verdict, citations, claims, evidence, source_docs, meta jsonb, error); returns qid. — :188,200-213,217 [DERIVED]
- question stored only as sha256 + `_head(question)` (200 chars), never full plaintext. — :27-29,210-211 [DERIVED]
- error path: status "error" with all-zero summary. — :190-192 [DERIVED]
- `knowledge_scope_of(req)` result, if not None, is attached as `meta.knowledge_scope`. — :193-195 [DERIVED]
- post-INSERT: if `principal_context.current()` set, separate `UPDATE query_receipts SET principal_id=%s WHERE query_id=%s` (migration 0066; `client` stays the SOFTWARE identity). — :214-216 [DERIVED]

`recent_queries` / `query_summary`
- filters: `received_at >= now() - make_interval(secs => since_h*3600.0)`, optional `principal_id = %s` (a principal sees only own receipts; no principal = legacy caller), `%s = ANY(corpus_ids)`, `kind = %s`. — shared/polymath_shared/query_receipts.py:235-244 [DERIVED]
- `recent_queries`: ORDER BY received_at DESC LIMIT (default 20). — :247-255 [DERIVED]
- `query_summary`: GROUP BY kind, `COALESCE(mode, '-')`; count, p50_ms/p95_ms (percentile_cont 0.5/0.95), max_ms, abstained (`status='abstained'`), errors (`status='error'`), avg_citations. — :259-273 [DERIVED]
- `_row`: `received_at` -> isoformat; `p50_ms`, `p95_ms`, `avg_citations` rounded to 1 decimal. — :224-232 [DERIVED]

## effect surface
- Postgres `query_receipts`: written (INSERT :200-213, UPDATE :216), read (:250-255, :263-272); FACTS tables_read/tables_written both `["query_receipts"]`. [DERIVED]
- SQL clocks: `clock_timestamp()` at :206, `now()` at :236. [DERIVED]
- Ambient context read: `principal_context.current()` at :214, :249, :262. [DERIVED]
- Imports: polymath_shared.principal_context, polymath_shared.code.scope, polymath_shared.funnel.compact (lazy, inside `_meta_json` :159-160). — :21-22 [DERIVED]
- No files, network, subprocess, env flags, or Qdrant access visible.

## invariants
INVARIANT: META_MAX_CHARS (64_000) > FUNNEL_MAX_CHARS (8_000) > 0 — shared/polymath_shared/query_receipts.py:126,131 [DERIVED]
  fails-if: funnel compaction alone could never bring an oversized meta back under budget.
INVARIANT: DROP_ORDER has 12 keys; SHRINK_LISTS_IN has 4 keys; every SHRINK_LISTS_IN key is also in DROP_ORDER — shared/polymath_shared/query_receipts.py:133-135 [DERIVED]
  fails-if: a trace key shrunk but not droppable could keep meta over budget forever.
INVARIANT: every SHRINK_LISTS_IN ∪ DROP_ORDER key ⊆ the summarize_response meta whitelist — :39-63 vs :133-135 [INFERRED — both lists name meta keys summarize_response keeps]
  fails-if: shrinking a key the whitelist never stores would be a no-op.
INVARIANT: len(source_docs) <= 32 (cap `[:32]` at all three assignment sites) — :74,85,95 [DERIVED]
  fails-if: receipt rows grow unbounded with citation/evidence counts.
INVARIANT: question_head <= 200 chars, client <= 120, error <= 500 — :27-29,207,213 [DERIVED]
  fails-if: oversized client strings or error text bloat the row.
INVARIANT: `_meta_json` never slices a JSON string; worst case returns `{"truncated": True, "keys": sorted(m)}` — :149-178 [DERIVED]
  fails-if: invalid JSON in the `meta` column makes the INSERT fail and the receipt is silently dropped (the old `json.dumps(meta)[:8000]` bug).
INVARIANT: when "funnel" is dropped, `("version", "counts", "lane_counts")` are kept — :172-174 [DERIVED]
  fails-if: forensics lose the funnel counts a forensic reads first (test_chat_funnel).
INVARIANT: Timer.__exit__ returns False -> exceptions propagate; `.ms` = elapsed*1000.0 — :280-282 [DERIVED]
  fails-if: Timer would silently swallow handler errors.
INVARIANT: since_h default is 24.0 in both readers; converted by * 3600.0 — :236-237,248,260 [DERIVED]
  fails-if: window semantics differ between the two read paths.

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid.uuid4 for qid :188; time.perf_counter in Timer :278,281; clock_timestamp() :206 and now() :236; Postgres reads/writes :200-216,250-272) — `summarize_response` (:32-110), `knowledge_scope_of` (:113-123), `_shrink_lists` (:138-146) and `_meta_json` (:149-178) are pure. [DERIVED]
idempotency: UNSAFE — each `record_query_receipt` call INSERTs a new row keyed by a fresh uuid qid (:188,200-213); no upsert / ON CONFLICT. Retrying a request duplicates receipts. [DERIVED]

## failure behaviour
- `record_query_receipt`: `except Exception` (:218) — SWALLOWED: `log.warning("query receipt not written: %s", ...)` with `extra={"error_code": "QUERY_RECEIPT_FAILED"}`, returns None (:219-221). Caller sees None; the query itself never fails. [DERIVED]
- `knowledge_scope_of`: `ScopeError` swallowed -> `{"invalid": True}` (:122-123); no exception escapes. [DERIVED]
- No error codes raised; only the `QUERY_RECEIPT_FAILED` log code is emitted. [DERIVED]

## dumb-code flags
- Dead branch: `if kind in ("chat", "ask")` at :105 — the `kind == "ask"` path already `return d` at :102, so `"ask"` is unreachable there. [INFERRED — ask returns at :102]
- Magic number 32 duplicated 3× as the source_docs cap with no named constant (:74,85,95). [DERIVED]
- Magic numbers: 200 (`_head` default :27), 120 (client :207), 500 (error :213), 24 (qid hex :188), 3600.0 (h→s :237). [DERIVED]
- Whitelist keys with no shrink/drop coverage: e.g. `deep_research`, `synthesis`, `gap_check`, `product_search`, `generation` appear in the meta whitelist (:39-63) but in neither SHRINK_LISTS_IN nor DROP_ORDER (:133-135); if they alone exceed META_MAX_CHARS the whole meta collapses to `{"truncated": True, "keys": ...}` (:178). [INFERRED — from the two key lists]
- `mode` normalization split across layers: `str(mode).upper()` on write (:209) vs `COALESCE(mode, '-')` on read (:264). [DERIVED]
- `_head(client or "", 120) or None` / `_head(error or "", 500) or None`: empty string coerced to None (:207,213). [DERIVED]

## refactor notes
- 7 orchestrator api modules import this module (FACTS.importers); changing any public signature (`record_query_receipt`, `recent_queries`, `query_summary`, `summarize_response`, `Timer`) has that blast radius. — shared/polymath_shared/query_receipts.py FACTS importers [DERIVED]
- INSERT column list (:203-205) must match migration 0047's `query_receipts` schema; `principal_id` is added post-insert via UPDATE (migration 0066, :214-216). Schema changes need a migration plus this edit. [DERIVED]
- The meta whitelist tuple (:39-63) is the single gate for what a receipt can carry: adding a tracked meta key requires editing it, and large keys also need SHRINK_LISTS_IN/DROP_ORDER entries or they can force total truncation (:133-135,178). [DERIVED]
- `_where`'s principal filter (:238-239) changes read visibility: with a principal set, `recent_queries`/`query_summary` return only that principal's rows; removing it widens history for every caller. [DERIVED]
- `Timer` measures milliseconds (:281) and is what callers pass as `wall_ms`; the INSERT rounds to int ms (:211). [DERIVED]
- Docstring cites the live shrink order as of 2026-09-27 (RECEIPT-SHRINK-ORDER); reordering DROP_ORDER silently changes what forensics see first. — :127-130 [DERIVED]

## VERIFY
```verify
grep -Fq 'META_MAX_CHARS = 64_000' shared/polymath_shared/query_receipts.py
grep -Fq 'qid = "q_" + uuid.uuid4().hex[:24]' shared/polymath_shared/query_receipts.py
grep -Fq 'QUERY_RECEIPT_FAILED' shared/polymath_shared/query_receipts.py
grep -Fq '"truncated": "ids_dropped"' shared/polymath_shared/query_receipts.py
grep -Eq 'if kind in \("chat", "ask"\)' shared/polymath_shared/query_receipts.py
test "$(grep -c -F '[:32]' shared/polymath_shared/query_receipts.py)" -ge 3
! grep -Fq 'return True' shared/polymath_shared/query_receipts.py
```
