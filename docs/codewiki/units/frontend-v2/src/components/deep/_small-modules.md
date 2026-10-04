# unit: frontend-v2/src/components/deep/_small-modules
anchor: frontend-v2/src/components/deep/PlanCard.tsx:1-148

## purpose
Five small frontend-v2 modules of deep-research mode (DEEP-RESEARCH-MODE-V1 §11/§11.2): the settings checkbox for skipping the plan, the editable plan card with a 10 s auto-start countdown, the Reports tab listing this browser's research reports, the chat-thread view for one research turn, and a remark step that marks uncited sentences in rendered report prose. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `DeepResearchSettings` | function component | `() -> JSX` | DeepResearchSettings.tsx:6-21 | — |
| `COUNTDOWN_S` | const | `= 10` | PlanCard.tsx:15 | — |
| `PlanCard` | function component | `({ run, onStart, onCancel, onRunPatch }) -> JSX` | PlanCard.tsx:17-33 | ResearchTurn.tsx:8 [DERIVED] |
| `ResearchTab` | type | `"runs" \| "reports"` | ReportsList.tsx:11 | — |
| `ResearchTabs` | function component | `({ tab, onTab }) -> JSX` | ReportsList.tsx:16-38 | — |
| `ReportsList` | function component | `({ sessions?, onOpen?, tabs }) -> JSX` | ReportsList.tsx:46-82 | — |
| `ResearchHandlers` | interface | 5 callbacks | ResearchTurn.tsx:14-20 | ResearchTurnView [DERIVED] |
| `ResearchTurnView` | function component | `({ t, models, ...ResearchHandlers }) -> JSX` | ResearchTurn.tsx:22-53 | — |
| `uncitedMarks` | function | `(ranges: Sentence[], base: number, whole: string) -> remark transformer` | remarkUncited.ts:19-72 | frontend-v2/src/components/deep/DeepReport.tsx [INFERRED: only importer in FACTS, and no other file here is plausibly imported by DeepReport] |

## contracts

**PlanCard** (PlanCard.tsx:17-33)
- in: `run: DeepRunState`, `onStart: (goals: DeepGoal[]) => void`, `onCancel: () => void`, `onRunPatch: (patch: Partial<DeepRunState>) => void` — PlanCard.tsx:17-22
- pre: `run.status === "planning"` renders loading skeleton with Cancel only — PlanCard.tsx:23-31; any other status renders `PlanReady` — PlanCard.tsx:32
- out: `onStart(confirmPlan(draft, run.plan))` on Start or countdown expiry — PlanCard.tsx:56
- post: `start()` is a no-op once `started.current` is true or `planProblem(draft, max)` is truthy — PlanCard.tsx:54

**ReportsList** (ReportsList.tsx:46-82)
- in: `sessions?: ChatSession[]`; when omitted, reads saved history via `loadSessions()` — ReportsList.tsx:52
- out: `onOpen?.(r.chatId, r.index)` on row click — ReportsList.tsx:70
- pre: reports computed once per `sessions` change via `useMemo(..., [sessions])` — ReportsList.tsx:52

**ResearchTurnView** (ResearchTurn.tsx:22-53)
- in: `t: Turn`, `models: Synthesizer[]`, plus the 5 `ResearchHandlers` callbacks — ResearchTurn.tsx:14-24
- `planning = !t.done && !!run && (run.status === "planning" || run.status === "ready")` selects `PlanCard`, else `LiveResearch` — ResearchTurn.tsx:26, 29-30
- report branch: `t.answerText` present → `DeepReport` if `reportModelOf(t)` returns a model, else `AnswerBody` + `ReportActions` when `t.done && t.deep` — ResearchTurn.tsx:27, 38-42

**uncitedMarks** (remarkUncited.ts:19-72)
- in: `ranges: Sentence[]` (`[start, end)` into the whole report), `base` = where this Markdown part starts in the whole prose, `whole` = the whole prose string — remarkUncited.ts:6-7, 19
- out: transformer returning `() => (tree: MdNode) => void`; early return if `!ranges.length` — remarkUncited.ts:20-21
- pre: must run BEFORE `remarkCitations`, while text nodes still carry source offsets — remarkUncited.ts:3-4
- post: overlapping text pieces wrapped in `uncited-mark`; an `uncited-note` ("no citation") follows the last piece of each sentence — remarkUncited.ts:16-17, 33-37

## effect surface
- No DB tables (`tables_read`/`tables_written` empty) — FACTS.
- Timers: `window.setInterval(..., 250)` (redraw) and `window.setTimeout(..., COUNTDOWN_S * 1000)` (auto-start) — PlanCard.tsx:66-67.
- Clock: `Date.now()` for new-part keys — PlanCard.tsx:80; `new Date(ms).toLocaleString(...)` for report timestamps — ReportsList.tsx:43.
- Browser persistence (mechanism in imported libs, not here): `useSkipPlan` from `../../lib/deep.ts` — DeepResearchSettings.tsx:1, PlanCard.tsx:5; `loadSessions` from `../../lib/chatStore.ts` — ReportsList.tsx:2. Copy claims data is "kept in this browser" — DeepResearchSettings.tsx:4-5, ReportsList.tsx:60.
- No Qdrant, network, subprocess, or env flags visible in SOURCE.

## invariants
- INVARIANT: countdown length `COUNTDOWN_S` == 10 seconds — PlanCard.tsx:15 [DERIVED]
  fails-if: settings copy "after 10 seconds" (DeepResearchSettings.tsx:17) no longer matches actual behavior.
- INVARIANT: countdown is active iff `!run.touched && !planProblem(draft, max)` — PlanCard.tsx:47 [DERIVED]
  fails-if: editing or an invalid plan should stop auto-start; a broken `touch` handler causes unwanted auto-run.
- INVARIANT: countdown effect re-arms only on `counting` change (dep array `[counting]`) — PlanCard.tsx:69 [DERIVED]
  fails-if: adding deps re-creates timers mid-count and resets `left`.
- INVARIANT: Start button disabled iff `!!problem` — PlanCard.tsx:134 [DERIVED]
- INVARIANT: Remove part disabled when `n <= 1` — PlanCard.tsx:231 [DERIVED]
  fails-if: last part removable → empty plan submitted.
- INVARIANT: "Add a part" rendered only when `n < max` where `max = maxPlanItems(run.request.preset)` — PlanCard.tsx:45, 129-131 [DERIVED]
- INVARIANT: goal textarea `maxLength` == 300, `rows` == 2 — PlanCard.tsx:107 [DERIVED]
- INVARIANT: `uncitedMarks` skips node types `["code", "inlineCode", "heading", "html", "link"]` — remarkUncited.ts:25 [DERIVED]
  fails-if: adding a type to code without this list marks code/links as uncited.
- INVARIANT: whole-node fallback marks only when `inside * 2 >= h.e - h.s` (covered ≥ half the node) — remarkUncited.ts:55-56 [DERIVED]
- INVARIANT: `refocus` is module-global (`let refocus = false`), set on tab switch, cleared on next mount — ReportsList.tsx:14, 20, 22 [DERIVED]
  fails-if: two mounted `ResearchTabs` steal each other's focus flag.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: Date.now key PlanCard.tsx:80, timers PlanCard.tsx:66-67; locale/env: toLocaleString ReportsList.tsx:43; browser store read when `sessions` absent ReportsList.tsx:52). `uncitedMarks` is a pure tree transform given `ranges`/`base`/`whole` — remarkUncited.ts:19-72 [DERIVED]
idempotency: SAFE (pure rendering; timers cleared in the effect cleanup PlanCard.tsx:68; double-start guarded by the `started` ref PlanCard.tsx:54) [DERIVED]

## failure behaviour
- No try/catch anywhere in the unit; FACTS lists no fallbacks — whole SOURCE.
- Turn error surfaced as `errorWords(t.error)` in an `answer-error` div — ResearchTurn.tsx:31.
- Empty report: `t.done && !t.error` with no `answerText` → advisory div "The model returned no report text. Send the question again, or pick another model." — ResearchTurn.tsx:44-48.
- No reports: `EmptyState` card "No deep research reports yet" — ReportsList.tsx:61-66.
- `when(ms)` renders "—" for `ms == 0` or invalid dates — ReportsList.tsx:41-43.
- `uncitedMarks` with no matching text nodes leaves the tree unchanged (empty `replaced` map, rebuild no-op) — remarkUncited.ts:39-40, 61-68 [INFERRED: no hits → nothing replaced].

## dumb-code flags
- "10" duplicated: `COUNTDOWN_S = 10` (PlanCard.tsx:15) vs hardcoded copy "after 10 seconds" (DeepResearchSettings.tsx:17) and comment "after 10 s" (PlanCard.tsx:12) — changing the const does not update the copy.
- Magic tick interval 250 ms — PlanCard.tsx:66.
- Magic maxLength 300 — PlanCard.tsx:107.
- Magic majority threshold `inside * 2 >= h.e - h.s` — remarkUncited.ts:56.
- Module-level mutable `let refocus = false` shared across all instances/mounts — ReportsList.tsx:14.
- `startNow.current = start` assigned during render — PlanCard.tsx:58-59.
- Key scheme `new-${Date.now().toString(36)}-${draft.length}` mixes clock and index — PlanCard.tsx:80.
- Same checkbox label "Start deep research without showing the plan" duplicated in two files — DeepResearchSettings.tsx:13, PlanCard.tsx:144 (intentional per DeepResearchSettings.tsx:4-5, but a literal pair to keep in sync).
- `../../lib/deep.ts` imported by 4 of the 5 files — heavy single-module coupling — FACTS.imports.

## refactor notes
- `PlanCard` and `PlanReady` duplicate the full 4-prop signature; any prop change must be mirrored — PlanCard.tsx:17-22 vs 35-40.
- Adding a `ResearchHandlers` member changes `ResearchTurnView`'s props and every caller — ResearchTurn.tsx:14-24.
- `uncitedMarks` ordering contract (before `remarkCitations`) and the `base` offset contract must be preserved or offset math breaks — remarkUncited.ts:3-7.
- Custom element names `uncited-mark` / `uncited-note` pair with `../../styles/deep.css` (imported at DeepResearchSettings.tsx:2, PlanCard.tsx:8, ReportsList.tsx:5); renaming either side breaks styling — remarkUncited.ts:16-17.
- `ReportsList` only reads `loadSessions()` when `sessions` is omitted; tests/standalone renders depend on that fallback — ReportsList.tsx:52.
- Plan/goal helpers (`confirmPlan`, `draftFromPlan`, `maxPlanItems`, `planProblem`, `MOVES`, `MOVE_WORDS`, `isMove`, `moveWords`) all live in `../../lib/deep.ts`; moving validation changes both PlanCard behavior and its anchor set — PlanCard.tsx:3-4.

## VERIFY
```verify
grep -Fq 'export const COUNTDOWN_S = 10;' frontend-v2/src/components/deep/PlanCard.tsx
grep -Fq 'const tick = window.setInterval(() => setLeft(Math.max(1, Math.ceil((deadline - Date.now()) / 1000))), 250);' frontend-v2/src/components/deep/PlanCard.tsx
grep -Fq 'Start deep research without showing the plan' frontend-v2/src/components/deep/DeepResearchSettings.tsx
grep -Fq 'if (!ranges.length) return;' frontend-v2/src/components/deep/remarkUncited.ts
test "$(grep -c -F 'uncited-mark' frontend-v2/src/components/deep/remarkUncited.ts)" -ge 2
grep -Fq 'const reports = useMemo(() => listReports(sessions ?? loadSessions()), [sessions]);' frontend-v2/src/components/deep/ReportsList.tsx
grep -Fq 'const planning = !t.done && !!run && (run.status === "planning" || run.status === "ready");' frontend-v2/src/components/deep/ResearchTurn.tsx
! grep -Fq 'catch' frontend-v2/src/components/deep/ResearchTurn.tsx
```
