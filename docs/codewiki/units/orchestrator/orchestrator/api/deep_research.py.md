# unit: orchestrator/orchestrator/api/deep_research.py
anchor: orchestrator/orchestrator/api/deep_research.py:1-527

## purpose

FastAPI router exposing the deep-research loop (engine in `polymath_shared.deep_research`) as three endpoints: `POST /research/deep` streams the breadth × depth run as SSE (`phase`/`token`/`answer`/`error`/`done` plus keep-alive comments), `POST /research/deep/plan` makes the level-1 plan card in one planner call, `POST /research/deep/finish` ends the caller's run early — orchestrator/orchestrator/api/deep_research.py:1-18 [DERIVED]. Scope is fixed once: every search names exactly the confirmed libraries and runs under the caller's principal; planning/extraction use the chat compiler's governed lanes; the report is written by the composer's model — orchestrator/orchestrator/api/deep_research.py:6-9 [DERIVED]. Router mounted by `orchestrator/orchestrator/main.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `deep_research` | route def | (req: DeepResearchRequest) -> StreamingResponse | deep_research.py:406 | orchestrator/orchestrator/main.py |
| `deep_research_plan` | route def | (req: DeepPlanRequest) -> dict[str, Any] | deep_research.py:490 | orchestrator/orchestrator/main.py |
| `deep_research_finish` | route def | () -> dict[str, Any] | deep_research.py:517 | orchestrator/orchestrator/main.py |
| `DeepPlanGoal` | model class | goal: str = "", query: str, move: str = "broad" | deep_research.py:55-59 | — |
| `DeepResearchRequest` | model class | question 3-2000, corpus_id(s), preset="standard", mode="HYBRID", synthesizer, moves=True, plan | deep_research.py:62-70 | — |
| `DeepPlanRequest` | model class | question 3-2000, corpus_id(s), preset="standard", mode="HYBRID", moves=True | deep_research.py:73-80 | — |
| `confirmed_plan` | def | (req, breadth: int) -> tuple[tuple[str, str, str], ...] \| None | deep_research.py:87 | — |
| `moves_enabled` | def | (req) -> bool | deep_research.py:83 | — |
| `evidence_rows_of` | def | (out, corpus_ids, limit, *, explore=False) -> list[dict] | deep_research.py:149 | — |
| `move_request` | def | (query, libraries, mode, move=None, anchor_docs=()) -> tuple[Any, bool] | deep_research.py:163 | — |
| `research_lane_names` | def | (stage_pin_fn, compiler_stage) -> list[str] | deep_research.py:225 | — |
| `receipt_block` | def | (answer: dict \| None) -> dict \| None | deep_research.py:473 | — |
| `_Aliases` | class | alias(row) -> str ("c1", "c2", …) | deep_research.py:115-129 | — |

## contracts

**deep_research** (POST /research/deep)
- pre: ≥1 corpus id after dedupe else 422 `LIBRARY_REQUIRED` — deep_research.py:136; `require_corpora(ids)` enforces read permission — deep_research.py:138; synthesizer must start `litellm:` or `ollama:` else 422 `UNKNOWN_SYNTHESIZER` — deep_research.py:410-412; preset must parse else 422 `UNKNOWN_PRESET` — deep_research.py:413-416; request `plan` validated by `confirmed_plan` — deep_research.py:417; no other run for same `who = principal or "owner"` else 409 `DEEP_RESEARCH_BUSY` — deep_research.py:418-422.
- out: `StreamingResponse(media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})` — deep_research.py:469-470.
- post: any stream exit sets `cancel` and removes `_RUNNING[who]`/`_FINISH[who]` — deep_research.py:452-458; a query receipt is recorded with `kind="deep_research"`, `route="research/deep"` — deep_research.py:462-465.

**deep_research_plan** (POST /research/deep/plan)
- pre: same library and preset checks as a run — deep_research.py:495-499; lanes must exist else 503 `NO_RESEARCH_LANE` — deep_research.py:246-247.
- out: dict `{intent, evaluative, preset, goals[{id,goal,query,move}], estimate, libraries, moves}` — deep_research.py:509-513.
- post: planner exception → 502 `PLAN_FAILED`; no usable goal → 502 `PLAN_EMPTY` — deep_research.py:503-507. Not under the one-run lock — deep_research.py:492-493.

**deep_research_finish** (POST /research/deep/finish)
- pre: caller has a run else 404 `NO_DEEP_RESEARCH_RUN` — deep_research.py:521-525.
- out: 202 `{"finishing": True}`; sets the run's finish event — deep_research.py:516, 526-527.

**confirmed_plan**
- in: req + `breadth` from the preset shape — deep_research.py:417.
- pre: ≤ `2 * breadth` goals; query 3-300 chars after strip; move in `DR.MOVES`; goal ≤ 2000 chars; empty plan refused; all problems in one 422 `PLAN_INVALID` — deep_research.py:94-107.
- out: tuple of stripped `(goal, query, move)` or None when `req.plan is None`; repeated queries allowed — deep_research.py:92-93, 108, 90-91.

**move_request**
- out per move: `deep` + anchors → `document_ids=anchor_docs`, explore False; `adjacent`/`inverse` → intent `RELATIONSHIP`/`COMPARISON` only when `mode in INTENT_MODES and retrieve_engine_flag() == "v2"`; else base mode with explore = `(move == "broad")` — deep_research.py:46, 177-182.
- every request: `limit=ROWS_PER_SEARCH`, `evidence=True` — deep_research.py:176.

**evidence_rows_of**
- out: copies existing `evidence_rows`; else rebuilds from order-preserving deduped `chunk_id` list with synthetic descending `rerank_score` (`float(len(ids) - i)`); `[]` when no ids — deep_research.py:154-160.

**receipt_block**
- post: replaces `report_model` with `report_model_counts` (goals, findings, confidence `{strong, single_source, contested}`, counter, open_questions, sources) so receipt meta stays under its 64 KB cap — deep_research.py:473-486.

## effect surface

- env read: `POLYMATH_DEEP_RESEARCH_HEARTBEAT_S` = "15" — deep_research.py:41; `POLYMATH_DEEP_RESEARCH_MOVES` = "1" — deep_research.py:84.
- network: `litellm.completion(stream=True, timeout=300)` — deep_research.py:281-288; `httpx.stream("POST", f"{OLLAMA_URL}/api/chat", timeout=300)` — deep_research.py:298-299; retrieval via `asyncio.run_coroutine_threadsafe(... _retrieve_impl(req))` — deep_research.py:186, 193; gate cross-encoder via `gate_probes(..., chat_retrieval._rerank_children, ...)` — deep_research.py:213-218; per-lane `LLMExtractionClient.complete_one` — deep_research.py:254-259.
- DB: `tx()` connection inside `_build_rows` — deep_research.py:144-146; `record_query_receipt(tx, kind="deep_research", ...)` — deep_research.py:460-465. FACTS.tables_read/tables_written: none named.
- in-process state: `_RUNNING`/`_FINISH` dicts guarded by `_LOCK` — deep_research.py:49-51; daemon thread `name="deep-research"` — deep_research.py:432-433.
- no files, no subprocess (FACTS + SOURCE).

## invariants

INVARIANT: rows per search ≤ ROWS_PER_SEARCH = 10 — deep_research.py:43, 202 [DERIVED]
  fails-if: a search floods the report prompt / alias table beyond the cap the engine expects.
INVARIANT: retrieve port wall timeout = PORT_TIMEOUT_S = 60.0 — deep_research.py:42, 193 [DERIVED]
  fails-if: a hung retrieval blocks the worker thread forever instead of raising.
INVARIANT: alias ids are unique per run, one alias per unique row id (`c{len(self._by_id) + 1}`) — deep_research.py:123-128 [DERIVED]
  fails-if: two rows share a cid and `validate_report_citations` mis-credits evidence.
INVARIANT: confirmed plan goals ≤ 2 × breadth — deep_research.py:95 [DERIVED]
  fails-if: 422 PLAN_INVALID instead of a run.
INVARIANT: confirmed query length ∈ [3, 300], goal length ≤ 2000 — deep_research.py:48, 100, 104 [DERIVED]
  fails-if: 422 PLAN_INVALID listing the goal number.
INVARIANT: per-caller run count ≤ 1, key = `principal or "owner"` — deep_research.py:418-424 [DERIVED]
  fails-if: two streams share one cancel event, or 409 DEEP_RESEARCH_BUSY never fires.
INVARIANT: failed lane attempts per complete call ≤ RESEARCH_DISPATCH_ATTEMPTS = 2 — deep_research.py:231, 251-252 [DERIVED]
  fails-if: research burns attempts on lanes a limiter already failed.
INVARIANT: citation text ≤ 600 chars, worker error message ≤ 300 chars, phase query label ≤ 120 chars — deep_research.py:393, 399, 324/339 [DERIVED]
  fails-if: oversized SSE frames / leaked source text in error frames.
INVARIANT: stream silent gap ≤ HEARTBEAT_S = 15 s (`": keep-alive\n\n"` on queue timeout) — deep_research.py:41, 440-442 [DERIVED]
  fails-if: a proxy closes the idle SSE connection mid-run.

## determinism & idempotency

determinism: NONDETERMINISTIC (clock `time.monotonic` at deep_research.py:336, 348, 374, 395, 429, 464; network litellm/httpx streams deep_research.py:288, 298; concurrency `threading.Thread` deep_research.py:432; env deep_research.py:41, 84) [DERIVED]
idempotency: UNSAFE — `/research/deep` starts retrieval+LLM work and writes a receipt per stream (deep_research.py:463-465); `/research/deep/plan` mutates nothing but is LLM-nondeterministic; `/research/deep/finish` is idempotent (event set) — deep_research.py:526 [INFERRED: from event semantics]

## failure behaviour

- `_worker` catches every `Exception` → SSE `error` frame with `error_code = type(exc).__name__`, message truncated to 300; stream still ends with `done` — deep_research.py:398-401, 450-451 [DERIVED].
- plan endpoint catches planner `Exception` → logs class name only, raises 502 `PLAN_FAILED`; empty draft → 502 `PLAN_EMPTY` — deep_research.py:503-507 [DERIVED].
- SWALLOWED: reasoning-policy overlay failure in `_report_tokens` → warning log, report streams without the thinking rule — deep_research.py:286-287 [DERIVED].
- SWALLOWED: receipt write failure → warning `"deep research receipt not written"`, stream unaffected — deep_research.py:466-467 [DERIVED].
- gate receipt error → `RuntimeError` raised to the engine (docstring: engine keeps the searches, fail-open) — deep_research.py:219-220, 209-211 [DERIVED].
- stream error codes: `CANCELLED` — deep_research.py:366, 381; `RESEARCH_FAILED` / `NOTHING_FOUND` — deep_research.py:369-372; `REPORT_EMPTY` — deep_research.py:383-385.
- HTTP codes: 422 `LIBRARY_REQUIRED`/`PLAN_INVALID`/`UNKNOWN_SYNTHESIZER`/`UNKNOWN_PRESET` — deep_research.py:136, 107, 412, 416; 409 `DEEP_RESEARCH_BUSY` — deep_research.py:422; 503 `NO_RESEARCH_LANE` — deep_research.py:247; 502 `PLAN_FAILED`/`PLAN_EMPTY` — deep_research.py:505, 507; 404 `NO_DEEP_RESEARCH_RUN` — deep_research.py:525.

## dumb-code flags

- Magic 300 duplicated as two unrelated caps: report stream timeout (litellm kwargs `"timeout": 300`, httpx `timeout=300`) — deep_research.py:281, 298 [DERIVED].
- Magic truncations 120 / 600 / 300 inline, not constants — deep_research.py:324, 339, 393, 399 [DERIVED].
- 64 KB receipt meta cap exists only in `receipt_block` docstring, not enforced here — deep_research.py:474 [DERIVED].
- `Config.preset` called with `score_floor=float("-inf")` in `_worker` — deep_research.py:352 — but without it in the plan endpoint — deep_research.py:497; the two call sites get different default behavior [DERIVED].
- Defaults duplicated across both request models: `preset: str = "standard"` and `mode: str = "HYBRID"` — deep_research.py:66-67, 78-79 [DERIVED].
- `req.preset.strip().lower()` computed twice on the answer path — deep_research.py:390, 510 [DERIVED].
- Preset names only in a comment (`quick 3×1 · standard 3×2 · thorough 4×2`); real shapes live in `DR.Config.preset` — deep_research.py:66 [DERIVED].

## refactor notes

- Private cross-module imports — renaming any breaks this unit: `orchestrator.api.retrieve._retrieve_impl`, `INTENT_MODES`, `retrieve_engine_flag` — deep_research.py:171-175, 186; `chat_retrieval._rerank_children` — deep_research.py:218; `orchestrator.api.ui._compiler_attempt_order`/`_chat_max_tokens`/`_litellm_credentials`/`_default_synthesizer`/`OLLAMA_URL` — deep_research.py:240, 279, 409, 297.
- Route paths and verbs are the mounted contract (importer: `orchestrator/orchestrator/main.py`) — deep_research.py:405, 489, 516 [DERIVED].
- SSE frame contract is client-facing: event names `phase`/`token`/`answer`/`error`/`done`, `coverage` frames, keep-alive comments, and `_STAGE_LABEL`/`_PHASE_FIELDS` shapes — deep_research.py:2-3, 312-318, 354-357, 441-442 [DERIVED].
- `_RUNNING`/`_FINISH` key scheme (`principal or "owner"`) is shared by run and finish endpoints; changing it breaks `/research/deep/finish` lookup — deep_research.py:418-424, 521-523 [DERIVED].
- Error-code strings (`PLAN_INVALID`, `DEEP_RESEARCH_BUSY`, `NO_DEEP_RESEARCH_RUN`, `PLAN_FAILED`, `PLAN_EMPTY`, `NO_RESEARCH_LANE`, `LIBRARY_REQUIRED`, `UNKNOWN_PRESET`, `UNKNOWN_SYNTHESIZER`, `CANCELLED`, `RESEARCH_FAILED`, `NOTHING_FOUND`, `REPORT_EMPTY`) are API contract for the page — deep_research.py:107, 136, 247, 412, 416, 422, 366/381, 369-372, 384, 505-507, 525 [DERIVED].
- Move semantics (`MOVE_INTENT` mapping and the `v2`-engine gating) change search behaviour for every planned search — deep_research.py:46, 179-181 [DERIVED].

## VERIFY

```verify
grep -Fq 'ROWS_PER_SEARCH = 10' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'PORT_TIMEOUT_S = 60.0' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'RESEARCH_DISPATCH_ATTEMPTS = 2' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'POLYMATH_DEEP_RESEARCH_HEARTBEAT_S' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'DEEP_RESEARCH_BUSY' orchestrator/orchestrator/api/deep_research.py
grep -Eq 'PLAN_(INVALID|FAILED|EMPTY)' orchestrator/orchestrator/api/deep_research.py
grep -Fq '{"finishing": True}' orchestrator/orchestrator/api/deep_research.py
test "$(grep -c -F 'time.monotonic' orchestrator/orchestrator/api/deep_research.py)" -ge 6
```
