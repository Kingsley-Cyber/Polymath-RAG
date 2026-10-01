# unit: sidecars/embedder/server.py
anchor: sidecars/embedder/server.py:1-272

## purpose
FastAPI embedder sidecar (ADR-0005, G2): one resident `SentenceTransformer` per process, host-native, serving dense vectors under the frozen neural embedding contract. The contract id is baked into every response, so an index written with this sidecar can only be replayed by the identical contract. `/ready` performs a real forward pass on every probe. — sidecars/embedder/server.py:1-11 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `infer` | route POST `/infer` | (`EmbedRequest`, `x_polymath_priority: str \| None` header) -> `EmbedResponse` | sidecars/embedder/server.py:236-271 | HTTP clients — |
| `ready` | route GET `/ready` | (`response: Response`) -> dict (503 when unusable) | sidecars/embedder/server.py:152-179 | HTTP clients — |
| `health` | route GET `/health` | () -> `{"status": "ok"}` | sidecars/embedder/server.py:147-148 | HTTP clients — |
| `manifest` | route GET `/manifest` | () -> dict (manifest + `contract_id` + `weights_verification`) | sidecars/embedder/server.py:139-143 | HTTP clients — |
| `EmbedRequest` | pydantic model | `texts: list[str]` (1..32), `representation_kind: str = "child_chunk"` | sidecars/embedder/server.py:37-39 | /infer body — |
| `EmbedResponse` | pydantic model | `vectors`, `contract_id`, `dimension`, `model_release`, `queued_ms: float = 0.0`, `priority: str = "background"` | sidecars/embedder/server.py:42-50 | /infer reply — |

No in-repo importers in FACTS; consumption is over HTTP.

## contracts

**POST `/infer`**
- in: body `EmbedRequest`; optional header `X-Polymath-Priority` (alias `PRIORITY_HEADER`) — sidecars/embedder/server.py:236-237 [DERIVED]
- pre: `app.state.weights.verified` must be truthy, else `HTTPException(status_code=503, detail="weights verification failed")` — sidecars/embedder/server.py:239-240 [DERIVED]
- in: `contract.query_prefix + text` applied iff `request.representation_kind == "query"`, else text unchanged — sidecars/embedder/server.py:242-245 [DERIVED]
- out: vectors in exact input order (`vectors[slot] = vec` per batch index); `contract_id = NEURAL_EMBED_CONTRACT.contract_id`; `dimension = contract.dimension`; `model_release = app.state.manifest["identity"]["version"]`; `queued_ms = round(sum(r.waited_ms for r in receipts), 1)`; `priority = request_priority(header)` — sidecars/embedder/server.py:258, 264-270 [DERIVED]
- post: Metal released after every request via `_release_mps()` in a `finally` — sidecars/embedder/server.py:260-261, 230-232 [DERIVED]

**GET `/ready`**
- 503 + `{"ready": False, "reason": "model not loaded"}` when `app.state.model` is None — sidecars/embedder/server.py:161-164 [DERIVED]
- 503 + `{"ready": False, "reason": f"weights unverified: {app.state.weights}"}` when weights unverified — sidecars/embedder/server.py:165-167 [DERIVED]
- probe: `model.encode(["readiness probe"], normalize_embeddings=True)` inside `device_lease("background", timeout_s=PROBE_LEASE_TIMEOUT_S, what="probe")` — sidecars/embedder/server.py:168-172 [DERIVED]
- 200 `{"ready": True}` only after the probe passes — sidecars/embedder/server.py:179 [DERIVED]

**`verify_weights(cache_dir, declared_sha) -> dict`** — sidecars/embedder/server.py:94-108 [DERIVED]
- `declared_pinned = not declared_sha.startswith("__PIN_")`; `require_pinned = os.environ.get("POLYMATH_REQUIRE_PINNED", "0") == "1"` — 95-96
- cache missing -> `{"verified": False, "mode": "missing_cache"}` — 97-98
- pinned -> `{"verified": digest == declared_sha, "mode": "declared", "digest": digest[:16]}` — 99-101
- unpinned + require_pinned -> `{"verified": False, "mode": "unpinned_refused"}` — 102-103
- unpinned + existing `weights.digest` -> tofu compare; absent -> record digest, `{"verified": True, "mode": "tofu_recorded"}` — 104-108

## effect surface
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty).
- Qdrant collections: none visible.
- Files: reads `manifest.toml` beside the module — sidecars/embedder/server.py:30, 81 [DERIVED]; reads/writes `weights.digest` beside the module (TOFU state) — sidecars/embedder/server.py:31, 104-107 [DERIVED]; reads/hashes model cache `~/.cache/polymath/embedder`, `mkdir(parents=True, exist_ok=True)` — sidecars/embedder/server.py:32, 85-91, 120 [DERIVED].
- Network: `SentenceTransformer(model_cfg["id"], revision=model_cfg["revision"], cache_folder=...)` may fetch from the model hub on cache miss — sidecars/embedder/server.py:118-126 [INFERRED: standard SentenceTransformer behavior on cold cache].
- Subprocesses: none visible.
- Cross-process device coordination via `polymath_shared.metal` lease (`device_lease`, `leased_run_adaptive`, `priority_scope`) — sidecars/embedder/server.py:26-27, 171, 223 [DERIVED].
- Env flags read:
  - `POLYMATH_EMBEDDER_DEVICE` = `manifest.get('runtime', {}).get('device', 'cpu')` — sidecars/embedder/server.py:116
  - `POLYMATH_REQUIRE_PINNED` = `'0'` — sidecars/embedder/server.py:95
  - `POLYMATH_MAX_BATCH_TEXTS` = `'8'` — sidecars/embedder/server.py:195
  - `POLYMATH_MAX_BATCH_TOKENS` = `'16384'` — sidecars/embedder/server.py:196
  - `POLYMATH_SIDECAR_THREADED` = `'0'` — sidecars/embedder/server.py:69

## invariants
INVARIANT: `len(texts)` ≤ 32 per request (`Field(min_length=1, max_length=32)`) — sidecars/embedder/server.py:38 [DERIVED]
  fails-if: request rejected at validation; caller gets a 422 before reaching the lease.
INVARIANT: texts per device batch ≤ `POLYMATH_MAX_BATCH_TEXTS` (default `8`) AND approx tokens per batch ≤ `POLYMATH_MAX_BATCH_TOKENS` (default `16384`), where `approx = max(1, len(text) // 4)` — sidecars/embedder/server.py:195-203 [DERIVED]
  fails-if: oversized batches reintroduce the quadratic-attention memory blowup the bound exists to prevent (188-189).
INVARIANT: batch groups are contiguous index ranges concatenated in input order, so results equal a single unbatched call — sidecars/embedder/server.py:190-193, 200-210 [DERIVED]
  fails-if: vectors permuted relative to inputs; callers match vectors to texts by position.
INVARIANT: every slot of `vectors = [None] * len(prefixed)` is filled exactly once (`vectors[slot] = vec` for each `slot` in each group) — sidecars/embedder/server.py:249, 258 [DERIVED]
  fails-if: a `None` reaches `v.tolist()` at line 265 and raises `AttributeError` — sidecars/embedder/server.py:265 [INFERRED: `.tolist()` undefined on None].
INVARIANT: response `contract_id` == `NEURAL_EMBED_CONTRACT.contract_id` on both `/manifest` and `/infer` — sidecars/embedder/server.py:141, 241, 266 [DERIVED]
  fails-if: indexes built by a mismatched contract become unreplayable (4-6).
INVARIANT: absent/unknown priority header -> `"background"` (`normalize_priority(header_value)`) — sidecars/embedder/server.py:58-61 [DERIVED]
  fails-if: unheadered callers silently change lease class and preempt/queue differently.
INVARIANT: `_snapshot_digest` excludes any file with `"blobs"` or `"refs"` in `path.parts` — sidecars/embedder/server.py:87-88 [DERIVED]
  fails-if: digest churns on mutable hub-internal files, breaking tofu/declared comparison.
INVARIANT: probe lease wait ≤ `PROBE_LEASE_TIMEOUT_S = 5.0` — sidecars/embedder/server.py:55, 171 [DERIVED]
  fails-if: readiness probe queues behind fleet work instead of failing fast.

## determinism & idempotency
determinism: NONDETERMINISTIC — `queued_ms` measures real lease wait time (269); device selected by env/manifest (116); TOFU first run writes `weights.digest` (107); threaded mode changes execution concurrency (64-69). Vector contents are order-stable per the batching contract (190-193) given fixed weights/device. — sidecars/embedder/server.py:64-69, 107, 116, 269 [DERIVED]
idempotency: SAFE — `/infer` writes no persistent state; per-request side effect is only Metal release (`_release_mps()`). The filesystem write (`weights.digest`) happens once in lifespan, not on the request path. — sidecars/embedder/server.py:230-232, 260-261, 104-107 [DERIVED]

## failure behaviour
- `ready`: broad `except Exception` around the probe — swallowed, caller sees 503 `{"ready": False, "reason": f"forward pass failed: {exc}"}` — sidecars/embedder/server.py:174-178 [DERIVED]
- `lifespan`: failed weights verification is `log.error`-ed but startup continues; enforcement deferred to `/ready` 503 and `/infer` 503 — sidecars/embedder/server.py:129-131 [DERIVED]
- `infer`: raises `HTTPException(status_code=503, detail="weights verification failed")` when weights unverified — sidecars/embedder/server.py:238-240 [DERIVED]
- `verify_weights`: never raises for the visible modes; returns `verified: False` dicts (`missing_cache`, `declared` mismatch, `unpinned_refused`, `tofu` mismatch) — sidecars/embedder/server.py:94-108 [DERIVED]
- Metal OOM: `_encode_adaptive` delegates halving-on-exhaustion to `leased_run_adaptive` in `polymath_shared.metal` — sidecars/embedder/server.py:213-227 [DERIVED]

## dumb-code flags
- `CONTRACTS` imported but never referenced in the file — sidecars/embedder/server.py:24 [DERIVED: appears only on the import line]
- Duplicated default `"background"` across four sites: `EmbedResponse.priority` (49), `_encode_adaptive` param (213), probe `device_lease("background", ...)` (171), docstring contract (59).
- Magic numbers: token proxy `len(text) // 4` (202); digest truncation `digest[:16]` repeated 4× (101, 103, 105, 107); `PROBE_LEASE_TIMEOUT_S = 5.0` (55).
- Local `manifest = dict(app.state.manifest)` inside handler `manifest` shadows the function's own name — sidecars/embedder/server.py:139-140 [DERIVED].
- `EmbedResponse` defaults `queued_ms: float = 0.0` and `priority: str = "background"` are dead at the only construction site, which passes both explicitly — sidecars/embedder/server.py:49-50, 264-271 [DERIVED].
- Request cap 32 texts vs batch cap 8 texts: two independent bounds on the same quantity, one in the schema, one in env — sidecars/embedder/server.py:38, 195 [DERIVED].

## refactor notes
- Changing `NEURAL_EMBED_CONTRACT` (id, dimension, query prefix) invalidates every index written by this sidecar: the contract id is baked into responses precisely to make cross-contract replay impossible — sidecars/embedder/server.py:4-6, 141, 241-245, 266 [DERIVED].
- Do not fork the OOM-halving/batching logic out of `polymath_shared.metal.leased_run_adaptive`; the docstring records the same OOM defect was fixed twice before it was shared — sidecars/embedder/server.py:216-219 [DERIVED].
- `PRIORITY_HEADER` alias and `normalize_priority` come from `polymath_shared.metal`; renaming the header breaks every caller's lease class and they silently fall to `background` — sidecars/embedder/server.py:27, 58-61, 236-237 [DERIVED].
- `weights.digest` and `manifest.toml` are located by `Path(__file__).with_name` — moving this file relocates TOFU state and manifest resolution — sidecars/embedder/server.py:30-31 [DERIVED].
- `POLYMATH_SIDECAR_THREADED` flips the concurrency model (event-loop serial FIFO vs threadpool with mid-batch priority registration); behavior and lease ordering assumptions change with it — sidecars/embedder/server.py:64-77, 251-255 [DERIVED].
- `EmbedRequest.texts` max 32 and `POLYMATH_MAX_BATCH_TEXTS` default 8 jointly bound device memory; change them together — sidecars/embedder/server.py:38, 195 [DERIVED].

## VERIFY
```verify
grep -Fq 'PROBE_LEASE_TIMEOUT_S = 5.0' sidecars/embedder/server.py
grep -Fq 'texts: list[str] = Field(min_length=1, max_length=32)' sidecars/embedder/server.py
grep -Fq 'POLYMATH_MAX_BATCH_TOKENS", "16384' sidecars/embedder/server.py
grep -Fq 'weights verification failed' sidecars/embedder/server.py
grep -Fq 'normalize_embeddings=True' sidecars/embedder/server.py
test "$(grep -c -F 'digest[:16]' sidecars/embedder/server.py)" -ge 4
! grep -Fq 'import psycopg' sidecars/embedder/server.py
```
