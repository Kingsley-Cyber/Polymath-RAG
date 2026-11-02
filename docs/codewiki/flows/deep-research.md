# flow: deep-research
Deep research: plan, the research loop (moves live in `DR.MOVES`), evidence rows, the cited report, finish-now. Two streaming endpoints plus a plan card; the run engine (`_worker`) is the depth boundary of this capture.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `POST /research/deep/plan` enters `deep_research_plan`; `_libraries` merges `[req.corpus_id]` + `req.corpus_ids`, dedupes via `dict.fromkeys` | orchestrator/orchestrator/api/deep_research.py:490-495, 132-139 | `DeepPlanRequest` -> `list[str]` corpus ids | 422 `LIBRARY_REQUIRED` when no id survives |
| 2 | Read-scope gate: `require_corpora` loops `require_corpus`; `can_see` per corpus | orchestrator/orchestrator/web_scope.py:108-110, 103-105 | corpus ids -> pass/refuse | `CORPUS_NOT_ALLOWED` "that library is not open to this account" |
| 3 | Preset + moves toggle: `DR.Config.preset(req.preset, moves=moves_enabled(req))`; `moves_enabled` = request flag AND env `MOVES_ENV` (default `"1"`) not in `("0","false","off","no")` | orchestrator/orchestrator/api/deep_research.py:496-499, 83-84 | preset string -> `DR.Config` | 422 `UNKNOWN_PRESET` on `ValueError` |
| 4 | Lane names: `research_lane_names` = `stage_pin_fn("deep_research") or stage_pin_fn(compiler_stage) or []` (DR0: deep_research pin else the chat compiler's lanes) | orchestrator/orchestrator/api/deep_research.py:225-227, 244-245 | `config/llm_accounts.yaml` pins -> lane names | — |
| 5 | Roster built: `cloud_endpoints` = settings primary (kept unless parked while other providers exist) + `_configured_providers` (config/cloud_providers.json, AUTO-GATE: enabled AND key resolves) + `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`; sorted by name; roster composition logged once | shared/polymath_shared/llm_extraction/pool.py:217-262, 152-208, 117-133 | env + .env + json files -> `list[CloudEndpoint]` | loud `ValueError`: malformed JSON, reserved/duplicate names, missing url+model; parked lanes logged, skipped |
| 6 | Endpoints filtered to lane names; empty -> 503 `NO_RESEARCH_LANE` | orchestrator/orchestrator/api/deep_research.py:245-247 | roster + lane names -> research endpoints | 503, run cannot plan |
| 7 | `_compiler_attempt_order`: deterministic order — preferred lane, else blake2b(key)%len home lane; then first lane of a different family (URL netloc); then ring neighbours; lanes cold within `_COMPILER_LANE_COOLDOWN_S` moved to back, never dropped; pure over inputs | orchestrator/orchestrator/api/ui.py:1741-1774, 1733-1738 | endpoints + session key -> attempt list | — |
| 8 | `complete` port loop: per lane an `LLMExtractionClient("cloud", ..., max_attempts=1)` with `interactive = True` (INTERACTIVE-ADMISSION-V1: never wait on a lane limiter); success returns non-empty text; `last_refusal` (zero HTTP) appends to `skipped` without spending an attempt; real failures count toward `RESEARCH_DISPATCH_ATTEMPTS`; only-refused -> `AllLanesRefused(skipped)`, else `RuntimeError("research lanes failed: ...")` | orchestrator/orchestrator/api/deep_research.py:249-270 | prompt/system/max_tokens -> completion text | typed `AllLanesRefused` (engine counts it, ends branch) vs RuntimeError |
| 9 | Plan made: `DR.plan_goals(req.question, complete=..., config=...)` in `asyncio.to_thread`; not under the one-run lock ("a person may plan while a run streams") | orchestrator/orchestrator/api/deep_research.py:500-502, 491-494 | question + port + config -> draft goals | any exception -> 502 `PLAN_FAILED` (class name only, message never leaked); `not draft.goals` -> 502 `PLAN_EMPTY` |
| 10 | Plan card returned: `intent`, `evaluative`, lowercased `preset`, goals (`id`, `goal`, `query`, `move`), `DR.estimate(replace(config, first_width=len(draft.goals)), planned=True)`, `libraries`, `config.moves` | orchestrator/orchestrator/api/deep_research.py:509-513 | draft -> JSON card | — |
| 11 | `POST /research/deep` enters `deep_research`; hops 1-2 repeat (`_libraries` -> `require_corpora`) | orchestrator/orchestrator/api/deep_research.py:406-407 | `DeepResearchRequest` -> libraries | as hops 1-2 |
| 12 | Synthesizer resolved: `req.synthesizer or _default_synthesizer()` — first offered preference among `_litellm_models()` + `_ollama_models()`; providers whose env-indirected key is unset are hidden; must start `litellm:` or `ollama:` | orchestrator/orchestrator/api/deep_research.py:409-412; orchestrator/orchestrator/api/ui.py:83-92, 648-668, 117-138 | optional synth -> synth id | 422 `UNKNOWN_SYNTHESIZER`; silent-history: empty synth once fell to `litellm:openai/glm-5-free` with key unset -> LiteLLM "Missing credentials" (ui.py:84-87) |
| 13 | Preset for the run: `DR.Config.preset(req.preset)` | orchestrator/orchestrator/api/deep_research.py:413-416 | preset -> `shape` | 422 `UNKNOWN_PRESET` |
| 14 | Confirmed plan validated: `confirmed_plan(req, shape.breadth)` — `None` -> run without plan; empty list -> "the plan has no goals"; ≤ `2 * breadth` goals; query length in `PLAN_QUERY_CHARS` (3-300); `item.move not in DR.MOVES` refused; goal ≤ `PLAN_GOAL_CHARS`; repeated queries allowed | orchestrator/orchestrator/api/deep_research.py:87-108 | `req.plan` -> `(goal, query, move)` tuples | one 422 `PLAN_INVALID` joining every problem |
| 15 | One-run lock: `who = principal or "owner"` (from `principal_context.current()`); if `who in _RUNNING` -> 409; else register `_RUNNING[who] = cancel`, `_FINISH[who] = finish` (`threading.Event` pair) | orchestrator/orchestrator/api/deep_research.py:408, 417-424; shared/polymath_shared/principal_context.py:23-25 | principal -> run slot | 409 `DEEP_RESEARCH_BUSY` "one deep research run at a time; stop the other first" |
| 16 | SSE opens: first frame `_sse("phase", {"stage": "deep_start", ...})` with libraries and preset; `_worker` thread started (daemon, name `"deep-research"`) carrying `(req, libraries, synth, principal, loop, out, cancel, finish, plan)` — the research loop itself is past this capture's depth | orchestrator/orchestrator/api/deep_research.py:426-437, 111-112 | queue `out` -> SSE text | — |
| 17 | Event pump: `await asyncio.to_thread(out.get, True, HEARTBEAT_S)`; timeout -> `": keep-alive\n\n"` comment frame; `kind is _END` breaks; `"answer"` and `"error"` captured for the receipt; every frame re-emitted via `_sse` | orchestrator/orchestrator/api/deep_research.py:438-451 | queue items -> SSE stream | silent keep-alives mask a slow worker |
| 18 | Terminal `"done"` frame; finally: `cancel.set()` (a disconnect or any exit stops the run); `_RUNNING`/`_FINISH` entries deleted only if identity matches the registered events | orchestrator/orchestrator/api/deep_research.py:451-458 | exit -> cleanup | — |
| 19 | Receipt meta: `receipt_block(answer)` reads `result.meta.deep_research`; if `report_model` present it is replaced by `report_model_counts` (goals, findings, confidence tallies `strong`/`single_source`/`contested`, counter, open_questions, sources) — texts stay out because meta is capped at 64 KB | orchestrator/orchestrator/api/deep_research.py:462, 473-486 | answer dict -> counts-only block | oversized meta would lose the whole block, hence counts only |
| 20 | Receipt written: `record_query_receipt(tx, kind="deep_research", ...)` INSERT INTO `query_receipts` (question sha256 + head, corpora, wall_ms, summarized meta, error); `principal_id` stamped (migration 0066); entire write wrapped — failure logs a warning, never raises | orchestrator/orchestrator/api/deep_research.py:459-467; shared/polymath_shared/query_receipts.py:184-224 | run result -> `query_receipts` row | silent fallback: "deep research receipt not written: %s" (class name) |
| 21 | Meta serialization: `summarize_response` allowlists meta keys (incl. `deep_research`); `_meta_json` shrinks structurally — funnel `compact`, then long lists, then `DROP_ORDER` keys (funnel ids dropped, counts kept) — never slices a JSON string; last resort `{"truncated": True, "keys": ...}` | shared/polymath_shared/query_receipts.py:32-113, 152-181; shared/polymath_shared/funnel.py:111-127 | meta -> jsonb ≤ cap | progressive truncation, forensic core kept last |
| 22 | Stream returned: `StreamingResponse(..., media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})` | orchestrator/orchestrator/api/deep_research.py:469-470 | generator -> HTTP stream | — |
| 23 | `POST /research/deep/finish` -> `deep_research_finish` (entry per routing; handler body not in this capture) [INFERRED: it signals the run through `_FINISH`, the per-principal `finish` event registered at hop 15 and handed to `_worker`] | orchestrator/orchestrator/api/deep_research.py:517, 419, 424, 432 | finish request -> `finish` event set | unknown in this capture |

## state written

| store | what | anchor |
|---|---|---|
| Postgres `query_receipts` | one row per run: `query_id` (`"q_" + uuid hex[:24]`), `kind="deep_research"`, question sha256 + head, corpus_ids, `wall_ms`, status/verdict/citations/claims/evidence/source_docs (capped `[:32]`), `meta` jsonb, `error`, `principal_id` | shared/polymath_shared/query_receipts.py:191-216, 217-219 |
| Postgres `llm_providers` | `CREATE TABLE IF NOT EXISTS` ensured on the synthesizer-default read path (rows read, not written here) | orchestrator/orchestrator/api/ui.py:610-617 |
| process memory | `_RUNNING[who] = cancel`, `_FINISH[who] = finish`; deleted on stream exit when identity matches | orchestrator/orchestrator/api/deep_research.py:420-424, 454-458 |
| process memory | `_ROSTER_LOGGED` set dedupes roster/parked log lines per process | shared/polymath_shared/llm_extraction/pool.py:211-214 |
| Qdrant / files | none written on this path in SOURCE | — |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `MOVES_ENV` env var | `"1"` | with a falsy `req.moves`, or env in `("0","false","off","no")`, moves are disabled for plan and run | orchestrator/orchestrator/api/deep_research.py:83-84 |
| `POLYMATH_LLM_CLOUD_PRIMARY` | truthy `llm_cloud_primary` | `0` parks the settings primary, but only while other providers exist — roster never empty | shared/polymath_shared/llm_extraction/pool.py:218-227 |
| `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | `""` | JSON list of `{name, url, model}` extra lanes; malformed JSON or a `primary` name fails loudly | shared/polymath_shared/llm_extraction/pool.py:229-247 |
| provider `enabled` / `api_key_env` / `url_template`+`account_id_env` in config/cloud_providers.json | — | AUTO-GATE membership: unset key or account id parks the lane, logged once, never silent | shared/polymath_shared/llm_extraction/pool.py:152-208 |
| `POLYMATH_OLLAMA_MODELS` | `""` -> `OLLAMA_FREE_CLOUD_MODELS` | allowlist of ollama synthesizer names offered | orchestrator/orchestrator/api/ui.py:100-103 |
| `_COMPILER_PREFERRED_LANE`, `_COMPILER_LANE_COOLDOWN_S` | values not in capture | preferred first lane; cooldown that demotes recently-failed lanes to the back | orchestrator/orchestrator/api/ui.py:1742, 1754 |

## failure modes

1. 422 `LIBRARY_REQUIRED` -> no corpus named after merge/dedupe -> orchestrator/orchestrator/api/deep_research.py:136-137
2. `CORPUS_NOT_ALLOWED` -> `can_see(corpus_id)` false for at least one library -> orchestrator/orchestrator/web_scope.py:103-105
3. 422 `UNKNOWN_PRESET` -> `DR.Config.preset` raised `ValueError`, on both endpoints -> orchestrator/orchestrator/api/deep_research.py:498-499, 415-416
4. 503 `NO_RESEARCH_LANE` -> lane pin names match no configured endpoint -> orchestrator/orchestrator/api/deep_research.py:246-247
5. 502 `PLAN_FAILED` / `PLAN_EMPTY` -> planner raised (class surfaced, message never) / wrote no usable goals; the page can still start the run without a plan -> orchestrator/orchestrator/api/deep_research.py:503-508
6. `AllLanesRefused` vs `RuntimeError("research lanes failed: ...")` -> every lane's limiter refused at once (zero HTTP, engine ends the branch) vs real failures hit `RESEARCH_DISPATCH_ATTEMPTS` -> orchestrator/orchestrator/api/deep_research.py:251-270
7. 422 `PLAN_INVALID` -> plan over `2 * breadth` goals, query outside 3-300 chars, move not in `DR.MOVES`, goal over `PLAN_GOAL_CHARS`, or empty plan list; all problems in one message -> orchestrator/orchestrator/api/deep_research.py:94-107
8. 409 `DEEP_RESEARCH_BUSY` -> same principal already has a live run; note the plan card is outside this lock -> orchestrator/orchestrator/api/deep_research.py:420-422, 491-494
9. 422 `UNKNOWN_SYNTHESIZER` -> synth id not prefixed `litellm:` / `ollama:`; silent fallback nearby: an empty synthesizer defaults to the first OFFERED model, key-missing providers hidden -> orchestrator/orchestrator/api/deep_research.py:410-412; orchestrator/orchestrator/api/ui.py:83-92
10. Client disconnect silently ends the run -> `cancel.set()` in the `finally` of any stream exit -> orchestrator/orchestrator/api/deep_research.py:453
11. Receipt lost without failing the request -> any receipt exception swallowed ("deep research receipt not written: %s", class name; "query receipt not written") -> orchestrator/orchestrator/api/deep_research.py:466-467; shared/polymath_shared/query_receipts.py:221-223
12. Meta truncation cascade -> oversized meta shrinks structurally (funnel ids, lists, `DROP_ORDER`), worst case `{"truncated": True, "keys": ...}`; funnel counts survive ids -> shared/polymath_shared/query_receipts.py:173-181
13. Half-speed pool looks normal -> provider parked for unset key/account id is logged exactly once via `_log_once`, then simply absent -> shared/polymath_shared/llm_extraction/pool.py:173-176, 189-193, 211-214
14. Keep-alive frames hide a stalled worker -> `": keep-alive\n\n"` on every `HEARTBEAT_S` timeout while `_worker` produces nothing -> orchestrator/orchestrator/api/deep_research.py:440-452

## invariants

- INVARIANT: one deep research run per principal (`who = principal or "owner"`); the plan card is not part of the one-run lock. orchestrator/orchestrator/api/deep_research.py:417-424, 491-494 [DERIVED]
- INVARIANT: any stream exit (including disconnect) sets `cancel` and removes `_RUNNING`/`_FINISH` entries only when they are this run's own events. orchestrator/orchestrator/api/deep_research.py:453-458 [DERIVED]
- INVARIANT: a limiter refusal costs zero HTTP and does not spend a dispatch attempt; only transport failures count toward `RESEARCH_DISPATCH_ATTEMPTS`. orchestrator/orchestrator/api/deep_research.py:251-265 [DERIVED]
- INVARIANT: research clients run with `interactive = True` — they never wait on a lane limiter. orchestrator/orchestrator/api/deep_research.py:258 [DERIVED]
- INVARIANT: `_compiler_attempt_order` is pure over its inputs; cold lanes are demoted to the back, never dropped. orchestrator/orchestrator/api/ui.py:1744-1749, 1770-1774 [DERIVED]
- INVARIANT: the roster never goes empty (primary kept unless parked while other providers exist); duplicate names and malformed extras raise, never silently drop. shared/polymath_shared/llm_extraction/pool.py:218-226, 256-259 [DERIVED]
- INVARIANT: planner failures surface only `type(exc).__name__`, never the message. orchestrator/orchestrator/api/deep_research.py:503-506 [DERIVED]
- INVARIANT: the receipt's `deep_research` meta carries counts (`report_model_counts`), never the evidence model's texts. orchestrator/orchestrator/api/deep_research.py:473-486 [DERIVED]
- INVARIANT: a receipt failure can never turn into a request failure. shared/polymath_shared/query_receipts.py:188-190, 221-223 [DERIVED]
- INVARIANT: a request naming no synthesizer is never routed to a provider whose key is missing. orchestrator/orchestrator/api/ui.py:83-92 [DERIVED]
- INVARIANT: a repeated query in a confirmed plan is allowed — every confirmed goal is searched. orchestrator/orchestrator/api/deep_research.py:90-91 [DERIVED]

## VERIFY

```verify
grep -Fq 'one deep research run at a time; stop the other first' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'client.interactive = True' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'raise AllLanesRefused(skipped)' orchestrator/orchestrator/api/deep_research.py
grep -Eq 'stage_pin_fn\("deep_research"\) or stage_pin_fn\(compiler_stage\) or \[\]' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS is not valid JSON' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'X-Accel-Buffering' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'query receipt not written' shared/polymath_shared/query_receipts.py
```
