# flow: deep-research
Deep research: plan, the research loop (moves: broad / deep / adjacent / inverse), evidence rows, the cited report, finish-now.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Plan entry `POST /research/deep/plan` -> `deep_research_plan`; resolve libraries: dedupe `corpus_id` + `corpus_ids` | orchestrator/orchestrator/api/deep_research.py:472-477 | question + corpus ids -> `list[str]` | 422 `LIBRARY_REQUIRED` when no id survives (deep_research.py:136-137) |
| 2 | Read-permission gate: `require_corpora` -> `require_corpus` per id | orchestrator/orchestrator/web_scope.py:90-92, 85-87 | ids -> ok | `CORPUS_NOT_ALLOWED` refusal (web_scope.py:87) |
| 3 | Moves gate: `moves_enabled` = `req.moves` AND env `MOVES_ENV` (default `"1"`) not in `("0","false","off","no")` | orchestrator/orchestrator/api/deep_research.py:83-84 | req.moves -> bool | moves silently off via env |
| 4 | Preset resolve `DR.Config.preset(req.preset, moves=...)` | orchestrator/orchestrator/api/deep_research.py:479-481 | preset name -> `DR.Config` | 422 `UNKNOWN_PRESET` on `ValueError` |
| 5 | Lane names: `research_lane_names` = `stage_pin("deep_research")` else the chat compiler stage pin (config/llm_accounts.yaml) | orchestrator/orchestrator/api/deep_research.py:225-227 | pin fn -> lane names | silent fallback to compiler lanes |
| 6 | Roster build `cloud_endpoints`: settings primary (unless parked) + `config/cloud_providers.json` providers + `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`; sorted by name; duplicate names refused | shared/polymath_shared/llm_extraction/pool.py:217-262 | settings + files + env -> `list[CloudEndpoint]` | loud `ValueError` on malformed extras JSON / duplicate names |
| 7 | Provider auto-gate: enabled not false AND key resolves (env then `.env`); Cloudflare `url_template`+`account_id_env` resolution | shared/polymath_shared/llm_extraction/pool.py:152-208, 117-133 | provider dicts -> endpoints | lane parked (logged once) when key/account unset |
| 8 | No endpoint matches lane names -> 503 | orchestrator/orchestrator/api/deep_research.py:237-239 | endpoints -> none | 503 `NO_RESEARCH_LANE` |
| 9 | `complete` port: up to 2 attempts via `_compiler_attempt_order` (hash home lane by `blake2b(key)`, then a lane of a different URL netloc family, then ring neighbours; lanes cold within `_COMPILER_LANE_COOLDOWN_S` moved last, never dropped); one `LLMExtractionClient` per attempt (`max_attempts=1`, `PORT_TIMEOUT_S`) | orchestrator/orchestrator/api/deep_research.py:241-252; orchestrator/orchestrator/api/ui.py:1669-1702 | prompt/system/max_tokens -> text | `RuntimeError("research lanes failed: " + ...)` after both fail or return empty |
| 10 | Plan drafted: `DR.plan_goals(question, complete=..., config=...)` off-thread | orchestrator/orchestrator/api/deep_research.py:482-484 | question -> `draft.goals` | any exception -> 502 `PLAN_FAILED`, class name only (deep_research.py:485-488) |
| 11 | Empty plan -> 502 | orchestrator/orchestrator/api/deep_research.py:489-490 | `draft.goals` -> 502 | `PLAN_EMPTY`; page may still start the run |
| 12 | Plan card returned: `intent`, `evaluative`, `preset`, goals `[{id, goal, query, move}]`, `DR.estimate(replace(config, first_width=len(draft.goals)), planned=True)`, `libraries`, `moves` | orchestrator/orchestrator/api/deep_research.py:491-495 | draft -> card JSON | — |
| 13 | Run entry `POST /research/deep` -> `deep_research`: same `_libraries` gate | orchestrator/orchestrator/api/deep_research.py:388-389 | req -> libraries | 422 `LIBRARY_REQUIRED` / `CORPUS_NOT_ALLOWED` |
| 14 | Synthesizer: `req.synthesizer or _default_synthesizer()`; must start with `"litellm:"` or `"ollama:"` | orchestrator/orchestrator/api/deep_research.py:391-394 | synth id -> synth | 422 `UNKNOWN_SYNTHESIZER` |
| 15 | Default synth = first offered preference across `_litellm_models` + `_ollama_models`; a provider whose env-indirected key is unset is hidden | orchestrator/orchestrator/api/ui.py:83-92, 575-579 | none -> synth id | silently skips unready providers |
| 16 | Preset `DR.Config.preset(req.preset)` for run shape | orchestrator/orchestrator/api/deep_research.py:395-398 | preset -> shape | 422 `UNKNOWN_PRESET` |
| 17 | `confirmed_plan`: `None` -> no plan; else at most `2 * breadth` goals, query 3-300 chars (`PLAN_QUERY_CHARS`), move in `DR.MOVES`, goal <= `PLAN_GOAL_CHARS`; repeated query allowed | orchestrator/orchestrator/api/deep_research.py:87-108 | `req.plan` -> `tuple[(goal, query, move)]` | 422 `PLAN_INVALID`, all problems joined `"; "` |
| 18 | One-run lock: `who = principal or "owner"`; `_RUNNING[who]`/`_FINISH[who]` under `_LOCK` | orchestrator/orchestrator/api/deep_research.py:400-406 | principal -> cancel/finish events | 409 `DEEP_RESEARCH_BUSY` |
| 19 | SSE stream opens: `phase` `deep_start` event; daemon worker thread `_worker` (name `"deep-research"`) carries the research loop (body not in SOURCE) | orchestrator/orchestrator/api/deep_research.py:408-419 | queue -> SSE frames | worker internals out of view here [INFERRED: only the thread spawn is visible] |
| 20 | Event pump: `queue.get` timeout `HEARTBEAT_S` -> `": keep-alive\n\n"`; `answer`/`error` captured; `_END` breaks; `done` emitted | orchestrator/orchestrator/api/deep_research.py:420-433, 111-112 | queue items -> SSE | keep-alive only on silence |
| 21 | `finally`: `cancel.set()` on ANY exit (a disconnect stops the run); lock cleanup of `_RUNNING`/`_FINISH` | orchestrator/orchestrator/api/deep_research.py:434-440 | — | run stops silently on client disconnect |
| 22 | Receipt block: texts stay out, counts go in — `report_model_counts` (goals, findings, confidence strong/single_source/contested, counter, open_questions, sources); meta capped at 64 KB | orchestrator/orchestrator/api/deep_research.py:455-468 | answer -> counts block | past the cap the whole meta is lost |
| 23 | `record_query_receipt`: `INSERT INTO query_receipts` (`query_id` = `"q_" + uuid hex[:24]`, `question_sha256`, `wall_ms`, meta jsonb); `principal_id` backfilled (migration 0066); meta shrunk structurally by `_meta_json` (funnel `compact`, `_shrink_lists`, `DROP_ORDER`) — never a sliced JSON string | shared/polymath_shared/query_receipts.py:178-218, 146-175 | answer/failure -> Postgres row | receipt silently missing; warning log only |
| 24 | Finish-now `POST /research/deep/finish`: `finish.set()`; in-flight calls complete, report written with stop reason `finished_early` | orchestrator/orchestrator/api/deep_research.py:499-509 | `{}` -> 202 `{"finishing": true}` | 404 `NO_DEEEP_RESEARCH_RUN` — literally `NO_DEEP_RESEARCH_RUN` (deep_research.py:507) |

## state written

| state | what | anchor |
|---|---|---|
| Postgres `query_receipts` | one row per run: kind `deep_research`, scope corpora, wall ms, status/verdict, meta `{"route": "research/deep", "model": synth, "deep_research": counts}` | shared/polymath_shared/query_receipts.py:198-210 |
| Postgres `query_receipts.principal_id` | backfilled when a principal context exists | shared/polymath_shared/query_receipts.py:211-213 |
| Postgres `llm_providers` | read here for the synthesizer roster (`CREATE TABLE IF NOT EXISTS` guard on read) | orchestrator/orchestrator/api/ui.py:540-558 |
| in-memory `_RUNNING` / `_FINISH` | per-principal cancel/finish events under `_LOCK` | orchestrator/orchestrator/api/deep_research.py:400-406, 436-440 |
| in-memory `_COMPILER_LANE_FAILED_AT` | last transport failure per lane name (cooldown ordering) | orchestrator/orchestrator/api/ui.py:1698-1700 |
| in-memory `_ROSTER_LOGGED` | once-only roster/parked logging | shared/polymath_shared/llm_extraction/pool.py:211-214 |
| SSE stream | `text/event-stream`, `no-cache`, `X-Accel-Buffering: no` | orchestrator/orchestrator/api/deep_research.py:451-452 |
| files read | `config/cloud_providers.json`, `.env` (gitignored), stage pins in `config/llm_accounts.yaml` | shared/polymath_shared/llm_extraction/pool.py:152-158, 117-133; orchestrator/orchestrator/api/deep_research.py:226 |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `MOVES_ENV` (constant) | `"1"` | value in `("0","false","off","no")` forces moves off even when `req.moves` is true | orchestrator/orchestrator/api/deep_research.py:84 |
| `POLYMATH_LLM_CLOUD_PRIMARY` | unset (`True`) | `0` parks the settings primary lane; roster stays non-empty while other providers exist | shared/polymath_shared/llm_extraction/pool.py:219-226 |
| `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | unset | JSON list of `{name,url,model}` appended to the roster; malformed JSON or a `primary` name raises `ValueError` | shared/polymath_shared/llm_extraction/pool.py:229-248 |
| `POLYMATH_OLLAMA_MODELS` | `OLLAMA_FREE_CLOUD_MODELS` | comma list overriding the Ollama synthesizer allowlist | orchestrator/orchestrator/api/ui.py:100-103 |
| `_COMPILER_PREFERRED_LANE` | module constant | named lane goes first for every session, replacing the hash home lane | orchestrator/orchestrator/api/ui.py:155-158 |

## failure modes

1. 422 `LIBRARY_REQUIRED` -> no corpus id in the request -> orchestrator/orchestrator/api/deep_research.py:136-137
2. `CORPUS_NOT_ALLOWED` -> a friend named a library they cannot read -> orchestrator/orchestrator/web_scope.py:85-87
3. 422 `UNKNOWN_PRESET` -> `DR.Config.preset` raised `ValueError` -> orchestrator/orchestrator/api/deep_research.py:479-481, 396-398
4. 502 `PLAN_FAILED` -> planner raised; only `type(exc).__name__` logged and surfaced ("the class only, never the message") -> orchestrator/orchestrator/api/deep_research.py:485-488
5. 502 `PLAN_EMPTY` -> planner wrote no usable search -> orchestrator/orchestrator/api/deep_research.py:489-490
6. 503 `NO_RESEARCH_LANE` -> neither the `deep_research` stage pin nor the compiler pin matched any roster endpoint -> orchestrator/orchestrator/api/deep_research.py:225-239
7. `RuntimeError("research lanes failed: ...")` -> both `_compiler_attempt_order` attempts errored or returned empty text -> orchestrator/orchestrator/api/deep_research.py:243-252
8. 422 `UNKNOWN_SYNTHESIZER` -> synth id not `litellm:`/`ollama:` prefixed -> orchestrator/orchestrator/api/deep_research.py:393-394
9. 422 `PLAN_INVALID` -> confirmed plan broke size/move/charset rules; every problem listed at once -> orchestrator/orchestrator/api/deep_research.py:94-107
10. 409 `DEEP_RESEARCH_BUSY` -> principal already holds the one run slot -> orchestrator/orchestrator/api/deep_research.py:402-405
11. 404 `NO_DEEP_RESEARCH_RUN` -> finish called with no live run -> orchestrator/orchestrator/api/deep_research.py:503-507
12. Silent stop: client disconnect sets `cancel` in `finally`, run ends without an error event -> orchestrator/orchestrator/api/deep_research.py:434-435
13. Silent missing receipt: receipt write failure only warns ("deep research receipt not written" / "query receipt not written") -> orchestrator/orchestrator/api/deep_research.py:448-449; shared/polymath_shared/query_receipts.py:215-217
14. Parked lane: provider key or `account_id_env` unset in env and `.env` -> lane leaves the roster with one log line, never silently -> shared/polymath_shared/llm_extraction/pool.py:172-177, 186-193
15. Roster poison (loud, not silent): malformed extras JSON, duplicate endpoint names, reserved `primary` -> `ValueError` -> shared/polymath_shared/llm_extraction/pool.py:234-235, 246-248, 258-259
16. Hidden synthesizer: env-indirected `api_key` unset -> provider excluded from offered models; empty request synth falls to the next offered -> orchestrator/orchestrator/api/ui.py:575-579, 83-92
17. Oversized receipt meta: past 64 KB the whole meta would be lost -> `receipt_block` keeps counts only and `_meta_json` shrinks structurally -> orchestrator/orchestrator/api/deep_research.py:456-460; shared/polymath_shared/query_receipts.py:146-175

## invariants

- INVARIANT: one deep research run at a time per principal (`who = principal or "owner"`); the plan endpoint is outside the lock — orchestrator/orchestrator/api/deep_research.py:400-406, 474-475 [DERIVED]
- INVARIANT: a failed or empty plan never blocks the run; both 502 bodies tell the page to start without one — orchestrator/orchestrator/api/deep_research.py:488, 490 [DERIVED]
- INVARIANT: any exit from the run stream, including disconnect, sets `cancel` — orchestrator/orchestrator/api/deep_research.py:434-435 [DERIVED]
- INVARIANT: receipts never break a stream or query; failures degrade to a warning log — orchestrator/orchestrator/api/deep_research.py:448-449; shared/polymath_shared/query_receipts.py:182-183 [DERIVED]
- INVARIANT: the receipt's `deep_research` meta carries counts only, never evidence texts (64 KB cap) — orchestrator/orchestrator/api/deep_research.py:456-460 [DERIVED]
- INVARIANT: receipt meta is shrunk structurally, never sliced into invalid JSON — shared/polymath_shared/query_receipts.py:147-150 [DERIVED]
- INVARIANT: lane order tries a different provider family second; cold lanes move to the back, never dropped — orchestrator/orchestrator/api/ui.py:1673-1677, 1700-1701 [DERIVED]
- INVARIANT: planner failures surface the exception class only, never the message — orchestrator/orchestrator/api/deep_research.py:486-488 [DERIVED]
- INVARIANT: a request naming no synthesizer never lands on a hidden (key-unset) provider — orchestrator/orchestrator/api/ui.py:84-87 [DERIVED]
- INVARIANT: roster composition and parked lanes are logged once, never silent — shared/polymath_shared/llm_extraction/pool.py:155-156, 174-177, 260-261 [DERIVED]
- INVARIANT: request scope parsing fails closed (`ScopeError`, never read as both roles) — shared/polymath_shared/code/scope.py:100-101 [DERIVED]

## VERIFY

```verify
grep -Fq 'one deep research run at a time; stop the other first' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'no model lane is configured for research' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'research lanes failed: ' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'you have no deep research run to finish' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'INSERT INTO query_receipts' shared/polymath_shared/query_receipts.py
test "$(grep -c -F 'query_receipts' shared/polymath_shared/query_receipts.py)" -ge 3
```
