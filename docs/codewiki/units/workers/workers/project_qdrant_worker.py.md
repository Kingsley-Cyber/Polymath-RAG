# unit: workers/workers/project_qdrant_worker.py
anchor: workers/workers/project_qdrant_worker.py:1-928

## purpose
Durable projection stage (`STAGE = "project_qdrant"`, `EVENT_TYPE = "project_qdrant.v1"`) that projects every child chunk of a run's corpus into the Qdrant collection `polymath_<corpus_hash>_<embedding_contract>`, plus routing representations (document/section summaries, child evidence, procedures, concepts, entity cards, latent rows) — workers/workers/project_qdrant_worker.py:1-18, 64-65, 5 [DERIVED]. Consumers are the retrieval lanes: production retrieval filters `representation_kind` ('routing_child' per pass1.py) and HYBRID uses the lexical sparse lane — workers/workers/project_qdrant_worker.py:334-337, 568-571 [DERIVED]. Postgres projection receipts are the commit point; Qdrant writes are re-drivable — workers/workers/project_qdrant_worker.py:12-15 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `process_event` | def | `(conn: Connection, event: dict) -> None` | workers/workers/project_qdrant_worker.py:734-910 | worker event loop [INFERRED: `run_worker` imported per FACTS.imports] |
| `run_forever` | def | `(poll_interval_s, batch_size) -> None` | workers/workers/project_qdrant_worker.py:913-924 | `polymath_shared.worker_runtime.run_worker` per FACTS.imports [INFERRED] |

All other defs are `_`-prefixed private helpers (see FACTS.symbols).

## contracts

**`process_event(conn, event)`**
- in: `event["payload"]`, `event["run_id"]`, optional `payload.get("corpus_id")` — workers/workers/project_qdrant_worker.py:735-737 [DERIVED]
- pre: corpus pin `embedding_contract_id` must resolve via `SHORT_NAMES` or `CONTRACTS`, else `ValueError` — workers/workers/project_qdrant_worker.py:92-104; falls back to `active_contract()` only when the corpus row predates the registry — workers/workers/project_qdrant_worker.py:97-98 [DERIVED]
- out: chunk points in `qdrant_collection_name(corpus_id, contract.contract_id)` — workers/workers/project_qdrant_worker.py:792; routing points under `NEURAL_EMBED_CONTRACT` — workers/workers/project_qdrant_worker.py:811-814; stage artifact `{"chunk_count", "embedding_contract"}` — workers/workers/project_qdrant_worker.py:756-759 [DERIVED]
- post: per-chunk `record_projection_attempt(..., KIND_CHUNK, chunk_id, receipt_hash(..., CONTRACT_VERSION), contract)` — workers/workers/project_qdrant_worker.py:797-805 [DERIVED]
- incremental: chunks/routing rows whose ACTIVE receipt hash already matches are skipped — workers/workers/project_qdrant_worker.py:769-786, 816-833 [DERIVED]

**`run_forever(poll_interval_s, batch_size)`**
- doc: "LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1." — workers/workers/project_qdrant_worker.py:913-924 (FACTS; body not in excerpt) [DERIVED]

## effect surface

| surface | detail | anchor |
|---|---|---|
| PG read | `chunks` (tier='child' + parent head) | workers/workers/project_qdrant_worker.py:226-233, 487-493, 584-588 |
| PG read | `corpora` (contract pin) | workers/workers/project_qdrant_worker.py:93 |
| PG read | `projection_receipts` (skip lookup) | workers/workers/project_qdrant_worker.py:639 |
| PG read | `retrieval_summaries` (active rows) | workers/workers/project_qdrant_worker.py:462-467 |
| PG read | `mentions`, `entities`, `facts`, `evidence` (entity cards, sparse surfaces) | workers/workers/project_qdrant_worker.py:387-396, 405-412, 573-578 |
| PG read | `procedure_artifacts`, `concept_artifacts` | workers/workers/project_qdrant_worker.py:514-520, 541-547 |
| PG read | `documents`, `runs` (joins) | workers/workers/project_qdrant_worker.py:228-229, 464-465, 518-519, 545-546 |
| PG write | `parent_enrichments` (FACTS.tables_written; write site is in the unshown tail 837-910) | workers/workers/project_qdrant_worker.py:837-910 [INFERRED] |
| Qdrant | create collection: dense `Distance.COSINE` + named `bm25` sparse with `Modifier.IDF` — workers/workers/project_qdrant_worker.py:187-192; upsert `wait=True` in batches of `UPSERT_BATCH = 128` — workers/workers/project_qdrant_worker.py:267-271 | workers/workers/project_qdrant_worker.py:187-192, 267-271 |
| network | Qdrant at `get_settings().stores.qdrant_url`, timeout `QDRANT_TIMEOUT_S = 300` — workers/workers/project_qdrant_worker.py:788-789, 834-836; `EmbedderClient` sidecar with `wait_ready` + `verify_pin` — workers/workers/project_qdrant_worker.py:147-156 | workers/workers/project_qdrant_worker.py:788-789, 147-156 |
| env | `POLYMATH_SIDECAR_READY_WAIT_S` = `'120'` — workers/workers/project_qdrant_worker.py:151-152; `POLYMATH_TEST_CRASH_AFTER_POINTS` = `'0'` — workers/workers/project_qdrant_worker.py:892 (FACTS) | workers/workers/project_qdrant_worker.py:151-152, 892 |
| module state | `_TELEMETRY` — workers/workers/project_qdrant_worker.py:112; `_SPARSE_CAPABLE` — workers/workers/project_qdrant_worker.py:195 | workers/workers/project_qdrant_worker.py:112, 195 |

## invariants
- INVARIANT: chunk point id == `qdrant_point_uuid(chunk["chunk_id"])` ("point ids are the source chunk ids — Qdrant never invents identity") — workers/workers/project_qdrant_worker.py:9, 323 [DERIVED]
  fails-if: retries create duplicate points; idempotent upsert broken.
- INVARIANT: receipt commit happens AFTER the Qdrant write (receipts are the commit point) — workers/workers/project_qdrant_worker.py:12-13, 293-296, 797-805 [DERIVED]
  fails-if: crash between write and receipt leaves an orphan point; VERIFY_PROJECTIONS acceptance test 7 detects — workers/workers/project_qdrant_worker.py:14-15.
- INVARIANT: `_RECEIPT_LOOKUP_BATCH` = 10,000 rows × 3 params + 1 = 30,001 ≤ 65,535 libpq ceiling — workers/workers/project_qdrant_worker.py:607-608, 634-645 [DERIVED]
  fails-if: unbatched VALUES on a 19k+ corpus fails "number of parameters must be between 0 and 65535" — workers/workers/project_qdrant_worker.py:630-632.
- INVARIANT: sidecar embed batch ≤ `EMBED_BATCH = 16` (chunk lane) and ≤ `contract.batch_limit or 32` (routing lane) — workers/workers/project_qdrant_worker.py:107, 158-160, 697-700 [DERIVED]
  fails-if: one book-sized call exceeds the HTTP client timeout ("timed out") — workers/workers/project_qdrant_worker.py:138-141.
- INVARIANT: chunk lane selects only `c.tier = 'child'`; parents route via `routing_section_summary` — workers/workers/project_qdrant_worker.py:219-223, 231 [DERIVED]
  fails-if: parent points duplicate section cards and pollute unfiltered searches — workers/workers/project_qdrant_worker.py:219-223.
- INVARIANT: routing points always embed under `NEURAL_EMBED_CONTRACT` even when the corpus pin differs — workers/workers/project_qdrant_worker.py:807-813 [DERIVED]
  fails-if: hash vectors land semantically next to neural vectors in one collection — workers/workers/project_qdrant_worker.py:807-810.
- INVARIANT: sparse vector attached only when `_collection_has_sparse(collection)` is true; legacy collections stay dense-only — workers/workers/project_qdrant_worker.py:702, 724-729, 179-184 [DERIVED]
  fails-if: lexical lane silently skipped (error_code `SPARSE_LANE_SKIPPED_LEGACY_COLLECTION`) — workers/workers/project_qdrant_worker.py:210-214.
- INVARIANT: entity card text ≤ `_ENTITY_CARD_MAX_CHARS` = 600; aliases ≤ 6; relations ≤ 6 — workers/workers/project_qdrant_worker.py:372-374, 429-435, 481 [DERIVED]
  fails-if: unbounded card text inflates per-entity embed cost.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` at workers/workers/project_qdrant_worker.py:122, 159, 162, 268, 271, 297, 315, 775, 777, 900; network Qdrant workers/workers/project_qdrant_worker.py:788-789, 834-836 and embedder sidecar workers/workers/project_qdrant_worker.py:147-161; db receipt lookups workers/workers/project_qdrant_worker.py:636-645; env workers/workers/project_qdrant_worker.py:151-152, 892; shared module dicts `_TELEMETRY` workers/workers/project_qdrant_worker.py:112 and `_SPARSE_CAPABLE` workers/workers/project_qdrant_worker.py:195)
idempotency: SAFE (point ids are source ids so upserts overwrite — workers/workers/project_qdrant_worker.py:9, 323, 705; receipt-hash skip makes retries incremental — workers/workers/project_qdrant_worker.py:611-648, 769-786, 816-833; a lost checkpoint costs re-work, never correctness — workers/workers/project_qdrant_worker.py:689-691)

## failure behaviour
- `_collection_exists`: any `Exception` swallowed → `return False` — workers/workers/project_qdrant_worker.py:174; auth/network errors read as "collection missing" [INFERRED: no error typing on the handler].
- `_collection_has_sparse`: `Exception` handled → `ok = False`, logs `SPARSE_LANE_SKIPPED_LEGACY_COLLECTION` — workers/workers/project_qdrant_worker.py:206, 210-214; caller then writes dense-only points.
- `_checkpoint_chunks`: `Exception` swallowed → warning "chunk checkpoint failed; progress will be re-done", `error_code="checkpoint_failed"` — workers/workers/project_qdrant_worker.py:311-313.
- `_checkpoint_routing`: same swallow — workers/workers/project_qdrant_worker.py:688-693.
- Raised: `ValueError` for unknown pinned contract — workers/workers/project_qdrant_worker.py:100-103; `SidecarUnavailable` when the readiness gate times out — workers/workers/project_qdrant_worker.py:150-155.

## dumb-code flags
- Docstring says consumes `extracted.v1` — workers/workers/project_qdrant_worker.py:3 — but `EVENT_TYPE = "project_qdrant.v1"` — workers/workers/project_qdrant_worker.py:65. Stale docstring [DERIVED].
- `"routing_child"` hardcoded at workers/workers/project_qdrant_worker.py:339 while the constant `ROUTING_KIND_CHILD = "routing_child"` is defined later at workers/workers/project_qdrant_worker.py:360.
- Dead branch: `else "parent_summary"` at workers/workers/project_qdrant_worker.py:340 is unreachable — `_chunks_for_run` filters `c.tier = 'child'` — workers/workers/project_qdrant_worker.py:231 [INFERRED: WHERE clause guarantees tier].
- Duplicated literal `"neural-embed-v1"` in `stage_contract_hash` — workers/workers/project_qdrant_worker.py:751 — duplicates `NEURAL_EMBED_CONTRACT` used at workers/workers/project_qdrant_worker.py:813; nothing keeps them in sync.
- `"child_chunk"` embed-kind literal duplicated at workers/workers/project_qdrant_worker.py:144 and 161.
- Two independent constants both `"1.1.0"`: `CONTRACT_VERSION` — workers/workers/project_qdrant_worker.py:67 — vs `ROUTING_CONTRACT_VERSION` — workers/workers/project_qdrant_worker.py:370; easy to desync.
- Batch constants diverge between lanes: chunk path fixed `EMBED_BATCH = 16` — workers/workers/project_qdrant_worker.py:107, 158 — vs routing path `contract.batch_limit or 32` — workers/workers/project_qdrant_worker.py:697-698.
- `checkpoint_every` defaults differ: 64 (chunk lane) — workers/workers/project_qdrant_worker.py:277 — vs 512 (routing lane) — workers/workers/project_qdrant_worker.py:652.
- Magic number `left(c.text, 120)` — workers/workers/project_qdrant_worker.py:584 — unrelated to the other literal `120` (sidecar wait default) at workers/workers/project_qdrant_worker.py:151-152.
- `_SPARSE_CAPABLE` caches per collection name for process lifetime — workers/workers/project_qdrant_worker.py:198-208; after `scripts/migrate_routing_sparse.py` runs, a live worker keeps skipping the lexical lane until restart [INFERRED: no invalidation path visible].
- `_TELEMETRY` is a module global reset per event — workers/workers/project_qdrant_worker.py:112, 115-123, 738; concurrent `process_event` calls would interleave counters [INFERRED].
- FACTS.tables_read lists a table `lateral`; no such table in visible SQL — the only LATERAL is the `CROSS JOIN LATERAL` at workers/workers/project_qdrant_worker.py:410-411 [INFERRED: analyzer read the SQL keyword as a table].

## refactor notes
- `representation_kind` payload values are load-bearing for production retrieval filters ('routing_child' per pass1.py) — renaming kinds breaks the FAST/dense lane — workers/workers/project_qdrant_worker.py:334-337, 358-368.
- Changing `CONTRACT_VERSION` or `ROUTING_CONTRACT_VERSION` changes every receipt hash → full corpus re-embed (by design: "a contract change ... produce[s] a different hash and [is] re-projected") — workers/workers/project_qdrant_worker.py:306-308, 683-685, 621-624.
- Dense vector is stored under the empty name `""` and sparse under `SPARSE_VECTOR_NAME` — workers/workers/project_qdrant_worker.py:726-727; readers must know both names.
- Collections are per (corpus, contract): `qdrant_collection_name(corpus_id, contract.contract_id)` — workers/workers/project_qdrant_worker.py:5, 792; legacy dense-only collections require `scripts/migrate_routing_sparse.py` — workers/workers/project_qdrant_worker.py:183-184, 211-214.
- `_write_points_checkpointed`/`_checkpoint_chunks` (workers/workers/project_qdrant_worker.py:275-316) and `_write_routing_points`/`_checkpoint_routing` (workers/workers/project_qdrant_worker.py:651-693) are the same slice/checkpoint pattern twice; unifying changes crash-replay bounds for both lanes.
- Corpus pin is the retrieval authority: "A projection must never run under a different contract than the vectors already stored for that corpus" — workers/workers/project_qdrant_worker.py:80-85.
- `run_forever` lease semantics ("claim depth 1") — workers/workers/project_qdrant_worker.py:913 — is a correctness contract for event claiming.

## VERIFY
```verify
grep -Fq 'EMBED_BATCH = 16' workers/workers/project_qdrant_worker.py
grep -Fq 'UPSERT_BATCH = 128' workers/workers/project_qdrant_worker.py
grep -Fq 'checkpoint_every: int = 512' workers/workers/project_qdrant_worker.py
grep -Fq '"POLYMATH_SIDECAR_READY_WAIT_S", "120"' workers/workers/project_qdrant_worker.py
grep -Eq 'c\.tier = .child.' workers/workers/project_qdrant_worker.py
grep -Fq 'project_qdrant.v1' workers/workers/project_qdrant_worker.py
test "$(grep -c -F 'routing_child' workers/workers/project_qdrant_worker.py)" -ge 3
```
