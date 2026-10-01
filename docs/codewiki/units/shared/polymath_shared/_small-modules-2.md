# unit: shared/polymath_shared/_small-modules-2
anchor: shared/polymath_shared/latent_portfolio.py:1-133

## purpose
Bundle of small shared modules for the Polymath pipeline: librarian evidence seating (`latent_portfolio`, `latent_selection`), layout-vs-identity evidence, structured JSON logging, Neo4j eligibility predicates, principal propagation, probe gating, librarian receipts, projection contracts/lifecycle/reconcile/want, query router/scope/shape, referential spans, resolution lift. Consumed by control, orchestrator API, workers, and both sidecars (FACTS.importers). Core seating module is "pure, deterministic, no I/O, no model" — shared/polymath_shared/latent_portfolio.py:1 [DERIVED].

## public surface
Unit-level importers (FACTS.importers, attribution per symbol unknown): control (census.py, generation_swap.py, main.py, process_supervisor.py, tickets.py), orchestrator (api: acquisition, adapter, ask, deep_research, fast, graph, hybrid, retrieve, ui, web_auth; main), workers (intake_worker … verify_worker), sidecars (embedder/server.py, reranker/server.py).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| seat_portfolio | def | candidates, *, capacity, direct_per_rep_cap=3, max_divergent=2, min_adequate_direct=1, complementary_cap=None, establishes_need=True, has_direct_grounding=None -> (seated, trace) | latent_portfolio.py:47-132 | — |
| grade_and_seat_latent | def | *, q0_text, pool, bridges, rerank, capacity, floor=DEFAULT_FLOOR, bridge_valid_floor=None, divergent_local_floor=None, direct_per_rep_cap=3, max_divergent=2, min_adequate_direct=1, complementary_cap=None, establishes_need=True, has_direct_grounding=None -> (seated, trace) | latent_selection.py:44-96 | — |
| project_regions | def | regions, doc_start, doc_end, chunk_start -> [(start, end)] | layout_evidence.py:33-55 | — |
| heading_regions | def | text -> [(start, end)] | layout_evidence.py:58-78 | — |
| in_heading | def | regions, start, end -> bool | layout_evidence.py:81-83 | — |
| independently_capitalized | def | token_text -> bool | layout_evidence.py:86-102 | — |
| JsonFormatter | class | (service); .format(record) -> JSON str | logging.py:24-40 | — |
| configure_logging | def | service, level=logging.INFO -> None | logging.py:43-48 | — |
| with_context | def | logger, **context -> LoggerAdapter | logging.py:51-55 | — |
| entity_eligible_sql | def | alias -> SQL predicate | neo4j_eligibility.py:44-46 | — |
| fact_eligible_sql | def | f_alias -> SQL predicate | neo4j_eligibility.py:49-59 | — |
| fact_eligible_from_row | def | subject_class, object_class, decision -> bool | neo4j_eligibility.py:62-65 | — |
| fact_eligible_from_classes | def | subject_class, object_class -> bool | neo4j_eligibility.py:68-73 | — |
| eligible_fact_ids_sql / ineligible_fact_ids_sql | def | () -> SQL | neo4j_eligibility.py:76-79 / 82-86 | — |
| current | def | () -> principal or None | principal_context.py:23-25 | — |
| acting_as | def | principal_id -> context manager | principal_context.py:29-37 | — |
| parse | def | value -> principal | principal_context.py:40-45 | — |
| PrincipalContextMiddleware | class | pure ASGI; __init__, __call__ | principal_context.py:48-71 | — |
| gate_probes | def | question, probes, rerank, floor, timeout_s, gated_origins -> (ids_to_drop, receipt) | probe_gate.py:34-73 | — |
| selected_evidence_query_ids | def | evidence_items -> set of subquery ids | profile_yield.py:35-41 | — |
| evidence_provenance | def | evidence_items -> normalized provenance | profile_yield.py:44-55 | — |
| evidence_yield_by_origin | def | subqueries, evidence_items -> per-origin breakdown | profile_yield.py:58-68 | — |
| profile_expansion_evidence_yield | def | subqueries, evidence_items -> yield metric | profile_yield.py:71-86 | — |
| librarian_receipt | def | plan, evidence_items, scout, resolution, mode, lanes, q0 -> receipt | profile_yield.py:89-105 | — |
| projection_id | def | projection, entity_kind, source_id, contract_version -> id | projection_contracts.py:59-66 | — |
| receipt_hash | def | same params -> hash (= projection identity) | projection_contracts.py:69-71 | — |
| entity_card_id | def | entity_id, corpus_id -> card id | projection_contracts.py:74-79 | — |
| qdrant_collection_name | def | corpus_id, contract_id -> collection name | projection_contracts.py:82-87 | — |
| qdrant_point_uuid | def | source_id -> uuid5 | projection_contracts.py:93-100 | — |
| hash_embed_v1 | def | text -> embedding (dim 512) | projection_contracts.py:103-122 | — |
| embed | def | text, contract_id -> embedding (unknown contract raises) | projection_contracts.py:125-137 | — |
| reconcile_state | def | expected_hash, observed_hash, failed, observed_present -> state | projection_lifecycle.py:36-52 | — |
| can_transition / is_current / is_rebuildable | def | state(s) -> bool | projection_lifecycle.py:55-56 / 59-61 / 64-66 | — |
| ReconcileReport | class | completeness, rebuildable, is_reconciled, as_dict | projection_reconcile.py:20-41 | — |
| reconcile | def | expected, observed -> report | projection_reconcile.py:44-61 | — |
| observed_from_rows | def | manifest rows -> observed map | projection_reconcile.py:64-79 | — |
| chunk_tier_sql | def | projection, alias -> predicate fragment | projection_want.py:19-23 | — |
| desired_chunk_ids | def | conn, run_id, projection -> ids | projection_want.py:26-41 | — |
| missing_chunk_receipts_for_run | def | conn, run_id, projection -> missing ids | projection_want.py:44-65 | — |
| missing_chunk_receipts_for_docs | def | conn, doc_ids, projection -> missing ids | projection_want.py:68-92 | — |
| corpora_with_missing_chunk_receipts | def | conn, projection -> corpora | projection_want.py:95-114 | — |
| classify_query | def | question -> route label | query_router.py:56-85 | — |
| QueryScopeRequired / UnknownQueryScope | class | typed refusals | query_scope.py:22-25 / 28-31 | — |
| QueryScope | class | .as_dict() | query_scope.py:35-40 | — |
| resolve_query_scope | def | conn, corpus_id, corpus_ids, workspace, all_authorized -> QueryScope | query_scope.py:43-86 | — |
| is_enumeration_query | def | query -> bool | query_shape.py:60-73 | — |
| depth_plan | def | plan -> DEPTH profile plan | query_shape.py:76-100 | — |
| is_document_metadata_query | def | query -> bool | query_shape.py:122-125 | — |
| plan_for_query | def | query, plan -> retrieval profile | query_shape.py:128-139 | — |
| ReferentialSpan | class | .expanded() | referential_span.py:37-53 | — |
| derive | def | proposal_surface, proposal_start, proposal_end, source_text, syntax -> ReferentialSpan | referential_span.py:62-115 | — |
| is_meaningful_term / is_identifier_like | def | term -> bool | resolution_lift.py:50-56 / 59-61 | — |
| specificity_beyond | def | term, query, query_exact_terms -> bool | resolution_lift.py:68-80 | — |
| LiftCandidate | class | data holder | resolution_lift.py:84-92 | — |
| score_candidate | def | c, corpus_doc_count -> score | resolution_lift.py:103-116 | — |
| rank_lift_candidates | def | candidates, query, query_exact_terms, k, corpus_doc_count -> ranked list | resolution_lift.py:119-136 | — |

## contracts

**seat_portfolio** — latent_portfolio.py:47-132
- in: `candidates` = rerank-ordered dicts, each with `chunk_id`, a rep key (`rep_key`/`parent_id`/`doc_id`), `role` (C4 state); `capacity` int — latent_portfolio.py:54-56 [DERIVED]
- pre: input order within each role IS the rerank priority — latent_portfolio.py:21 [DERIVED]
- out: `(seated, trace)`; seated item = input dict + `seat_role`, in seating order; `capacity ≤ 0` ⇒ `([], trace)` — latent_portfolio.py:56-57, 66 [DERIVED]
- post: deterministic, never raises — latent_portfolio.py:57 [DERIVED]
- gating: COMPLEMENTARY needs `establishes_need`; DIVERGENT needs actual DIRECT grounding (`has_direct_grounding`, else seated DIRECT ≥ `min_adequate_direct`) — latent_portfolio.py:59-65, 99-102 [DERIVED]

**grade_and_seat_latent** — latent_selection.py:44-96
- in: pool dicts `{chunk_id, doc_id, parent_id, text, query_ids, q0_score}`; `bridges` = `{bridge_id: {query, proposed_role}}`; injected `rerank(query, rows)` — latent_selection.py:54-58 [DERIVED]
- pre: `q0_score` = existing q0 rerank logit, REUSED, never recomputed — latent_selection.py:7, 55 [DERIVED]
- out: `(seated, trace)`; seated = pool candidate + `seat_role` + C4 `eligibility`; trace = `bridge_q0`, `n_bridges`, `graded`, C5 counts — latent_selection.py:60-62, 93-96 [DERIVED]
- budget: extra cost = 1 + (#distinct bridges) rerank calls, never per-candidate — latent_selection.py:10, 65-74 [DERIVED]

**heading_regions** — layout_evidence.py:58-78
- pre: text must still have line structure (materialized source); assembled chunk text has no newlines, so a leading `###` makes the whole chunk look like one heading — layout_evidence.py:61-64 [DERIVED]
- out: `[start, end)` regions of ATX (`#{1,6}`) and setext (`=+` / `-{2,}` underline) heading lines — layout_evidence.py:29-30 [DERIVED]
- deliberate: a short capitalized prose line is NOT a heading — layout_evidence.py:15-18 [DERIVED]

**project_regions** — layout_evidence.py:33-55: clips regions to `[doc_start, doc_end)` and shifts by `chunk_start`; caller must project per sentence because chunk text joins sentences with a single space — layout_evidence.py:39-47, 49-55 [DERIVED]

**independently_capitalized** — layout_evidence.py:86-102: `False` for title-case `Xxxxx` and for `len(core) < 2`; `True` for internal capitals or all-caps (`PostgreSQL`, `GLiNER`, `NIST`) — layout_evidence.py:89-102 [DERIVED]

**configure_logging / with_context** — logging.py:43-55
- out: JSON lines on stdout with `timestamp`, `level`, `service`, `event`, `message` + CONTEXT_FIELDS, optional `exception` — logging.py:30-40, 44-47 [DERIVED]
- pre: `with_context` keys ⊆ CONTEXT_FIELDS ∪ {`event`, `service`}, else `ValueError` — logging.py:52-54 [DERIVED]

**eligibility predicates** — neo4j_eligibility.py:44-86
- entity eligible ⇔ `admission_class IS DISTINCT FROM 'MENTION_ONLY'` (ADMITTED_SQL, line 41); NULL = legacy pre-0007 rows are eligible — neo4j_eligibility.py:15-16, 41 [DERIVED]
- fact eligible ⇔ both endpoints eligible AND decision not REJECT — neo4j_eligibility.py:17-18 [DERIVED]
- shared by project_neo4j_worker, control census, verify_worker — neo4j_eligibility.py:5-12 [DERIVED]

**resolve_query_scope** — query_scope.py:43-86: fail-closed; no explicit scope ⇒ `QueryScopeRequired` (query_scope.py:22), unknown named scope ⇒ `UnknownQueryScope` (query_scope.py:28); returns `QueryScope` with `as_dict` (query_scope.py:35-40) [DERIVED]

**gate_probes** — probe_gate.py:34-73: probes = `(id, origin, text)`; only `GATED_ORIGINS` = `["BRIDGE", "CORPUS_EXPLORE", "PROFILE"]` scored (probe_gate.py:24); `DEFAULT_FLOOR = 0.2`, `PROBE_GATE_VERSION = "probe-gate-v1"` (probe_gate.py:26-27); returns (ids to drop, receipt) (probe_gate.py:38-39) [DERIVED]

**projection identity family** — projection_contracts.py:59-137: `projection_id` = deterministic identity of one artifact (line 60); `receipt_hash` = same inputs, same key (line 70); `qdrant_point_uuid` = uuid5 from source chunk id, namespace `polymath-qdrant-point-v1`, Qdrant 1.13 (lines 90-92); `hash_embed_v1` = deterministic hashed 3-gram bag, zero model, dim 512 (lines 48, 103); `embed` raises on unknown contract (line 126) [DERIVED]

**reconcile_state** — projection_lifecycle.py:36-52: derives state ∈ `PENDING`/`PROJECTED`/`STALE`/`FAILED` (lines 21-24) from canonical-expected vs store-observed (line 37); `is_rebuildable` = not already current (line 65) [DERIVED]

**projection_want gates** — projection_want.py:19-114: want-set tier filter is literally `c.tier = 'child'` (line 16); `missing_chunk_receipts_for_run` = census promotion gate (line 45); `missing_chunk_receipts_for_docs` = RUN-SCOPED-RECEIPTS-V1, 2026-09-03 (line 69); `corpora_with_missing_chunk_receipts` = barrier gate preserving BULK-RECEIPT-COMPLETENESS-V1 shape (line 96) [DERIVED]

**classify_query** — query_router.py:56-85: returns one of `FACT_QUERY`/`PROCEDURE_QUERY`/`CONCEPT_QUERY`/`POLYMATH_QUERY` (lines 18-21) via regex pattern lists `_PROCEDURE_PATTERNS`, `_CONCEPT_PATTERNS`, `_POLYMATH_PATTERNS`, `_FACT_PATTERNS` (lines 24-50) [DERIVED]

**plan_for_query** — query_shape.py:128-139: picks the retrieval profile (line 129); `depth_plan` = same engine, caps re-shaped for completeness (line 77) [DERIVED]

**derive** — referential_span.py:62-115: referential envelope for one GLiNER proposal (line 63); determiner list `_DETERMINERS` (line 30) [DERIVED]

**rank_lift_candidates** — resolution_lift.py:119-136: filters to source-derived terms that ADD specificity, dedupes by lowercased term (line 120); `score_candidate` = §11 weighted specificity (line 104) with `_SOURCE_PRIOR` weights `EXACT_ID 1.0, MAP_ID 0.95, ENTITY 0.9, ALIAS 0.85, MAP_HOOK 0.65, ATOM 0.55, TOPIC 0.5, TERM 0.7, HEADING 0.45` (line 40) [DERIVED]

**principal_context** — principal_context.py:23-71: `current()` → principal or None for legacy/trusted-local (line 24); `acting_as` carries a request's principal onto work started elsewhere, e.g. a worker thread's callback into the event loop (line 30); middleware is pure ASGI, same task as the endpoint so the context variable is visible (line 49); collection `polymath_principal_id` (line 20) [DERIVED]

## effect surface
- Postgres read (via `conn` params): `chunks`, `corpora`, `documents`, `entities`, `facts`, `projection_receipts`, `query_workspaces`, `runs` (FACTS.tables_read; conn at projection_want.py:26-114, query_scope.py:43-86) [DERIVED]
- Postgres written: none (FACTS.tables_written = []) [DERIVED]
- Qdrant: naming/identity only — collection prefix `"polymath"` (projection_contracts.py:55, 82-87), point uuid5 namespace `"polymath-qdrant-point-v1"` (projection_contracts.py:90-93) [DERIVED]
- Files: constant `NEO4J_CONSTRAINT_FILE = "stores/neo4j/constraints/0001_uniqueness.cypher"` (projection_contracts.py:56) — reference only [DERIVED]
- Model/network: injected `rerank` cross-encoder (latent_selection.py:58; probe_gate.py:34-73) [DERIVED]
- Clock: `dt.datetime.now` (logging.py:31); `time.perf_counter` (probe_gate.py:40, 45, 59, 72) [DERIVED]
- Concurrency: `ThreadPoolExecutor` (probe_gate.py:53) [DERIVED]
- Env flags: none visible.

## invariants
INVARIANT: len(seated) ≤ capacity — latent_portfolio.py:84-87 [DERIVED]
  fails-if: portfolio overflows the bounded context budget.
INVARIANT: each chunk_id seated at most once (`seen` set) — latent_portfolio.py:84-87 [DERIVED]
  fails-if: duplicate evidence rows double-count seats.
INVARIANT: DISTINCT COMPLEMENTARY (step 3) seated before redundant DIRECT (step 5) — latent_portfolio.py:19-20, 103-114, 122-128 [DERIVED]
  fails-if: redundant DIRECT greedily consumes a seat a distinct complementary candidate could occupy (rule B).
INVARIANT: REQUIRED DIRECT (step 1) seated first, never displaced — latent_portfolio.py:20, 89-96 [DERIVED]
  fails-if: latent candidates displace evidence required to answer q0 (rule A).
INVARIANT: divergent_allowed == establishes_need AND direct_grounded — latent_portfolio.py:102, 116 [DERIVED]
  fails-if: DIVERGENT seats on PARTIAL-only or absent grounding.
INVARIANT: defaults direct_per_rep_cap=3, max_divergent=2, min_adequate_direct=1 — latent_portfolio.py:37-39 [DERIVED]
  fails-if: caller relies on drifted defaults; seating mix changes.
INVARIANT: extra rerank calls == 1 + #distinct bridges — latent_selection.py:10, 65-74 [DERIVED]
  fails-if: per-candidate rescoring reintroduces the cost this design forbids.
INVARIANT: heading detection runs only on line-structured text — layout_evidence.py:61-64 [DERIVED]
  fails-if: called on assembled chunk text (no newlines) → whole chunk reads as one heading.
INVARIANT: title-case token ⇒ independently_capitalized == False — layout_evidence.py:89-97 [DERIVED]
  fails-if: publisher house style is misread as semantic identity evidence (layout_evidence.py:7).
INVARIANT: log context keys ⊆ CONTEXT_FIELDS ∪ {event, service} — logging.py:11-21, 52-54 [DERIVED]
  fails-if: ValueError at with_context; log schema drift.
INVARIANT: entity eligible ⇔ admission_class IS DISTINCT FROM 'MENTION_ONLY' — neo4j_eligibility.py:15, 41 [DERIVED]
  fails-if: worker, census, and verify disagree on parked entities/facts.
INVARIANT: qdrant point id == uuid5(namespace "polymath-qdrant-point-v1", source chunk id) — projection_contracts.py:90-92 [DERIVED]
  fails-if: point identity churn; orphaned/duplicate vectors.
INVARIANT: projection want-set tier == 'child' — projection_want.py:16 [DERIVED]
  fails-if: gates under/over-count receipts relative to what projectors actually emit.
INVARIANT: unknown df ⇒ idf 0.5 — resolution_lift.py:95-96 [DERIVED]
  fails-if: unseen terms score as maximally rare and skew lift ranking.

## determinism & idempotency
determinism: DETERMINISTIC for seating ("pure, deterministic, no I/O, no model" latent_portfolio.py:1; "Deterministic given the injected rerank" latent_selection.py:62). NONDETERMINISTIC spots: logging.py:31 (clock `dt.datetime.now`), probe_gate.py:40, 45, 59, 72 (clock `time.perf_counter`), probe_gate.py:53 (concurrency `ThreadPoolExecutor`) [DERIVED]
idempotency: SAFE — no tables written (FACTS.tables_written = []), DB access read-only via `conn` (projection_want.py:26-114, query_scope.py:43-86), pure functions elsewhere [DERIVED]

## failure behaviour
- latent_selection.py:34 — `Exception` SWALLOWED → `return {}` (latent_selection.py:34-35): rerank failure degrades to no latent additions; the DIRECT/q0 portfolio is unaffected (latent_selection.py:14-15) [DERIVED]
- probe_gate.py:58 — `Exception` handled → `return (set(), receipt)` (FACTS.fallbacks; probe_gate.py:58): caller drops no probes [DERIVED]
- `embed`: unknown contract raises — projection_contracts.py:126 [DERIVED]
- `with_context`: raises `ValueError` on unknown fields — logging.py:53-54 [DERIVED]
- `resolve_query_scope`: raises `QueryScopeRequired` / `UnknownQueryScope` — query_scope.py:22-31 [DERIVED]
- `seat_portfolio`: never raises — latent_portfolio.py:57 [DERIVED]

## dumb-code flags
- Module header says `LAYOUT-EVIDENCE-V1` but `LAYOUT_CONTRACT = "layout-evidence-v2"` — layout_evidence.py:1 vs 27 [DERIVED]
- Two `DEFAULT_FLOOR` homes: `probe_gate.py:26` defines `DEFAULT_FLOOR = 0.2` while `latent_selection.py:19` imports `DEFAULT_FLOOR` from `polymath_shared.latent_eligibility` — same name, separate values; drift risk [INFERRED: latent_eligibility's value not shown here]
- `DEFAULT_DIRECT_PER_REP_CAP = 3` justified only by comment "matches the existing composer's per-document soft max" — coupling unenforced in code — latent_portfolio.py:37 [DERIVED]
- `SEAT_RELATED` used only for the step-5 `other` catch-all pool — latent_portfolio.py:35, 70, 124-128 [DERIVED]
- `redundant_comp` collects both blocked and seat-failed candidates — two causes, one list — latent_portfolio.py:109-114 [DERIVED]
- `_key` fallback chain `rep_key` → `parent_id` → `doc_id` → `chunk_id` silently changes distinctness if any key is missing — latent_portfolio.py:44 [DERIVED]

## refactor notes
- Any public rename touches control, orchestrator API (acquisition…web_auth), 12+ workers, both sidecars (FACTS.importers) [DERIVED]
- Seating depends on latent_eligibility exports `COMPLEMENTARY_ELIGIBLE`, `DIRECT_ELIGIBLE`, `DIVERGENT_ELIGIBLE`, `DEFAULT_FLOOR`, `evaluate_candidate` — latent_portfolio.py:25-29, latent_selection.py:19 [DERIVED]
- Version/contract strings are persisted identities: `layout-evidence-v2` (layout_evidence.py:27), `probe-gate-v1` (probe_gate.py:27), `query-router-v1` (query_router.py:22), `resolution-lift-v1` (resolution_lift.py:33), `referential-span-v1` (referential_span.py:28), `projection-lifecycle-v1` (projection_lifecycle.py:19), `projection-reconcile-v1` (projection_reconcile.py:16) [DERIVED]
- `EMBEDDING_CONTRACT = "hash-embed-v1"` with dim 512 fixes the Qdrant vector shape; a new contract id is required to change dims — projection_contracts.py:47-53 [DERIVED]
- `QDRANT_CHUNK_TIER_SQL = "c.tier = 'child'"` shapes every want-set and both gates in projection_want (census promotion, barrier) — projection_want.py:16-23, 44-65, 95-114 [DERIVED]
- `HEADER = "x-polymath-principal"` is a wire header (principal_context.py:18); orchestrator api/web_auth.py is a unit importer [DERIVED]
- Seating steps 1–5 ARE the policy (rules A/B fall out of order) — reordering changes outcomes — latent_portfolio.py:12-21 [DERIVED]

## VERIFY
```verify
grep -Fq 'DEFAULT_DIRECT_PER_REP_CAP = 3' shared/polymath_shared/latent_portfolio.py
grep -Eq 'LAYOUT_CONTRACT = .layout-evidence-v2.' shared/polymath_shared/layout_evidence.py
grep -Fq 'admission_class IS DISTINCT FROM' shared/polymath_shared/neo4j_eligibility.py
grep -Fq 'x-polymath-principal' shared/polymath_shared/principal_context.py
grep -Fq 'polymath-qdrant-point-v1' shared/polymath_shared/projection_contracts.py
grep -Fq 'CORPUS_EXPLORE' shared/polymath_shared/probe_gate.py
test "$(grep -c -F 'perf_counter' shared/polymath_shared/probe_gate.py)" -ge 4
! grep -Fq 'import random' shared/polymath_shared/latent_portfolio.py
```
