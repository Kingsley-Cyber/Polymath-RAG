---
change_id: DEEP-RESEARCH-DR7-UI
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The research experience, frontend (DR7c-e): the plan card, the live research view with Finish now, the report view (TL;DR, Evidence / Sources / Method tabs, the audit's no-citation marks, Markdown export, Research this next) and the Reports list. Built against §11.3 with fake frames; the backend (DR7a-b) is a parallel slice."
architecture_impact: "frontend-v2 only. New: src/lib/deep.ts, src/styles/deep.css, src/components/deep/{PlanCard,LiveResearch,DeepReport,remarkUncited,ResearchTurn,ReportsList,DeepResearchSettings}.tsx|ts, src/__tests__/{deep-research-ui,deep-report}.test.tsx. Small edits: src/screens/Chat.tsx (sendDeep plans first; startDeep; TurnView hands research turns to ResearchTurnView), src/lib/chat.ts (Turn.deepRun / deepCoverage, the coverage frame), src/lib/api.ts (deepResearchPlan, deepResearchFinish), src/lib/contracts.ts (§11.3 types), src/App.tsx + src/screens/Research.tsx (Reports tab, open a report at its turn), src/screens/Settings.tsx (the setting), src/__tests__/chat-deep.test.tsx (one line: the DR3 cases opt into the direct send)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR7c–e: the research experience (frontend)

## Contract
- DEEP-RESEARCH-MODE-V1 §11.2 parts 1–5 and §11.3 (register 11.529); slices DR7c, DR7d, DR7e and the UI half of DR7a. The
  owner, 2026-09-26: "go ahead, build it all".
- Built against §11.3's names with fake fetch replies and fake SSE frames; the backend is being built at the same time.
  Every field the UI reads is optional, so today's backend and turns already saved in browsers still draw.
- Details §11.3 leaves open, and the shape chosen (the backend has to match the ones marked **must**):
  - **Requests.**
    - `POST /research/deep/plan` sends `{question, corpus_id, preset, mode}`.
    - `POST /research/deep` sends today's `{question, corpus_id, preset, mode, synthesizer?}` plus, after the card,
      `plan: [{goal, query, move}]`. At most 2 × breadth parts (6 / 6 / 8); each part needs 3+ characters. A part the
      person edited or added searches its own text (`query` = the goal, clipped at 300 characters).
    - `POST /research/deep/finish` sends `{}`. 202 = finishing (a JSON body is expected; an empty body is taken as accepted).
      404 = "Nothing to finish: this research has already stopped searching."
  - **Older backend.** The UI falls back to today's direct send in three cases:
    - the plan route answers 404 / 405 with no `detail.error_code` (FastAPI's missing route);
    - it answers 403 `ROUTE_NOT_ALLOWED` (an older web boundary, which fails closed);
    - it returns a plan with no goals.
    Any other error is shown on the turn, and nothing runs.
  - **Goal ids (must).** A confirmed plan carries no ids, so the UI numbers its goals by position in the plan response's own
    scheme: `1.1, 1.2, …` stays `1.1, 1.2, …` after a removal. DR6a names a level-1 goal by its query id. Another scheme
    falls back to `g1, g2, …`. A coverage entry whose id is unknown maps to the confirmed goal at its position.
  - **Frames read.**
    - `event: coverage`, `data: {goals: [{id, learnings, documents}], documents?, passages?}`. A goal's `documents` is a
      count, or the doc ids. The top-level `documents` / `passages` are run totals and optional. A `phase` frame carrying
      `goals` is read the same way.
    - `deep_retrieve` / `deep_extract` frames (DR6 sends `move` and `query`; DR7 adds `goal_id`) become the activity feed,
      one row per search, keyed by `query`. When present, the UI also reads `rows` (passages), `status` (`empty` / `error`)
      and `new_learnings` (findings).
    - `deep_gate` is shown as a note. `deep_level_done.new_learnings` counts findings until coverage frames come.
    - `deep_report` means "Writing the report": Finish now hides.
  - **Answer meta read.**
    - The report view is used when `meta.deep_research.report_model` is present, and reads its
      `goals[].{id, goal, findings[].{text, cids, confidence, move}, documents}`, `counter[].{text, cids, goal_id}`,
      `open_questions[]` (strings or `{question|text}`, first 5) and `sources[].{doc_id, title, cids, findings}`.
    - `confidence`: `strong | single_source | contested`, in any case; `single` is accepted.
    - The Method tab reads these keys of `method`: `preset, intent, evaluative, searches, moves, learnings, gate{scored,
      dropped, failed_open, user_kept}, stop_reason, elapsed_s, model`. Keys it lacks come from the run's counts, then from
      DR6's `moves` block (`levels[].searched`, `gate`, `intent`, `evaluative`).
    - Stop reasons are put in words, `coverage_complete` and `finished_early` included.
    - The counter-evidence line is DR6c's, from `moves.inverse`, with the same words and class.
  - **The audit's sentence split (must match).** It is `auditSentences` in `src/lib/deep.ts`:
    1. The prose is read line by line. Skipped: blank lines, headings (`#` first), fenced code (the fences too), table
       rows (`|` first) and rules (`---`, `***`, `___`, `===`).
    2. A kept line loses its leading `>` and list marker.
    3. The line is split at each whitespace run that follows `.`, `!` or `?`, optionally followed by closing quotes, `)`,
       `]`, `*` or `_`.
    4. A piece that begins with citation groups (`[c3]`, `[c3, c4]`, not followed by `(`) gives them to the sentence
       before it.
    5. Empty pieces are dropped. The indices count the kept sentences from 0.
    The marks are placed only when the UI's count equals `audit.sentences` and every flagged sentence really has no valid
    `[cN]`. Otherwise the view shows the counts alone and says the sentences could not be matched.
  - **The TL;DR block.** It is the section under an opening "TL;DR" (or Summary / In short / Short answer / Answer /
    Bottom line / Key takeaways) heading, else the prose before the first heading. A report with no heading gets no box.
  - **The Markdown export.**
    - The file starts with `# <question>`.
    - In the prose, `[cN]` and `[cN, cM]` become `[^cN]` and `[^cN][^cM]`. Code and links are left alone.
    - The footnotes read `[^cN]: Title — where`, in first-cited order. "where" is the citation's `source`, dropped when it
      equals the title. An unknown id reads "cited, but not found in the research".
    - The file is named `deep-research-<slug>.md`.
  - **Browser state.**
    - The setting is `localStorage["polymath.deep-research.skip-plan"] = "1"`, read in a try / catch like the appearance
      store.
    - The estimate of a run sent without a plan is the top of §3's range: 40 s, 120 s or 150 s.

## Changes
- **Plan card (DR7a UI).**
  - `sendDeep` now posts `/research/deep/plan` first.
  - The card shows "I'll research this in N parts". Each goal is an editable text with its move in plain words: Main answer
    = broad, Deeper = deep, Connections = adjacent, Counter-evidence = inverse. Parts can be removed, and "Add a part" adds
    one.
  - It also shows the library, the depth, the estimate and the question type.
  - **Start** carries a 10 s countdown on the button. The countdown stops for good when the person focuses, clicks, types
    in or edits the card, and "touched" is kept on the turn, so an edited plan never auto-starts after a chat switch.
  - **Cancel**, or Stop in the composer, drops the plan. The plan's wait is registered like a stream, and the question goes
    back into the box.
  - "Start deep research without showing the plan" appears on the card and in Settings, and both read one store.
  - Start sends `plan`.
- **Live research view (DR7c).** For a research turn it replaces the process rail:
  - a checklist of the goals with coverage meters (findings · books; 2 and 2 = covered, per §11.4) and the goal being
    searched;
  - a collapsible activity feed: "Main answer · <query> — 10 passages · 2 findings", "nothing in the libraries", and the
    relevance check's note;
  - counters for books, passages and findings (the answer's exact counts once it is in) and the elapsed time against the
    estimate;
  - **Finish now** posts `/research/deep/finish` and shows "Finishing…". **Stop** is the existing cancel.
  - When the turn ends, the view folds into one line.
- **Report view (DR7d).** It is used when `report_model` exists. Otherwise today's AnswerBody and DeepSources stay, so
  older saved turns and older backends are unchanged.
  - The TL;DR comes first in its own box, then the prose with the same citation chips (`components/Citations.tsx`).
  - Each uncited sentence gets a dotted underline and a "no citation" tag. A remark step places them from source offsets,
    the TL;DR slice included. A note above gives the counts and any cited id the research did not hold.
  - Tabs: Report / Evidence / Sources / Method.
    - Evidence: per goal, each finding with its badge (Strong / Single source / Contested), the goal's counter-evidence,
      loose counter-evidence, and the open questions.
    - Sources: by book, the passages used and how many findings each supports.
    - Method: in plain words.
  - The tabs follow the arrow keys, Home and End.
  - **Copy as Markdown** and **Download .md** give the footnoted file.
  - **"Research this next"** chips come from `open_questions`. A chip fills the composer, turns Deep research on and sets
    the depth to Quick. It sends nothing.
- **Reports list (DR7e).** The Research section gains Runs / Reports tabs.
  - Reports lists this browser's finished deep research turns from the chat history, newest first: question, date,
    library, depth and findings.
  - Opening one goes to its chat and scrolls to that turn.
  - A one-line note says the list is kept in this browser only, like chats.
  - A turn saved before DR7 has no start time and no research state. Its date is its chat's last change, and its library
    is its chat's.
- **Wiring.**
  - `api.deepResearchPlan` and `api.deepResearchFinish` are in the existing style, so the live contract test reads them
    after the deploy.
  - `Chat.tsx` keeps building `deepRequest`, now with `deepRequest.plan`.
  - `runTurn` stores `coverage` frames in `turn.deepCoverage`.
  - `Turn.deepRun` holds the plan, the draft, the confirmed goals, the start time and Finish now.
  - `TurnView` hands research turns to `ResearchTurnView` in one line.
  - `ProcessRail.tsx` and `AnswerBody.tsx` are untouched.
- **An existing test.** In `chat-deep.test.tsx`, one line in `beforeEach` turns on the skip-plan setting. DR7a changes the
  default Send (the plan comes first), and these DR3 cases pin the direct send. Their assertions are unchanged.

## Proof
- `npx tsc -p . --noEmit`: clean.
- `npx vitest run --exclude src/__tests__/live-contract.test.ts`: **125 passed** in 16 files. The baseline was 89 in 14
  files; 36 are new.
- `deep-research-ui.test.tsx` (20) runs through the real app:
  - the card appears; edits, removal, adding a part and a move change apply; Start sends exactly the confirmed `plan`;
  - it auto-starts at 10 s (fake timers); a focused card never starts by itself; Cancel sends nothing and gives the
    question back;
  - the skip-plan setting skips the card; the card and Settings share it;
  - 404 / 405 / 403 `ROUTE_NOT_ALLOWED` fall back to the direct send; a 503 is shown and nothing runs;
  - coverage frames and each frame's `goal_id` feed the checklist, the counters and the feed; unknown coverage ids map by
    position;
  - Finish now posts `/research/deep/finish` and does not stop the stream; a 404 is explained; Stop cancels;
  - a "Research this next" chip fills the composer (Deep research on, Quick) and posts nothing;
  - a deep turn saved before DR7 still renders the process rail and the sources list;
  - the Reports list reads the chat store, leaves out chat turns and opens a report at its turn;
  - the Research tabs follow the arrow keys and keep the keyboard focus across the switch.
- `deep-report.test.tsx` (16):
  - the tabs, the TL;DR box and the counter-evidence line;
  - the three uncited sentences are underlined with "no citation", including inside bold and in the TL;DR slice;
  - the counts alone when the audit's sentence count differs, or when it flags a sentence that is cited;
  - the badges, the counter-evidence and the open questions; sources by book; the Method lines;
  - arrow-key tabs;
  - the chips' callback;
  - the exact footnoted Markdown; Copy and Download;
  - the sentence split; the TL;DR split; the id scheme; a run without a plan named from its searches; an older run's
    Method.
- In a real browser (the Browser pane), the worktree's UI was served by vite. Its API was proxied to a FAKE backend in the
  scratchpad on 127.0.0.1:7299, never :7200. The whole path ran: plan card, auto-start, live view, report, tabs, Reports
  list, Settings.
  - Checked at 1280 px (light), 768 px (light) and 375 px (dark).
  - `document.documentElement.scrollWidth` equalled the viewport width at each size, and no element under the chat ran past
    the right edge.
  - The check found and fixed a stray scrollbar in the tab row and the chips' accessible names.
- The live contract test was not run: `/research/deep/plan` and `/research/deep/finish` are not on the live server yet.

## Rejected claims
- "The confirmed goals can be numbered g1…gN": DR6a names a level-1 goal by its query id (`1.2`). The UI follows the plan's
  own scheme and maps coverage by position when the ids differ.
- "Any 404 from the plan route means an older backend": a 404 with an error code comes from the route itself and is shown.
  An older web boundary refuses the unknown route with 403 `ROUTE_NOT_ALLOWED`, not 404, so that case also falls back.
- "The books counter can be summed from per-goal counts": goals share books. The counter shows only an exact number: the
  frame's total, the union of doc ids, or the report's sources. Otherwise it stays hidden.

## Open contract gaps
- **The backend (DR7a–b) must:**
  - classify `POST /research/deep/plan` and `POST /research/deep/finish` in the web boundary (USER);
  - declare `plan` on the deep request (the live contract test checks every field the UI sends);
  - number a confirmed plan's goals in plan order, in the plan response's id scheme;
  - send coverage as `event: coverage`;
  - split the audit's sentences as above;
  - answer the finish's 202 with JSON.
- **Optional, and read when present:**
  - `rows` and `status` on retrieve / extract frames (DR6b's `_phase` drops them today);
  - run totals `documents` / `passages` in coverage frames (without them the books and passages counters appear only once
    the answer is in).
- **At the merge with DR6c (`fea64ecb` on feat/fix-it-all):**
  - Its test "labels each search in the process rail by its move, in words" reads `.phase-label`. New deep turns no longer
    render it: the live view's feed supersedes the rail labels, as the coordinator allowed. The test needs retargeting to
    `.research-feed__item` ("Main answer · <query>", "Counter-evidence · <query>"), or it can check a saved turn without
    `deepRun`.
  - Its other three tests go through AnswerBody unchanged. `beforeEach` merges cleanly (different lines).
- DR7f, the live acceptance through the UI on the five DR4 questions, waits for the deploy and the owner's word. The
  screenshots at three widths for the owner belong there.
