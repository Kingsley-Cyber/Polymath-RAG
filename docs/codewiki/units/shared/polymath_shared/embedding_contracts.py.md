# unit: shared/polymath_shared/embedding_contracts.py
anchor: shared/polymath_shared/embedding_contracts.py:1-152

## purpose
Freezes the embedding representation contract — model id/revision, dimension, distance metric, normalization, prefixes, tokenization, representation kinds — behind a content-hash id, so any semantic difference is a NEW contract and can never silently mutate an existing index (module docstring, shared/polymath_shared/embedding_contracts.py:1-22) [DERIVED]. Separates representation from routing policy and from backend location (MPS/CUDA/API deliberately absent, shared/polymath_shared/embedding_contracts.py:6-8) [DERIVED]. Consumed by 13 modules: retrieval APIs, workers, embedder sidecar, shared hybrid/pass1 (FACTS.importers) [DERIVED]. Keeps `hash-embed-v1` permanently as a zero-model deterministic test contract (shared/polymath_shared/embedding_contracts.py:19-21) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| EmbeddingContract | frozen dataclass, 13 fields | fields incl. defaults `query_prefix=""`, `document_prefix=""`, `tokenization="default"`, `max_input_tokens=512`, `batch_limit=64`, `embed_fn=None` -> contract object | shared/polymath_shared/embedding_contracts.py:36-52 | module importers (below) |
| EmbeddingContract.contract_id | property | -> str = `"embed_" + content_hash(...)[:16]` | shared/polymath_shared/embedding_contracts.py:54-70 | internal; CONTRACTS keys :126-127 |
| EmbeddingContract.content_hash | method | () -> str (alias of contract_id) | shared/polymath_shared/embedding_contracts.py:72-73 | — |
| EmbeddingContract.embed | method | (text: str, kind: str) -> list[float] | shared/polymath_shared/embedding_contracts.py:75-85 | module importers |
| _hash_embed_fn | def | (text: str) -> list[float] | shared/polymath_shared/embedding_contracts.py:88-91 | HASH_EMBED_CONTRACT only (:103) |
| HASH_EMBED_CONTRACT | instance | EmbeddingContract(dimension=512, tokenization="char-3gram", embed_fn=_hash_embed_fn) | shared/polymath_shared/embedding_contracts.py:95-104 | projection/reconstruction/fusion/migration tests (:19-21) |
| NEURAL_EMBED_CONTRACT | instance | EmbeddingContract(dimension=1024, embed_fn=None) | shared/polymath_shared/embedding_contracts.py:110-123 | embedder sidecar (:122 comment) |
| CONTRACTS | dict | derived contract_id -> EmbeddingContract | shared/polymath_shared/embedding_contracts.py:125-128 | active_contract (:148) |
| SHORT_NAMES | dict | friendly id -> EmbeddingContract | shared/polymath_shared/embedding_contracts.py:132-135 | active_contract (:148) |
| ACTIVE_CONTRACT_ID | str constant | = `"hash-embed-v1"` | shared/polymath_shared/embedding_contracts.py:138 | not referenced elsewhere in file |
| active_contract | def | () -> EmbeddingContract | shared/polymath_shared/embedding_contracts.py:141-151 | module importers |

Module importers (FACTS.importers): control/control/generation_swap.py; orchestrator/orchestrator/api/chat_retrieval.py, fast.py, retrieve.py, ui.py; shared/polymath_shared/hybrid.py, pass1.py; sidecars/embedder/server.py; workers/workers/doc_parent_map_stage_worker.py, doc_profile_worker.py, project_qdrant_worker.py, semantic_chunker.py, verify_worker.py [DERIVED].

## contracts
**EmbeddingContract.embed(text, kind)** — shared/polymath_shared/embedding_contracts.py:75-85
- in: `text: str`, `kind: str`
- out: `list[float]`
- pre: `kind in self.representation_kinds` (:76); `self.embed_fn is not None` (:83)
- post: kind `"query"` gets `query_prefix` prepended (:79-80); kind in `("document_profile", "parent_summary", "child_chunk")` gets `document_prefix` (:81-82); returns `self.embed_fn(prefixed)` (:85)

**EmbeddingContract.contract_id** — shared/polymath_shared/embedding_contracts.py:54-70
- out: `"embed_" + content_hash({...})[:16]`; hashed keys: version, model, revision, dim, distance, normalization, query_prefix, document_prefix, tokenization, max_tokens, batch, kinds (12 keys, :57-70)

**EmbeddingContract.content_hash** — shared/polymath_shared/embedding_contracts.py:72-73
- out: exactly `self.contract_id` (alias, no extra hashing)

**active_contract()** — shared/polymath_shared/embedding_contracts.py:141-151
- in: none; reads `get_settings().stores.embedding_contract_id` (:147)
- out: `EmbeddingContract`
- pre: settings id is a `SHORT_NAMES` key or a `CONTRACTS` key (:148)
- post: unknown id raises `ValueError(f"unknown embedding contract: {contract_id}")`; no fallback (:149-150, docstring :143-144)

## effect surface
- Postgres: none — `tables_read` `[]`, `tables_written` `[]` (FACTS) [DERIVED].
- Qdrant: no collections touched in this file; the derived contract id "keys the index names" per comment shared/polymath_shared/embedding_contracts.py:130-131 [DERIVED]; actual collection naming happens in importers such as workers/workers/project_qdrant_worker.py [INFERRED: it is listed as an importer and named for Qdrant].
- Settings/env: `stores.embedding_contract_id` read via lazy `get_settings` import (:145-147); documented default `hash-embed-v1` (:142) [DERIVED].
- Module deps: `polymath_shared.identity.content_hash` (:28); lazy `polymath_shared.projection_contracts.hash_embed_v1` (:89); lazy `polymath_shared.settings.get_settings` (:145) [DERIVED].
- Network/subprocess/files: none in this file; NEURAL embedding served by embedder sidecar, `embed_fn=None` (:122) [DERIVED].

## invariants
INVARIANT: contract_id == "embed_" + content_hash(12 frozen keys)[:16] — shared/polymath_shared/embedding_contracts.py:57-70 [DERIVED]
  fails-if: a model/dimension/normalization change reuses an id and silently mixes vectors in one index (docstring :5-8).
INVARIANT: hashed key set excludes `embed_fn` (field at :52, absent from hash dict :57-70) — shared/polymath_shared/embedding_contracts.py:52-70 [DERIVED]
  fails-if: same id, different embed implementation → all vectors change while index names stay.
INVARIANT: kind acceptance set == representation_kinds, default REPRESENTATION_KINDS == `("document_profile", "parent_summary", "child_chunk", "query")` — shared/polymath_shared/embedding_contracts.py:30, :51, :76 [DERIVED]
  fails-if: a caller passing an unlisted kind gets ValueError at :77 instead of embedding with intended lane semantics.
INVARIANT: prefix rule — kind `"query"` ⇔ query_prefix; kind ∈ {"document_profile","parent_summary","child_chunk"} ⇔ document_prefix — shared/polymath_shared/embedding_contracts.py:79-82 [DERIVED]
  fails-if: query and document vectors land in different spaces than scoring assumes (NEURAL is asymmetric, query_prefix set at :117, document_prefix "" at :118).
INVARIANT: lookup order `SHORT_NAMES.get(id) or CONTRACTS.get(id)` — SHORT_NAMES wins — shared/polymath_shared/embedding_contracts.py:148 [DERIVED]
  fails-if: a friendly id that collides with a derived id silently shadows the derived contract.
INVARIANT: NEURAL_EMBED_CONTRACT.model_revision == "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3" == embedder sidecar manifest revision — shared/polymath_shared/embedding_contracts.py:107-109, :113 [DERIVED]
  fails-if: index naming and sidecar identity drift apart (:108-109 comment).

## determinism & idempotency
determinism: DETERMINISTIC — contract_id is a pure content hash of frozen fields; no clock/random/uuid/env/network in the hash (shared/polymath_shared/embedding_contracts.py:57-70) [DERIVED]. embed() output depends on injected embed_fn: hash path delegates to `hash_embed_v1` (:88-91); active_contract() resolution depends on settings/env via `get_settings` (:145-147) [DERIVED].
idempotency: SAFE — pure construction and lookup, no writes or side effects anywhere in the file (shared/polymath_shared/embedding_contracts.py:36-151) [DERIVED].

## failure behaviour
No try/except, nothing swallowed (whole file) [DERIVED]. Three raise sites, all `ValueError`:
- `f"representation kind {kind!r} not in contract {self.contract_id}"` — shared/polymath_shared/embedding_contracts.py:77
- `f"contract {self.contract_id} has no embed implementation"` — shared/polymath_shared/embedding_contracts.py:84
- `f"unknown embedding contract: {contract_id}"` — shared/polymath_shared/embedding_contracts.py:150

Callers see hard failures by design: "a contract is an explicit versioning decision, never a fallback" (:143-144) [DERIVED].

## dumb-code flags
- `DISTANCE_METRICS` (:32) and `NORMALIZATIONS` (:33) declared but never checked — no validation that `distance_metric`/`normalization` field values are members anywhere in the file.
- `ACTIVE_CONTRACT_ID` (:138) unreferenced elsewhere in the file; the operative default comes from `settings.stores.embedding_contract_id` (:147) — constant and settings default can drift.
- `embed_fn` is a dataclass field (:52) but excluded from identity hash (:57-70).
- Magic truncation `[:16]` in the id (:70).
- `512` carries two unrelated meanings: `max_input_tokens` default 512 (:49) vs HASH dimension 512 (:99).
- Literal `"hash-embed-v1"` duplicated at :19, :133, :138, :142.
- `content_hash()` method is a pure alias of `contract_id` (:72-73).
- Performance fields `max_input_tokens`/`batch_limit` are hashed into identity (keys "max_tokens"/"batch", :67-68) — retuning batch size mints a new contract id.

## refactor notes
- The contract_id recipe (prefix `"embed_"`, 12-key dict, `[:16]` truncation) keys index names (:130-131) — changing it re-keys every collection; blast radius = all 13 importers (FACTS.importers).
- `representation_kinds` default feeds hash key "kinds" (:70, :51) — adding a representation kind changes every contract id; embed()'s prefix branch hardcodes the three document kinds (:81).
- NEURAL `query_prefix` literal (:117) is part of identity — editing the string invalidates the contract and every stored query vector.
- HASH_EMBED_CONTRACT must not be deleted — "retained PERMANENTLY" (:19-21), "never deleted" (:94); projection/reconstruction/fusion/contract-migration tests depend on it (:20-21).
- Removing a SHORT_NAMES friendly id breaks configurations that use it (:148); active_contract() deliberately raises instead of defaulting (:144, :150).
- NEURAL field changes (dimension=1024 :114, revision pin :113) must be mirrored in the embedder sidecar manifest (:107-109).

## VERIFY
```verify
grep -Fq 'ACTIVE_CONTRACT_ID = "hash-embed-v1"' shared/polymath_shared/embedding_contracts.py
grep -Fq 'model_id="Qwen/Qwen3-Embedding-0.6B"' shared/polymath_shared/embedding_contracts.py
grep -Fq 'return "embed_" + content_hash({' shared/polymath_shared/embedding_contracts.py
grep -Fq 'raise ValueError(f"unknown embedding contract: {contract_id}")' shared/polymath_shared/embedding_contracts.py
grep -Fq 'max_input_tokens=8192' shared/polymath_shared/embedding_contracts.py
! grep -Fq 'distance_metric not in DISTANCE_METRICS' shared/polymath_shared/embedding_contracts.py
test "$(grep -c -F 'ValueError' shared/polymath_shared/embedding_contracts.py)" -ge 3
```
