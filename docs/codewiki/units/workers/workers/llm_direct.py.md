# unit: workers/workers/llm_direct.py
anchor: workers/workers/llm_direct.py:1-277

## purpose
Persists gate-attested LLM relations for one document directly into `entities`/`mentions`/`facts`/`evidence` under contract `"llm-direct-facts-v1"`, replacing the predicate-compiler/admission-harbor second authority that discarded them (283 gated relations → 3 admitted facts, 2026-08-30 re-ingest) — workers/workers/llm_direct.py:1-9 [DERIVED]. Deterministic and idempotent; module imported by the extraction worker — workers/workers/llm_direct.py:51 (FACTS.importers: workers/workers/extract_worker.py) [DERIVED]. Not a filter: everything the gate passed is persisted; rejections stay in the artifact — workers/workers/llm_direct.py:32-33 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `materialize` | def | (conn, *, corpus_id, doc_id, chunk_rows: dict[str, dict], merged: NormalizedExtraction, lane: str, model: str, stamp: Callable[[dict], dict] \| None = None) -> dict | workers/workers/llm_direct.py:86-276 | workers/workers/extract_worker.py (module importer) |
| `_mention_id` | def | (doc_id: str, chunk_id: str, core: str, start: int, end: int) -> str | workers/workers/llm_direct.py:70-72 | — (module-internal) |
| `_endpoint_offsets` | def | (surface: str, view: ChunkView, quote: tuple[int, int]) -> tuple[int, int] | workers/workers/llm_direct.py:75-83 | — (module-internal) |

## contracts

### materialize — workers/workers/llm_direct.py:86-276
- in: `chunk_rows` values supply `"text"` (builds `ChunkView(cid, row["text"])`) and optional `"char_start"`/`"char_end"` (missing → `0`) — workers/workers/llm_direct.py:141, 190-191, 203 [DERIVED].
- in: `merged` exposes `entities_by_chunk` and `evidence_by_chunk` keyed by chunk id — workers/workers/llm_direct.py:111, 137 [DERIVED].
- in: `stamp=None` → identity lambda; `bundle_hash = stamp({}).get("generated_by_bundle_hash")` — workers/workers/llm_direct.py:92-93 [DERIVED].
- pre: every relation is already gate-attested (subject, object and quote are exact source substrings) and typed with one of the 17 ontology predicates (+RELATED_TO) — workers/workers/llm_direct.py:5-8 [DERIVED].
- pre (guard): predicate not in `RELATION_ONTOLOGY` → counted in `unknown_predicates`, skipped, "never expected" — workers/workers/llm_direct.py:144-146 [DERIVED].
- pre: unresolved closed-class pronouns dropped as entities and as endpoints (LLM-DIRECT-PRONOUN-GATE-V1) — workers/workers/llm_direct.py:118-120, 148-150, 103-106 [DERIVED].
- post: returns keys `contract`, `lane`, `model`, `seen` (entities/mentions/facts/evidence), `written` (same four), `unknown_predicates`, `pronoun_entities_dropped`, `pronoun_endpoints_dropped`, `endpoint_attestation`, `predicates` — workers/workers/llm_direct.py:267-276 [DERIVED].
- post: replay writes zero rows (content-derived ids + ON CONFLICT) — workers/workers/llm_direct.py:89-91 [DERIVED].
- ordering: symmetric predicates with `oid < sid` swap both endpoints and core types so A↔B and B↔A aggregate — workers/workers/llm_direct.py:165-169 [DERIVED].
- endpoint typing: core type = placed type of the same surface (by surface, then by normalized lookup), else `"Concept"` — workers/workers/llm_direct.py:155-158 [DERIVED].

### _endpoint_offsets — workers/workers/llm_direct.py:75-83
- returns offsets inside the quote when the surface occurs there (`quote[0] + inside`), else `_locate` hit in the chunk, else the whole quote `(quote[0], quote[1])` — workers/workers/llm_direct.py:79-83 [DERIVED].

### _mention_id — workers/workers/llm_direct.py:70-72
- returns `"mention_" + content_hash({"doc", "chunk", "type", "start", "end"})` — workers/workers/llm_direct.py:71-72 [DERIVED].

## effect surface
- Postgres INSERT: `entities` (ON CONFLICT (entity_id) DO UPDATE) — workers/workers/llm_direct.py:220-239; `mentions` — workers/workers/llm_direct.py:243-250; `facts` — workers/workers/llm_direct.py:254-258; `evidence` — workers/workers/llm_direct.py:262-265 [DERIVED].
- Postgres read inside entities upsert: `jsonb_array_elements_text(entities.raw_types || EXCLUDED.raw_types)` for the set-union — workers/workers/llm_direct.py:229-231 [DERIVED].
- No Qdrant, files, network, subprocess, or env flags appear in this unit.

## invariants

- INVARIANT: SYMMETRIC_PREDICATES == `frozenset({"CORRELATES_WITH", "ALTERNATIVE_TO", "SAME_AS", "RELATED_TO"})` — workers/workers/llm_direct.py:67 [DERIVED]
  fails-if: A↔B and B↔A stop aggregating onto one fact row — workers/workers/llm_direct.py:26-28.
- INVARIANT: `fact_id = _fact_id(pred, sid, oid, {})` with qualifiers always `"{}"` — workers/workers/llm_direct.py:173, 183 [DERIVED]
  fails-if: the same fact from N documents becomes N rows instead of one row with N evidence rows — workers/workers/llm_direct.py:23-25.
- INVARIANT: `entity_id = _entity_id(core, normalized_for_lookup(surface))` with `core_type` in the key — workers/workers/llm_direct.py:124, 163-164, 171-172 [DERIVED]
  fails-if: one surface seen in two documents of a corpus lands on two entity rows — workers/workers/llm_direct.py:14-19.
- INVARIANT: replay run → `written == {"entities": 0, "mentions": 0, "facts": 0, "evidence": 0}` (containment guard `WHERE NOT entities.raw_types @> EXCLUDED.raw_types OR entities.extractor_version IS NULL`, plus three `DO NOTHING`) — workers/workers/llm_direct.py:237-238, 250, 258, 265, 215-218 [DERIVED]
  fails-if: replays double-write rows and stage-artifact counts stop being idempotent.
- INVARIANT: `unknown_predicates == 0` in normal operation — workers/workers/llm_direct.py:144-145 [DERIVED]
  fails-if: gate predicate normalization regressed and relations are silently dropped.
- INVARIANT: unresolved pronouns never persist (entities and both endpoints checked) — workers/workers/llm_direct.py:118-120, 148-150 [DERIVED]
  fails-if: `'me'`/`'we'`/`'you'`/`'i'` endpoints become durable facts (13 ACCEPT facts previously) — workers/workers/llm_direct.py:103-106.

## determinism & idempotency
determinism: DETERMINISTIC apart from `stamp` (caller-supplied callable injects `generated_by_bundle_hash`) and the DB connection — workers/workers/llm_direct.py:92-93 [INFERRED: stamp closure is external input; all ids are pure hashes of inputs].
idempotency: SAFE — every id content-derived; entities upsert guarded by raw_types containment, mentions/facts/evidence `ON CONFLICT ... DO NOTHING` — workers/workers/llm_direct.py:89-91, 237-238, 250, 258, 265 [DERIVED].

## failure behaviour
- No try/except in this unit; DB errors from `cur.execute` propagate to the caller — workers/workers/llm_direct.py:211-265 [INFERRED: no handler exists, caller is the importer extract_worker.py].
- Chunk ids missing from `chunk_rows` are silently skipped (`row is None: continue`) for both entities and evidence — workers/workers/llm_direct.py:112-114, 138-140 [DERIVED].
- Unknown predicates and pronoun endpoints are counted in the return dict, not raised — workers/workers/llm_direct.py:144-146, 148-150, 272-274 [DERIVED].

## dumb-code flags
- `map_core_type` imported but never called in this file (comment says the old fallback used the TYPE mapper) — workers/workers/llm_direct.py:49, 152-154 [DERIVED].
- Import statement placed mid-file between constants after the GENERATION-STAMPING-V1 comment — workers/workers/llm_direct.py:55-58 [DERIVED].
- `"sentence_index": 0` hardcoded — workers/workers/llm_direct.py:192 [DERIVED].
- `"trigger_lemma": None` hardcoded — workers/workers/llm_direct.py:195 [DERIVED].
- GLiNER-era columns reused by the llm lane: `gliner_score` = `float(e.get("score", 1.0))` (default 1.0), `gliner_scores` = `"{}"` — workers/workers/llm_direct.py:131, 206, 244-247 [DERIVED].
- Endpoint fallback returns the whole quote span when the surface is found neither inside the quote nor in the chunk — workers/workers/llm_direct.py:83 [DERIVED].
- `admission_reason` and `semantic_contract` both set to `CONTRACT` (`"llm-direct-facts-v1"`); `anchor_kind` and `reference_basis` both `"ATTESTED_QUOTE"` — workers/workers/llm_direct.py:133 [DERIVED].
- Hardcoded provenance strings `"gate": "polymath-extraction-v1"`, `"gate_version": "attestation-levels-v1"` — workers/workers/llm_direct.py:178-179 [DERIVED].

## refactor notes
- Signature or return-key changes to `materialize` ripple to workers/workers/extract_worker.py, the sole importer — workers/workers/extract_worker.py (FACTS.importers) [DERIVED].
- Changing any id composition (`_entity_id`, `_fact_id`, `_evidence_id`, `_mention_id` args) or the symmetric swap re-keys rows: old and new ids coexist, breaking aggregation and replay-zero — workers/workers/llm_direct.py:67, 124, 173, 202-204, 70-72 [DERIVED].
- The four INSERT column lists must stay aligned with the shared tables the projections already consume ("no downstream change") — workers/workers/llm_direct.py:11-12, 220-223, 243-248, 254-256, 262-264 [DERIVED].
- `QUERY_POLICY_VERSION` is stamped into every mention row; bumping it in polymath_shared changes written values here — workers/workers/llm_direct.py:52, 132 [DERIVED].
- Pronoun gate depends on `polymath_shared.entity_admission.is_unresolved_pronoun`; removing it reintroduces pronoun endpoints — workers/workers/llm_direct.py:58, 118, 148 [DERIVED].

## VERIFY
```verify
grep -Fq 'CONTRACT = "llm-direct-facts-v1"' workers/workers/llm_direct.py
grep -Fq 'SYMMETRIC_PREDICATES = frozenset({"CORRELATES_WITH", "ALTERNATIVE_TO", "SAME_AS", "RELATED_TO"})' workers/workers/llm_direct.py
grep -Fq 'fid = _fact_id(pred, sid, oid, {})' workers/workers/llm_direct.py
grep -Fq '"gate_version": "attestation-levels-v1"' workers/workers/llm_direct.py
grep -Fq 'ON CONFLICT (mention_id) DO NOTHING' workers/workers/llm_direct.py
test "$(grep -c -F 'ON CONFLICT' workers/workers/llm_direct.py)" -ge 4
grep -Fq 'is_unresolved_pronoun' workers/workers/llm_direct.py
! grep -Fq 'map_core_type(' workers/workers/llm_direct.py
```
