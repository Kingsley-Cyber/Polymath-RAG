# unit: shared/polymath_shared/pass1.py
anchor: shared/polymath_shared/pass1.py:1-716

## purpose
R1B Pass-1 summary-led retrieval engine: "SUMMARIES ROUTE / CHILDREN PROVE / GLOBAL CHILD SEARCH PROTECTS RECALL" (shared/polymath_shared/pass1.py:241-244). Runs three/four neural lane searches over the routing projection, RRF-fuses them into documents, descends document → section → child, unions a global-child rescue lane, and returns bounded hierarchical evidence plus a full diagnostic trace (shared/polymath_shared/pass1.py:246-261). Consumed by the Fast and Hybrid retrieval layers (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Pass1RetrievalPlan` | class (frozen dataclass) | fields -> plan instance; `plan_version: str = PLAN_VERSION` | shared/polymath_shared/pass1.py:54-129 | module importers (see refactor notes) |
| `LaneHit` | class (dataclass) | 11 fields (representation_kind, rank, raw_similarity, corpus_id, doc_id, parent_id, chunk_id, summary_id, source_name, text) | shared/polymath_shared/pass1.py:135-146 | internal + trace consumers |
| `DocumentCandidate` | class (dataclass) | doc_id, corpus_id, per-lane hit lists, `rrf_contributions`, ranks; property `representation_kinds_present` | shared/polymath_shared/pass1.py:149-179 | internal |
| `Pass1Result` | class (dataclass) | query, plan, 3 lanes, documents, selected_documents, selected_sections, deepened_children, rescue_children, final_evidence, trace, `qvec: list[float] = None` | shared/polymath_shared/pass1.py:182-198 | Fast/Hybrid callers |
| `aggregate_documents` | def | (doc_lane, section_lane, child_lane, k) -> list[DocumentCandidate] | shared/polymath_shared/pass1.py:205-220 | FAST lane (R1D frozen signature) |
| `aggregate_documents_n` | def | (lanes: list[tuple[str, list[LaneHit]]], k) -> list[DocumentCandidate] | shared/polymath_shared/pass1.py:223-269 | hybrid.py path |
| `resolve_sections` | def | (selected_docs, max_sections_per_document) -> list[dict] | shared/polymath_shared/pass1.py:272-308 | internal |
| `_truncate_reserving_rescue` | def | (candidates, limit, reserved, rescue_arrivals=(ARRIVAL_GLOBAL_CHILD_RESCUE,)) -> list[dict] | shared/polymath_shared/pass1.py:311-341 | internal + future seed lanes |
| `_expand_neighbors` | def | (candidates, plan, neighbor_lookup) -> (list[dict], int) | shared/polymath_shared/pass1.py:344-382 | internal |
| `pass1_retrieve` | def | (query, *, plan, embed_query, routing_search, rerank_children?, neighbor_lookup?, region_lookup?) -> Pass1Result | shared/polymath_shared/pass1.py:385-716 | orchestrator/api/fast.py, orchestrator/api/hybrid.py |

Module importers (FACTS.importers): `orchestrator/orchestrator/api/fast.py`, `orchestrator/orchestrator/api/hybrid.py`, `shared/polymath_shared/candidate_engine.py`, `shared/polymath_shared/compiler_context.py`, `shared/polymath_shared/hybrid.py`, `shared/polymath_shared/reach.py`, `shared/polymath_shared/_small-modules-3`.

## contracts

**`pass1_retrieve` (shared/polymath_shared/pass1.py:385-716)**
- in: `query: str`; `plan: Pass1RetrievalPlan = PASS1_DEFAULT_PLAN`; `embed_query: Callable[[str], list[float]]`; `routing_search: Callable[[str, list[float], dict], list[dict]]`; optional `rerank_children`, `neighbor_lookup`, `region_lookup` (386-393).
- pre: `routing_search(collection, vector, filters)` returns `[{payload, score}]` sorted by score desc; filters keyed `representation_kind`, `corpus_id`, optional `doc_id`/`parent_id` (395-397).
- in (collections): one per `plan.corpus_ids` entry via `qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id)`; empty corpus_ids → `[(None, None)]`, caller resolves cross-corpus (405-413).
- out: `Pass1Result`; `final_evidence` capped at `plan.final_max_total_items` (15 default), assembled per winning document first, leftovers after (638-652).
- post: G3 rerank is order-only — `assert set(post_g3) == set(pre_g3), "G3 changed the candidate set"` (619-626); neighbor expansion runs after G3 (630-634).
- post: `trace` carries `plan`, `rrf_k`, `lane_sizes`, `document_candidates`, `pre_g3_order`/`post_g3_order`, `funnel_lanes`/`funnel_union`, `rescue_seated`/`rescue_candidates`, `neighbors_added`, `noisy_candidates`/`noisy_demoted` (654-700).

**`aggregate_documents_n` (shared/polymath_shared/pass1.py:223-269)**
- in: `lanes: list[tuple[str, list[LaneHit]]]`, `k: int`.
- out: candidates sorted `key=lambda c: (-c.aggregate_score, c.doc_id)` (266); `aggregate_score = sum(cand.rrf_contributions.values())` (257).
- pre: each lane's hits already ranked (rank assigned by caller's `search`, 476-478).
- post: RRF contribution counted once per (lane, doc) via `seen` set (244-253); `_rrf_score(rank, k) = 1.0 / (k + rank + 1)` (201-202).

**`resolve_sections` (shared/polymath_shared/pass1.py:272-308)**
- in: winning docs, `max_sections_per_document`.
- out: per doc, sections ordered `(best_section_rank, parent_id)`, cut to `[:max_sections_per_document]` (303-306); sources tagged `"from": ["section_summary"]` and/or `"child_rescue"` (287, 299, 302).

**`_truncate_reserving_rescue` (shared/polymath_shared/pass1.py:311-341)**
- post: with `reserved=0`, no rescue present, or everything fitting, result identical to `candidates[:limit]` (327-335); order otherwise preserved, only membership changes (325-329); `seats = min(reserved, len(rescue), limit)` (336).

**`_expand_neighbors` (shared/polymath_shared/pass1.py:344-382)**
- out: `(candidates + added, len(added))`; neighbours APPENDED, never displace a ranked candidate (349-351); capped at `plan.neighbor_expansion_max` (380-381); added items get `"similarity": None`, `"arrival": ARRIVAL_NEIGHBOR_EXPANSION` (370-379).

## effect surface
- Qdrant (read-only, through injected `routing_search`): collections named `qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id)` per corpus (405-411); no direct client in this unit.
- Postgres: none — `tables_read`/`tables_written` empty (FACTS).
- Network/model/external: only via injected `embed_query`, `routing_search`, `rerank_children`, `neighbor_lookup`, `region_lookup` (389-393).
- Files / subprocess / env flags: none visible.
- Deferred imports: `polymath_shared.embedding_contracts.NEURAL_EMBED_CONTRACT`, `polymath_shared.projection_contracts.qdrant_collection_name` (402-403); `polymath_shared.document_region.is_noisy` at two call sites (472, 590).

## invariants

INVARIANT: `final_max_children` (12) <= `final_max_total_items` (15) — shared/polymath_shared/pass1.py:86-87 [DERIVED]
  fails-if: the child-level cut no longer nests inside the item-level cut; rescue/neighbor children could evict per-document hierarchy assembly.
INVARIANT: `rescue_reserved_slots` (2) < `final_max_children` (12); seats = `min(reserved, len(rescue), limit)` — shared/polymath_shared/pass1.py:86,102,336 [DERIVED]
  fails-if: reserved >= limit starves hierarchy seats to zero.
INVARIANT: first-rank RRF contribution = 1/(60+0+1) = 1/61 under default `rrf_k = 60` — shared/polymath_shared/pass1.py:77,201-202 [DERIVED]
  fails-if: changing the `+1` rank base or `rrf_k` silently re-orders document fusion.
INVARIANT: entity-card pool <= `entity_card_top_k` (8) cards; each card votes for <= `entity_card_max_docs_per_card` (4) docs — shared/polymath_shared/pass1.py:74-75,433-438 [DERIVED]
  fails-if: vote expansion leaks into the card pool and floods fusion.
INVARIANT: G3 preserves the candidate set — `assert set(post_g3) == set(pre_g3)` — shared/polymath_shared/pass1.py:622 [DERIVED]
  fails-if: AssertionError aborts the whole query.
INVARIANT: `neighbor_expansion` default 0; added neighbours <= `neighbor_expansion_max` (8), appended after G3 — shared/polymath_shared/pass1.py:114-115,349-351,630-634,380-381 [DERIVED]
  fails-if: default-on expansion changes the frozen plan for ordinary questions.
INVARIANT: noisy-region handling is reorder-only ("DEMOTION, never deletion") — shared/polymath_shared/pass1.py:362-364,596-597 [DERIVED]
  fails-if: dropping chunks removes the recall floor where boilerplate is all that exists.
INVARIANT: RRF counts one contribution per (lane, doc) via the `seen` set — shared/polymath_shared/pass1.py:244-253 [DERIVED]
  fails-if: duplicate hits from multi-collection search double-count votes.

## determinism & idempotency
determinism: DETERMINISTIC (modulo injected `embed_query`/`routing_search`/`rerank_children` — model/db/network, shared/polymath_shared/pass1.py:389-392). All internal sorts have ID tiebreaks: hits `(-raw_similarity, doc_id, parent_id)` (460), candidates `(-aggregate_score, doc_id)` (266), sections `(best_section_rank, parent_id)` (303-305); docstring promises identical output for identical (query, plan, corpus state, pinned models) (258-260).
idempotency: SAFE (pure computation over injected callbacks; no table writes per FACTS, no state mutated outside the returned `Pass1Result`).

## failure behaviour

| site | handler | behaviour | caller sees |
|---|---|---|---|
| shared/polymath_shared/pass1.py:360-362 | `except Exception` in `_expand_neighbors` | SWALLOWED: `return (candidates, 0)` | query proceeds without neighbours; `trace["neighbors_added"] == 0` |
| shared/polymath_shared/pass1.py:468-470 | `except Exception` around lane-level `region_lookup` | handled: assign `roles = {}` | child-lane demotion silently skipped |
| shared/polymath_shared/pass1.py:586-588 | `except Exception` around global `region_lookup` | handled: assign `_roles = {}` | global demotion silently skipped |
| shared/polymath_shared/pass1.py:622 | G3 assert | raised, not swallowed | `AssertionError("G3 changed the candidate set")` propagates |

## dumb-code flags
- Stale v1 comment: "`max_documents × max_sections_per_document × max_children_per_section = 30 by default`" and "cut to `final_max_children` = 10" vs v2 defaults 5×3×3 = 45 and `final_max_children: int = 12` — shared/polymath_shared/pass1.py:91-93 vs 79-81,86 [DERIVED]
- Stale "~30 candidates compete for final_max_children slots" vs 45 under v2 defaults — shared/polymath_shared/pass1.py:578 vs 79-81 [DERIVED]
- `qvec: list[float] = None` — annotation excludes the actual `None` default — shared/polymath_shared/pass1.py:198 [DERIVED]
- `is_noisy` imported at two call sites instead of module top — shared/polymath_shared/pass1.py:472,590 [DERIVED]
- Lane demotion runs after a per-collection `[:top_k]` pre-cut (rows truncated at 425 before demotion at 465-475), so it can only reorder within already-fetched rows even though the comment claims "BEFORE the top_k cut" — shared/polymath_shared/pass1.py:425,461-464 [INFERRED: both cuts visible; comment addresses only the second cut at 478]
- Entity-card search requests `entity_card_top_k * entity_card_max_docs_per_card` (8×4=32) rows then discards cards at `i >= plan.entity_card_top_k` — shared/polymath_shared/pass1.py:433-434,495-496 [DERIVED]

## refactor notes
- Plan defaults are a versioned contract (`PLAN_VERSION = "pass1-retrieval-v2"` at 38, recorded in `trace["plan"]` at 695); changing any default (e.g. `final_max_children`, `neighbor_expansion`) changes frozen-plan behavior across all seven FACTS.importers, including both Fast and Hybrid API layers.
- `aggregate_documents` three-lane signature is frozen for FAST (R1D); Hybrid must use `aggregate_documents_n` with the lexical lane — shared/polymath_shared/pass1.py:213-214.
- `rescue_arrivals` default `(ARRIVAL_GLOBAL_CHILD_RESCUE,)` must stay byte-identical; future additive seed lanes plug in there instead of forking — shared/polymath_shared/pass1.py:319-329.
- Trace keys are receipts consumed downstream: `funnel_lanes`/`funnel_union` (RETRIEVAL-FUNNEL-V1) and `rescue_seated`/`rescue_candidates` for lane liveness — shared/polymath_shared/pass1.py:677-693. Renaming breaks diagnostics.
- `qvec` must remain the single embedded query vector (SINGLE-EMBED-V1); downstream latent-rescue lanes reuse it instead of re-embedding — shared/polymath_shared/pass1.py:196-198.
- External coupling outside this file: depth profile turns `neighbor_expansion` on via `query_shape.enumeration_plan`; document-metadata queries disable demotion via `query_shape.is_document_metadata_query` — shared/polymath_shared/pass1.py:111-113,124-125.
- `rerank_children` implementations must satisfy the order-only G3 contract (set equality asserted at 622).

## VERIFY
```verify
grep -Fq 'PLAN_VERSION = "pass1-retrieval-v2"' shared/polymath_shared/pass1.py
grep -Fq 'final_max_children: int = 12' shared/polymath_shared/pass1.py
grep -Fq 'rescue_reserved_slots: int = 2' shared/polymath_shared/pass1.py
grep -Fq 'neighbor_expansion: int = 0' shared/polymath_shared/pass1.py
grep -Fq 'return 1.0 / (k + rank + 1)' shared/polymath_shared/pass1.py
grep -Fq 'assert set(post_g3) == set(pre_g3), "G3 changed the candidate set"' shared/polymath_shared/pass1.py
test "$(grep -c -F 'from polymath_shared.document_region import is_noisy' shared/polymath_shared/pass1.py)" -ge 2
```
