# unit: frontend-v2/src/components/deep/_small-modules
anchor: frontend-v2/src/components/deep/DeepResearchSettings.tsx:1-21

## purpose
Five small frontend modules for the deep-research chat mode (spec tag `DEEP-RESEARCH-MODE-V1 §11 / DR7`): a one-checkbox settings card, an editable plan card with a 10 s auto-start countdown, a Reports tab listing past research turns from browser-local chat history, the composition view for one research turn, and a remark plugin that marks uncited sentences in rendered report prose. [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `DeepResearchSettings` | function component | `() -> JSX` | DeepResearchSettings.tsx:6 | — |
| `COUNTDOWN_S` | const | `number = 10` | PlanCard.tsx:15 | PlanCard.tsx:64-67 (internal; no external importer in FACTS) |
| `PlanCard` | function component | `{ run: DeepRunState; onStart: (goals: DeepGoal[]) => void; onCancel: () => void; onRunPatch: (patch: Partial<DeepRunState>) => void } -> JSX` | PlanCard.tsx:17-33 | ResearchTurn.tsx:7,34 |
| `ResearchTab` | type | `"runs" \| "reports"` | ReportsList.tsx:11 | ResearchTabs |
| `ResearchTabs` | function component | `{ tab: ResearchTab; onTab: (t: ResearchTab) => void } -> JSX` | ReportsList.tsx:16-38 | — |
| `ReportsList` | function component | `{ sessions?: ChatSession[]; onOpen?: (chatId: string, turnIndex: number) => void; tabs: ReactNode } -> JSX` | ReportsList.tsx:46-82 | — |
| `ResearchHandlers` | interface | `{ onStart, onCancel, onStop, onRunPatch, onResearchNext }` | ResearchTurn.tsx:13-19 | ResearchTurnView |
| `ResearchTurnView` | function component | `{ t: Turn; models: Synthesizer[] } & ResearchHandlers -> JSX` | ResearchTurn.tsx:21-51 | — |
| `uncitedMarks` | function | `(ranges: Sentence[], base: number, whole: string) -> remark transformer` | remarkUncited.ts:19-72 | DeepReport.tsx (per FACTS.importers; exact symbol not shown) |

## contracts

**PlanCard / PlanReady**
- in: `run.status === "planning"` → loading skeleton + Cancel only — PlanCard.tsx:23-31 [DERIVED]
- in: otherwise `draft = run.draft ?? draftFromPlan(run.plan)`; draft and `touched` live on the turn so a chat switch keeps edits — PlanCard.tsx:44, comment 10-13 [DERIVED]
- pre: `start()` no-ops when `started.current || planProblem(draft, max)` — PlanCard.tsx:54 [DERIVED]
- post: `onStart(confirmPlan(draft, run.plan))` fires exactly once per card — PlanCard.tsx:55-56 [DERIVED]
- countdown: effect keyed `[counting]`, `counting = !run.touched && !problem`; auto-start via `setTimeout(..., COUNTDOWN_S * 1000)`; both timers cleared on teardown — PlanCard.tsx:47,62-69 [DERIVED]
- any edit sets `touched: true` via `onRunPatch` — PlanCard.tsx:76-78 [DERIVED]

**uncitedMarks**
- in: `ranges` are `[start, end)` offsets into `whole`; `base` is where this Markdown part starts — remarkUncited.ts:19, comment 3-8 [DERIVED]
- pre: must run BEFORE `remarkCitations`, while text nodes still carry source offsets — remarkUncited.ts:4 [DERIVED]
- skips node types exactly `code, inlineCode, heading, html, link` — remarkUncited.ts:25 [DERIVED]
- exact path: when `whole.slice(h.s, h.e) === node.value`, wraps per-range pieces in `uncited-mark`; the sentence's last piece gets an `uncited-note` ("no citation") — remarkUncited.ts:33-37,43-53 [DERIVED]
- fuzzy path: node whose source is not its literal text (escapes/entities) is marked whole only when `inside * 2 >= h.e - h.s` — remarkUncited.ts:54-57 [DERIVED]
- post: mutates the mdast tree in place, replacing matched text nodes — remarkUncited.ts:61-70 [DERIVED]

**ReportsList**
- in: `sessions` optional; fallback `loadSessions()` (browser-stored history) — ReportsList.tsx:47-52, comment 7-8 [DERIVED]
- out: row click → `onOpen(chatId, turnIndex)` — ReportsList.tsx:70 [DERIVED]
- `when(ms)`: `0` or `NaN` date → `"—"` — ReportsList.tsx:40-44 [DERIVED]

**ResearchTurnView**
- planning view iff `!t.done && !!run && (run.status === "planning" || run.status === "ready")` — ResearchTurn.tsx:25 [DERIVED]
- report branch: `reportModelOf(t)` non-null → `DeepReport`; null → `AnswerBody` + `ReportActions` when `t.done && t.deep` (older backend) — ResearchTurn.tsx:26,36-42 [DERIVED]
- `t.done && !t.error && !t.answerText` → fixed empty-answer notice — ResearchTurn.tsx:43-47 [DERIVED]

**DeepResearchSettings**
- checkbox bound to `useSkipPlan()` store, same store the plan card's checkbox reads — DeepResearchSettings.tsx:7,12-14; PlanCard.tsx:43,142-145 [DERIVED]

## effect surface
- No Postgres tables, no Qdrant, no network calls, no env flags in this unit — FACTS `tables_read: []`, `tables_written: []` [DERIVED]
- Browser-local preference store via `useSkipPlan()` from `lib/deep.ts` ("kept in this browser") — DeepResearchSettings.tsx:4-5,7 [DERIVED]
- Browser-local chat history read via `loadSessions()` fallback ("Reports are kept in this browser only, like your chats") — ReportsList.tsx:52,60 [DERIVED]
- Timers: `window.setInterval` 250 ms tick, `window.setTimeout` `COUNTDOWN_S * 1000` ms auto-start, both cleared on cleanup — PlanCard.tsx:66-68 [DERIVED]
- Module-level mutable `let refocus = false` — ReportsList.tsx:14 [DERIVED]
- CSS side-effect import `"../../styles/deep.css"` in three files — DeepResearchSettings.tsx:2, PlanCard.tsx:7, ReportsList.tsx:5 [DERIVED]

## invariants
INVARIANT: auto-start delay == `COUNTDOWN_S * 1000` == 10000 ms — PlanCard.tsx:15,64,67 [DERIVED]
  fails-if: countdown hint text (`Starts by itself in N s`) disagrees with actual auto-start time.
INVARIANT: parts count >= 1 (remove button `disabled={n <= 1}`) — PlanCard.tsx:122 [DERIVED]
  fails-if: a plan with zero parts could be started.
INVARIANT: parts count <= `maxPlanItems(run.request.preset)` ("Add a part" only when `n < max`) — PlanCard.tsx:45,129 [DERIVED]
  fails-if: plan exceeds the preset's part limit.
INVARIANT: goal textarea `maxLength={300}` — PlanCard.tsx:107 [DERIVED]
  fails-if: UI accepts goals longer than the backend/store limit (if any).
INVARIANT: countdown runs only while `counting = !run.touched && !problem` — PlanCard.tsx:47,62-63 [DERIVED]
  fails-if: an edited plan auto-starts under the user.
INVARIANT: displayed `left >= 1` while counting (`Math.max(1, ...)`) — PlanCard.tsx:66 [DERIVED]
  fails-if: button shows "· 0 s" or negative before the timeout fires.
INVARIANT: fuzzy mark threshold is `inside * 2 >= h.e - h.s` (≥ 50 % coverage) — remarkUncited.ts:55-56 [DERIVED]
  fails-if: partially-matching escaped nodes get dotted underlines for barely-covered text.
INVARIANT: planning view iff `!t.done && run.status ∈ {"planning","ready"}` — ResearchTurn.tsx:25 [DERIVED]
  fails-if: a running/finished turn re-renders the plan card, or a ready plan shows LiveResearch.

## determinism & idempotency
determinism: NONDETERMINISTIC (`Date.now()` deadline — PlanCard.tsx:64; `Date.now().toString(36)` key gen — PlanCard.tsx:80; timers — PlanCard.tsx:66-67; `toLocaleString` timestamp — ReportsList.tsx:42-43; browser-storage fallback — ReportsList.tsx:52). `uncitedMarks` itself is a pure function of `(ranges, base, whole, tree)`.
idempotency: UNSAFE (`uncitedMarks` mutates the tree in place — remarkUncited.ts:61-70; a second pass would find no positioned text nodes in the synthesized marks, so re-running is effectively a no-op — [INFERRED: synthesized `text()` nodes carry no `position`, so they never become hits]). Render/timer cleanup is SAFE (PlanCard.tsx:68).

## failure behaviour
- No `try/catch` anywhere in the unit; nothing is swallowed locally. [DERIVED — absence across all five SOURCE files]
- `t.error` renders `errorWords(t.error)` in an `answer-error` block — ResearchTurn.tsx:35 [DERIVED]
- Finished turn with no answer text → static notice `The model returned no report text. Send the question again, or pick another model.` — ResearchTurn.tsx:43-47 [DERIVED]
- Invalid/zero timestamps degrade to `"—"` — ReportsList.tsx:40-44 [DERIVED]
- `uncitedMarks` early-returns when `ranges` is empty — remarkUncited.ts:21 [DERIVED]
- Empty reports list → `EmptyState` card with guidance — ReportsList.tsx:61-66 [DERIVED]

## dumb-code flags
- Duplicated literal `"Start deep research without showing the plan"` in DeepResearchSettings.tsx:13 and PlanCard.tsx:144 — two copies of one user-facing string. [DERIVED]
- Magic numbers: `250` ms tick — PlanCard.tsx:66; `300` maxLength — PlanCard.tsx:107; `rows={2}` — PlanCard.tsx:107; icon `size={14}` — PlanCard.tsx:135. [DERIVED]
- `COUNTDOWN_S` is exported but FACTS shows no importer outside PlanCard.tsx — possible dead export. [DERIVED]
- Module-global mutable `refocus` shared by every `ResearchTabs` instance — ReportsList.tsx:14. [DERIVED]
- `onChange` writes `goal` and `query` to the same value (`change(i, { goal: e.target.value, query: e.target.value })`), so the `Searches:` hint at PlanCard.tsx:119-121 can only appear if `query` diverges via another path (e.g. `draftFromPlan`) — [INFERRED: hint requires `d.query.trim() !== d.goal.trim()`]. [DERIVED]
- Fuzzy threshold written as `inside * 2 >= h.e - h.s` instead of a halved comparison — remarkUncited.ts:55-56. [DERIVED]

## refactor notes
- The skip-plan label text exists in two files; any wording change must touch DeepResearchSettings.tsx:13 and PlanCard.tsx:144 together, or extract a shared constant.
- `uncitedMarks` pipeline position is load-bearing: it must run BEFORE `remarkCitations` while text nodes still carry source offsets — remarkUncited.ts:3-4. Reordering breaks all marking.
- PlanCard's props type is duplicated verbatim on `PlanCard` (17-22) and `PlanReady` (35-40); changing one without the other drifts the signature.
- `ResearchTurnView`'s `AnswerBody` fallback renders older backends without a report model — ResearchTurn.tsx:37-42; removing it breaks those turns.
- Moving `PlanCard` requires updating `ResearchTurn.tsx:7`; FACTS.importers also lists `DeepReport.tsx` as an importer of this unit — verify which symbol it pulls before relocating any export.
- `refocus` module state assumes the two tabs render on separate pages/remounts — ReportsList.tsx:13-14,19-20; a same-page tab bar changes focus semantics.

## VERIFY
```verify
grep -Fq 'export const COUNTDOWN_S = 10;' frontend-v2/src/components/deep/PlanCard.tsx
grep -Fq 'Start deep research without showing the plan' frontend-v2/src/components/deep/DeepResearchSettings.tsx
grep -Fq 'Start deep research without showing the plan' frontend-v2/src/components/deep/PlanCard.tsx
grep -Fq 'let refocus = false;' frontend-v2/src/components/deep/ReportsList.tsx
grep -Fq '["code", "inlineCode", "heading", "html", "link"]' frontend-v2/src/components/deep/remarkUncited.ts
grep -Fq 'The model returned no report text. Send the question again, or pick another model.' frontend-v2/src/components/deep/ResearchTurn.tsx
grep -Fq 'maxLength={300}' frontend-v2/src/components/deep/PlanCard.tsx
```
