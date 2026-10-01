# unit: shared/polymath_shared/_small-modules-3
anchor: shared/polymath_shared/retrieval_modes.py:1-115

## purpose
Batch of small shared modules: versioned retrieval-mode → plan mapping (retrieval_modes.py:1-11 [DERIVED]), deterministic routing summaries and their ids (retrieval_summaries.py:1-24 [DERIVED]), authoritative scientific registry lookup (scientific_registries.py:1-10 [DERIVED]), SEE ALSO question-blended probes (seealso_blend.py:1-18 [DERIVED]), mode-driven skeleton-door budget overrides (skeleton_routes.py:1-33 [DERIVED]), deterministic sparse BM25 vectors (sparse_bm25.py:1-14 [DERIVED]), startup precondition validation (startup_contract.py:1-26 [DERIVED]), plus store clients, subquery provenance, summary envelope/projection/workers layers, surface registry, and type ontology (FACTS symbols [DERIVED]). Consumed by the orchestrator API, control, and workers (FACTS.importers [DERIVED]).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| mode_plan | def | (mode: str) -> Pass1RetrievalPlan | retrieval_modes.py:45-49 [DERIVED] | — (unit importers) |
| hybrid_mode_plan | def | (mode: str) -> HybridRetrievalPlan | retrieval_modes.py:52-55 [DERIVED] | — |
| apply_latent | def | (plan, enabled: bool \| None) -> HybridRetrievalPlan | retrieval_modes.py:58-71 [DERIVED] | — |
| apply_utility | def | (plan, enabled: bool \| None) -> HybridRetrievalPlan | retrieval_modes.py:74-87 [DERIVED] | — |
| validate_mode | def | (mode: str \| None) -> str | retrieval_modes.py:107-114 [DERIVED] | — |
| section_retrieval_summary | def | (children, *, parent_id, background=None, facts=None) -> (str, list[dict]) | retrieval_summaries.py:50-60 [DERIVED] | — |
| document_retrieval_summary | def | (parents, *, doc_id, profile=None, facts=None) -> (str, list[dict]) | retrieval_summaries.py:63-76 [DERIVED] | — |
| summary_id | def | (kind, source_id, summary_text) -> str | retrieval_summaries.py:79-86 [DERIVED] | — |
| load_registries | def | () -> dict[str, dict[str, str]] | scientific_registries.py:23-39 [DERIVED] | — |
| registry_lookup | def | (surface) -> dict[str, str] \| None | scientific_registries.py:42-44 [DERIVED] | — |
| enabled | def | (env=None) -> bool | seealso_blend.py:28-29 [DERIVED] | — |
| blend | def | (question_vector, item_vector, alpha=0.5) -> list[float] | seealso_blend.py:32-39 [DERIVED] | — |
| blend_rows | def | (items, item_vectors, *, question_vector, search_children, alpha=0.5, children_per_item=4) -> (rows, trace) | seealso_blend.py:42-79 [DERIVED] | — |
| enabled | def | (env=None) -> bool | skeleton_routes.py:64-65 [DERIVED] | — |
| apply_skeleton_routes | def | (budget, *, mode, plan=None, env=None) -> budget | skeleton_routes.py:68-114 [DERIVED] | — |
| token_index | def | (token: str) -> int | sparse_bm25.py:27-29 [DERIVED] | — |
| tokenize | def | (text: str) -> list[str] | sparse_bm25.py:32-33 [DERIVED] | — |
| sparse_vector | def | (text: str) -> (list[int], list[float]) | sparse_bm25.py:36-45 [DERIVED] | — |
| StartupContractError | class | (code: str, detail: str); carries .code/.detail | startup_contract.py:45-52 [DERIVED] | — |
| validate_postgres | def | (dsn, *, timeout=5.0) -> None | startup_contract.py:55-88 [DERIVED] | — |
| validate_startup | def | (settings) -> None (raises) | startup_contract.py:91-100 [DERIVED] | — |
| GraphBackendUnavailable | class | typed graph-store failure | stores.py:19-25 [DERIVED] | — |
| neo4j_driver | def | () -> driver | stores.py:28-33 [DERIVED] | — |
| qdrant_client | def | (timeout) -> client | stores.py:36-37 [DERIVED] | — |
| annotate_subquery_provenance | def | (plan, scout) -> plan + receipt block | subquery_provenance.py:34-93 [DERIVED] | — |
| q0_preserved | def | (plan) -> bool | subquery_provenance.py:96-105 [DERIVED] | — |
| provenance_complete | def | (plan) -> bool | subquery_provenance.py:108-110 [DERIVED] | — |
| provenance_completeness | def | (plan) -> fraction (1.0 when none) | subquery_provenance.py:113-118 [DERIVED] | — |
| build_envelope | def | (derived_from, payload, version, model, prompt_version) -> envelope | summary_layer.py:24-42 [DERIVED] | — |
| validate_envelope | def | (envelope) -> problems | summary_layer.py:45-51 [DERIVED] | — |
| point_id | def | (corpus_id, artifact_id) -> UUID-shaped str | summary_projection.py:18-21 [DERIVED] | — |
| project_summary_points | def | (qdrant_client, corpus_id, items, embed, collection_for_type) | summary_projection.py:31-58 [DERIVED] | — |
| project_navigation_edges | def | (neo4j_session, corpus_id, edges) | summary_projection.py:69-89 [DERIVED] | — |
| snapshot_projections | def | (qdrant_client, collections, neo4j_session, nav_query) | summary_projection.py:92-105 [DERIVED] | — |
| build_document_summary | def | (document_id, title, parent_summaries, procedures, concepts) | summary_workers.py:11-56 [DERIVED] | — |
| build_corpus_summary | def | (corpus_id, document_summaries) | summary_workers.py:59-85 [DERIVED] | — |
| vocabulary_admission | def | (document_summaries, accepted_facts) | summary_workers.py:88-117 [DERIVED] | — |
| SurfacePolicy | class | surface policy holder | surface_registry.py:31-38 [DERIVED] | — |
| group_surfaces | def | (group) -> surface attrs | surface_registry.py:83-85 [DERIVED] | — |
| graph_policy | def | (kind) -> 'off' \| 'resolve_on_use' | surface_registry.py:88-91 [DERIVED] | — |
| ontology / node_names / concrete_leaves / expand_type / validate_closure / expand_signature | def | ontology access + type expansion/closure | type_ontology.py:27-93 [DERIVED] | — |

Unit-level importers (FACTS.importers [DERIVED]): orchestrator/orchestrator/api/{ask,chat,chat_retrieval,evidence,fast,graph,graph_browse,hybrid,retrieve,ui}.py, orchestrator/orchestrator/main.py, control/control/generation_swap.py, shared/polymath_shared/{candidate_engine,conformance/discovery,corpus_mapping,document_profile/profile_atom,document_profile/projection,parent_summary,query_intent,summary_runtime}.py, workers/workers/{profile_worker,project_canonical_worker,project_neo4j_worker,project_qdrant_worker,verify_worker}.py.

## contracts
- mode_plan: in `mode`; pre `mode == "FAST"`; out `PASS1_DEFAULT_PLAN`; any other mode raises `ValueError(f"mode {mode!r} has no pass-1 plan")` — retrieval_modes.py:45-49 [DERIVED]
- hybrid_mode_plan: pre `mode in ("HYBRID", "GRAPH")`; out `HYBRID_PROMOTED_PLAN = HybridRetrievalPlan(mmr_enabled=False, mmr_lambda=1.0)`; else ValueError — retrieval_modes.py:42,52-55 [DERIVED]
- validate_mode: `None` or `""` → `DEFAULT_MODE` (= `MODE_LEGACY`); `mode not in EXPOSED_MODES` → ValueError listing exposed modes — retrieval_modes.py:36,107-114 [DERIVED]
- apply_latent / apply_utility: `enabled=None` inherits from `get_settings().worker.latent_retrieval_enabled` / `evidence_utility_enabled` (default False via getattr); unchanged value returns same plan; else `replace(plan, ...)` — retrieval_modes.py:58-87 [DERIVED]
- blend: each side unit-normalized first; alpha clamped `[0.0, 1.0]`; output re-normalized — seealso_blend.py:32-39 [DERIVED]
- blend_rows: fetches `children_per_item * 2`, keeps `<= children_per_item` (default 4); dedupes on payload `chunk_id` across items; rows tagged `fanout_atom` and `seealso_blend = {item, from_doc, kind (default "SEEALSO")}`; empty text or `None` vector skips the item — seealso_blend.py:42-78 [DERIVED]
- apply_skeleton_routes: no-op when flag off or mode in `_SKIP_MODES`; returns a NEW budget via `dataclasses.replace`, "the input is never mutated"; overrides applied only for fields the budget has (`hasattr`) — skeleton_routes.py:68-114 [DERIVED]
- tokenize: lowercase, `[a-z0-9]+` runs, drop tokens with `len(t) < 2` — sparse_bm25.py:24,32-33 [DERIVED]
- token_index: blake2b `digest_size=8`, big-endian int, `% (2 ** 31)` — sparse_bm25.py:27-29 [DERIVED]
- sparse_vector: empty text → `([], [])`; indices sorted ascending; values are float tf — sparse_bm25.py:41-45 [DERIVED]
- summary_id: returns `"summ_" + content_hash({kind, source, contract, text})` with `contract = "retrieval-summary-v3"`; "no wall-clock metadata" — retrieval_summaries.py:42,79-86 [DERIVED]
- load_registries: `@lru_cache(maxsize=1)`; reads `resources/registries/scientific-registries.yaml`; keys are `surface.lower()`; source recorded as `registry:{section}:{source}` — scientific_registries.py:19-20,23-39 [DERIVED]
- registry_lookup: exact case-insensitive match, "never fuzzy, never frequency-based"; None on miss — scientific_registries.py:8-9,42-44 [DERIVED]
- validate_postgres: raises `StartupContractError` with codes `POSTGRES_CONFIG_MISSING`, `POSTGRES_DRIVER_MISSING`, `POSTGRES_AUTH_FAILED`; DSN never echoed ("it carries the password") — startup_contract.py:61-79 [DERIVED]
- graph_policy: returns `'off' | 'resolve_on_use'`, default `'off'` ("never a direct text edge") — surface_registry.py:88-91 [DERIVED]
- build_document_summary / build_corpus_summary: input is envelopes/payloads, "Never raw text" — summary_workers.py:11,59 [DERIVED]

## effect surface
- env flags read (default): `POLYMATH_CHAT_SEEALSO_BLEND` = '0' (seealso_blend.py:25,29; skeleton_routes.py:50,89), `POLYMATH_CHAT_SKELETON_ROUTES` = '0' (skeleton_routes.py:46,64-65), `POLYMATH_CHAT_SKELETON_PROBES` = '0' (skeleton_routes.py:48,105), `POLYMATH_CHAT_PROBE_GATE` = '0' (skeleton_routes.py:49,107), `POLYMATH_CHAT_CONTEXTUAL_JUDGE` = '0' (skeleton_routes.py:47,99), `POLYMATH_CHAT_DOC_STEER` = '0' (skeleton_routes.py:51,92), `POLYMATH_PG_DSN` = null (startup_contract.py:39) [DERIVED]
- files read: `resources/registries/scientific-registries.yaml` (scientific_registries.py:19-20); repo-root `.env` existence check (startup_contract.py:37-41); type ontology file via `_load(path, mtime)` (type_ontology.py:23-24) [DERIVED]
- network: `psycopg.connect(dsn, connect_timeout=timeout)` to Postgres (startup_contract.py:73); Neo4j driver / Qdrant client construction (stores.py:28-37) [DERIVED]
- Qdrant collections: `{"concept": "concept_families", "document": "summary_documents", "parent": "summary_parents"}` (summary_projection.py:24) [DERIVED]
- Neo4j edges: `Document-HAS_SUMMARY->DocumentSummary`, `Concept-SUPPORTED_BY->DocumentSummary`, `Fact-SUPPORTED_BY->Evidence` (summary_projection.py:61) [DERIVED]
- Postgres tables: none read/written (FACTS.tables_read/tables_written empty) [DERIVED]
- skeleton_routes is "Pure: no I/O" beyond env reads (skeleton_routes.py:33) [DERIVED]

## invariants
INVARIANT: GRAPH_DEFINITIONAL_MAX_SEEDS (2) < GRAPH_MAX_SEEDS (8); GRAPH_MAX_FACTS = 20 — retrieval_modes.py:94-95,100 [DERIVED]
  fails-if: definitional questions expand at full relational width, defeating MODE-COMPOSITION-V1.
INVARIANT: EXPOSED_MODES = (FAST, HYBRID, GRAPH, WILDCARD, GNN, LEGACY) and excludes MODE_VECTOR — retrieval_modes.py:33-34,104 [INFERRED: VECTOR defined at :104 but absent from the tuple; comment says chat routes map VECTOR → FAST themselves]
  fails-if: `validate_mode("VECTOR")` raises on a name the chat surfaces legitimately use.
INVARIANT: DEFAULT_MODE == MODE_LEGACY == "LEGACY"; empty/None mode resolves to it — retrieval_modes.py:36,107-109 [DERIVED]
  fails-if: every mode-omitting caller silently changes lanes on a default bump.
INVARIANT: production HYBRID = FAST + lexical with mmr_enabled=False, mmr_lambda=1.0 (relevance-only) — retrieval_modes.py:38-42 [DERIVED]
  fails-if: re-enabling MMR contradicts the R1D rejection verdict recorded in the comment.
INVARIANT: fetched per item == children_per_item * 2; kept per item <= children_per_item (4) — seealso_blend.py:60,74-75,43 [DERIVED]
  fails-if: dedupe starves items or over-fetch wastes probe budget.
INVARIANT: returned chunk_ids unique across items (shared `seen` set) — seealso_blend.py:54,66-68 [DERIVED]
  fails-if: duplicate evidence rows double-count one passage in fusion.
INVARIANT: doc_steer_kinds non-empty only when DOC_STEER_FLAG == "1" AND SEEALSO_BLEND_FLAG == "1" — skeleton_routes.py:90-92 [DERIVED]
  fails-if: doc steer runs without the blend it rides on.
INVARIANT: probe gate never applies when mode == "WILDCARD" — skeleton_routes.py:107 [DERIVED]
  fails-if: the "not-so-obvious" mode loses its non-obvious bridges (documented live decision).
INVARIANT: _SKIP_MODES = {"FAST", "VECTOR", "GNN"} get zero skeleton doors — skeleton_routes.py:60,74-75 [DERIVED]
  fails-if: FAST latency budget is blown by skeleton lanes.
INVARIANT: WILDCARD seats: route_prefix_seats=3 (else 2), compose_aspect_slots >= 6 (else 5), contextual_max_needs >= 6 (else 4), skeleton_probe_routes=7 (else 4) — skeleton_routes.py:95,98,103,106 [DERIVED]
  fails-if: seat counts drift from the measured WILDCARD depth configuration.
INVARIANT: min token length 2; index space 2^31; indices sorted ascending — sparse_bm25.py:29,33,44 [DERIVED]
  fails-if: index/query tokenizer mismatch "silently zeroes recall" (sparse_bm25.py:7-8).
INVARIANT: summary_id = "summ_" + hash over {kind, source, contract="retrieval-summary-v3", text} — retrieval_summaries.py:42,81-86 [DERIVED]
  fails-if: changing CONTRACT re-ids every stored summary without any content change.
INVARIANT: REQUIRED_FIELDS has 6 entries: artifact_id, input_hash, output_hash, version, derived_from, created_at — summary_layer.py:20 [DERIVED]
  fails-if: validate_envelope passes envelopes missing a provenance field.
INVARIANT: registry keys lowercase; lookup strips + lowercases the query — scientific_registries.py:35,44 [DERIVED]
  fails-if: case-variant surfaces miss the authoritative match.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now` in summary_layer.py:40 per FACTS.nondeterminism; network: Postgres connect startup_contract.py:73, Neo4j/Qdrant clients stores.py:28-37; env: seven POLYMATH_CHAT_* flags + POLYMATH_PG_DSN above; file reads: registries YAML scientific_registries.py:19-20, ontology type_ontology.py:23-24). Pure/deterministic core: mode mapping (retrieval_modes.py:45-55), sparse vectors (sparse_bm25.py:27-45), blend math (seealso_blend.py:32-39), skeleton overrides ("Pure: no I/O" skeleton_routes.py:33) [DERIVED]
idempotency: SAFE — apply_skeleton_routes returns a new budget, "the input is never mutated" (skeleton_routes.py:69,114); load_registries cached via `lru_cache(maxsize=1)` (scientific_registries.py:23); summary/point identities are content-derived ("Deterministic versioned identity (no wall-clock metadata)" retrieval_summaries.py:80; "Stable UUID-shaped point id" summary_projection.py:18-21), so re-projection targets the same ids [INFERRED: stable content-addressed ids make repeated writes overwrite rather than duplicate]

## failure behaviour
- blend_rows swallows any Exception per probe (`except Exception: ... continue`, `# noqa: BLE001`): one failed search drops only that item; caller sees fewer rows and no trace entry for it — seealso_blend.py:59-62 [DERIVED]
- validate_postgres: `POSTGRES_CONFIG_MISSING` on empty DSN (startup_contract.py:61-65), `POSTGRES_DRIVER_MISSING` on psycopg import failure (startup_contract.py:66-70, FACTS.fallbacks line 68 "handled: raise"), connect failure mapped to `POSTGRES_AUTH_FAILED` vs unreachable (startup_contract.py:73-79, FACTS.fallbacks line 74 "handled: assign, if, raise"); DSN is never included in the message — startup_contract.py:76 [DERIVED]
- validate_startup raises StartupContractError on the first failed precondition — startup_contract.py:91-100 [DERIVED]
- mode_plan / hybrid_mode_plan raise ValueError on unmapped modes — retrieval_modes.py:49,55 [DERIVED]
- validate_mode raises ValueError enumerating EXPOSED_MODES — retrieval_modes.py:110-113 [DERIVED]
- validate_envelope returns a problems list instead of raising — summary_layer.py:45-51 [DERIVED]
- GraphBackendUnavailable is the typed graph-store failure surface — stores.py:19-25 [DERIVED]

## dumb-code flags
- `"POLYMATH_CHAT_SEEALSO_BLEND"` literal lives in two modules: `FLAG` seealso_blend.py:25 and `SEEALSO_BLEND_FLAG` skeleton_routes.py:50 — rename one and the other orphans silently [INFERRED: same string, no shared constant]
- DEFAULT_MODE = MODE_LEGACY while the docstring calls FAST "the promoted Pass-1 semantic route" — the default disagrees with the promoted lane — retrieval_modes.py:3-4,36 [DERIVED]
- MODE_VECTOR is defined but excluded from EXPOSED_MODES; chat routes "map VECTOR → FAST themselves and stamp the truthful name" — retrieval_modes.py:101-104 [DERIVED]
- `_SKIP_MODES` contains `"VECTOR"`, a string that is not an EXPOSED_MODE — skeleton_routes.py:60 [DERIVED]
- `POLYMATH_CHAT_CONTEXTUAL_JUDGE` overloads `"1"` with the sentinel `"wildcard"` — skeleton_routes.py:99 [DERIVED]
- JUDGE_FLAG is read twice in one expression on line 99 (matches the duplicated FACTS.env entries at line 99) — skeleton_routes.py:99 [DERIVED]
- probe floor 0.2 appears in the docstring (skeleton_routes.py:31) while the code imports `DEFAULT_FLOOR` from probe_gate at line 112 — the operative number is not visible in this module — skeleton_routes.py:31,112 [DERIVED]
- fetch factor 2 in `children_per_item * 2` is unexplained magic — seealso_blend.py:60 [DERIVED]
- seat magic numbers 3/2, 6/5, 6/4, 7/4 hardcoded per mode — skeleton_routes.py:95,98,103,106 [DERIVED]
- DOC_STEER_KINDS excludes INVERSION for WILDCARD based on replay ("adding INVERSION made one worse") — a tuned constant from a one-session measurement — skeleton_routes.py:53-59 [DERIVED]

## refactor notes
- The tokenizer is the contract: "index-side and query-side must import THIS function; any drift silently zeroes recall" — sparse_bm25.py:6-8. Blast radius: every routing point and every query-side caller.
- One engine rule: production FAST and qualification both resolve `PASS1_DEFAULT_PLAN` through mode_plan; "no duplicate retrieval implementation exists" — retrieval_modes.py:8-10,45-49. A second FAST path violates the module's stated contract.
- retrieval_summaries re-exports the summary_compiler API (`COMPILER_CONTRACT`, `DOC_MAX_CHARS`, `DOC_MAX_SENTENCES`, `SECTION_MAX_CHARS`, `SECTION_MAX_SENTENCES`, `CompiledSummary`, `build_background`, `compile_document`, `compile_section`, `digest_variant`, `serialize`) under `# noqa: F401` — importers depend on this module path — retrieval_summaries.py:28-40 [DERIVED]
- summary_id hashes CONTRACT into identity; bumping `"retrieval-summary-v3"` re-ids every stored summary — retrieval_summaries.py:42,81-86 [DERIVED]
- apply_skeleton_routes filters overrides by `hasattr(budget, k)` — renaming a budget field silently drops that door instead of erroring — skeleton_routes.py:114 [INFERRED: hasattr guard skips unknown fields]
- The env flag names are a cross-module public contract (see duplicated FLAG literal); 25 importer modules listed in FACTS.importers must be grepped before any rename [INFERRED]
- Errors from validate_postgres must never contain the DSN ("it carries the password") — startup_contract.py:76 [DERIVED]
- HYBRID_PROMOTED_PLAN encodes the R1D qualification verdict (lexical promoted, MMR rejected); changing mmr values re-litigates a recorded decision — retrieval_modes.py:38-42 [DERIVED]

## VERIFY
```verify
grep -Fq 'MODE_WILDCARD = "WILDCARD"' shared/polymath_shared/retrieval_modes.py
grep -Fq 'HYBRID_PROMOTED_PLAN = HybridRetrievalPlan(mmr_enabled=False, mmr_lambda=1.0)' shared/polymath_shared/retrieval_modes.py
grep -Fq 'GRAPH_DEFINITIONAL_MAX_SEEDS = 2' shared/polymath_shared/retrieval_modes.py
test "$(grep -c -F 'POLYMATH_CHAT_SEEALSO_BLEND' shared/polymath_shared/skeleton_routes.py)" -ge 2
grep -Fq 'children_per_item * 2' shared/polymath_shared/seealso_blend.py
grep -Fq 'DEDUPE_JACCARD = 0.8' shared/polymath_shared/retrieval_summaries.py
! grep -Fq 'POLYMATH_CHAT_SKELETON_ROUTES' shared/polymath_shared/seealso_blend.py
grep -Fq 'conn = psycopg.connect(dsn, connect_timeout=timeout)' shared/polymath_shared/startup_contract.py
```
