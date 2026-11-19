# unit: orchestrator/orchestrator/api/retrieve.py
anchor: orchestrator/orchestrator/api/retrieve.py:1-991

## purpose
POST /retrieve: the three-lane cross-domain retrieval route. It returns the routing TRACE (document ranking with reasons, parent hits, child evidence, graph expansion); the caller judges the mapping, not just the answer (orchestrator/orchestrator/api/retrieve.py:1-9) [DERIVED]. Answer generation stays outside this endpoint (orchestrator/orchestrator/api/retrieve.py:8-9) [DERIVED]. Consumers: HTTP callers of POST /retrieve plus ten importing modules (FACTS.importers) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| retrieve | def (route POST /retrieve) | (req, request) -> JSON response | retrieve.py:970-991 | HTTP route; module mounted by main.py (importer) [DERIVED] |
| RetrieveRequest | class | pydantic model: query, corpus_id, corpus_ids, workspace, all_authorized, limit, mode, latent, utility, evidence, explore, document_ids, scope, intent | retrieve.py:94-121 | request body of POST /retrieve [DERIVED] |
| resolve_http_scope | def | (conn, req) -> QueryScope | retrieve.py:166-202 | importers (ask.py, evidence.py, graph.py, …) [INFERRED: FACTS lists module importers only] |
| graph_expand_or_502 | def | (surfaces, corpus_ids, preferred_chunk_ids, seed_entity_ids, document_ids, max_seeds, fact_cap) -> list[dict] | retrieve.py:205-237 | — |
| single_corpus_or_422 | def | (scope, mode) -> str | retrieve.py:240-252 | — |
| retrieve_engine_flag | def | (override: str or None) -> "v1" or "v2" | retrieve.py:255-263 | — |
| intent_or_422 | def | (req) -> str or None | retrieve.py:128-137 | — |
| document_filter | def | (req) -> Optional[list[str]] | retrieve.py:157-163 | — |
| rank_graph_facts | def | (rows, seed_ids, selected_fact_ids) -> list[dict] | retrieve.py:66-91 | — |
| fact_rank_enabled | def | () -> bool | retrieve.py:56-57 | — |
| seed_word_match_enabled | def | () -> bool | retrieve.py:641-642 | — |
| _retrieve_impl | def (private core) | async (req: RetrieveRequest) -> dict | retrieve.py:275-472 | retrieve wrapper only [DERIVED] |

Module importers (FACTS): ask.py, chat_retrieval.py, compare_review.py, corpus_plan.py, deep_research.py, evidence.py, graph.py, product.py, ui.py, main.py [DERIVED].

## contracts

**retrieve / _retrieve_impl (POST /retrieve)**
- in: `RetrieveRequest`; query must be non-blank or 422 "query is required" (retrieve.py:276-278) [DERIVED].
- pre: exactly one explicit scope resolved before dispatch; missing scope = 422 `QUERY_SCOPE_REQUIRED`, never search-everything (retrieve.py:166-190) [DERIVED].
- out (default lane): keys `document_lane`, `parent_lane`, `child_dense_lane`, `child_lexical_lane`, `selected_documents`, `child_evidence_count`, `child_evidence`, `graph_facts`; optional `graph_fact_order`, `document_ids`, `evidence_rows`, `evidence_contract` (retrieve.py:446-472) [DERIVED].
- post (v2 engine path): byte-shape-identical contract `evidence/meta/query/selected_documents/selected_sections/trace` (retrieve.py:258-260) [DERIVED].
- dispatch: mode=EXPLORE rewrites to default lane with `explore=True, evidence=True, limit=max(int(req.limit or 12), 24)` (retrieve.py:292-294) [DERIVED]; FAST fans out per corpus (retrieve.py:314-317) [DERIVED]; HYBRID/GRAPH/WILDCARD need one corpus and use `chat_retrieve_mode` when engine is v2 and not `utility`, else the v1 engines (retrieve.py:318-360) [DERIVED]; GNN exists only on v2 without `utility`, else 422 `gnn_requires_v2` (retrieve.py:362-374) [DERIVED].
- post: QUERY-RECEIPTS-V1 — serve exactly as before, then record one receipt (retrieve.py:970, docstring) [DERIVED].

**resolve_http_scope**
- in: conn + req fields `corpus_id`, `corpus_ids`, `workspace`, `all_authorized` (retrieve.py:179-184) [DERIVED].
- out: exactly one resolved scope, narrowed by `narrow_scope` for a principal (retrieve.py:199-202) [DERIVED].
- errors: 422 `QUERY_SCOPE_REQUIRED`, 404 `QUERY_SCOPE_UNKNOWN`, 422 `QUERY_SCOPE_AMBIGUOUS` (retrieve.py:185-198) [DERIVED].

**graph_expand_or_502**
- in: surfaces, corpus_ids, preferred_chunk_ids; optional seed_entity_ids, document_ids, max_seeds (None = 8), fact_cap (None = 20) (retrieve.py:205-220) [DERIVED].
- out: list of fact dicts; zero relationships stays `[]` (retrieve.py:214-216) [DERIVED].
- errors: `GraphBackendUnavailable` -> 502 `graph_backend_unavailable` (retrieve.py:233-237) [DERIVED].

**single_corpus_or_422**
- pre: `len(scope.corpus_ids) == 1` else 422 `mode_requires_single_corpus`; fails closed, never silently narrowed (retrieve.py:246-252) [DERIVED].

**retrieve_engine_flag**
- out: `"v1"` or `"v2"`; anything else folds to `"v2"`; default `POLYMATH_RETRIEVE_ENGINE="v2"` (retrieve.py:262-263) [DERIVED].

**intent_or_422**
- out: canonical upper-cased intent or None when blank; unknown = 422 `unknown_intent` (retrieve.py:129-137) [DERIVED].
- honoured only when `mode in INTENT_MODES` AND engine v2 AND not `req.utility`; else 422 `intent_unsupported` (retrieve.py:308-313) [DERIVED].

**document_filter**
- out: None when absent/empty, else de-duplicated non-blank ids in request order; honoured only by default lane and EXPLORE, other modes 422 `document_filter_unsupported` (retrieve.py:157-163, 299-305) [DERIVED].

**rank_graph_facts**
- out order: (1) facts with evidence in selected chunks, (2) specific predicate before `RELATED_TO`, (3) seeds take turns, (4) `fact_id` ties; deterministic and weight-free (retrieve.py:67-74) [DERIVED].

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | chunks, documents, entities, evidence, facts, retrieval_summaries | FACTS.tables_read; SQL at retrieve.py:508-519, 528-535 |
| Postgres write | none | FACTS.tables_written (empty) |
| Qdrant | only collections named `polymath_*` ending `_{contract_id}` of the ACTIVE contract, restricted to resolved corpora; payload filter `representation_kind="routing_child"` + `corpus_id` MatchAny (+ `doc_id` when filtered); client timeout 30 | retrieve.py:551-600 |
| Neo4j | one-hop expansion via `_neo4j_expand` (canonical bidirectional) | retrieve.py:865-966 (FACTS symbol doc); import `polymath_shared.stores.neo4j_driver` in FACTS.imports |
| Network | embedder (EmbedderClient, wake-on-query), reranker (`apply_rerank`) | retrieve.py:570-579, 424-431 |
| Env | `POLYMATH_GRAPH_FACT_RANK` = `'0'`; `POLYMATH_GRAPH_SEED_WORD_MATCH` = `'0'`; `POLYMATH_RETRIEVE_ENGINE` = `'v2'`; `POLYMATH_GRAPH_SEED_STOP_TERMS` = `''` | FACTS.env; retrieve.py:57, 642, 262, 675 |
| Receipts | one query receipt per request via `record_query_receipt` | retrieve.py:970 (docstring); FACTS.imports |

## invariants
INVARIANT: HYBRID/GRAPH/WILDCARD resolved corpus count == 1 (else 422); FAST exempt — retrieve.py:246-252, 314-317 [DERIVED]
  fails-if: a wider scope either errors (HYBRID/GRAPH) or, if the gate were dropped, engines would scan cross-corpus in memory.
INVARIANT: intent honoured ⇔ (mode ∈ INTENT_MODES) ∧ (engine == "v2") ∧ (not req.utility) — retrieve.py:308, 125 [DERIVED]
  fails-if: an intent silently no-ops on a path that cannot apply its policy.
INVARIANT: `_GRAPH_FACT_CAP` (20) == default `fact_cap` (None = 20) — retrieve.py:53, 219-220 [DERIVED]
  fails-if: the two caps drift and the ranked path returns a different fact count than callers expect.
INVARIANT: `max_seeds` None == `_GRAPH_SEED_CAP` == 8 — retrieve.py:217-218, 750 [DERIVED]
  fails-if: seed cap drift changes graph expansion breadth between callers.
INVARIANT: `_FACT_RANK_POOL` (500) > expected hop-1 facts per 8 seeds (~1 edge per entity) — retrieve.py:50-52 [DERIVED]
  fails-if: the ranked window truncates before ranking, restoring the arbitrary `fact_id` pick.
INVARIANT: `graph_fact_order` key present ⇔ `fact_rank_enabled()` — retrieve.py:461-462 [DERIVED]
  fails-if: consumers cannot tell ranked from legacy fact order.
INVARIANT: child dense lane filters `representation_kind == "routing_child"` — retrieve.py:590-592 [DERIVED]
  fails-if: entity cards/procedures compete in the child lane and surface as empty-chunk_id junk rows.
INVARIANT: unfiltered SQL is byte-identical to the pre-filter path (`_document_clause` returns `""` when no filter) — retrieve.py:479-481, 488-494 [DERIVED]
  fails-if: a no-op change in plan or results breaks the DOCUMENT-SCOPED-RETRIEVE-V1 parity claim.

## determinism & idempotency
determinism: NONDETERMINISTIC (env flags retrieve.py:57, 262, 642, 675; db reads retrieve.py:484-541; Qdrant/Neo4j/embedder network retrieve.py:544-629, 865-966). `rank_graph_facts` itself is deterministic lexicographic (retrieve.py:67-74); `_ordered_terms` removes set-iteration nondeterminism from `tokens` (retrieve.py:680-681) [DERIVED].
idempotency: SAFE — no tables written (FACTS.tables_written empty); each request only reads and records one receipt [DERIVED].

## failure behaviour
- `except Exception: return []` — the whole Qdrant child search swallows any failure; the caller sees an empty dense lane with no signal (retrieve.py:626-627, FACTS.fallbacks) [DERIVED].
- `except Exception: continue` — one broken Qdrant collection never kills the lane; its hits are just missing (retrieve.py:612-613, FACTS.fallbacks) [DERIVED].
- `GraphBackendUnavailable` — handled then raised for translation to 502 (retrieve.py:957 per FACTS.fallbacks; 233-237) [DERIVED].
- receipt-recording failure — handled (assign, expr, raise) inside the wrapper (retrieve.py:980 per FACTS.fallbacks) [DERIVED].
- `RerankUnavailable` — degrades to fusion order (same candidates, same recall, reorder only) and sets `_RERANK_DEGRADED`; never fails the query (retrieve.py:424-431) [DERIVED].
- typed HTTP errors: 422 `QUERY_SCOPE_REQUIRED`, 404 `QUERY_SCOPE_UNKNOWN`, 422 `QUERY_SCOPE_AMBIGUOUS`, 422 `invalid_scope`, 422 "query is required", 422 `mode_requires_single_corpus`, 422 `document_filter_unsupported`, 422 `unknown_intent`, 422 `intent_unsupported`, 422 `gnn_requires_v2`, 502 `graph_backend_unavailable` (retrieve.py:135-371, 234-237) [DERIVED].

## dumb-code flags
- `HIGH_MEDIUM_PREDICATES` mixes lower-case and upper-case spellings of the same predicates: `"causes"`/`"CAUSES"`, `"is_a"`/`"IS_A"`, `"part_of"`/`"PART_OF"`, `"located_in"`/`"LOCATED_IN"` (retrieve.py:33-45) [DERIVED].
- `"v2"` default stated three times: env default, `or "v2"`, and the final `else "v2"` (retrieve.py:262-263) [DERIVED].
- cap 20 duplicated: constant `_GRAPH_FACT_CAP` and the docstring "20-fact cap"/"None = 20" in `graph_expand_or_502` (retrieve.py:53, 219-220) [DERIVED].
- magic numbers in EXPLORE rewrite: `12` and `24` inline (retrieve.py:293-294) [DERIVED].
- magic number `10` in `[c["chunk_id"] for c in result.selected_children[:10]]` (retrieve.py:410) [DERIVED].
- plural-"s" strip only for words longer than three letters (`"hells"` -> `"hell"`), an asymmetric token rule (retrieve.py:654-656) [DERIVED].
- legacy branch kept: default OFF `POLYMATH_GRAPH_FACT_RANK` preserves `ORDER BY fact_id LIMIT 20` (retrieve.py:47-48) [DERIVED].

## refactor notes
- Ten modules import this file (ask.py, chat_retrieval.py, compare_review.py, corpus_plan.py, deep_research.py, evidence.py, graph.py, product.py, ui.py, main.py — FACTS.importers); changing public helper signatures ripples through all of them [DERIVED].
- The v2 response contract (top-level keys `evidence/meta/query/selected_documents/selected_sections/trace`) is parity-proven; compare_review.py calls `chat_retrieve_mode`'s output "the /retrieve contract" (retrieve.py:258-260, 336-339) [DERIVED]. Renaming keys breaks /chat and /compare consumers.
- LEGACY is the frozen lane route retained for G1/G2 golden contracts (retrieve.py:284-286) [DERIVED]. Do not fold it into the mode dispatch.
- FAST no longer passes through `single_corpus_or_422` (multi-corpus fan-out, audit F8) (retrieve.py:242-245, 314-317) [DERIVED].
- `_fetch_parents` authority: `retrieval_summaries` ACTIVE rows win, `chunks.summary` is the fallback (ONE-SUMMARY-AUTHORITY, audit F5) (retrieve.py:499-505, 508-515) [DERIVED]. Changing the COALESCE order reintroduces summary drift.
- Any change to the default lane must keep unfiltered statements byte-identical (retrieve.py:479-481) [DERIVED].

## VERIFY
```verify
grep -Fq 'FACT_RANK_FLAG = "POLYMATH_GRAPH_FACT_RANK"' orchestrator/orchestrator/api/retrieve.py
grep -Fq 'POLYMATH_RETRIEVE_ENGINE' orchestrator/orchestrator/api/retrieve.py
grep -Fq 'mode_requires_single_corpus' orchestrator/orchestrator/api/retrieve.py
grep -Fq 'routing_child' orchestrator/orchestrator/api/retrieve.py
test "$(grep -c -F 'HTTPException(status_code=422' orchestrator/orchestrator/api/retrieve.py)" -ge 8
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/retrieve.py
```
