# unit: orchestrator/orchestrator/api/deep_research.py
anchor: orchestrator/orchestrator/api/deep_research.py:1-510

## purpose
FastAPI router for deep research (DEEP-RESEARCH-MODE-V1 DR2/DR6/DR7): `POST /research/deep` runs the shared breadth × depth loop (`polymath_shared.deep_research`) over the request's libraries and streams chat-style SSE frames (`phase`, `token`, `answer`, `error`, `done`) plus keep-alive comments; `POST /research/deep/plan` builds the level-1 plan card; `POST /research/deep/finish` ends the caller's run early. Libraries are resolved and read-checked once, and every search runs under the caller's principal so no step widens scope (K1); one run per person, a disconnect cancels it. — orchestrator/orchestrator/api/deep_research.py:1-18 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `deep_research` | route `POST /research/deep` | `(req: DeepResearchRequest) -> StreamingResponse` | orchestrator/orchestrator/api/deep_research.py:387-452 | orchestrator/orchestrator/main.py |
| `deep_research_plan` | route `POST /research/deep/plan` | `(req: DeepPlanRequest) -> dict[str, Any]` | orchestrator/orchestrator/api/deep_research.py:471-495 | orchestrator/orchestrator/main.py |
| `deep_research_finish` | route `POST /research/deep/finish` (202) | `() -> dict[str, Any]` | orchestrator/orchestrator/api/deep_research.py:498-509 | orchestrator/orchestrator/main.py |
| `moves_enabled` | def | `(req: DeepResearchRequest \| DeepPlanRequest) -> bool` | orchestrator/orchestrator/api/deep_research.py:83-84 | — |
| `confirmed_plan` | def | `(req: DeepResearchRequest, breadth: int) -> tuple[tuple[str, str, str], ...] \| None` | orchestrator/orchestrator/api/deep_research.py:87-108 | — |
| `evidence_rows_of` | def | `(out: dict, corpus_ids: list[str], limit: int, *, explore: bool = False) -> list[dict]` | orchestrator/orchestrator/api/deep_research.py:149-160 | — |
| `move_request` | def | `(query, libraries, mode, move=None, anchor_docs=()) -> tuple[Any, bool]` | orchestrator/orchestrator/api/deep_research.py:163-182 | — |
| `research_lane_names` | def | `(stage_pin_fn, compiler_stage: str) -> list[str]` | orchestrator/orchestrator/api/deep_research.py:225-227 | — |
| `receipt_block` | def | `(answer: dict[str, Any] \| None) -> dict[str, Any] \| None` | orchestrator/orchestrator/api/deep_research.py:455-468 | — |

Sole importer: `orchestrator/orchestrator/main.py` (FACTS.importers).

## contracts

**deep_research** (orchestrator/orchestrator/api/deep_research.py:387-452)
- in: `question` 3–2000 chars, `preset="standard"`, `mode="HYBRID"`, `synthesizer=None`, `moves=True`, `plan: list[DeepPlanGoal] | None` (62-70).
- pre: ≥1 library after dedupe else 422 `LIBRARY_REQUIRED` (134-137); `require_corpora(ids)` read check (138); synthesizer (request or `_default_synthesizer()`) must start with `"litellm:"`/`"ollama:"` else 422 `UNKNOWN_SYNTHESIZER` (392-394); preset must parse else 422 `UNKNOWN_PRESET` (395-398); plan passes `confirmed_plan` else 422 `PLAN_INVALID` (399, 107); caller must not already run else 409 `DEEP_RESEARCH_BUSY` (402-404).
- out: `StreamingResponse` `media_type="text/event-stream"`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` (451-452); SSE events `phase`/`token`/`answer`/`error`/`done` (111-112, 433) and `": keep-alive\n\n"` comments on idle (422-424).
- post: receipt recorded `kind="deep_research"`, route `"research/deep"`, meta carries `receipt_block(answer)` (441-447); `_RUNNING`/`_FINISH` entries removed and `cancel.set()` on any exit, including disconnect (434-440).

**deep_research_plan** (orchestrator/orchestrator/api/deep_research.py:471-495)
- in: `DeepPlanRequest` — same question/corpus/preset/mode/moves shape; `mode` accepted but planning searches nothing (73-80).
- pre: library + preset checks as above (477-481); ≥1 research lane else 503 `NO_RESEARCH_LANE` via `_complete_port` (236-239).
- out: dict `{"intent", "evaluative", "preset", "goals": [{id, goal, query, move}], "estimate", "libraries", "moves"}` (491-495); planner exception → 502 `PLAN_FAILED` (485-488); no usable goals → 502 `PLAN_EMPTY` (489-490).
- post: none; explicitly not under the one-run lock (475).

**deep_research_finish** (orchestrator/orchestrator/api/deep_research.py:498-509)
- in: no body ("the page posts `{}`", 500).
- pre: caller has a run else 404 `NO_DEEP_RESEARCH_RUN` (503-507).
- out: 202 `{"finishing": True}` (498, 509).
- post: finish event set — run starts nothing new, lets in-flight calls finish, writes the report with stop reason `finished_early` (500-502).

**confirmed_plan** (orchestrator/orchestrator/api/deep_research.py:87-108)
- `plan is None` → `None` (92-93); empty list → problem `"the plan has no goals"` (94); `len(plan) > 2 * breadth` rejected (95-96); each query 3–300 chars after strip, move in `DR.MOVES`, goal ≤ 2000 chars (97-105); any problem → single 422 `PLAN_INVALID` joining all with `"; "` (106-107); returns `tuple((goal.strip(), query.strip(), move))` (108).

**move_request** (orchestrator/orchestrator/api/deep_research.py:163-182)
- base request fields: `query`, `corpus_ids`, `limit=ROWS_PER_SEARCH`, `evidence=True` (176).
- `deep` with anchors → `document_ids=list(anchor_docs)`, explore False (177-178); `adjacent`/`inverse` → intent `RELATIONSHIP`/`COMPARISON` only when `mode in INTENT_MODES` and `retrieve_engine_flag() == "v2"` (179-181, 46); otherwise base mode; explore True only when `move == "broad"` (182).

**evidence_rows_of** (orchestrator/orchestrator/api/deep_research.py:149-160)
- returns copy of `out["evidence_rows"]` when present (154-155); else dedupes `chunk_id` from the flat `evidence` list, preserving order (156-160); `explore=True` = EXPLORE cap, 2 rows per document, interleaved (150-153).

**receipt_block** (orchestrator/orchestrator/api/deep_research.py:455-468)
- returns `answer.result.meta.deep_research` (or None); when it holds `report_model`, swaps the model for `report_model_counts` (goals/findings/confidence buckets/counter/open_questions/sources) to stay under the 64 KB receipt meta cap (456-468).

## effect surface
- env: `POLYMATH_DEEP_RESEARCH_HEARTBEAT_S` = `"15"` (41); `POLYMATH_DEEP_RESEARCH_MOVES` = `"1"`, any of `"0"/"false"/"off"/"no"` disables moves (44, 84).
- network: `litellm.completion(..., stream=True, timeout=300)` for `litellm:` synthesizers (259-270); `httpx.stream("POST", f"{OLLAMA_URL}/api/chat", timeout=300)` for `ollama:` (277-281); relevance gate via `gate_probes` + `chat_retrieval._rerank_children`, origin `"DEEP_RESEARCH"` (207-218); retrieval via `asyncio.run_coroutine_threadsafe(_retrieve_impl(req))` under the caller's principal (188-194).
- Postgres: via `polymath_shared.db.tx()` in `_build_rows` (142-146) and `record_query_receipt(tx, kind="deep_research", ...)` (441-447); no specific tables listed in FACTS (tables_read/tables_written empty).
- process state: module dicts `_RUNNING`/`_FINISH` keyed by principal, guarded by `_LOCK` (49-51); daemon worker thread name `"deep-research"` (414); `_Aliases` per-run lock (121).
- files/Qdrant/subprocesses: none visible.

## invariants
INVARIANT: len(req.plan) <= 2 * shape.breadth — 95-96 [DERIVED]; fails-if: 422 PLAN_INVALID, plan rejected.
INVARIANT: 3 <= len(query.strip()) <= 300 (PLAN_QUERY_CHARS) — 48, 97-101 [DERIVED]; fails-if: 422 PLAN_INVALID.
INVARIANT: len(item.goal) <= 2000 == question max_length (PLAN_GOAL_CHARS) — 48, 63, 104-105 [DERIVED]; fails-if: 422 PLAN_INVALID.
INVARIANT: rows per search <= ROWS_PER_SEARCH = 10 — 43, 203 [DERIVED]; fails-if: oversized evidence feeds the model per search.
INVARIANT: retrieve port timeout == LLM client timeout_s == PORT_TIMEOUT_S == 60.0 — 42, 194, 245 [DERIVED]; fails-if: port raises into the worker's catch-all error frame.
INVARIANT: one _RUNNING entry per principal (who = principal or "owner") — 49, 400-405 [DERIVED]; fails-if: 409 DEEP_RESEARCH_BUSY on second start.
INVARIANT: idle gap between SSE yields <= HEARTBEAT_S (default 15 s) — 41, 422-424 [DERIVED]; fails-if: proxy may close a silent stream.
INVARIANT: error message length <= 300 chars; citation text <= 600; phase query <= 120 — 382, 375, 307/321 [DERIVED]; fails-if: oversized frames leak source text into the stream.
INVARIANT: alias ids are "c<N>" assigned in first-seen order of row id, unique per run — 123-128 [DERIVED]; fails-if: report citations cannot map back to evidence rows.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` at 318, 330, 356, 377, 411, 446; concurrency `threading.Thread` at 414 plus locks 51/121; network `httpx.stream` 280 and `litellm.completion` 270; env flags 41, 84) — orchestrator/orchestrator/api/deep_research.py:270-446 [DERIVED]
idempotency: UNSAFE (each `POST /research/deep` spawns a worker thread and writes a query receipt, 414, 441-447; repeats while running are refused with 409, 403-404)

## failure behaviour
- Worker catch-all: any `Exception` → SSE `error` frame with `error_code = type(exc).__name__`, message truncated to 300 chars, then `_END` → `done` (381-384, 426-433).
- Stream error codes: `CANCELLED` (348, 363), `RESEARCH_FAILED` vs `NOTHING_FOUND` chosen by `retrieval_errors or llm_errors` (350-354), `REPORT_EMPTY` (365-367).
- Plan endpoint: `Exception` → `log.warning` + 502 `PLAN_FAILED` (class name only, never the message) (485-488); no goals → 502 `PLAN_EMPTY` (489-490).
- SWALLOWED: reasoning-policy overlay failure in `_report_tokens` → `log.warning`, stream continues without the overlay (266-269).
- SWALLOWED: receipt write failure → `log.warning("deep research receipt not written: ...")`, stream unaffected (448-449).
- Relevance gate: judge error/timeout raises `RuntimeError` into the engine, which fails open and counts the searches (207-220).
- Disconnect: `finally` in `events()` sets cancel and still attempts the receipt (434-447).

## dumb-code flags
- Fallback principal literal `"owner"` duplicated at 400 and 503.
- Model timeout literal `300` duplicated: litellm kwargs (263) and ollama `httpx.stream` (280).
- Truncation literals scattered with no named constant: `120` (307, 321), `300` (382), `600` (375).
- Comment says `POLYMATH_DEEP_RESEARCH_MOVES=0` forces moves off (44), but `moves_enabled` also treats `"false"`, `"off"`, `"no"` (84).
- `DeepPlanRequest.mode` accepted and never used by the handler (73-80, docstring 74).
- Preset shapes live only in a comment (`# quick 3×1 · standard 3×2 · thorough 4×2`, 66); real values are in `DR.Config.preset` (396, 479).
- `_STAGE_LABEL`/`_PHASE_FIELDS` duplicate the engine's event vocabulary (294-300).

## refactor notes
- `orchestrator/orchestrator/main.py` is the sole importer (FACTS.importers); the three route paths are the HTTP contract (275-289 in FACTS routes; 387, 471, 498).
- Private cross-module imports that break on rename: `orchestrator.api.retrieve._retrieve_impl` (186), `INTENT_MODES`/`retrieve_engine_flag` (171-174, 180); `orchestrator.api.ui._compiler_attempt_order` (232), `_chat_max_tokens`/`_litellm_credentials` (261), `OLLAMA_URL` (279), `_default_synthesizer` (373); `orchestrator.api.chat_retrieval._rerank_children` (218).
- Client-facing SSE contract: event names `phase`/`token`/`answer`/`error`/`done`, keep-alive comments, answer `kind: "deep"` with `meta.verdict` `"supported"`/`"unsupported"` (2-4, 377-380, 424, 433).
- `receipt_block` hardcodes the evidence-model keys (`goals`, `findings`, `counter`, `open_questions`, `sources`, confidence buckets `"strong"`/`"single_source"`/`"contested"`) — any `DR.evidence_model` shape change must update 462-468.
- `_RUNNING`/`_FINISH` are in-process dicts keyed by principal (49-50); running multiple orchestrator processes would break the one-run lock and `/finish` routing [INFERRED — no shared store is visible].

## VERIFY
```verify
grep -Fq 'ROWS_PER_SEARCH = 10' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'MOVE_INTENT = {"adjacent": "RELATIONSHIP", "inverse": "COMPARISON"}' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'raise HTTPException(409, {"error_code": "DEEP_RESEARCH_BUSY"' orchestrator/orchestrator/api/deep_research.py
grep -Eq '"error_code": "(PLAN_INVALID|PLAN_FAILED|PLAN_EMPTY|CANCELLED|RESEARCH_FAILED|NOTHING_FOUND|REPORT_EMPTY)"' orchestrator/orchestrator/api/deep_research.py
grep -Fq 'rows[:ROWS_PER_SEARCH]' orchestrator/orchestrator/api/deep_research.py
! grep -Fq '@router.get' orchestrator/orchestrator/api/deep_research.py
test "$(grep -c -F 'time.monotonic' orchestrator/orchestrator/api/deep_research.py)" -ge 6
```
