# unit: orchestrator/orchestrator/api/fast.py
anchor: orchestrator/orchestrator/api/fast.py:1-712

## purpose
R1C FAST production route: orchestrator-owned HTTP reads for retrieval. Production FAST runs the qualified Pass-1 engine (`pass1-retrieval-v1`) from `polymath_shared.pass1` over the neural routing projection; this file holds only thin client adapters (Qdrant, embedder, Postgres lookups) — no hash-embed fallback, an incomplete projection is a loud typed 502. — fast.py:3-14 [DERIVED]

Importers of this module: `orchestrator/orchestrator/api/{_small-modules, ask.py, chat_retrieval.py, evidence.py, graph.py, hybrid.py, retrieve.py, ui.py}` — FACTS.importers [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `FastSearcher` | class | `(client: QdrantClient, collections: dict[str,str], query: str \| None = None, scope=None)` -> callable searcher | 48-209 | `fast_retrieve` (581); pass1 engine via `routing_search` (583-584) [DERIVED] |
| `entity_card_probe` | def | `(client, collections, corpus_id: str, query: str, qvec: list[float], limit: int = 8, scope=None) -> list[dict]` | 212-259 | FAST advisory lane; GRAPH seed resolution (F1) per docstring (217); graph.py [INFERRED: docstring names GRAPH] |
| `fast_retrieve` | def | `(query: str, corpus_id, plan: Optional[Pass1RetrievalPlan] = None, scope=None) -> dict` | 542-712 | importers listed above, symbol-level unverified [DERIVED module list] |
| `note_sparse_fallback` | def | `(reason: str) -> None` | 397-401 | hybrid.py child lexical lane [INFERRED: R2 comment names the v1 HYBRID lane, 381-384] |
| `degradations` | def | `() -> list[dict]` | 404-423 | meta builders (fast_retrieve:639); importers [DERIVED] |
| `_begin_retrieval` | def | `() -> None` | 391-394 | `fast_retrieve` (559); sibling retrieve routes [INFERRED: resets shared ContextVars] |
| `_embed_queries` | def | `(texts: list[str]) -> list[list[float]]` | 329-347 | no in-file caller; chat route per docstring P1.b/P1.d (330-331) [INFERRED] |
| `_embed_query` | def | `(query: str) -> list[float]` | 350-364 | `fast_retrieve` (597, 611); pass1 engine callback [DERIVED] |
| `_presentation_joins` | def | `(chunk_ids: list[str], doc_ids: list[str]) -> dict` | 504-539 | `fast_retrieve` (625); importers [DERIVED] |

## contracts

**`fast_retrieve`** (542-712)
- in: `corpus_id` is one corpus id or a list of them (MULTI-CORPUS-FAST-V1, audit F8) — 551-552, 561-562 [DERIVED]; `plan` defaults to `mode_plan(MODE_FAST)` — 560 [DERIVED]
- pre: `corpus_ids` non-empty else HTTP 422 `corpus_required` — 563-567 [DERIVED]; each corpus passes `_ensure_fast_ready`: ≥1 run with `status = 'query_ready'` (502 `corpus_not_ready` otherwise) — 273-281 [DERIVED]; routing collection exists and count > 0 (502 `routing_projection_not_ready`) — 284-295 [DERIVED]
- pre: readiness fails closed — one unready corpus fails the whole query rather than narrowing scope — 554-556 [DERIVED]
- out: dict keys `query, meta, entity_card_lane, selected_documents, selected_sections, evidence, trace` — 628-712 [DERIVED]; `meta` keys: `mode, plan_version, corpus_id, corpus_ids, rrf_k, selected_document_count, selected_section_count, evidence_count, degraded, liveness, entity_card_votes` — 630-646 [DERIVED]; `trace` keys: `lane_sizes, pre_g3_order, post_g3_order, funnel_lanes, funnel_union, plan, latency_ms` — 703-711 [DERIVED]
- post: `meta.corpus_id` = `corpus_ids[0]` when exactly one corpus, else `None` — 633 [DERIVED]

**`FastSearcher`** (48-209)
- pre: `_filter_for` is the ONE chokepoint applying `representation_kind`, `corpus_id`, `doc_id`, `parent_id`, `exclude_doc_ids`, hidden `chunk_contract_version` generations, and scope must/must_not — shared by dense and sparse lanes — 91-123 [DERIVED]
- out: `__call__` returns up to `limit=50` payload/score dicts sorted by `-score` — 168-169, 209 [DERIVED]
- post: hidden blue/green generations excluded via `must_not` on `chunk_contract_version`; legacy points without the field pass — 111-115 [DERIVED]

**`entity_card_probe`** (212-259)
- in: dense + sparse probes per collection, filter = `representation_kind="routing_entity"` + `corpus_id` + scope — 226-230 [DERIVED]
- out: `[{card_id, entity_id, doc_ids, text, score, lane}]` best-first, deduped by card keeping max score, cut to `limit` — 215-218, 246-259 [DERIVED]

**`_embed_query` / `_embed_queries`** (329-364)
- pre: `_await_embedder` blocks up to `EMBED_WAKE_BUDGET_S` polling every 2.0 s — 322-326 [DERIVED]
- out: vectors via `client.embed(..., "query")` — 340, 357 [DERIVED]
- post: any exception → HTTP 502 `embedder_unavailable` with exception type name — 341-345, 358-362 [DERIVED]

**degradation trio** `_begin_retrieval` / `note_sparse_fallback` / `degradations` (379-423)
- per-request ContextVar state (`_RERANK_DEGRADED`, `_SPARSE_FALLBACK`), reset by `_begin_retrieval`, emitted as `{component, effect, reason}` entries — 379-394, 406-422 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `runs`: `COUNT(*) WHERE corpus_id = %s AND status = 'query_ready'` | 273-275 [DERIVED] |
| Postgres read | `chunks` + `documents` neighbor expansion (CTE `seeds`, `unnest(doc_ids, chunk_ids)`, `tier = 'child'`, `chunk_index ± distance`) | 438-455 [DERIVED] |
| Postgres read | `chunks.region_role` for bounded candidate set | 486-489 [DERIVED] |
| Postgres read | `documents.source_name`, `chunks.heading_path` presentation joins | 515-523 [DERIVED] |
| Postgres write | none — FACTS.tables_written empty | FACTS [DERIVED] |
| Qdrant | collections named `qdrant_collection_name(corpus_id, NEURAL_EMBED_CONTRACT.contract_id)` | 262-266 [DERIVED] |
| Qdrant | dense `query_points` (limit 50), sparse BM25 `query_points` via `SPARSE_VECTOR_NAME`, companion sparse probe appended to dense results | 137-144, 155-161, 177-199, 209 [DERIVED] |
| Qdrant | `collection_exists` + `count` readiness probe | 285-290 [DERIVED] |
| network | embedder sidecar via `EmbedderClient` (`priority="interactive"` in `_embed_queries`); Qdrant client at `get_settings().stores.qdrant_url`, `timeout=60` | 282, 332-340, 574 [DERIVED] |
| env | `POLYMATH_EMBED_WAKE_BUDGET_S` = `'150'` (seconds, float) | 313-314 [DERIVED] |

FACTS.tables_read also lists `seeds` and `unnest` — both are the CTE name and set-function inside `_neighbor_lookup`'s SQL, not base tables — 440-444 [DERIVED].

## invariants

INVARIANT: `EMBED_WAKE_BUDGET_S` == `float(os.environ.get("POLYMATH_EMBED_WAKE_BUDGET_S", "150"))` — 313-314 [DERIVED]
  fails-if: budget below the ~20 s measured cold start (306) yields typed `embedder_unavailable` instead of a successful wait.
INVARIANT: `_await_embedder` poll interval == 2.0 s — 324 [DERIVED]
  fails-if: tighter polling hammers a waking sidecar; looser wastes budget.
INVARIANT: `FastSearcher.__call__` dense limit == 50 — 209 [DERIVED]
  fails-if: lowering truncates lane candidates before RRF fusion.
INVARIANT: `entity_card_probe` limit default == 8 — 214 [DERIVED]
INVARIANT: `COUNT(runs WHERE corpus_id AND status='query_ready')` >= 1 per corpus — 273-281 [DERIVED]
  fails-if: 502 `corpus_not_ready`.
INVARIANT: Qdrant collection point count > 0 per corpus — 290-295 [DERIVED]
  fails-if: 502 `routing_projection_not_ready`.
INVARIANT: `len(corpus_ids)` >= 1 — 563-567 [DERIVED]
  fails-if: 422 `corpus_required`.
INVARIANT: dense and sparse lanes use the identical `_filter_for` must/must_not — 134, 152 [DERIVED]
  fails-if: divergent filters leak another corpus or a rebuilding generation into a lane.
INVARIANT: rerank degradation preserves the candidate set — effect string `"same candidate set, same recall"` — 410-413, 493-501 [DERIVED]
  fails-if: a degraded reranker that also dropped candidates would silently reduce recall.
INVARIANT: `meta.corpus_id` is `corpus_ids[0]` iff `len(corpus_ids) == 1`, else `None` — 633 [DERIVED]
  fails-if: multi-corpus responses reporting a misleading single corpus_id.

## determinism & idempotency
determinism: NONDETERMINISTIC — clocks `time.time` at 135, 146, 153, 167, 178, 202 and `time.monotonic` at 322-323 (all latency/wake timing) — FACTS.nondeterminism [DERIVED]; network (embedder, Qdrant) and db (Postgres) calls throughout; concurrency via `threading.Lock` guarding per-kind latency sums shared across chat-route lanes — 59-61, 73-75 [DERIVED]. Output ordering is stabilized by explicit sorts (`-score` at 148, 169; `ORDER BY n.doc_id, n.chunk_index` at 454) — [DERIVED].
idempotency: SAFE — read-only against Postgres and Qdrant (no tables written, only searches/counts); sole mutation is the in-object `_hidden_cache` — 80-89, FACTS.tables_written [DERIVED].

## failure behaviour

Typed HTTP errors via `_fail` (default `status_code=502`) — 44-45 [DERIVED]:

| error_code | status | trigger | anchor |
|---|---|---|---|
| `corpus_required` | 422 | empty corpus scope | 564-567 [DERIVED] |
| `corpus_not_ready` | 502 | no `query_ready` run | 278-281 [DERIVED] |
| `routing_projection_not_ready` | 502 | missing or empty collection | 286-295 [DERIVED] |
| `qdrant_unavailable` | 502 | QdrantClient construction fails | 575-579 [DERIVED] |
| `embedder_unavailable` | 502 | any embedder exception | 341-345, 358-362 [DERIVED] |

Swallowed / fail-open (caller still gets a response):
- sparse companion probe in `FastSearcher._search`: `except Exception: pass` — legacy dense-only collections skip silently — 175-176, 199-200 [DERIVED]
- `entity_card_probe` per-probe: `except Exception: continue` — 244-245 [DERIVED]
- hidden-generation guard failure: cache set to `[]`, query never fails on the guard — 87-88 [DERIVED]
- sparse query build failure: `_sparse_query = None` — 70-71 [DERIVED]
- `_presentation_joins`: log + return partial dict ("presentation must never fail a query") — 511, 534-538 [DERIVED]
- entity card display probe in `fast_retrieve`: log warning, lane stays empty — 616-620 [DERIVED]

Degradations surfaced in `meta.degraded` instead of errors: reranker unavailable → fusion order (`rerank_degraded` log code) — 493-501, 409-414 [DERIVED]; child lexical lane served by Postgres scan instead of BM25 (`sparse_fallback` log code) — 397-401, 415-422 [DERIVED].

## dumb-code flags
- `import httpx` (24) and `import psycopg` (25) have no other reference in this file — [DERIVED: full source 1-712 scanned, single occurrence each]
- `fast_retrieve` wires `_embed_query` into the engine (597) and calls `_embed_query(query)` again for the card lane (611) — two embedder round trips for identical text per retrieve — 597, 611 [DERIVED]
- `timeout=60` duplicated at 282 and 574; `limit=50` hardcoded at 209 [DERIVED]
- two logger names: `"orchestrator-retrieval"` (41) vs ad-hoc `logging.getLogger("fast")` (535, 617) [DERIVED]
- `MatchAny` imported twice inside the same function body — 106, 117 [DERIVED]
- `__call__` comment says "ignore the passed name" yet forwards the passed `collection` to `_search` — 205-209 [DERIVED]
- default `'150'` vs the comment's own numbers (reconcile within 15 s, cold start ~20 s) — deliberately generous per owner rule, not a bug — 306, 310-311 [DERIVED]
- R2 comment records a historical bug: the v1 HYBRID sparse fallback fired on EVERY turn because collection dict KEYS were queried as collection names (404) — 381-386 [DERIVED]

## refactor notes
- Response shape of `fast_retrieve` (all top-level and `meta`/`trace` keys, 628-712) is consumed by 8 importer modules (FACTS.importers) — renaming keys is a wide blast radius [DERIVED].
- `FastSearcher._filter_for` is the single filter chokepoint; the payload key names `representation_kind`, `corpus_id`, `doc_id`, `parent_id`, `chunk_contract_version` are a contract with the projection writer — changing either side alone leaks or hides points — 97-115 [DERIVED].
- Collection naming is pinned to `NEURAL_EMBED_CONTRACT.contract_id`; changing the contract id orphans every existing collection and triggers `routing_projection_not_ready` — 262-266, 284 [DERIVED].
- Multi-corpus is FAST-only: HYBRID/GRAPH stay single-corpus and keep the 422 gate (in-memory lexical scan / graph seeding are corpus-local) — 554-557 [DERIVED].
- Degradation state is module-level ContextVars; any new degradation lane must reset in `_begin_retrieval` or it bleeds across requests — 379-394, 559 [DERIVED].
- Scope (K1) must thread through `FastSearcher` and `entity_card_probe` — reference-only role must never see implementation material — 57, 121-122, 226-230, 581, 615 [DERIVED].
- Engine logic belongs in `polymath_shared.pass1` (shared with qualification); this file must stay thin adapters — 3-6 [DERIVED].

## VERIFY
```verify
grep -Fq 'def fast_retrieve(' orchestrator/orchestrator/api/fast.py
grep -Fq 'POLYMATH_EMBED_WAKE_BUDGET_S' orchestrator/orchestrator/api/fast.py
grep -Eq 'status = .query_ready.' orchestrator/orchestrator/api/fast.py
grep -Fq 'time.sleep(2.0)' orchestrator/orchestrator/api/fast.py
grep -Fq 'limit=50' orchestrator/orchestrator/api/fast.py
test "$(grep -c -F 'embedder_unavailable' orchestrator/orchestrator/api/fast.py)" -ge 2
! grep -Fq 'import random' orchestrator/orchestrator/api/fast.py
```
