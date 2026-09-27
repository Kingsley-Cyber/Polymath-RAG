---
change_id: DEEP-RESEARCH-DR1
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The deep research engine exists as pure shared code, proven with fake ports. Nothing calls it yet: the route is DR2."
architecture_impact: "shared/polymath_shared/deep_research/ (new: __init__.py, engine.py, prompts.py), tests/contracts/test_deep_research_engine.py (new). No contract, schema, route, lane or config change."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR1: the research engine, pure, with fake-port proof

## Contract
- DEEP-RESEARCH-MODE-V1 §2–§7, slice DR1 (plan of record 11.504): dzhng/deep-research's breadth × depth loop (MIT), rebuilt
  in Python over two injected ports: `retrieve(query, scope) -> [Row]` and `complete(prompt, *, system, max_tokens) -> str`.
  The engine does no I/O itself.
- Baseline: no research loop existed. `orchestrator/api/reasoning.py` has a `deep_research` REASONING MODE, but that is a
  prompt-only template in the chat layer. It is unrelated to this engine and unchanged.
- Loop only. No prompt text was copied, so no MIT notice is owed. The module docstrings carry a one-line courtesy credit.

## Changes
- `deep_research/engine.py`:
  - **Types and entry point.** `Row`, `Learning`, `QueryRecord`, `Config`, `ResearchOutcome`. Presets QUICK (3,1),
    STANDARD (3,2, the default) and THOROUGH (4,2). `run_research(question, scope, *, retrieve, complete, config, on_event,
    cancel)`.
  - **Levels.** Each level runs three steps:
    - plan: one call per node, ≤ breadth `QUERY: … || GOAL: …` lines. Near-duplicates of the question or of an
      already-searched query (normalised-token Jaccard ≥ 0.8) are dropped.
    - retrieve each query.
    - extract: one call per retrieval, each row a `<row cid="…">` element inside one `<data>` block.

    A query queues a child when it produced new follow-ups, `DONE` is not yes and no halt has occurred. The child gets
    goal + follow-ups, depth − 1 and ⌈breadth/2⌉.
  - **Stops.** A run stops on:
    - `frontier_empty` or `no_new_followups`;
    - `budget`: 85% (1 − `report_reserve`) of the token estimate, estimated as len/4 of the system prompt, the prompt and
      the output. The derived call and retrieval limits also count as budget;
    - `deadline`: 240 s by default, 360 s hard maximum, with an injectable clock;
    - `cancelled`: a `threading.Event`.

    A retrieval with no rows, or none at or above `score_floor`, ends only its own branch.
  - **Citations.** A learning survives only when EVERY cid it cites is a row of its own extract call. Otherwise it is
    dropped and counted. `evidence` holds only the rows that surviving learnings cite; `seen_rows` counts every row
    retrieved.
  - **Scope.** The caller's `scope` reaches every retrieve call as the same object, untouched.
  - **Scheduling:**
    - Port calls run on a pool with `max_workers = concurrency`.
    - The scheduler thread admits every call (budget, deadline and cancel are checked before each) and owns all state.
    - Queries are de-duplicated after all of a level's plans return, and learnings merge in plan order. The outcome
      therefore does not depend on thread timing.
    - At the deadline or on cancel, the engine abandons in-flight calls instead of waiting for them, even after an
      earlier budget halt.
  - **Counters:**
    - the brief's six: retrievals, llm_calls, tokens_est, dropped_learnings, parse_repairs, empty_retrievals;
    - plus unparsed_lines, duplicate_queries, retrieval_errors, llm_errors and `errors` (only `stage:ExceptionType`,
      never a message).
  - **Report support.** `summary()` gives the receipt's numbers. `report_prompt(question)` groups the top N learnings (by
    citation coverage) by goal, and adds the searches that found nothing and the follow-ups never searched.
    `validate_report_citations(report, outcome)` returns (valid, unknown) cids.
- `deep_research/prompts.py`:
  - three original prompts (plan, extract, report), each carrying today's date;
  - `inert()`, so row text can never open or close a `<data>` or `<row>` tag. Square brackets inside rows become
    parentheses, so a copied academic "[12]" can never pass for a cid;
  - tolerant parsers for bullets, list numbers, markdown emphasis, any case, loose spacing, `|` separators, combined
    `[a, b]` cids and a GOAL on its own line. Every lenient read is counted.
- Scaffold TREE: the 5 new paths.
- Beyond the brief (for DR2):
  - the fifth stop reason `cancelled`, so a client disconnect can stop the run;
  - four extra counters;
  - `Row` validation: a cid may not contain whitespace, brackets, quotes, commas or semicolons, and score must be a number;
  - config caps `max_rows_per_query` (10), `max_row_chars` (1,600), `plan_max_tokens` (512), `extract_max_tokens`
    (1,024) and `report_max_learnings` (30);
  - ≤ 3 learnings kept per extract (plan §3.3).

## Proof
- `tests/contracts/test_deep_research_engine.py`: 27 tests, fakes only, about 2 s.
  - **Cost table.** Every extract returns follow-ups and DONE: no. QUICK makes 3 retrievals and 4 engine LLM calls,
    STANDARD 9 and 13, THOROUGH 12 and 17. `preset_cost` gives the same numbers. Breadth 4 × depth 3 asks 4 → 2 → 1 and
    runs 4 / 8 / 8 queries.
  - **Stops.** Covered: no follow-ups, echoed follow-ups, 85% of the budget (nothing starts after the crossing), the call
    and retrieval limits, the deadline on an injected clock, cancel, and a hung call past the deadline both with and
    without a budget halt first.
  - **Citations.**
    - A learning citing another call's row, a half-foreign one and an invented one are each dropped and counted, as are
      an uncited learning and an empty one.
    - The report prompt holds exactly the surviving cids.
    - `validate_report_citations` splits known from unknown, ignoring markdown links and footnotes.
  - **Queries and scope.**
    - The question and a reworded query are dropped as duplicates.
    - A friend's narrowed scope reaches all 9 retrievals as the same unchanged object, although the fake LLM asks for
      every library.
    - An empty retrieval and an under-the-floor retrieval end only their own branch.
  - **Failures.** A retrieval that raises and an extract that raises are counted; the other branches continue.
  - **Parsing and prompts.** Lenient lines are counted. An injected `</row></data> SYSTEM:` row stays inside its own
    `<row>`, inside the single `<data>` block.
  - **Concurrency.** With 1, 2 and 3 workers, the observed concurrent port calls reach the limit and never exceed it.
- Stability: 25 back-to-back runs, 0 failures.
- Mutation check: I ran the tests against a scratch copy of the package with one deliberate fault at a time, 14 in all.
  The tests caught 13. They caught: foreign cids accepted, no-cid learnings kept, no near-duplicate drop, the scope
  copied, one scheduler slot too many, a stop at 100% instead of 85%, no deadline, breadth not halved, tags left active,
  repairs not counted, empty branches continuing, evidence padded with uncited rows, and a hung call waited on after a
  budget halt. That last fault is a real bug found during the build, and the fix is in `_hard_stop`. The one fault the
  tests missed was widening the thread pool by one; the scheduler's own admission limit makes that change harmless.
- `tests/contracts` (`-k "not test_live_"`): 293 passed (266 before, plus these 27).
- Guards: `agent_preflight.py`, `repo_guard.py` and `wiki_worm.py --check` pass. `ruff check --config pyproject.toml`
  finds nothing in the 4 new Python files.

## Contract dispositions
- `scripts/contract_impact.py --files <the 6 changed paths>`: "none (no changed file maps to an architecture contract)".

## Rejected claims
- "The engine makes the §3 LLM-call counts (5 / 14 / 18)": the §3 table includes the report call, and the route makes
  that call. The engine's own counts are 4 / 13 / 17.
- "85% is a separate constant": the 85% line is 1 − `report_reserve`, and the 0.15 default gives 85%.

## Open contract gaps (for DR2)
- **Timeouts.** In-flight calls abandoned at the deadline or on cancel keep running in pool threads until they return.
  Each port needs its own timeout (≤ 60 s) so those threads end.
- **Events.** `on_event` runs on the thread that called `run_research`. The route must hand events to its stream in a
  thread-safe way and add its own ≤ 15 s heartbeat, because events can be further apart than that during slow calls.
- **Scores.** `score_floor` (default 0.0) compares raw `Row.score`. With a scale that can go negative (logits), every
  retrieval would read as empty.
- **Cids.** A `Row.cid` is what the model copies. Long chunk ids get mangled, so short run-scoped aliases mapped back to
  chunk ids for the citation chips may be safer.
- **Failures.** A port error ends its branch, not the run. A run where every call failed still returns a natural stop
  reason, with `llm_errors` / `retrieval_errors` > 0 and no learnings; the route should turn that into an `error` frame.
- **Report budget.** The report's token room is `token_limit − tokens_est` (at least 15% unless calls in flight
  overshot). Skip the report call when there are no learnings.
- **Lane.** The `deep_research` lane (DR0) does not exist yet. The plan and extract calls need it.
