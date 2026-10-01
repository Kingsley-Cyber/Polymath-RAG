# unit: shared/polymath_shared/deep_research/engine.py
anchor: shared/polymath_shared/deep_research/engine.py:1-1116

## purpose
DEEP-RESEARCH-MODE-V1 engine (slice DR1): a breadth × depth research loop run over the caller's own libraries via injected ports (`retrieve`, `complete`, optional `gate`). Pure module: no I/O, no network, no Polymath imports; the route (DR2) owns transport. — engine.py:1-11 [DERIVED]
Loop modeled on dzhng/deep-research (MIT), no text copied; tree walked one level at a time so progress streams, budget/deadline checked before every port call. — engine.py:1-2, 13-15 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| run_research | func | (question, scope, *, retrieve, complete, config=None, on_event=None, cancel=None, gate=None, finish=None, plan=None) -> ResearchOutcome | engine.py:315-333 | shared/polymath_shared/deep_research/_small-modules |
| plan_goals | func | (question, *, complete, config=None) -> PlanDraft | engine.py:346-351 | shared/polymath_shared/deep_research/_small-modules |
| Config | class | frozen dataclass; `Config.preset(name, **overrides)`; properties retrieval_limit / llm_call_limit / token_limit / stop_tokens | engine.py:162-241 | — |
| Row | class | frozen dataclass (cid, text, source, score, doc_id="", title="") | engine.py:76-94 | — |
| Learning | class | frozen dataclass (text, cids, goal, depth, query="", move="broad", goal_id="", doc_ids=()) | engine.py:98-106 | — |
| QueryRecord | class | frozen dataclass (id, node, query, goal, depth, rows=0, status="unfinished", move="", goal_id="") | engine.py:110-119 | — |
| Goal | class | frozen dataclass (id, goal, query, move) | engine.py:123-129 | — |
| ResearchOutcome | class | frozen dataclass; `report_prompt(question, *, max_learnings=None) -> (system, prompt)`; `summary() -> dict` | engine.py:260-306 | — |
| PlanDraft | class | frozen dataclass (goals, parse_repairs, unparsed_lines, duplicate_queries, inverse_unanchored) | engine.py:337-343 | — |
| preset_cost | func | (breadth, depth, first=None) -> (plans, retrievals, extract calls) | engine.py:147-158 | — |
| estimate | func | (config, *, planned=False) -> {"searches", "llm_calls", "seconds"} | engine.py:244-250 | — |
| top_learnings | func | (learnings, n) -> list[Learning] | engine.py:253-256 | — |
| validate_report_citations | func | (report_text, outcome) -> (valid cids, unknown cids) | engine.py:309-312 | — |
| RetrievePort / CompletePort / GatePort | Protocol | `__call__(query, scope) -> Sequence[Row]` / `__call__(prompt, *, system, max_tokens) -> str` / `__call__(question, items) -> Mapping[str, float]` | engine.py:132-144 | — |

## contracts

**run_research** — engine.py:315-333
- in: `question` non-empty str (else ValueError, engine.py:437-438); `scope` opaque — passed to every retrieve call as the exact object the caller passed; no LLM output touches it (K1: an LLM never widens a scope) — engine.py:16-17 [DERIVED]
- in: `plan` = confirmed level-1 as (goal, query, move) items, 1..2 × breadth, replaces the level-1 planner call; every item is searched, gate never drops it; if `cfg.first_width is None` it is set to `len(seed)` — engine.py:325-332 [DERIVED]
- pre: `gate` read only when `config.moves`; `cancel`/`finish` are threading.Event — engine.py:320-324
- post: returns ResearchOutcome with a stop_reason from STOP_REASONS; `on_event` is called from the scheduler thread only, never from the pool — engine.py:320-321, 56-57
- cancel: run stops within ~`_POLL_S` = 0.25 s; in-flight port calls abandoned, not awaited — engine.py:320-321, 67

**plan_goals** — engine.py:346-351
- in: one complete port; makes exactly one planner call and accepts it exactly as a run would (quota order, leftovers, duplicates, unanchored inverse queries) — engine.py:347-349
- out: PlanDraft; a complete-port error propagates — engine.py:348-349
- pre: retrieve is `_no_search`, which raises `RuntimeError("plan_goals never searches")` — engine.py:354-355

**Config** — engine.py:162-241
- defaults: breadth=3, depth=2, concurrency=2, deadline_s=240.0, report_reserve=0.15, score_floor=0.0, max_rows_per_query=10, max_row_chars=1600, plan_max_tokens=512, extract_max_tokens=1024, report_max_learnings=30, moves=False, gate_floor=0.2, spawn_floor=0.35, first_width=None, clock=time.monotonic — engine.py:165-184
- post: `None` budgets re-derived from breadth × depth × HEADROOM via `dataclasses.replace` — engine.py:163-164, 216-236
- presets: quick=(3,1), standard=(3,2), thorough=(4,2) — engine.py:49-50

**Row** — engine.py:76-94
- pre: `cid` must fullmatch `_CID = re.compile(r"[^\s\[\]<>\"',;]{1,200}")` — 1-200 chars, no whitespace/brackets/quotes/commas/semicolons (downstream parsers split on those) — engine.py:68, 77-78, 87-88
- raises: ValueError (bad cid), TypeError (text/source not str; score not number or is bool; doc_id/title not str) — engine.py:87-94

**ResearchOutcome** — engine.py:260-306
- `evidence` holds only rows a surviving learning cites, first-citation order; a learning survives only when ALL its cids are rows of the call that produced it, others dropped and counted — engine.py:19, 262, 271
- `errors` entries are `"stage:ExceptionType"`, never the message (may carry source text) — engine.py:278

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read / tables_written empty) [DERIVED]
- Network / files / subprocess / env flags: none — module docstring "no I/O, no network, no Polymath imports" — engine.py:4 [DERIVED]
- Threads: `ThreadPoolExecutor(max_workers=cfg.concurrency, thread_name_prefix="deep-research")` per run — engine.py:476
- Clocks: `_dt.datetime.now(_dt.UTC).astimezone().date().isoformat()` for `today` — engine.py:441; `cfg.clock()` (default `time.monotonic`) for the deadline — engine.py:180, 442, 583
- All external effects flow through the injected `retrieve` / `complete` / `gate` ports — engine.py:7-9 [DERIVED]

## invariants
INVARIANT: Config.breadth ∈ 1..MAX_BREADTH(6) and Config.depth ∈ 1..MAX_DEPTH(4) — engine.py:61, 186-188 [DERIVED]
  fails-if: ValueError at construction; a run never starts.
INVARIANT: Config.concurrency ∈ 1..MAX_CONCURRENCY(8) — engine.py:61, 193-194 [DERIVED]
  fails-if: ValueError; pool size would be invalid.
INVARIANT: 0 < Config.deadline_s ≤ DEADLINE_HARD_MAX_S(360.0) — engine.py:60, 195-196 [DERIVED]
  fails-if: ValueError; run could outlive the hard cap.
INVARIANT: derived retrieval_limit = ceil(preset_cost(breadth, depth, first_width)[1] × HEADROOM(1.25)) — engine.py:62, 216-219 [DERIVED]
  fails-if: a full run trips "budget" before finishing its preset shape.
INVARIANT: stop_tokens = round(token_limit × (1 − report_reserve)); default reserve 0.15 → engine stops at 85% of max_tokens — engine.py:172, 239-241 [DERIVED]
  fails-if: report call has no token reserve left.
INVARIANT: two queries are near-duplicates when normalised-token Jaccard ≥ NEAR_DUPLICATE(0.8) — engine.py:63, 376-377 [DERIVED]
  fails-if: same query re-searched, wasting retrievals; counter duplicate_queries drifts.
INVARIANT: preset_cost is an upper bound — a plan keeps ≤ breadth queries, each query spawns ≤ 1 child; nothing exceeds (plans, retrievals, extracts) of a full run — engine.py:148-149, 158 [DERIVED]
  fails-if: derived budgets under-provision a legal run.
INVARIANT: Row.cid matches `[^\s\[\]<>\"',;]{1,200}` — engine.py:68, 87-88 [DERIVED]
  fails-if: ValueError; citation parsers downstream would mis-split.
INVARIANT: confirmed plan length ∈ 1..2 × Config.breadth; moves on ⇒ every move ∈ M.MOVES — engine.py:360-366 [DERIVED]
  fails-if: ValueError from _check_plan before the run starts.
INVARIANT: `coverage_complete` early stop only when intent ∈ COVERAGE_STOP_INTENTS({"EXACT","DEFINITION"}) or levels ≥ 2 — engine.py:55, 469-471 [DERIVED]
  fails-if: a non-lookup question stops after level 1 (the DR6d bug: thorough runs read 5 books, not 12) — engine.py:53-54.

## determinism & idempotency
determinism: NONDETERMINISTIC (concurrency: ThreadPoolExecutor engine.py:476; clock: `_dt.datetime.now` engine.py:441) — but the outcome is timing-independent by design: queries de-duplicated in frontier order after a level's plans all return, learnings merge in plan order after extracts return; only halts cut a level short — engine.py:20-22 [DERIVED]
idempotency: SAFE (engine holds no external state; all effects go through injected ports, scope passed through untouched) — engine.py:4, 16-17 [INFERRED: no writes visible in SOURCE]

## failure behaviour
- Constructor validation raises immediately: ValueError for bad cid / all Config ranges / unknown preset / bad confirmed plan / empty question; TypeError for wrong Row field types — engine.py:87-94, 186-205, 212, 361-366, 437-438 [DERIVED]
- Halts cut the run and become the stop_reason: "budget" (llm/retrieval/token limits, engine.py:599-600, 610-611, 584-585), "deadline", "cancelled", "finished_early" (finish: in-flight calls finish and merge, nothing new starts) — engine.py:576-586, 320-324 [DERIVED]
- Cancel/deadline are hard stops even after a budget halt: in-flight calls abandoned via `pool.shutdown(wait=False, cancel_futures=True)` — engine.py:491, 588-594 [DERIVED]
- Port exceptions are swallowed into counters, not raised: plan LLM error → `llm_errors` + `errors["plan:…"]`, node planned as None — engine.py:625-629; retrieval/LLM errors end that branch/node — engine.py:276-277 [DERIVED]
- plan_goals is the exception: a complete-port error propagates to the caller — engine.py:348-349 [DERIVED]
- Queued-but-never-planned followups surface as `open_followups`, not errors — engine.py:488-489, 280 [DERIVED]
- Gate failures are tracked by `gate_failed_open` — engine.py:463 [INFERRED: counter name implies gate errors fail open; handling body beyond shown excerpt]

## dumb-code flags
- `report_max_learnings` default `30` duplicated: Config field (engine.py:178) and ResearchOutcome field (engine.py:283); report_prompt prefers the outcome's copy — engine.py:291 [DERIVED]
- `LEARNINGS_PER_EXTRACT = 3` defined at engine.py:64; no reference visible in the shown excerpt (lines 1-664) — [DERIVED]
- Magic timing pair `ESTIMATE_BASE_S, ESTIMATE_PER_SEARCH_S = 10.0, 11.0`, hand-fit to five live runs (38-47 s for 3 searches, 98-115 s for 9, 132 s for 12) — engine.py:58-59 [DERIVED]
- Two different deadline numbers: default `deadline_s = 240.0` (engine.py:168) vs cap `DEADLINE_HARD_MAX_S = 360.0` (engine.py:60) [DERIVED]
- Token accounting is the crude `len(text) // 4` estimate, applied at three sites — engine.py:512, 630, 1030 [DERIVED]
- `Learning.move` defaults to `"broad"` even with moves off — engine.py:104 [DERIVED]
- Halts are sticky by design: `jobs.clear()` on a failed admit means a halt discards all queued jobs — engine.py:557-559 [DERIVED]

## refactor notes
- `Config.moves = False` must keep DR1 behaviour "byte for byte"; any change to the shared `_Run` path must be tested with moves off — engine.py:181 [DERIVED]
- Blast radius: imported by `shared/polymath_shared/deep_research/_small-modules`; internal deps are sibling modules `evidence` (E), `moves` (M), `prompts` (P) — engine.py:44-46, FACTS.importers [DERIVED]
- Scope opacity (K1) is a security contract: keep `scope` unreachable from LLM output; retrieve-port signature extensions go through kwargs (`move=…, anchor_docs=…`) — engine.py:16-17, 133 [DERIVED]
- `on_event` must stay on the scheduler thread only; moving it to pool threads breaks the documented callback contract — engine.py:320-321 [DERIVED]
- Row.cid's character ban is load-bearing for downstream parsers; loosening `_CID` requires updating them — engine.py:77-78 [DERIVED]
- Config is frozen and limits are derived properties; adding budget fields means updating `retrieval_limit` / `llm_call_limit` / `token_limit` / `stop_tokens` together so `replace()` re-derives correctly — engine.py:163-164, 216-241 [DERIVED]

## VERIFY
```verify
grep -Fq 'NEAR_DUPLICATE = 0.8' shared/polymath_shared/deep_research/engine.py
grep -Fq 'HEADROOM = 1.25' shared/polymath_shared/deep_research/engine.py
grep -Fq 'DEADLINE_HARD_MAX_S = 360.0' shared/polymath_shared/deep_research/engine.py
grep -Fq 'QUICK, STANDARD, THOROUGH = (3, 1), (3, 2), (4, 2)' shared/polymath_shared/deep_research/engine.py
grep -Fq 'plan_goals never searches' shared/polymath_shared/deep_research/engine.py
grep -Fq 'Follow-up directions:' shared/polymath_shared/deep_research/engine.py
test "$(grep -c -F 'ValueError' shared/polymath_shared/deep_research/engine.py)" -ge 10
```
