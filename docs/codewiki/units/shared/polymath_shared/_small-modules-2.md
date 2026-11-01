# unit: shared/polymath_shared/_small-modules-2
anchor: shared/polymath_shared/latent_portfolio.py:1-133

## purpose
Bundle of small shared library modules for Polymath: WLK2C latent evidence grading/seating (C4/C5), layout evidence, structured JSON logging, Neo4j eligibility SQL, principal propagation, probe gating, evidence-yield receipts, projection identity/lifecycle/reconcile/want contracts, query routing/shape, referential spans, resolution lift, and retrieval modes. Shared by control/, orchestrator/, workers/, sidecars/ (unit-level FACTS.importers).

## public surface
"used by" = direct consumer when FACTS show one; otherwise any unit importer (control/, orchestrator/, workers/, sidecars/, FACTS.importers).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| seat_portfolio | def | candidates, capacity, direct_per_rep_cap=3, max_divergent=2, min_adequate_direct=1, complementary_cap=None, establishes_need=True, has_direct_grounding=None -> (seated, trace) | latent_portfolio.py:47-132 | latent_selection.py:20-24 |
| grade_and_seat_latent | def | q0_text, pool, bridges, rerank, capacity, floor, bridge_valid_floor, divergent_local_floor, direct_per_rep_cap, max_divergent, min_adequate_direct, complementary_cap, establishes_need, has_direct_grounding -> (seated, trace) | latent_selection.py:44-96 | — |
| project_regions | def | regions, doc_start, doc_end, chunk_start -> list[(int,int)] | layout_evidence.py:33-55 | — |
| heading_regions | def | text -> list[(start,end)] | layout_evidence.py:58-78 | — |
| in_heading | def | regions, start, end -> bool | layout_evidence.py:81-83 | — |
| independently_capitalized | def | token_text -> bool | layout_evidence.py:86-102 | — |
| JsonFormatter | class | __init__(service), format(record) -> str | logging.py:24-40 | — |
| configure_logging | def | service, level -> — | logging.py:43-48 | — |
| with_context | def | logger -> — | logging.py:51-55 | — |
| entity_eligible_sql | def | alias -> SQL predicate | neo4j_eligibility.py:44-46 | — |
| fact_eligible_sql | def | f_alias -> SQL predicate | neo4j_eligibility.py:49-59 | — |
| fact_eligible_from_row | def | subject_class, object_class, decision -> bool | neo4j_eligibility.py:62-65 | — |
| fact_eligible_from_classes | def | subject_class, object_class -> bool | neo4j_eligibility.py:68-73 | — |
| eligible_fact_ids_sql | def | () -> SQL (corpus-independent) | neo4j_eligibility.py:76-79 | — |
| ineligible_fact_ids_sql | def | () -> SQL | neo4j_eligibility.py:82-86 | — |
| current | def | () -> principal or None | principal_context.py:23-25 | — |
| acting_as | def | principal_id -> — | principal_context.py:29-37 | — |
| parse | def | value -> — | principal_context.py:40-45 | — |
| PrincipalContextMiddleware | class | __init__, __call__ (pure ASGI) | principal_context.py:48-71 | — |
| gate_probes | def | question, probes, rerank, floor, timeout_s, gated_origins -> (ids-to-drop, receipt) | probe_gate.py:34-73 | — |
| selected_evidence_query_ids | def | evidence_items -> set of subquery ids | profile_yield.py:35-41 | — |
| evidence_provenance | def | evidence_items -> normalized provenance | profile_yield.py:44-55 | — |
| evidence_yield_by_origin | def | subqueries, evidence_items -> per-origin breakdown | profile_yield.py:58-68 | — |
| profile_expansion_evidence_yield | def | subqueries, evidence_items -> metric | profile_yield.py:71-86 | — |
| librarian_receipt | def | plan, evidence_items, scout, resolution, mode, lanes, q0 -> receipt | profile_yield.py:89-105 | — |
| projection_id | def | projection, entity_kind, source_id, contract_version -> id | projection_contracts.py:59-66 | — |
| receipt_hash | def | projection, entity_kind, source_id, contract_version -> hash | projection_contracts.py:69-71 | — |
| entity_card_id | def | entity_id, corpus_id -> card id (ROUTING-ENTITY-CARDS-V1 §11 L1) | projection_contracts.py:74-79 | — |
| qdrant_collection_name | def | corpus_id, contract_id -> collection name | projection_contracts.py:82-87 | — |
| qdrant_point_uuid | def | source_id -> uuid5 | projection_contracts.py:93-100 | — |
| hash_embed_v1 | def | text -> deterministic embedding | projection_contracts.py:103-122 | — |
| embed | def | text, contract_id -> embedding | projection_contracts.py:125-137 | — |
| reconcile_state | def | expected_hash, observed_hash, failed, observed_present -> lifecycle state | projection_lifecycle.py:36-52 | — |
| can_transition | def | frm, to -> bool | projection_lifecycle.py:55-56 | — |
| is_current | def | state -> bool | projection_lifecycle.py:59-61 | — |
| is_rebuildable | def | state -> bool | projection_lifecycle.py:64-66 | — |
| ReconcileReport | class | completeness, rebuildable, is_reconciled, as_dict | projection_reconcile.py:20-41 | — |
| reconcile | def | expected (entity_id→canonical hash), observed -> ReconcileReport | projection_reconcile.py:44-61 | — |
| observed_from_rows | def | rows (projection_manifest_row shape) -> observed | projection_reconcile.py:64-79 | — |
| chunk_tier_sql | def | projection, alias -> predicate ('' = all) | projection_want.py:19-23 | — |
| desired_chunk_ids | def | conn, run_id, projection -> ids | projection_want.py:26-41 | — |
| missing_chunk_receipts_for_run | def | conn, run_id, projection -> missing ids (census gate) | projection_want.py:44-65 | — |
| missing_chunk_receipts_for_docs | def | conn, doc_ids, projection -> missing ids (RUN-SCOPED-RECEIPTS-V1) | projection_want.py:68-92 | — |
| corpora_with_missing_chunk_receipts | def | conn, projection -> corpora (barrier gate) | projection_want.py:95-114 | — |
| classify_query | def | question -> route | query_router.py:56-85 | — |
| is_enumeration_query | def | query -> bool | query_shape.py:60-73 | — |
| depth_plan | def | plan -> depth profile | query_shape.py:76-100 | — |
| is_document_metadata_query | def | query -> bool | query_shape.py:122-125 | — |
| plan_for_query | def | query, plan -> retrieval profile | query_shape.py:128-139 | — |
| ReferentialSpan | class | expanded() | referential_span.py:37-53 | — |
| derive | def | proposal_surface, proposal_start, proposal_end, source_text, syntax -> envelope | referential_span.py:62-115 | — |
| is_meaningful_term | def | term -> bool | resolution_lift.py:50-56 | — |
| is_identifier_like | def | term -> bool | resolution_lift.py:59-61 | — |
| specificity_beyond | def | term, query, query_exact_terms -> bool | resolution_lift.py:68-80 | — |
| LiftCandidate | class | no methods | resolution_lift.py:84-92 | — |
| score_candidate | def | c, corpus_doc_count -> score | resolution_lift.py:103-116 | — |
| rank_lift_candidates | def | candidates, query, query_exact_terms, k, corpus_doc_count -> list | resolution_lift.py:119-136 | — |
| mode_plan | def | mode -> retrieval plan | retrieval_modes.py:45-49 | — |
| hybrid_mode_plan | def | mode -> plan | retrieval_modes.py:52-55 | — |
| apply_latent | def | plan, enabled -> plan (per-request `latent` flag) | retrieval_modes.py:58-71 | — |
| apply_utility | def | plan, enabled -> plan (per-request `utility` flag) | retrieval_modes.py:74-87 | — |
| validate_mode | def | mode -> — | retrieval_modes.py:107-114 | — |

Module state: `polymath_principal_id` ContextVar at principal_context.py:20.

## contracts

**seat_portfolio** — latent_portfolio.py:47-132
- in: `candidates` = rerank-ordered dicts each with `chunk_id`, a rep key (`rep_key`/`parent_id`/`doc_id`) and `role` (a C4 state: DIRECT_ELIGIBLE / COMPLEMENTARY_ELIGIBLE / DIVERGENT_ELIGIBLE) — latent_portfolio.py:54-56,67-70 [DERIVED]
- out: `(seated, trace)`; each seated item = input dict + `seat_role` ∈ DIRECT/COMPLEMENTARY/DIVERGENT/RELATED, in seating order — latent_portfolio.py:56-57,86 [DERIVED]
- pre: `capacity ≤ 0` ⇒ `([], trace)` — latent_portfolio.py:57-58,66 [DERIVED]
- post: never raises; trace carries capacity/direct/complementary/divergent/fill counts, `establishes_need`, `direct_grounded`, `divergent_allowed`, `redundant_direct_yielded`, `complementary_yielded` — latent_portfolio.py:57,78-80,130-131 [DERIVED]
- post: seating order is fixed 5 steps — REQUIRED DIRECT (≤ `direct_per_rep_cap` per representation) → grounding check → DISTINCT COMPLEMENTARY → DIVERGENT → fill (redundant DIRECT, redundant COMPLEMENTARY, ordinary) — latent_portfolio.py:13-19,89-129 [DERIVED]
- post: `establishes_need is False` ⇒ no COMPLEMENTARY and no DIVERGENT seats; PARTIAL-only ⇒ COMPLEMENTARY may seat, DIVERGENT capacity 0 — latent_portfolio.py:59-65,99-102,105-108 [DERIVED]

**grade_and_seat_latent** — latent_selection.py:44-96
- in: `pool` items `{chunk_id, doc_id, parent_id, text, query_ids, q0_score}` (q0_score REUSED, never recomputed); `bridges` = `{bridge_id: {query, proposed_role}}` — latent_selection.py:54-58 [DERIVED]
- out: `(seated, trace)`; trace = `bridge_q0`, `n_bridges`, `graded` receipt (every graded candidate incl. rejected, for C6 calibration) + the C5 counts — latent_selection.py:60-62,93-96 [DERIVED]
- pre/post: cost bound 1 + (#distinct bridges) rerank calls, never per-candidate — latent_selection.py:8-11,65-74 [DERIVED]
- post: deterministic given the injected rerank — latent_selection.py:63 [DERIVED]

**heading_regions** — layout_evidence.py:58-78
- pre: MUST be called on text that still has line structure (the source document); assembled chunk text has no newlines — layout_evidence.py:62-67 [DERIVED]
- out: [start, end) regions of heading lines only (ATX `#{1,6}` or setext underline); short capitalized prose is NOT a heading — layout_evidence.py:14-18,29-30 [DERIVED]

**independently_capitalized** — layout_evidence.py:86-102
- in/out: token with ≥2 letters; True iff all-caps or an internal capital (title-casing cannot produce it): `Working`→False, `PostgreSQL`/`GLiNER`/`NIST`→True — layout_evidence.py:93-99 [DERIVED]

**JsonFormatter.format** — logging.py:29-40
- out: JSON with `timestamp` (UTC now), `level`, `service`, `event`, `message`, the 9 CONTEXT_FIELDS (null when absent), optional `exception` — logging.py:30-40 [DERIVED]

**gate_probes** — probe_gate.py:34-73
- in: `probes` = (id, origin, text); only `gated_origins` are scored; default gate set GATED_ORIGINS = `["BRIDGE", "CORPUS_EXPLORE", "PROFILE"]`, DEFAULT_FLOOR = `0.2`, PROBE_GATE_VERSION = `"probe-gate-v1"` — probe_gate.py:24-27,39 [DERIVED]
- out: `(ids to drop, receipt)` — probe_gate.py:39 [DERIVED]

**embed / hash_embed_v1** — projection_contracts.py:103-137
- in: contract id; only `"hash-embed-v1"` registered (dim 512, "deterministic hashed 3-gram bag, zero model"); unknown contracts raise — projection_contracts.py:47,53,125-137 [DERIVED]
- out: qdrant point id = uuid5 under namespace `"polymath-qdrant-point-v1"`; collection names prefixed `"polymath"` — projection_contracts.py:55,90,93-100 [DERIVED]

**reconcile** — projection_reconcile.py:44-61
- in: `expected` = entity_id → canonical artifact hash (authoritative version); `observed` from `observed_from_rows` (manifest rows) — projection_reconcile.py:52-53,64-79 [DERIVED]
- out: ReconcileReport (completeness, rebuildable, is_reconciled, as_dict) — projection_reconcile.py:20-41 [DERIVED]

**projection lifecycle** — projection_lifecycle.py:19-66
- states PENDING/PROJECTED/STALE/FAILED, version `"projection-lifecycle-v1"`; `is_rebuildable` when not `is_current` — projection_lifecycle.py:19-24,59-66 [DERIVED]

## effect surface
- Postgres read (unit-level FACTS): `chunks`, `documents`, `entities`, `facts`, `projection_receipts`, `runs`; writers take `conn`: projection_want.py:26-114 [INFERRED: conn/run_id args imply SQL reads]. tables_written: none (FACTS).
- Qdrant: collection naming + point uuids only — projection_contracts.py:82-100.
- Files: NEO4J_CONSTRAINT_FILE = `"stores/neo4j/constraints/0001_uniqueness.cypher"` — projection_contracts.py:56.
- Concurrency: ThreadPoolExecutor in gate_probes — probe_gate.py:53.
- Network: none direct; the cross-encoder rerank is injected by the caller — latent_selection.py:58.
- Env flags: none visible in FACTS/SOURCE.

## invariants
INVARIANT: DEFAULT_DIRECT_PER_REP_CAP = 3, DEFAULT_MAX_DIVERGENT = 2, DEFAULT_MIN_ADEQUATE_DIRECT = 1 — latent_portfolio.py:37-39 [DERIVED]
  fails-if: seat mix changes silently; latent_selection re-imports these same constants (latent_selection.py:20-24).
INVARIANT: establishes_need == False ⇒ seated complementary = 0 and divergent_allowed = False — latent_portfolio.py:63-65,102,106-108 [DERIVED]
  fails-if: ungrounded answers get enrichment seats; substitution instead of expansion.
INVARIANT: divergent seats ≤ max_divergent (2) and only a new representation — latent_portfolio.py:116-121 [DERIVED]
  fails-if: DIVERGENT floods the portfolio over DIRECT grounding.
INVARIANT: DISTINCT COMPLEMENTARY seated at step 3 BEFORE redundant DIRECT at step 5 — latent_portfolio.py:20-22,103-112,122-129 [DERIVED]
  fails-if: rule B breaks — redundant DIRECT greedily consumes diverse seats.
INVARIANT: extra rerank calls = 1 + (#distinct bridges), never per-candidate — latent_selection.py:6-11 [DERIVED]
  fails-if: latent layer becomes a per-candidate cost blowup.
INVARIANT: hash-embed-v1 dim = 512 — projection_contracts.py:47 [DERIVED]
  fails-if: stored Qdrant vectors no longer match the contract dim.
INVARIANT: DEFAULT_FLOOR (probe gate) = 0.2 — probe_gate.py:26 [DERIVED]
  fails-if: gate tightness changes for BRIDGE/CORPUS_EXPLORE/PROFILE probes.
INVARIANT: len(CONTEXT_FIELDS) = 9 (trace_id…error_code) — logging.py:11-21 [DERIVED]
  fails-if: log consumers parsing the JSON field contract break.
INVARIANT: embed('text', unknown-contract) raises — projection_contracts.py:125-137 [DERIVED]
  fails-if: silent wrong-dimension embeddings enter stores.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: logging.py:31 `dt.datetime.now`; probe_gate.py:40,45,59,72 `time.perf_counter`; concurrency: probe_gate.py:53 ThreadPoolExecutor). Pure and deterministic otherwise: latent_portfolio ("pure, deterministic, no I/O, no model" latent_portfolio.py:1); grade_and_seat_latent deterministic given injected rerank (latent_selection.py:63).
idempotency: SAFE — no table writes (FACTS tables_written = []), pure modules stateless; configure_logging mutates process logging config on each call (logging.py:43-48).

## failure behaviour
- latent_selection `_score_map`: any `Exception` swallowed → returns `{}` → latent layer degrades to no latent additions; the DIRECT/q0 portfolio is unaffected — latent_selection.py:14-15,33-35 [DERIVED]
- probe_gate: `Exception` handled → returns `(set(), receipt)` — probe_gate.py:58 (FACTS.fallbacks) [DERIVED]
- seat_portfolio: "Deterministic; never raises" — latent_portfolio.py:57 [DERIVED]
- embed: unknown contract raises (new contract must be added explicitly) — projection_contracts.py:126-137 [DERIVED]

## dumb-code flags
- Magic string `"DIRECT_ELIGIBLE"` in the graded-receipt filter instead of the imported constant — latent_selection.py:94-95 [DERIVED]
- Step-5 `break` exits only the inner pool loop; the outer pool loop keeps iterating after capacity is full (harmless scan) — latent_portfolio.py:124-128 [DERIVED]
- Four separate `time.perf_counter` call sites in one 40-line module — probe_gate.py:40,45,59,72 [DERIVED]
- Magic numbers: GRAPH_MAX_SEEDS = 8, GRAPH_MAX_FACTS = 20, GRAPH_DEFINITIONAL_MAX_SEEDS = 2 — retrieval_modes.py:94,95,100 [DERIVED]
- Ten-entry `_SOURCE_PRIOR` float dict (EXACT_ID 1.0 … TOPIC 0.5) — resolution_lift.py:40 [DERIVED]
- SEAT_RELATED = "RELATED" used only for the step-5 "other" fill — latent_portfolio.py:35,125 [DERIVED]

## refactor notes
- Blast radius: 50 importers across control/, orchestrator/ (api/*), workers/, sidecars/ (FACTS.importers) — any signature change here hits all of them.
- Seating order encodes rules A/B; reordering steps breaks non-displacement of DIRECT and complementary-yields-to-distinct — latent_portfolio.py:5-7,20-22,89-129.
- q0↔chunk score reuse contract: grade_and_seat_latent never recomputes q0 scores; pool schema change (q0_score/query_ids) breaks it — latent_selection.py:6-8,54-55.
- Persisted identity strings must not change without store migration: `"polymath-qdrant-point-v1"` namespace, `"polymath"` collection prefix, `hash-embed-v1`, plus version markers `layout-evidence-v2` (layout_evidence.py:27), `probe-gate-v1` (probe_gate.py:27), `projection-lifecycle-v1` (projection_lifecycle.py:19), `projection-reconcile-v1` (projection_reconcile.py:16), `query-router-v1` (query_router.py:22), `resolution-lift-v1` (resolution_lift.py:33), `retrieval-mode-v1` (retrieval_modes.py:17), `referential-span-v1` (referential_span.py:28).
- HEADER `"x-polymath-principal"` is a wire contract consumed by PrincipalContextMiddleware — principal_context.py:18,48-71.
- CONTEXT_FIELDS is a cross-service log contract referencing AGENTS.md — logging.py:1,11-21.
- ADMITTED_SQL (`admission_class IS DISTINCT FROM 'MENTION_ONLY'`) is shared by entity and fact eligibility SQL — neo4j_eligibility.py:41-59.
- heading_regions must keep receiving line-structured source text, not chunk text — layout_evidence.py:62-67.

## VERIFY
```verify
grep -Fq 'DEFAULT_DIRECT_PER_REP_CAP = 3' shared/polymath_shared/latent_portfolio.py
grep -Fq 'is seated BEFORE redundant DIRECT' shared/polymath_shared/latent_portfolio.py
grep -Fq 'Fail-open to {}' shared/polymath_shared/latent_selection.py
grep -Fq 'layout-evidence-v2' shared/polymath_shared/layout_evidence.py
grep -Fq 'x-polymath-principal' shared/polymath_shared/principal_context.py
grep -Fq 'admission_class IS DISTINCT FROM' shared/polymath_shared/neo4j_eligibility.py
grep -Fq 'polymath-qdrant-point-v1' shared/polymath_shared/projection_contracts.py
test "$(grep -c -F 'time.perf_counter' shared/polymath_shared/probe_gate.py)" -ge 4
```
