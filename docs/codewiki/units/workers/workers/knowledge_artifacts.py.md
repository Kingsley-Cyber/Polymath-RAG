# unit: workers/workers/knowledge_artifacts.py
anchor: workers/workers/knowledge_artifacts.py:1-188

## purpose
Persister for the `compile_objects.v1` stage: compiles Procedure and Concept artifacts as first-class objects and writes them to Postgres; they are "NOT facts and never touch the entity graph here" — workers/workers/knowledge_artifacts.py:1-8, 65-67 [DERIVED]. Split out of `extract_worker` on 2026-09-03 (LLM-DIRECT-CANON, ADR-0017) as a separate deterministic lane, behaviour claimed byte-for-byte identical to the old `_persist_knowledge_artifacts` — workers/workers/knowledge_artifacts.py:3-7 [DERIVED]. Also records per-lane opportunity/acceptance counters (SEMANTIC-LANE-LIVENESS-V1) — workers/workers/knowledge_artifacts.py:84-89 [DERIVED].

## public surface
All symbols are underscore-private; the stage entry point is `_persist_knowledge_artifacts`.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_persist_knowledge_artifacts` | function | (conn, *, corpus_id, doc_id, doc_text, chunk_ids, durable_surfaces) -> dict | workers/workers/knowledge_artifacts.py:61-187 | workers/workers/_small-modules (FACTS.importers) |
| `_record_lane_attempt` | function | (conn, *, doc_id, corpus_id, lane, opportunities, accepted, capped) -> None | workers/workers/knowledge_artifacts.py:29-58 | `_persist_knowledge_artifacts` at workers/workers/knowledge_artifacts.py:171-184 |
| `_bundle_hash` | function | () -> str | workers/workers/knowledge_artifacts.py:20-26 | workers/workers/knowledge_artifacts.py:58, :133, :168 |

## contracts

`_persist_knowledge_artifacts` — workers/workers/knowledge_artifacts.py:61-187
- in: `conn: Connection`; keyword-only `corpus_id: str`, `doc_id: str`, `doc_text: str`, `chunk_ids: list[str]`, `durable_surfaces: list[str]` — workers/workers/knowledge_artifacts.py:61-64 [DERIVED]
- out: counts dict with keys `procedures`, `concepts`, `routing_disabled` (workers/workers/knowledge_artifacts.py:81-82) plus `procedure_opportunities`, `concept_opportunities` (workers/workers/knowledge_artifacts.py:185-186); returned at :187 [DERIVED]
- pre: none enforced; compilers are self-gating LOCAL-EVIDENCE detectors — "no procedural or conceptual evidence → no artifact"; `classify_document` output is routing metadata only and "never vetoes a compiler" — workers/workers/knowledge_artifacts.py:70-74, 80 [DERIVED]
- post: every yielded procedure row upserted into `procedure_artifacts` (workers/workers/knowledge_artifacts.py:111-134); every concept row upserted into `concept_artifacts` (:144-169); lane attempts recorded for lanes `"procedure"` and `"concept"` (:171-184); replay idempotent via content-addressed ids (:68)

`_record_lane_attempt` — workers/workers/knowledge_artifacts.py:29-58
- in: keyword-only `doc_id: str`, `corpus_id: str`, `lane: str`, `opportunities: int`, `accepted: int`, `capped: bool` — workers/workers/knowledge_artifacts.py:29-31 [DERIVED]
- out: None — workers/workers/knowledge_artifacts.py:31 [DERIVED]
- post: one upserted row in `knowledge_lane_attempts` keyed `(doc_id, lane)` with `bundle_hash = _bundle_hash()` — workers/workers/knowledge_artifacts.py:45-58 [DERIVED]
- post: disposition mapping — workers/workers/knowledge_artifacts.py:37-42 [DERIVED]

| condition | disposition |
|---|---|
| `opportunities <= 0` | `NO_OPPORTUNITY` |
| `accepted > 0` | `ACCEPTED` |
| else | `GATED` |

`NO_OPPORTUNITY` is a CORRECT outcome and must stay distinguishable from `GATED` (the dead-feature signal) — workers/workers/knowledge_artifacts.py:32-36 [DERIVED].

`_bundle_hash` — workers/workers/knowledge_artifacts.py:20-26
- out: `bundle_id(compute_execution_bundle())`, memoized in module global `_BUNDLE_STAMP` (`str | None = None` at :17); import is lazy — workers/workers/knowledge_artifacts.py:17, 23-25 [DERIVED]

## effect surface
- Postgres INSERT ... ON CONFLICT (no reads; FACTS.tables_read = []):
  - `knowledge_lane_attempts` — cols `doc_id, corpus_id, lane, opportunities, accepted, capped, disposition, bundle_hash`; conflict `(doc_id, lane)` — workers/workers/knowledge_artifacts.py:45-56 [DERIVED]
  - `procedure_artifacts` — cols `procedure_id, document_id, corpus_id, title, goal, steps_json, tools_json, confidence, source_chunk_ids, provenance, generated_by_bundle_hash`; conflict `(procedure_id)` — workers/workers/knowledge_artifacts.py:117-125 [DERIVED]
  - `concept_artifacts` — cols `concept_id, document_id, corpus_id, name, description, domain, related_entities, source_sentence, confidence, supporting_chunks, provenance, generated_by_bundle_hash`; conflict `(concept_id)` — workers/workers/knowledge_artifacts.py:152-160 [DERIVED]
- JSON serialization via `json.dumps` for `steps`, `tools`, `provenance`, `related_entities` — workers/workers/knowledge_artifacts.py:129-132, 164-167 [DERIVED]
- No Qdrant, file, network, subprocess, or env-flag access visible in SOURCE.

## invariants
INVARIANT: disposition = `NO_OPPORTUNITY` iff `opportunities <= 0`, else `ACCEPTED` iff `accepted > 0`, else `GATED` — workers/workers/knowledge_artifacts.py:37-42 [DERIVED]
  fails-if: GATED collapses into NO_OPPORTUNITY and the dead-feature signal (:34-36) becomes unreadable.
INVARIANT: counts["procedures"] == procedure_artifacts rows inserted this call — workers/workers/knowledge_artifacts.py:111-134 [DERIVED]
  fails-if: liveness `accepted` counter understates real lane output.
INVARIANT: counts["concepts"] == concept_artifacts rows inserted this call — workers/workers/knowledge_artifacts.py:144-169 [DERIVED]
  fails-if: same, concept lane.
INVARIANT: procedure accepted <= procedure opportunities — workers/workers/knowledge_artifacts.py:99-101 vs :111-114 [INFERRED: comment :95-98 states counter/compiler version mismatch would report accepted > opportunities seen]
  fails-if: lane looks like it manufactures evidence.
INVARIANT: `capped=False` on both recorded lanes — workers/workers/knowledge_artifacts.py:174, :184 [DERIVED]
  fails-if: a reintroduced storage cap without `capped=True` reads as admission refusal, i.e. silent truncation (:179-184 comment).
INVARIANT: conflict keys are exactly `(doc_id, lane)`, `(procedure_id)`, `(concept_id)` — workers/workers/knowledge_artifacts.py:49, :122, :157 [DERIVED]
  fails-if: replay duplicates rows; idempotency claim at :68 breaks.

## determinism & idempotency
determinism: DETERMINISTIC (self-described "separate deterministic lane", workers/workers/knowledge_artifacts.py:4-5); sole clock-dependent value is `created_at = now()` (db clock, workers/workers/knowledge_artifacts.py:55); `_bundle_hash` frozen per process after first call (:20-26) [DERIVED]
idempotency: SAFE — all three writes are upserts on stable keys; artifact ids content-addressed so replay converges (workers/workers/knowledge_artifacts.py:68, :49, :122, :157); caveat: `created_at = now()` bumps on every conflict-update (:55) [DERIVED]

## dumb-code flags
- `split_sentences` imported twice from `workers.summarizer` — as `_split` (workers/workers/knowledge_artifacts.py:92) and bare again (:138); `doc_text` re-split at :146 although `_doc_sentences` already exists at :94. Duplicate import + duplicate work.
- `capped` threaded through `_record_lane_attempt` (:31, :46, :52) but both call sites hardcode `capped=False` (:174, :184) — no path in this file can store `capped=true`.
- Procedure upsert refreshes only `source_chunk_ids, provenance, generated_by_bundle_hash` — workers/workers/knowledge_artifacts.py:123-125; `title, goal, steps_json, tools_json, confidence` keep first-write values. Concept upsert refreshes only `supporting_chunks, provenance, generated_by_bundle_hash` — :158-160; `name, description, domain, related_entities, source_sentence, confidence` keep first-write values. [DERIVED]
- FACTS.tables_written lists `"set"` — no such table exists in SOURCE; static-analysis artifact.
- Confidence default `0.0` duplicated at workers/workers/knowledge_artifacts.py:130 and :165.

## refactor notes
- Blast radius: the three table schemas and conflict keys (workers/workers/knowledge_artifacts.py:45-58, :117-133, :152-168) — changing any column or key breaks replay idempotency (:68) and downstream readers of the liveness table.
- Counter/compiler version coupling: `count_opportunities_v2` must move in lockstep with `compile_procedures` (workers/workers/knowledge_artifacts.py:95-101); counters deliberately share the compilers' helpers so they "cannot drift" (:87-89).
- `_BUNDLE_STAMP` module-global memo (workers/workers/knowledge_artifacts.py:17, :20-26): a long-lived process keeps stamping the first-seen bundle hash into all three tables (:58, :133, :168) — no invalidation path exists in SOURCE [INFERRED].
- `durable_surfaces` is lowercased only for the opportunity counter (`e.lower()` at workers/workers/knowledge_artifacts.py:100) but passed raw to both compilers (:113, :121); admission case-handling changes must be mirrored or opportunities/accepted diverge [INFERRED].
- Docstring pins external contract names — `compile_objects.v1`, ADR-0017, byte-for-byte prior behaviour (workers/workers/knowledge_artifacts.py:3-7), `PROCEDURE_ARTIFACT_V2 (P3)` one-artifact-per-LOCAL-TASK (:106-110), `CONCEPT_CONTRACT_V2 (P4)` no storage ceiling, top-N only as `summary_rank` (:139-143) — refactors must preserve or update these references.

## VERIFY
```verify
grep -Fq 'INSERT INTO knowledge_lane_attempts' workers/workers/knowledge_artifacts.py
grep -Fq 'ON CONFLICT (procedure_id) DO UPDATE SET' workers/workers/knowledge_artifacts.py
grep -Fq 'ON CONFLICT (concept_id) DO UPDATE SET' workers/workers/knowledge_artifacts.py
grep -Fq 'count_opportunities_v2' workers/workers/knowledge_artifacts.py
! grep -Fq 'capped=True' workers/workers/knowledge_artifacts.py
test "$(grep -c -F 'capped=False' workers/workers/knowledge_artifacts.py)" -ge 2
```
