# flow: deep-research
Deep research: plan, the research loop (moves: broad / deep / adjacent / inverse), evidence rows, the cited report, finish-now.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Library check: `_libraries` merges `req.corpus_id` + `req.corpus_ids`, drops empties, dedupes via `dict.fromkeys`; empty -> 422 `LIBRARY_REQUIRED`; `require_corpora` -> `require_corpus` -> `can_see` per id | orchestrator/orchestrator/api/deep_research.py:132-139, orchestrator/orchestrator/web_scope.py:85-92 [DERIVED] | DeepPlanRequest / DeepResearchRequest -> list[str] corpus ids | 422 LIBRARY_REQUIRED; refusal CORPUS_NOT_ALLOWED |
| 2 | Preset + moves for the plan: `DR.Config.preset(req.preset, moves=moves_enabled(req))`; `moves_enabled` = `bool(req.moves)` and `MOVES_ENV` env not in `("0", "false", "off", "no")` (default `"1"`) | orchestrator/orchestrator/api/deep_research.py:479-481, 83-84 [DERIVED] | preset string, req.moves -> DR config | ValueError -> 422 UNKNOWN_PRESET |
| 3 | Research lane names: `research_lane_names` = the `deep_research` stage pin, else the chat compiler stage lanes (`COMPILER_STAGE`); then filter `cloud_endpoints()` by name; no endpoint -> 503 `NO_RESEARCH_LANE` | orchestrator/orchestrator/api/deep_research.py:230-239, 225-227 [DERIVED] | stage_pin fn + stage -> endpoint list | 503 NO_RESEARCH_LANE |
| 4 | Cloud roster assembled: settings primary + `_configured_providers` (config/cloud_providers.json; joins iff `enabled` is not false AND key resolves — `_resolve_key` reads process env then repo `.env`) + `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` JSON; sorted by name; per-lane opts `reasoning_effort`, `json_mode`, `structured`, `dedicated`, `request_char_budget`, `enable_thinking`, `think_suffix`, `max_output_tokens` | shared/polymath_shared/llm_extraction/pool.py:217-262, 152-208, 117-133 [DERIVED] | settings + config files -> list[CloudEndpoint] | malformed JSON / missing name+url+model / reserved or duplicate names -> ValueError (loud); unset key parks the lane, logged once |
| 5 | Lane ordering: `_compiler_attempt_order(endpoints, key, max_attempts=2)` — preferred lane (`_COMPILER_PREFERRED_LANE`) else `blake2b(key)` home lane, then first lane of a different family (`_lane_family` = URL netloc), then ring neighbours; lanes cold within `_COMPILER_LANE_COOLDOWN_S` moved to back, never dropped; pure over inputs | orchestrator/orchestrator/api/ui.py:1669-1702, 1661-1666 [DERIVED] | endpoints + session key -> ordered attempt list (2) | all-cold still tries |
| 6 | `complete` closure: per lane an `LLMExtractionClient("cloud", ..., timeout_s=PORT_TIMEOUT_S, max_attempts=1)` with `attempt_stage="deep_research"`, `attempt_function="DEEP_RESEARCH"`; first non-error non-empty text wins; else `RuntimeError("research lanes failed: " + failures)` | orchestrator/orchestrator/api/deep_research.py:241-252 [DERIVED] | prompt/system/max_tokens -> text | both lanes fail -> RuntimeError (surfaces as PLAN_FAILED in the plan path) |
| 7 | Planner call: `DR.plan_goals(req.question, complete=complete, config=config)` in `asyncio.to_thread`; exception -> 502 `PLAN_FAILED` (only `type(exc).__name__` logged and shown, never the message); `draft.goals` empty -> 502 `PLAN_EMPTY` | orchestrator/orchestrator/api/deep_research.py:482-490 [DERIVED] | question + port + config -> draft goals | 502 PLAN_FAILED / PLAN_EMPTY; the page can still start the run without a plan |
| 8 | Plan card returned (not part of the one-run lock): `intent`, `evaluative`, preset, goals `[{id, goal, query, move}]`, `DR.estimate(replace(config, first_width=len(draft.goals)), planned=True)`, libraries, `config.moves` | orchestrator/orchestrator/api/deep_research.py:491-495, 472-476 [DERIVED] | draft -> card dict | none past step 7 |
| 9 | Run entry: `_libraries(req)` again; `principal = principal_context.current()` (None = legacy / trusted-local caller) | orchestrator/orchestrator/api/deep_research.py:388-390, shared/polymath_shared/principal_context.py:23-25 [DERIVED] | DeepResearchRequest -> libraries + principal | same as hop 1 |
| 10 | Synthesizer: `req.synthesizer or _default_synthesizer()` — first `_PREFERRED_DEFAULTS` entry that is offered, else first offered model; offered = `_litellm_models` (llm_providers rows, enabled + `_provider_ready` — an `env:` key that resolves to nothing is hidden) + `_ollama_models` (allowlist from `POLYMATH_OLLAMA_MODELS` else `OLLAMA_FREE_CLOUD_MODELS`, `available` when the daemon registers it via `OLLAMA_URL/api/tags`, 3 s); must start `"litellm:"` / `"ollama:"` | orchestrator/orchestrator/api/deep_research.py:392-394, orchestrator/orchestrator/api/ui.py:83-92, 582-602, 117-138, 575-579, 100-114 [DERIVED] | req.synthesizer -> synth id | 422 UNKNOWN_SYNTHESIZER |
| 11 | Run preset: `DR.Config.preset(req.preset)` -> `shape` (uses `shape.breadth` next) | orchestrator/orchestrator/api/deep_research.py:395-399 [DERIVED] | preset -> shape | ValueError -> 422 UNKNOWN_PRESET |
| 12 | Confirmed plan validated: `req.plan is None` -> None (run plans itself); else at most `2 * breadth` goals, each query within `PLAN_QUERY_CHARS` (3-300 per the docstring), each move in `DR.MOVES`, goal at most `PLAN_GOAL_CHARS`; empty plan refused ("the plan has no goals"); all problems joined into one 422 `PLAN_INVALID`; repeated query allowed — every confirmed goal is searched | orchestrator/orchestrator/api/deep_research.py:87-108 [DERIVED] | req.plan -> tuple[(goal, query, move)] or None | 422 PLAN_INVALID |
| 13 | One-run lock: `who = principal or "owner"`; under `_LOCK`, `who in _RUNNING` -> 409 `DEEP_RESEARCH_BUSY`; else `_RUNNING[who] = cancel`, `_FINISH[who] = finish` (threading.Event pair) | orchestrator/orchestrator/api/deep_research.py:400-406 [DERIVED] | principal -> registered cancel/finish events | 409 DEEP_RESEARCH_BUSY |
| 14 | SSE stream `events()`: `_sse` frames (`event: {name}\ndata: {json}`); daemon thread `_worker` (name `"deep-research"`) runs the research loop and puts `(kind, data)` on a queue (worker body not in this material); queue get with `HEARTBEAT_S` via `asyncio.to_thread`, empty -> `": keep-alive\n\n"`; `kind is _END` breaks; `"answer"` captured, `"error"` captures `error_code`; final `_sse("done", {})` | orchestrator/orchestrator/api/deep_research.py:408-433, 111-112, 414-415 [DERIVED] | req/libraries/synth/principal/plan -> SSE events + answer dict | worker "error" events stream out as failure |
| 15 | Exit path: `finally` sets `cancel` (a disconnect or any exit stops the run) and removes `_RUNNING`/`_FINISH` entries under `_LOCK` only if identity matches | orchestrator/orchestrator/api/deep_research.py:434-440 [DERIVED] | events teardown -> clean registries | dropped connection kills the run |
| 16 | Receipt shaping: `receipt_block(answer)` reads `answer.result.meta.deep_research`; if `report_model` present it is replaced by `report_model_counts` — goals, findings, confidence tallies over `("strong", "single_source", "contested")`, counter, open_questions, sources — because receipt meta is capped at 64 KB; evidence texts stay out | orchestrator/orchestrator/api/deep_research.py:455-468 [DERIVED] | answer dict or None -> meta block | oversized meta would lose the whole meta, hence counts only |
| 17 | Receipt write: `record_query_receipt(tx, kind="deep_research", scope_kind="explicit", meta={"route": "research/deep", "model": synth, ...})` — `summarize_response` allowlists meta keys (incl. `deep_research`, `generation`, `synthesis`, `gap_check`), `knowledge_scope_of` reads `req.scope` only (`parse_scope` fails closed; malformed -> `{"invalid": true}`), INSERT into `query_receipts` with sha256 + head of the question, then `principal_id` UPDATE (migration 0066; `client` stays the software identity); `_meta_json` shrinks structurally (funnel compact -> list shrink -> DROP_ORDER keys -> `{"truncated": True, "keys": ...}`), never slices JSON | shared/polymath_shared/query_receipts.py:176-216, 32-107, 110-120, 146-173; shared/polymath_shared/code/scope.py:99-111; shared/polymath_shared/funnel.py:111-127; orchestrator/orchestrator/api/deep_research.py:441-449 [DERIVED] | answer/failure -> `query_receipts` row | receipt failure swallowed: warning "deep research receipt not written: %s" / `QUERY_RECEIPT_FAILED`, returns None |
| 18 | Response transport: `StreamingResponse(media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})` | orchestrator/orchestrator/api/deep_research.py:451-452 [DERIVED] | events -> HTTP stream | none shown |
| 19 | Finish-now: `deep_research_finish` looks up `_FINISH[who]` under `_LOCK`; absent -> 404 `NO_DEEP_RESEARCH_RUN`; present -> `finish.set()`, returns `{"finishing": true}` — the run starts nothing new, lets in-flight calls finish, writes the report with stop reason `finished_early` | orchestrator/orchestrator/api/deep_research.py:499-509, shared/polymath_shared/principal_context.py:23-25 [DERIVED] | `{}` -> `{"finishing": true}` | 404 NO_DEEP_RESEARCH_RUN |

## state written

- Postgres `query_receipts` row: kind `"deep_research"`, corpus ids, scope `"explicit"`, question sha256 + 200-char head, wall_ms, status/verdict/citations/claims/evidence/source_docs, meta jsonb, error — shared/polymath_shared/query_receipts.py:196-208 [DERIVED]; `principal_id` backfilled (migration 0066) — shared/polymath_shared/query_receipts.py:209-211 [DERIVED].
- In-memory `_RUNNING[who] = cancel` and `_FINISH[who] = finish`, `who = principal or "owner"`, under `_LOCK`; removed on any stream exit — orchestrator/orchestrator/api/deep_research.py:402-406, 436-440 [DERIVED].
- In-memory `_COMPILER_LANE_FAILED_AT` lane-failure timestamps consulted for cooldown ordering (writes not in this material) — orchestrator/orchestrator/api/ui.py:1698-1701 [DERIVED].
- In-memory `_ROSTER_LOGGED` set so each roster composition is logged once ("cloud extraction pool: %s") — shared/polymath_shared/llm_extraction/pool.py:211-214, 260-261 [DERIVED].
- Postgres `llm_providers` ensured (`CREATE TABLE IF NOT EXISTS`) and read for the synthesizer default — orchestrator/orchestrator/api/ui.py:540-555 [DERIVED].

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `MOVES_ENV` env (name held in the constant `MOVES_ENV`) | `"1"` | moves disabled when value in `("0", "false", "off", "no")` and/or `req.moves` falsy; feeds `moves_enabled` | orchestrator/orchestrator/api/deep_research.py:83-84 [DERIVED] |
| `POLYMATH_LLM_CLOUD_PRIMARY` (settings `llm_cloud_primary`) | true | `0` parks the primary lane, but only while other providers exist — the roster never goes empty | shared/polymath_shared/llm_extraction/pool.py:225-227 [DERIVED] |
| `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | empty | JSON list of `{name, url, model, api_key_env, reasoning_effort, json_mode, structured}`; malformed JSON / missing fields / duplicate or reserved names -> ValueError, loud | shared/polymath_shared/llm_extraction/pool.py:229-259 [DERIVED] |
| `POLYMATH_OLLAMA_MODELS` | `OLLAMA_FREE_CLOUD_MODELS` | comma list of Ollama synthesizer names; unregistered names still list with a pull hint | orchestrator/orchestrator/api/ui.py:100-103, 117-138 [DERIVED] |
| config/llm_accounts.yaml stage pin `deep_research` | fall back to `COMPILER_STAGE` lanes | picks which cloud endpoints serve planning/extraction | orchestrator/orchestrator/api/deep_research.py:225-227 [DERIVED] |
| config/cloud_providers.json `enabled` / `api_key_env` / `account_id_env` | enabled unless false; key must resolve | auto-gate: unset key or account id parks the lane, logged once; `url_template` + `{account_id}` builds the Cloudflare OpenAI-compat URL | shared/polymath_shared/llm_extraction/pool.py:152-208 [DERIVED] |

## failure modes

1. Symptom: 422 `LIBRARY_REQUIRED` -> request named no library -> deep_research.py:136-137.
2. Symptom: refusal `CORPUS_NOT_ALLOWED` -> `can_see(corpus_id)` false for some requested corpus -> web_scope.py:85-87.
3. Symptom: 422 `UNKNOWN_PRESET` / `UNKNOWN_SYNTHESIZER` -> bad preset string; synthesizer not `litellm:`/`ollama:` -> deep_research.py:479-481, 393-394, 396-398.
4. Symptom: 422 `PLAN_INVALID` -> plan empty, over `2 * breadth` goals, query outside `PLAN_QUERY_CHARS`, move not in `DR.MOVES`, goal over `PLAN_GOAL_CHARS`; every problem listed at once -> deep_research.py:94-107.
5. Symptom: 409 `DEEP_RESEARCH_BUSY` -> the principal (or "owner") already holds `_RUNNING` -> deep_research.py:402-404.
6. Symptom: 503 `NO_RESEARCH_LANE` -> stage pin names match no enabled cloud endpoint -> deep_research.py:236-239.
7. Symptom: 502 `PLAN_FAILED` -> planner raised, or both lanes failed (`RuntimeError("research lanes failed: ...")` from hop 6); only the exception class is logged/shown, never the message; silent fallback: the page can still start the run without a plan -> deep_research.py:484-490, 252.
8. Symptom: 502 `PLAN_EMPTY` -> `draft.goals` empty -> deep_research.py:489-490.
9. Symptom: 404 `NO_DEEP_RESEARCH_RUN` -> finish called with no `_FINISH[who]` entry -> deep_research.py:503-507.
10. Silent fallback: a lane quietly missing -> provider with unset `api_key_env` / `account_id_env` is parked and logged once ("cloud provider %r parked: %s not set"), never silently dropped; duplicate/malformed config instead raises -> pool.py:169-193, 221-222, 234-245.
11. Silent fallback: receipt lost -> any receipt-write exception is swallowed to a warning ("deep research receipt not written: %s", `QUERY_RECEIPT_FAILED`) -> deep_research.py:448-449, query_receipts.py:212-215.
12. Silent degradation: oversized receipt meta -> `_meta_json` shrinks funnel, then long lists, then drops whole `DROP_ORDER` keys to `{"truncated": True}`; last resort keeps only `{"truncated": True, "keys": sorted(m)}` -> query_receipts.py:146-173.
13. Symptom: run dies mid-stream -> any disconnect or exit sets `cancel`; cold lanes (recent transport failure) are demoted, not dropped, so a provider storm delays but does not remove attempts -> deep_research.py:434-435, ui.py:1698-1701.

## invariants

- INVARIANT: one deep research run at a time per principal; the plan endpoint is outside the one-run lock — deep_research.py:402-404, 474-476 [DERIVED].
- INVARIANT: a friend may only research libraries they can read (`require_corpora` before anything else) — deep_research.py:138 [DERIVED].
- INVARIANT: receipts never break a stream or query — deep_research.py:448-449, query_receipts.py:180-182, 213-214 [DERIVED].
- INVARIANT: evidence texts stay out of the receipt meta; only `report_model_counts` go in (64 KB meta cap, past which the whole meta is lost) — deep_research.py:456-458 [DERIVED].
- INVARIANT: the cloud roster never goes empty — the primary is parked only while other providers exist — pool.py:225-227 [DERIVED].
- INVARIANT: malformed provider/extra-endpoint config fails loudly (ValueError); a parked lane is logged once, never silent — pool.py:221-222, 174-177 [DERIVED].
- INVARIANT: lane attempt order is pure over its inputs; cold lanes move to the back, never dropped — ui.py:1672-1677, 1700-1701 [DERIVED].
- INVARIANT: the planner's exception message is never surfaced, only its class — deep_research.py:486-488 [DERIVED].
- INVARIANT: knowledge scope is read from the request only; a response can never set or widen it; a malformed scope never reads as "both roles" (fail closed) — query_receipts.py:112-115, scope.py:100-102 [DERIVED].
- INVARIANT: every confirmed goal is searched; a repeated query is allowed — deep_research.py:90-91 [DERIVED].
- INVARIANT: a request naming no synthesizer is never routed to a hidden provider (missing env key -> skipped) — ui.py:84-87, 575-579 [DERIVED].
- INVARIANT: `client` in the receipt stays the software identity; the principal is recorded separately as `principal_id` — query_receipts.py:209-210 [DERIVED].

## VERIFY

```verify
grep -Fq 'one deep research run at a time; stop the other first' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'research lanes failed: ' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'finished_early' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'NO_RESEARCH_LANE' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS' shared/polymath_shared/llm_extraction/pool.py
test "$(grep -c -F 'CloudEndpoint(' shared/polymath_shared/llm_extraction/pool.py)" -ge 3
grep -Fq 'INSERT INTO query_receipts' shared/polymath_shared/query_receipts.py
! grep -Fq 'DEEP_RESEARCH_BUSY' orchestrator/orchestrator/api/ui.py
```
