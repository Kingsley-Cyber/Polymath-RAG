# unit: shared/polymath_shared/document_profile/projection.py
anchor: shared/polymath_shared/document_profile/projection.py:1-315
## purpose
Step 4 of DOCUMENT-PROFILE-V1: projects a compiled document profile into its own Qdrant collection (`polymath_document_profiles_<embedding contract>`) as one multi-representation point per document — dense `title`/`identity`/`theme`, multivectors `questions`/`searches`/`theories`/`concepts`/`seealso` — plus F4 per-section points for giant documents. shared/polymath_shared/document_profile/projection.py:1-11 [DERIVED]
Consumed by the retrieval lanes (RRF nomination, "the S8/S9 door") and the doc-profile worker; both embedder and Qdrant client are injected. shared/polymath_shared/document_profile/projection.py:6-7, 53-65 [DERIVED]
## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| collection_name | def | (embedding_contract_id: str) -> str | shared/polymath_shared/document_profile/projection.py:39-40 | — |
| point_id | def | (doc_id: str) -> str | shared/polymath_shared/document_profile/projection.py:43-45 | — |
| section_point_id | def | (doc_id: str, section_key: str) -> str | shared/polymath_shared/document_profile/projection.py:48-50 | — |
| profile_nominate | def | (client, collection, query_vec, corpus_id, k=8, *, surfaces=ANSWER_SURFACES, scope=None) -> list[str] | shared/polymath_shared/document_profile/projection.py:53-95 | — |
| projection_key | def | (*, source_doc_hash, schema_version, prompt_version, embedding_contract_id) -> str | shared/polymath_shared/document_profile/projection.py:98-101 | — |
| vectors_config | def | (dim: int) -> dict[str, Any] | shared/polymath_shared/document_profile/projection.py:104-111 | — |
| ensure_collection | def | (client, name: str, dim: int) -> bool | shared/polymath_shared/document_profile/projection.py:114-119 | — |
| texts_to_embed | def | (title: str, representations: dict) -> list[tuple[str, int or None, str]] | shared/polymath_shared/document_profile/projection.py:122-136 | — |
| build_point_vectors | def | (batch, vectors: list[list[float]]) -> dict[str, Any] | shared/polymath_shared/document_profile/projection.py:139-149 | — |
| section_payload | def | (section: dict) -> dict[str, Any] | shared/polymath_shared/document_profile/projection.py:152-162 | — |
| project_profile | def | (client, *, embed, embedding_contract_id, dim, doc_id, corpus_id, title, representations, payload_extra=None, existing_surfaces=None, force=False, source_doc_hash, schema_version, prompt_version, compiled_hash, section=None, input_hash=None) -> dict | shared/polymath_shared/document_profile/projection.py:165-219 | — |
| has_required_vectors | def | (receipt: dict) -> tuple[bool, list[str]] | shared/polymath_shared/document_profile/projection.py:222-232 | — |
| fetch_existing_point | def | (client, embedding_contract_id, doc_id, *, section_key=None, fields=EXISTING_POINT_FIELDS) -> dict or None | shared/polymath_shared/document_profile/projection.py:240-255 | — |
| fetch_existing_surfaces | def | (client, embedding_contract_id, doc_id, *, section_key=None) -> dict[str, int] or None | shared/polymath_shared/document_profile/projection.py:258-268 | — |
| list_section_points | def | (client, embedding_contract_id, doc_id, *, fields=EXISTING_POINT_FIELDS) -> dict[str, dict] | shared/polymath_shared/document_profile/projection.py:282-300 | — |
| purge_section_points | def | (client, embedding_contract_id, doc_id, *, keep_keys=None) -> int | shared/polymath_shared/document_profile/projection.py:303-314 | — |

Module imported by: orchestrator/orchestrator/api/chat_retrieval.py, orchestrator/orchestrator/api/ui.py, shared/polymath_shared/resolution_lift_gather.py, workers/workers/doc_profile_worker.py (FACTS.importers).
## contracts
**profile_nominate** — in: query_vec, corpus_id, k=8, surfaces (default `ANSWER_SURFACES`), scope. pre: collection exists (caller's job; read-only query). out: ordered `doc_id` list, length ≤ k. post: document query filtered `must=[corpus], must_not=[scope==section]`; section query `must=[corpus, scope==section]` with fetch `max(1, int(k)) * NOMINATE_OVERFETCH`; each doc counted once at its best score; merge keeps document-query order on ties. shared/polymath_shared/document_profile/projection.py:53-95 [DERIVED]
**project_profile** — in: compiled representations + identity fields. pre: `texts_to_embed` must yield ≥ 1 item else `ValueError`. out: receipt dict (no vectors: counts, hashes, collection, point id, `kept_last_known_good`, `selection`). post: when `_select(...).replace` is False, no upsert happens, `projection_hash` is None, `vectors` is {}. Otherwise point upserted `wait=True`. shared/polymath_shared/document_profile/projection.py:165-219 [DERIVED]
**build_point_vectors** — pre: `len(batch) == len(vectors)` else `ValueError`. post: idx None → single vector per surface; idx set → appended to a list (multivector). shared/polymath_shared/document_profile/projection.py:139-149 [DERIVED]
**purge_section_points** — out: number of points deleted; `keep_keys` excludes those keys from deletion. Idempotent: second call returns 0. shared/polymath_shared/document_profile/projection.py:303-314 [DERIVED]
**has_required_vectors** — post: True iff `identity` and `theme` and (`questions` or `searches`) counts are non-zero; else missing-tag list from `{"identity_vector","theme_vector","query_hook_vector"}`. shared/polymath_shared/document_profile/projection.py:222-232 [DERIVED]
## effect surface
Qdrant collection `polymath_document_profiles_<embedding_contract_id>` (prefix constant at shared/polymath_shared/document_profile/projection.py:25, name built at :39-40). Ops: `create_collection` :118, `upsert` wait=True :210, `query_points` RRF-fused :76-77, `retrieve` :249, `scroll` limit=256 :291-292, `count` exact=True :312, `delete` FilterSelector wait=True :314, `collection_exists` :116, :246, :286, :308. [DERIVED]
Postgres: none (FACTS.tables_read/tables_written empty). No files, subprocesses, or env flags visible.
## invariants
INVARIANT: point id == `uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:doc_profile:{doc_id}")` — shared/polymath_shared/document_profile/projection.py:44-45 [DERIVED]
  fails-if: a rebuilt document creates a second point instead of replacing; nomination sees stale + new copies of the same doc.
INVARIANT: section point id == uuid5 over `f"polymath:doc_profile:{doc_id}#section:{section_key}"` — shared/polymath_shared/document_profile/projection.py:49-50 [DERIVED]
  fails-if: rebuilt sections accumulate orphan points that `purge_section_points` then "cleans" while live ones linger.
INVARIANT: section-query depth == `max(1, int(k)) * NOMINATE_OVERFETCH` with `NOMINATE_OVERFETCH = 4` — shared/polymath_shared/document_profile/projection.py:36, 83 [DERIVED]
  fails-if: a giant's sections crowd out other documents or vote more than once (the F4 goal stated at :33-36).
INVARIANT: len(embedder output) == len(texts_to_embed batch), else ValueError — shared/polymath_shared/document_profile/projection.py:141-143 [DERIVED]
  fails-if: vectors silently map to the wrong surfaces.
INVARIANT: dense surface count == 1, multivector count == number of non-empty items — shared/polymath_shared/document_profile/projection.py:186, 144-149 [DERIVED]
  fails-if: `has_required_vectors` gate and the selection guard read wrong counts.
INVARIANT: each `doc_id` appears at most once in nomination output (`best`/`order` dedup) — shared/polymath_shared/document_profile/projection.py:84-94 [DERIVED]
INVARIANT: result length ≤ k (`ranked[:k]`) — shared/polymath_shared/document_profile/projection.py:95 [DERIVED]
## determinism & idempotency
determinism: NONDETERMINISTIC (injected `embed` callable shared/polymath_shared/document_profile/projection.py:184; Qdrant network/db calls :76, :210, :291; RRF scores come from the server :78). IDs and hashes are deterministic: uuid5 :44-50, sha256 projection_key :99-101, projection_hash :212-213. [DERIVED]
idempotency: SAFE (stable point ids + `upsert` replaces :210; section rebuild replaces its point :48-50; `ensure_collection` returns False when present :116-117; purge returns 0 on rerun :308-313). [DERIVED]
## failure behaviour
`fetch_existing_point` swallows every `Exception` → returns None (FACTS.fallbacks; shared/polymath_shared/document_profile/projection.py:254-255). Downstream, `fetch_existing_surfaces` None is treated as "no existing", so the new profile projects — the CANONICAL-PROFILE-SELECTION guard can never wedge ingestion (:261-263). [DERIVED]
Raised: `ValueError("nothing to project: the profile has no embeddable surface")` :182-183; `ValueError(f"embedded {len(vectors)} vectors for {len(batch)} texts")` :142-143. Absent collection → `list_section_points` returns {} :286-287, `purge_section_points` returns 0 :308-309, `fetch_existing_point` returns None :246-247. [DERIVED]
## dumb-code flags
- Surface names duplicated as bare strings: `("identity", "theme")` in `texts_to_embed` (:127) vs `ANSWER_SURFACES` (:27) and `surface_registry` imports (:22) — rename in one place desyncs embedding order from the registry. [DERIVED]
- `EXISTING_POINT_FIELDS` requests `"compiled"` (:236-237) but the payload built here writes only `"compiled_hash"` (:205); only `payload_extra` could supply `compiled` — [INFERRED] the field is for caller-injected data, but nothing in this module guarantees it exists.
- `section_payload` writes `heading_path`, `parent_ids`, `section_ordinal` (:159-162) but none are in `EXISTING_POINT_FIELDS` (:236-237), so rebuild read-back drops them. [DERIVED]
- Asymmetric k guard: document query uses raw `k` (:81), section query uses `max(1, int(k))` (:83) — k=0 still fires a full section query for an empty result. [DERIVED]
- `order.index(d)` inside the sort key (:94) is O(n²) on the deduped order list. [DERIVED]
- Double-default `float(getattr(p, "score", 0.0) or 0.0)` (:79) — `or` re-defaults a legitimate 0.0. [DERIVED]
## refactor notes
- The uuid5 namespaces `polymath:doc_profile:{doc_id}` and `...#section:{section_key}` (:44-50) are on-disk identity; changing them orphans every existing point in every `polymath_document_profiles_*` collection.
- `collection_name` format `{COLLECTION_PREFIX}_{embedding_contract_id}` (:39-40) is the shared addressing contract for all four importer files (FACTS.importers) — chat_retrieval, ui, resolution_lift_gather, doc_profile_worker.
- `ANSWER_SURFACES` as the default `surfaces` of `profile_nominate` (:27, :54) is the live nomination lane; changing membership changes retrieval behaviour in the dual-read/canary paths named in the docstring (:58-61).
- Receipt keys `kept_last_known_good`, `vectors: {}`, `projection_hash: None` on a rejected projection (:196-202) are the contract the worker consumes alongside `selection` — renaming breaks the CANONICAL-PROFILE-SELECTION guard's callers.
- `DENSE_SURFACES`/`MULTI_SURFACES` come from `surface_registry` as the single source (P4a) (:22) — local string lists (flag above) must not diverge from it.
## VERIFY
```verify
grep -Fq 'PROJECTION_VERSION = "doc-profile-projection-v1"' shared/polymath_shared/document_profile/projection.py
grep -Fq 'NOMINATE_OVERFETCH = 4' shared/polymath_shared/document_profile/projection.py
grep -Fq 'uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:doc_profile:{doc_id}")' shared/polymath_shared/document_profile/projection.py
grep -Fq 'nothing to project: the profile has no embeddable surface' shared/polymath_shared/document_profile/projection.py
grep -Fq 'qm.FusionQuery(fusion=qm.Fusion.RRF)' shared/polymath_shared/document_profile/projection.py
test "$(grep -c -F 'kept_last_known_good' shared/polymath_shared/document_profile/projection.py)" -ge 2
! grep -Fq 'uuid4' shared/polymath_shared/document_profile/projection.py
```
