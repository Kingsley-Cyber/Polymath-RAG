# unit: orchestrator/orchestrator/api/ask.py
anchor: orchestrator/orchestrator/api/ask.py:1-391

## purpose
Production `/ask` route: knowledge-type-aware question answering over stored Polymath objects. QUERY-ROUTER-V1 classifies intent (FACT / PROCEDURE / CONCEPT / POLYMATH) and the route assembles answers purely from persisted rows — "Nothing is generated; the response assembles" — orchestrator/orchestrator/api/ask.py:1-17. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ask` | def (route handler) | `(req: AskRequest, request: Request) -> dict` | orchestrator/orchestrator/api/ask.py:368-390 | POST /ask; module imported by `orchestrator/orchestrator/api/ui.py`, `orchestrator/orchestrator/main.py` (FACTS.importers) [INFERRED: importers are module-level] |
| `AskRequest` | class (pydantic BaseModel) | fields: `question: str`, `corpus_id`, `corpus_ids`, `workspace` (Optional), `all_authorized: bool = False`, `scope: Optional[dict] = None` | orchestrator/orchestrator/api/ask.py:43-50 | — |
| `router` | module var (APIRouter) | mounts POST /ask | orchestrator/orchestrator/api/ask.py:40, 367 | same importers as above |

All lane helpers (`_procedures`, `_concepts`, `_facts`, `_concept_graph`, `_vector_object_ranks`, `_ask_impl`, `_terms`, `_norm`, `_match_score`, `_merge_terms`) are underscore-private — orchestrator/orchestrator/api/ask.py:53-299. [DERIVED]

## contracts

**`ask` (route wrapper)** — orchestrator/orchestrator/api/ask.py:368-390
- in: `AskRequest` + FastAPI `Request`; derives `scope_kind` from which of `corpus_id`/`corpus_ids`/`workspace`/`all_authorized` is set — orchestrator/orchestrator/api/ask.py:372-374. [DERIVED]
- post: records exactly one query receipt via `record_query_receipt(tx, kind="ask", ...)` on success — orchestrator/orchestrator/api/ask.py:387-389 — and one with `error=...` before re-raising on failure — orchestrator/orchestrator/api/ask.py:379-386. [DERIVED]
- out: `echo_scope(out, req.scope)` (K1b scope confirmation) — orchestrator/orchestrator/api/ask.py:390. [DERIVED]

**`_ask_impl`** — orchestrator/orchestrator/api/ask.py:299-364
- pre: `question` non-empty else `HTTPException(422, "question required")` — orchestrator/orchestrator/api/ask.py:301-303. [DERIVED]
- pre: scope resolved fail-closed via `_role_scope_or_422(req)` + `resolve_http_scope(conn, req)` from `orchestrator.api.retrieve` (shared with /retrieve, /evidence, /chat) — orchestrator/orchestrator/api/ask.py:306-312. [DERIVED]
- in: `classify_query(question)` picks one of `ROUTE_FACT`/`ROUTE_PROCEDURE`/`ROUTE_CONCEPT`/`ROUTE_POLYMATH`; only the routed lane is populated, except POLYMATH fills concepts[:6] + facts[:6] + related_concepts — orchestrator/orchestrator/api/ask.py:314-336. [DERIVED]
- in: CORPUS-MAP-PLANNING-V1 expansion terms from `plan_with_corpus_map(conn, scope, question)` merged into every lane — orchestrator/orchestrator/api/ask.py:320-323, 82-91. [DERIVED]
- out: dict keys `question, router, route, objects{procedures,concepts,facts,related_concepts}, cited_document_ids, grounded, scope, map, latency_ms, contracts` — orchestrator/orchestrator/api/ask.py:349-364. [DERIVED]
- post: `grounded` is true iff every served object has `document_id` or `source_chunk_ids` or `evidence_chunk_ids` — orchestrator/orchestrator/api/ask.py:345-348. [DERIVED]

**`_vector_object_ranks`** — orchestrator/orchestrator/api/ask.py:95-147
- in: `kind` is `"routing_procedure"` or `"routing_concept"`; dense probe `(qvec, None)` plus sparse BM25 probe when `si` non-empty — orchestrator/orchestrator/api/ask.py:124-127, 159, 208. [DERIVED]
- out: `{object_id: rank}` with 0 = best; `limit=8` per probe per corpus collection, payload key `summary_id` — orchestrator/orchestrator/api/ask.py:99, 130-141, 144-145. [DERIVED]
- post: returns `{}` on any failure (fail-open to term matching) — orchestrator/orchestrator/api/ask.py:146-147, 99-100. [DERIVED]

**Lane queries**
- `_procedures`: SELECT from `procedure_artifacts` WHERE `corpus_id = ANY(%s)`; inadmissible titles replaced by `f"Procedure ({len(steps_l)} steps)"`; score = `round(match, 4)` (confidence deliberately not used) — orchestrator/orchestrator/api/ask.py:153-176. [DERIVED]
- `_concepts`: SELECT from `concept_artifacts`, same where-clause; rows with inadmissible names skipped entirely — orchestrator/orchestrator/api/ask.py:202-212. [DERIVED]
- `_facts`: joins `facts`+`entities`×2+`evidence`+`documents`, `WHERE f.decision='ACCEPT' AND d.corpus_id = ANY(%s)` plus ILIKE ANY on subject/predicate/object — orchestrator/orchestrator/api/ask.py:246-258. [DERIVED]
- `_concept_graph`: SELECT `canonical_name, definition` from `concept_families`, matches by normalized name/word overlap — orchestrator/orchestrator/api/ask.py:282-291. [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `procedure_artifacts`, `concept_artifacts`, `facts`, `entities`, `evidence`, `documents`, `concept_families` | orchestrator/orchestrator/api/ask.py:157, 207, 246-254, 283; FACTS.tables_read |
| Postgres write | none (FACTS.tables_written = []) — except the receipt helper call | FACTS |
| receipt write | `record_query_receipt(tx, ...)` per request, best-effort | orchestrator/orchestrator/api/ask.py:381-385, 387-389 |
| Qdrant | `QdrantClient(url=get_settings().stores.qdrant_url, timeout=20)`; `query_points` over `_corpus_collections(list(scope.corpus_ids))` | orchestrator/orchestrator/api/ask.py:113, 115-116, 130-133 |
| clock | `time.perf_counter` ×3 → `latency_ms` | orchestrator/orchestrator/api/ask.py:300, 358, 383 |
| env/settings | `get_settings().stores.qdrant_url` (default set in polymath_shared) | orchestrator/orchestrator/api/ask.py:113 |

## invariants

```
INVARIANT: len(procedures) <= 5 — orchestrator/orchestrator/api/ask.py:193 [DERIVED]
  fails-if: response shape/paging assumptions of /ask consumers break
INVARIANT: len(concepts) <= 8 (<= 6 on POLYMATH route) — orchestrator/orchestrator/api/ask.py:233, 333 [DERIVED]
  fails-if: POLYMATH responses exceed the documented 6-concept lane
INVARIANT: len(facts) <= 8 and every served fact has score > 0 — orchestrator/orchestrator/api/ask.py:272-273 [DERIVED]
  fails-if: zero-match facts pollute the answer lane
INVARIANT: len(related_concepts) <= 6 — orchestrator/orchestrator/api/ask.py:294 [DERIVED]
  fails-if: unbounded concept-graph bloat in POLYMATH answers
INVARIANT: every served fact has f.decision='ACCEPT' — orchestrator/orchestrator/api/ask.py:243 [DERIVED]
  fails-if: unreviewed/rejected facts leak into answers
INVARIANT: vector-ranked objects (rank 0..7, enumerate at 144-145) always outrank term-only matches (sentinel _vrank=999) — orchestrator/orchestrator/api/ask.py:180, 193, 222, 233 [DERIVED]
  fails-if: ordering contract flips; term substring beats semantic rank
INVARIANT: facts fetch capped at LIMIT 2000 — orchestrator/orchestrator/api/ask.py:259 [DERIVED]
  fails-if: unbounded SQL result on broad terms
INVARIANT: concepts with inadmissible names are never served — orchestrator/orchestrator/api/ask.py:211-212 [DERIVED]
  fails-if: GLiNER-era junk names (audit F12) reach clients
```

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` → `latency_ms` — orchestrator/orchestrator/api/ask.py:300, 358, 383; network Qdrant scores — orchestrator/orchestrator/api/ask.py:113, 130; db reads). Ranking itself uses fixed weights with ties broken by `object_id` — orchestrator/orchestrator/api/ask.py:16, 193, 233, 273. [DERIVED]
idempotency: UNSAFE (each call appends one durable query receipt — orchestrator/orchestrator/api/ask.py:381-389; answer assembly itself writes no tables, FACTS.tables_written = []).

## failure behaviour
- `_vector_object_ranks` outer `except Exception: return {}` — swallowed; caller silently falls back to term-match ranking (fail-open) — orchestrator/orchestrator/api/ask.py:146-147, 99-100. [DERIVED]
- `_vector_object_ranks` per-probe `except Exception: continue` — a failed corpus/probe yields no vector candidates from it, silently — orchestrator/orchestrator/api/ask.py:134-135. [DERIVED]
- `ask` wrapper `except Exception as exc` — records receipt with `error=f"{type(exc).__name__}: ..."` then `raise` unchanged; caller sees the original error — orchestrator/orchestrator/api/ask.py:379-386. [DERIVED]
- `HTTPException(422, "question required")` for blank question — orchestrator/orchestrator/api/ask.py:303. [DERIVED]
- Malformed knowledge-role scope refused with typed 422 via `_role_scope_or_422` — orchestrator/orchestrator/api/ask.py:49-50, 310. [DERIVED]

## dumb-code flags
- Sentinel `999` for "no vector rank", duplicated in `_procedures` and `_concepts` — orchestrator/orchestrator/api/ask.py:180, 222. [DERIVED]
- Hardcoded stop-word set and punctuation strip set `".,!?;:\"'()[]{}"` — orchestrator/orchestrator/api/ask.py:58-60, 66. [DERIVED]
- Magic caps: `LIMIT 2000`, `limit=8`, `timeout=20`, `[:200]` — orchestrator/orchestrator/api/ask.py:259, 132, 113, 293. [DERIVED]
- `_procedures`/`_concepts` are near-duplicate scoring+sort blocks — orchestrator/orchestrator/api/ask.py:150-196 vs 199-236. [DERIVED]
- Dead-in-effect fields: concept confidence is a hardcoded `0.9` constant; old procedure confidence was `min(1.0, 0.6 + 0.05 * len(steps))` (a length function) — both removed from scoring — orchestrator/orchestrator/api/ask.py:170-176, 214-218. [DERIVED]
- Repeated lazy imports inside loops/functions: `scope_or_all` re-imported per corpus iteration — orchestrator/orchestrator/api/ask.py:117. [DERIVED]

## refactor notes
- Route path `"/ask"` and response keys (`objects` lanes, `cited_document_ids`, `grounded`, `scope`, `map`, `contracts`) are consumed by `ui.py` and `main.py` (FACTS.importers) — orchestrator/orchestrator/api/ask.py:367, 349-364. [DERIVED]
- Scope resolution is the single canonical path shared with `/retrieve`, `/evidence`, `/chat`; do not fork it — orchestrator/orchestrator/api/ask.py:306-312. [DERIVED]
- Private cross-module borrow: `from orchestrator.api.fast import _corpus_collections, _embed_query` — renaming those in `fast.py` breaks this file — orchestrator/orchestrator/api/ask.py:108. [DERIVED]
- Sort keys and lane caps (5/8/6, sentinel 999) are observable in API output — orchestrator/orchestrator/api/ask.py:180, 193, 222, 233, 273, 294. [DERIVED]
- `echo_scope(out, req.scope)` at the return is the K1b scope-confirmation contract — orchestrator/orchestrator/api/ask.py:390. [DERIVED]
- Receipt call shape (`kind="ask"`, `scope_corpora`, `scope_kind`, `wall_ms`, `error`/`out`, `client`) is coupled to `polymath_shared.query_receipts` — orchestrator/orchestrator/api/ask.py:381-389. [DERIVED]

## VERIFY
```verify
grep -Fq 'class AskRequest(BaseModel):' orchestrator/orchestrator/api/ask.py
grep -Fq '@router.post("/ask")' orchestrator/orchestrator/api/ask.py
grep -Fq 'raise HTTPException(422, "question required")' orchestrator/orchestrator/api/ask.py
grep -Eq 'routing_(concept|procedure)' orchestrator/orchestrator/api/ask.py
grep -Fq 'LIMIT 2000' orchestrator/orchestrator/api/ask.py
test "$(grep -c -F 'vrank if vrank is not None else 999' orchestrator/orchestrator/api/ask.py)" -ge 2
grep -Fq 'return echo_scope(out, req.scope)' orchestrator/orchestrator/api/ask.py
```
