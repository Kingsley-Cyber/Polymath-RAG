# flow: deep-research
Deep research: plan, the research loop (moves: broad / deep / adjacent / inverse), evidence rows, the cited report, finish-now.

Entries (web class: user): `POST /research/deep/plan` → `deep_research_plan` (orchestrator/orchestrator/api/deep_research.py:490), `POST /research/deep` → `deep_research` (deep_research.py:406), `POST /research/deep/finish` → `deep_research_finish` (deep_research.py:517).

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Plan card entry. DR7a (§11.3): level-1 plan made alone, ONE planner call, outside the one-run lock (a person may plan while a run streams) | deep_research.py:490-494 [DERIVED] | DeepPlanRequest -> plan card dict | none at this line |
| 2 | `_libraries`: merge `corpus_id` + `corpus_ids`, dedupe via `dict.fromkeys`, then `require_corpora` → `require_corpus` → `can_see` ("a friend may only research libraries they can read") | deep_research.py:132-139; web_scope.py:103-110 [DERIVED] | corpus ids -> `list[str]` | 422 `LIBRARY_REQUIRED`; 422 `CORPUS_NOT_ALLOWED` |
| 3 | `moves_enabled`: request `moves` AND env `MOVES_ENV` (default `"1"`) not one of `"0"`, `"false"`, `"off"`, `"no"` | deep_research.py:83-84 [DERIVED] | req.moves + env -> bool | moves silently off when either is false |
| 4 | `DR.Config.preset(req.preset, moves=...)` for the plan config | deep_research.py:497-499 [DERIVED] | preset name -> Config | ValueError → 422 `UNKNOWN_PRESET` |
| 5 | `research_lane_names`: stage pin `"deep_research"`, else the chat compiler's stage (DR0); pins live in config/llm_accounts.yaml | deep_research.py:225-227 [DERIVED] | stage pins -> lane names | silent fallback to compiler lanes when the pin is unset |
| 6 | `cloud_endpoints` builds the roster: settings primary (parks only when `POLYMATH_LLM_CLOUD_PRIMARY=0` and other providers exist), providers from config/cloud_providers.json (AUTO-GATE: enabled AND key resolves; Cloudflare `url_template`+`account_id_env`), extras from `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`; sorted by name; duplicate names rejected; composition logged once | pool.py:217-262, 152-208, 117-133 [DERIVED] | settings + config files -> `CloudEndpoint` list | loud `ValueError` on malformed JSON, missing name+url+model, reserved/duplicate `"primary"` |
| 7 | `_complete_port`: keep endpoints whose name is in the lane names; builds the `complete` closure; INTERACTIVE-ADMISSION-V1 rules | deep_research.py:234-249 [DERIVED] | key + endpoints -> `complete(prompt, system, max_tokens)` | 503 `NO_RESEARCH_LANE` when no endpoint matches |
| 8 | `complete` asks `_compiler_attempt_order`: home lane = blake2b hash of the key (or `_COMPILER_PREFERRED_LANE`), then the first lane of a DIFFERENT family (`_lane_family` = URL netloc), then ring neighbours; lanes cold within `_COMPILER_LANE_COOLDOWN_S` move to the back, never dropped | deep_research.py:251; ui.py:1742-1775, 1734-1739 [DERIVED] | endpoints + key -> ordered attempt list | single-family roster: `alt` is None, no different-family second hop |
| 9 | Per lane: `LLMExtractionClient("cloud", ..., timeout_s=PORT_TIMEOUT_S, max_attempts=1)`, `attempt_stage="deep_research"`, `attempt_function="DEEP_RESEARCH"`, `interactive=True` (never waits on a limiter); non-empty text wins; a limiter refusal (`last_refusal`, zero HTTP) skips the lane without spending an attempt; other errors count toward `RESEARCH_DISPATCH_ATTEMPTS` | deep_research.py:252-266 [DERIVED] | prompt/system/max_tokens -> text | all refused → typed `AllLanesRefused`; failures → `RuntimeError("research lanes failed: ...")` |
| 10 | `DR.plan_goals` on `asyncio.to_thread` — the one planner call | deep_research.py:502 [DERIVED] | question + complete + config -> draft goals | exception → 502 `PLAN_FAILED` (exception class name only, never the message); no goals → 502 `PLAN_EMPTY` |
| 11 | Plan card returned: `intent` (`DR.question_intent`), `evaluative` (`DR.is_evaluative`), preset, goals `[{id, goal, query, move}]`, `estimate` (`DR.estimate`, `first_width=len(goals)`, `planned=True`), libraries, moves | deep_research.py:509-513 [DERIVED] | draft -> JSON card | — |
| 12 | Run entry `deep_research`: same `_libraries` gate; principal from `principal_context.current()` (None = legacy / trusted-local) | deep_research.py:406-408; principal_context.py:23-25 [DERIVED] | DeepResearchRequest -> SSE stream | same 422s as hop 2 |
| 13 | Synthesizer: `req.synthesizer` or `_default_synthesizer()`; must start with `"litellm:"` or `"ollama:"` | deep_research.py:409-412 [DERIVED] | model id | 422 `UNKNOWN_SYNTHESIZER` |
| 14 | `_default_synthesizer`: first `_PREFERRED_DEFAULTS` id that is offered; offered = `_litellm_models` (llm_providers rows, env-indirected unset keys hidden by `_provider_ready`) + `_ollama_models` (allowlist `POLYMATH_OLLAMA_MODELS` else `OLLAMA_FREE_CLOUD_MODELS`; daemon `{OLLAMA_URL}/api/tags`, 3 s, non-fatal); else first offered, else `_PREFERRED_DEFAULT` | ui.py:84-93, 649-669, 607-646, 101-139 [DERIVED] | provider rows + daemon -> model id | silent default to first offered (measured 2026-09-06: empty synthesizer fell to `litellm:openai/glm-5-free` with the OpenCode key unset) |
| 15 | `DR.Config.preset(req.preset)` for the run shape; `shape.breadth` feeds the plan check | deep_research.py:413-416 [DERIVED] | preset -> shape | 422 `UNKNOWN_PRESET` |
| 16 | `confirmed_plan`: None passes; else at most `2 * breadth` goals, each query `3-300` characters (`PLAN_QUERY_CHARS`), each move in `DR.MOVES`, goal at most `PLAN_GOAL_CHARS`; every problem listed in one 422; a repeated query is allowed (every confirmed goal is searched) | deep_research.py:87-108 [DERIVED] | req.plan -> `(goal, query, move)` tuples or None | 422 `PLAN_INVALID`, including `"the plan has no goals"` |
| 17 | One-run lock: `who = principal or "owner"`; under `_LOCK`, register `cancel`/`finish` Events in `_RUNNING`/`_FINISH` | deep_research.py:418-424 [DERIVED] | who -> Events | 409 `DEEP_RESEARCH_BUSY` ("one deep research run at a time; stop the other first") |
| 18 | Stream opens: `_sse("phase", {"stage": "deep_start", ...})`; daemon thread named `"deep-research"` runs `_worker` with `(req, libraries, synth, principal, loop, out, cancel, finish, plan)` — the moves loop, evidence rows and report are inside `_worker` / the DR engine, not shown in SOURCE | deep_research.py:426-437 [DERIVED] | confirmed plan -> worker thread | — |
| 19 | Event pump: `out.get` with `HEARTBEAT_S` timeout; on Empty yield `": keep-alive\n\n"`; `_END` breaks; `"answer"` and `"error"` captured for the receipt; every kind re-emitted as `_sse` frame (`event: <kind>` + JSON data) | deep_research.py:438-451, 111-112 [DERIVED] | queue items -> SSE frames | no data → only keep-alive comments |
| 20 | Any exit: `cancel.set()` stops the run (a disconnect stops it); `_RUNNING`/`_FINISH` entries removed under `_LOCK` | deep_research.py:452-458 [DERIVED] | — | run is lost on client disconnect |
| 21 | `receipt_block`: keeps the answer meta's `deep_research` audit but replaces `report_model` texts with `report_model_counts` (goals, findings, confidence `strong`/`single_source`/`contested`, counter, open_questions, sources) — receipt meta is capped at 64 KB and past the cap the whole meta is lost | deep_research.py:462-465, 473-486 [DERIVED] | answer -> meta block | oversized meta loses everything |
| 22 | `record_query_receipt`: `summarize_response` (meta whitelist includes `"deep_research"`), `knowledge_scope_of` reads the request's `scope` only (malformed → `{"invalid": true}`), INSERT into `query_receipts` (`qid = "q_" + uuid hex[:24]`, question sha256/head, corpus ids, `scope_kind="explicit"`, wall_ms, meta jsonb, error); `principal_id` backfilled when set (migration 0066; `client` stays the software identity) | query_receipts.py:184-224, 32-113, 116-126; deep_research.py:462-465 [DERIVED] | stream outcome -> receipt row | any exception logs `QUERY_RECEIPT_FAILED` and returns None; the stream is unaffected |
| 23 | `_meta_json` (JSON-SAFE-META-V1): shrink structurally — `funnel.compact` (drop per-stage ids, keep counts), then long lists, then whole keys in `DROP_ORDER`; never slice a JSON string | query_receipts.py:152-181; funnel.py:111-127 [DERIVED] | meta -> jsonb string | worst case `{"truncated": true, "keys": ...}` |
| 24 | Response: `StreamingResponse(media_type="text/event-stream")`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` | deep_research.py:469-470 [DERIVED] | — | — |
| 25 | `POST /research/deep/finish` → `deep_research_finish`; its body is not in SOURCE; the live run it targets holds a per-principal `finish` Event in `_FINISH` | deep_research.py:517 [INFERIVED→INFERRED: entry line given as FACT, body absent; the tie to `_FINISH` (deep_research.py:419-424) is name-based] | finish signal | — |

## state written

- Postgres `query_receipts`: one row per deep-research stream, `kind="deep_research"`; columns `query_id, kind, received_at, client, corpus_ids, scope, mode, latent, question_sha256, question_head, wall_ms, status, verdict, citations, claims, evidence, source_docs, meta (jsonb), error`; `principal_id` set when a principal is in context (migration 0066) — query_receipts.py:204-219 [DERIVED]; meta = `{route: "research/deep", model: synth, deep_research: counts}` — deep_research.py:462-465 [DERIVED]
- Postgres `llm_providers`: created on read (`CREATE TABLE IF NOT EXISTS`; `provider_id` PK, `provider`, `api_key`, `api_base`, `models jsonb`, `enabled`, `created_at`) — ui.py:607-625 [DERIVED]
- Process memory (lost on restart): `_RUNNING` / `_FINISH` maps under `_LOCK` — deep_research.py:420-424, 454-458 [DERIVED]; `_COMPILER_LANE_FAILED_AT` cooldown map read by `_compiler_attempt_order` — ui.py:1771-1773 [DERIVED]; `_ROSTER_LOGGED` once-log set — pool.py:211-214 [DERIVED]
- Files read, never written here: config/cloud_providers.json — pool.py:157 [DERIVED]; repo `.env` (gitignored) via `_resolve_key` — pool.py:117-133 [DERIVED]; stage pins in config/llm_accounts.yaml — deep_research.py:226 [DERIVED]
- No Qdrant collection or file write appears on this path in SOURCE.

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `MOVES_ENV` env var (name held in the `MOVES_ENV` constant) | `"1"` | `"0"`, `"false"`, `"off"`, `"no"` disable moves in the plan config | deep_research.py:83-84 |
| `moves` request field | falsy | must be truthy AND env on for moves | deep_research.py:83-84 |
| `POLYMATH_LLM_CLOUD_PRIMARY` | `True` | `"0"` parks the settings primary while other providers exist; roster never goes empty | pool.py:226-227 |
| `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` | `""` | JSON list of `{name, url, model, ...}` adds lanes; malformed JSON raises loudly | pool.py:229-248 |
| provider `enabled: false`, unresolved `api_key_env`, unset `account_id_env` in config/cloud_providers.json | provider active | parks the lane (AUTO-GATE), surfaced by a once-log | pool.py:165-193 |
| `deep_research` stage pin in config/llm_accounts.yaml | compiler stage lanes | names the lanes that serve research (DR0) | deep_research.py:225-227 |
| `POLYMATH_OLLAMA_MODELS` | `""` | comma list of ollama names; empty falls back to `OLLAMA_FREE_CLOUD_MODELS` | ui.py:101-104 |
| provider `structured` (legacy `json_mode`) | `"json"` | capability level, one of `schema`, `json`, `text` | pool.py:139-149 |
| `_COMPILER_PREFERRED_LANE`, `_COMPILER_LANE_COOLDOWN_S` (values not in SOURCE) | not shown | preferred lane goes first; cooldown window demotes recently failed lanes to the back | ui.py:1755, 1771-1774 |

## failure modes

1. 502 `PLAN_FAILED` — the planner call raised; only `type(exc).__name__` is logged and returned, never the message → deep_research.py:501-506.
2. 502 `PLAN_EMPTY` — `draft.goals` is empty ("the planner wrote no usable search; start without a plan"); the page can still start the run → deep_research.py:507-508, 492-494.
3. 503 `NO_RESEARCH_LANE` — pinned lane names matched no enabled endpoint (pin names absent, or every named lane parked) → deep_research.py:244-247; park rules at pool.py:165-193.
4. Typed `AllLanesRefused` — every lane's limiter refused at once (breaker open, Retry-After hold, saturated; zero HTTP); the engine counts it and ends that branch instead of waiting out a cooldown → deep_research.py:236-239, 262-268.
5. `RuntimeError("research lanes failed: ...")` — real call failures reached `RESEARCH_DISPATCH_ATTEMPTS`, or all endpoints errored → deep_research.py:251-253, 266-270.
6. Loud roster `ValueError` — malformed `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS` or cloud_providers.json (bad JSON, entry without name+url+model, reserved or duplicate `"primary"`) → pool.py:229-248, 156-197.
7. Silent fallback: no `deep_research` pin → the chat compiler's lanes serve research (by design, DR0) → deep_research.py:225-227.
8. Silent fallback: a parked provider (key/account-id unset, `enabled: false`) leaves the roster; only a once-log marks it, so a half-speed pool looks normal → pool.py:169-193, 211-214.
9. Silent fallback: request names no synthesizer → first offered preference; a provider with an unset env key is hidden, and the request lands on a different model (measured 2026-09-06: `litellm:openai/glm-5-free` with the OpenCode key unset → LiteLLM "Missing credentials") → ui.py:84-93, 642-646.
10. Silent behaviour: lane cooldown demotes recently failed lanes to the back but never drops them; if every lane is cold, all are still tried → ui.py:1771-1774.
11. Ollama daemon down: `_ollama_registered` returns an empty set (3 s timeout, non-fatal); models still list with `available: false` and the pull command → ui.py:107-139.
12. Receipt silently missing — any receipt exception logs `QUERY_RECEIPT_FAILED` and returns None after the stream ended; oversized meta (> 64 KB) loses the whole meta unless `receipt_block`/`_meta_json` shrank it → deep_research.py:466-467, 473-478; query_receipts.py:152-181, 221-223.
13. 409 `DEEP_RESEARCH_BUSY` — the same principal (or `"owner"`) already streams a run; the plan endpoint is exempt → deep_research.py:420-422, 493-494.
14. 422 family: `LIBRARY_REQUIRED`, `CORPUS_NOT_ALLOWED`, `UNKNOWN_PRESET`, `UNKNOWN_SYNTHESIZER`, `PLAN_INVALID` (all plan problems in one message) → deep_research.py:136-137, 499, 412, 416, 94-107; web_scope.py:103-105.

## invariants

- INVARIANT: one deep-research run per principal at a time; the plan card sits outside that lock — deep_research.py:420-422, 490-494 [DERIVED]
- INVARIANT: a friend may only research libraries they can read — deep_research.py:138 [DERIVED]
- INVARIANT: an interactive research lane never waits on a limiter; a refusal skips a lane without spending an attempt; zero admission fails fast and typed — deep_research.py:236-239, 251-268 [DERIVED]
- INVARIANT: the second attempt is a lane of a different provider family (URL netloc) whenever one exists — ui.py:1747-1749, 1764-1766, 1734-1739 [DERIVED]
- INVARIANT: a request that names no synthesizer is never routed to a provider whose key is unset — ui.py:84-93, 642-646 [DERIVED]
- INVARIANT: receipts never break a query or a stream — query_receipts.py:188-190, 221-223; deep_research.py:466-467 [DERIVED]
- INVARIANT: the receipt's `deep_research` meta holds counts only, never evidence texts (64 KB meta cap) — deep_research.py:473-486 [DERIVED]
- INVARIANT: receipt meta is shrunk structurally, never sliced into invalid JSON — query_receipts.py:152-160 [DERIVED]
- INVARIANT: `knowledge_scope` is read from the request only; a response can never set or widen it — query_receipts.py:116-126 [DERIVED]
- INVARIANT: every roster composition and every parked lane is logged once, never silent — pool.py:153-156, 260-261 [DERIVED]

## VERIFY

```verify
grep -Fq 'DEEP_RESEARCH_BUSY' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'PLAN_EMPTY' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'NO_RESEARCH_LANE' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'research lanes failed' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'report_model_counts' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'QUERY_RECEIPT_FAILED' shared/polymath_shared/query_receipts.py
test "$(grep -c -F 'deep_research' orchestrator/orchestrator/api/deep_research.py)" -ge 5
```
