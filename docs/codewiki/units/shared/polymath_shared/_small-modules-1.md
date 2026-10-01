# unit: shared/polymath_shared/_small-modules-1
anchor: shared/polymath_shared/__init__.py:1

## purpose
Shared kernel of the Polymath pipeline: pure deterministic gates (bridge structural admissibility, concept/entity split, generic classification), content-addressed identity hashing, acceptance-harness scoring, retrieval-funnel receipts, Postgres transaction helpers, and an experimental GNN parent-routing lane — shared/polymath_shared/__init__.py:1 [DERIVED] (package docstring points to the AGENTS.md process-role contract).
Consumed across the codebase: `control/*`, `orchestrator/*` (api + main), `workers/*`, and ~40 other `polymath_shared` modules (FACTS.importers) — shared/polymath_shared/__init__.py:1 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| entity_recall | def | (labels: dict, admitted_entities: list[str]) -> dict | acceptance_harness.py:15 | — |
| predicate_precision | def | (labels: dict, admitted_facts: list[dict]) -> dict | acceptance_harness.py:25 | — |
| event_recall | def | (labels: dict, admitted_events: list[dict]) -> dict | acceptance_harness.py:43 | — |
| evidence_support | def | (labels: dict, admitted_facts: list[dict]) -> dict | acceptance_harness.py:64 | — |
| score_acceptance | def | (labels, *, admitted_entities, admitted_facts, admitted_events) -> dict | acceptance_harness.py:86 | — |
| AdmissionVerdict | class | fields admissible: bool, reasons: list; .to_dict() | bridge_admission.py:49 | — |
| structural_bridge_admissibility | def | (path, root_query, *, duplicate_ceiling=0.8, min_content_tokens=2) -> AdmissionVerdict | bridge_admission.py:59 | — |
| admissible_bridge_paths | def | (lineage, **kw) -> list | bridge_admission.py:84 | — |
| annotate_admissibility | def | (lineage, **kw) -> dict | bridge_admission.py:91 | — |
| compound_head_nouns | def | () -> frozenset[str] | compound_heads.py:27 | concept_split.py:17-18 [DERIVED] |
| is_generic_head | def | (surface: str) -> bool | compound_heads.py:40 | concept_split.py:17-18 [DERIVED] |
| resolve_compound_heads | def | (spans: list[dict]) -> list[dict] | compound_heads.py:45 | — |
| strip_head_from_subject | def | (subject_surface, subject_entity_surface) -> bool | compound_heads.py:75 | — |
| classify_surface | def | (surface: str) -> 'concept' \| 'entity' | concept_split.py:27 | — |
| activations_to_concepts | def | (activations, *, max_concepts=8) -> list[Concept] | corpus_explore.py:28 | — |
| plan_corpus_explore_expansion | def | (plan, activations, *, generate, max_add=4, weight=0.55) -> dict | corpus_explore.py:47 | — |
| plan_with_corpus_map | def | (conn, scope, question) — "Deterministic scoped map consultation. Pure read; no writes." | corpus_map_planning.py:45 | — |
| get_pool | def | () -> pool | db.py:34 | — |
| tx | def | () — one transaction on the workflow authority; commits on clean exit | db.py:44 | — |
| advisory_lock | def | (conn, key) — lock key = content hash, not wall-clock | db.py:58 | — |
| compute_chunk_summary | def | (children, parents) — tier-filtered chunk row dicts | document_chunk_summary.py:18 | — |
| event_candidate | def | (predicate, subject_id, object_id, qualifiers, subject_surface, object_surface, agent_surface) -> candidate \| None | event_reification.py:37 | — |
| admit_event | def | (candidate) — "Deterministic promotion gate." | event_reification.py:62 | — |
| derive_extract_projection | def | (payload: dict) -> projection dict | extract_projection.py:61 | — |
| extract_projection_columns_for | def | (payload) -> dict \| None | extract_projection.py:77 | — |
| coverage_verdict | def | (stats, floor, drop_tolerance) -> verdict | extraction_coverage.py:33 | — |
| parse_frontmatter | def | (text) — flat `key: value` between first two `---` lines | frontmatter.py:22 | — |
| build_funnel | def | (lanes, union, pre_rerank, post_rerank, selected, cited, plan_version, query_ids) -> funnel receipt | funnel.py:39 | — |
| rank_at | def | (funnel, chunk_id) -> 1-based rank per stage \| None | funnel.py:84 | — |
| where_did_it_die | def | (funnel, chunk_id) -> death label | funnel.py:95 | — |
| compact | def | (funnel, max_chars) -> shrunken funnel | funnel.py:111 | — |
| funnel_from_trace | def | (trace, selected, cited, plan_version) -> funnel | funnel.py:130 | — |
| chunk_visible_sql | def | (chunks_alias, documents_alias) -> SQL visibility clause | generation.py:37 | — |
| hidden_generations | def | (conn, corpus_id) -> in-flight blue/green successor generations | generation.py:41 | — |
| is_blue_green_run | def | (conn, run_id) -> bool | generation.py:56 | — |
| GenericEvidence / GenericDecision | class | data classes, no methods | generic_classification.py:42,50 | — |
| classify_generic | def | (surface, tokens, has_identity_anchor) -> evidence \| None | generic_classification.py:71 | — |
| GnnRouteRefused | class | typed refusal: experimental collection ≠ live contract | gnn_route.py:33 | — |
| gnn_contract | def | (family, variant) -> contract | gnn_route.py:41 | — |
| collection_name | def | (embedding_contract, contract) -> `polymath_gnn_parent_<embedding_contract>_<gnn_contract>` | gnn_route.py:47 | — |
| verify_collection | def | (client, collection, expect_dim, embedding_contract) — refuses wrong dim/contract (G11) | gnn_route.py:53 | — |
| gnn_parent_search | def | (client, collection, qvec, corpus_id, limit, scope) -> parent nominations (G12) | gnn_route.py:75 | — |
| hydrate_original_children | def | (child_search, qvec, parents, corpus_id, per_parent, cap) | gnn_route.py:98 | — |
| route | def | (client, collection, child_search, qvec, corpus_id, parent_k, per_parent, cap, scope) — full query-time route, receipt on `trace.gnn` | gnn_route.py:123 | — |
| canonicalize / content_hash | def | (obj) -> sha256 hex of canonical serialization | identity.py:16,28 | — |
| fact_id / evidence_id / entity_id | def | (predicate, subject_id, object_id, qualifiers) / (fact_id, doc_id, chunk_id, span_offsets, rule_id) / (core_type, normalized_surface, kb_id) | identity.py:33,38,43 | — |
| document_id / chunk_id / run_id | def | (normalized_bytes) / (doc_id, chunk_index, chunk_text) / (corpus_id, intake_payload) | identity.py:50,55,59 | — |
| receipt_id / attempt_id / contract_hash | def | (run, stage, contract_hash) / (run, stage, contract_hash) / (schema_version, frozen_params) | identity.py:65,70,88 | — |
| owner_id / lease_key | def | (hostname, role, started_at_iso) / () | identity.py:74,84 | — |
| normalize_document_bytes | def | (raw, strip_bom, normalize_crlf) | identity.py:95 | — |
| document_fingerprint / artifact_hash | def | (normalized_content, corpus_id) / (document_fingerprint, ingestion_contract_version, extraction_version, semantic_bundle_version) | identity_model.py:17,23 | — |
| entity_key / fact_key | def | (corpus_id, normalized_name, entity_type) / (subject_id, predicate, object_id) | identity_model.py:35,41 | — |
| canonical_intake_payload | def | (corpus_id, source_name, media_type, content_b64, config, content_ref) — hash defines run identity | intake_submission.py:24 | — |
| submit_intake | def | (conn, canonical_payload) — one run row + intake.v1 outbox event in a single transaction | intake_submission.py:60 | — |

Per-symbol importer mapping is not in FACTS; treat every row as package-wide (FACTS.importers).

## contracts

**structural_bridge_admissibility** — bridge_admission.py:59-81
- in: one `DiscoveryPath` + `root_query` — bridge_admission.py:59 [DERIVED]
- out: `AdmissionVerdict(admissible=not reasons, reasons=[...])` — bridge_admission.py:81 [DERIVED]
- pre: path with `is_primary`, `origin_query`, `query_id`, `origin` attributes — bridge_admission.py:64-70 [DERIVED]
- post: reasons may contain exactly `not_a_bridge_path`, `empty_origin_query`, `ungrounded_origin`, `boilerplate_or_too_short`, `duplicate_of_q0`, `no_distinct_content` — bridge_admission.py:65-80 [DERIVED]; admissible ⇒ token-Jaccard(origin_query, q0) < 0.8 AND origin introduces ≥1 content token beyond q0 AND ≥2 content tokens — bridge_admission.py:30,73-80 [DERIVED]
- scope: structural only, never a relevance judgment (that is C4) — bridge_admission.py:4-7,62 [DERIVED]

**classify_surface** — concept_split.py:27-44
- out: literal `'concept'` or `'entity'` — concept_split.py:28 [DERIVED]
- ordered rules: any digit token OR all-caps token (len ≥ 2) → entity; head token (last word, `removesuffix("s")`) in compound-head allowlist with all-lowercase predecessors → concept; single lowercase token → concept iff in allowlist; default entity — concept_split.py:30-44 [DERIVED]
- gated by `POLYMATH_CONCEPT_SPLIT=1` upstream, before entity admission — concept_split.py:9 [DERIVED]

**resolve_compound_heads** — compound_heads.py:45-72
- in: spans `[{text, start, end, core_type?, score?}, ...]` in document order — compound_heads.py:49 [DERIVED]
- post: generic head dropped when previous kept span abuts with `0 <= gap <= 1`; bare generic head dropped; all other spans unchanged — compound_heads.py:64-72 [DERIVED]

**entity_recall / predicate_precision / evidence_support** — acceptance_harness.py:15-83
- all comparisons over `_norm` (strip+lower) triples/pairs — acceptance_harness.py:11-12,28-30,67-69 [DERIVED]
- scores `round(x, 4)`; `None` when denominator empty (no expected entities / no admitted facts / no matched facts) — acceptance_harness.py:20-21,36-38,87 [DERIVED]
- evidence_support counts a matched fact supported iff provenance has `trigger_surface`, `evidence_start is not None`, or `chunk_id` — acceptance_harness.py:77-80 [DERIVED]
- score_acceptance emits `"contract": "acceptance-harness-v1"` — acceptance_harness.py:90 [DERIVED]

**plan_corpus_explore_expansion** — corpus_explore.py:47-90
- pre: ≥1 `PRIMARY` query in plan, else returns `{"added": 0, "eligible": False, "reason": "no_primary"}` (q0 authority) — corpus_explore.py:58-61 [DERIVED]
- the single model call is the injected `generate` — corpus_explore.py:47,50 [DERIVED]
- post: additive append to `plan.queries`, text-deduped case-insensitively against all existing queries; diag stashed at `plan.compiler['corpus_explore_expansion']` — corpus_explore.py:79-90,54-55 [DERIVED]
- concepts derived from activations: key=`concept_id`, label whitespace-normalized and truncated `[:200]`, source=first `source_document_ids` entry — corpus_explore.py:34-40 [DERIVED]

**identity layer** — identity.py
- fact_id is "the canonical fact identity. See ADR-0001 §17" — identity.py:33 [DERIVED]; evidence_id "re-derived, never duplicated" — identity.py:38 [DERIVED]; entity_id two-tier KB-linked or surface-derived — identity.py:43 [DERIVED]; document_id = sha256 of normalized bytes so identical re-uploads map to one document — identity.py:50 [DERIVED]; run_id replay-stable over a corpus — identity.py:59 [DERIVED]; receipt_id = idempotency key of one stage attempt — identity.py:65 [DERIVED]; owner_id is the persistent control-plane owner (ISSUES_REPORT §1.1 fix) — identity.py:74 [DERIVED]

**tx / advisory_lock** — db.py:44,58
- tx: commits on clean exit; one transaction on the workflow authority — db.py:44 [DERIVED]
- advisory_lock key is a content hash, not a wall-clock field — db.py:58 [DERIVED]

**submit_intake** — intake_submission.py:60
- writes one run row + `intake.v1` outbox event in a single transaction; canonical payload hash defines run identity — intake_submission.py:60,24 [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `hr` (in visibility SQL) | generation.py:26 [DERIVED] |
| Postgres read | `concept_aliases`, `concept_families`, `corpus_summaries`, `metadata`, `runs` (FACTS.tables_read) | corpus_map_planning.py:45-136 [INFERRED: the "deterministic scoped map consultation, pure read" is the only FACTS doc claiming reads] |
| Postgres write | `runs`, `outbox_events` (FACTS.tables_written) | intake_submission.py:60 [DERIVED] |
| Qdrant collection | prefix `polymath_gnn_parent`, name pattern `polymath_gnn_parent_<embedding_contract>_<gnn_contract>` | gnn_route.py:24,47 [DERIVED] |
| File read | `config/ontology/scientific-predicate-ontology-v2.yaml` via `parents[2]`, cached `lru_cache(maxsize=1)` | compound_heads.py:23,26-27 [DERIVED] |
| Env | `POLYMATH_GNN_FAMILY` (default `FAMILY_M1`) | gnn_route.py:30 [DERIVED] |
| Env (upstream gate) | `POLYMATH_CONCEPT_SPLIT=1` enables concept routing | concept_split.py:9 [DERIVED] |
| Clock | `time.perf_counter` ×2 (route latency) | gnn_route.py:126,132 [DERIVED] |
| Model call | injected `generate` in `compile_bridges` — the ONE model call in corpus_explore | corpus_explore.py:47,50,76 [DERIVED] |

## invariants

INVARIANT: token-Jaccard(origin_query, q0) < 0.8 for any admissible bridge — bridge_admission.py:30,77-78 [DERIVED]
  fails-if: paraphrases of q0 get admitted as bridges, duplicating the primary lane.
INVARIANT: distinct content tokens of origin_query >= 2 — bridge_admission.py:32,73-74 [DERIVED]
  fails-if: boilerplate/one-word subqueries become bridge candidates.
INVARIANT: len(STAGES) == len(DEATHS) == 6 (`retrieved…cited` vs `NEVER_RETRIEVED…CITED`) — funnel.py:23-24 [DERIVED]
  fails-if: `rank_at`/`where_did_it_die` stage↔death alignment breaks.
INVARIANT: STAGE_CAP == 100 per funnel stage — funnel.py:22 [DERIVED]
  fails-if: receipts silently drop per-stage ids beyond cap during compact.
INVARIANT: IN_FLIGHT_STATUSES == `('intake','reconciling','degraded')` literal embedded in CHUNK_VISIBLE_SQL — generation.py:23,26 [DERIVED]
  fails-if: in-flight blue/green successor chunks leak into retrieval.
INVARIANT: CORPUS_EXPLORE_WEIGHT == BRIDGE_SUBQUERY_WEIGHT == 0.55 — corpus_explore.py:23 [DERIVED]
  fails-if: explore subqueries outrank the bridge fusion class relative to C5 admission.
INVARIANT: set(EVENT_PREDICATES) == set(keys(_EVENT_TYPE_BY_PREDICATE)) — event_reification.py:18,23 [INFERRED: FACTS value lists overlap and predicate→type mapping must be total]
  fails-if: an accepted event predicate has no event type and promotion fails.
INVARIANT: compound-modifier gap window 0 <= gap <= 1 char — compound_heads.py:68-69 [DERIVED]
  fails-if: "BERT  model" (double space) head is kept and anchors a relation.
INVARIANT: every acceptance score uses round(x, 4) — acceptance_harness.py:20,39,60,87 [DERIVED]
  fails-if: score comparison thresholds mis-align across metrics.
INVARIANT: evidence_id is re-derived from (fact_id, doc_id, chunk_id, span_offsets, rule_id), never duplicated — identity.py:38-40 [DERIVED]
  fails-if: duplicate evidence rows break the idempotency key of stage attempts.

## determinism & idempotency
determinism: DETERMINISTIC for the pure gates/scoring/identity modules (no clock/random/network in acceptance_harness.py, bridge_admission.py, compound_heads.py, concept_split.py — full SOURCE shows no such calls); NONDETERMINISTIC elements: `time.perf_counter` — gnn_route.py:126,132 [DERIVED]; injected model `generate` — corpus_explore.py:47 [DERIVED]; env flag `POLYMATH_GNN_FAMILY` — gnn_route.py:30 [DERIVED]; DB pool/transactions — db.py:34,44 [DERIVED].
idempotency: SAFE — identity layer is content-hash keyed (document_id from normalized bytes, identity.py:50; run_id replay-stable, identity.py:59; receipt_id as stage idempotency key, identity.py:65) and submit_intake writes run + outbox in one transaction (intake_submission.py:60) [DERIVED].

## failure behaviour
- corpus_explore.py:105 — `Exception` SWALLOWED with `pass` (diag stash write); caller sees the returned diag, never the stash error — FACTS.fallbacks [DERIVED].
- db.py:52 — `BaseException` handled then re-raised (`raise`); caller sees the original exception — FACTS.fallbacks [DERIVED].
- gnn_route.py:57 — `Exception` handled with `raise` (inside verify_collection, lines 53-72); typed refusal class `GnnRouteRefused` documented as "never a fallback" — gnn_route.py:33,53-57 [DERIVED].
- intake_submission.py:70 — `Exception` handled with `raise`; the run+outbox write fails atomically — FACTS.fallbacks [DERIVED].
- extract_projection.py:45 — `_int_or_none` is "safe, never-raising": a malformed stat reads as `None` — extract_projection.py:45 [DERIVED].
- event_reification.py:37 — `event_candidate` returns `None` (not an exception) when an accepted fact is not event-eligible — event_reification.py:37 [DERIVED].

## dumb-code flags
- Dead branch: `event_recall` computes `hit = sum(...)` at acceptance_harness.py:49-51, then unconditionally overwrites with `hit = 0` and a second loop at acceptance_harness.py:54-58 — first computation is dead [DERIVED].
- Duplicated helper: `_norm` defined in both acceptance_harness.py:11 and corpus_map_planning.py:34 (FACTS symbols) [DERIVED].
- Duplicated literal: `0.55` in corpus_explore.py:23 mirrors `BRIDGE_SUBQUERY_WEIGHT` defined outside this unit (comment at corpus_explore.py:23) — two places to update [DERIVED].
- Duplicated literals: status list `intake/reconciling/degraded` appears both as `IN_FLIGHT_STATUSES` and inside the `CHUNK_VISIBLE_SQL` string — generation.py:23,26 [DERIVED].
- Magic numbers: `[:200]` label truncation — corpus_explore.py:40 [DERIVED]; `len(t) > 2` token floor — bridge_admission.py:44-45 [DERIVED]; `DROP_TOLERANCE = 0.1` — extraction_coverage.py:30 [DERIVED].
- Inline stopword blob `_STOP` hard-coded in code, not config — bridge_admission.py:36-39 [DERIVED].
- `lru_cache(maxsize=1)` on a YAML file read: ontology edits during a process lifetime are invisible — compound_heads.py:26-27 [INFERRED: cache has no invalidation].

## refactor notes
- identity.py hash functions are the system-wide idempotency keys (facts, evidence, documents, runs, receipts); importers include receipts.py, execution.py, identity_allocation.py and all workers (FACTS.importers) — changing `canonicalize` (identity.py:16) invalidates every stored id.
- Reason strings from `structural_bridge_admissibility` and `AdmissionVerdict.to_dict` are receipt vocabulary consumed downstream; renaming them breaks receipt consumers — bridge_admission.py:55-56,65-80 [DERIVED].
- `CHUNK_VISIBLE_SQL` is templated with `{d}` placeholders — callers pass table aliases; status changes must edit both generation.py:23 and generation.py:26.
- Contract/version strings compared downstream: `acceptance-harness-v1` (acceptance_harness.py:90), `retrieval-funnel-v1` (funnel.py:21), `gnn-route-v1` (gnn_route.py:21), `generic-classification-v1` (generic_classification.py:31), `extraction-coverage-v1` (extraction_coverage.py:17), `corpus-map-planning-v1` (corpus_map_planning.py:31) — FACTS.constants [DERIVED].
- Ontology YAML path is hard-coded via `Path(__file__).resolve().parents[2]` — moving `config/ontology/` breaks `compound_head_nouns`, `is_generic_head`, `classify_surface`, and `resolve_compound_heads` — compound_heads.py:23 [DERIVED].
- `POLYMATH_CONCEPT_SPLIT` gate routes surfaces to the concept layer before entity admission; removing `classify_surface` changes durable entity identity — concept_split.py:9 [DERIVED].
- GNN collections are isolated from production by name pattern `polymath_gnn_parent_<embedding_contract>_<gnn_contract>`; keep `verify_collection` in the path or wrong-contract collections get queried — gnn_route.py:47,53 [DERIVED].

## VERIFY
```verify
grep -Fq 'DUPLICATE_Q0_CEILING = 0.8' shared/polymath_shared/bridge_admission.py
grep -Fq 'hit = 0' shared/polymath_shared/acceptance_harness.py
grep -Fq 'CORPUS_EXPLORE_WEIGHT = 0.55' shared/polymath_shared/corpus_explore.py
grep -Fq 'STAGE_CAP = 100' shared/polymath_shared/funnel.py
grep -Fq 'POLYMATH_GNN_FAMILY' shared/polymath_shared/gnn_route.py
grep -Fq 'scientific-predicate-ontology-v2.yaml' shared/polymath_shared/compound_heads.py
grep -Fq 'acceptance-harness-v1' shared/polymath_shared/acceptance_harness.py
test "$(grep -c -F 'time.perf_counter' shared/polymath_shared/gnn_route.py)" -ge 2
```
