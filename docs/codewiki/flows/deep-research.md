# flow: deep-research
Deep research: plan, the research loop (moves: broad / deep / adjacent / inverse), evidence rows, the cited report, finish-now.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Plan entry: resolve libraries from `req.corpus_id` + `req.corpus_ids`, dedupe, require >= 1, then read-permission check per corpus | deep_research.py:132-139, web_scope.py:85-92 [DERIVED] | request corpus ids -> `list[str]` | 422 `LIBRARY_REQUIRED` if none; `CORPUS_NOT_ALLOWED` ("that library is not open to this account") via `require_corpus` web_scope.py:85-87 |
| 2 | Moves gate: request flag AND env not off | deep_research.py:83-84 [DERIVED] | `req.moves` + `MOVES_ENV` -> bool | moves silently off when env in `("0", "false", "off", "no")` |
| 3 | Preset to config for the plan card | deep_research.py:479-481 [DERIVED] | `req.preset` -> `DR.Config` | 422 `UNKNOWN_PRESET` on `ValueError` |
| 4 | Research lane names: `deep_research` stage pin, else the chat compiler stage pin | deep_research.py:225-227 [DERIVED] | `stage_pin` fn -> lane names | falls back to compiler lanes when no pin |
| 5 | Cloud roster: settings primary + `config/cloud_providers.json` providers + env extras; auto-gate = enabled and key resolves; key/env resolution | pool.py:217-262, 152-208, 117-133 [DERIVED] | settings + config files -> `CloudEndpoint` list | `ValueError` on malformed extras JSON, duplicate names, missing url+model; parked providers (key or account id unset) excluded but logged once |
| 6 | Empty lane set check | deep_research.py:236-239 [DERIVED] | lane names -> filtered endpoints | 503 `NO_RESEARCH_LANE` |
| 7 | `complete` port: one `LLMExtractionClient` per lane, `timeout_s=PORT_TIMEOUT_S`, `max_attempts=1`, stage `"deep_research"`, function `"DEEP_RESEARCH"` | deep_research.py:241-252 [DERIVED] | prompt/system/max_tokens -> text | `RuntimeError("research lanes failed: " + failures)` after attempts |
| 8 | Lane attempt order: home lane = blake2b(key) mod roster (or preferred lane), then first lane of a DIFFERENT provider family (netloc), then ring neighbours; cold lanes (last transport failure inside cooldown) moved to back, never dropped; capped at `max_attempts=2` | ui.py:1669-1702, 1661-1666 [DERIVED] | endpoints + key -> ordered attempt list | a same-family 503 storm cannot eat both attempts |
| 9 | Planner call in a thread | deep_research.py:484-490 [DERIVED] | question + complete + config -> `draft.goals` | 502 `PLAN_FAILED` (exception class name only, never the message); 502 `PLAN_EMPTY` if no goals |
| 10 | Plan card response: `intent`, `evaluative`, lowercased preset, goals `[{id, goal, query, move}]`, `estimate` (config with `first_width=len(draft.goals)`, `planned=True`), libraries, `config.moves`. Outside the one-run lock | deep_research.py:491-495, 473-476 [DERIVED] | draft -> plan card dict | plan failure is recoverable: page may start the run without a plan |
| 11 | Run entry: libraries (same check) + principal | deep_research.py:388-390, principal_context.py:23-25 [DERIVED] | req -> libraries, principal or None | same 422s as hop 1 |
| 12 | Synthesizer: request value or `_default_synthesizer()` (first offered preference among litellm + ollama models; providers with unset env keys skipped); must start with `"litellm:"` or `"ollama:"` | deep_research.py:391-394, ui.py:83-92, 575-579, 582-602, 117-138 [DERIVED] | `req.synthesizer` -> synth id | 422 `UNKNOWN_SYNTHESIZER`; default never routes to a hidden provider |
| 13 | Run preset + confirmed-plan validation: plan optional; at most `2 * breadth` goals, query length window (`PLAN_QUERY_CHARS`, docstring says 3-300), move in `DR.MOVES`, goal <= `PLAN_GOAL_CHARS`; repeated queries allowed | deep_research.py:87-108, 395-399 [DERIVED] | `req.plan` + breadth -> `(goal, query, move)` tuples or None | one 422 `PLAN_INVALID` listing every problem, `"; "`-joined |
| 14 | One-run lock keyed by `who = principal or "owner"` | deep_research.py:400-406 [DERIVED] | who -> `cancel`/`finish` events registered in `_RUNNING`/`_FINISH` | 409 `DEEP_RESEARCH_BUSY` "one deep research run at a time; stop the other first" |
| 15 | SSE start + worker launch: phase event `{stage: "deep_start", label, t: 0, preset}`; daemon thread `deep-research` running `_worker(req, libraries, synth, principal, loop, out, cancel, finish, plan)` | deep_research.py:408-419 [DERIVED] | plan+req -> worker thread + queue | worker internals (loop, moves, evidence rows, report) not in this material |
| 16 | SSE pump: `out.get` with `HEARTBEAT_S` timeout; `_END` sentinel breaks; `answer`/`error` events captured; final `done` event; `_sse` frames as `event: <kind>\ndata: <json>` | deep_research.py:420-433, 111-112 [DERIVED] | queue -> SSE stream | `": keep-alive\n\n"` comment on empty queue timeout |
| 17 | Exit cleanup: `cancel.set()` (a disconnect or any exit stops the run); `_RUNNING`/`_FINISH` entries removed under `_LOCK` | deep_research.py:434-440 [DERIVED] | cancel/finish events | run stops on client disconnect |
| 18 | Receipt block: reads `answer.result.meta.deep_research`; replaces `report_model` with `report_model_counts` (goals, findings, confidence tallies over `strong`/`single_source`/`contested`, counter, open_questions, sources) because receipt meta caps at 64 KB | deep_research.py:455-468 [DERIVED] | answer -> counts-only block | evidence texts dropped from the receipt |
| 19 | Receipt write: `record_query_receipt(kind="deep_research", scope_kind="explicit", wall_ms, out={"meta": meta}, error=failure)` with `meta = {"route": "research/deep", "model": synth, "deep_research": ...}` | deep_research.py:441-449, query_receipts.py:178-218 [DERIVED] | meta -> `query_receipts` row (`q_` + uuid hex[:24]) | swallowed: warning "deep research receipt not written", returns None |
| 20 | Receipt internals: `summarize_response` allowlists meta keys (incl. `deep_research`, `route`, `model`); `knowledge_scope_of` reads `req.scope` only, malformed -> `{"invalid": true}`; `principal_id` backfilled (migration 0066) | query_receipts.py:32-107, 110-120, code/scope.py:99-111, 211-213 [DERIVED] | response -> summary columns | all failures logged, never raised |
| 21 | Meta shrink (`_meta_json`): funnel compact -> shrink long lists -> drop keys in `DROP_ORDER` -> last resort `{"truncated": true, keys}`; never slices a JSON string | query_receipts.py:146-175, funnel.py:111-127, 135-143 [DERIVED] | meta -> JSON within cap | over-cap metas shrink structurally, not invalidly |
| 22 | Stream returned: `text/event-stream`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | deep_research.py:451-452 [DERIVED] | events() -> StreamingResponse | — |
| 23 | Finish-now: looks up `_FINISH[who]` under `_LOCK`; sets it; worker writes the report with stop reason `finished_early` | deep_research.py:499-509 [DERIVED] | `{}` -> `{"finishing": true}` | 404 `NO_DEEP_RESEARCH_RUN` when the caller has no run |

## state written

| state | what | anchor |
|---|---|---|
| Postgres `query_receipts` | one row per run: kind `"deep_research"`, corpus ids, scope `"explicit"`, `question_sha256` + `question_head`, `wall_ms`, status, meta JSON (`route`, `model`, `deep_research` counts), error | query_receipts.py:199-210 [DERIVED] |
| Postgres `query_receipts.principal_id` | backfilled by UPDATE when a principal is set | query_receipts.py:211-213 [DERIVED] |
| `llm_providers` table | `CREATE TABLE IF NOT EXISTS` runs on read (side effect of listing synthesizers) | ui.py:544-551 [DERIVED] |
| in-proc `_RUNNING[who]`, `_FINISH[who]` | cancel/finish events per principal, under `_LOCK`; removed on any stream exit | deep_research.py:402-406, 436-440 [DERIVED] |
| `_COMPILER_LANE_FAILED_AT` | last-failure map read for lane cooldown (write site not in this material) | ui.py:1698-1700 [DERIVED] |
| `_ROSTER_LOGGED` | once-only roster/parked log set | pool.py:211-214 [DERIVED] |
| Qdrant / files | no writes on this path appear in the material | [INFERRED] none present in SOURCE |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| env `MOVES_ENV` | `"1"` | any of `"0"`, `"false"`, `"off"`, `"no"` turns moves off in the plan config | deep_research.py:84 |
| `req.moves` | not shown | request half of the moves gate | deep_research.py:83-84 |
| `req.preset` | not shown | selects `DR.Config.preset`; unknown -> 422 | deep_research.py:479-481, 395-398 |
| `req.synthesizer` | `_default_synthesizer()` | must be `litellm:`/`ollama:` prefixed | deep_research.py:391-394 |
| `req.plan` | None | confirmed plan validated at run start; None = planner plans alone | deep_research.py:87-108, 399 |
| env `POLYMATH_LLM_CLOUD_PRIMARY` | unset (true) | `"0"` parks the settings primary while other providers exist | pool.py:226 |
| env `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | empty | JSON list of `{name, url, model}` appended to the roster; malformed JSON raises loudly | pool.py:229-255 |
| `config/cloud_providers.json` `enabled` | not false | provider joins only if enabled AND its key resolves | pool.py:168-177 |
| `config/llm_accounts.yaml` stage pin `deep_research` | fallback to compiler stage | chooses the research lanes | deep_research.py:225-227 |
| env `POLYMATH_OLLAMA_MODELS` | `OLLAMA_FREE_CLOUD_MODELS` | comma list overriding the ollama allowlist | ui.py:100-103 |

## failure modes

1. 422 `LIBRARY_REQUIRED` — no corpus named in the request -> deduped id list empty -> deep_research.py:136-137.
2. 422 `CORPUS_NOT_ALLOWED` — friend lacks read on a named library -> `can_see` false in `require_corpus` -> web_scope.py:85-87.
3. 422 `UNKNOWN_PRESET` — `DR.Config.preset` raised `ValueError` -> deep_research.py:479-481 (plan), 395-398 (run).
4. 503 `NO_RESEARCH_LANE` — no model lane matches the stage pins -> deep_research.py:236-239; typical cause: providers parked for unset keys or account ids (pool.py:173-177, 189-193) — logged once, never silent.
5. 502 `PLAN_FAILED` — planner exception; log and message carry the class name only, never the message -> deep_research.py:484-488. Under it: `RuntimeError("research lanes failed: ...")` after both lane attempts -> deep_research.py:243-252.
6. 502 `PLAN_EMPTY` — planner returned no usable goals -> deep_research.py:489-490; page can still start the run.
7. 422 `UNKNOWN_SYNTHESIZER` — synth id not `litellm:`/`ollama:` prefixed -> deep_research.py:392-394.
8. 422 `PLAN_INVALID` — confirmed plan violates goal count (`2 * breadth`), query length, move membership, or goal length; every problem listed in one message -> deep_research.py:94-107.
9. 409 `DEEP_RESEARCH_BUSY` — same principal already has a run -> deep_research.py:402-404.
10. 404 `NO_DEEP_RESEARCH_RUN` — finish posted with no live run for the caller -> deep_research.py:505-507.
11. Loud roster failure — malformed `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` or `cloud_providers.json` raises `ValueError` (a silently-dropped provider would look like a half-speed pool) -> pool.py:232-235, 196-198.
12. Silent fallbacks on this path: cold lanes moved to the back of the attempt order, never dropped -> ui.py:1700-1701; parked providers excluded from the roster with a once-log -> pool.py:173-177; receipt write failure swallowed with a warning -> deep_research.py:448-449, query_receipts.py:215-217; keep-alive comment on queue timeout -> deep_research.py:424-425; over-cap receipt meta shrunk structurally instead of dropped -> query_receipts.py:146-175.

## invariants

- INVARIANT: at most one deep research run per principal (`who = principal or "owner"`) under `_LOCK` — deep_research.py:402-406.
- INVARIANT: planning is outside the one-run lock; a person may plan while a run streams — deep_research.py:473-476.
- INVARIANT: any stream exit, including a client disconnect, sets `cancel` and removes the run's registry entries — deep_research.py:434-440.
- INVARIANT: a receipt failure never breaks the stream or the query — deep_research.py:448-449, query_receipts.py:182-184.
- INVARIANT: planner failures expose the exception class only, never the message — deep_research.py:485-488.
- INVARIANT: the second lane attempt is a different provider family (netloc), so one provider's 503 storm cannot eat both attempts — ui.py:1672-1675, 1661-1666.
- INVARIANT: a request naming no synthesizer is never routed to a hidden (unready) provider — ui.py:84-88, 575-579.
- INVARIANT: knowledge scope is read from the request only; a response can never set or widen it; malformed scope records `{"invalid": true}` (fail closed) — query_receipts.py:111-114, code/scope.py:100-101.
- INVARIANT: the receipt's `deep_research` block carries counts only, never evidence texts (64 KB meta cap) — deep_research.py:456-457.
- INVARIANT: roster composition changes are surfaced by a once-log, never silent — pool.py:153-156, 211-214.
- INVARIANT: receipt meta is shrunk structurally and never sliced into invalid JSON — query_receipts.py:147-150.

## VERIFY

```verify
grep -Fq 'one deep research run at a time; stop the other first' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'research lanes failed: ' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'or stage_pin_fn(compiler_stage)' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'INSERT INTO query_receipts' shared/polymath_shared/query_receipts.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS is not valid JSON' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'X-Accel-Buffering' orchestrator/orchestrator/api/deep_research.py
test "$(grep -c -F 'HTTPException' orchestrator/orchestrator/api/deep_research.py)" -ge 10
```
