# unit: workers/workers/llm_provider.py
anchor: workers/workers/llm_provider.py:1-953

## purpose
The LLM proposal lane inside the extract stage — the GLiNER-replacement seam (owner directive 2026-08-29): the model proposes, `gate.py` validates, and the frozen deterministic layer decides everything else; identity, Harbor admission, E1–E7, the predicate compiler and F1–F8 are untouched. workers/workers/llm_provider.py:1-14 [DERIVED]
Lane routing is byte-threshold THROUGHPUT: above `cloud_min_bytes` always cloud; at/below prefers local and may ride the cloud pool as an explicit ASSIST. workers/workers/llm_provider.py:9-13 [DERIVED]
Only known consumer: `workers/workers/extract_worker.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Neighborhood` | class | (nid: str, chunks: list[tuple[str, str]]) -> `char_len` property | 55-62 | workers/workers/extract_worker.py (module-level import only) |
| `build_neighborhoods` | def | (child_chunks: list[dict], max_chars: int \| None = None) -> list[Neighborhood] | 73-136 | workers/workers/extract_worker.py |
| `contract_identity` | def | () -> dict | 144-208 | workers/workers/extract_worker.py |
| `select_lane` | def | (source_bytes: int, affinity: str \| None = None) -> lane | 216-222 | workers/workers/extract_worker.py |
| `make_client` | def | (lane: str, doc_id: str = "", ring_offset: int = 0) -> LLMExtractionClient | 225-243 | workers/workers/extract_worker.py |
| `batch_lane_indices` | def | (slice_idx: list[int], n_batches: int, doc_id: str) -> list[int] | 246-259 | workers/workers/extract_worker.py |
| `spread_decision` | def | (queue_depth: int \| None, doc_id: str, n_neighborhoods: int) -> bool | 262-271 | workers/workers/extract_worker.py |
| `run_proposals` | def | (neighborhoods, *, lane, source_bytes, doc_id="", assist=False, queue_depth=None, active_rank=None, active_docs=None, call_cache=None) -> tuple[list[LLMCallResult], NormalizedExtraction] | 295-759 | workers/workers/extract_worker.py |
| `to_precomputed_entities` | def | (merged, label_compositions, all_chunk_ids) -> PHASE B2 precomputed form | 874-897 | workers/workers/extract_worker.py |
| `to_evidence_spans` | def | (merged) -> spans | 900-910 | workers/workers/extract_worker.py |
| `ledger_items` | def | (merged) -> raw-ledger items | 913-933 | workers/workers/extract_worker.py |
| `call_receipts` | def | (results) -> per-call receipts | 936-952 | workers/workers/extract_worker.py |

Constants: `LLM_ENTITY_VERSION = "polymath-extraction-v1-entity"` (41), `LLM_EVIDENCE_VERSION = "polymath-extraction-v1-evidence"` (42), `LLM_RELATION_CLASS = "llm_relation"` (43), `LLM_MIN_CHUNK_WORDS = 15` (44), `NEIGHBORHOODS_PER_CALL = 4` (46), `_REISSUE_DISPOSITIONS = ["incomplete", "missing", "quarantined", "unaccounted"]` (762), `_STORE_ATTACHED = false` (846). FACTS.constants [DERIVED]

## contracts

**build_neighborhoods** (73-136)
- in: rows keyed `"char_start"`, `"chunk_id"`, `"text"`, `"parent_id"`, optional `"region_role"` (97, 102, 108).
- pre: `max_chars is None` -> `get_settings().worker.llm_max_neighborhood_chars` (92-93).
- post: rows sorted by `(char_start, chunk_id)` (97); `< 15` words skipped (98-99); durable `region_role` noise wins, heading-classifier noise is fallback (100-107); orphan parent id = `__orphan__{chunk_id}` (108); `k = max(1, -(-total // max_chars))` balanced buckets, `max_chars` hard cap, children never split (117-133); `nid = f"{pid}:{len(out)}"` (135). Stored parent summary is never sent (86-87).

**run_proposals** (295-759)
- in: `lane` is `"local"` or `"cloud"` (321, 333); `call_cache` is a `(get, put)` tuple or None (416-417).
- pre: local lane blocks on `/ready` up to `timeout_s = 180.0` (274, 327).
- post: limiter refusal fails the stage via `_raise_if_refused` — never completes with neighborhoods missing (651-655, 1101); every neighborhood gets exactly one disposition (666-667, 730-732); dispositions in `_REISSUE_DISPOSITIONS` are re-issued once, singly (667, 684-690, 814); parse failures surface as QUARANTINED call results (307-308).
- out: merged `NormalizedExtraction` whose `stats` carries `neighborhoods_sent/returned/reissued/dropped/...` and `calls*` counters (733-749).

**contract_identity** (144-208)
- out: dict hashing `CONTRACT_ID`, `cloud_min_bytes`, local/cloud models, cloud pool fingerprint, neighborhood params, prompt/ontology/type-fallback/chunk-kind hashes, `GENERATION_CONFIG`, limiter seeds, materialization (`"llm-direct-facts-v1"` iff `extraction_provider == "llm_live"` else `"compiler"`, 195-196), gate version + attestation policy, `region_role_sha256`, entity/evidence versions (181-208).
- post: a change to any hashed input must yield a NEW receipt so the document is re-extracted (145-148).

**select_lane** (216-222): returns `_policy_select_lane(source_bytes, s.worker.cloud_min_bytes, affinity=affinity)`; durable input is `documents.byte_length` (217, 220-222).

**make_client** (225-243): `"local"` -> settings `sidecars.llm_local_extract_url`/`llm_local_extract_model` (228-230); `"cloud"` -> deterministic doc→endpoint `select_cloud_endpoint(doc_id, ring_offset)` (232-235); sets `attempt_stage, attempt_function = "extract", "EXTRACT"` (241); other lane raises `ValueError(f"unknown lane: {lane!r}")` (243).

**batch_lane_indices** (246-259): batch i -> `slice_idx[(i + h) % n]`, `h = blake2b("slice-start:" + doc_id, digest_size=8) % n` (258-259); empty slice -> `[]` (256-257); replays pick the same lanes (250-251).

**spread_decision** (262-271): `True` iff `queue_depth is not None and queue_depth <= 1 and bool(doc_id) and n_neighborhoods > NEIGHBORHOODS_PER_CALL` (270-271); unknown depth (`None`) never spreads (268-269).

## effect surface
- Network (cloud): endpoints via `select_cloud_endpoint` / `select_cloud_endpoint_abs` / `cloud_ring` (234-235, 363-364, 378); live calls `client.extract(...)` (443). Network (local): `client.extract_batched` against `/infer_batch` (310, 328-330); readiness `GET {base_url}/ready`, `timeout=3` (282, 286).
- Postgres: `PostgresControllerStore` attached once per process by `_ensure_controller_store` (849-859; invoked at 317). No direct table reads/writes in this module — FACTS `tables_read`/`tables_written` are `[]`.
- External cache: `call_cache` (get, put); receipt keys `"ecr_" + hash[:40]`, put tried with 8/7/6/5 args (416-424, 460-469).
- Settings (env-backed; defaults not shown in material): `worker.llm_max_neighborhood_chars` (93), `worker.cloud_min_bytes` (183, 221, 330, 444), `worker.extraction_provider` (195), `sidecars.llm_local_extract_url`/`llm_local_extract_model` (229-230), `sidecars.llm_cloud_model` (175), plus `s.sidecars.llm_local_extract_url` at 327.
- Structured logs with `error_code`: `EXTRACTION_V2_DISPATCH` (641), `EXTRACTION_LANE_AUTH_DEAD` (491-492), `EXTRACTION_LANE_FAILOVER` (553, 621), `EXTRACTION_SEMANTIC_ESCAPE` (607-608), `EXTRACTION_V2_STATS` (648-649).

## invariants
INVARIANT: cloud batch size <= `NEIGHBORHOODS_PER_CALL` (4) — 46 vs 408, 418 [DERIVED]
  fails-if: dense batches overflow the OUTPUT budget (`finish_reason == "length"`) and force splits (555-561).
INVARIANT: `contract_identity["neighborhood"]["min_chunk_words"] == LLM_MIN_CHUNK_WORDS` (15) — 192 vs 44 [DERIVED]
  fails-if: contract hash drifts without behavior change (or vice versa) — stale receipts or spurious re-extraction (145-148).
INVARIANT: `spread_decision` True requires `n_neighborhoods > 4` — 271 [DERIVED]
  fails-if: single-batch docs spread and lose per-doc affinity.
INVARIANT: `k = max(1, ceil(total / max_chars))` buckets per parent, `k >= 1` — 117 [DERIVED]
  fails-if: zero buckets or last-bucket absorption (the pre-fix behavior, 123-126).
INVARIANT: `len(merged.dispositions) == len(neighborhoods)` — 730-732 [DERIVED]
  fails-if: census cannot refuse promotion on `dropped` (663-664).
INVARIANT: reissue set == `_REISSUE_DISPOSITIONS` (`incomplete/missing/quarantined/unaccounted`) — 667 vs 762 [DERIVED]
  fails-if: failed neighborhoods silently never re-issued.
INVARIANT: `pool_size = max(1, min(len(work), 4 * n_lanes, 24))` — bounds `1 <= pool_size <= 24` — 635 [DERIVED]
  fails-if: unbounded thread pools or serial dispatch.
INVARIANT: `h` depends only on `doc_id` -> replay picks the same batch lanes — 258, 250-251 [DERIVED]
  fails-if: ring-head hot-spotting returns (ledger 2026-09-24 note, 252).

## determinism & idempotency
determinism: NONDETERMINISTIC — `ThreadPoolExecutor` pools at 642 and 837 (FACTS.nondeterminism), live network calls (328, 443), `time.monotonic` readiness wait (283-284). Merged output order is rebuilt from `neighborhoods` order regardless (709-710).
idempotency: SAFE with `call_cache` — content-addressed `"ecr_"` keys (421-424) replay cached raws through the same sanitize path; retries "only pay for calls it never made" (348-351, 429-442). UNSAFE with `call_cache=None` — `cache_get`/`cache_put` disabled (416-417), so every retry re-buys live calls.

## failure behaviour
- `except Exception: pass` at 289 (SWALLOWED) — readiness poll errors in `_wait_local_ready` are ignored; on timeout returns `False` and the real call "fail[s] loudly as before" (278-279, 292).
- `except Exception: raw = None` at 432 (handled: assign) — a `cache_get` error degrades to a cache miss; the live `client.extract` at 443 runs and pays full price.
- `except Exception: break` at 468 (handled: break) — non-TypeError from `cache_put` in the 8/7/6/5-arity ladder silently drops the receipt.
- `except Exception: pass` at 582 (SWALLOWED) — if `r.packet.model_copy(update={"items": keep})` fails, the truncated call's partial items are lost from the split result (574-586).
- `except (NameError, UnboundLocalError)` at 672 and 681 — on the local lane, `_call`/`_dispatch` don't exist; reissue falls back to the plain call path (673, 680-683).
- Raised: `ValueError(f"unknown lane: {lane!r}")` (243); `ExtractionTransportError` re-raised when no cross-host lane exists (504, 520, 549); `_raise_if_refused` fails the stage on limiter refusal (655, 1101).
- Lane quarantine: 401/403 marks an endpoint dead for the run (`_dead`, 478, 485-504) and escapes cross-host.

## dumb-code flags
- `__import__("re")` used twice on one line instead of a top-level import — 48.
- getattr default disagreement: `request_char_budget` defaults to `60000` at 393 but `0` at 395.
- Settings-path suspicion: `s = get_settings().worker` at 316, then `s.sidecars.llm_local_extract_url` at 327 — but `make_client` reads `get_settings().sidecars` (227). If `Settings.worker` has no `sidecars`, line 327 raises AttributeError. [INFERRED] (settings schema not in material)
- Duplicated literal assignment `client.attempt_stage, client.attempt_function = "extract", "EXTRACT"` at 241 and 384.
- `from urllib.parse import urlparse` re-imported at 493, 511, 535, 596.
- Magic numbers: `60000` (393), `4 * n_lanes`, `24` (635), arity ladder `(8, 7, 6, 5)` (462), `180.0`/`3.0`/`3` (274, 286, 291), budget anchors `800` / `15_000` (189-190), key cut `[:40]` (424), log cuts `[:100]`/`[:120]` (490, 552).
- Module-level mutable `_STORE_ATTACHED = false` gating one-time store attach (846, 849-859).
- Lambda rebinding of `_reissue_call` at 683 shadows the earlier binding (671).

## refactor notes
- Only importer is `workers/workers/extract_worker.py` (FACTS.importers) — but the stage depends on `contract_identity()` output and on the disposition vocabulary (`returned`, `returned_empty`, `reissued_returned`, `incomplete_kept`, `dropped`, `unaccounted`, 696-706, 730-732); the coverage census "refuses promotion" on `dropped` (663-664). Renaming either breaks receipt hashing or coverage accounting.
- The bare local call (`doc_id == ""`) "keeps the frozen single-endpoint shape (and the test doubles that pin it)" — 322-324, 734; do not change `make_client`/`run_proposals` signatures without updating those tests.
- Gate, prompt, ontology, pool roster, chunk-kind rules, region-role fingerprint are contract inputs (181-208); any change re-extracts every document under contract drift (145-148, 197-201).
- Reissue pool sizing couples to `limiter.spec.conc_cap` / `limiter.spec.max` (687-689) — limiter schema changes ripple here.
- 401/403 quarantine, 413 ladder, multi-hop transport failover and semantic escape all walk `cloud_ring()` offsets (485-554, 588-614) — endpoint ring ordering changes alter failover behavior.

## VERIFY
```verify
grep -Fq 'NEIGHBORHOODS_PER_CALL = 4' workers/workers/llm_provider.py
grep -Fq 'LLM_MIN_CHUNK_WORDS = 15' workers/workers/llm_provider.py
grep -Fq 'unknown lane: {lane!r}' workers/workers/llm_provider.py
grep -Fq 'digest_size=8' workers/workers/llm_provider.py
grep -Fq 'max(1, min(len(work), 4 * n_lanes, 24))' workers/workers/llm_provider.py
grep -Fq 'queue_depth <= 1' workers/workers/llm_provider.py
grep -Fq 'EXTRACTION_LANE_AUTH_DEAD' workers/workers/llm_provider.py
test "$(grep -c -F 'ThreadPoolExecutor' workers/workers/llm_provider.py)" -ge 3
```
