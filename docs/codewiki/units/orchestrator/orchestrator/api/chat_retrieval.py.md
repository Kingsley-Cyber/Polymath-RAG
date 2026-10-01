# unit: orchestrator/orchestrator/api/chat_retrieval.py
anchor: orchestrator/orchestrator/api/chat_retrieval.py:1-1388

## purpose
The chat path's retrieval engine: `chat_retrieve_v2` runs HYBRID retrieval (lanes A dense-parent / B dense-child / C sparse, one batched embedding, one bounded rerank) on the CANDIDATE-RETRIEVAL-V1 engine; `chat_retrieve_mode` composes the chat modes VECTOR/FAST, HYBRID (default), GRAPH, WILDCARD from the same primitives, plus the experimental GNN fifth mode. orchestrator/orchestrator/api/chat_retrieval.py:1-39 [DERIVED], orchestrator/orchestrator/api/chat_retrieval.py:22-27 [DERIVED], orchestrator/orchestrator/api/chat_retrieval.py:967-986 [DERIVED]. Consumers: the /chat stream handler, `/retrieve`, the evidence route, deep research, compare_review, ui. orchestrator/orchestrator/api/chat_retrieval.py:16-18 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| merge_atom_frontier | def | (parents: dict, atoms: list, maps: list) -> dict | chat_retrieval.py:98-134 | — (WILDCARD atom frontier, P12) |
| graph_dest_parents_from_maps | def | (maps: list, dest_docs: list[str], k: int) -> list[tuple[str, str]] | chat_retrieval.py:137-155 | — (P7 graph destinations) |
| bind_graph_fact_chunks | def | (facts: list[dict], preferred_chunk_ids: list[str]) -> list[dict] | chat_retrieval.py:158-185 | — (graph fact proving chunks) |
| chat_retrieval_flag | def | (override: str \| None = None) -> str | chat_retrieval.py:229-232 | — (rollback flag readers) |
| default_budget | def | () -> CandidateBudget | chat_retrieval.py:260-275 | chat, `/retrieve`, evidence route, deep research searches, mode compositions (chat_retrieval.py:261-263) |
| intent_policy_enabled | def | () -> bool | chat_retrieval.py:278-281 | — |
| chat_retrieve_v2 | def | (query: str, corpus_id: str, *, exact_terms=(), budget=None, query_id="q0", subqueries=(), lanes=None, latent_bridge_ids=(), on_context=None, scope=None, facets=(), second_pass=None) -> dict | chat_retrieval.py:284-820 | stream handler, /chat, bundle assembler, funnel (chat_retrieval.py:16-17) |
| chat_retrieve_mode | def | (mode, query, corpus_id, graph_useful, graph_assist, keep_latent) | chat_retrieval.py:928-964 | — (owner of the four compositions, chat_retrieval.py:22-23) |

Module imported by: orchestrator/orchestrator/api/compare_review.py, deep_research.py, evidence.py, retrieve.py, ui.py [DERIVED from FACTS.importers].

Internal helpers: `_run_second_pass` chat_retrieval.py:823-882, `_with_graph_assist` chat_retrieval.py:901-912, `_fast_budget` chat_retrieval.py:920-925, `_retrieve_gnn(query, corpus_id)` chat_retrieval.py:967-986, `_attach_graph(out, query, corpus_id, qvec, graph_useful, scope)` chat_retrieval.py:989-1043, `_unverified_bridges(slots, children_of, baseline, quota, fill_deadline, plan, qtoks)` chat_retrieval.py:1046-1077, `_jaccard_tokens(qtoks, text)` chat_retrieval.py:1080-1082, `_facet_query_texts(query, kw)` chat_retrieval.py:1085-1093, `_retrieve_wildcard(query, corpus_id, lanes, budget, question)` chat_retrieval.py:1096-1387. [DERIVED from FACTS.symbols]

## contracts

**chat_retrieve_v2** chat_retrieval.py:284-820
- pre: `corpus_id is None` ⇒ HTTPException 422 `{"error_code": "corpus_required", "message": "HYBRID requires an explicit corpus_id (authorized corpus scope)"}` — chat_retrieval.py:308-311 [DERIVED]
- pre: any lane name not in `LANES` ⇒ HTTPException 422 `error_code: "unknown_lane"` — chat_retrieval.py:312-316 [DERIVED]
- in: `subqueries` are `(id, type, text, weight)` tuples from the compiled plan, non-PRIMARY; one batched embedding for all distinct texts — chat_retrieval.py:290-291, chat_retrieval.py:5-6 [DERIVED]
- in: `lanes` restricts the engine; VECTOR = (HIERARCHICAL_ROUTE, GLOBAL_DENSE_CHILD), HYBRID = all three — chat_retrieval.py:300-301 [DERIVED]
- in: `on_context` called ONCE, in-thread, with the immutable SearchContext + the turn's pool, right after the embedding; must not raise — chat_retrieval.py:302-306 [DERIVED]
- in: `second_pass` called ONCE between lanes and judge, `(ctx, pool, result) -> (rows, receipt, deadline)`; rows with `kept` False are built but not searched — chat_retrieval.py:294-299 [DERIVED]
- post: budget resolved as `shape_budget(query, budget or default_budget())`; explicit lanes reordered to canonical `LANES` order — chat_retrieval.py:320-322 [DERIVED]
- out: same dict shape as `hybrid_fast_retrieve`; `meta.plan_version` / `trace.plan` say `chat-retrieval-v2` — chat_retrieval.py:16-18 [DERIVED]

**chat_retrieval_flag** chat_retrieval.py:229-232: returns exactly one of `"v1"`, `"v2"`, `"v2-single"`; any other value (incl. empty env) coerced to `"v2"`. [DERIVED]

**default_budget** chat_retrieval.py:260-275: `CandidateBudget()` → `facet_diversity_budget` applied first when `facet_diversity_enabled()` → env overrides `POLYMATH_CHAT_<NAME>` cast per `_INT_KNOBS`/`_FLOAT_KNOBS`/`_STR_KNOBS`; unparseable values silently skipped (`ValueError` → pass). [DERIVED]

**bind_graph_fact_chunks** chat_retrieval.py:158-185: attaches a proving `chunk_id` per fact via `SELECT DISTINCT ON (fact_id) fact_id, chunk_id FROM evidence ...` preferring judged evidence chunks; any Exception ⇒ facts returned unchanged. chat_retrieval.py:169-176 [DERIVED]

**merge_atom_frontier** chat_retrieval.py:98-134: atoms nominate docs, parent maps open parents; existing latent slots keep precedence (`hop1` max'd, `abstraction` filled only when empty); empty atoms/maps leave `parents` unchanged. chat_retrieval.py:101-103 [DERIVED]

**graph_dest_parents_from_maps** chat_retrieval.py:137-155: only `doc_id` in `dest_docs` (when non-empty), unique `parent_id`, capped at `k`; empty maps ⇒ `[]`. chat_retrieval.py:139-154 [DERIVED]

**intent_policy_enabled** chat_retrieval.py:278-281: true iff `POLYMATH_CHAT_INTENT_POLICY` ∈ ("1","true","yes","on") case-insensitive; default OFF ⇒ budget byte-identical. [DERIVED]

## effect surface
- Postgres read: `evidence` (fact_id, chunk_id) — chat_retrieval.py:169-173 [DERIVED]; `document_parent_maps` (parent_id, routing_signature) — chat_retrieval.py:404-406 [DERIVED]; `mentions` — per FACTS.tables_read, read site beyond shown excerpt, plausibly via `gather_lift_candidates`/`LiveLiftSources` in `lift_search` — chat_retrieval.py:427-431 [INFERRED: only live Postgres handle in that closure]
- Postgres written: none (FACTS.tables_written empty) [DERIVED]
- Qdrant: `QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)` — chat_retrieval.py:324 [DERIVED]; searches via `searcher._search` with filters `representation_kind`/`corpus_id` — chat_retrieval.py:356-359, chat_retrieval.py:439-441 [DERIVED]; profile/atom/parent-map collections via `polymath_shared.document_profile` projections (`profile_nominate`, `search_atoms`, `search_parent_maps`) — chat_retrieval.py:379, chat_retrieval.py:388, chat_retrieval.py:395, chat_retrieval.py:470-489 [DERIVED]
- Embeddings: `_embed_queries(terms)` in `lift_search` — chat_retrieval.py:438 [DERIVED]; one batched embedding for all distinct plan texts — chat_retrieval.py:5-6 [DERIVED]
- Concurrency: `ThreadPoolExecutor(max_workers=max(1, int(budget.max_workers)), thread_name_prefix="chat-lanes")` — chat_retrieval.py:333 [DERIVED]; second pool at chat_retrieval.py:1297 [DERIVED from FACTS.nondeterminism]
- Env: `POLYMATH_CHAT_RETRIEVAL` = `"v2"` (values v1 | v2 | v2-single) — chat_retrieval.py:226, chat_retrieval.py:231 [DERIVED]; `POLYMATH_CHAT_INTENT_POLICY` = `""` (off) — chat_retrieval.py:281 [DERIVED]; knob family `POLYMATH_CHAT_<NAME>` — chat_retrieval.py:269 [DERIVED]; `POLYMATH_CHAT_LATENT_SELECTION` = `'0'` — chat_retrieval.py:741 [DERIVED from FACTS.env]; `POLYMATH_LATENT_POOL_MAX` = `'60'` — chat_retrieval.py:745 [DERIVED from FACTS.env]

## invariants
- INVARIANT: `chat_retrieval_flag(non-enum value)` == `"v2"` — chat_retrieval.py:231-232 [DERIVED]; fails-if: a typo'd env flag silently selects v2 instead of erroring, hiding the v1 rollback.
- INVARIANT: embeddings per turn for plan texts == 1 (all distinct texts, one call; WILDCARD reuses the same vector, no second call) — chat_retrieval.py:5-6, chat_retrieval.py:31-32 [DERIVED]; fails-if: extra embedding calls blow the embed deadline and get receipted.
- INVARIANT: `len(sub_specs)` ≤ `budget.max_subqueries` — chat_retrieval.py:342 [DERIVED]; fails-if: extra plan subqueries silently dropped.
- INVARIANT: pool `max_workers` ≥ 1 (`max(1, int(budget.max_workers))`) — chat_retrieval.py:333 [DERIVED]; fails-if: a 0/negative knob value would construct a dead executor.
- INVARIANT: GRAPH bounded G — seeds ≤ 8 (≤ 2 when the plan says not relational), hop-1, ≤ 20 facts, fail-open — chat_retrieval.py:27-29 [DERIVED]; fails-if: unbounded expansion breaks the GRAPH latency budget.
- INVARIANT: WILDCARD bridges ≤ 3 and never in the evidence list; frontier bounded by `wildcard_deadline_s` — chat_retrieval.py:30-34 [DERIVED]; fails-if: bridges leak into evidence and change answers.
- INVARIANT: `graph_dest_parents_from_maps` output length ≤ `k` and `parent_id`s unique — chat_retrieval.py:149-154 [DERIVED]; fails-if: duplicate parents flood the P7 lane.
- INVARIANT: tables written by this unit = ∅ — FACTS.tables_written [DERIVED]; fails-if: retrieval becomes stateful, breaking retry/idempotency.

## determinism & idempotency
determinism: NONDETERMINISTIC (clocks: `time.perf_counter` at chat_retrieval.py:328, 633, 637, 650, 653, 691, 701, 706, 709, 713, 830, 844, 851, 862, 882, 999, 1024, 1053, 1130, 1144-1145, 1169, 1180-1182, 1191, 1201, 1215, 1221-1225, 1240, 1263, 1277, 1298, 1302-1303, 1317, 1329, 1335, 1381; concurrency: ThreadPoolExecutor chat_retrieval.py:333, chat_retrieval.py:1297; network: Qdrant chat_retrieval.py:324, embeddings chat_retrieval.py:438; db: Postgres reads chat_retrieval.py:166-173, chat_retrieval.py:403-406; env: chat_retrieval.py:231, chat_retrieval.py:269, chat_retrieval.py:281, chat_retrieval.py:741, chat_retrieval.py:745) [DERIVED from FACTS.nondeterminism + SOURCE]
idempotency: SAFE — no tables written (FACTS.tables_written empty); every call re-reads stores and re-embeds [DERIVED]

## failure behaviour
- Swallowed, caller sees unchanged input: `bind_graph_fact_chunks` DB error ⇒ facts returned without `chunk_id` — chat_retrieval.py:175-176 [DERIVED]
- Swallowed, feature silently off: `fact_rank_enabled` ImportError ⇒ stub returns `False` (merge → bounce window; 2026-09-25 the unguarded import made /retrieve GRAPH answer 500) — chat_retrieval.py:217-224 [DERIVED]
- Swallowed, empty result: `sparse_vector_for` failure ⇒ `sparse_q = None`, "lane C degrades in the engine" — chat_retrieval.py:346-349 [DERIVED]; `lift_search` gather error ⇒ `[]` — chat_retrieval.py:432-433 [DERIVED]; atom lane error ⇒ `pass` — chat_retrieval.py:393-394 [DERIVED]; per FACTS.fallbacks also `return []` at chat_retrieval.py:540, chat_retrieval.py:548, chat_retrieval.py:563 [DERIVED]
- Swallowed, partial result: blend nomination error ⇒ `q_docs = []` — chat_retrieval.py:472-473 [DERIVED]; per FACTS.fallbacks `handled: assign` at chat_retrieval.py:599, chat_retrieval.py:834, chat_retrieval.py:857, chat_retrieval.py:1012, chat_retrieval.py:1022, chat_retrieval.py:1059, chat_retrieval.py:1166, chat_retrieval.py:1174, chat_retrieval.py:1269, chat_retrieval.py:1339; `return (rec, facets, round((time.perf_counter()...` at chat_retrieval.py:849; `return (rows, rec, None)` at chat_retrieval.py:1198 [DERIVED from FACTS.fallbacks]
- Raised: HTTPException 422 `corpus_required` — chat_retrieval.py:309-311; HTTPException 422 `unknown_lane` — chat_retrieval.py:315-316; HTTPException 502 `qdrant_unavailable` (message includes `type(exc).__name__`) — chat_retrieval.py:325-327; bare re-raise at chat_retrieval.py:1127 (inside `_retrieve_wildcard`) [DERIVED from FACTS.fallbacks]
- Degradation receipts, not errors: embedding breach receipted never dropped; core lane past `lane_deadline_s` dropped + receipted `<lane>_timeout`; judge past `rerank_deadline_s` yields fusion order + `rerank_timeout`; all land in `meta.degraded`, per-stage `latency_ms` in trace — chat_retrieval.py:10-14 [DERIVED]

## dumb-code flags
- Magic numbers: `MAPPED_MIN_WINDOW_S = 0.35` chat_retrieval.py:86, `MAPPED_MIN_LANES_S = 0.2` chat_retrieval.py:87, `WILDCARD_FINISH_GRACE_S = 1.5` chat_retrieval.py:90, Qdrant `timeout=60` chat_retrieval.py:324, lift `k=3` chat_retrieval.py:430, atom `k` default `12` chat_retrieval.py:388, steer `k` default `4` chat_retrieval.py:484. [DERIVED]
- Naming inconsistency: `POLYMATH_LATENT_POOL_MAX` chat_retrieval.py:745 breaks the `POLYMATH_CHAT_<NAME>` knob convention of chat_retrieval.py:269 — env-only, invisible to `default_budget`'s override loop [INFERRED: it would be skipped by the `POLYMATH_CHAT_` prefix rule].
- Duplicated atom-kind vocabulary: `_WILDCARD_ATOM_KINDS` chat_retrieval.py:92-95 vs kinds also selected via `budget.atom_kinds` chat_retrieval.py:384 and `RELATIONAL_KINDS` chat_retrieval.py:455 — two sources of truth [INFERRED: kinds added in one list won't appear in the other].
- Defensive `getattr(budget, "atom_kinds", ())` / `"atom_k"` / `"doc_steer_kinds"` defaults scattered — chat_retrieval.py:384, chat_retrieval.py:388, chat_retrieval.py:480 — implies older `CandidateBudget` objects without these fields must still work [INFERRED].
- Mid-file imports below definitions (`retrieval_modes`, `fast`, `graph`, `retrieve`, `settings` imported at chat_retrieval.py:186-215, after `bind_graph_fact_chunks` ends at 185) plus the guarded `fact_rank_enabled` import — a circular-import / merge-window workaround, not dead code — chat_retrieval.py:186-224 [DERIVED]
- `"v2"` literal appears 3× in one expression of `chat_retrieval_flag` — chat_retrieval.py:231-232 [DERIVED]

## refactor notes
- Result-dict shape is the widest contract: stream handler, /chat, bundle assembler and funnel consume it unchanged — chat_retrieval.py:16-18 [DERIVED]; plus five importer modules (FACTS.importers). Changing keys breaks all of them.
- `default_budget` is "the one budget every surface starts from"; the `POLYMATH_CHAT_<NAME>` env names are an external operator contract — chat_retrieval.py:261-263, chat_retrieval.py:269 [DERIVED]. Renaming any knob in `_INT_KNOBS`/`_FLOAT_KNOBS`/`_STR_KNOBS` (chat_retrieval.py:236-257) silently orphans deployed env settings.
- v1 rollback boundary: `POLYMATH_CHAT_RETRIEVAL=v1` flag or per-request `retrieval: "v1"`; `/retrieve`, `/ask`, TRAIL stay on `hybrid-retrieval-v1` — chat_retrieval.py:19-20, chat_retrieval.py:226-232 [DERIVED].
- Do not remove the `fact_rank_enabled` import guard — it exists for the merge → bounce window and its absence caused a real /retrieve GRAPH 500 — chat_retrieval.py:217-224 [DERIVED].
- Heavy private-symbol coupling to `orchestrator.api.fast` (`_begin_retrieval`, `_embed_queries`, `_corpus_collections`, `_ensure_fast_ready`, `_neighbor_lookup`, `_presentation_joins`, `_region_lookup`, `_rerank_children`, `_RERANK_DEGRADED`, `degradations`, `entity_card_probe`) and `orchestrator.api.graph._selected_surfaces`, `orchestrator.api.retrieve.graph_expand_or_502` — chat_retrieval.py:199-214 [DERIVED]; also direct `searcher._search` / `searcher._hidden_for` — chat_retrieval.py:338, chat_retrieval.py:359 [DERIVED]. Renaming any of those privates breaks this module.
- The `on_context` seam is architectural: the primary vector must reach graph seeds and the sweep through the immutable SearchContext, never through the result dict — chat_retrieval.py:36-38 [DERIVED].
- Mode composition semantics are stamped `MODE_COMPOSITION_CONTRACT = "mode-composition-v1"` — chat_retrieval.py:888 [DERIVED from FACTS.constants]; changing compositions needs a new contract string.

## VERIFY
```verify
grep -Fq 'MAPPED_MIN_WINDOW_S = 0.35' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'WILDCARD_FINISH_GRACE_S = 1.5' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'return v if v in ("v1", "v2", "v2-single") else "v2"' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'SELECT DISTINCT ON (fact_id) fact_id, chunk_id' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'thread_name_prefix="chat-lanes"' orchestrator/orchestrator/api/chat_retrieval.py
grep -Fq 'MODE_COMPOSITION_CONTRACT = "mode-composition-v1"' orchestrator/orchestrator/api/chat_retrieval.py
test "$(grep -c -F 'time.perf_counter' orchestrator/orchestrator/api/chat_retrieval.py)" -ge 30
```
