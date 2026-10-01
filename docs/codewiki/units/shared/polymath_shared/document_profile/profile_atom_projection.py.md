# unit: shared/polymath_shared/document_profile/profile_atom_projection.py
anchor: shared/polymath_shared/document_profile/profile_atom_projection.py:1-248

## purpose
Projects Profile Atoms (routing surfaces lifted from compiled document/section profiles) into a per-embedding-contract Qdrant collection: one dense point per atom, named vector `"atom"` — shared/polymath_shared/document_profile/profile_atom_projection.py:1-8 [DERIVED]. Postgres `document_profile_atoms` is the authority; the collection is a rebuildable cache of its ACTIVE rows, gated by `reconcile()` — shared/polymath_shared/document_profile/profile_atom_projection.py:4-5 [DERIVED]. The atom lane (`search_atoms`) is a read-only routing/expansion lookup that "never returns factual evidence, only nominated (doc, atom) routes" — shared/polymath_shared/document_profile/profile_atom_projection.py:5-7 [DERIVED].

## public surface
Module imported by (FACTS.importers): `orchestrator/orchestrator/api/chat_retrieval.py`, `orchestrator/orchestrator/api/ui.py`, `workers/workers/doc_profile_worker.py`.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| collection_name | def | (embedding_contract_id: str) -> str | shared/polymath_shared/document_profile/profile_atom_projection.py:32-33 | — |
| point_id | def | (atom_id: str) -> str | shared/polymath_shared/document_profile/profile_atom_projection.py:36-37 | — |
| vectors_config | def | (dim: int) -> dict | shared/polymath_shared/document_profile/profile_atom_projection.py:40-42 | — |
| build_payload | def | (atom: ProfileAtom) -> dict | shared/polymath_shared/document_profile/profile_atom_projection.py:45-51 | — |
| ensure_collection | def | (client, name: str, dim: int) -> bool | shared/polymath_shared/document_profile/profile_atom_projection.py:54-58 | — |
| project_atoms | def | (client, *, embed, embedding_contract_id: str, dim: int, atoms: Sequence[ProfileAtom]) -> dict | shared/polymath_shared/document_profile/profile_atom_projection.py:61-81 | — |
| projected_count | def | (client, embedding_contract_id: str, corpus_id: str \| None = None) -> int | shared/polymath_shared/document_profile/profile_atom_projection.py:84-92 | — |
| reconcile | def | (conn, client, *, corpus_id: str, embedding_contract_id: str) -> dict | shared/polymath_shared/document_profile/profile_atom_projection.py:95-101 | — |
| purge | def | (client, embedding_contract_id: str, corpus_id: str) -> int | shared/polymath_shared/document_profile/profile_atom_projection.py:104-113 | — |
| purge_doc | def | (client, embedding_contract_id: str, doc_id: str) -> int | shared/polymath_shared/document_profile/profile_atom_projection.py:116-127 | — |
| ingest_document_atoms | def | (conn, client, *, embed, embedding_contract_id, dim, doc_id, corpus_id, compiled, profile_contract, source=None) -> dict | shared/polymath_shared/document_profile/profile_atom_projection.py:130-153 | doc_profile_worker (FACTS.importers) |
| purge_section_atoms | def | (client, embedding_contract_id: str, doc_id: str, section_key: str) -> int | shared/polymath_shared/document_profile/profile_atom_projection.py:156-168 | — |
| ingest_section_atoms | def | (conn, client, *, embed, embedding_contract_id, dim, doc_id, corpus_id, compiled, profile_contract, section_key, parent_ids, compiled_hash) -> dict | shared/polymath_shared/document_profile/profile_atom_projection.py:171-190 | doc_profile_worker (FACTS.importers) |
| corpus_scope | def | (corpus_ids) -> list[str] | shared/polymath_shared/document_profile/profile_atom_projection.py:193-197 | — |
| search_atoms | def | (client, collection, query_vec, kinds, k: int = 12, *, corpus_ids, doc_ids=None, scope=None) -> list[dict] | shared/polymath_shared/document_profile/profile_atom_projection.py:200-227 | chat_retrieval, ui (FACTS.importers) |
| count_atoms | def | (client, collection, kinds, *, corpus_ids, exact: bool = False, scope=None) -> int | shared/polymath_shared/document_profile/profile_atom_projection.py:233-247 | chat_retrieval, ui (FACTS.importers) |
| _embed_batched | def (private) | (embed, texts: list[str]) -> list[list[float]] | shared/polymath_shared/document_profile/profile_atom_projection.py:25-29 | project_atoms:72 |

## contracts

**project_atoms** — shared/polymath_shared/document_profile/profile_atom_projection.py:61-81
- in: `atoms: Sequence[ProfileAtom]`, `embed: Callable[[list[str]], list[list[float]]]`, `dim: int` [DERIVED]
- out: receipt `{projection: "profile-atom-projection-v1", collection, created_collection: bool, points: int, point_ids: list, projection_hash: sha256-hex}` — no vectors — shared/polymath_shared/document_profile/profile_atom_projection.py:60-81 [DERIVED]
- pre: embedder must accept batches of ≤ `EMBED_BATCH = 32` (sidecar measured: 32 ok, 64 fails) — shared/polymath_shared/document_profile/profile_atom_projection.py:21-22 [DERIVED]
- post: one point per atom, upserted `wait=True`; empty `atoms` → `points: 0`, `projection_hash = sha256(b"")` — shared/polymath_shared/document_profile/profile_atom_projection.py:69-78 [DERIVED]

**reconcile** — shared/polymath_shared/document_profile/profile_atom_projection.py:95-101
- in: `corpus_id`, `embedding_contract_id`
- out: `{corpus_id, active_atoms, projected_points, reconciled}` with `reconciled = (active == projected)`; active from Postgres `active_atom_count`, projected from Qdrant exact count — shared/polymath_shared/document_profile/profile_atom_projection.py:96-101 [DERIVED]

**ingest_document_atoms** — shared/polymath_shared/document_profile/profile_atom_projection.py:130-153
- pipeline: `extract_atoms` → `persist_atoms(conn, ..., source=source)` → `purge_doc` → `project_atoms(to_project)` — shared/polymath_shared/document_profile/profile_atom_projection.py:142-147 [DERIVED]
- ATOM-REPAIR-V1: with a `source` (`family:compiled_hash`) supersession is family-scoped; `to_project = active_atoms(conn, doc_id=doc_id)` (all families), else `to_project = atoms` — shared/polymath_shared/document_profile/profile_atom_projection.py:139-146 [DERIVED]
- out: `{ok: True, active, persisted, purged_points, projected_points, collection, by_kind, profile_contract, source}` — shared/polymath_shared/document_profile/profile_atom_projection.py:151-153 [DERIVED]

**ingest_section_atoms** — shared/polymath_shared/document_profile/profile_atom_projection.py:171-190
- source tag: `source_tag("section", compiled_hash, section_key)` → family `section:<key>:<hash>`; persists family-scoped, purges only that section's points, projects only the section's atoms — shared/polymath_shared/document_profile/profile_atom_projection.py:175-184 [DERIVED]
- out: same receipt shape plus `"scope": "section"`, `"section_key"` — shared/polymath_shared/document_profile/profile_atom_projection.py:188-190 [DERIVED]

**purge / purge_doc / purge_section_atoms** — shared/polymath_shared/document_profile/profile_atom_projection.py:104-113, 116-127, 156-168
- in: filter keys `corpus_id` / `doc_id` / `doc_id`+`section_key`; missing collection → `0` — shared/polymath_shared/document_profile/profile_atom_projection.py:108-109, 122-123, 161-162 [DERIVED]
- out: pre-delete exact count ("points removed"), delete `wait=True` — shared/polymath_shared/document_profile/profile_atom_projection.py:110-113, 125-127, 165-168 [DERIVED]

**search_atoms** — shared/polymath_shared/document_profile/profile_atom_projection.py:200-227
- pre: `corpus_ids` REQUIRED and non-empty after `corpus_scope`, else `[]` (fail closed); corpus filter rides INSIDE the Qdrant `query_filter`, not post-filter — shared/polymath_shared/document_profile/profile_atom_projection.py:205-212 [DERIVED]
- out: `[{doc_id, corpus_id, atom_kind, text, atom_id, score}]` desc, `k = 12` default, payload subset only — shared/polymath_shared/document_profile/profile_atom_projection.py:201, 222-227 [DERIVED]
- `doc_ids is not None` → additionally filter `doc_id MatchAny`; empty list → `[]` (SEEALSO-BLEND-V1) — shared/polymath_shared/document_profile/profile_atom_projection.py:216-221 [DERIVED]

**count_atoms** — shared/polymath_shared/document_profile/profile_atom_projection.py:233-247
- same scope rule: no corpora → `0`; `exact` default `False` — shared/polymath_shared/document_profile/profile_atom_projection.py:235-242 [DERIVED]

## effect surface
- Qdrant collection `f"{COLLECTION_PREFIX}_{embedding_contract_id}"` = `polymath_document_profile_atoms_<contract>` — shared/polymath_shared/document_profile/profile_atom_projection.py:19, 32-33 [DERIVED]
- Qdrant ops: `create_collection` (named vector `"atom"`, `VectorParams(size=dim, distance=COSINE)`) — shared/polymath_shared/document_profile/profile_atom_projection.py:40-42, 57; `upsert` wait=True — shared/polymath_shared/document_profile/profile_atom_projection.py:78; `count` — shared/polymath_shared/document_profile/profile_atom_projection.py:92, 125, 165, 247; `delete` (FilterSelector) wait=True — shared/polymath_shared/document_profile/profile_atom_projection.py:111-112, 123, 167; `query_points` — shared/polymath_shared/document_profile/profile_atom_projection.py:222-224
- Postgres: no SQL in this file (FACTS `tables_read`/`tables_written` empty); delegated to `polymath_shared.document_profile.profile_atom`: `persist_atoms` — shared/polymath_shared/document_profile/profile_atom_projection.py:144, 182, `active_atoms` — shared/polymath_shared/document_profile/profile_atom_projection.py:146, `active_atom_count` — shared/polymath_shared/document_profile/profile_atom_projection.py:98; authority table named `document_profile_atoms` — shared/polymath_shared/document_profile/profile_atom_projection.py:4 [DERIVED]
- Network: `embed` callback to embedder sidecar, batched at 32 — shared/polymath_shared/document_profile/profile_atom_projection.py:21-22, 25-29, 72
- Files / subprocess / env flags: none.

## invariants
INVARIANT: projected Qdrant point count == Postgres active atom count (per corpus, per embedding contract) — shared/polymath_shared/document_profile/profile_atom_projection.py:95-101 [DERIVED]
  fails-if: `reconciled: false`; atom lane serves stale or ghost (doc, atom) routes.
INVARIANT: embed request batch size <= 32 — shared/polymath_shared/document_profile/profile_atom_projection.py:21-22, 27-28 [DERIVED]
  fails-if: sidecar rejects the request (measured: 64 fails), projection aborts mid-batch.
INVARIANT: points per atom == 1; point id == uuid5(NAMESPACE_URL, "polymath:profile_atom:" + atom_id) — shared/polymath_shared/document_profile/profile_atom_projection.py:36-37, 74-77 [DERIVED]
  fails-if: re-projection of the same atom creates duplicate/oscillating points.
INVARIANT: empty corpus scope -> search_atoms returns [] and count_atoms returns 0 (fail closed) — shared/polymath_shared/document_profile/profile_atom_projection.py:209-211, 240-242 [DERIVED]
  fails-if: a corpus-A query activates a corpus-B concept (cross-corpus leak).
INVARIANT: section atoms carry their DOCUMENT's doc_id plus `scope: "section"`, `section_key`, `parent_ids` — shared/polymath_shared/document_profile/profile_atom_projection.py:48-50 [DERIVED]
  fails-if: section atom routes to a section id that is not a queryable document.
INVARIANT: named vector `"atom"` uses distance COSINE with size == dim — shared/polymath_shared/document_profile/profile_atom_projection.py:40-42 [DERIVED]
  fails-if: dimension/metric mismatch with the embedder contract breaks similarity or collection creation.

## determinism & idempotency
determinism: NONDETERMINISTIC (embed network callback — shared/polymath_shared/document_profile/profile_atom_projection.py:72; Qdrant upsert/count/query — shared/polymath_shared/document_profile/profile_atom_projection.py:78, 92, 222; Postgres reads — shared/polymath_shared/document_profile/profile_atom_projection.py:98). Derived ids and hashes are deterministic: uuid5 point ids — shared/polymath_shared/document_profile/profile_atom_projection.py:36-37; `projection_hash` = sha256 over `{"collection", "points": sorted(pids)}` (order-independent) — shared/polymath_shared/document_profile/profile_atom_projection.py:79 [DERIVED].
idempotency: SAFE — same atoms re-derive the same uuid5 ids, so upsert overwrites in place — shared/polymath_shared/document_profile/profile_atom_projection.py:36-37, 74-78; `ensure_collection` is a no-op when the collection exists — shared/polymath_shared/document_profile/profile_atom_projection.py:55-56; purges return 0 when nothing matches — shared/polymath_shared/document_profile/profile_atom_projection.py:108-109, 122-123, 161-162. [INFERRED] a crash between `purge_doc` (145) and upsert (78) leaves the collection short of active rows until re-run; `reconcile` (95-101) detects that state.

## failure behaviour
- No try/except anywhere in the file; qdrant_client, embed, and Postgres errors propagate raw to the caller — shared/polymath_shared/document_profile/profile_atom_projection.py:1-247 [DERIVED]
- Missing collection is treated as empty by the count/purge family: `projected_count` → 0 — shared/polymath_shared/document_profile/profile_atom_projection.py:87-88; `purge` → 0 — shared/polymath_shared/document_profile/profile_atom_projection.py:108-109; `purge_doc` → 0 — shared/polymath_shared/document_profile/profile_atom_projection.py:122-123; `purge_section_atoms` → 0 — shared/polymath_shared/document_profile/profile_atom_projection.py:161-162 [DERIVED]
- Fail-closed lookups: no corpora → `[]` / `0`; `doc_ids=[]` → `[]` — shared/polymath_shared/document_profile/profile_atom_projection.py:210-211, 219-220, 241-242 [DERIVED]
- `search_atoms`/`count_atoms` take `collection` as a parameter and do NOT check `collection_exists`; a wrong/missing collection name reaches qdrant_client directly — shared/polymath_shared/document_profile/profile_atom_projection.py:200-227, 233-247 [INFERRED: no guard visible, so the client error surfaces]

## dumb-code flags
- `ingest_document_atoms` receipt reports `"active": len(atoms)` (newly extracted only) while `projected_points` counts ALL active rows when `source is not None` — the two numbers can disagree by design — shared/polymath_shared/document_profile/profile_atom_projection.py:146, 151, 153 [DERIVED]
- Empty-atoms hash is `sha256(b"")`, which differs from the general formula's hash of `{"collection": name, "points": []}` — two different "empty" receipts — shared/polymath_shared/document_profile/profile_atom_projection.py:70-71 vs 79 [DERIVED]
- `purge_section_atoms` skips the delete call when `before == 0` (`if before:`) while `purge` and `purge_doc` always issue the delete — shared/polymath_shared/document_profile/profile_atom_projection.py:166 vs 111-112, 123 [DERIVED]
- `count_atoms` defaults `exact=False` (approximate diagnostic) while `projected_count`/`purge_doc`/`purge_section_atoms` count with `exact=True` — shared/polymath_shared/document_profile/profile_atom_projection.py:233 vs 92, 125, 165 [DERIVED]
- Magic default `k: int = 12` in `search_atoms` — shared/polymath_shared/document_profile/profile_atom_projection.py:201 [DERIVED]
- `purge`/`purge_doc`/`purge_section_atoms` return the PRE-delete count and never re-count after deletion, so "points removed" is assumed, not verified — shared/polymath_shared/document_profile/profile_atom_projection.py:110-113, 125-127, 165-168 [DERIVED]

## refactor notes
- Payload keys `doc_id`, `corpus_id`, `atom_kind`, `section_key` are load-bearing: they are the Qdrant filter keys in every search and purge — renaming them orphans all deletes/lookups — shared/polymath_shared/document_profile/profile_atom_projection.py:46-50 vs 124, 163-164, 212-221, 243-246 [DERIVED]
- Collection naming `f"{COLLECTION_PREFIX}_{embedding_contract_id}"` is the cross-component contract; all three importers (chat_retrieval, ui, doc_profile_worker) must resolve the same name — shared/polymath_shared/document_profile/profile_atom_projection.py:32-33 [DERIVED]
- Changing the `point_id` uuid5 scheme changes every point id; old points survive until a purge (deletes filter on payload, not id), doubling counts in between — shared/polymath_shared/document_profile/profile_atom_projection.py:36-37, 75, 111-112 [INFERRED: delete selectors use payload filters, not ids]
- `EMBED_BATCH = 32` encodes a measured sidecar limit (32 ok, 64 fails); raising it breaks embedding at runtime — shared/polymath_shared/document_profile/profile_atom_projection.py:21-22 [DERIVED]
- Receipt keys (`ok`, `active`, `persisted`, `purged_points`, `projected_points`, `collection`, `by_kind`, `profile_contract`, `source`) are consumed by the ingest callers (doc_profile_worker) — shared/polymath_shared/document_profile/profile_atom_projection.py:151-153, 188-190 [DERIVED]

## VERIFY
```verify
grep -Fq 'EMBED_BATCH = 32' shared/polymath_shared/document_profile/profile_atom_projection.py
grep -Fq 'profile-atom-projection-v1' shared/polymath_shared/document_profile/profile_atom_projection.py
grep -Fq 'polymath:profile_atom:' shared/polymath_shared/document_profile/profile_atom_projection.py
grep -Fq 'hashlib.sha256(b"").hexdigest()' shared/polymath_shared/document_profile/profile_atom_projection.py
grep -Eq 'def (purge|purge_doc|purge_section_atoms)\(' shared/polymath_shared/document_profile/profile_atom_projection.py
! grep -Fq 'try:' shared/polymath_shared/document_profile/profile_atom_projection.py
test "$(grep -c -F 'qm.MatchAny' shared/polymath_shared/document_profile/profile_atom_projection.py)" -ge 4
```
