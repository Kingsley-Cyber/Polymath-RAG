---
change_id: DEEP-RESEARCH-DR7-BACKEND
owner: "@king"
date: 2026-09-26
status: complete
status_note: "DR7a, DR7b and the backend of DR7c built on feat/deep-research-experience: the plan card (POST /research/deep/plan) and the confirmed plan, the deterministic evidence model with the report's sentence audit, coverage frames and the coverage_complete stop, and Finish now (POST /research/deep/finish). Moves off stays DR1's engine, byte for byte. The DR7 frontend (DR7c-e) is built separately against these contracts."
architecture_impact: "shared/polymath_shared/deep_research/evidence.py (new), engine.py, prompts.py, __init__.py; orchestrator/orchestrator/api/deep_research.py (two routes, plan, finish, coverage frames, report_model, audit, receipt block); orchestrator/orchestrator/web_boundary.py (two USER paths); tests/contracts/test_deep_research_experience.py (new), test_deep_research_route.py (+17 tests), test_deep_research_moves.py (the report layout)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR7a-c (backend): the research experience

## Contract
- DEEP-RESEARCH-MODE-V1 §11.3 and §11.4, slices DR7a, DR7b and the backend of DR7c (register 11.529). The owner said "go
  ahead, build it all".
- §11.3's field names are followed exactly. Where §11.3 is silent, the choice is listed under Rejected claims, so the
  frontend (DR7c-e, built in parallel) can be matched.

## Changes
- **Engine** (`shared/polymath_shared/deep_research/`):
  - `plan_goals(question, complete, config)` makes exactly one planner call and accepts its reply as a run's level 1
    (quota order, leftovers, duplicates, unanchored inverse queries). It returns a `PlanDraft`.
  - `run_research(..., plan=[(goal, query, move)], finish=Event)`:
    - A confirmed plan becomes level 1 with no planner call, and every item is a goal with `confirmed=True`. The gate
      scores it but never drops it (`gate.user_kept`). The run's limits grow with its width (`Config.first_width`,
      `preset_cost(..., first=)`).
    - `finish` is a soft halt like budget: calls in flight finish, nothing new starts, and the stop reason is
      `finished_early`.
  - With moves, a `coverage` event follows each level. The run stops with `coverage_complete` when every goal the gate
    kept has 2 or more findings from 2 or more documents and a next level was queued.
  - `estimate(config, planned=)` returns `{searches, llm_calls, seconds}`. `STOP_REASONS` gains the two new reasons.
    `Row.title`, `ResearchOutcome.confirmed_plan`, and learnings' `doc_ids` are now kept current as citations pool.
  - `evidence.py` (new, pure) holds `evidence_model`, `coverage` / `coverage_complete`, `split_sentences` +
    `SENTENCE_PATTERN`, and `audit_report`.
  - With moves, the report prompt (§11.4) asks for a TL;DR, one section per goal in plan order, then "Where sources
    disagree". Counter-evidence is listed apart. There is no sources list and no open-questions section. This replaces
    DR6's three move sections.
- **Route** (`orchestrator/orchestrator/api/deep_research.py`):
  - `POST /research/deep/plan` (USER; outside the one-run lock).
  - `DeepResearchRequest.plan`, checked by `confirmed_plan` (422 `PLAN_INVALID`).
  - `POST /research/deep/finish` (USER; 202 / 404).
  - With moves, a `coverage` SSE frame follows each level.
  - `goal_id`, `goals`, `confirmed` and `user_kept` are passed through on phase frames.
  - The answer's `meta.deep_research` gains `report_model` and `audit`. The receipt stores the audit and
    `report_model_counts`, never the model's texts.

## Proof
- `test_deep_research_experience.py`, 21 tests:
  - the plan card is one call, the same as a run's level 1;
  - a confirmed plan makes no level-1 planner call, is checked, and is never dropped by the gate;
  - Finish now keeps the in-flight learning;
  - coverage frames, the stop, gated goals, moves off;
  - the evidence model on fixed learnings: every confidence rule, counter-evidence, open questions, sources order, method;
  - the split rule and the audit on crafted reports;
  - the estimate against §3's table.
- `test_deep_research_route.py`, +17 tests:
  - `/plan`: one call and no search; library, preset and lock behaviour; 502s;
  - the plan seeds level 1, and a low-scored confirmed goal is still searched;
  - 7 kinds of bad plan are refused before any work;
  - `/finish`: 404 / 202 per caller, and an end-to-end Finish now that still writes the report;
  - coverage frames; goal ids on frames; `report_model`, `audit` and the receipt; the web boundary.
- DR6's two report-layout tests now assert DR7's layout, and the gate dicts gain `user_kept`. No other assertion changed.
- Mutation checks (scratch): all 36 deliberate breaks of the engine, evidence model, audit and route were caught.
- Moves off still matches the pre-DR6 engine (`7051bf0c`) on the 20 scripted scenarios.
- `tests/contracts -k "not test_live_"`: 596 passed (558 before).
- Determinism tests that touch retrieval, intents, the gate or the boundary: 194 passed. Two fail identically at `HEAD`:
  `test_chat_runtime.py::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` (stale expected kwargs) and
  `test_chat_modes.py::test_wildcard_sweep_overlaps_...` (a timing assertion).
- Frontend: tsc 0, vitest 93 passed; no frontend change. The three guards: 0. Ruff: no new findings.

## Rejected claims
The choices below are where §11.3 / §11.4 are silent. Field names are exact.
- **`/plan`**:
  - The response adds `libraries` (the checked list) and `moves` (bool).
  - `goals[].id` is the level-1 search id ("1.1", "1.2", …). With moves off every goal's `move` is `broad`.
  - `estimate` counts the run's searches, its LLM calls (report included, the level-1 planner left out) and seconds
    (10 + 11 per search, from DR4, capped at the deadline).
  - Errors: 403 / 422 `LIBRARY_REQUIRED` from the library checks; 422 `UNKNOWN_PRESET`; 503 `NO_RESEARCH_LANE`; 502
    `PLAN_FAILED` (the planner failed, class name only) or `PLAN_EMPTY` (no usable query). After a 502 the page can start
    without a plan. No receipt.
- **`plan` items**:
  - `goal` defaults to "" and `move` to "broad".
  - Also refused (422 `PLAN_INVALID`, with every problem listed): an empty plan, a goal over 1000 characters, and the same
    query twice (ignoring case and spacing).
  - A kept goal is still under the spawn floor (no children), as the literal reading of "never dropped" gives.
- **`/finish`**: 202 `{"status": "finishing"}`; 404 `{"error_code": "NO_DEEP_RESEARCH_RUN"}`. It is scoped to the caller.
- **Frames** (moves on only; moves off streams exactly as before):
  - `event: coverage`, data `{goals: [{id, learnings, documents}], level}`. `learnings` counts every learning of the goal,
    counter-evidence included; `documents` counts its distinct known documents.
  - `deep_retrieve` and `deep_extract` carry `goal_id`, `move` and `query`.
  - `deep_plan` carries `moves` (one per query) and `goal_id` (the node's goal, null at level 1). At level 1 it also
    carries `goals: [{id, goal, query, move}]` and `confirmed`.
  - `deep_gate` adds `user_kept`.
- **`report_model`**:
  - `goals[]` adds `query`, `move` and `status`.
  - `documents` is a count.
  - `findings` are the goal's non-inverse learnings. `confidence` is `strong`, `single_source` or `contested`.
  - `counter` holds the inverse learnings.
  - `open_questions` are thin goals first (their goal text, else their query; a gate-dropped goal never counts), then
    follow-ups, capped at 5.
  - `sources` are ordered most findings first, then first cited. A title falls back to the row's label.
  - `method` = `{preset, model, intent, evaluative, moves, plan: "confirmed"|"planned", levels, searches, searches_by_move,
    llm_calls, learnings, passages, documents, gate, gap_nodes, drift_stopped, dropped_learnings, empty_searches, errors,
    stop_reason, elapsed_s}` (the moves-only keys are null with moves off).
  - `report_model` and `audit` come on every answer, moves on or off. With moves off the report prompt is DR1's.
- **`audit`**:
  - Indices are 0-based into `split_sentences(text)`. `invalid_cids` equals `unknown_citations`.
  - The split rule, for the page to mirror: normalise line ends and split into lines; skip fences (and the lines between),
    blank lines, headings, horizontal rules and table rows; strip the blockquote and list marker from each kept line; the
    line's sentences are the matches of `SENTENCE_PATTERN` (JavaScript flags `gis`). A sentence never spans lines.
- **The report prompt** omits goals with no learning. Empty searches and follow-ups go to the page's open questions.

## Open contract gaps
- DR7c-e (the frontend) must render these contracts. `frontend-v2/src/lib/chat.ts` does not yet type `report_model`,
  `audit` or `coverage`, and `api.ts` has no `/plan` or `/finish` call; that is the UI branch's work.
- The DR7f live acceptance waits for the deploy. It must watch:
  - the audit's uncited rate: DR1-style reports put "Open questions" prose into moves-off runs;
  - `coverage_complete` firing, and whether it fires too eagerly on 2 learnings per goal;
  - `/plan` latency: one planner call, up to 2 lanes × 60 s at worst;
  - a confirmed plan's wider level 1 against the 4-minute deadline.
- `/plan` writes no receipt: its one call is metered by the lane limiter only.
