# unit: shared/polymath_shared/llm_extraction/client.py
anchor: shared/polymath_shared/llm_extraction/client.py:1-1215

Note: SOURCE shows file lines 1–600; anchors above 600 come from FACTS (static analysis), tagged [DERIVED] where used.

## purpose
Direct OpenAI-compatible HTTP transport for the `polymath-extraction-v1` contract; deliberately the plan's documented fallback shape (direct calls behind the Pydantic contract) — the contract, gate, and admission pipeline are the load-bearing parts, this file is swappable — shared/polymath_shared/llm_extraction/client.py:1-6 [DERIVED].
Two lanes: `local` (MLX extraction sidecar, loopback, no API key) and `cloud` (Ollama daemon proxying the account's cloud model; auth is the daemon's signed-in account; `require_cloud_eligible` runs immediately before every dispatch) — shared/polymath_shared/llm_extraction/client.py:8-14 [DERIVED].

## public surface

| symbol | kind | signature | anchor | used by |
|---|---|---|---|---|
| LLMExtractionClient | class | (lane, *, url, model, timeout_s=180.0, max_attempts=2, limiter_key="default", api_key=None, cloud_opts=None) | shared/polymath_shared/llm_extraction/client.py:359-1214 | module importers (list below) |
| LLMCallResult | dataclass | fields: lane, model, raw_text, packet, sanitize, wall_ms, tokens_in=0, tokens_out=0, attempts=1, error_class=None, raw_head="", lane_decision, limiter_effective, batch_tokens_cap, finish_reason, neighborhood_ids=[], reissue=False | shared/polymath_shared/llm_extraction/client.py:202-225 | — |
| ExtractionTransportError | class | RuntimeError subclass | shared/polymath_shared/llm_extraction/client.py:248-249 | — |
| LaneSkip | frozen dataclass | (lane, reason, retry_after_s=None); .as_dict() | shared/polymath_shared/llm_extraction/client.py:260-272 | — |
| AllLanesRefused | class | RuntimeError(skips); .skips, .receipt | shared/polymath_shared/llm_extraction/client.py:282-290 | — |
| degraded_receipt | def | (skips) -> dict | shared/polymath_shared/llm_extraction/client.py:275-279 | — |
| local_batch_budget | def | () -> REGISTRY budget | shared/polymath_shared/llm_extraction/client.py:238-245 | — |
| output_budget_for | def | (input_tokens: float, neighborhoods: int = 1) -> int | shared/polymath_shared/llm_extraction/client.py:293-306 | — |
| estimate_input_tokens | def | (user_prompt: str) -> int | shared/polymath_shared/llm_extraction/client.py:309-310 | — |
| admission_tokens | def | (*texts: str \| None) -> int | shared/polymath_shared/llm_extraction/client.py:319-321 | — |
| alias_neighborhoods | def | (neighborhoods) -> (aliased list, aliases dict) | shared/polymath_shared/llm_extraction/client.py:324-332 | — |
| restore_neighborhood_ids | def | (packet, aliases) -> packet (in place) | shared/polymath_shared/llm_extraction/client.py:335-340 | — |
| build_user_prompt | def | (neighborhoods) -> str | shared/polymath_shared/llm_extraction/client.py:343-350 | — |
| GENERATION_CONFIG | const | dict | shared/polymath_shared/llm_extraction/client.py:48-56 | — |
| SYSTEM_PROMPT / SYSTEM_PROMPT_TEMPLATE / LEAN_SYSTEM_PROMPT | const | str | shared/polymath_shared/llm_extraction/client.py:123-156,198 | — |

Module importers (file-level, FACTS.importers): orchestrator/orchestrator/api/deep_research.py, orchestrator/orchestrator/api/ui.py, shared/polymath_shared/latent/compiler.py, shared/polymath_shared/worker_runtime.py, workers/workers/doc_parent_map_stage_worker.py, workers/workers/doc_profile_worker.py, workers/workers/llm_provider.py, workers/workers/summary_worker_impl.py — shared/polymath_shared/llm_extraction/client.py:1-1215 [DERIVED].
LLMExtractionClient methods (FACTS): _record_attempt, __init__, _headers, _chat, probe, complete_one, _account_env, _provider, _response_hash, _lane_limiter, extract_batched, _infer_batch, extract, complete_batched, _extract_prompt, extract_from_raw — shared/polymath_shared/llm_extraction/client.py:208-225 [DERIVED]; bodies after line 600 not shown in SOURCE.

## contracts

**LLMExtractionClient.\_\_init\_\_**
- pre: `lane in ("local", "cloud")` else `ValueError(f"unknown lane: {lane!r}")` — shared/polymath_shared/llm_extraction/client.py:388-389
- post: calls `REGISTRY.ensure_store()` (idempotent, fail-soft; explicit attach_store() still wins) — shared/polymath_shared/llm_extraction/client.py:390-397
- default `cloud_opts = {"reasoning_effort": "none", "json_mode": True}` — shared/polymath_shared/llm_extraction/client.py:414-417

**complete_one(user_prompt, \*, system_prompt, max_tokens) -> (raw_text, error_class|None)**
- never interprets content; caller's gate parses; cloud lanes only (local goes through complete_batched) — shared/polymath_shared/llm_extraction/client.py:582-586
- admission: `limiter.admit(est_tokens=admission_tokens(system_prompt, user_prompt) + max_tokens, reserved_output=max_tokens, block=not self.interactive)` — shared/polymath_shared/llm_extraction/client.py:591-592
- post: `self._last_refusal_reason = decision.reason`; bare "LIMITER_REFUSED" return kept for exact-match consumers — shared/polymath_shared/llm_extraction/client.py:593-598
- on exception: returns `('', type(exc).__name__)` — shared/polymath_shared/llm_extraction/client.py:655 [DERIVED]

**_chat(user_prompt, max_tokens, system_prompt=None) -> (content, prompt_tokens, completion_tokens, hdrs)**
- POST `{base_url}/v1/chat/completions` — shared/polymath_shared/llm_extraction/client.py:509-511
- local payload: `repetition_penalty=1.15`, `repetition_context_size=400`, `chat_template_kwargs={"enable_thinking": False}` — shared/polymath_shared/llm_extraction/client.py:452-461
- cloud: `response_format` json_schema only when `cloud_opts["structured"] == "schema"` AND `system_prompt is None`; else json_object when json_mode (default True) — shared/polymath_shared/llm_extraction/client.py:480-491
- out: non-mapping header object degrades to `{}` — shared/polymath_shared/llm_extraction/client.py:530-533

**probe() -> dict**
- no document content; one-token ping: messages=[{"role":"user","content":"ping"}], `max_tokens: 1` — shared/polymath_shared/llm_extraction/client.py:536-537,551-552
- timeout `min(self.timeout_s, 30.0)`; recorded with `limiter_admitted=False, limiter_bypassed=True, http_dispatched=True` — shared/polymath_shared/llm_extraction/client.py:553-558

**output_budget_for(input_tokens, neighborhoods=1) -> int**
- out: `int(GENERATION_CONFIG["max_tokens"] + GENERATION_CONFIG["extra_tokens_per_neighborhood"] * max(0, neighborhoods - 1))` = 2500 + 700×(n−1) — shared/polymath_shared/llm_extraction/client.py:305-306
- `input_tokens` kept for signature; no longer lowers the cap — shared/polymath_shared/llm_extraction/client.py:297-304

**estimate_input_tokens / admission_tokens**
- estimate: `max(1, int(len(user_prompt) / 4.0))` — shared/polymath_shared/llm_extraction/client.py:310
- admission: Σ ceil(len(t)/3.0) over non-empty texts — shared/polymath_shared/llm_extraction/client.py:316,319-321

**alias_neighborhoods / restore_neighborhood_ids**
- aliases `f"n{i + 1}"` → real neighborhood ids; restore maps back in place before the gate — shared/polymath_shared/llm_extraction/client.py:324-339

**_lean_expand(obj) -> dict**
- entity surface `[:200]`, type `[:80]`, quote = surface `[:2000]`; relation predicate `[:120]`, quote `[:2000]`; relations with si/oi outside `[0, len(entities))` dropped — shared/polymath_shared/llm_extraction/client.py:173-190
- out: `{"contract": "polymath-extraction-v1", "profile": "volume", items}` — shared/polymath_shared/llm_extraction/client.py:194-195

**_quarantine_class(s_res)**: returns `"QUARANTINED_UNPARSEABLE"` when s_res None or error_class in (None, "SANITIZE_UNPARSEABLE"); else the sanitize disposition — shared/polymath_shared/llm_extraction/client.py:93-95
**_retry_nudge(s_res)**: SANITIZE_UNKNOWN_NEIGHBORHOOD gets the id-specific nudge; everything else the generic JSON nudge — shared/polymath_shared/llm_extraction/client.py:99-104

## effect surface
- network: `httpx.post` to `/v1/chat/completions` — shared/polymath_shared/llm_extraction/client.py:509 (_chat), 557 (probe), 827, 993 (extract paths; FACTS.nondeterminism) [DERIVED]
- file read: `config/extraction_models/limiter.yaml` at `Path(__file__).resolve().parents[3]` — shared/polymath_shared/llm_extraction/client.py:76-78,107-109
- env: POLYMATH_LLM_LOCAL_BATCH_TOKENS = '28000' — shared/polymath_shared/llm_extraction/client.py:241; POLYMATH_LLM_LOCAL_BATCH_TOKENS_MAX = '72000' — shared/polymath_shared/llm_extraction/client.py:242; POLYMATH_LEAN_LOCAL = 'on' — shared/polymath_shared/llm_extraction/client.py:751 [DERIVED]
- store attach: `REGISTRY.ensure_store()` in \_\_init\_\_ (limiter/controller-store persistence; the one seam every provider-calling path goes through) — shared/polymath_shared/llm_extraction/client.py:390-397
- Postgres tables read/written: none (FACTS.tables_read and tables_written empty)

## invariants
INVARIANT: output cap == 2500 + 700 × max(0, neighborhoods−1) — shared/polymath_shared/llm_extraction/client.py:305-306 [DERIVED]
  fails-if: truncation as measured: cap 484 → finish=length, salvaged JSON, 3 relations vs cap 2500 → 841 tokens, 9 relations — shared/polymath_shared/llm_extraction/client.py:298-301 [DERIVED]
INVARIANT: GENERATION_CONFIG temperature == 0.0 and max_tokens == 2500 (LOCKED, decision 18) — shared/polymath_shared/llm_extraction/client.py:49-50 [DERIVED]
  fails-if: hash feeds workers.llm_provider.contract_identity → every document re-extracts — shared/polymath_shared/llm_extraction/client.py:45-47 [DERIVED]
INVARIANT: estimate rate 4.0 chars/token > admission reserve rate 3.0 chars/token — shared/polymath_shared/llm_extraction/client.py:310,316 [DERIVED]
  fails-if: under-reservation is what produced 429s; over-reservation is refunded by settle() — shared/polymath_shared/llm_extraction/client.py:313-315 [DERIVED]
INVARIANT: batch budget floor 4000 ≤ effective ≤ max(seed, ceiling), seed 28000, ceiling env 72000, step 2000 — shared/polymath_shared/llm_extraction/client.py:234-235,241-245 [DERIVED]
  fails-if: 45K OOMed with the fleet resident; ceiling below seed collapses the climb — shared/polymath_shared/llm_extraction/client.py:230-231,245 [DERIVED]
INVARIANT: degraded_receipt http_dispatched == False always (nothing was dispatched) — shared/polymath_shared/llm_extraction/client.py:277-279 [DERIVED]
  fails-if: receipt would misreport quota spend for an all-skipped walk
INVARIANT: AllLanesRefused.receipt == degraded_receipt(self.skips) — shared/polymath_shared/llm_extraction/client.py:287-288 [DERIVED]
INVARIANT: _lean_expand drops relations whose si/oi not in [0, len(entities)) — shared/polymath_shared/llm_extraction/client.py:183-184 [DERIVED]
  fails-if: out-of-range indices would emit wrong surfaces in the flat packet
INVARIANT: probe payload max_tokens == 1 and content == "ping" (no document content) — shared/polymath_shared/llm_extraction/client.py:536-537,551-552 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network: httpx.post — shared/polymath_shared/llm_extraction/client.py:509,557,827,993 [DERIVED]; clocks: time.perf_counter / time.monotonic — shared/polymath_shared/llm_extraction/client.py:550,562,564,605,613,631,653,660,812,847,865,875,903,982,987,1009,1019,1026,1071,1081,1085,1093,1112,1143,1152,1161,1176,1185 [DERIVED]; env reads — shared/polymath_shared/llm_extraction/client.py:241-242,751 [DERIVED]; limiter.yaml file read — shared/polymath_shared/llm_extraction/client.py:76-78 [DERIVED])
idempotency: UNSAFE (each dispatch spends provider quota; probe deliberately bypasses the limiter — shared/polymath_shared/llm_extraction/client.py:553-555 [DERIVED]; `_LIMITER_CONFIG` memoized globally after first load, a failed load caches `{}` — shared/polymath_shared/llm_extraction/client.py:73-81 [DERIVED])

## failure behaviour
- _ontology_text: SWALLOWED → `return ""`; system prompt ships without the ontology block — shared/polymath_shared/llm_extraction/client.py:115
- limiter.yaml load: handled → `_LIMITER_CONFIG = {}`; falls back to `_LANE_LIMITS` code seeds — shared/polymath_shared/llm_extraction/client.py:79-80,60-65
- _chat header read: handled → `hdrs = {}` — shared/polymath_shared/llm_extraction/client.py:532
- reasoning-policy overlay: SWALLOWED pass; never breaks the compiler — shared/polymath_shared/llm_extraction/client.py:507
- probe transport error: records the Attempt, then re-raises — shared/polymath_shared/llm_extraction/client.py:560-563
- complete_one exception: returns `('', type(exc).__name__)` — shared/polymath_shared/llm_extraction/client.py:655 [DERIVED]
- further SWALLOWED pass / return None at shared/polymath_shared/llm_extraction/client.py:677,690,707,1210 and handled raise paths at shared/polymath_shared/llm_extraction/client.py:910,1147 — dispositions per FACTS.fallbacks; bodies beyond shown SOURCE [DERIVED]
- raised types: ValueError (unknown lane) — shared/polymath_shared/llm_extraction/client.py:388-389; ExtractionTransportError (endpoint unreachable or repeated garbage) — shared/polymath_shared/llm_extraction/client.py:248-249; AllLanesRefused (every lane refused; fail fast, never a wait) — shared/polymath_shared/llm_extraction/client.py:282-284

## dumb-code flags
- dead parameter: `input_tokens` in output_budget_for ignored for the cap (kept for signature) — shared/polymath_shared/llm_extraction/client.py:297-304
- two chars-per-token literals: `/4.0` (estimate) vs `ADMISSION_CHARS_PER_TOKEN = 3.0` (admission reserve); intentional (conservative) but must move together — shared/polymath_shared/llm_extraction/client.py:310,313-316
- truncation magic numbers in _lean_expand: 200 (surface), 80 (type), 2000 (quote), 120 (predicate) — shared/polymath_shared/llm_extraction/client.py:173-190; raw_head first 200 chars — shared/polymath_shared/llm_extraction/client.py:213-214
- `ALL_LANES_REFUSED = "ALL_LANES_REFUSED"` used both as receipt "type" and exception-message prefix — shared/polymath_shared/llm_extraction/client.py:256,289-290
- `_NO_INFER_BATCH_STATUSES = (400, 404, 405)` — statuses meaning "no batch endpoint", fall back to per-neighborhood calls — shared/polymath_shared/llm_extraction/client.py:353-356
- `expected_output_tokens: 900` used "for batch-budget accounting only" — shared/polymath_shared/llm_extraction/client.py:52

## refactor notes
- GENERATION_CONFIG is LOCKED (decision 18), hashed into the extract-stage contract via workers.llm_provider.contract_identity — change only with a new A/B record; expect every document to re-extract — shared/polymath_shared/llm_extraction/client.py:45-47
- complete_one's bare "LIMITER_REFUSED" return string is exact-matched by existing consumers — shared/polymath_shared/llm_extraction/client.py:593-595
- 8 file-level importers (FACTS.importers) depend on this module: orchestrator deep_research/ui, latent compiler, worker_runtime, doc_parent_map_stage_worker, doc_profile_worker, llm_provider, summary_worker_impl — shared/polymath_shared/llm_extraction/client.py:1-1215 [DERIVED]
- SHORT-ID CONTRACT (measured 2026-08-30): never ask the model to echo 70-char hash ids — 5/25 calls dropped the ':0' suffix and were quarantined SANITIZE_UNKNOWN_NEIGHBORHOOD — shared/polymath_shared/llm_extraction/client.py:326-330
- extraction clients must never set `reasoning_role`: extraction stays byte-identical so its contract hash (GENERATION_CONFIG / pool_fingerprint) is untouched — shared/polymath_shared/llm_extraction/client.py:492-495
- file is the documented swappable fallback; preserve the contract/gate/admission pipeline — shared/polymath_shared/llm_extraction/client.py:2-6

## VERIFY
```verify
grep -Fq '"max_tokens": 2500' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'ADMISSION_CHARS_PER_TOKEN = 3.0' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'return max(1, int(len(user_prompt) / 4.0))' shared/polymath_shared/llm_extraction/client.py
grep -Fq '_NO_INFER_BATCH_STATUSES = (400, 404, 405)' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'os.environ.get(LOCAL_BATCH_TOKENS_MAX_ENV, "72000")' shared/polymath_shared/llm_extraction/client.py
grep -Fq 'class AllLanesRefused(RuntimeError):' shared/polymath_shared/llm_extraction/client.py
test "$(grep -c -F 'httpx.post' shared/polymath_shared/llm_extraction/client.py)" -ge 4
```
