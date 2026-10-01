# unit: shared/polymath_shared/candidate_engine.py
anchor: shared/polymath_shared/candidate_engine.py:1-2259

## purpose
The CHAT-RETRIEVAL-V2 candidate engine (`CANDIDATE_ENGINE_VERSION = "candidate-retrieval-v1"`): runs independent retrieval lanes — A `HIERARCHICAL_ROUTE`, B `GLOBAL_DENSE_CHILD`, C `GLOBAL_SPARSE_CHILD`, plus additive lanes D–G and graph/GNN arrivals — unions them with full provenance, reranks a bounded prefix with one cross-encoder judge, and composes final synthesis evidence. Pure over injected search callables ("no Qdrant, no Postgres here") — candidate_engine.py:1-39. The module is imported by `orchestrator/orchestrator/api/chat_retrieval.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| synthesis_role | def | (arrivals) -> str | candidate_engine.py:113-126 | — |
| CandidateBudget | class | frozen dataclass; to_dict() -> dict | candidate_engine.py:130-360 | — |
| facet_diversity_enabled | def | (env=None) -> bool | candidate_engine.py:371-373 | — |
| facet_diversity_budget | def | (budget) -> CandidateBudget | candidate_engine.py:376-378 | — |
| shape_budget | def | (resolved_request, budget) -> CandidateBudget | candidate_engine.py:381-395 | — |
| sparse_query_for | def | (text, exact_terms) -> tokens + choosing rule | candidate_engine.py:414-426 | — |
| sparse_vector_for | def | (text, exact_terms) -> (indices, values) | candidate_engine.py:429-438 | — |
| SearchContext | class | immutable per-turn search inputs (one query vector) | candidate_engine.py:442-453 | — |
| SubQuery | class | one typed subquery of the compiled plan, own vector | candidate_engine.py:457-474 | — |
| CandidateEvidence | class | to_row() | candidate_engine.py:531-572 | — |
| CandidateResult | class | — | candidate_engine.py:576-589 | — |
| retrieve_candidates | def | (ctx, budget, dense_search, sparse_search, latent_search, dualread_search, lift_search, fanout_search, graph_dest_search, gnn_search, region_lookup, subqueries, executor, prestarted) -> CandidateResult | candidate_engine.py:720-774 | — |
| retrieve_extra_subqueries | def | (ctx, budget, subqueries, dense_search, sparse_search, executor, deadline, region_lookup) | candidate_engine.py:1447-1490 | — |
| merge_extra_candidates | def | (result, items, aspects, budget) | candidate_engine.py:1493-1589 | — |
| replace_candidate | def | (c) | candidate_engine.py:1592-1593 | — |
| effective_score | def | (c) -> score | candidate_engine.py:1604-1608 | — |
| judged_score | def | (c, budget) -> score | candidate_engine.py:1611-1616 | — |
| compose_evidence | def | (judged, budget, weak_aspects, primary_id, facets) | candidate_engine.py:1642-1919 | — |
| structural_noise_reason | def | (text) -> reason or None | candidate_engine.py:1928-1946 | — |
| judged_prefix | def | (fused, ranked_lanes, budget, fallback) | candidate_engine.py:1983-2039 | — |
| select_evidence | def | (result, budget, rerank_children, neighbor_lookup, facets) | candidate_engine.py:2152-2259 | — |

"used by" is module-level: only `orchestrator/orchestrator/api/chat_retrieval.py` imports this file (FACTS.importers); per-symbol importers not in FACTS.

## contracts

**retrieve_candidates** — candidate_engine.py:720-774
- in: injected callables `dense_search(kind, top_k, extra_filters) -> [{payload, score}]` (desc), `sparse_search(top_k)` (raises when unavailable), `region_lookup(chunk_ids) -> {chunk_id: region_role}` — candidate_engine.py:16-20.
- pre: one `CandidateBudget` consumed directly; no plan copy — candidate_engine.py:25-26.
- out: lanes collected BY NAME against one absolute deadline, fused in fixed lane order (`_gather`, candidate_engine.py:672-695).
- post: no deadline hit ⇒ byte-identical to the sequential engine — candidate_engine.py:34-36; a lane past `lane_deadline_s` is dropped with a `<lane>_timeout` receipt in `degraded` — candidate_engine.py:32-34.

**compose_evidence** — candidate_engine.py:1642-1919
- in: `judged` = the reranked prefix in judge order.
- post: deterministic, metadata-only slot order: pure relevance → source diversity → sparse winners (lane C arrivals) → aspect coverage → fill; scores compared on a sigmoid of the raw judge logit — candidate_engine.py:233-239.

**judged_prefix** — candidate_engine.py:1983-2039
- post: fills `rerank_max` seats document-fairly — round 1 seats every surfaced document's best candidate, then fusion order under a per-document cap, then remaining seats ignore the cap; receipt names `judged_docs`, `capped_out`, `prefix_policy` — candidate_engine.py:160-167.

**shape_budget** — candidate_engine.py:381-395
- post: enumeration query raises minimums: `hierarchy_section_k` ≥ 32, `hierarchy_max_sections_per_document` ≥ 8, `hierarchy_child_k` ≥ 4, `global_dense_k` ≥ 60, `rerank_max` ≥ 28, `synthesis_max` ≥ 28, `neighbor_expansion` ≥ 1 — candidate_engine.py:386-392; document-metadata queries lift region demotion (docstring) — candidate_engine.py:383-384.

**synthesis_role** — candidate_engine.py:113-126
- post: arrivals ∩ {A,B,C} ⇒ `"DIRECT"`; `ARRIVAL_GRAPH_DEST` or `ARRIVAL_GNN_ROUTE` ⇒ `"RELATIONAL"`; `LANE_F` ⇒ `"PRECISION"`; ∩ {D,E,G} ⇒ `"LATENT"`; else `"DIRECT"`. §47 law: LATENT may never substitute for DIRECT — candidate_engine.py:105-110, 117-126.

**facet_diversity_enabled** — candidate_engine.py:371-373
- post: returns False only when the value (default `"1"`) is one of `("0", "false", "no", "off")`.

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read / tables_written empty; "no Qdrant, no Postgres here" — candidate_engine.py:16).
- Threads: per-turn `ThreadPoolExecutor` pools — candidate_engine.py:525, 765 (FACTS.nondeterminism).
- env flags read (name = default):
  - `POLYMATH_CHAT_FACET_DIVERSITY` = `'1'` — candidate_engine.py:372
  - `POLYMATH_CHAT_LATENT_FUSION` = `'0'` — candidate_engine.py:1256
  - `POLYMATH_FUSION_PRESERVE_TOP_N` = `'5'` — candidate_engine.py:1960
- env names referenced in comments (read by callers, defaults not in this file): `POLYMATH_CHAT_HIERARCHY_ROUTE_DOCUMENTS` (candidate_engine.py:137), `POLYMATH_CHAT_MAX_SUBQUERIES` (candidate_engine.py:187), `POLYMATH_CHAT_SKELETON_ROUTES` / `POLYMATH_CHAT_CONTEXTUAL_JUDGE` (candidate_engine.py:208-209), `POLYMATH_CHAT_SKELETON_PROBES` (candidate_engine.py:219), `POLYMATH_CHAT_PROBE_GATE` (candidate_engine.py:229), `POLYMATH_CHAT_WILDCARD_DEADLINE_S` (candidate_engine.py:288), `POLYMATH_CHAT_DUALREAD_ENABLED` (candidate_engine.py:309), `POLYMATH_CHAT_SYNTHESIS_MAX` (candidate_engine.py:365).

## invariants
INVARIANT: `rerank_max` (24) < `rerank_max_fair` (32) — candidate_engine.py:159,173 [DERIVED]
  fails-if: fair round-robin path judges more pairs than the rerank budget admits; 24→28 seats cost +1.7 s p50 under contention (comment candidate_engine.py:154-158, 169-173).
INVARIANT: `lane_deadline_s` (3.0) < `rerank_deadline_s` (8.0) — candidate_engine.py:277,282 [DERIVED]
  fails-if: judge timed out on 30/30 turns at 3.0 s (reranker floor ~240 ms/pair ⇒ 5.8 s for 24 pairs), silently turning composition into fusion order — candidate_engine.py:278-281.
INVARIANT: `max_subqueries` (10) ⇒ 1 primary + 10 subqueries ≤ 32 texts = one embedder round trip — candidate_engine.py:184-188 [INFERRED: comment states the embedder batches ≤ 32 texts per call].
INVARIANT: default `facet_seats` = 0, `compose_doc_lane_max` = 0, `mmr_lambda` = 0.0 ⇒ bare `CandidateBudget()` composes byte-identically — candidate_engine.py:249-253,260-262 [DERIVED]
  fails-if: flipping any default changes composition output for every mode.
INVARIANT: `LANES = (LANE_A, LANE_B, LANE_C)`; fusion and collection by lane NAME in fixed order, never completion order — candidate_engine.py:103,34-35 [DERIVED]
  fails-if: union would depend on thread completion order.
INVARIANT: `_DIRECT_LANES` = {A, B, C}; `_LATENT_LANES` = {D, E, G}; DIRECT outranks every other role — candidate_engine.py:108-110,117-126 [DERIVED]
  fails-if: LATENT evidence substitutes for DIRECT, violating §47 — candidate_engine.py:106-107.
INVARIANT: `FACET_DIVERSITY_PROFILE` `synthesis_max` (24) == default `rerank_max` (24) — candidate_engine.py:367,159 [DERIVED]
  fails-if: synthesis set larger than the judged prefix seats unjudged candidates; smaller wastes judged seats.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` at candidate_engine.py:661,663,682,686,692,694,705,762,828,886,891,948,971,980,1010,1018,1030,1039,1080,1089,1105,1114,1144,1151,1154,1178,1191,1266,1351,1352,2066,2093,2148; concurrency `ThreadPoolExecutor` at candidate_engine.py:525,765). Wall-clock deadlines make lane survival load-dependent; with no deadline hit output is byte-identical to sequential — candidate_engine.py:34-36.
idempotency: SAFE (pure over injected callables; no tables, files or collections written — candidate_engine.py:16-20, FACTS.tables_written empty).

## failure behaviour
- Lane exception in `_run_route_lanes` → SWALLOWED: returns `([], {'enabled': True, 'degraded': ...})` — lane lost with degraded receipt, other lanes continue — candidate_engine.py:521; sparse unavailability is DEGRADED, dense lanes continue — candidate_engine.py:23-25.
- `_latent_fused_union` exception → SWALLOWED: return `fallback` — candidate_engine.py:1979.
- `_judge_or_none` exception → SWALLOWED: return `None`; "never raises" — candidate_engine.py:2042-2046.
- `_gather` exception → handled: assign — candidate_engine.py:693.
- Handled-assign / continue inside `_retrieve_on` and helpers at candidate_engine.py:849, 958, 997, 1027, 1077, 1102, 1129, 1141, 1187, 1473 — lane-level failures recorded, turn continues.
- Rerank past deadline → turn proceeds in fusion order, receipted `rerank_timeout` — candidate_engine.py:273-274.
- Wildcard finish budget missed → top unvalidated parents ship as UNVERIFIED bridges, labelled and receipted — candidate_engine.py:290-294.
- Primary all below `aspect_weak_floor` (0.5) → q0 flagged `below_floor` — candidate_engine.py:203-207.

## dumb-code flags
- Comments name "lane H" (graph destination) and "lane I" (GNN) but no `LANE_H` / `LANE_I` constants exist — only `ARRIVAL_GRAPH_DEST` / `ARRIVAL_GNN_ROUTE` — candidate_engine.py:343,348 vs candidate_engine.py:93,95 [DERIVED].
- `hierarchy_doc_k: int = 16` retained while `hierarchy_route_documents: bool = False` (document-summary search off unless `POLYMATH_CHAT_HIERARCHY_ROUTE_DOCUMENTS=1`) — candidate_engine.py:133,135-140 [DERIVED].
- Evaluator-only causal-control arms `"real | nograph | shuffled"` live in the production budget as `gnn_variant: str = "real"` — candidate_engine.py:354-355 [DERIVED].
- `_MMR_STOP` hard-codes a stopword list — candidate_engine.py:1619 [DERIVED].
- Deadline drift documented in-place: §3.16 starting `rerank_deadline_s` 3.0 s vs shipped default 8.0 s — candidate_engine.py:278-282 [DERIVED].
- The "union byte-identical" guarantee is repeated across ≥6 knob comments — candidate_engine.py:137-140,305-309,321-323,325-327,332-333,345-349 [DERIVED].

## refactor notes
- `orchestrator/orchestrator/api/chat_retrieval.py` imports this module — signature changes to `retrieve_candidates`, `CandidateBudget` or `select_evidence` hit it directly (FACTS.importers).
- Latent knob names mirror v1 `HybridRetrievalPlan` names so `latent_rescue_parents` reads them unchanged — renaming `latent_*` breaks that reader — candidate_engine.py:297-299.
- Default-off additive lanes (`latent_enabled`, `dualread_enabled`, `resolution_lift_enabled`, `seealso_fanout_enabled`, `seealso_blend_enabled`, `graph_dest_enabled`, `gnn_enabled` all `False`) are the byte-identical guarantee; flipping any default changes output for every mode — candidate_engine.py:299,310,323,327,333,346,350.
- `FACET_DIVERSITY_PROFILE` is applied by chat_retrieval's `default_budget`, then env knobs override single values afterwards — changing the dict changes all modes with the flag on — candidate_engine.py:363-368.
- Receipt strings (`<lane>_timeout`, `rerank_timeout`, `embed_deadline`, `wildcard_timeout:finish`, `below_floor`), `SYNTHESIS_ROLES`, lane names and arrival tags are external vocabulary consumed downstream — candidate_engine.py:32-34,203-205,273-274,291,68-110.

## VERIFY
```verify
grep -Fq 'CANDIDATE_ENGINE_VERSION = "candidate-retrieval-v1"' shared/polymath_shared/candidate_engine.py
grep -Fq 'rerank_deadline_s: float = 8.0' shared/polymath_shared/candidate_engine.py
grep -Fq 'SYNTHESIS_ROLES = ("DIRECT", "PRECISION", "RELATIONAL", "LATENT")' shared/polymath_shared/candidate_engine.py
grep -Fq 'FACET_DIVERSITY_FLAG = "POLYMATH_CHAT_FACET_DIVERSITY"' shared/polymath_shared/candidate_engine.py
! grep -Fq 'LANE_H =' shared/polymath_shared/candidate_engine.py
test "$(grep -c -F 'time.perf_counter' shared/polymath_shared/candidate_engine.py)" -ge 20
```
