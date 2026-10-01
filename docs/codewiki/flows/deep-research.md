# flow: deep-research
Deep research: plan, the research loop (moves: broad / deep / adjacent / inverse), evidence rows, the cited report, finish-now.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | `POST /research/deep/plan` → `deep_research_plan`; `_libraries` merges `corpus_id` + `corpus_ids`, dedupes via `dict.fromkeys` | orchestrator/orchestrator/api/deep_research.py:472-477, 132-139 [DERIVED] | `DeepPlanRequest` -> `list[str]` libraries | 422 `LIBRARY_REQUIRED` when no id survives |
| 2 | `require_corpora` → `require_corpus` per id → `can_see` read check | orchestrator/orchestrator/web_scope.py:90-92, 85-87 [DERIVED] | corpus ids -> None | 422 `CORPUS_NOT_ALLOWED` |
| 3 | moves gate `moves_enabled`: `req.moves` AND env `MOVES_ENV` (default `"1"`) not in `("0", "false", "off", "no")` | orchestrator/orchestrator/api/deep_research.py:83-84 [DERIVED] | req -> bool | moves silently off via env |
| 4 | `DR.Config.preset(req.preset, moves=...)` | orchestrator/orchestrator/api/deep_research.py:479-481 [DERIVED] | preset str -> `Config` | `ValueError` → 422 `UNKNOWN_PRESET` |
| 5 | `_complete_port(req.question)`: lane names = `stage_pin("deep_research")` else `stage_pin(COMPILER_STAGE)` (pin lives in `config/llm_accounts.yaml` per docstring) | orchestrator/orchestrator/api/deep_research.py:230-236, 225-227 [DERIVED] | question -> lane name list | silent fallback to the chat compiler's lanes |
| 6 | roster `cloud_endpoints`: primary endpoint (kept unless parked) + `_configured_providers()` + `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`; sorted by name; duplicate names → `ValueError`; composition logged once | shared/polymath_shared/llm_extraction/pool.py:217-262 [DERIVED] | settings + config + env -> `list[CloudEndpoint]` | loud `ValueError` on malformed extras JSON / missing fields / name `"primary"` |
| 7 | provider auto-gate: `enabled` not false AND key resolves (`_resolve_key`: process env first, then repo `.env`); Cloudflare lanes may use `url_template` + `account_id_env` with `{account_id}` substituted; parked lanes logged once, never silent | shared/polymath_shared/llm_extraction/pool.py:152-208, 117-133 [DERIVED] | `cloud_providers.json` -> endpoints | provider parked (absent from roster, one log line) |
| 8 | endpoints filtered to lane names; none match → 503 | orchestrator/orchestrator/api/deep_research.py:237-239 [DERIVED] | roster -> research lanes | 503 `NO_RESEARCH_LANE` |
| 9 | `complete` closure: `_compiler_attempt_order(endpoints, key, max_attempts=2)` (preferred/home lane via `blake2b(key) % len(roster)`, first lane of a different netloc family, then ring neighbours; lanes cold within `_COMPILER_LANE_COOLDOWN_S` moved to back, never dropped); per lane `LLMExtractionClient("cloud", ..., timeout_s=PORT_TIMEOUT_S, max_attempts=1)` with `attempt_stage="deep_research"`, `attempt_function="DEEP_RESEARCH"`; success = no error and non-empty text | orchestrator/orchestrator/api/deep_research.py:241-252; orchestrator/orchestrator/api/ui.py:1687-1720, 1679-1684 [DERIVED] | prompt/system/max_tokens -> text | `RuntimeError("research lanes failed: " + failures)` |
| 10 | `DR.plan_goals(req.question, complete=..., config=...)` via `asyncio.to_thread`; exception → 502 `PLAN_FAILED` (exception **class name only**, never the message); `not draft.goals` → 502 `PLAN_EMPTY` | orchestrator/orchestrator/api/deep_research.py:484-490 [DERIVED] | question + complete + config -> goals | 502 `PLAN_FAILED` / `PLAN_EMPTY`; page may still start the run |
| 11 | plan card returned: `intent`, `evaluative`, `preset` (lowered), `goals[{id, goal, query, move}]`, `estimate(replace(config, first_width=len(draft.goals)), planned=True)`, `libraries`, `moves` | orchestrator/orchestrator/api/deep_research.py:491-495 [DERIVED] | draft -> JSON card | — |
| 12 | `POST /research/deep` → `deep_research`: `_libraries` again, then `principal_context.current()` | orchestrator/orchestrator/api/deep_research.py:388-390; shared/polymath_shared/principal_context.py:23-25 [DERIVED] | `DeepResearchRequest` -> libraries + principal | 422s as hops 1-2 |
| 13 | synthesizer pick: `req.synthesizer` or `_default_synthesizer()` (first of `_PREFERRED_DEFAULTS` among offered litellm+ollama models, key-missing providers skipped; else first offered; else `_PREFERRED_DEFAULT`); must `startswith(("litellm:", "ollama:"))` | orchestrator/orchestrator/api/deep_research.py:392-394; orchestrator/orchestrator/api/ui.py:83-92 [DERIVED] | req -> synth id | 422 `UNKNOWN_SYNTHESIZER` |
| 14 | `DR.Config.preset(req.preset)`; `confirmed_plan(req, shape.breadth)`: plan optional (`None` passes); at most `2 * breadth` goals; query length within `PLAN_QUERY_CHARS` (docstring: 3-300 chars); `item.move` in `DR.MOVES`; goal ≤ `PLAN_GOAL_CHARS`; empty plan list → "the plan has no goals" | orchestrator/orchestrator/api/deep_research.py:395-398, 87-108 [DERIVED] | `req.plan` -> `(goal, query, move)` tuples or `None` | 422 `PLAN_INVALID`, all problems joined `"; "` |
| 15 | one-run lock under `_LOCK`: `who = principal or "owner"`; already in `_RUNNING` → 409; else `_RUNNING[who] = cancel`, `_FINISH[who] = finish` | orchestrator/orchestrator/api/deep_research.py:399-406 [DERIVED] | -> registered `threading.Event` pair | 409 `DEEP_RESEARCH_BUSY` |
| 16 | return `StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})` | orchestrator/orchestrator/api/deep_research.py:451-452 [DERIVED] | generator -> SSE response | — |
| 17 | `events()`: `_sse("phase", {"stage": "deep_start", ...})`; daemon thread `_worker` (name `"deep-research"`, args include `synth`, `cancel`, `finish`, `plan`); queue pump `out.get(True, HEARTBEAT_S)` — `Empty` yields `": keep-alive\n\n"`; `_END` breaks; `answer`/`error` captured; final `_sse("done", {})`; frames via `_sse`: `event: {event}\ndata: {json}\n\n` (worker body not in this slice) | orchestrator/orchestrator/api/deep_research.py:408-433, 414-415, 111-112 [DERIVED] | worker queue -> SSE frames | client disconnect handled in finally |
| 18 | finally: `cancel.set()` (comment: "a disconnect (or any exit) stops the run"); `_RUNNING`/`_FINISH` entries deleted only if identity matches | orchestrator/orchestrator/api/deep_research.py:434-440 [DERIVED] | | run always stopped and cleaned |
| 19 | receipt: `receipt_block(answer)` replaces `report_model` with `report_model_counts` (goals, findings, confidence counts over `"strong"/"single_source"/"contested"`, counter, open_questions, sources — texts stay out, meta cap 64 KB); `record_query_receipt(kind="deep_research", scope_kind="explicit", meta={"route": "research/deep", "model": synth, ...}, error=failure)`; failure only logged | orchestrator/orchestrator/api/deep_research.py:441-449, 455-468 [DERIVED] | answer -> receipt row | warning "deep research receipt not written"; stream unharmed |
| 20 | receipt internals: `summarize_response` allowlists meta keys incl. `deep_research`; qid `"q_" + uuid.uuid4().hex[:24]`; INSERT into `query_receipts` with `question_sha256`, `meta` jsonb via `_meta_json` (funnel compact → shrink long lists → `DROP_ORDER` keys → `{"truncated": true}`; never text-slices); `principal_id` backfilled (migration 0066) | shared/polymath_shared/query_receipts.py:32-107, 178-218, 146-175 [DERIVED] | | meta structurally truncated; DB error → receipt dropped, `QUERY_RECEIPT_FAILED` logged |
| 21 | `POST /research/deep/finish` → `deep_research_finish`: `who = principal_context.current() or "owner"`; `_FINISH.get(who)` under `_LOCK`; missing → 404; else `finish.set()` → `{"finishing": True}` (docstring: 202, run stops with reason `finished_early`) | orchestrator/orchestrator/api/deep_research.py:499-509 [DERIVED] | -> finishing flag | 404 `NO_DEEP_RESEARCH_RUN` |

## state written

- Postgres `query_receipts`: INSERT of `(query_id, kind, received_at=clock_timestamp(), client, corpus_ids, scope, mode, latent, question_sha256, question_head, wall_ms, status, verdict, citations, claims, evidence, source_docs, meta jsonb, error)` — shared/polymath_shared/query_receipts.py:197-210 [DERIVED]
- `query_receipts.principal_id` UPDATE when a principal is set — shared/polymath_shared/query_receipts.py:211-213 [DERIVED]
- Postgres `llm_providers` table `CREATE TABLE IF NOT EXISTS` (touched on the synthesizer-dropdown read path) — orchestrator/orchestrator/api/ui.py:562-569 [DERIVED]
- In-memory run registry: `_RUNNING[who] = cancel`, `_FINISH[who] = finish`, deleted on exit — orchestrator/orchestrator/api/deep_research.py:405-406, 437-440 [DERIVED]
- In-memory once-log set `_ROSTER_LOGGED` for roster/parked messages — shared/polymath_shared/llm_extraction/pool.py:211-214 [DERIVED]
- Files read, not written: `config/cloud_providers.json` (`_PROVIDERS_FILE`), repo `.env` (`_ENV_FILE`) — shared/polymath_shared/llm_extraction/pool.py:157-158, 124-125 [DERIVED]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `MOVES_ENV` | `"1"` | values `("0", "false", "off", "no")` disable moves even when `req.moves` is set | orchestrator/orchestrator/api/deep_research.py:84 [DERIVED] |
| `deep_research` stage pin (`config/llm_accounts.yaml`) | absent | absent → research lanes fall back to the chat compiler stage pin (`COMPILER_STAGE`) | orchestrator/orchestrator/api/deep_research.py:225-227 [DERIVED] |
| `POLYMATH_LLM_CLOUD_PRIMARY` | unset → `True` | `"0"` parks the primary lane while other providers exist; roster never goes empty otherwise | shared/polymath_shared/llm_extraction/pool.py:218-227 [DERIVED] |
| `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | `""` | JSON list of `{name, url, model, ...}`; malformed JSON / missing fields / reserved name / duplicates → loud `ValueError` | shared/polymath_shared/llm_extraction/pool.py:229-259 [DERIVED] |
| `cloud_providers.json` `enabled` / `api_key_env` / `account_id_env` | enabled | false or an unresolved env var parks the provider (logged once, never silent) | shared/polymath_shared/llm_extraction/pool.py:169-193 [DERIVED] |
| `POLYMATH_OLLAMA_MODELS` | `""` → `OLLAMA_FREE_CLOUD_MODELS` | comma-separated names feeding the synthesizer dropdown and default pick | orchestrator/orchestrator/api/ui.py:100-103 [DERIVED] |

## failure modes

1. 422 `LIBRARY_REQUIRED` → no corpus id in the request → orchestrator/orchestrator/api/deep_research.py:136-137 [DERIVED]
2. 422 `CORPUS_NOT_ALLOWED` → principal cannot see a named corpus → orchestrator/orchestrator/web_scope.py:85-87 [DERIVED]
3. 422 `UNKNOWN_PRESET` → `DR.Config.preset` raises `ValueError` (plan and run entries) → orchestrator/orchestrator/api/deep_research.py:480-481, 396-398 [DERIVED]
4. 422 `UNKNOWN_SYNTHESIZER` → synth id not prefixed `litellm:` / `ollama:` → orchestrator/orchestrator/api/deep_research.py:393-394 [DERIVED]
5. 422 `PLAN_INVALID` → over `2 * breadth` goals, query outside 3-300 chars, move outside `DR.MOVES`, goal over `PLAN_GOAL_CHARS`, or empty plan list → orchestrator/orchestrator/api/deep_research.py:94-107 [DERIVED]
6. 503 `NO_RESEARCH_LANE` → no cloud endpoint matches the stage pins → orchestrator/orchestrator/api/deep_research.py:238-239 [DERIVED]
7. 502 `PLAN_FAILED` → `DR.plan_goals` raised; log and body carry the exception class name only, never the message → orchestrator/orchestrator/api/deep_research.py:485-488 [DERIVED]
8. 502 `PLAN_EMPTY` → planner produced no usable goals; page can still start the run → orchestrator/orchestrator/api/deep_research.py:489-490 [DERIVED]
9. `RuntimeError` "research lanes failed: ..." → every attempt (max 2) errored or returned empty text → orchestrator/orchestrator/api/deep_research.py:249-252 [DERIVED]
10. 409 `DEEP_RESEARCH_BUSY` → the principal already holds the one run slot → orchestrator/orchestrator/api/deep_research.py:402-404 [DERIVED]
11. 404 `NO_DEEP_RESEARCH_RUN` → finish posted with no live run → orchestrator/orchestrator/api/deep_research.py:505-507 [DERIVED]
12. Silent fallback: parked provider/lane absent from the roster — surfaced only by a once-log ("drop the key in .env to activate") → shared/polymath_shared/llm_extraction/pool.py:173-177, 189-193 [DERIVED]
13. Silent fallback: lane selection quietly drops to the chat compiler's lanes when no `deep_research` pin exists → orchestrator/orchestrator/api/deep_research.py:225-227 [DERIVED]
14. Silent fallback: receipt not written — warning log with `QUERY_RECEIPT_FAILED`, stream unaffected → shared/polymath_shared/query_receipts.py:215-217; orchestrator/orchestrator/api/deep_research.py:448-449 [DERIVED]
15. Silent fallback: oversized receipt meta shrunk structurally, worst case whole keys replaced by `{"truncated": true}` → shared/polymath_shared/query_receipts.py:146-175 [DERIVED]
16. Provider-family storm: attempt order forces the second attempt onto a different netloc family so one provider's 503 storm cannot eat both attempts → orchestrator/orchestrator/api/ui.py:1690-1693 [DERIVED]
17. Empty synthesizer request: defaults to the first offered preference; with nothing offered it falls to `_PREFERRED_DEFAULT` (docstring records a 2026-09-06 misrouting incident) → orchestrator/orchestrator/api/ui.py:83-92 [DERIVED]

## invariants

- INVARIANT one deep research run per principal at a time; key is `principal or "owner"` — orchestrator/orchestrator/api/deep_research.py:399-406 [DERIVED]
- INVARIANT the plan endpoint takes no run lock: a person may plan while a run streams — orchestrator/orchestrator/api/deep_research.py:475-476 [DERIVED]
- INVARIANT a failed or empty plan never blocks the run; both 502 bodies say to start without a plan — orchestrator/orchestrator/api/deep_research.py:487-490 [DERIVED]
- INVARIANT every exit path sets `cancel` and removes the caller's `_RUNNING`/`_FINISH` entries — orchestrator/orchestrator/api/deep_research.py:434-440 [DERIVED]
- INVARIANT receipt writes can never break the stream or the request — shared/polymath_shared/query_receipts.py:182-185; orchestrator/orchestrator/api/deep_research.py:448-449 [DERIVED]
- INVARIANT the receipt's `deep_research` block carries counts only, never evidence texts (64 KB meta cap) — orchestrator/orchestrator/api/deep_research.py:456-457 [DERIVED]
- INVARIANT receipt meta is shrunk structurally, never sliced into invalid JSON — shared/polymath_shared/query_receipts.py:147-150 [DERIVED]
- INVARIANT cold lanes are moved to the back of the attempt order, never dropped; if every lane is cold we still try — orchestrator/orchestrator/api/ui.py:1693-1695 [DERIVED]
- INVARIANT the cloud roster always has ≥ 1 endpoint unless the primary is explicitly parked while other providers exist — shared/polymath_shared/llm_extraction/pool.py:218-220, 225-227 [DERIVED]
- INVARIANT `_compiler_attempt_order` is pure over its inputs — orchestrator/orchestrator/api/ui.py:1695 [DERIVED]
- INVARIANT `knowledge_scope` on a receipt is read from the request only; a response can never set or widen it — shared/polymath_shared/query_receipts.py:112-114 [DERIVED]

## VERIFY

```verify
grep -Fq 'one deep research run at a time; stop the other first' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'the planner wrote no usable search; start without a plan' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'research lanes failed: ' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'X-Accel-Buffering' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS' shared/polymath_shared/llm_extraction/pool.py
grep -Eq 'home_idx = int.from_bytes\(digest, .big.\) % len\(roster\)' orchestrator/orchestrator/api/ui.py
! grep -Fq 'report_model_counts' shared/polymath_shared/query_receipts.py
test "$(grep -c -F 'HTTPException' orchestrator/orchestrator/api/deep_research.py)" -ge 8
```
