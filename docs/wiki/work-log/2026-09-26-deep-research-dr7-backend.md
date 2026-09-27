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
- §11.3's field names are followed exactly. Where §11.3 is silent, the choice is listed under Rejected claims.
- The frontend (DR7c-e) was built in parallel on `feat/deep-research-ui` (`37509d09`, its work-log
  `2026-09-26-deep-research-dr7-ui.md`). The orchestrating session then asked the backend to match the UI's choices
  exactly. The second commit on this branch does that; every point is listed under Changes.

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
  - `evidence.py` (new, pure) holds `evidence_model`, `coverage` / `coverage_complete`, `split_sentences` (the page's
    split) and `audit_report`.
  - With moves, the report prompt (§11.4) asks for a TL;DR, one section per goal in plan order, then "Where sources
    disagree". Counter-evidence is listed apart. There is no sources list and no open-questions section. This replaces
    DR6's three move sections.
- **Matched to the UI** (the second commit):
  - `split_sentences` is the report view's `auditSentences` (`frontend-v2/src/lib/deep.ts`), ported line for line. It uses
    JavaScript's whitespace set, the closers `" ' ” ’ ) ] * _`, and one list marker. A leading citation group goes to the
    sentence before. An earlier regex version was replaced.
  - `method.moves` is the searches per move (`{broad, deep, adjacent, inverse}`), the shape the page reads; it replaces the
    boolean and `searches_by_move`.
  - Coverage frames also carry the run's totals, `documents` (distinct documents cited) and `passages` (rows read).
  - Moves-on search frames also carry `rows` and `status`.
  - `/finish` answers 202 `{"finishing": true}` and takes the page's `{}`.
  - A plan may repeat a query, as the page allows. The goal cap is 2000 characters (the question's own).
  - `test_web_boundary.py` gains the three `/research/deep*` cases and the deep research library guard.
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
  - the split, one test per rule plus the page's own cases, and the audit on the page's fixture report;
  - the estimate against §3's table.
- `test_deep_research_route.py`, +17 tests:
  - `/plan`: one call and no search; library, preset and lock behaviour; 502s;
  - the plan seeds level 1, and a low-scored confirmed goal is still searched;
  - 7 kinds of bad plan are refused before any work;
  - `/finish`: 404 / 202 per caller, and an end-to-end Finish now that still writes the report;
  - coverage frames; goal ids on frames; `report_model`, `audit` and the receipt; the web boundary.
- DR6's two report-layout tests now assert DR7's layout, and the gate dicts gain `user_kept`. No other assertion changed.
- Mutation checks (scratch):
  - all 36 deliberate breaks of the engine, evidence model and route were caught;
  - 13 of the 14 breaks of the ported split were caught. The survivor keeps a line's trailing `\r`; that changes no
    sentence, since `\r` is whitespace and is trimmed anyway.
- The split against the page's own function (scratch). `auditSentences` was taken from the UI commit, transpiled with the
  worktree's TypeScript and run in node. On 20,019 inputs (the tests' strings plus fuzz: emoji, NBSP, U+0085, BOM, CR,
  fences, tables, links, citations) its sentences and the port's were identical: 51,266 sentences, 0 differences.
- Moves off still matches the pre-DR6 engine (`7051bf0c`) on the 20 scripted scenarios.
- `tests/contracts -k "not test_live_"`: 607 passed (558 before).
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
  - Also refused (422 `PLAN_INVALID`, with every problem listed): an empty plan (the page's own rule), and a goal over 2000
    characters.
  - The 2000 cap is the one rule the page does not have. It only guards the report prompt against absurd input.
  - A repeated query is allowed.
  - A kept goal is still under the spawn floor (no children), as the literal reading of "never dropped" gives.
- **`/finish`**: 202 `{"finishing": true}`; 404 `{"error_code": "NO_DEEP_RESEARCH_RUN"}`. It is scoped to the caller.
- **Frames** (moves on only; moves off streams exactly as before):
  - `event: coverage`, data `{goals: [{id, learnings, documents}], documents, passages, level}`. A goal's `learnings`
    counts every learning of its thread, counter-evidence included; its `documents` counts the distinct known documents
    they cite. The run's `documents` and `passages` are the distinct documents cited and the rows read so far.
  - `deep_retrieve` and `deep_extract` carry `goal_id`, `move`, `query`, `rows` and, when a search ends, `status`
    (`ok` / `empty` / `error`); `deep_extract` also carries `new_learnings`.
  - `deep_plan` carries `moves` (one per query) and `goal_id` (the node's goal, null at level 1). At level 1 it also
    carries `goals: [{id, goal, query, move}]` and `confirmed`.
  - The page reads a phase frame's `goals` as coverage until the first coverage frame. The plan's goals then show with
    their ids and unknown counts, which is harmless.
  - `deep_gate` adds `user_kept`.
- **`report_model`**:
  - `goals[]` adds `query`, `move` and `status`.
  - `documents` is a count.
  - `findings` are the goal's non-inverse learnings. `confidence` is `strong`, `single_source` or `contested`.
  - `counter` holds the inverse learnings.
  - `open_questions` are thin goals first (their goal text, else their query; a gate-dropped goal never counts), then
    follow-ups, capped at 5.
  - `sources` are ordered most findings first, then first cited. A title falls back to the row's label.
  - `method` = `{preset, model, intent, evaluative, moves: {broad, deep, adjacent, inverse}, plan: "confirmed"|"planned",
    levels, searches, llm_calls, learnings, passages, documents, gate, gap_nodes, drift_stopped, dropped_learnings,
    empty_searches, errors, stop_reason, elapsed_s}` (the moves-only keys are null with moves off).
  - `report_model` and `audit` come on every answer, moves on or off. With moves off the report prompt is DR1's.
- **`audit`**:
  - Indices are 0-based into `split_sentences(text)`, the page's own split. `invalid_cids` equals `unknown_citations`.
  - The split, line by line:
    1. Skip blank lines, headings (first non-blank `#`), fenced code (``` or ~~~, the fences too), table rows (`|`) and
       rules (3 or more of one of `-*_=`).
    2. Strip leading `>` marks and one list marker.
    3. Split at each whitespace run after `.`, `!` or `?`, with optional closers `" ' ” ’ ) ] * _` between.
    4. A piece's leading `[cN]` groups go to the sentence before it.
    5. Empty pieces are dropped.
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
- **Integration note (orchestrator, 2026-09-26).** This alignment arrived after `feat/fix-it-all` had already aligned the split the
  other way (`f9ddad8e`: the page runs the backend's `SENTENCE_PATTERN`, with Markdown emphasis as a closer, pinned by the shared
  fixture `frontend-v2/src/__tests__/fixtures/deep-sentence-split.json`). The integration keeps that split, because its
  abbreviation guard (`e.g.`, `fig.`, `vs.` …) avoids false "no citation" marks, and adds this commit's setext rule (`===`).
  Everything else here is kept: `method.moves` as per-move counts, the coverage run totals, `/finish` answering
  `{"finishing": true}`, repeated queries allowed, the 2000-character goal cap, and the boundary cases. The two split tests were
  updated to the kept rule: `#hashtag` is prose (CommonMark), and an abbreviation never ends a sentence. The U+0085 case was
  dropped (Python's `\s` differs from JavaScript's there; the page shows counts only).
