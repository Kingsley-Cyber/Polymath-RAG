# flow: deep-research
Deep research: plan, the research loop (moves: broad / deep / adjacent / inverse), evidence rows, the cited report, finish-now.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Plan entry: `POST /research/deep/plan` -> `deep_research_plan`; the level-1 plan card, ONE planner call, after the same library and preset checks as a run; **not** part of the one-run lock — a person may plan while a run streams | orchestrator/orchestrator/api/deep_research.py:490-494 [DERIVED] | `DeepPlanRequest` -> plan-card dict | see rows 2-11 |
| 2 | Library scope: `_libraries` merges `[corpus_id]` + `corpus_ids`, dedupes order-preserving | deep_research.py:132-139 [DERIVED] | req -> `list[str]` corpus ids | empty -> 422 `LIBRARY_REQUIRED` (137) |
| 3 | Read permission: `require_corpora` -> `require_corpus` -> `can_see` | orchestrator/orchestrator/web_scope.py:103-110 [DERIVED] | corpus ids -> None | `_refuse("CORPUS_NOT_ALLOWED", "that library is not open to this account")` (104-105) |
| 4 | Moves gate: `moves_enabled` = `req.moves` AND env `MOVES_ENV` (default `"1"`) not in `("0", "false", "off", "no")` | deep_research.py:83-84 [DERIVED] | req + env -> bool | env set to an off-value disables moves |
| 5 | Preset: `DR.Config.preset(req.preset, moves=moves_enabled(req))` | deep_research.py:497-499 [DERIVED] | preset name -> `DR.Config` | `ValueError` -> 422 `UNKNOWN_PRESET` (499) |
| 6 | Planner port: `_complete_port` closes over `complete()`; lanes = `research_lane_names` = `stage_pin("deep_research")` or `stage_pin(COMPILER_STAGE)` (config/llm_accounts.yaml, else the chat compiler's lanes) | deep_research.py:234-247, 225-227 [DERIVED] | question key -> `complete(prompt, system, max_tokens)` | no endpoint matches the pin -> 503 `NO_RESEARCH_LANE` (246-247) |
| 7 | Roster: `cloud_endpoints` = settings primary (parkable) + `config/cloud_providers.json` via `_configured_providers` (AUTO-GATE: `enabled` not false AND key resolves; `url_template`+`account_id_env` supported) + `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`; sorted by name; keys via `_resolve_key` (process env, then repo `.env`) | shared/polymath_shared/llm_extraction/pool.py:217-262, 152-208, 117-133 [DERIVED] | settings + files -> `CloudEndpoint` list | loud `ValueError`: bad extras JSON (234-235), non-list (237-238), missing name+url+model (244-245), duplicate names (258-259); keyless provider parked, logged once (172-176) |
| 8 | Lane order: `_compiler_attempt_order` — home lane = `blake2b(key)` mod roster length (or `_COMPILER_PREFERRED_LANE`), then first lane of a different family (`_lane_family` = urlparse netloc), then ring neighbours; lanes whose last transport failure is inside `_COMPILER_LANE_COOLDOWN_S` move to the back, never dropped; capped at `max_attempts` | orchestrator/orchestrator/api/ui.py:1741-1774, 1733-1738 [DERIVED] | endpoints + key -> attempt list | every lane cold -> still tried, just reordered (1772-1773) |
| 9 | Lane call loop: `complete()` — per lane an `LLMExtractionClient("cloud", ..., timeout_s=PORT_TIMEOUT_S, max_attempts=1)`, `attempt_stage="deep_research"`, `attempt_function="DEEP_RESEARCH"`, `interactive=True` (never wait on a limiter); a limiter refusal (`last_refusal`) skips the lane at zero HTTP | deep_research.py:249-266 [DERIVED] | prompt/system/max_tokens -> text | `len(failures) >= RESEARCH_DISPATCH_ATTEMPTS` stops the loop (252); skipped-only -> `AllLanesRefused(skipped)` (267-268); else `RuntimeError("research lanes failed: " + ...)` (269-270) |
| 10 | Planner: `DR.plan_goals` off-thread via `asyncio.to_thread` | deep_research.py:500-508 [DERIVED] | question + complete + config -> `draft.goals` | any exception -> 502 `PLAN_FAILED`, logged as `type(exc).__name__` only, never the message (503-506); `not draft.goals` -> 502 `PLAN_EMPTY` (507-508) |
| 11 | Plan card returned: `intent`, `evaluative`, `preset`, `goals` [{id, goal, query, move}], `estimate(replace(config, first_width=len(draft.goals)), planned=True)`, `libraries`, `moves` | deep_research.py:509-513 [DERIVED] | draft -> JSON | — |
| 12 | Run entry: `POST /research/deep` -> `deep_research`; `_libraries` again; principal from `principal_context.current()` (None = legacy / trusted-local caller) | deep_research.py:406-409; shared/polymath_shared/principal_context.py:23-25 [DERIVED] | `DeepResearchRequest` + principal -> run | rows 2-3 repeat |
| 13 | Synthesizer: `req.synthesizer` or `_default_synthesizer()` — first `_PREFERRED_DEFAULTS` entry present in offered (`_litellm_models` from `llm_providers` rows with `_provider_ready` hiding unresolvable `env:` keys, plus `_ollama_models` from `POLYMATH_OLLAMA_MODELS`/`OLLAMA_FREE_CLOUD_MODELS` with daemon `/api/tags` check, 3 s), else `offered[0]`, else `_PREFERRED_DEFAULT` | deep_research.py:410-412; ui.py:83-92, 648-668, 641-645, 606-624, 117-138, 106-114, 100-103 [DERIVED] | req -> synth id | not `startswith(("litellm:", "ollama:"))` -> 422 `UNKNOWN_SYNTHESIZER` (421-422) |
| 14 | Run preset + confirmed plan: `DR.Config.preset(req.preset)`; `confirmed_plan` — plan None allowed, else at most `2 * breadth` goals, query length inside `PLAN_QUERY_CHARS` (3-300 per docstring), move in `DR.MOVES`, goal <= `PLAN_GOAL_CHARS`; repeated query allowed | deep_research.py:413-417, 87-108 [DERIVED] | `req.plan` + `shape.breadth` -> `(goal, query, move)` tuples or None | any problem -> 422 `PLAN_INVALID` listing every problem (106-107) |
| 15 | One-run lock: `who = principal or "owner"`; under `_LOCK`, register `cancel`/`finish` Events in `_RUNNING`/`_FINISH` | deep_research.py:418-424 [DERIVED] | principal -> slots | `who in _RUNNING` -> 409 `DEEP_RESEARCH_BUSY` "one deep research run at a time; stop the other first" (420-423) |
| 16 | SSE stream: daemon thread `_worker` (name `"deep-research"`) posts to a queue; `events()` opens with a `phase` frame `{"stage": "deep_start", ...}`, relays `_sse` frames, waits `HEARTBEAT_S` -> `": keep-alive\n\n"` on empty, captures `answer` and failure `error_code`, ends with a `done` frame; `StreamingResponse(media_type="text/event-stream")` | deep_research.py:426-451, 111-112, 469-470 [DERIVED] | queue items -> event stream | heartbeat is only a comment frame; `error` events set `failure` (448-449) |
| 17 | Teardown: `finally` — `cancel.set()` (a disconnect or any exit stops the run), `_RUNNING`/`_FINISH` entries removed when identity matches | deep_research.py:452-458 [DERIVED] | — | — |
| 18 | Run receipt: `record_query_receipt(kind="deep_research", ...)` with `meta = {"route": "research/deep", "model": synth, "deep_research": receipt_block(answer)}`; `receipt_block` keeps the run counts and swaps `report_model` for `report_model_counts` (goals, findings, confidence strong/single_source/contested, counter, open_questions, sources) — the evidence model's texts stay out (receipt meta cap 64 KB); a block without `report_model` passes through unchanged | deep_research.py:459-467, 473-486 [DERIVED] | answer -> receipt row | receipt failure only warned: "deep research receipt not written: %s" (466-467) |
| 19 | Receipt row: `qid = "q_" + uuid.uuid4().hex[:24]`; `summarize_response` whitelists meta keys; `knowledge_scope_of` reads `req.scope` via `parse_scope` (anything not exactly `{"roles": [...]}` raises `ScopeError`; malformed recorded as `{"invalid": true}`); INSERT INTO `query_receipts` (…, meta jsonb, error); `principal_id` backfilled when set (migration 0066) | shared/polymath_shared/query_receipts.py:181-221, 32-110, 113-123; shared/polymath_shared/code/scope.py:99-111 [DERIVED] | summary -> Postgres row | any exception -> returns None + warning `QUERY_RECEIPT_FAILED` (218-220) |
| 20 | Meta sizing: `_meta_json` shrinks structurally — `funnel.compact`, then list shrinks (`SHRINK_LISTS_IN`), then `DROP_ORDER` keys (funnel id lists go, counts stay) — never slices a JSON string; last resort `{"truncated": True, "keys": ...}` | query_receipts.py:149-178; shared/polymath_shared/funnel.py:111-127 [DERIVED] | meta -> JSON text | oversized meta is truncated, never invalid JSON |
| 21 | Finish entry: `POST /research/deep/finish` -> `deep_research_finish` declared at deep_research.py:517; the run's `finish` Event is registered in `_FINISH[who]` (424) and cleared on exit (457-458). Body not in this material | deep_research.py:517, 424, 457-458 [INFERRED — the :517 anchor comes from the route table; only the Event plumbing is in SOURCE] | — | — |

## state written

- Postgres `query_receipts`: one row per run (`kind="deep_research"`, `question_sha256`, `wall_ms`, `meta` jsonb incl. `deep_research` counts, `error`) — query_receipts.py:202-213; `principal_id` update — query_receipts.py:214-216.
- Postgres `llm_providers`: `CREATE TABLE IF NOT EXISTS` on read; source of the synthesizer dropdown — ui.py:610-617.
- In-memory `_RUNNING[who] = cancel` and `_FINISH[who] = finish`, per principal, removed on stream exit — deep_research.py:420-424, 454-458.
- Files read only: `config/cloud_providers.json` — pool.py:158; repo `.env` (gitignored) — pool.py:125.
- The plan endpoint (`/research/deep/plan`) writes nothing — no receipt call in deep_research.py:490-513 [DERIVED].
- No Qdrant collection appears on this path in SOURCE.

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `req.moves` | not shown in SOURCE | with the env gate, sets `moves=` on the preset | deep_research.py:83-84, 497 |
| `MOVES_ENV` (constant; literal env name not in SOURCE) | `"1"` | `"0"`, `"false"`, `"off"`, `"no"` disable moves | deep_research.py:84 |
| `POLYMATH_LLM_CLOUD_PRIMARY` | `llm_cloud_primary` getattr default `True` | parks the primary endpoint unless no configured providers remain (roster never empty) | pool.py:226 |
| `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | `""` / unset | adds extra endpoints (JSON list of `{name,url,model}`); malformed fails loudly | pool.py:229-245 |
| `POLYMATH_OLLAMA_MODELS` | `OLLAMA_FREE_CLOUD_MODELS` | ollama name allowlist behind the default synthesizer | ui.py:100-103 |
| `_COMPILER_PREFERRED_LANE` | not shown in SOURCE | overrides the hash home lane for every session | ui.py:1754-1757 |
| `_COMPILER_LANE_COOLDOWN_S` | not shown in SOURCE | lanes failing inside the cooldown are demoted to the back | ui.py:1742, 1772 |
| `req.preset` | — | selects the `DR.Config` shape (`breadth` etc.); unknown -> 422 | deep_research.py:497-499, 413-416 |
| `req.synthesizer` | `_default_synthesizer()` | must start with `"litellm:"` or `"ollama:"` | deep_research.py:410-412 |
| `req.plan` | `None` | `None` = no confirmed plan; else validated against `2 * breadth` | deep_research.py:87-108 |

## failure modes

1. 502 `PLAN_FAILED` -> any planner exception -> only `type(exc).__name__` logged, never the message; the page can still start the run without a plan -> deep_research.py:503-506, 493-494.
2. 502 `PLAN_EMPTY` -> planner wrote no usable search -> deep_research.py:507-508.
3. 503 `NO_RESEARCH_LANE` -> the `deep_research` stage pin (else `COMPILER_STAGE`) names no configured endpoint -> deep_research.py:246-247, 225-227; check the pin in config/llm_accounts.yaml (docstring at 226).
4. `AllLanesRefused` -> every lane's limiter refused at zero HTTP (breaker open, Retry-After hold, saturated); the engine counts it and ends that branch instead of waiting out a cooldown -> deep_research.py:237-239, 267-268.
5. `RuntimeError("research lanes failed: ...")` -> mixed failures/skips once `RESEARCH_DISPATCH_ATTEMPTS` is reached -> deep_research.py:252, 269-270.
6. 422 `UNKNOWN_PRESET` -> `ValueError` from `DR.Config.preset` -> deep_research.py:497-499 (plan), 413-416 (run).
7. 422 `PLAN_INVALID` -> plan over `2 * breadth` goals, query outside `PLAN_QUERY_CHARS`, move outside `DR.MOVES`, goal over `PLAN_GOAL_CHARS`, or an empty plan; every problem listed at once -> deep_research.py:94-107.
8. 422 `UNKNOWN_SYNTHESIZER` -> synth id without a `litellm:`/`ollama:` prefix -> deep_research.py:421-422.
9. 409 `DEEP_RESEARCH_BUSY` -> same principal already has a run registered -> deep_research.py:420-423.
10. 422 `LIBRARY_REQUIRED` / `CORPUS_NOT_ALLOWED` -> no corpus named / `can_see` false -> deep_research.py:137; web_scope.py:104-105.
11. Silent: run receipt lost -> any receipt-layer exception is swallowed and warned (`QUERY_RECEIPT_FAILED`) -> deep_research.py:466-467; query_receipts.py:218-220.
12. Silent: provider parked (key or Cloudflare `account_id_env` unset) -> absent from the roster, logged once; a silently-dropped provider looks like a half-speed pool -> pool.py:172-176, 189-193, 218-220.
13. Silent: empty synthesizer historically fell to a keyless provider (measured 2026-09-06: `litellm:openai/glm-5-free` -> LiteLLM "Missing credentials"); `_default_synthesizer` now only offers ready providers -> ui.py:84-87.
14. Oversized receipt meta -> structural shrink, worst case `{"truncated": True}`; the old `json.dumps(meta)[:8000]` slice produced invalid JSON and silently dropped the receipt -> query_receipts.py:150-153, 178.

## invariants

- INVARIANT one deep-research run per principal (`_RUNNING`, 409 `DEEP_RESEARCH_BUSY`); the plan endpoint is outside the lock — deep_research.py:420-423, 492-493.
- INVARIANT any exit from the run stream — disconnect included — sets `cancel` and unregisters the run — deep_research.py:452-458.
- INVARIANT a receipt failure can never fail the request, at either layer — deep_research.py:466-467; query_receipts.py:185-187, 218-220.
- INVARIANT receipt meta is shrunk structurally and never text-sliced; the funnel's counts outlive its ids — query_receipts.py:150-153, 171-173.
- INVARIANT the receipt's `deep_research` block carries counts, never the evidence model's texts (64 KB meta cap) — deep_research.py:474-475, 481-486.
- INVARIANT planner failures log the exception class only, never the message — deep_research.py:503-504.
- INVARIANT interactive lanes never wait on a limiter; a refusal is a zero-HTTP skip to the next lane — deep_research.py:258, 262-265.
- INVARIANT lane attempt order is a pure function of its inputs; cold lanes are demoted, never dropped — ui.py:1744, 1747-1749.
- INVARIANT a malformed knowledge scope fails closed, never read as both roles — scope.py:100-101.
- INVARIANT a friend may only research libraries they can read — deep_research.py:138.

## VERIFY

```verify
grep -Fq 'one deep research run at a time; stop the other first' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'raise AllLanesRefused(skipped)' orchestrator/orchestrator/api/deep_research.py
grep -Fq ': keep-alive' orchestrator/orchestrator/api/deep_research.py
grep -Fq '"0", "false", "off", "no"' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS is not valid JSON' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'CREATE TABLE IF NOT EXISTS llm_providers' orchestrator/orchestrator/api/ui.py
test "$(grep -c -F 'LIBRARY_REQUIRED' orchestrator/orchestrator/api/deep_research.py)" -ge 1
```
