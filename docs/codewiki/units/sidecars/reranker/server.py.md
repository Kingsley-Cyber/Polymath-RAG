# unit: sidecars/reranker/server.py
anchor: sidecars/reranker/server.py:1-403

## purpose
Reranker sidecar (ADR-0005, G3), role `sidecar-gpu`: one resident cross-encoder producing cross-representation relevance scores for (query, candidate) pairs over FUSED retrieval candidates — sidecars/reranker/server.py:1-13. It never invents candidates, never fuses, never applies calibrated weights; the caller keeps rank-based fusion and applies the scores ordinally — sidecars/reranker/server.py:3-7. Pinned model: `Qwen3-Reranker-0.6B @ e61197ed45024b0ed8a2d74b80b4d909f1255473`; `/ready` does a real forward pass on every probe and weights are verified trust-on-first-use — sidecars/reranker/server.py:9-12.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `RerankRequest` | class | `query: str, documents: list[str] (1..64), top_k: int \| None` | sidecars/reranker/server.py:41-44 | — |
| `RerankResponse` | class | `scores, order, model_id, model_revision, queued_ms, priority, dtype, max_length, batch, memo_hits, memo_misses, nonfinite, dtype_fallback` | sidecars/reranker/server.py:47-63 | — |
| `health` | route GET /health | `() -> dict` (`{"status": "ok"}`) | sidecars/reranker/server.py:263-264 | — |
| `ready` | route GET /ready | `() -> dict` | sidecars/reranker/server.py:268-289 | — |
| `rerank` | route POST /rerank | `(req: RerankRequest, x_polymath_priority: str \| None) -> RerankResponse` | sidecars/reranker/server.py:345-403 | — |
| `score_in_batches` | def | `(predict, pairs: list, batch: int = RERANK_BATCH, priority: str = "background", receipts: list[LeaseReceipt] \| None) -> list[float]` | sidecars/reranker/server.py:310-341 | `rerank` — sidecars/reranker/server.py:370 |
| `verify_weights` | def | `(cache_dir: Path, declared_sha: str) -> dict` | sidecars/reranker/server.py:180-194 | `lifespan` — sidecars/reranker/server.py:253 |
| `sanitize_scores` | def | `(scores: list[float]) -> tuple[list[float], int]` | sidecars/reranker/server.py:137-141 | `rerank` — sidecars/reranker/server.py:378 |

No importers listed in FACTS; this unit imports `polymath_shared.logging` and `polymath_shared.metal` (`PRIORITY_HEADER`, `LeaseReceipt`, `device_lease`, `normalize_priority`, `priority_scope`) — sidecars/reranker/server.py:31-32.

## contracts

**POST /rerank** (sidecars/reranker/server.py:345-403)
- in: `RerankRequest.query: str`; `documents` bounded `min_length=1, max_length=64` (line 43); optional `top_k`; header `X-Polymath-Priority` (alias from `PRIORITY_HEADER`), absent/unknown → `"background"` — sidecars/reranker/server.py:346, 144-147.
- out: `scores` with `len(scores) == len(req.documents)` (built as `[0.0] * len(pairs)` then filled from memo + fresh) — sidecars/reranker/server.py:385-389; `order` = indices sorted by score descending, truncated to `top_k` when provided — sidecars/reranker/server.py:390-392; `queued_ms = round(sum(r.waited_ms for r in receipts), 1)` — sidecars/reranker/server.py:398; per-request receipts `dtype, max_length, batch, memo_hits, memo_misses, nonfinite, dtype_fallback` — sidecars/reranker/server.py:400-402.
- pre: `app.state.model` set by `lifespan` — sidecars/reranker/server.py:248, 348.
- post: finite fresh scores stored in the memo; `_STATS` (`requests, pairs, memo_hits, memo_misses, nonfinite`) updated — sidecars/reranker/server.py:381-384.
- error: any scoring exception → HTTP 503, `detail={"error_code": "rerank_failed", "reason": <exception type name>, "pairs": len(pairs)}` — sidecars/reranker/server.py:374-377.

**GET /ready** (sidecars/reranker/server.py:268-289)
- out: `ready` from a real `model.predict([["probe", "probe"]])` under a `device_lease("background", timeout_s=PROBE_LEASE_TIMEOUT_S, what="probe")` — sidecars/reranker/server.py:273-275; payload includes `model_id, model_revision, device, dtype, max_length, batch, memo_max, dtype_fallback, stats` (with `memo_size=len(_MEMO)`) — sidecars/reranker/server.py:279-286.
- error: exception → `{"ready": False, "reason": type(exc).__name__}` — sidecars/reranker/server.py:288-289.

**GET /health** (sidecars/reranker/server.py:263-264): always `{"status": "ok"}`.

**`score_in_batches`** (sidecars/reranker/server.py:310-341)
- in: `predict` callable, `pairs` list, `batch` (default `RERANK_BATCH`), `priority` (default `"background"`), optional `receipts` sink.
- post: result order and length equal input; pure over `predict`; every device batch runs under `device_lease(priority, what="rerank")` with the receipt appended; accelerator cache released between batches; OOM → `_release_accelerator_cache()` then `cur = max(1, cur // 2)` retry, re-raise once `cur == 1` — sidecars/reranker/server.py:316-340.

**`verify_weights`** (sidecars/reranker/server.py:180-194)
- in: `cache_dir`, `declared_sha`; unpinned iff `declared_sha.startswith("__PIN_")` (line 182).
- out modes: `"missing_cache"` (no dir), `"declared"` (digest == pinned sha), `"unpinned_refused"` when `POLYMATH_REQUIRE_PINNED == "1"` and sha unpinned (lines 181, 188-189), `"tofu"` (digest == recorded `weights.digest`), `"tofu_recorded"` (first run writes digest) — lines 185-194.
- post: verification failure only `log.error`'d in `lifespan`, server still starts — sidecars/reranker/server.py:254-255.

**`sanitize_scores`** (sidecars/reranker/server.py:137-141): non-finite replaced by `floor = (min(finite) - 1.0)` or `-1.0e4` when no finite score; returns `(scores, nonfinite_count)`.

## effect surface

| kind | item | anchor |
|---|---|---|
| env | `POLYMATH_RERANKER_DTYPE` = `'fp16'` | sidecars/reranker/server.py:77 |
| env | `POLYMATH_RERANK_MAX_LENGTH` = `'384'` (floor `max(32, ...)`) | sidecars/reranker/server.py:80 |
| env | `POLYMATH_RERANK_MEMO_MAX` = `'20000'` (0 = off) | sidecars/reranker/server.py:81 |
| env | `POLYMATH_RERANK_BATCH` = `'64'` | sidecars/reranker/server.py:293 |
| env | `POLYMATH_SIDECAR_THREADED` = `'0'` | sidecars/reranker/server.py:155 |
| env | `POLYMATH_REQUIRE_PINNED` = `'0'` | sidecars/reranker/server.py:181 |
| env | `POLYMATH_RERANKER_DEVICE` = `manifest runtime.device` else `'cpu'` | sidecars/reranker/server.py:202-203 |
| file read | `manifest.toml` (via `tomllib`) | sidecars/reranker/server.py:34, 166-168 |
| file read/write | `weights.digest` (TOFU state, next to server.py) | sidecars/reranker/server.py:35, 190-193 |
| file read/write | `~/.cache/polymath/reranker` (model cache; snapshot digest over all files except `blobs`/`refs` parts) | sidecars/reranker/server.py:36, 171-177, 217 |
| network | `CrossEncoder(model_cfg["id"], revision=..., cache_folder=MODEL_CACHE_DIR, max_length=RERANK_MAX_LENGTH, ...)` — remote fetch on cache miss [INFERRED: HF-style loader given id+revision+cache_folder] | sidecars/reranker/server.py:221-222 |
| in-proc state | `_MEMO: OrderedDict` + `_MEMO_LOCK`, `_STATS` dict | sidecars/reranker/server.py:85-88 |

No DB tables or Qdrant collections appear in FACTS (`tables_read`/`tables_written` empty).

## invariants
INVARIANT: `max_length=64` on `documents` equals default `RERANK_BATCH` "64" — one forward pass per request at the wire cap — sidecars/reranker/server.py:43, 292-293 [DERIVED]
  fails-if: batch default raised above 64 is dead headroom; lowered below 64 splits one request into multiple device-batch leases.
INVARIANT: `len(scores) == len(req.documents)` and pre-truncation `len(order) == len(scores)` — sidecars/reranker/server.py:385-390 [DERIVED]
  fails-if: `order` indexes out of range at the caller.
INVARIANT: `RERANK_MAX_LENGTH == max(32, int(env))` — floor 32 — sidecars/reranker/server.py:80 [DERIVED]
  fails-if: env below 32 silently clamps; callers receipting `max_length` see 32, not their value.
INVARIANT: memo scope = `f"{revision}|{dtype}|{RERANK_MAX_LENGTH}"` hashed with `\x1e`/`\x1f` separators; scope change → miss — sidecars/reranker/server.py:107-109, 352 [DERIVED]
  fails-if: dropping a scope part serves stale scores across a dtype or revision change.
INVARIANT: `len(_MEMO) <= RERANK_MEMO_MAX` — `popitem(last=False)` LRU eviction — sidecars/reranker/server.py:133-134 [DERIVED]
  fails-if: unbounded memory growth on repeated carry reranks.
INVARIANT: memo stores only finite scores (`math.isfinite(sc)`) — sidecars/reranker/server.py:129-130 [DERIVED]
  fails-if: a `-1.0e4`/overflow floor gets cached and permanently ranks that pair last.
INVARIANT: non-finite request-time score ranks last, `floor = min(finite) - 1.0`, counted in `nonfinite` — sidecars/reranker/server.py:137-141 [DERIVED]
  fails-if: fp16 overflow either crashes (500) or silently wins rank.
INVARIANT: reduced precision only when `device == "mps"` — `dtype = RERANK_DTYPE if (device == "mps" or RERANK_DTYPE == "fp32") else "fp32"` — sidecars/reranker/server.py:229 [DERIVED]
  fails-if: fp16 on cpu/other device routes through the self-test fallback on every start.
INVARIANT: probe lease wait bounded by `PROBE_LEASE_TIMEOUT_S = 5.0` — sidecars/reranker/server.py:67, 274 [DERIVED]
  fails-if: readiness probe blocks indefinitely behind a busy device.

## determinism & idempotency
determinism: NONDETERMINISTIC (env knobs lines 77-81, 155, 181, 202, 293; MPS availability check 204-212; cross-request `_MEMO`/`_STATS` under `_MEMO_LOCK` 85-88, 382-384; `queued_ms` is wall-clock lease wait 398). Individual score values are pure over `predict` for fixed (revision, dtype, max_length) — sidecars/reranker/server.py:316-318 [DERIVED]
idempotency: SAFE — `/rerank` is read-only scoring, order/length equal input (sidecars/reranker/server.py:316-318); side effects are `_MEMO`/`_STATS` updates (381-384) and the one-time TOFU write of `weights.digest` on first run (193).

## failure behaviour

| site | type | behaviour | anchor |
|---|---|---|---|
| `_inference_scope` | Exception | SWALLOWED: `return contextlib.nullcontext()` — no-torch CI path | sidecars/reranker/server.py:97 |
| `/ready` probe | Exception | SWALLOWED: `{"ready": False, "reason": type(exc).__name__}` — probe reports not-ready, no 500 | sidecars/reranker/server.py:288 |
| `_release_accelerator_cache` | Exception | SWALLOWED: `pass` — cache release is best effort | sidecars/reranker/server.py:301 |
| `rerank` scoring | Exception | handled: log, raise — HTTP 503 `error_code "rerank_failed"`, never a bare 500 | sidecars/reranker/server.py:374-377 |
| MPS availability | Exception | handled: assign — `device = "cpu"` explicit fallback | sidecars/reranker/server.py:204-212 |
| dtype self-test | Exception | handled: log, assign — reload at `fp32`, `dtype_fallback = f"{dtype}->fp32"` | sidecars/reranker/server.py:237-246 |
| batch OOM | Exception | handled: if `_is_oom(exc)` and `cur > 1` → halve batch and retry, else raise | sidecars/reranker/server.py:332-338 |
| weights verify fail | — | `log.error` only; startup continues | sidecars/reranker/server.py:254-255 |

## dumb-code flags
- Duplicate `import hashlib` at lines 17 and 19 — sidecars/reranker/server.py:17,19.
- `RERANK_BATCH` defined at line 293, *after* `lifespan` (198-256) and `app = FastAPI(...)` (259), but referenced inside `lifespan` (247) and as a default arg (310) — works only because lifespan runs post-import — sidecars/reranker/server.py:247, 293, 310.
- Magic error strings in `_is_oom`: `"out of memory"`, `"mps backend"`, `"memory"`, with `or`/`and` precedence carrying the logic — sidecars/reranker/server.py:305-307.
- Magic numbers in `sanitize_scores`: `-1.0e4` empty-finite floor and `min(finite) - 1.0` — sidecars/reranker/server.py:140.
- Magic prefix `"__PIN_"` marks a sha unpinned — sidecars/reranker/server.py:182.
- `except TypeError` shim inside `_predict` exists only for `predict()` signatures without batch kwargs (test doubles) — a CI-compat branch on the production path — sidecars/reranker/server.py:360-362.
- `RerankResponse.priority` hardcodes default `"background"` while `request_priority` derives it via `normalize_priority` — duplicated source of truth — sidecars/reranker/server.py:55, 144-147.

## refactor notes
- Wire contract: `RerankRequest`/`RerankResponse` field names, the 503 detail shape (`error_code`, `reason`, `pairs`), and the JUDGE-FAST-PATH-V1 receipt fields are consumed by the FUSED-retrieval caller — rename = client break — sidecars/reranker/server.py:47-63, 374-377, 393-403.
- `X-Polymath-Priority` header name is owned by `polymath_shared.metal.PRIORITY_HEADER`; renaming it there changes this endpoint's wire alias — sidecars/reranker/server.py:32, 346.
- `memo_key` scope must keep all three parts (revision, dtype, max_length); separator changes only cause misses, but dropping a part serves cross-dtype stale scores — sidecars/reranker/server.py:107-109, 352.
- `score_in_batches` appends `LeaseReceipt`s whose `waited_ms` is summed into `queued_ms` — signature or ordering changes alter the receipt — sidecars/reranker/server.py:326-328, 398.
- The no-torch CI path (`_inference_scope` nullcontext, `_predict` TypeError fallback) exists so the endpoint runs with a fake model — removing it breaks CI doubles — sidecars/reranker/server.py:91-98, 357-362.
- `MANIFEST_PATH`/`DIGEST_STATE_PATH` are `Path(__file__).with_name(...)` — relocating server.py orphans the manifest and TOFU state — sidecars/reranker/server.py:34-35.
- Moving `score_in_batches` (or any import-time reader of `RERANK_BATCH`) above line 293 raises `NameError` at import — sidecars/reranker/server.py:293, 310.

## VERIFY
```verify
grep -Fq 'Qwen3-Reranker-0.6B @ e61197ed45024b0ed8a2d74b80b4d909f1255473' sidecars/reranker/server.py
grep -Fq 'documents: list[str] = Field(min_length=1, max_length=64)' sidecars/reranker/server.py
grep -Fq 'PROBE_LEASE_TIMEOUT_S = 5.0' sidecars/reranker/server.py
grep -Fq 'raise HTTPException(status_code=503, detail={"error_code": "rerank_failed",' sidecars/reranker/server.py
grep -Fq 'RERANK_BATCH = max(1, int(os.environ.get("POLYMATH_RERANK_BATCH", "64")))' sidecars/reranker/server.py
test "$(grep -c -F 'import hashlib' sidecars/reranker/server.py)" -ge 2
grep -Fq 'return {"verified": True, "mode": "tofu_recorded", "digest": digest[:16]}' sidecars/reranker/server.py
```
