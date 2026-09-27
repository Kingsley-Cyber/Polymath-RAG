---
change_id: DEEP-RESEARCH-TUNING
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Three tunings from the live acceptance (register 11.533 / 11.534), owner-approved: a judgement asked as useful / better than / recommended / … is evaluative; a level-2 follow-up that misses the question but fits its own thread is searched (no child); on a phone the composer's option chips fold behind one Options button. Unit and worktree proven on feat/deep-research-tuning; not merged, not deployed."
architecture_impact: "shared/polymath_shared/deep_research/moves.py (_EVALUATIVE, is_evaluative); shared/polymath_shared/deep_research/engine.py (_gate_job, _thread_job, _close_gate, _gate_scores; gate.thread_kept in the moves block); orchestrator/orchestrator/api/deep_research.py (the deep_gate frame carries thread_kept and its label names it); frontend-v2/src/lib/deep.ts (the Method line); frontend-v2/src/screens/Chat.tsx + src/styles/app.css (the folded composer); tests: tests/contracts/test_deep_research_{moves,experience,route}.py, frontend-v2/src/__tests__/chat-composer.test.tsx (new), deep-report.test.tsx; scripts/scaffold_polymath_v4.py (2 TREE entries)."
last_reviewed: 2026-09-27
---

# DEEP-RESEARCH tuning: judgement words, the gate's thread check, the folded composer

## Contract
- The owner approved ("YEA GO") three tunings found by the live acceptance of 2026-09-26/27 (register 11.533, 11.534; plan
  DEEP-RESEARCH-MODE-V1 §10–§11).
  1. **Evaluative questions (§10.3).** Live, "What is Laban's effort theory, and is it useful for film actors?" planned no
     counter-evidence part, because "useful" was not a judgement word. Widen `is_evaluative` conservatively; "good" alone
     stays out.
  2. **The relevance gate keeps a follow-up that fits its thread (§10.4).** Live, the thorough question 5 lost 5 of its 12
     planned searches: level-2 follow-ups scored low against the WHOLE question while drilling correctly into their thread.
     - A level ≥ 2 query under `gate_floor` against the question (and not user-confirmed) is scored once more against its
       thread (`br.node.query`) with the same `gate` port.
     - At or over `gate_floor`: searched, but no children (`br.drift = True`). Otherwise dropped, as before.
     - Level 1 has no thread and is never rescued. A thread check that raises or leaves an item unscored keeps it
       (fail-open, counted).
     - A new counter, `thread_kept`: in the `deep_gate` frame, the receipt's `meta.deep_research.moves.gate`,
       `report_model.method.gate` and the Method tab's relevance line.
  3. **A folded composer on phones (§11.2).** At 375 px the option chips took about 40% of the screen height.
     - At ≤ 560 px (a CSS media query) they fold behind one "Options" button with a one-line summary: the mode, a short model
       name, and "Deep · <depth>" while deep research is on.
     - A tap opens them; `aria-expanded` and an open class follow.
     - Desktop is unchanged.
- Boundaries: worktree `pmv4-drtune`, branch `feat/deep-research-tuning` from `feat/fix-it-all` at `bbaa3b0b`. No live
  system, no register / CONTINUITY / plan edits, no push.

## Changes
- **1 · `moves.py`.** `_EVALUATIVE` also matches, as whole words, any case: useful, usefulness, helpful, valuable,
  recommend, recommended, recommendation, good idea, any good, is it good, better than, worse than, reliable, trustworthy,
  overrated, underrated, work well, works well. The `is_evaluative` docstring lists every word. At breadth 3 the Laban
  question (DEFINITION) now plans 1 broad, 1 deep and 1 inverse query instead of 1 broad and 2 deep.
- **2 · `engine.py`.**
  - `_gate_job` sorts a level as before (confirmed and low = `user_kept`; low; under the spawn floor = drift; unscored =
    fail-open), but holds the low queries back.
  - At level ≥ 2 it hands back `_thread_job` for the first thread: the low follow-ups grouped by the node that planned them,
    in plan order. Each thread job makes one call, `gate(thread_query, items)`, and hands back the next thread's job.
  - The last one calls `_close_gate`: it drops what no score kept, marks every kept low query `drift` (no child), adds the
    counts to the run's and emits ONE `gate` event per level, now with `thread_kept`.
  - `_level` drives that chain to its end before it starts any of the level's searches (one `_drive`, then the next).
  - `_gate_scores` holds the type checks both calls share: a wrong type still raises (the route's bug).
  - A halt that cuts the chain leaves the low queries unfinished and the level's gate uncounted, like a halt during the gate
    call itself today.
  - The receipt's `moves.gate` is `{scored, dropped, user_kept, thread_kept, failed_open}`; `scored` still counts the
    queries scored against the question.
- **2 · route** (`api/deep_research.py`).
  - `_PHASE_FIELDS` carries `thread_kept` into the `deep_gate` frame.
  - The frame's label reads "…: N dropped as off the question, K kept because they follow their thread" ("it follows its
    thread" for one).
  - The `_gate_port` docstring names the thread call. No new route, no new port.
- **2 · the Method tab** (`frontend-v2/src/lib/deep.ts`, `methodLines`). "Relevance check: 12 planned searches scored
  against your question, 3 dropped as off the question, 2 kept because they follow their thread." One reads "1 kept because
  it follows its thread"; with none, nothing is added.
- **3 · `Chat.tsx`.**
  - The chips sit in a new `.composer__options` wrapper, after a new `button.composer__fold`: "▸ Options" and the
    `.composer__fold-summary`.
  - The button carries `aria-expanded` and `aria-controls` (the chips' `useId` id); the chips get `composer__chips--open`
    while open. `optionsSummary()` builds the line; nothing picked = the backend's default model, named.
  - The wrapper stops the click as the chips did, so a tap on the button never focuses the message box.
- **3 · `app.css`.** `.composer__fold` is hidden by default. `@media (max-width: 560px)` shows it and hides `.composer__chips`
  unless it is `--open`. Only tokens and the existing `.disclosure` are used.
- `scripts/scaffold_polymath_v4.py`: TREE entries for `chat-composer.test.tsx` and this work-log.

## Proof
- **Tests first.** Each new test failed before its change, for the reason it names.
  - Item 1: 18 phrase cases and the Laban quota case failed on the old pattern. The 4 neutral cases ("How does light shape
    mood?", "What makes a good shot?", "How do good actors prepare a role?", "What is the bestiary about?") pass before and
    after.
  - Item 2: 7 engine cases failed on the old engine (no thread call; the follow-up was gated):
    - searched without a child: breadth 2 × depth 3, its sibling goes on to level 3;
    - low on both: dropped;
    - level 1: never checked against a thread;
    - fail-open on a raise and on an unscored item;
    - one call per thread, in plan order, and no level-2 search before the last returns (concurrency 3, slowed checks);
    - the counts in the event, the receipt and the method.
  - Item 2, outside the engine: 1 route case (the frame, its label, the receipt, `report_model.method.gate`) and 1 vitest
    case (the Method line, which failed on the base `deep.ts`).
  - Item 3: 2 vitest cases failed with no button. They pin the toggle (`aria-expanded`, the open class, `aria-controls`, a
    real button, the message box not focused) and the summary through mode, model, Deep on, depth and Deep off.
- **Existing tests.** Moves off, and every behaviour the existing DR6 / DR7 tests pin, are unchanged.
  - Five exact assertions of the gate dict (3 in `test_deep_research_moves.py`, 1 in `test_deep_research_experience.py`,
    1 in `test_deep_research_route.py`) failed against the new engine ONLY by the new key. pytest: "Left contains 1 more
    item: {'thread_kept': 0}", the other 4 items identical.
  - Each was widened with `"thread_kept": 0`, as DR7a did for `user_kept` (`6d710009`). Nothing else in them changed; the
    route one's `and len(moves["levels"]) == 2` became its own assert line.
- **A/B, the base engine (`bbaa3b0b`) against this one,** on scripted fake ports (a scratch script, not committed).
  - 210 runs: 7 questions × quick / standard / thorough × (moves off; moves on × no gate, all 0.9, a level-1 query at 0.1, a
    gate that raises) × 1 or 2 books per search.
  - All identical: queries, statuses, learnings, summaries (minus the new key) and report prompts. 132 of them reach level 2.
  - A run whose level-2 follow-ups score 0.1 against the question and 0.5 against their thread differs as intended: the base
    gated them, this engine searches them.
- **The composer, measured in a real browser.** A scratch page held the Chat screen's rendered markup with tokens, app and
  deep CSS, base against new, each page loaded fresh at each width.
  - At 1280, 800, 600 and 561 px every chip box and the Send button are identical, and the button is hidden.
  - At 375 px the composer (without its text box) goes from 168 to 62 px: the chips' 138 px become one 30 px row. Opened, it
    is 204 px. `scrollWidth` is 375 at phone width, open or closed.
- **Guards** on the final tree:
  - `tests/contracts` (`-k "not test_live_"`): 640 passed (609 at `bbaa3b0b`, +31 new);
  - `tsc --noEmit` exit 0; vitest (live-contract excluded): 18 files, 134 tests passed (131 at `bbaa3b0b`, +3 new);
  - `agent_preflight` ok, `repo_guard` ok, `wiki_worm --check` ok;
  - ruff: no new findings. The five deep research files are clean; `scripts/scaffold_polymath_v4.py` keeps the 6 findings
    it has at `bbaa3b0b` (unused imports, a shebang, `date.today()`, a slice), none added.
  - The vitest suite's proxy test fetches the live `:7200/openapi.json`. A scratch preload made that fetch fail fast, so the
    test skipped as designed, except in the first full run of this slice, which made that one read-only GET.

## Rejected claims
- "A follow-up that fits its thread should spawn too": no, the owner's rule. A thread check is one step; the spawn floor
  stays on the question's score, so a kept follow-up ends its thread (tested at depth 3).
- "`scored` should count the thread checks": no. It stays the queries scored against the question, so "N scored, D dropped,
  K kept because they follow their thread" adds up.
- "'good' makes a question evaluative": no. "What makes a good shot?" asks for no judgement; "good idea", "any good" and "is
  it good" do.
- "The fold moves the desktop layout": no, measured identical above 560 px.

## Open contract gaps
- Live proof after the owner's deploy, 2 runs:
  - DR6d question 5 (thorough, moves on): the Method tab should name follow-ups kept by their thread; compare its books with
    9 (moves, 11.534) and 12 (the old loop);
  - the Laban question: its plan card should show a Counter-evidence part.
- The thread check reuses `gate_floor` 0.2, unmeasured on real plans. Each check is one more reranker call: at most one per
  thread holding a low follow-up, each bounded by the probe gate's 3 s timeout.
- Plan §10.3 and §10.4 still list the old words and the question-only gate. The plan note and the register row are the
  lead's: this slice made no plan or register edits.
- The fold is not remembered across reloads. The summary names mode, model and depth only (Reasoning and Corpus Explore stay
  behind the button), as specified.
