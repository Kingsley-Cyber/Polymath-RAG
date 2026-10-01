# unit: sidecars/local_extractor/batched_server.py
anchor: sidecars/local_extractor/batched_server.py:1-418

## purpose
Flask server ("LOCAL-LLM-EXTRACTION-V1") wrapping mlx_lm `batch_generate` for the pinned model `mlx-community/Qwen3.5-4B-MLX-4bit` behind `POST /infer_batch`, plus an OpenAI-compatible `POST /v1/chat/completions` that micro-batches concurrent single requests into one decode — so the fleet's existing OpenAI-compatible client gets batch-40 throughput with no client change. batched_server.py:2-16, 311-315 [DERIVED]
Also serves `GET /v1/models` (health-probe compatibility) and `GET /ready` (memory/limits report). batched_server.py:14, 294-308 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| infer_batch | route POST /infer_batch | () -> Flask JSON | batched_server.py:259 | extraction callers (— in FACTS) |
| chat_completions | route POST /v1/chat/completions | () -> Flask JSON | batched_server.py:373 | fleet's OpenAI-compatible client (313-315) |
| models | route GET /v1/models | () -> Flask JSON | batched_server.py:289 | OpenAI-compatible health probe (14) |
| ready | route GET /ready | () -> Flask JSON | batched_server.py:295 | — |
| load_model | def | () -> None | batched_server.py:60 | `__main__` 416, `_generate` 213 |

All other defs (`_render_prompt`, `_clamp_tokens`, `_finalize`, `_common_token_prefix`, `_prefix_cache_for`, `_longest_stored_prefix`, `_generate`, `_split_messages`, `_error_body`, `_run_micro_batch`, `_queue_collector`) are module-private helpers. batched_server.py:112-411 [DERIVED]

## contracts
**infer_batch** — batched_server.py:259-285
- in: JSON body `{"prompts": [{"system","user","max_tokens"}, ...], "max_tokens": N}`; `prompts` must be 1..`MAX_BATCH` (40 default) dicts, else 400 `prompts must be 1..40 objects`. batched_server.py:262-264 [DERIVED]
- pre: budgets clamped per item via `_clamp_tokens(p.get("max_tokens", default_budget), default_budget)`, default `DEFAULT_MAX_TOKENS = 2500`. batched_server.py:265-267, 47 [DERIVED]
- out: `{"results": [{"content","stop_reason","completion_tokens","prompt_tokens"}], "wall_s", "batch"}`. batched_server.py:279-285 [DERIVED]
- post: any generation exception → HTTP 500 `{"error": "<Type>: msg", "type": "generation_failed"}`. batched_server.py:276-278 [DERIVED]

**chat_completions** — batched_server.py:373-402
- in: OpenAI `messages` list; `_split_messages` validates shape BEFORE enqueue → 400 `invalid_request` on bad shape. batched_server.py:375-378, 323-333 [DERIVED]
- post: item queued in `_MICRO_QUEUE`; batch fired immediately at `MICRO_BATCH_MAX = min(8, MAX_BATCH)`, else window flush after `MICRO_BATCH_WINDOW_S = 0.30`. batched_server.py:383-395, 319-320 [DERIVED]
- post: `gate.wait(timeout=GATE_WAIT_S)` with `GATE_WAIT_S = 1800.0`; timeout → 504 `{"error":{"message":"generation did not complete","type":"timeout"}}`. batched_server.py:396-400, 50 [DERIVED]
- post: every queued item is answered exactly once — `finally: it["gate"].set()` runs even when generation raises. batched_server.py:362-369 [DERIVED]

**_generate** — batched_server.py:211-255
- pre: decode runs under `_GEN_LOCK` (one decode on device at a time). batched_server.py:216, 56 [DERIVED]
- post: `len(texts) != len(token_lists)` → `RuntimeError`. batched_server.py:252-254 [DERIVED]
- post: each text cut to its own budget by `_finalize`; `finish_reason` is `"length"` when `len(ids) >= budget`, else `"stop"`; `completion_tokens` = real token count. batched_server.py:136-144, 255 [DERIVED]

**ready** — batched_server.py:295-308: returns `{"ready": true, "batched": true, "max_batch", "max_tokens", "memory": {active_gb, cache_gb, peak_gb}, "limits_gb"}`. [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| env | `POLYMATH_LLM_LOCAL_BATCH = '40'` | batched_server.py:45 |
| env | `POLYMATH_LLM_LOCAL_MAX_TOKENS = '4096'` | batched_server.py:46 |
| env | `POLYMATH_LLM_LOCAL_CACHE_GB = '1.0'` | batched_server.py:48 |
| env | `POLYMATH_LLM_LOCAL_MEMORY_GB = '12.0'` | batched_server.py:49 |
| env | `POLYMATH_PREFIX_CACHE = 'on'` | batched_server.py:165 |
| env | `POLYMATH_JSON_MASK = 'on'` | batched_server.py:89 |
| files | reads pinned snapshot `~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots/32f3e8ecf65426fc3306969496342d504bfa13f3` via `load()` | batched_server.py:40-43, 80 |
| module import | `from json_mask import make_json_mask` | batched_server.py:95 |
| network | Flask `app.run(host="127.0.0.1", port=port, threaded=True)`, port from `sys.argv[1]` default `8755` | batched_server.py:415, 418 |
| GPU/metal | `mx.set_cache_limit(CACHE_LIMIT_BYTES)`, `mx.set_memory_limit(MEMORY_LIMIT_BYTES)`, `mx.clear_cache()` after each batch | batched_server.py:75-77, 249 |
| stderr | status prints (mask on/off, prefix-cache failure, memory-limit unavailability) | batched_server.py:79, 92, 99-103, 233-234 |
| Postgres/Qdrant | none (FACTS `tables_read`/`tables_written` empty) | FACTS |

## invariants
INVARIANT: `len(prompts)` >= 1 and <= `MAX_BATCH` (40) — batched_server.py:262-264 [DERIVED]
  fails-if: request rejected with 400 before any GPU work.
INVARIANT: every per-item budget in [1, `SERVER_MAX_TOKENS` (4096)] — batched_server.py:133, 46 [DERIVED]
  fails-if: oversized `max_tokens` silently clamped, `finish_reason` flips to "length".
INVARIANT: exactly one decode on the device at a time (`_GEN_LOCK` around both `/infer_batch` and micro-batch paths) — batched_server.py:56, 216, 20-22 [DERIVED]
  fails-if: concurrent Metal decodes; measured OOM/swap per comment 68-74.
INVARIANT: `_common_token_prefix` result < min list length (every suffix keeps >= 1 token) — batched_server.py:173-175 [DERIVED]
  fails-if: an empty suffix prompt would be handed to `batch_generate`.
INVARIANT: prefix cache reused only when prefix length >= `_PREFIX_MIN_TOKENS` (64); cache store capped at `_PREFIX_CACHE_MAX` (4), oldest entry evicted — batched_server.py:223, 229, 163, 192-194 [DERIVED]
  fails-if: LRU thrash or near-full-prompt "prefixes" poison the cache.
INVARIANT: a single prompt (batch of 1) never BUILDS a prefix cache, only reuses one a real batch established — batched_server.py:221-231, 199-201 [DERIVED]
  fails-if: unique single-prompt content churns the 4-slot LRU.
INVARIANT: `len(texts) == len(token_lists)` after generation — batched_server.py:252-254 [DERIVED]
  fails-if: RuntimeError → caller gets typed 500.
INVARIANT: every queued micro item's `gate` is set exactly once (in `finally`) — batched_server.py:367-369 [DERIVED]
  fails-if: request hangs until the 1800.0 s gate timeout → 504.
INVARIANT: `MICRO_BATCH_MAX = min(8, MAX_BATCH)` = 8 with default env — batched_server.py:320, 45 [DERIVED]
INVARIANT: `DEFAULT_MAX_TOKENS` (2500) <= `SERVER_MAX_TOKENS` (4096) — batched_server.py:46-47 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` at batched_server.py:268, 283 feeding `wall_s`; concurrency `threading.Thread` at 387, 395, 417 plus `threading.Event` gates; comment 156-160 notes greedy outputs already differ across batch compositions) [DERIVED]
idempotency: SAFE (no external writes; retries only mutate in-process `_PREFIX_CACHES` at 194 and `_MICRO_QUEUE` at 384) [INFERRED — no DB/file writes exist in SOURCE]

## failure behaviour
| where | type | behaviour | caller sees |
|---|---|---|---|
| batched_server.py:75-79 | Exception | SWALLOWED: print `mlx memory limits unavailable` (fail-open) | no limits; OOM risk described in comment 68-74 |
| batched_server.py:94-103 | Exception | SWALLOWED: print `json grammar mask failed to load ... (fail-open)` | generation without mask (37% salvage-repair baseline, comment 86-87) |
| batched_server.py:232-235 | Exception | handled: print `prefix cache failed (full prefill)` | slower but correct decode |
| batched_server.py:249-251 | Exception | SWALLOWED: pass (`clear_cache`) | buffers not returned to OS |
| batched_server.py:276-278 | Exception | SWALLOWED: return 500 JSON | `{"error","type":"generation_failed"}` |
| batched_server.py:297-304 | Exception | SWALLOWED: pass | `/ready` returns `"memory": {}` |
| batched_server.py:362-366 | Exception | handled: unanswered items get `_error_body`, status 500 | every queued request still answered once |
Error codes: 400 (264, 378), 500 (277-278, 366), 504 (396-400). [DERIVED]

## dumb-code flags
- `import os as _os` at line 88 duplicates top-level `import os` at line 35. batched_server.py:88, 35 [DERIVED]
- Magic 2048 chunk in prefix prefill loop, unexplained. batched_server.py:189-190 [DERIVED]
- Magic 8 in `MICRO_BATCH_MAX = min(8, MAX_BATCH)`. batched_server.py:320 [DERIVED]
- Two redundant drain mechanisms: per-request `_flush` thread AND `_queue_collector` loop; comment admits the flush "also covers an app imported without the collector thread". batched_server.py:392-395, 405-411, 389-391 [DERIVED]
- Naming split: `/infer_batch` returns member `stop_reason` (renamed from `_finalize`'s `finish_reason`) while `/v1` returns `finish_reason` — same concept, two literal names. batched_server.py:279, 356, 136-144 [DERIVED]
- Compatibility dead branch: `batch_generate is None` → per-prompt `generate` loop for older mlx_lm. batched_server.py:244-247, 105-109 [DERIVED]
- `POLYMATH_JSON_MASK` defaults on but comment 90-92 says it was DISABLED for quadratic per-step cost "pending incremental-state fix" — default disagrees with the recorded perf decision. batched_server.py:89-92 [INFERRED — env default "on" vs comment describing disable-for-perf]

## refactor notes
- Response shapes are the client contract: `results[].stop_reason/completion_tokens/prompt_tokens`, `wall_s`, `batch` (9-12, 279-285) and OpenAI `choices[].finish_reason` + `usage` (353-360) — renaming any member breaks callers. [DERIVED]
- Generation config is LOCKED to match `config/extraction_models/qwen35-4b-extraction-v1.yaml` (plan decision 18): `repetition_penalty=1.15, repetition_context_size=400`, `enable_thinking=False` — duplicated here, must stay in sync. batched_server.py:15-18, 81-82, 117-119 [DERIVED]
- `PIN_SNAPSHOT`/`MODEL_ID`/`MODEL_PATH` pin the HF cache dir; changing them requires that snapshot dir to exist on disk. batched_server.py:40-44, 80 [DERIVED]
- `_GEN_LOCK` single-decode guarantee and the `finally`-set gates (exactly-once answering) must survive any refactor; removing the `finally` strands requests for 1800 s. batched_server.py:56, 216, 367-369 [DERIVED]
- Env flag names/values are operator contract (`POLYMATH_LLM_LOCAL_*`, `POLYMATH_PREFIX_CACHE`, `POLYMATH_JSON_MASK`). batched_server.py:45-49, 89, 165 [DERIVED]

## VERIFY
```verify
grep -Fq 'MODEL_ID = "mlx-community/Qwen3.5-4B-MLX-4bit"' sidecars/local_extractor/batched_server.py
grep -Fq 'DEFAULT_MAX_TOKENS = 2500' sidecars/local_extractor/batched_server.py
grep -Fq 'GATE_WAIT_S = 1800.0' sidecars/local_extractor/batched_server.py
grep -Fq 'repetition_penalty=1.15, repetition_context_size=400' sidecars/local_extractor/batched_server.py
grep -Fq 'MICRO_BATCH_WINDOW_S = 0.30' sidecars/local_extractor/batched_server.py
grep -Fq 'status=504, mimetype="application/json"' sidecars/local_extractor/batched_server.py
test "$(grep -c -F 'threading.Thread' sidecars/local_extractor/batched_server.py)" -ge 3
```
