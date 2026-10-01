# unit: orchestrator/orchestrator/api/retrieve.py
anchor: orchestrator/orchestrator/api/retrieve.py:1-882

## purpose
POST `/retrieve` — the three-lane cross-domain retrieval route; returns the routing TRACE (document ranking with reasons, parent hits, child evidence, graph expansion) so the caller judges the mapping. Document routing is parallel and never a recall gate: a child hit survives even when its document scores zero. Answer generation lives outside this endpoint. — orchestrator/orchestrator/api/retrieve.py:1-10 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `retrieve` | def (route handler) | async (req, request) -> dict; POST `/retrieve` | retrieve.py:860-881 | mounted on router; module imported by ask.py, chat_retrieval.py, compare_review.py, corpus_plan.py, deep_research.py, evidence.py, graph.py, ui.py, main.py (FACTS.importers) |
| `RetrieveRequest` | class (BaseModel) | fields: `query`, `corpus_id`, `corpus_ids`, `workspace`, `all_authorized=False`, `limit=10`, `mode`, `latent`, `utility`, `evidence=False`, `explore=False`, `document_ids`, `scope`, `intent` | retrieve.py:92-119 | — |
| `resolve_http_scope` | def | (conn, req) -> QueryScope | retrieve.py:164-200 | — |
| `graph_expand_or_502` | def | (surfaces, corpus_ids, preferred_chunk_ids, seed_entity_ids=None, document_ids=None, max_seeds=None) -> list[dict] | retrieve.py:203-231 | — |
| `single_corpus_or_422` | def | (scope, mode) -> str | retrieve.py:234-246 | — |
| `retrieve_engine_flag` | def | (override=None) -> str | retrieve.py:249-257 | — |
| `rank_graph_facts` | def | (rows: list[dict], seed_ids: list[str], selected_fact_ids) -> list[dict] | retrieve.py:64-89 | — |
| `fact_rank_enabled` | def | () -> bool | retrieve.py:54-55 | — |
| `document_filter` | def | (req) -> Optional[list[str]] | retrieve.py:155-161 | — |
| `intent_or_422` | def | (req) -> str \| None | retrieve.py:126-135 | — |

Per-symbol importers are not in FACTS; only module-level importers are known (9 files, listed above).

## contracts

**POST /retrieve — `retrieve` (860-881, FACTS) wrapping `_retrieve_impl` (269-466)**
- in: `RetrieveRequest` body; blank `query` → 422 `"query is required"` — retrieve.py:270-272 [DERIVED]
- pre: exactly one explicit scope (corpus_id / corpus_ids / workspace / all_authorized), never implicit-all — retrieve.py:164-188; `mode=EXPLORE` is rewritten to `{"mode": None, "explore": True, "evidence": True, "limit": max(int(req.limit or 12), 24)}` — retrieve.py:286-288; `document_ids` only on the default lane, else 422 — retrieve.py:293-299; `intent` only when `mode in INTENT_MODES` AND engine `v2` AND not `utility`, else 422 — retrieve.py:301-307 [DERIVED]
- dispatch: FAST → `fast_retrieve(query, list(scope.corpus_ids), **scope_kwargs(role_scope))` (multi-corpus) — retrieve.py:308-311; HYBRID/GRAPH/WILDCARD → single corpus (313/327/344), v2 core `chat_retrieve_mode` when `retrieve_engine_flag() == "v2" and not req.utility` (317-320, 335-338, 348-351), else v1 `hybrid_fast_retrieve`/`graph_retrieve`/`wildcard_retrieve` (321-325, 339-341, 352-354); GNN → v2-only, else 422 — retrieve.py:356-368; default lane → `run_lanes` — retrieve.py:392-398 [DERIVED]
- out: keys `query`, `document_lane`, `parent_lane`, `child_dense_lane`, `child_lexical_lane`, `selected_documents`, `child_evidence_count`, `child_evidence`, `graph_facts` — retrieve.py:440-447; `graph_fact_order = "ranked"` iff `fact_rank_enabled()` — retrieve.py:455-456; `document_ids` echo — retrieve.py:457-458; `evidence_rows` + `evidence_contract = "retrieve-evidence-rows-v1"` when `req.evidence or req.explore` — retrieve.py:459-465 [DERIVED]
- post: wrapper records one query receipt after serving (QUERY-RECEIPTS-V1) — retrieve.py:860-881 (FACTS doc) [DERIVED]

**`resolve_http_scope`**: missing scope → 422 `QUERY_SCOPE_REQUIRED` — retrieve.py:183-188; unknown → 404 `QUERY_SCOPE_UNKNOWN` — retrieve.py:189-192; ValueError → 422 `QUERY_SCOPE_AMBIGUOUS` — retrieve.py:193-196; friends principals narrowed via `narrow_scope(scope)` — retrieve.py:197-200 [DERIVED]

**`graph_expand_or_502`**: `GraphBackendUnavailable` → 502 `graph_backend_unavailable`; GRAPH_SUCCESS with zero relationships stays `[]`; `max_seeds` narrows the D2 default of 8, `None = 8` — retrieve.py:211-215, 227-231 [DERIVED]

**`retrieve_engine_flag`**: returns only `"v1"` or `"v2"`; any other value (incl. blank after strip/lower) → `"v2"`; default from env `"v2"` — retrieve.py:249-257 [DERIVED]

**`rank_graph_facts`**: deterministic, weight-free order — (1) facts with evidence in selected chunks first, (2) specific predicate before the ontology last resort (`RELATED_TO`), (3) seeds take turns, (4) `fact_id` ties — retrieve.py:64-72 [DERIVED]

**`_corpus_seed_ids`**: seeds only from corpus-authorized eligible entities with evidence; card-resolved ids seed first; `MENTION_ONLY` never seeds; `matched.sort(key=lambda x: (not x[0], x[1]))` for determinism; cap = `_GRAPH_SEED_CAP` (8), `max_seeds` may only narrow — retrieve.py:651-669, 711-713 [DERIVED]

**`_authorized_fact_ids`**: a fact is authorized when supported by evidence in a scoped corpus; facts with no evidence anywhere are intentionally kept — retrieve.py:717-725, 740 [DERIVED]

**`_qdrant_search`**: queries only active-contract collections of the resolved corpora, filter `representation_kind="routing_child"` + `corpus_id` (+ optional `doc_id` payload filter applied before `limit`) — retrieve.py:545-560, 583-596 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `chunks`, `documents`, `entities`, `evidence`, `facts`, `retrieval_summaries` (FACTS.tables_read; SQL at 484-488, 502-514, 522-529, 676-689, 732-738) | retrieve.py:484-738 [DERIVED] |
| Postgres write | none (FACTS.tables_written = []) | FACTS [DERIVED] |
| Qdrant | `query_points` on collections with prefix `polymath_` + suffix `_{contract_id}` ∩ resolved corpora; client `timeout=30` | retrieve.py:544-560, 599-604 [DERIVED] |
| Network | `EmbedderClient` embed of the query; Neo4j one-hop expand via `_neo4j_expand`; rerank service `apply_rerank` | retrieve.py:566-573, 759-856 (FACTS), 414-421 [DERIVED] |
| Env | `POLYMATH_GRAPH_FACT_RANK` = `'0'`; `POLYMATH_RETRIEVE_ENGINE` = `'v2'` | retrieve.py:55, 256 (FACTS) [DERIVED] |
| Env (comment only) | `POLYMATH_G3_RERANKER=1` — actual gate lives in `polymath_shared.rerank.apply_rerank`, not read here | retrieve.py:409-413 [DERIVED] |

## invariants

INVARIANT: resolved seed count ≤ `_GRAPH_SEED_CAP` = 8; `max_seeds` only narrows (`max(0, min(_GRAPH_SEED_CAP, int(max_seeds)))`) — retrieve.py:646, 712-713 [DERIVED]
  fails-if: widening past 8 changes the D2 expansion budget and hop-1 fact mix.
INVARIANT: HYBRID/GRAPH/WILDCARD/GNN run on exactly 1 corpus (`len(scope.corpus_ids) != 1` → 422) — retrieve.py:240-245, 313, 327, 344, 358 [DERIVED]
  fails-if: wider scope fails closed rather than silently narrowing.
INVARIANT: Qdrant targets ⊆ `{qdrant_collection_name(cid, contract.contract_id) for cid in corpus_ids}` — retrieve.py:550-560 [DERIVED]
  fails-if: other contracts' collections have different vector dimensions — retrieve.py:546-548.
INVARIANT: child dense lane filters `representation_kind == "routing_child"` — retrieve.py:585-586 [DERIVED]
  fails-if: unfiltered lane lets entity cards/procedures compete as empty-chunk_id junk rows — retrieve.py:577-582.
INVARIANT: rerank only reorders; on `RerankUnavailable` the fusion-order candidates survive unchanged — retrieve.py:409-425 [DERIVED]
  fails-if: failing the query on a cold reranker would destroy recall for no ranking gain.
INVARIANT: unfiltered SQL is byte-identical to the pre-filter statement (empty clause when no filter) — retrieve.py:469-475 [DERIVED]
  fails-if: default-path drift breaks DOCUMENT-SCOPED-RETRIEVE-V1 parity.
INVARIANT: evidence-less facts stay authorized (kept in `in_scope` handling) — retrieve.py:740, 722-725 [DERIVED]
  fails-if: silently hiding them removes the loud R3a assembly failure.
INVARIANT: `"graph_fact_order": "ranked"` present iff `fact_rank_enabled()` — retrieve.py:455-456 [DERIVED]
  fails-if: clients cannot distinguish ranked facts from the legacy `fact_id` window (45-46).

## determinism & idempotency
determinism: NONDETERMINISTIC (db reads via `tx()`, Qdrant `query_points` — retrieve.py:599-604; embedder network call — retrieve.py:566-573; Neo4j expand — retrieve.py:759-856; env flags — retrieve.py:55, 256; reranker availability — retrieve.py:422-425). Internal orderings are deterministic: `rank_graph_facts` lexicographic — retrieve.py:65-72; seed ties by `entity_id` — retrieve.py:711. [DERIVED]
idempotency: SAFE for retrieval output (no table writes; FACTS.tables_written = []); each call does record one query receipt (QUERY-RECEIPTS-V1 wrapper) — retrieve.py:860-881 (FACTS) [DERIVED]

## failure behaviour

| site | behaviour | anchor |
|---|---|---|
| `_qdrant_search` outer handler | SWALLOWED: `except Exception: return []` — any Qdrant/embedder failure yields an empty child dense lane, caller sees no error | retrieve.py:619-621 (FACTS line 620) [DERIVED] |
| `_qdrant_search` per collection | SWALLOWED: `except Exception: continue` — one broken collection never kills the lane | retrieve.py:606-607 [DERIVED] |
| `_neo4j_expand` | handled Exception (importfrom, raise) — tail not shown in excerpt | retrieve.py:847 (FACTS) [DERIVED] |
| `retrieve` wrapper | handled Exception (assign, expr, raise) — tail not shown in excerpt | retrieve.py:870 (FACTS) [DERIVED] |
| rerank | `RerankUnavailable` → degrade to fusion order; `_RERANK_DEGRADED.set(str(exc)[:300])` | retrieve.py:422-425 [DERIVED] |
| graph backend | `GraphBackendUnavailable` → 502 `graph_backend_unavailable` | retrieve.py:227-231 [DERIVED] |

Typed codes raised: 422 `"query is required"` (272), 422 `QUERY_SCOPE_REQUIRED` (185), 404 `QUERY_SCOPE_UNKNOWN` (191), 422 `QUERY_SCOPE_AMBIGUOUS` (195), 422 `invalid_scope` (265), 422 `unknown_intent` (134), 422 `intent_unsupported` (304), 422 `document_filter_unsupported` (296), 422 `mode_requires_single_corpus` (242), 422 `gnn_requires_v2` (364), 502 `graph_backend_unavailable` (229). [DERIVED]

## dumb-code flags
- `max(int(req.limit or 12), 24)`: the `12` fallback disagrees with the model default `limit: int = 10` and only fires when `limit` is falsy; `24` is the EXPLORE floor — retrieve.py:287-288 vs 98 [DERIVED]
- `HIGH_MEDIUM_PREDICATES` stores both cases of the same predicate: `"causes"`/`"CAUSES"`, `"is_a"`/`"IS_A"`, `"part_of"`/`"PART_OF"`, `"located_in"`/`"LOCATED_IN"`, `"uses"`/`"USES"` — retrieve.py:31-43; no use visible in lines 1-747, so any consumer is in the invisible tail (`_neo4j_expand` 759-856) [INFERRED: constant defined but unreferenced in the shown half]
- `_FACT_RANK_POOL = 500` and `_GRAPH_FACT_CAP = 20` are unreferenced in the visible source; presumably consumed by `_neo4j_expand` (759-856, not shown) — retrieve.py:50-51 [INFERRED: no visible reader in lines 1-747]
- `POLYMATH_G3_RERANKER=1` named only in a comment; the gate is inside `polymath_shared.rerank.apply_rerank` — retrieve.py:411, 414 [DERIVED]
- `_RERANK_DEGRADED` is `fast.py` module state mutated here — retrieve.py:416, 423 [DERIVED]

## refactor notes
- Blast radius: 9 modules import this file (ask.py, chat_retrieval.py, compare_review.py, corpus_plan.py, deep_research.py, evidence.py, graph.py, ui.py, main.py — FACTS.importers); renaming any public symbol or the response shape touches all of them.
- Response keys (440-447) plus optional `graph_fact_order`/`document_ids`/`evidence_rows`/`evidence_contract` (455-465) are the external contract; v1/v2 output is claimed byte-shape-identical (parity-proven, same top-level keys evidence/meta/query/selected_documents/selected_sections/trace) and compare_review.py calls `chat_retrieve_mode` output "the /retrieve contract" — retrieve.py:250-255, 328-333, 440-465 [DERIVED]
- Contract literals that must not drift: `"retrieve-evidence-rows-v1"` — retrieve.py:465; `"ranked"` — retrieve.py:456 [DERIVED]
- Parent summary authority is `COALESCE(rs.summary_text, c.summary)` gated on `rs.active AND rs.kind = 'section_retrieval_summary'` (audit F5, ONE-SUMMARY-AUTHORITY) — retrieve.py:503-510; reordering this join changes which text scores.
- `scope_kwargs(role_scope)` (K1) is threaded into every engine dispatch: FAST 311, HYBRID 320/325, GRAPH 338/341, WILDCARD 351/354, GNN 368 — dropping any silently broadens the role scope. [DERIVED]
- The two swallowed handlers (606-607, 619-621) are deliberate resilience; converting them to raises changes lane-failure semantics for every caller. [DERIVED]

## VERIFY
```verify
grep -Fq 'POLYMATH_GRAPH_FACT_RANK' orchestrator/orchestrator/api/retrieve.py
grep -Fq 'match=MatchValue(value="routing_child")' orchestrator/orchestrator/api/retrieve.py
grep -Fq 'cap = _GRAPH_SEED_CAP if max_seeds is None else max(0, min(_GRAPH_SEED_CAP, int(max_seeds)))' orchestrator/orchestrator/api/retrieve.py
grep -Fq '"error_code": "gnn_requires_v2",' orchestrator/orchestrator/api/retrieve.py
grep -Fq 'COALESCE(rs.summary_text, c.summary) AS summary' orchestrator/orchestrator/api/retrieve.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/retrieve.py
test "$(grep -c -F 'HTTPException' orchestrator/orchestrator/api/retrieve.py)" -ge 10
```
