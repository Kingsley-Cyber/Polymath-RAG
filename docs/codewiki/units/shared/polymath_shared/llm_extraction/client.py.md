# unit: shared/polymath_shared/llm_extraction/client.py
anchor: shared/polymath_shared/llm_extraction/client.py:1-1154

## purpose
Direct OpenAI-compatible HTTP transport for contract `polymath-extraction-v1`, bypassing an Instructor dependency by design — the contract, gate, and admission pipeline are the real seams; this file is swappable. [DERIVED] shared/polymath_shared/llm_extraction/client.py:1-17
Two lanes: `local` (MLX extraction sidecar, loopback, no API key) and `cloud` (Ollama daemon proxying the account's cloud model tag; auth is the daemon's signed-in account). [DERIVED] shared/polymath_shared/llm_extraction/client.py:8-14

## public surface
Module imported by: orchestrator/orchestrator/api/deep_research.py, orchestrator/orchestrator/api/ui.py, shared/polymath_shared/latent/compiler.py, shared/polymath_shared/worker_runtime.py, workers/workers/doc_parent_map_stage_worker.py, workers/workers/doc_profile_worker.py, workers/workers/llm_provider.py, workers/workers/summary_worker_impl.py [DERIVED] FACTS.importers

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `LLMExtractionClient` | class | (lane, *, url, model, timeout_s=180.0, max_attempts=2, limiter_key="default", api_key=None, cloud_opts=None); methods: probe, complete_one, extract_batched, extract, complete_batched, extract_from_raw, _infer_batch, _chat, … | shared/polymath_shared/llm_extraction/client.py:315-1153 | module importers above |
| `LLMCallResult` | dataclass | fields lane, model, raw_text, packet, sanitize, wall_ms, tokens_in=0, tokens_out=0, attempts=1, error_class=None, raw_head, lane_decision, limiter_effective, batch_tokens_cap, finish_reason, neighborhood_ids, reissue=False | shared/polymath_shared/llm_extraction/client.py:199-222 | — |
| `ExtractionTransportError` | class | RuntimeError subclass, no extra args | shared/polymath_shared/llm_extraction/client.py:245-246 | — |
| `local_batch_budget` | def | () -> REGISTRY.budget("llm_local:batch_tokens", …) | shared/polymath_shared/llm_extraction/client.py:235-242 | — |
| `output_budget_for` | def | (input_tokens: float, neighborhoods=1) -> int | shared/polymath_shared/llm_extraction/client.py:249-262 | — |
| `estimate_input_tokens` | def | (user_prompt: str) -> int | shared/polymath_shared/llm_extraction/client.py:265-266 | — |
| `admission_tokens` | def | (*texts: str \| None) -> int | shared/polymath_shared/llm_extraction/client.py:275-277 | — |
| `alias_neighborhoods` | def | (neighborhoods) -> (aliased_neighborhoods, aliases dict) | shared/polymath_shared/llm_extraction/client.py:280-288 | — |
| `restore_neighborhood_ids` | def | (packet, aliases) -> packet (in place) | shared/polymath_shared/llm_extraction/client.py:291-296 | — |
| `build_user_prompt` | def | (neighborhoods) -> str | shared/polymath_shared/llm_extraction/client.py:299-306 | — |
| `_lean_expand` | def | (obj: dict) -> dict (LEAN index form -> flat packet) | shared/polymath_shared/llm_extraction/client.py:156-192 | — |
| `_lane_limit` | def | (lane, provider=None) -> ProviderLimit | shared/polymath_shared/llm_extraction/client.py:66-83 | — |
| `SYSTEM_PROMPT` / `SYSTEM_PROMPT_TEMPLATE` / `LEAN_SYSTEM_PROMPT` | const | module-level strings; SYSTEM_PROMPT built at import time | shared/polymath_shared/llm_extraction/client.py:120,142,195 | — |

## contracts

**`output_budget_for(input_tokens, neighborhoods=1)`** shared/polymath_shared/llm_extraction/client.py:249-262
- out: `int(GENERATION_CONFIG["max_tokens"] + 700 * max(0, neighborhoods - 1))` = 2500 for 1 neighborhood [DERIVED] shared/polymath_shared/llm_extraction/client.py:261-262
- post: `input_tokens` is kept for the signature only; it no longer lowers the cap [DERIVED] shared/polymath_shared/llm_extraction/client.py:259-260

**`admission_tokens(*texts)`** shared/polymath_shared/llm_extraction/client.py:275-277
- in: every message the provider counts (system + user); None/empty skipped [DERIVED] shared/polymath_shared/llm_extraction/client.py:276
- out: sum of ceil(chars / 3) using `ADMISSION_CHARS_PER_TOKEN = 3.0` [DERIVED] shared/polymath_shared/llm_extraction/client.py:272,277

**`alias_neighborhoods(neighborhoods)` / `restore_neighborhood_ids(packet, aliases)`** shared/polymath_shared/llm_extraction/client.py:280-296
- out: prompts carry `n1`, `n2`, … aliases; restore maps back in place before the gate; unknown ids pass through unchanged (`aliases.get(item.neighborhood_id, item.neighborhood_id)`) [DERIVED] shared/polymath_shared/llm_extraction/client.py:287-288,294-295

**`build_user_prompt(neighborhoods)`** shared/polymath_shared/llm_extraction/client.py:299-306
- out: blocks `[neighborhood:{nid}]\n[chunk:{cid}]\n{text}` joined by `"\n\n"` [DERIVED] shared/polymath_shared/llm_extraction/client.py:303-306

**`LLMExtractionClient.__init__`** shared/polymath_shared/llm_extraction/client.py:332-373
- pre: `lane in ("local", "cloud")` else `ValueError(f"unknown lane: {lane!r}")` [DERIVED] shared/polymath_shared/llm_extraction/client.py:337-338
- post: `REGISTRY.ensure_store()` called (idempotent, fail-soft) [DERIVED] shared/polymath_shared/llm_extraction/client.py:345-346
- post: `cloud_opts` default = `{"reasoning_effort": "none", "json_mode": True}` [DERIVED] shared/polymath_shared/llm_extraction/client.py:363-366

**`probe()`** shared/polymath_shared/llm_extraction/client.py:487-526
- in: no document content; one-token ping (`"max_tokens": 1`) [DERIVED] shared/polymath_shared/llm_extraction/client.py:17,500-501
- out: `{"ok": True, "lane", "model", "wall_ms", "served_model"}`; raises on transport error after recording the attempt [DERIVED] shared/polymath_shared/llm_extraction/client.py:508-511,525-526
- post: recorded with `limiter_admitted=False, limiter_bypassed=True, http_dispatched=True`; timeout = `min(self.timeout_s, 30.0)` [DERIVED] shared/polymath_shared/llm_extraction/client.py:502-503,506-507

**`complete_one(user_prompt, *, system_prompt, max_tokens)`** shared/polymath_shared/llm_extraction/client.py:528-606
- in: cloud lanes only; local batched path uses `complete_batched` [DERIVED] shared/polymath_shared/llm_extraction/client.py:533-535
- out: `(raw_text, error_class|None)`; bare `"LIMITER_REFUSED"` on limiter refusal (existing consumers exact-match it); never interprets content [DERIVED] shared/polymath_shared/llm_extraction/client.py:531-533,541-544,561
- pre: reserves `admission_tokens(system_prompt, user_prompt) + max_tokens`; `settle()` trues up from real usage [DERIVED] shared/polymath_shared/llm_extraction/client.py:537-539,565
- post: `finally: limiter.release()` — the concurrency slot must be released [DERIVED] shared/polymath_shared/llm_extraction/client.py:601-606

**`_chat(user_prompt, max_tokens, system_prompt=None)`** shared/polymath_shared/llm_extraction/client.py:382-483
- out: `(content, prompt_tokens, completion_tokens, headers_dict)`; headers degrade to `{}` if not a plain mapping [DERIVED] shared/polymath_shared/llm_extraction/client.py:478-483
- post: local lane payload adds `repetition_penalty=1.15`, `repetition_context_size=400`, `chat_template_kwargs={"enable_thinking": False}`; cloud lane conditionally adds `reasoning_effort`, top-level `enable_thinking`, and `response_format` json_schema (only when `structured == "schema"` and `system_prompt is None`) else json_object [DERIVED] shared/polymath_shared/llm_extraction/client.py:400-409,416-439

## effect surface
- network: `httpx.post` to `{base_url}/v1/chat/completions` at shared/polymath_shared/llm_extraction/client.py:457 (_chat), :505 (probe); two more `httpx.post` sites at :766 and :932 (methods `_infer_batch` and one further site, beyond the shown excerpt) [DERIVED] FACTS.nondeterminism
- file read: `config/extraction_models/limiter.yaml` via `Path(__file__).resolve().parents[3]` shared/polymath_shared/llm_extraction/client.py:104-106
- store: `REGISTRY.ensure_store()` attaches the controller store at construction; a comment names `llm_controller_state` as the affected table [DERIVED] shared/polymath_shared/llm_extraction/client.py:345-346,344
- env: `POLYMATH_LLM_LOCAL_BATCH_TOKENS` = "28000" shared/polymath_shared/llm_extraction/client.py:238; `POLYMATH_LLM_LOCAL_BATCH_TOKENS_MAX` = "72000" shared/polymath_shared/llm_extraction/client.py:239; `POLYMATH_LEAN_LOCAL` = "on" shared/polymath_shared/llm_extraction/client.py:690 [DERIVED] FACTS.env
- env (comment-mentioned gate): `POLYMATH_REASONING_POLICY=1` gates the reasoning-policy overlay [DERIVED] shared/polymath_shared/llm_extraction/client.py:1040-1041
- Postgres tables read/written, Qdrant collections, subprocesses: none in this material [DERIVED] FACTS.tables_read/tables_written

## invariants
INVARIANT: output_budget_for(n neighborhoods) = 2500 + 700·(n−1), independent of input_tokens — shared/polymath_shared/llm_extraction/client.py:261-262 [DERIVED]
  fails-if: cap re-coupled to input size → finish=length truncation returns (measured: cap 484 → 3 relations; cap 2500 → 9 relations) shared/polymath_shared/llm_extraction/client.py:253-257
INVARIANT: local batch ceiling = max(seed, ceiling_env) ≥ seed 28000; floor 4000 < seed; step 2000 — shared/polymath_shared/llm_extraction/client.py:238-242 [DERIVED]
  fails-if: ceiling below seed → AdaptiveBudget cannot climb; comment: 45K OOMed with the fleet resident shared/polymath_shared/llm_extraction/client.py:226-228
INVARIANT: admission reserve chars/token (3.0) < estimate_input_tokens chars/token (4.0) — shared/polymath_shared/llm_extraction/client.py:266,272 [DERIVED]
  fails-if: reserve drops to 4.0 → under-reservation → the 429s the comment says this was built to stop shared/polymath_shared/llm_extraction/client.py:269-271
INVARIANT: temperature == 0.0 on every dispatched payload, both lanes — shared/polymath_shared/llm_extraction/client.py:46,397 [DERIVED]
  fails-if: nonzero temperature breaks the LOCKED decision-18 contract hash shared/polymath_shared/llm_extraction/client.py:42-45
INVARIANT: probe sends max_tokens=1 with no document content and bypasses the limiter — shared/polymath_shared/llm_extraction/client.py:17,500-503 [DERIVED]
  fails-if: probe queues behind a rate hold → liveness probe measures the limiter, not the endpoint shared/polymath_shared/llm_extraction/client.py:490-492
INVARIANT: every dispatched complete_one releases its limiter slot via `finally` — shared/polymath_shared/llm_extraction/client.py:601-606 [DERIVED]
  fails-if: slot leak deadlocked enrichment at 2 calls (threads parked in acquire forever) shared/polymath_shared/llm_extraction/client.py:602-605
INVARIANT: lane limiter seeds — local `kind="concurrency", init=2, min=1, max=4`; cloud `kind="rate", rpm=120, tpm=200000, conc_cap=18, min=2, max=18, use_headers=True` — shared/polymath_shared/llm_extraction/client.py:57-62 [DERIVED]
  fails-if: shared pool limiter lets one slow provider drag the pool's AIMD budget shared/polymath_shared/llm_extraction/client.py:348-350
INVARIANT: LEAN relation tuples with indices outside the entity array or non-int indices are silently dropped — shared/polymath_shared/llm_extraction/client.py:174-181 [DERIVED]
  fails-if: out-of-range indices reach the gate → SANITIZE quarantine of the whole packet

## determinism & idempotency
determinism: NONDETERMINISTIC (network `httpx.post` :457,:505,:766,:932; clocks `time.perf_counter`/`time.monotonic` e.g. :498,:552,:592; env reads :238-239; shared limiter/REGISTRY concurrency :345-346) [DERIVED] FACTS.nondeterminism
idempotency: UNSAFE for transport methods (probe/complete_one/extract* consume provider quota and park AIMD state on failure); SAFE for pure helpers (build_user_prompt, alias_neighborhoods, restore_neighborhood_ids, admission_tokens, estimate_input_tokens, _lean_expand) [INFERRED — network side effects vs. pure string/dict functions in SOURCE]

## failure behaviour
- `_ontology_text` swallows all exceptions → returns `""`; SYSTEM_PROMPT then ships with an empty `{{ONTOLOGY}}` slot — shared/polymath_shared/llm_extraction/client.py:109-113 [DERIVED]
- `_lane_limit` swallows yaml load failure → `_LIMITER_CONFIG = {}` → lane default seeds from `_LANE_LIMITS` — shared/polymath_shared/llm_extraction/client.py:71-77 [DERIVED]
- `_chat` header observability: non-mapping headers degrade to `{}`; transport never breaks — shared/polymath_shared/llm_extraction/client.py:478-481 [DERIVED]
- `_chat` reasoning overlay: any exception swallowed (`pass`) — additive feature, must never break the compiler — shared/polymath_shared/llm_extraction/client.py:447-456 [DERIVED]
- `complete_one`: `httpx.HTTPStatusError` → Cloudflare 3036-class daily quota parks the provider for the day (`park_provider_day`); 3040/429 → `record_failure` AIMD backoff; generic `Exception` → returns `("", type(exc).__name__)`, does not raise — shared/polymath_shared/llm_extraction/client.py:572-600 [DERIVED]
- `probe`: exception recorded then re-raised (caller sees it); HTTP ≥400 recorded as `HTTP_{status}` with parsed `retry-after` — shared/polymath_shared/llm_extraction/client.py:508-524 [DERIVED]
- `/infer_batch` statuses `(400, 404, 405)` mean "no batch endpoint" → fall back to per-neighborhood `/v1/chat/completions` — shared/polymath_shared/llm_extraction/client.py:309-312 [DERIVED]
- `ExtractionTransportError` raised when the endpoint is unreachable or repeatedly returns garbage; raised at :1086 (handled: expr, expr, raise) — shared/polymath_shared/llm_extraction/client.py:245-246 [DERIVED] FACTS.fallbacks
- Additional swallowed handlers beyond the shown excerpt: `pass` at :616 and :1149; `return None` at :629 and :646; handled-assign at :849 — shared/polymath_shared/llm_extraction/client.py:616,629,646,849,1149 [DERIVED] FACTS.fallbacks
- Quarantine mapping: sanitize failure → `_quarantine_class` = the sanitize disposition, except generic unparseable → `"QUARANTINED_UNPARSEABLE"` (so `SANITIZE_UNKNOWN_NEIGHBORHOOD` is never masked) — shared/polymath_shared/llm_extraction/client.py:86-92 [DERIVED]

## dumb-code flags
- Two chars-per-token ratios in one file: `len(user_prompt) / 4.0` vs `ADMISSION_CHARS_PER_TOKEN = 3.0`; comment admits English ~4, code/JSON ~3 — shared/polymath_shared/llm_extraction/client.py:266,269-272 [DERIVED]
- Dead parameter: `input_tokens` in `output_budget_for` kept "for the signature" only — shared/polymath_shared/llm_extraction/client.py:249,259-260 [DERIVED]
- Module-level side effect at import: `SYSTEM_PROMPT = _system_prompt()` runs ontology loading once at import time — shared/polymath_shared/llm_extraction/client.py:195 [DERIVED]
- Magic truncation lengths in `_lean_expand`: surface `[:200]`, type `[:80]`, quote `[:2000]`, predicate `[:120]` — shared/polymath_shared/llm_extraction/client.py:170-187 [DERIVED]
- Magic probe timeout `30.0` combined with per-client `timeout_s` — shared/polymath_shared/llm_extraction/client.py:506-507 [DERIVED]
- FACTS reports `_NO_INFER_BATCH_STATUSES` as `[400, 404, 405]` while SOURCE shows a tuple `(400, 404, 405)` — shared/polymath_shared/llm_extraction/client.py:312 [DERIVED]
- `"expected_output_tokens": 900` in GENERATION_CONFIG used "for batch-budget accounting only", not generation — shared/polymath_shared/llm_extraction/client.py:49 [DERIVED]

## refactor notes
- `GENERATION_CONFIG` is LOCKED (plan decision 18) and hashed into the extract stage contract via `workers.llm_provider.contract_identity`; changing it requires a new A/B record and re-extracts every document — shared/polymath_shared/llm_extraction/client.py:42-45
- `"LIMITER_REFUSED"` is an exact-match API for existing consumers; `_last_refusal_reason`/`_last_http_dispatched` were added precisely so the string itself need not change — shared/polymath_shared/llm_extraction/client.py:540-544
- `config/extraction_models/limiter.yaml` is the editable source of truth for limiter seeds; `_LANE_LIMITS` is only the code-level fallback — shared/polymath_shared/llm_extraction/client.py:55-56
- Local-lane payload keys `repetition_penalty` / `repetition_context_size` / `chat_template_kwargs.enable_thinking` are LOCKED (decision 18); Qwen3.5 thinking measured at 1600 tokens vs 38-token direct JSON when off — shared/polymath_shared/llm_extraction/client.py:402-409
- Constructor is the single seam all provider-calling paths go through (`ensure_store`); pMAP-stage dispatches previously escaped store attachment — shared/polymath_shared/llm_extraction/client.py:339-346
- Blast radius: 8 importer files listed in FACTS.importers; extraction contract hash also covers `GENERATION_CONFIG` / `pool_fingerprint` — shared/polymath_shared/llm_extraction/client.py:442-444

## VERIFY
```verify
grep -Fq '"max_tokens": 2500' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'ADMISSION_CHARS_PER_TOKEN = 3.0' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'return max(1, int(len(user_prompt) / 4.0))' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'rpm=120, tpm=200000, conc_cap=18' shared/polymath_shared/llm_extraction/client.py
grep -Fq '(400, 404, 405)' shared/polymath_shared/llm_extraction/client.py
test "$(grep -c -F 'httpx.post' shared/polymath_shared/llm_extraction/client.py)" -ge 4
! grep -Fq 'import instructor' shared/polymath_shared/llm_extraction/client.py
```
