# unit: shared/polymath_shared/document_profile/parent_map_projection.py
anchor: shared/polymath_shared/document_profile/parent_map_projection.py:1-187

## purpose
DOCUMENT-SEMANTIC-INDEX-V1 slice S10: the parent-map Qdrant projection contract (§9.2, §14, §36.6) — shared/polymath_shared/document_profile/parent_map_projection.py:1-4 [DERIVED].
Builds the contract-named collection name, stable point id, routing vector text and payload for one Qdrant point per eligible parent; embedding and the Qdrant client are injected, the module makes no network call itself — shared/polymath_shared/document_profile/parent_map_projection.py:6-14 [DERIVED].
Postgres stays authoritative; a projected point is a rebuildable cache of an active `document_parent_maps` row, gated by `reconcile()` — shared/polymath_shared/document_profile/parent_map_projection.py:16-18 [DERIVED].

## public surface
Module imported by: `orchestrator/orchestrator/api/chat_retrieval.py`, `workers/workers/doc_parent_map_stage_worker.py` (FACTS.importers; per-symbol usage not in FACTS).

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `collection_name` | def | `embedding_contract_id: str -> str` | shared/polymath_shared/document_profile/parent_map_projection.py:37-38 | — |
| `point_id` | def | `doc_id, parent_id, map_contract -> str (uuid)` | shared/polymath_shared/document_profile/parent_map_projection.py:41-43 | — |
| `search_parent_maps` | def | `client, collection, query_vec, doc_ids, k=24, *, scope=None -> list[dict]` | shared/polymath_shared/document_profile/parent_map_projection.py:46-59 | — |
| `compact_heading` | def | `heading_path, *, max_chars=80 -> str` | shared/polymath_shared/document_profile/parent_map_projection.py:62-63 | — |
| `vector_text` | def | `routing_signature, hooks, heading_path -> str` | shared/polymath_shared/document_profile/parent_map_projection.py:66-77 | — |
| `projection_key` | def | `map_hash, map_contract, embedding_contract_id -> str (sha256)` | shared/polymath_shared/document_profile/parent_map_projection.py:80-86 | — |
| `build_payload` | def | 10 kwargs -> `dict[str, Any]` | shared/polymath_shared/document_profile/parent_map_projection.py:89-105 | — |
| `vectors_config` | def | `dim: int -> dict` | shared/polymath_shared/document_profile/parent_map_projection.py:108-110 | — |
| `ensure_collection` | def | `client, name, dim -> bool` | shared/polymath_shared/document_profile/parent_map_projection.py:113-119 | — |
| `texts_to_embed` | def | `maps: Sequence[CompiledMap], manifest: SkeletonManifest -> list[tuple[str, str]]` | shared/polymath_shared/document_profile/parent_map_projection.py:122-133 | — |
| `project_parent_maps` | def | `client, embed, embedding_contract_id, dim, doc_id, corpus_id, maps, manifest, map_contract -> dict` | shared/polymath_shared/document_profile/parent_map_projection.py:136-177 | — |
| `reconcile` | def | `active_map_count, projected_point_count -> dict` | shared/polymath_shared/document_profile/parent_map_projection.py:180-186 | — |

## contracts

**collection_name** — shared/polymath_shared/document_profile/parent_map_projection.py:37-38
- out: `f"{COLLECTION_PREFIX}_{embedding_contract_id}"` with `COLLECTION_PREFIX = "polymath_document_parent_maps"` — shared/polymath_shared/document_profile/parent_map_projection.py:31-32,37-38 [DERIVED]

**point_id** — shared/polymath_shared/document_profile/parent_map_projection.py:41-43
- out: `uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:parent_map:{map_contract}:{doc_id}:{parent_id}")` as str — shared/polymath_shared/document_profile/parent_map_projection.py:43 [DERIVED]
- post: one stable UUID per (doc, parent, contract) — shared/polymath_shared/document_profile/parent_map_projection.py:41-42 [DERIVED]

**search_parent_maps** — shared/polymath_shared/document_profile/parent_map_projection.py:46-59
- pre: `doc_ids` non-empty, else returns `[]` — shared/polymath_shared/document_profile/parent_map_projection.py:51-52 [DERIVED]
- in: ONE query filtered by `qm.MatchAny(any=list(doc_ids))` on key `"doc_id"`, optionally wrapped by `scope_or_all(scope).apply(...)`; `using=VECTOR_NAME`, `limit=k`, `with_payload=["doc_id", "parent_id", "alias"]` — shared/polymath_shared/document_profile/parent_map_projection.py:54-57 [DERIVED]
- out: `[{doc_id, parent_id, alias, score}]` from Qdrant order — shared/polymath_shared/document_profile/parent_map_projection.py:58-59 [DERIVED]
- post: read-only, one search total (never per-doc) — shared/polymath_shared/document_profile/parent_map_projection.py:47-49 [DERIVED]

**vector_text** — shared/polymath_shared/document_profile/parent_map_projection.py:66-77
- out: `routing_signature | hooks-joined-with-"; " | compact_heading`, parts joined with `" | "`, empty parts dropped — shared/polymath_shared/document_profile/parent_map_projection.py:69-77 [DERIVED]
- post: deterministic, order-stable — shared/polymath_shared/document_profile/parent_map_projection.py:67-68 [DERIVED]

**projection_key** — shared/polymath_shared/document_profile/parent_map_projection.py:80-86
- out: sha256 over sorted-keys JSON of `{map_hash, map_contract, embedding, projection: PROJECTION_VERSION}` — shared/polymath_shared/document_profile/parent_map_projection.py:83-86 [DERIVED]
- post: re-runs only when embedding model or map content (`map_hash`) changes; chunking changes do not move it — shared/polymath_shared/document_profile/parent_map_projection.py:80-82 [DERIVED]

**ensure_collection** — shared/polymath_shared/document_profile/parent_map_projection.py:113-119
- out: `True` only when the collection was created; `False` if it already existed — shared/polymath_shared/document_profile/parent_map_projection.py:116-119 [DERIVED]
- post: additive creation only, never mutates existing collections — shared/polymath_shared/document_profile/parent_map_projection.py:113-115 [DERIVED]

**texts_to_embed** — shared/polymath_shared/document_profile/parent_map_projection.py:122-133
- in: maps matched to manifest skeletons by `alias` — shared/polymath_shared/document_profile/parent_map_projection.py:126,128-129 [DERIVED]
- out: `(alias, vector_text(...))` in map order; maps with unknown alias are skipped — shared/polymath_shared/document_profile/parent_map_projection.py:129-132 [DERIVED]

**project_parent_maps** — shared/polymath_shared/document_profile/parent_map_projection.py:136-177
- pre: `len(embed(texts)) == len(texts)` else `ValueError` — shared/polymath_shared/document_profile/parent_map_projection.py:152-154 [DERIVED]
- out: receipt without vectors — keys `projection, collection, created_collection, points, point_ids, projection_hash, embedding_contract, map_contract` (+`texts_embedded` when non-empty) — shared/polymath_shared/document_profile/parent_map_projection.py:174-177 [DERIVED]
- post: one `qm.PointStruct` per map upserted with `wait=True`, vector name `"routing"` — shared/polymath_shared/document_profile/parent_map_projection.py:167-168 [DERIVED]
- post: `projection_hash` = sha256 over `{collection, map_contract, points: sorted((point_id, map_hash))}` — shared/polymath_shared/document_profile/parent_map_projection.py:169-173 [DERIVED]

**reconcile** — shared/polymath_shared/document_profile/parent_map_projection.py:180-186
- out: `{"ok": delta == 0, "active_maps", "projected_points", "delta"}` with `delta = projected_point_count - active_map_count` — shared/polymath_shared/document_profile/parent_map_projection.py:184-186 [DERIVED]

## effect surface
- Postgres tables read/written: none — FACTS `"tables_read": [], "tables_written": []` [DERIVED]
- Qdrant collection: `polymath_document_parent_maps_<embedding contract>` via prefix `COLLECTION_PREFIX` — shared/polymath_shared/document_profile/parent_map_projection.py:32,37-38 and :6-8 [DERIVED]
- Qdrant ops: `collection_exists` (:116), `create_collection` (:118), `query_points` (:56), `upsert` with `wait=True` (:168) — all through injected `client` [DERIVED]
- Network: none made by the module; `embed` + `client` injected, tests wire deterministic stubs — shared/polymath_shared/document_profile/parent_map_projection.py:11-14 [DERIVED]
- Env flags: none visible in SOURCE [DERIVED]

## invariants
INVARIANT: `projected_point_count` == `active_map_count` (delta == 0 → ok) — shared/polymath_shared/document_profile/parent_map_projection.py:184-186 [DERIVED]
  fails-if: a stale receipt masks a missing point, or an orphan point exists; gate reports ok=false — shared/polymath_shared/document_profile/parent_map_projection.py:181-183
INVARIANT: point id == uuid5 over `"polymath:parent_map:{map_contract}:{doc_id}:{parent_id}"` (exactly one point per eligible parent) — shared/polymath_shared/document_profile/parent_map_projection.py:41-43 [DERIVED]
  fails-if: id-format change orphans/re-duplicates points; upserts no longer replace prior projections
INVARIANT: `len(vectors) == len(batch)` after embed — shared/polymath_shared/document_profile/parent_map_projection.py:152-154 [DERIVED]
  fails-if: `ValueError(f"embedded {len(vectors)} vectors for {len(batch)} texts")` raised
INVARIANT: compact heading length ≤ `COMPACT_HEADING_MAX_CHARS` (80) — shared/polymath_shared/document_profile/parent_map_projection.py:34,63 [DERIVED]
  fails-if: longer heading silently truncates, changing vector_text content
INVARIANT: vector distance == `qm.Distance.COSINE`, vector name `"routing"` — shared/polymath_shared/document_profile/parent_map_projection.py:33,109-110 [DERIVED]
  fails-if: mismatch with query-side `using=VECTOR_NAME` breaks search
INVARIANT: empty batch → receipt `points: 0`, `projection_hash = hashlib.sha256(b"").hexdigest()` — shared/polymath_shared/document_profile/parent_map_projection.py:148-151 [DERIVED]
  fails-if: consumers treating the sentinel digest as a real projection hash mis-detect drift

## determinism & idempotency
determinism: DETERMINISTIC — uuid5 ids (:43), sorted-keys sha256 (:83-86, :169-173), fixed separators (:63,:70,:77); vector values come from injected `embed` (:152) [DERIVED]
idempotency: SAFE — stable uuid5 point ids mean re-running `project_parent_maps` upserts the same ids (:43,:168); `ensure_collection` returns False when the collection exists (:116-117) [DERIVED]

## failure behaviour
No fallback handlers in FACTS. Explicit behaviours:
- `search_parent_maps` with empty `doc_ids` returns `[]`, no query issued — shared/polymath_shared/document_profile/parent_map_projection.py:51-52 [DERIVED]
- `texts_to_embed` silently skips a map whose alias is absent from the manifest (it "can never have been produced against this manifest") — shared/polymath_shared/document_profile/parent_map_projection.py:129-131,124-125 [DERIVED]
- embed/batch length mismatch raises `ValueError` — shared/polymath_shared/document_profile/parent_map_projection.py:153-154 [DERIVED]
- `reconcile` never raises; it reports `ok: false` with the delta — shared/polymath_shared/document_profile/parent_map_projection.py:184-186 [DERIVED]

## dumb-code flags
- `from qdrant_client.http import models as qm` duplicated in three functions instead of a top-level import — :50, :109, :143 [DERIVED]
- `scope_or_all` lazily imported inside `search_parent_maps` while sibling `polymath_shared` modules are imported at top — :53 vs :28-29 [INFERRED: import-style inconsistency, no behavioural effect]
- magic default `k: int = 24` with no named constant — :46 [DERIVED]
- sentinel `hashlib.sha256(b"").hexdigest()` for the empty-batch projection_hash — :150 [DERIVED]
- payload key `"embedding_contract"` vs parameter name `embedding_contract_id` (name drift inside one dict) — :101,:103 [INFERRED: cosmetic, but greppability suffers]

## refactor notes
- `COLLECTION_PREFIX`, `VECTOR_NAME`, `PROJECTION_VERSION` and the `point_id` string format are contract-named; changing them orphans existing points and breaks the §14 blue/green isolation — :6-9, :31-33, :43. Importers `orchestrator/orchestrator/api/chat_retrieval.py` and `workers/workers/doc_parent_map_stage_worker.py` (FACTS.importers) must be updated together [DERIVED]
- `with_payload=["doc_id", "parent_id", "alias"]` in search must stay a subset of `build_payload` keys — :57 vs :92-104 [DERIVED]
- `vector_text` format feeds every embedded routing vector; changing separators or truncation invalidates all parent-map embeddings — :66-77, :34 [DERIVED]
- `projection_key`/`projection_hash` compositions are receipt-stable contracts; altering the JSON key sets changes every hash without changing content — :83-86, :169-173 [DERIVED]

## VERIFY
```verify
grep -Fq 'parent-map-projection-v1' shared/polymath_shared/document_profile/parent_map_projection.py
grep -Fq 'polymath:parent_map:' shared/polymath_shared/document_profile/parent_map_projection.py
grep -Fq 'qm.Distance.COSINE' shared/polymath_shared/document_profile/parent_map_projection.py
grep -Eq 'def (search_parent_maps|project_parent_maps|reconcile)\(' shared/polymath_shared/document_profile/parent_map_projection.py
test "$(grep -c -F 'from qdrant_client.http import models as qm' shared/polymath_shared/document_profile/parent_map_projection.py)" -ge 3
! grep -Fq 'QdrantClient(' shared/polymath_shared/document_profile/parent_map_projection.py
```
