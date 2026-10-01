# unit: workers/workers/llm_provider.py
anchor: workers/workers/llm_provider.py:1-935

## purpose
The LLM proposal lane of the extract stage (LOCAL-LLM-EXTRACTION-V1), the GLiNER-replacement seam (directive 2026-08-29): the model proposes, `gate.py` validates, the frozen deterministic layer decides; identity, Harbor admission, E1–E7, predicate compiler, F1–F8 untouched. — workers/workers/llm_provider.py:1-7 [DERIVED]
Lane routing is the byte-threshold THROUGHPUT policy: above threshold always cloud; at/below prefers local, with cloud riding as an explicit ASSIST. — workers/workers/llm_provider.py:9-13 [DERIVED]

## public surface
| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| `Neighborhood` | class | `nid: str; chunks: list[tuple[str, str]]`, property `char_len -> int` | workers/workers/llm_provider.py:56-62 | extract_worker.py |
| `build_neighborhoods` | def | `(child_chunks: list[dict], max_chars: int \| None = None) -> list[Neighborhood]` | workers/workers/llm_provider.py:73-136 | extract_worker.py |
| `contract_identity` | def | `() -> dict` | workers/workers/llm_provider.py:144-208 | extract_worker.py |
| `select_lane` | def | `(source_bytes: int, affinity: str \| None = None)` | workers/workers/llm_provider.py:216-222 | extract_worker.py |
| `make_client` | def | `(lane: str, doc_id: str = "", ring_offset: int = 0) -> LLMExtractionClient` | workers/workers/llm_provider.py:225-243 | extract_worker.py |
| `batch_lane_indices` | def | `(slice_idx: list[int], n_batches: int, doc_id: str) -> list[int]` | workers/workers/llm_provider.py:246-259 | extract_worker.py |
| `spread_decision` | def | `(queue_depth: int \| None, doc_id: str, n_neighborhoods: int) -> bool` | workers/workers/llm_provider.py:262-271 | extract_worker.py |
| `run_proposals` | def | `(neighborhoods, *, lane, source_bytes, doc_id="", assist=False, queue_depth=None, active_rank=None, active_docs=None, call_cache=None) -> tuple[list[LLMCallResult], NormalizedExtraction]` | workers/workers/llm_provider.py:295-741 | extract_worker.py |
| `to_precomputed_entities` | def | `(merged, label_compositions, all_chunk_ids)` | workers/workers/llm_provider.py:856-879 | extract_worker.py |
| `to_evidence_spans` | def | `(merged)` | workers/workers/llm_provider.py:882-892 | extract_worker.py |
| `ledger_items` | def | `(merged)` | workers/workers/llm_provider.py:895-915 | extract_worker.py |
| `call_receipts` | def | `(results)` | workers/workers/llm_provider.py:918-934 | extract_worker.py |

Constants: `LLM_ENTITY_VERSION="polymath-extraction-v1-entity"` (:41), `LLM_EVIDENCE_VERSION="polymath-extraction-v1-evidence"` (:42), `LLM_RELATION_CLASS="llm_relation"` (:43), `LLM_MIN_CHUNK_WORDS=15` (:44), `NEIGHBORHOODS_PER_CALL=4` (:46) — workers/workers/llm_provider.py:41-46 [DERIVED].
Private tail (`_reissue` :796-825, `_ensure_controller_store` :831-841, `_controller_snapshot` :844-853) exists only in FACTS; SOURCE cut at line 773. "used by" is per-module (FACTS.importers = `workers/workers/extract_worker.py`), per-symbol use unknown [INFERRED].

## contracts
**build_neighborhoods — workers/workers/llm_provider.py:73-136**
- in: rows keyed `text`, `char_start`, `chunk_id`, `parent_id`, optional `region_role` — workers/workers/llm_provider.py:97-108 [DERIVED]
- pre: none; sorts by `(char_start, chunk_id)` itself — workers/workers/llm_provider.py:97 [DERIVED]
- post: skips `< LLM_MIN_CHUNK_WORDS` words (:98), `_region_is_noise(row.get("region_role"))` (:102-104), `is_noisy(_chunk_heading_kind(text))` (:105-107); per parent `k = max(1, -(-total // max_chars))` buckets (:117), a bucket exceeds `max_chars` only when a single child does (:124-129); `nid = f"{pid}:{len(out)}"` (:135); the stored parent summary row is never sent — workers/workers/llm_provider.py:86-87 [DERIVED]
- default: `max_chars = get_settings().worker.llm_max_neighborhood_chars` — workers/workers/llm_provider.py:92-93 [DERIVED]

**contract_identity — workers/workers/llm_provider.py:144-208**
- out: keys `contract, cloud_min_bytes, models, cloud_pool, neighborhood, prompt_sha256, ontology_sha256, type_fallbacks_sha256, generation, chunk_kind_sha256, limiter_seeds, materialization, gate, coverage, region_role_sha256, entity_version, evidence_version` — workers/workers/llm_provider.py:171-208 [DERIVED]
- post: any change to a hashed input must yield a NEW receipt so the document is re-extracted and old facts stay attributable — workers/workers/llm_provider.py:145-148 [DERIVED]

**make_client — workers/workers/llm_provider.py:225-243**
- in: `"local"` → `s.sidecars.llm_local_extract_url` / `llm_local_extract_model` (:228-230); `"cloud"` → `select_cloud_endpoint(doc_id, ring_offset)` (:234-235) [DERIVED]
- raises: `ValueError(f"unknown lane: {lane!r}")` — workers/workers/llm_provider.py:243 [DERIVED]

**run_proposals — workers/workers/llm_provider.py:295-741**
- in: local = one client, `extract_batched`, one neighborhood per prompt (:310-311, :324-331); cloud = rank slicing + size packing + receipts + 413 ladder (:333-364) [DERIVED]
- post: every neighborhood appears in `merged.dispositions` (:712-714); stats include `neighborhoods_sent/returned/returned_empty/reissued/recovered/incomplete_kept/dropped/unaccounted`, `parents_total/parents_with_extraction`, `calls*`, `controller.before/after/persisted` (:715-740) [DERIVED]
- raises: `ExtractionTransportError` when any result has `error_class == "LIMITER_REFUSED"` — workers/workers/llm_provider.py:643-647, 747-752 [DERIVED]

## effect surface
- Postgres: no tables read/written directly (FACTS `tables_read: []`, `tables_written: []`); `PostgresControllerStore` attached once per process via `_ensure_controller_store` (:831-841, FACTS), surfaced through `REGISTRY.store_attached` — workers/workers/llm_provider.py:32,739 [DERIVED]
- Network: urllib GET `{base_url}/ready` readiness poll (:282-288); LLM calls to local `s.sidecars.llm_local_extract_url` (:230, :327) or cloud pool endpoints via `select_cloud_endpoint` / `select_cloud_endpoint_abs` — workers/workers/llm_provider.py:234-235,378 [DERIVED]
- Settings via `get_settings()`: `worker.llm_max_neighborhood_chars` (:93,:180), `worker.cloud_min_bytes` (:183,:221,:231), `worker.extraction_provider` (:195), `sidecars.llm_local_extract_url` (:230,:327), `sidecars.llm_local_extract_model` (:174,:230), `sidecars.llm_cloud_model` (:175); defaults not shown in material [DERIVED]
- Concurrency: `ThreadPoolExecutor` at :634 and :819 (FACTS nondeterminism). No files, Qdrant, or subprocess in material. [DERIVED]

## invariants
INVARIANT: cloud batch neighborhood count <= `NEIGHBORHOODS_PER_CALL` == 4 — workers/workers/llm_provider.py:407-408 [DERIVED]
  fails-if: dense batch overflows the OUTPUT budget → `finish_reason == "length"` truncation forces splits (:547-556)
INVARIANT: kept chunk word count >= `LLM_MIN_CHUNK_WORDS` == 15 — workers/workers/llm_provider.py:98 [DERIVED]
  fails-if: <15-word structural stubs burn prompt tokens for zero extraction value (:44, :84)
INVARIANT: buckets per parent k == `max(1, -(-total // max_chars))`, hard cap `max_chars` breached only by a single child — workers/workers/llm_provider.py:117-129 [DERIVED]
  fails-if: last planned bucket absorbs every remaining child (:124-126)
INVARIANT: reissue set == `{"missing", "incomplete", "quarantined", "unaccounted"}` (`_REISSUE_DISPOSITIONS`, :744), applied at :659 — workers/workers/llm_provider.py:744,659 [DERIVED]
  fails-if: a neighborhood silently missing; census must refuse promotion (:649-656)
INVARIANT: batch i lane == `slice_idx[(i + h) % n]` with `h = int(blake2b("slice-start:" + doc_id)) % n` — workers/workers/llm_provider.py:258-259 [DERIVED]
  fails-if: replay picks different lanes; head-of-ring skew (ledger 2026-09-24: gemini1 155 attempts, gemini5 4, gemini6 0 — :252)
INVARIANT: `spread_decision` true iff `queue_depth is not None and queue_depth <= 1 and bool(doc_id) and n_neighborhoods > 4` — workers/workers/llm_provider.py:270-271 [DERIVED]
  fails-if: spreading under queue contention starves other extract docs (:264-269)
INVARIANT: `pool_size == max(1, min(len(work), 4 * n_lanes, 24))` — workers/workers/llm_provider.py:627 [DERIVED]
  fails-if: thread fan-out beyond provider limits re-creates the 429 storm (:334-336)
INVARIANT: a 401/403 endpoint stays in `_dead` for the whole run and every failover scan skips it — workers/workers/llm_provider.py:485-503,534-535 [DERIVED]
  fails-if: one revoked key fails a whole document's extract stage (:474-477)
INVARIANT: quarantined call gets at most ONE cross-host semantic escape (`depth < 1`) — workers/workers/llm_provider.py:580-582 [DERIVED]
  fails-if: unbounded cross-provider retry loops

## determinism & idempotency
determinism: NONDETERMINISTIC (ThreadPoolExecutor concurrency at :634 and :819 [FACTS]; live LLM endpoints; `time.monotonic` ready-poll loop :283-291). Dispatch is stable per doc: receipt key = `"ecr_" + content_hash({ident, batch})[:40]` with `ident = content_hash({"contract": contract_identity()})` (:418, :421-424); ring start hashed from doc_id (:258). [DERIVED]
idempotency: SAFE for cloud calls — receipts persist content-addressed and a stage retry replays cached raws through the same sanitize path, paying only for calls never made (:349-351, :429-442); AIMD limiter controller state still advances and persists per document (:735-740). [DERIVED]

## failure behaviour
| site | type | behaviour | caller sees | anchor |
|---|---|---|---|---|
| :289-290 | Exception | swallowed `pass` in ready-poll | `_wait_local_ready` returns False after `timeout_s=180.0`; call proceeds and fails loudly | workers/workers/llm_provider.py:274-292 [DERIVED] |
| :432-433 | Exception | `raw = None` on `cache_get` failure | treated as cache miss; fresh paid call | workers/workers/llm_provider.py:429-433 [DERIVED] |
| :468-469 | Exception | `break` out of `cache_put` arity probe | receipt silently not persisted | workers/workers/llm_provider.py:462-469 [DERIVED] |
| :574-575 | Exception | swallowed `pass` on `model_copy` keep-filter | partial truncated items not back-filled onto `r`; split halves still returned | workers/workers/llm_provider.py:566-578 [DERIVED] |

Raised: `ValueError` unknown lane (:243); `ExtractionTransportError` on limiter refusal — "stage must retry, not complete" (:750-752); transport errors re-raised when no cross-host escape lane exists (:504, :520, :541). Log `error_code`s: `EXTRACTION_LANE_AUTH_DEAD` (:491-492), `EXTRACTION_LANE_FAILOVER` (:545, :613), `EXTRACTION_SEMANTIC_ESCAPE` (:599-600), `EXTRACTION_V2_DISPATCH` (:633), `EXTRACTION_V2_STATS` (:641). [DERIVED]

## dumb-code flags
- `re` pulled in via `__import__("re")` twice on one line instead of a top-level import — workers/workers/llm_provider.py:48 [DERIVED]
- comprehension variable `s` shadows `s = get_settings().worker` (:316) at `slice_idx = [base + s for s in range(n_lanes)]` — workers/workers/llm_provider.py:390 [DERIVED]
- `client.attempt_stage, client.attempt_function = "extract", "EXTRACT"` duplicated — workers/workers/llm_provider.py:241,384 [DERIVED]
- cloud client construction duplicated in `make_client` (:236-241) and `_client_abs` (:379-386), including identical `ep.cloud_opts if ep.name != "primary" else None` (:239, :382) — [DERIVED]
- same attribute, two getattr defaults: `"request_char_budget", 60000` (:393) vs `"request_char_budget", 0` (:395) — workers/workers/llm_provider.py:391-395 [DERIVED]
- `cache_put` arity duck-probe `for n_args in (8, 7, 6, 5)` — workers/workers/llm_provider.py:462 [DERIVED]
- `_reissue_call = _call` guarded by `except (NameError, UnboundLocalError)` because `_call` only exists on the cloud path — workers/workers/llm_provider.py:663-665 [DERIVED]
- `extract_from_raw(payload, raw)` TypeError fallback for legacy client doubles — workers/workers/llm_provider.py:441-442 [DERIVED]

## refactor notes
- `contract_identity` (:144-208) feeds both the extract-stage contract hash and the receipt cache key `_ident` (:418): changing any hashed input (SYSTEM_PROMPT, RELATION_ONTOLOGY/PREDICATE_ALIASES, GATE_VERSION, chunk_kind `_RULES`/`NOISY_KINDS`, pool fingerprint, `cloud_min_bytes`, neighborhood params, GENERATION_CONFIG, limiter seeds, region_role fingerprint) re-extracts every document and orphans old receipts. [DERIVED]
- Sole importer is `workers/workers/extract_worker.py` (FACTS.importers); the bare local `make_client(lane)` call shape is kept for frozen test doubles — workers/workers/llm_provider.py:322-324 [DERIVED]
- Receipt `cache_put` is probed at arities 8→5 (:460-469): changing the 8-arg schema or arg order silently degrades to an older ledger double or drops persistence. [DERIVED]
- `_STORE_ATTACHED` defaults `false` (:828, FACTS), making `_ensure_controller_store` a once-per-process side effect; forks/test isolation that do not reset it share controller snapshots — workers/workers/llm_provider.py:828-841 [INFERRED: process-global flag implies shared state across non-reset forks]
- `LLM_ENTITY_VERSION` / `LLM_EVIDENCE_VERSION` are contract fields (:206-207); renaming them breaks stored entity/evidence attribution. [DERIVED]

## VERIFY
```verify
grep -Fq 'NEIGHBORHOODS_PER_CALL = 4' workers/workers/llm_provider.py
grep -Fq 'LLM_MIN_CHUNK_WORDS = 15' workers/workers/llm_provider.py
grep -Fq 'frozenset({"missing", "incomplete", "quarantined", "unaccounted"})' workers/workers/llm_provider.py
grep -Fq 'EXTRACTION_LANE_AUTH_DEAD' workers/workers/llm_provider.py
grep -Fq 'if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):' workers/workers/llm_provider.py
grep -Fq 'timeout_s: float = 180.0, poll_s: float = 3.0' workers/workers/llm_provider.py
test "$(grep -c -F 'ThreadPoolExecutor' workers/workers/llm_provider.py)" -ge 2
```
