# unit: shared/polymath_shared/hybrid.py
anchor: shared/polymath_shared/hybrid.py:1-553

## purpose
HYBRID retrieval on top of the shared FAST engine (`pass1`): reuses pass1's neural lanes unchanged, adds an independent global lexical child lane, four-lane RRF document aggregation, optional document-level MMR, `LEXICAL_RESCUE`/`LATENT_RESCUE` arrivals, and its own G3 cross-encoder stage — shared/polymath_shared/hybrid.py:1-21 [DERIVED]. Consumed by the orchestrator API (`graph.py`, `hybrid.py`) — FACTS.importers.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| HybridRetrievalPlan | class (frozen dataclass) | ~40 config fields -> versioned plan | shared/polymath_shared/hybrid.py:51-112 | — |
| HYBRID_PLAN_VERSION | constant | `"hybrid-retrieval-v1"` | shared/polymath_shared/hybrid.py:42 | — |
| ARRIVAL_LEXICAL_RESCUE | constant | `"LEXICAL_RESCUE"` | shared/polymath_shared/hybrid.py:44 | — |
| HYBRID_DEFAULT_PLAN | constant | `HybridRetrievalPlan()` | shared/polymath_shared/hybrid.py:115 | — |
| MMR_LAMBDA_GRID | constant | `(1.0, 0.9, 0.8, 0.7)` | shared/polymath_shared/hybrid.py:117 | — |
| _cosine | def (private) | `(a: list[float], b: list[float]) -> float` | shared/polymath_shared/hybrid.py:120-124 | — |
| mmr_select | def | `(candidates, *, relevance, vectors, lambda_, max_documents) -> list` | shared/polymath_shared/hybrid.py:127-160 | — |
| HybridResult | class (dataclass) | 10 fields (query, plan, result, documents, lexical_lane, mmr_applied, selected_documents, selected_sections, final_evidence, trace) | shared/polymath_shared/hybrid.py:163-174 | — |
| hybrid_retrieve | def | `(query, *, plan=HYBRID_DEFAULT_PLAN, embed_query, routing_search, lexical_search, rerank_children=None, summary_vectors=None, neighbor_lookup=None, region_lookup=None, latent_rescue=None) -> HybridResult` | shared/polymath_shared/hybrid.py:177-552 | orchestrator/orchestrator/api/graph.py, orchestrator/orchestrator/api/hybrid.py, shared/polymath_shared/_small-modules-3 (unit-level; per-symbol split unknown) |

## contracts
hybrid_retrieve — shared/polymath_shared/hybrid.py:177-552
- in: `query: str`; required callables `embed_query`, `routing_search`, `lexical_search`; optional `rerank_children`, `summary_vectors`, `neighbor_lookup`, `region_lookup`, `latent_rescue` — shared/polymath_shared/hybrid.py:177-188 [DERIVED]
- pre: lexical lane runs only if `plan.lexical_enabled and lexical_search is not None` — shared/polymath_shared/hybrid.py:228 [DERIVED]; MMR only if `plan.mmr_enabled and summary_vectors is not None and documents` — shared/polymath_shared/hybrid.py:244 [DERIVED]; latent lane only if `plan.latent_enabled and latent_rescue is not None` — shared/polymath_shared/hybrid.py:304 [DERIVED]; G3 only if `plan.rerank_enabled and rerank_children is not None and deduped` — shared/polymath_shared/hybrid.py:445 [DERIVED]
- out: `HybridResult`; `final_evidence` capped at `plan.final_max_total_items` — shared/polymath_shared/hybrid.py:470-483 [DERIVED]; trace keys `latent, evidence_utility, plan, rrf_k, mmr_enabled, mmr_lambda, lane_sizes, document_candidates, pre_g3_order, post_g3_order, funnel_lanes, funnel_union, g3_scores, rescue_seated, neighbors_added` — shared/polymath_shared/hybrid.py:506-539 [DERIVED]
- post: `deduped` chunk_ids unique — shared/polymath_shared/hybrid.py:374-380 [DERIVED]; rerank must not change the candidate set (assert) — shared/polymath_shared/hybrid.py:448 [DERIVED]

mmr_select — shared/polymath_shared/hybrid.py:127-160
- in: candidates list; keyword-only `relevance: dict[str, float]`, `vectors: dict[str, list[float]]`, `lambda_: float`, `max_documents: int` — shared/polymath_shared/hybrid.py:127-134 [DERIVED]
- out: selected list with `len(selected) < max_documents` loop bound — shared/polymath_shared/hybrid.py:141 [DERIVED]
- post: `score = lambda_ * rel - (1.0 - lambda_) * red` — shared/polymath_shared/hybrid.py:151 [DERIVED]; deterministic ties by `doc_id` (initial sort `(-relevance, doc_id)`, then `cand.doc_id < best.doc_id`) — shared/polymath_shared/hybrid.py:139,152-153 [DERIVED]

## effect surface
- Postgres: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant: search only via injected `routing_search`; latent path resolves collection as `qdrant_collection_name(_corpus, NEURAL_EMBED_CONTRACT.contract_id)` — shared/polymath_shared/hybrid.py:307-313 [DERIVED] — and filters payload `{"representation_kind": "routing_child", "corpus_id": ..., "parent_id": ...}` — shared/polymath_shared/hybrid.py:329-333 [DERIVED].
- Embeddings via injected `embed_query`; latent path reuses `getattr(fast, "qvec", None) or embed_query(query)` — shared/polymath_shared/hybrid.py:314-316 [DERIVED].
- Files, subprocesses, env flags: none read in this unit.
- All external behavior flows through the 8 injected callables — shared/polymath_shared/hybrid.py:181-188 [DERIVED].

## invariants
INVARIANT: `len(final_evidence) <= plan.final_max_total_items` (default 12) — shared/polymath_shared/hybrid.py:474,479,81 [DERIVED]
  fails-if: evidence budget overrun; downstream gets more items than the plan promises.
INVARIANT: `set(post_g3) == set(pre_g3)` — shared/polymath_shared/hybrid.py:448 [DERIVED]
  fails-if: AssertionError `"G3 changed the candidate set"`.
INVARIANT: MMR pool is `documents[: plan.max_documents * 3]` for both `summary_vectors` and `mmr_select` — shared/polymath_shared/hybrid.py:248,251 [DERIVED]
  fails-if: key mismatch → `vectors.get(...)` returns `[]` → cosine falls to `0.0` — shared/polymath_shared/hybrid.py:124,147.
INVARIANT: lexical hits enter sections only when their doc is in `selected_documents` — shared/polymath_shared/hybrid.py:263-266 [DERIVED]
  fails-if: lexical lane bypasses document selection / hierarchy provenance.
INVARIANT: latent children admitted only under latent-nominated `parent_id`, skipping ids already in `deepened`/`rescue_neural`/`rescue_lexical`/`rescue_latent` — shared/polymath_shared/hybrid.py:329-341 [DERIVED]
  fails-if: latent lane injects candidates outside hierarchy provenance.
INVARIANT: rescue lanes appended after all deepened children; final cut reserves `rescue_reserved_slots` (+`latent_reserved_slots` when latent active) — shared/polymath_shared/hybrid.py:357-372,421-440 [DERIVED]
  fails-if: flat cut deletes recall lanes (stated at shared/polymath_shared/hybrid.py:408-410).
INVARIANT: defaults `latent_enabled=False`, `evidence_utility_enabled=False`, `neighbor_expansion=0` keep `hybrid-retrieval-v1` byte-identical — shared/polymath_shared/hybrid.py:83-85,97-104,109 [DERIVED]
  fails-if: changed defaults break the frozen-behavior claim.

## determinism & idempotency
determinism: NONDETERMINISTIC (results of injected `embed_query`/`routing_search`/`lexical_search`/`rerank_children`/`latent_rescue`, and `lr.latency_ms` recorded into `trace.latent.latency_ms` — shared/polymath_shared/hybrid.py:325; all internal sorts have fixed keys with `doc_id` tie-breaks — shared/polymath_shared/hybrid.py:139,152-153,276-278)
idempotency: SAFE (pure composition over callbacks; no writes — FACTS `tables_written: []`, no file/subprocess effects)

## failure behaviour
- `except Exception` at shared/polymath_shared/hybrid.py:334: latent deepening failure swallowed → `latent_trace["degraded"] = "deepen_failed"`, `rows = []`; caller sees only the trace flag — shared/polymath_shared/hybrid.py:334-336 [DERIVED].
- `except Exception` at shared/polymath_shared/hybrid.py:399: `region_lookup` failure swallowed → `_roles = {}` → demotion silently skipped, noisy regions keep rank — shared/polymath_shared/hybrid.py:399-406 [DERIVED].
- `assert set(post_g3) == set(pre_g3), "G3 changed the candidate set"` — only explicit raise; propagates — shared/polymath_shared/hybrid.py:448 [DERIVED].
- Latent lane documented fail-open, "absence invisible (§0b)" — shared/polymath_shared/hybrid.py:299-301 [DERIVED].
- Empty collection name `""` documented to 404 in the searcher; that is why the collection is resolved — shared/polymath_shared/hybrid.py:305-306,313 [DERIVED].

## dumb-code flags
- Magic fallback rank `10**9` in four sort keys — shared/polymath_shared/hybrid.py:360,367,369,371 [DERIVED].
- `mmr_applied=plan.mmr_enabled` reports the flag even when MMR was skipped (`summary_vectors is None` or no documents) — shared/polymath_shared/hybrid.py:244 vs 547 [DERIVED]; same conflation in `trace["mmr_enabled"]` — shared/polymath_shared/hybrid.py:511.
- Two different empty-corpus sentinels for the same tuple: `(plan.corpus_ids or ("",))[0]` vs `(plan.corpus_ids or (None,))[0]` — shared/polymath_shared/hybrid.py:311,326 [DERIVED].
- One concept, three spellings: `ARRIVAL_LEXICAL_RESCUE = "LEXICAL_RESCUE"` — shared/polymath_shared/hybrid.py:44 — vs section marker `"from": ["lexical_rescue"]` — shared/polymath_shared/hybrid.py:274 — vs funnel lane key `"global_sparse_child"` — shared/polymath_shared/hybrid.py:386 [DERIVED].
- Literal `"LATENT_RESCUE"` at shared/polymath_shared/hybrid.py:492-493 duplicates the imported `ARRIVAL_LATENT_RESCUE` — shared/polymath_shared/hybrid.py:48 [INFERRED: same concept; constant value not visible in this unit].
- `MMR_LAMBDA_GRID` defined, never referenced elsewhere in this file — shared/polymath_shared/hybrid.py:117 [INFERRED: no other occurrence in SOURCE].
- `trace.rescue_seated` counts only `ARRIVAL_GLOBAL_CHILD_RESCUE`/`ARRIVAL_LEXICAL_RESCUE`, excluding latent arrivals while `children_admitted` counts them separately — shared/polymath_shared/hybrid.py:534-537,503 [DERIVED].
- `rrf_k: int = 60` duplicated as docstring claim "RRF over FOUR rankings (k=60)" — shared/polymath_shared/hybrid.py:8,67 [DERIVED].

## refactor notes
- Unit imported by orchestrator/orchestrator/api/graph.py, orchestrator/orchestrator/api/hybrid.py, shared/polymath_shared/_small-modules-3 — FACTS.importers; signature/plan-field changes hit all three.
- Keep `from polymath_shared.latent.rescue import ARRIVAL_LATENT_RESCUE` at module level: a function-local import shadowed the name for the whole scope and caused the `graph.py` `_embed_query` failure class, "measured twice" — shared/polymath_shared/hybrid.py:45-48 [DERIVED].
- Any `rerank_children` implementation must preserve the candidate set — enforced by assert at shared/polymath_shared/hybrid.py:448.
- `summary_vectors` is called with at most `plan.max_documents * 3` doc_ids and must return `dict[doc_id -> vector]` — shared/polymath_shared/hybrid.py:246-253 [DERIVED].
- Trace keys `funnel_lanes`/`funnel_union` (RETRIEVAL-FUNNEL-V1 receipt) and `latent.*` diagnostics (P6 metric raw material) are consumed downstream; renaming breaks receipts — shared/polymath_shared/hybrid.py:381-389,485-505 [DERIVED].
- Flipping `latent_enabled`, `evidence_utility_enabled`, or `neighbor_expansion` defaults is a plan-version change, not a patch — shared/polymath_shared/hybrid.py:83-85,97-109 [DERIVED].

## VERIFY
```verify
grep -Fq 'HYBRID_PLAN_VERSION = "hybrid-retrieval-v1"' shared/polymath_shared/hybrid.py
grep -Fq 'assert set(post_g3) == set(pre_g3), "G3 changed the candidate set"' shared/polymath_shared/hybrid.py
grep -Fq 'latent_enabled: bool = False' shared/polymath_shared/hybrid.py
grep -Fq 'MMR_LAMBDA_GRID = (1.0, 0.9, 0.8, 0.7)' shared/polymath_shared/hybrid.py
grep -Fq 'latent_trace["degraded"] = "deepen_failed"' shared/polymath_shared/hybrid.py
grep -Fq 'mmr_applied=plan.mmr_enabled' shared/polymath_shared/hybrid.py
test "$(grep -c -F '10**9' shared/polymath_shared/hybrid.py)" -ge 4
```
