# unit: shared/polymath_shared/knowledge_objects/_small-modules
anchor: shared/polymath_shared/knowledge_objects/__init__.py:1-1

## purpose
Defines the knowledge artifact layer: grounded representations beyond facts, compiled from accepted evidence alongside `CanonicalFact` (docstring: `EvidenceSpan -> KnowledgeArtifact(FACT | PROCEDURE | CONCEPT)`) — shared/polymath_shared/knowledge_objects/knowledge_artifact.py:1-7 [DERIVED].
Pure compilation from provided inputs — `No I/O, no models` — shared/polymath_shared/knowledge_objects/knowledge_artifact.py:15 [DERIVED].
Package `__init__.py` is empty (no re-exports) — shared/polymath_shared/knowledge_objects/__init__.py:1-1 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `KnowledgeArtifact` | class (pydantic `BaseModel`) | 9 fields -> model instance | knowledge_artifact.py:32-42 | shared/polymath_shared/knowledge_objects/concept.py, shared/polymath_shared/knowledge_objects/procedure.py, workers/workers/knowledge_artifacts.py (module importers) |
| `finalize` | def | (artifact: "KnowledgeArtifact", body: dict) -> "KnowledgeArtifact" | knowledge_artifact.py:45-52 | same module importers (per-symbol split not in FACTS) |
| `_artifact_id` | def (module-private) | (kind: str, document_id: str, body: Any) -> str | knowledge_artifact.py:25-29 | `finalize` only, knowledge_artifact.py:49-51 |

Importers are file-level; FACTS does not say which symbols each importer pulls.

## contracts

**`finalize(artifact, body)`** — knowledge_artifact.py:45-52
- in: `artifact: "KnowledgeArtifact"`, `body: dict` — knowledge_artifact.py:45-46 [DERIVED]
- out: the same artifact instance returned — knowledge_artifact.py:52 [DERIVED]
- pre: `artifact_type` and `document_id` must be set (required fields, no defaults) — knowledge_artifact.py:35-36 [DERIVED]
- post: `artifact.artifact_id == _artifact_id(artifact.artifact_type, artifact.document_id, body)` — knowledge_artifact.py:48-51 [DERIVED]
- post: written via `object.__setattr__` (bypasses pydantic assignment path) — knowledge_artifact.py:48 [DERIVED]

**`_artifact_id(kind, document_id, body)`** — knowledge_artifact.py:25-29
- in: `kind: str`, `document_id: str`, `body: Any` — knowledge_artifact.py:25 [DERIVED]
- out: `f"{kind[:4].lower()}_{h[:32]}"` where `h` = sha256 hexdigest of `json.dumps({"kind": kind, "doc": document_id, "body": body}, sort_keys=True, default=str)` — knowledge_artifact.py:26-29 [DERIVED]
- pre: `body` JSON-serializable or coercible via `default=str` — knowledge_artifact.py:27 [DERIVED]

**`KnowledgeArtifact` defaults** — knowledge_artifact.py:34-42
- required: `artifact_id`, `artifact_type`, `document_id`; defaults: `corpus_id = ""`, `source_chunk_ids = []`, `evidence_span_ids = []`, `confidence = 1.0`, `created_by = "knowledge-artifact-compiler"`, `provenance = {}` — knowledge_artifact.py:34-42 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`) [DERIVED]
- Files, network, subprocesses, env flags: none — module docstring `No I/O, no models` — knowledge_artifact.py:15 [DERIVED]

## invariants

INVARIANT: artifact_id prefix length <= 4 chars (`kind[:4].lower()`) — knowledge_artifact.py:29 [DERIVED]
  fails-if: kinds sharing the first 4 chars (e.g. hypothetical `FACT`/`FACE`) become indistinguishable by prefix; only the hash separates them.
INVARIANT: artifact_id hash suffix length == 32 hex chars (`h[:32]`) — knowledge_artifact.py:29 [DERIVED]
  fails-if: ids with any other length come from a different/older generator; dedup against stored ids breaks.
INVARIANT: default confidence == 1.0 — knowledge_artifact.py:40 [DERIVED]
  fails-if: unstamped artifacts silently count as fully confident downstream.
INVARIANT: default created_by == "knowledge-artifact-compiler" — knowledge_artifact.py:41 [DERIVED]
  fails-if: provenance audit can no longer distinguish compiler-made artifacts.
INVARIANT: `finalize` writes only `artifact_id`, mutates nothing else — knowledge_artifact.py:48-51 [DERIVED]
  fails-if: any field changed after finalize desyncs the content-addressed id from the body.
INVARIANT: same (artifact_type, document_id, body) -> same artifact_id (hash over `sort_keys=True` JSON) — knowledge_artifact.py:26-29 [DERIVED]
  fails-if: dropping `sort_keys` or `default=str` changes ids for identical bodies and breaks content addressing.

## determinism & idempotency
determinism: DETERMINISTIC (pure sha256 over `json.dumps(..., sort_keys=True, default=str)`; no clock/random/uuid/network/db/env — knowledge_artifact.py:26-29, :15) [DERIVED]
idempotency: SAFE (re-running `finalize` on the same artifact+body re-stamps the identical id; pure function of `artifact_type`, `document_id`, `body` — knowledge_artifact.py:48-51) [DERIVED]

## failure behaviour
- No `try:`/`except` anywhere in the unit — errors from `hashlib`/`json` propagate to the caller — knowledge_artifact.py:1-52 [DERIVED]
- `default=str` silently coerces non-JSON-serializable `body` values to their `str()`; caller sees no error — knowledge_artifact.py:27 [DERIVED]; two distinct objects with equal `str()` collide into one artifact_id — [INFERRED: same string input, same hash]
- `object.__setattr__` stamps `artifact_id` without pydantic validation; a malformed value passes unnoticed — knowledge_artifact.py:48 [INFERRED: setattr bypasses the model's assignment/validation path]

## dumb-code flags
- Magic number `4` in `kind[:4]` — knowledge_artifact.py:29 [DERIVED]
- Magic number `32` in `h[:32]` — knowledge_artifact.py:29 [DERIVED]
- `artifact_type: str` with the allowed set `FACT | PROCEDURE | CONCEPT` enforced nowhere — only a trailing comment and the docstring — knowledge_artifact.py:35, :7 [DERIVED]
- `default=str` in the identity hash can stringify body objects in surprising, silent ways — knowledge_artifact.py:27 [DERIVED]
- `object.__setattr__` used instead of normal assignment/model copy — knowledge_artifact.py:48 [DERIVED]
- `corpus_id: str = ""` — a lineage field defaults to empty, so artifacts can lack corpus linkage silently — knowledge_artifact.py:37 [DERIVED]

## refactor notes
- Any change to `_artifact_id` (payload keys `"kind"`/`"doc"`/`"body"`, prefix rule, slice lengths) changes every artifact_id; importers shared/polymath_shared/knowledge_objects/concept.py, shared/polymath_shared/knowledge_objects/procedure.py, workers/workers/knowledge_artifacts.py must be checked first — knowledge_artifact.py:25-29 + FACTS.importers [INFERRED: blast radius follows from importers plus content-addressed ids]
- Field names `document_id`, `source_chunk_ids`, `evidence_span_ids`, `created_by`, `provenance` are the non-negotiable lineage contract named in the docstring — renames break it — knowledge_artifact.py:8-12 [DERIVED]
- `finalize` assumes a non-frozen, assignment-permissive `BaseModel`; freezing the model or enabling `validate_assignment` changes `object.__setattr__` behavior — knowledge_artifact.py:48 [INFERRED: setattr bypass exists precisely to skip that path]
- `__init__.py` is empty; there are no package re-exports to preserve — shared/polymath_shared/knowledge_objects/__init__.py:1-1 [DERIVED]

## VERIFY
```verify
grep -Fq 'knowledge-artifact-compiler' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
grep -Fq 'sort_keys=True, default=str' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
grep -Fq '{kind[:4].lower()}_{h[:32]}' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
grep -Fq 'object.__setattr__(artifact, "artifact_id",' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
grep -Eq 'confidence: float = 1\.0' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
grep -Fq 'source_chunk_ids: list[str] = Field(default_factory=list)' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
grep -Fq 'evidence_span_ids: list[str] = Field(default_factory=list)' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
! grep -Fq 'try:' shared/polymath_shared/knowledge_objects/knowledge_artifact.py
```
