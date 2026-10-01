# unit: shared/polymath_shared/query_receipts.py
anchor: shared/polymath_shared/query_receipts.py:1-277

## purpose
QUERY-RECEIPTS-V1: one durable row per served query in `query_receipts` (migration 0047). Every `/chat`, `/ask` and `/retrieve` writes ONE row after the response is composed — best effort, its own short transaction, never on the request's critical path, failures logged and swallowed. shared/polymath_shared/query_receipts.py:1-10 [DERIVED]
Read back by the MCP tool `recent_queries`, `GET /queries` and `scripts/query_log.py`. shared/polymath_shared/query_receipts.py:9 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `summarize_response` | def | (kind: str, out: Any) -> dict | shared/polymath_shared/query_receipts.py:32-107 | — |
| `knowledge_scope_of` | def | (req: Any) -> dict \| None | shared/polymath_shared/query_receipts.py:110-120 | — |
| `record_query_receipt` | def | (tx_factory, *, kind, question, req, scope_corpora, scope_kind, wall_ms, out=None, error=None, client=None) -> str \| None | shared/polymath_shared/query_receipts.py:176-216 | — |
| `recent_queries` | def | (conn, *, corpus_id=None, kind=None, limit=20, since_h=24.0) -> list[dict] | shared/polymath_shared/query_receipts.py:242-251 | — |
| `query_summary` | def | (conn, *, corpus_id=None, kind=None, since_h=24.0) -> list[dict] | shared/polymath_shared/query_receipts.py:254-268 | — |
| `Timer` | class | `__enter__` -> self (sets `t0`); `__exit__` -> False (sets `ms`) | shared/polymath_shared/query_receipts.py:271-277 | — |

Module-level importers (FACTS.importers, symbol-level attribution unknown): `orchestrator/orchestrator/api/_small-modules`, `ask.py`, `chat.py`, `deep_research.py`, `retrieve.py`, `ui.py`.
Private helpers: `_head` :27-29, `_shrink_lists` :135-143, `_meta_json` :146-173, `_row` :219-227, `_where` :230-239.

## contracts

**summarize_response(kind, out) — pure, no I/O** shared/polymath_shared/query_receipts.py:33 [DERIVED]
- in: any handler response `out`; non-dict returns the default `{"status": "ok", "verdict": None, "citations": None, "claims": None, "evidence": None, "source_docs": [], "meta": {}}`. :34-37 [DERIVED]
- post: `meta` keeps only the allowlisted keys (`mode` … `gap_check`, incl. `funnel`, `chat_plan`, `route`, `deep_research`, `generation`, `retrieval_trace`, `wildcard`, `synthesis`, `gap_check`). :39-60 [DERIVED]
- post: `citations` = length of the citations list; `source_docs` = sorted union of `source_document_ids` + `human_locators`, capped `[:32]`. :62-71 [DERIVED]
- post: `evidence` = length of the first list-valued key among `("evidence", "hits", "selected_children", "child_dense_lane")`; fallback `source_docs` from `source_name`/`doc_id`/`document_id`. :75-83 [DERIVED]
- post (`kind == "ask"`): `evidence` = len(objects), `citations`/`source_docs` from `cited_document_ids`; `route`/`grounded`/`latency_ms` copied into meta; `status = "abstained"` if `grounded is False` or objects list is empty; `verdict` = route. :84-99 [DERIVED]
- post (other kinds): `status = "abstained"` when the answer text starts with `"i don't have enough grounded evidence"`, `"i cannot answer"`, `"insufficient evidence"`, or verdict contains `"insufficient"`. :102-106 [DERIVED]

**knowledge_scope_of(req) — pure**
- pre: reads only `req.scope`; a response can never set or widen it. :111-114 [DERIVED]
- out: `None` when absent/not `Mapping`/`RetrievalScope`; `parse_scope(raw).as_dict()` on success; `{"invalid": True}` on `ScopeError` (the 422 case). :114-120 [DERIVED]

**record_query_receipt(tx_factory, ...)**
- pre: `tx_factory` is `polymath_shared.db.tx`, a context manager yielding a connection. :180-182 [DERIVED]
- out: fresh `qid = "q_" + uuid.uuid4().hex[:24]`, or `None` on any failure. :183, 212, 216 [DERIVED]
- effect: single INSERT into `query_receipts` (query_id, kind, received_at=`clock_timestamp()`, client, corpus_ids, scope, mode, latent, question_sha256, question_head, wall_ms, status, verdict, citations, claims, evidence, source_docs, meta `%s::jsonb`, error); then `UPDATE ... SET principal_id` when `principal_context.current()` is set (migration 0066; `client` stays the SOFTWARE identity). :195-211 [DERIVED]
- post: question text never stored — only sha256 hexdigest + `_head(question)` (200 chars). :205-206 [DERIVED]
- post: `wall_ms` stored as `int(round(wall_ms))`. :206 [DERIVED]

**recent_queries / query_summary**
- pre: both filter by `principal_context.current()` via `_where`; no principal = legacy caller sees all rows. :230-239, 244, 257 [DERIVED]
- out (query_summary): per `(kind, COALESCE(mode,'-'))`: count, p50/p95/max wall_ms, abstained count, error count, avg citations. :256-267 [DERIVED]

**_meta_json(meta) — structural shrink, never slices JSON text**
- order over `META_MAX_CHARS = 64_000`: (1) compact `funnel` to `FUNNEL_MAX_CHARS = 8_000`; (2) `_shrink_lists` on `SHRINK_LISTS_IN` keys; (3) replace whole keys with `{"truncated": True}` in `DROP_ORDER`; (4) terminal `{"truncated": True, "keys": sorted(m)}`. :123-132, 146-173 [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| Postgres write | `INSERT INTO query_receipts` (18 columns, `::jsonb` meta) | shared/polymath_shared/query_receipts.py:196-208 |
| Postgres write | `UPDATE query_receipts SET principal_id=%s WHERE query_id=%s` | shared/polymath_shared/query_receipts.py:209-211 |
| Postgres read | `recent_queries` SELECT, `ORDER BY received_at DESC LIMIT %s` | shared/polymath_shared/query_receipts.py:245-250 |
| Postgres read | `query_summary` SELECT with `percentile_cont` / `FILTER` aggregates | shared/polymath_shared/query_receipts.py:258-267 |
| Lazy import | `from polymath_shared.funnel import compact` on the over-budget path only | shared/polymath_shared/query_receipts.py:155-157 |
| Qdrant / files / network / subprocess / env flags | none in SOURCE | — |

## invariants
INVARIANT: len(source_docs) ≤ 32 (slice `[:32]`) — shared/polymath_shared/query_receipts.py:71,82,92 [DERIVED]
  fails-if: receipt rows exceed the documented cap; consumers assuming ≤32 doc ids mis-handle rows.
INVARIANT: successful `_meta_json` output length ≤ META_MAX_CHARS (64_000) unless it is the terminal `{"truncated": True, "keys": ...}` dump — shared/polymath_shared/query_receipts.py:152-173 [DERIVED]
  fails-if: oversized meta re-triggers the historical INSERT-failure path (invalid JSON from slicing, :147-149).
INVARIANT: every shrunk long list keeps exactly LIST_MAX_ITEMS = 8 head items plus `{"truncated": True, "held": len(obj)}` — shared/polymath_shared/query_receipts.py:129,137-139 [DERIVED]
  fails-if: truncation marker lost — consumers cannot tell a full list from a cut one.
INVARIANT: DROP_ORDER terminates with the forensic core `"legend", "used_evidence", "chat_plan"` (dropped last) — shared/polymath_shared/query_receipts.py:124-132 [DERIVED]
  fails-if: reordering drops the fields a forensic reads first, repeating the 2026-09-27 wildcard-turn loss (:124-126).
INVARIANT: raw question text is never persisted — only `question_sha256` + `question_head` (default 200 chars) — shared/polymath_shared/query_receipts.py:205-206 [DERIVED]
  fails-if: privacy property of the receipt store broken.
INVARIANT: `record_query_receipt` either returns a qid or None — never raises to the caller — shared/polymath_shared/query_receipts.py:184-216 [DERIVED]
  fails-if: a receipt failure turns into a request failure, violating the module charter (:7-8).
INVARIANT: `kind == "ask"` returns at :99, so `"ask"` in the `kind in ("chat", "ask")` test at :102 is unreachable — shared/polymath_shared/query_receipts.py:99,102 [INFERRED] (control flow: the ask branch returns first)
  fails-if: none today; a dead tuple member invites wrong assumptions about which kinds reach the abstention check.

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid: `uuid.uuid4().hex[:24]` for query_id shared/polymath_shared/query_receipts.py:183; clock: `time.perf_counter` in Timer shared/polymath_shared/query_receipts.py:273,276; db: `clock_timestamp()` in the INSERT shared/polymath_shared/query_receipts.py:201 and `now()`-relative reads :231)
idempotency: UNSAFE (each call INSERTs a new row under a fresh uuid; replaying a request writes a second receipt — shared/polymath_shared/query_receipts.py:183,196-208 [DERIVED])

## failure behaviour
- `except Exception` around the whole of `record_query_receipt`: swallowed — `log.warning("query receipt not written: %s", ...)` with `extra={"error_code": "QUERY_RECEIPT_FAILED"}`, returns `None`; caller sees only a missing qid. shared/polymath_shared/query_receipts.py:213-216 [DERIVED]
- `ScopeError` in `knowledge_scope_of` is converted, not swallowed: `{"invalid": True}` (the refused-422 case). shared/polymath_shared/query_receipts.py:119-120 [DERIVED]
- No error codes raised; the module never breaks a query. shared/polymath_shared/query_receipts.py:180-182, 213 [DERIVED]

## dumb-code flags
- Magic numbers: `64_000` :123, `8_000` :128, `8` :129, `[:32]` :71/82/92, `[:24]` :183, `120` (client head) :202, `500` (error head) :208, default `200` in `_head` :27. [DERIVED]
- Operator-precedence-dependent abstention test: `A and B or C and D` at :103-104 — correct only because `and` binds tighter than `or`. [DERIVED]
- Dead tuple member: `"ask"` in `("chat", "ask")` at :102 is unreachable (ask returned at :99). :99,102 [INFERRED]
- Key-name duplication: the meta allowlist (:40-60) repeats every `SHRINK_LISTS_IN`/`DROP_ORDER` key (`funnel`, `prompt`, `carry`, `latent`, `latent_selection`, `retrieval_trace`, `wildcard`, `lanes`, `timings`, `legend`, `used_evidence`, `chat_plan`) — two lists must stay in sync by hand. :40-60,130-132 [DERIVED]
- Migration numbers live only in comments/strings: `0047` :6, `0066` :210. [DERIVED]

## refactor notes
- Blast radius: renaming/changing signatures of the public six ripples into `orchestrator/orchestrator/api/_small-modules`, `ask.py`, `chat.py`, `deep_research.py`, `retrieve.py`, `ui.py` (FACTS.importers).
- The INSERT column list (:197-201) must stay in lockstep with the `query_receipts` schema from migration 0047 plus the 0066 `principal_id` UPDATE (:209-211).
- `DROP_ORDER` is a live forensic contract (RECEIPT-SHRINK-ORDER, :124-127): reordering changes what evidence survives an over-budget receipt.
- Any key added to `SHRINK_LISTS_IN`/`DROP_ORDER` that is not in the meta allowlist (:40-60) is dead weight — it can never appear in meta.
- `client` vs `principal_id` semantics (software identity vs principal, :210-211) must not be merged without checking `_where`'s principal filter (:233-234).
- `knowledge_scope_of` duck-types `req.scope` via `getattr` + isinstance (:114-115); request models with an unrelated `scope` field are tolerated by design.

## VERIFY
```verify
grep -Fq 'META_MAX_CHARS = 64_000' shared/polymath_shared/query_receipts.py
grep -Fq 'qid = "q_" + uuid.uuid4().hex[:24]' shared/polymath_shared/query_receipts.py
grep -Fq 'INSERT INTO query_receipts' shared/polymath_shared/query_receipts.py
grep -Fq 'QUERY_RECEIPT_FAILED' shared/polymath_shared/query_receipts.py
grep -Fq 'if kind in ("chat", "ask"):' shared/polymath_shared/query_receipts.py
grep -Fq 'since_h: float = 24.0' shared/polymath_shared/query_receipts.py
test "$(grep -c -F 'time.perf_counter' shared/polymath_shared/query_receipts.py)" -ge 2
! grep -Fq 'import requests' shared/polymath_shared/query_receipts.py
```
