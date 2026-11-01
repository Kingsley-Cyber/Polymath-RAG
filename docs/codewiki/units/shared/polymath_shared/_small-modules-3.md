# unit: shared/polymath_shared/_small-modules-3
anchor: shared/polymath_shared/retrieval_summaries.py:1-87

## purpose
Bundle of small shared modules: deterministic retrieval summaries and their ids (retrieval_summaries.py), scientific registry lookup, SEE-ALSO vector blending and skeleton-route budget doors, sparse BM25 vectors, startup config validation, store driver factories, subquery provenance receipts, summary envelopes/projection/workers, surface registry and type ontology. Consumed by orchestrator API routes, control, shared engines and workers. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| section_retrieval_summary | def | (children, *, parent_id, background, facts) -> (summary, sentences) | shared/polymath_shared/retrieval_summaries.py:50-60 | unit importers |
| document_retrieval_summary | def | (parents, *, doc_id, profile, facts) -> (summary, provenance) | shared/polymath_shared/retrieval_summaries.py:63-76 | unit importers |
| summary_id | def | (kind, source_id, summary_text) -> str (`"summ_" + content_hash`) | shared/polymath_shared/retrieval_summaries.py:79-86 | unit importers |
| load_registries | def | () -> dict[str, dict[str, str]] (lru_cache) | shared/polymath_shared/scientific_registries.py:24-39 | — |
| registry_lookup | def | (surface) -> dict or None | shared/polymath_shared/scientific_registries.py:42-44 | — |
| enabled / blend / blend_rows | def | blend(q_vec, item_vec, alpha=0.5) -> unit vec; blend_rows(items, item_vectors, *, question_vector, search_children, alpha=0.5, children_per_item=4) -> (rows, trace) | shared/polymath_shared/seealso_blend.py:28-79 | — |
| apply_skeleton_routes | def | (budget, *, mode, plan, env) -> new budget | shared/polymath_shared/skeleton_routes.py:68-114 | unit importers |
| token_index / tokenize / sparse_vector | def | token_index(token) -> int; tokenize(text) -> list[str]; sparse_vector(text) -> (indices, values) | shared/polymath_shared/sparse_bm25.py:27-45 | — |
| StartupContractError / validate_postgres / validate_startup | class/def | (code, detail); (dsn, *, timeout=5.0) -> None; (settings) -> report dict | shared/polymath_shared/startup_contract.py:45-100 | orchestrator/orchestrator/main.py |
| GraphBackendUnavailable / neo4j_driver / qdrant_client | class/def | () -> Neo4jDriver; (timeout=60.0) -> QdrantClient | shared/polymath_shared/stores.py:19-37 | unit importers |
| annotate_subquery_provenance | def | (plan, scout) -> receipt block | shared/polymath_shared/subquery_provenance.py:34-93 | unit importers |
| q0_preserved / provenance_complete / provenance_completeness | def | (plan) -> bool / bool / float | shared/polymath_shared/subquery_provenance.py:96-118 | — |
| build_envelope / validate_envelope | def | (derived_from, payload, version, model, prompt_version) -> envelope; (envelope) -> problems | shared/polymath_shared/summary_layer.py:24-51 | — |
| point_id / project_summary_points / project_navigation_edges / snapshot_projections | def | (corpus_id, artifact_id) -> UUID-shaped id; project into Qdrant/Neo4j | shared/polymath_shared/summary_projection.py:18-105 | workers |
| build_document_summary / build_corpus_summary / vocabulary_admission | def | per docstrings; inputs are envelopes, never raw text | shared/polymath_shared/summary_workers.py:11-117 | — |
| SurfacePolicy / group_surfaces / graph_policy | class/def | group_surfaces(group); graph_policy(kind) -> 'off' or 'resolve_on_use' (default 'off') | shared/polymath_shared/surface_registry.py:31-91 | skeleton_routes.py:40-44 |
| ontology / concrete_leaves / expand_type / validate_closure / expand_signature | def | per docstrings; closure: every canonical type covered exactly once | shared/polymath_shared/type_ontology.py:27-93 | — |

Unit-level importers (FACTS, per-module split unknown): `control/control/generation_swap.py`, `orchestrator/orchestrator/api/{ask,chat_retrieval,fast,graph_browse,hybrid,retrieve,ui}.py`, `orchestrator/orchestrator/main.py`, `shared/polymath_shared/{candidate_engine,corpus_mapping,query_intent,summary_runtime,parent_summary}.py`, `shared/polymath_shared/conformance/discovery.py`, `shared/polymath_shared/document_profile/{profile_atom,projection}.py`, `workers/workers/{profile_worker,project_canonical_worker,project_neo4j_worker,project_qdrant_worker,verify_worker}.py`.

## contracts

**apply_skeleton_routes** — shared/polymath_shared/skeleton_routes.py:68-114
- in: `budget`, `mode` (default `"HYBRID"` when empty), optional `plan`, optional `env` (defaults to `os.environ`).
- pre: `enabled(env)` must be `"1"` or budget returns unchanged; `mode in _SKIP_MODES` (`FAST`/`VECTOR`/`GNN`) returns unchanged.
- out: a NEW budget via `dataclasses.replace`; input never mutated; overrides applied only for attrs the budget already has (`hasattr` filter).
- post (mode doors): `seealso_fanout_enabled` on for GRAPH/WILDCARD or when plan has PROFILE/BRIDGE-origin queries; `doc_steer_kinds` non-empty only if `DOC_STEER_FLAG=="1"` AND `SEEALSO_BLEND_FLAG=="1"`; `route_prefix_seats` 3 for WILDCARD else 2; `contextual_judge` true when `JUDGE_FLAG=="1"` or (`"wildcard"` and mode WILDCARD).

**annotate_subquery_provenance** — shared/polymath_shared/subquery_provenance.py:34-93
- in: `(ChatPlan, ProfileScoutResult | None)`; pure, no I/O, no LLM.
- mutates `plan.queries` in place; records block on `plan.compiler["subquery_provenance"]` with contract `"subquery-provenance-v1"`.
- post: PRIMARY gets `role="direct"`, `origin="USER"`, empty `inspired_by_profile`; non-primary keeps only `doc_id`s the scout actually nominated; a surviving scout link flips `origin` USER→PROFILE.

**sparse_vector / tokenize** — shared/polymath_shared/sparse_bm25.py:6-45
- pre: the tokenizer IS the contract — index-side and query-side must import THIS `tokenize`; drift silently zeroes recall.
- out: sorted `(indices, values)` with `{token_index: tf}`; token_index = blake2b-64 big-endian mod `2**31`.

**validate_postgres** — shared/polymath_shared/startup_contract.py:55-88
- pre: non-empty DSN.
- post: opens+closes a psycopg connection with the given credentials; never echoes the DSN; raises `StartupContractError` with codes `POSTGRES_CONFIG_MISSING`, `POSTGRES_DRIVER_MISSING`, `POSTGRES_AUTH_FAILED`, `POSTGRES_UNREACHABLE`.

## effect surface
- Files read: `resources/registries/scientific-registries.yaml` (scientific_registries.py:19-20, 26); `.env` existence probe at repo root (startup_contract.py:37, 41).
- Network: `psycopg.connect` (startup_contract.py:73); Neo4j `GraphDatabase.driver` (stores.py:30-33); `QdrantClient` (stores.py:36-37); Qdrant point projection (summary_projection.py:31-58); Neo4j edge writes (summary_projection.py:69-89).
- Postgres tables: none read/written by this unit (FACTS `tables_read`/`tables_written` empty); Postgres is only connectivity-tested.
- Env flags (name = default): `POLYMATH_CHAT_SEEALSO_BLEND = '0'` (seealso_blend.py:29; skeleton_routes.py:89, 92); `POLYMATH_CHAT_SKELETON_ROUTES = '0'` (skeleton_routes.py:65); `POLYMATH_CHAT_SKELETON_PROBES = '0'` (skeleton_routes.py:105); `POLYMATH_CHAT_PROBE_GATE = '0'` (skeleton_routes.py:107); `POLYMATH_CHAT_CONTEXTUAL_JUDGE = '0'` (skeleton_routes.py:99); `POLYMATH_CHAT_DOC_STEER = '0'` (skeleton_routes.py:92); `POLYMATH_PG_DSN = None` (startup_contract.py:38-39).

## invariants
- INVARIANT: token_index(token) < 2**31 — sparse_bm25.py:27-29 [DERIVED]; fails-if: indices leave the sparse-vector integer range.
- INVARIANT: tokenize keeps only tokens with len >= 2 — sparse_bm25.py:32-33 [DERIVED]; fails-if: index/query tokenizers diverge → silent recall zeroing (sparse_bm25.py:6-8).
- INVARIANT: `blend` output is unit-length for any alpha in [0,1] (clamped) — seealso_blend.py:33-39 [DERIVED]; fails-if: a longer side dominates the probe.
- INVARIANT: q0_preserved ⇔ exactly 1 PRIMARY with `role="direct"` and no scout derivation — subquery_provenance.py:96-105 [DERIVED]; fails-if: receipt reports `q0_preserved: false`.
- INVARIANT: `doc_steer_kinds` non-empty only when DOC_STEER_FLAG=="1" AND SEEALSO_BLEND_FLAG=="1" — skeleton_routes.py:91-92 [DERIVED]; fails-if: steer lines run without the blend lane they ride.
- INVARIANT: `route_prefix_seats == 3` iff mode=="WILDCARD" else 2 — skeleton_routes.py:95 [DERIVED].
- INVARIANT: `summary_id` hashes `{"kind", "source", "contract": "retrieval-summary-v3", "text"}` — retrieval_summaries.py:81-86 [DERIVED]; fails-if: ids from different contract versions collide.
- INVARIANT: apply_skeleton_routes returns a new object; input budget fields unchanged — skeleton_routes.py:68-69, 114 [DERIVED]; fails-if: callers holding the old budget see doors half-open.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now` summary_layer.py:40; file read: scientific_registries.py:26; network: stores.py:30-37, startup_contract.py:73, summary_projection.py:31-105). Pure modules: skeleton_routes.py:33 ("Pure: no I/O"), subquery_provenance.py:18-19 ("Pure ... No I/O, no LLM"), seealso_blend (search injected by caller).
idempotency: SAFE — annotate_subquery_provenance documented idempotent for the same scout (subquery_provenance.py:38-39); apply_skeleton_routes non-mutating (skeleton_routes.py:69). summary_projection upserts are keyed by stable `point_id(corpus_id, artifact_id)` — [INFERRED] point-keyed upserts repeat cleanly.

## failure behaviour
- seealso_blend.py:61 — Exception from `search_children` SWALLOWED (`continue`): one failed probe drops only its item; caller sees fewer rows and a thinner `trace`, no error.
- startup_contract.py:68 — psycopg import failure handled: raise `StartupContractError("POSTGRES_DRIVER_MISSING", ...)`.
- startup_contract.py:73-86 — connect failure handled (assign, if, raise): message containing "authentication failed" → `POSTGRES_AUTH_FAILED`, else `POSTGRES_UNREACHABLE`; the DSN is never echoed because it carries the password.
- stores.py:19-25 — `GraphBackendUnavailable`: a Neo4j outage must NEVER surface as an empty expansion; query routes translate it into 502 `graph_backend_unavailable`.
- StartupContractError carries machine-readable `code` and `detail` (startup_contract.py:49-52).

## dumb-code flags
- `document_retrieval_summary` accepts `profile` but never passes it to `compile_document` — unused parameter — retrieval_summaries.py:63-76 [DERIVED].
- `"POLYMATH_CHAT_SEEALSO_BLEND"` literal defined twice in the unit: `FLAG` (seealso_blend.py:25) and `SEEALSO_BLEND_FLAG` (skeleton_routes.py:50) — drift risk [DERIVED].
- `blend_rows` over-fetches `children_per_item * 2` then keeps at most `children_per_item` — seealso_blend.py:60, 75-76 [DERIVED].
- `DOC_MIN_PER_PARENT = 1` and `DEDUPE_JACCARD = 0.8` defined at retrieval_summaries.py:46-47 with no use anywhere in this 87-line file [DERIVED].
- `hasattr` filter silently drops any override the budget class lacks — skeleton_routes.py:114 [DERIVED].
- `JUDGE_FLAG` is a stringly tri-state: `"0"`, `"1"`, `"wildcard"` — skeleton_routes.py:99 [DERIVED].
- PROBES door measured harmful in replay (displaced two cross-domain finds) and stays default OFF with code retained — skeleton_routes.py:21-27, 105-106 [DERIVED].

## refactor notes
- retrieval_summaries.py:28-40 re-exports the `summary_compiler` API (`noqa: F401`); importers resolve those names here — renaming breaks every consumer.
- The sparse tokenizer is a cross-process contract (sparse_bm25.py:6-8): index-side and query-side changes must ship together or recall silently zeroes.
- `summary_id`'s hash-input shape `{kind, source, contract, text}` is persisted identity — changing keys invalidates every stored summary id (retrieval_summaries.py:81-86).
- `SUMMARY_COLLECTIONS` (`concept_families` / `summary_documents` / `summary_parents`) and `NEO4J_NAVIGATION` edge list drive projections — renames break project_qdrant/project_neo4j workers (summary_projection.py:24, 61).
- The `"subquery-provenance-v1"` block is consumed by RETRIEVAL_RECEIPT (P11) and CANDIDATE_ENGINE per the module doc (subquery_provenance.py:19-20) — field changes ripple into receipts.
- Two identity schemes coexist: content-hash `summary_id` (no clock) vs `summary_layer` envelopes carrying `datetime.now` `created_at` — merging them changes both persisted formats (retrieval_summaries.py:79-86, summary_layer.py:40) [INFERRED].

## VERIFY
```verify
grep -Fq 'retrieval-summary-v3' shared/polymath_shared/retrieval_summaries.py
test "$(grep -c -F 'JUDGE_FLAG' shared/polymath_shared/skeleton_routes.py)" -ge 2
grep -Fq 'POLYMATH_CHAT_SEEALSO_BLEND' shared/polymath_shared/skeleton_routes.py
grep -Fq 'POSTGRES_AUTH_FAILED' shared/polymath_shared/startup_contract.py
grep -Fq 'subquery-provenance-v1' shared/polymath_shared/subquery_provenance.py
grep -Fq 'sparse-bm25-v1' shared/polymath_shared/sparse_bm25.py
grep -Fq 'GraphBackendUnavailable' shared/polymath_shared/stores.py
grep -Fq 'summary-envelope-v1' shared/polymath_shared/summary_layer.py
```
