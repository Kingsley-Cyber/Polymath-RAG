# unit: frontend-v2/src/screens/Chat.tsx
anchor: frontend-v2/src/screens/Chat.tsx:1-337

## purpose
Chat screen for one corpus: renders a session's Q&A turns (App owns the turn list), streams answers through a process rail into Markdown, and runs deep-research turns with a confirmable plan card. Retrieval mode, model and Corpus Explore are read from header controls (`useComposerSettings`); the composer itself keeps only Deep research (+ depth) and Reasoning. Mounted by App. [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Chat | function component | ({ corpusId: string, session: ChatSession, onUpdateTurns, models: Synthesizer[], corpusExploreAvailable: boolean, focusTurn?: number \| null = null, onFocusDone?: () => void, onOpenResearch?: (runId: string) => void }) -> JSX | frontend-v2/src/screens/Chat.tsx:41-297 | frontend-v2/src/App.tsx |

Module-local (not exported): `STARTERS` frontend-v2/src/screens/Chat.tsx:35-39, `TurnView` frontend-v2/src/screens/Chat.tsx:299-327, `AnswerActions` frontend-v2/src/screens/Chat.tsx:330-336. [DERIVED]

## contracts

**Chat** (frontend-v2/src/screens/Chat.tsx:41-297)
- in: 8 props; `focusTurn` defaults to `null` — frontend-v2/src/screens/Chat.tsx:42-64 [DERIVED]
- reads `{ mode, model, corpusExplore }` from `useComposerSettings()` on every render — frontend-v2/src/screens/Chat.tsx:66 [DERIVED]
- out: turn list is mutated only through `onUpdateTurns(fn)`; `busy = !!last && !last.done` — frontend-v2/src/screens/Chat.tsx:73-74 [DERIVED]
- pre: session already created by App before mount (prop doc) — frontend-v2/src/screens/Chat.tsx:52 [DERIVED]

**send()** (frontend-v2/src/screens/Chat.tsx:104-124)
- pre: `q` non-empty and `!busy`, else no-op — frontend-v2/src/screens/Chat.tsx:105-106 [DERIVED]
- in: builds body `{ message, corpus_id: corpusId, mode, require_retrieval: true }`; adds `synthesizer`, `reasoning`, `corpus_explorer: true` only when set/allowed — frontend-v2/src/screens/Chat.tsx:111-114 [DERIVED]
- post: stream bracketed by `beginStream(session.id)` / `endStream(session.id, ac)` in `finally` — frontend-v2/src/screens/Chat.tsx:116-123 [DERIVED]

**sendDeep(q)** (frontend-v2/src/screens/Chat.tsx:135-160)
- pre: `send()` routes here when `deep` — frontend-v2/src/screens/Chat.tsx:108 [DERIVED]
- in: request `{ corpusId, preset, mode, ...synthesizer? }`; `loadSkipPlan()` forces the direct route — frontend-v2/src/screens/Chat.tsx:137-141 [DERIVED]
- post: plan with `goals.length > 0` → turn stays at status `"ready"`, nothing runs until confirmed — frontend-v2/src/screens/Chat.tsx:151 [DERIVED]

**startDeep(idx, q, request, goals, estimateS?)** (frontend-v2/src/screens/Chat.tsx:163-177)
- in: serializes goals as `goals.map(({ goal, query, move }) => ({ goal, query, move }))` — frontend-v2/src/screens/Chat.tsx:167 [DERIVED]
- post: run status `"running"`, `startedAt: Date.now()`, `estimateS: estimateS ?? presetSeconds(request.preset)`; streams via `runTurn(..., deepResearchStream)` — frontend-v2/src/screens/Chat.tsx:164-173 [DERIVED]

**researchNext(q)** (frontend-v2/src/screens/Chat.tsx:180-185)
- post: question in box, `deep = true`, `preset = "quick"`, input focused; nothing sent — frontend-v2/src/screens/Chat.tsx:181-184 [DERIVED]

## effect surface
- Network: `api.reasoningModes(s)` on mount — frontend-v2/src/screens/Chat.tsx:76; `api.deepResearchPlan({ question, corpus_id, preset, mode }, signal)` — frontend-v2/src/screens/Chat.tsx:149; chat stream `runTurn(body, ...)` — frontend-v2/src/screens/Chat.tsx:118; deep stream `runTurn(deepRequest, ..., deepResearchStream)` — frontend-v2/src/screens/Chat.tsx:171. [DERIVED]
- Stream registry (lib/chat): `beginStream` / `endStream` / `stopStream(session.id)` — frontend-v2/src/screens/Chat.tsx:116,122,142,152,156,169,175,192-193,282. [DERIVED]
- DOM writes: textarea `style.height`/`overflowY` — frontend-v2/src/screens/Chat.tsx:85-88; `scrollTop = scrollHeight` — frontend-v2/src/screens/Chat.tsx:93-94; `.msg-user` `scrollIntoView({ block: "start" })` — frontend-v2/src/screens/Chat.tsx:100. [DERIVED]
- Browser-persisted settings read: `useComposerSettings()` — frontend-v2/src/screens/Chat.tsx:66; `loadSkipPlan()` — frontend-v2/src/screens/Chat.tsx:139. [DERIVED]
- Clock: `Date.now()` — frontend-v2/src/screens/Chat.tsx:164. [DERIVED]
- Postgres/Qdrant/files/subprocess/env flags: none in this file (FACTS: `tables_read: []`, `tables_written: []`; imports are ui/lib/components only) — frontend-v2/src/screens/Chat.tsx:1-14. [DERIVED]

## invariants
- INVARIANT: non-deep request body always has `require_retrieval: true` — frontend-v2/src/screens/Chat.tsx:111 [DERIVED]
  fails-if: answers could arrive with no cited passages, contradicting the welcome copy "Every answer cites the passages it rests on" — frontend-v2/src/screens/Chat.tsx:212.
- INVARIANT: `busy` ⇔ last turn has `done === false` — frontend-v2/src/screens/Chat.tsx:73-74 [DERIVED]
  fails-if: Send/Stop button and the `!q || busy` guard desync from the live stream.
- INVARIANT: plan is shown ⇔ `Array.isArray(plan?.goals) && plan.goals.length` — frontend-v2/src/screens/Chat.tsx:151 [DERIVED]
  fails-if: empty plan blocks the run instead of falling through to `startDeep(..., null)` — frontend-v2/src/screens/Chat.tsx:152-153.
- INVARIANT: plan payload keys are exactly `goal`, `query`, `move` — frontend-v2/src/screens/Chat.tsx:167 [DERIVED]
  fails-if: server deep-run contract mismatch; extra keys silently dropped.
- INVARIANT: `corpus_explorer` sent ⇔ `corpusExplore && corpusExploreAvailable` — frontend-v2/src/screens/Chat.tsx:114 [DERIVED]
  fails-if: capability flag bypassed on servers that don't advertise it.
- INVARIANT: depth option count is 3 (`quick`, `standard`, `thorough`) and initial preset is `"standard"` — frontend-v2/src/screens/Chat.tsx:264-266, frontend-v2/src/screens/Chat.tsx:69 [DERIVED]
  fails-if: preset string unknown to `presetSeconds` — frontend-v2/src/screens/Chat.tsx:164.
- INVARIANT: Enter sends ⇔ `!e.shiftKey && !e.nativeEvent.isComposing` — frontend-v2/src/screens/Chat.tsx:244 [DERIVED]
  fails-if: IME composition confirm sends a half-typed question.
- INVARIANT: textarea height ≤ CSS max-height with numeric fallback `320` — frontend-v2/src/screens/Chat.tsx:86-87 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network `api.reasoningModes` frontend-v2/src/screens/Chat.tsx:76, `api.deepResearchPlan` :149, `runTurn` streams :118/:171; clock `Date.now()` :164; CSS read `getComputedStyle(el).maxHeight` :85-86; patch arrival order from streaming drives `onUpdateTurns` :119/:172).
idempotency: SAFE (double-send blocked by `if (!q || busy) return` — frontend-v2/src/screens/Chat.tsx:105-106 — and `busy` flips once the turn is appended with `done` unset :110; abort listener registered `{ once: true }` :147). Each confirmed send still appends one new turn by design :110.

## failure behaviour
- Plan-phase abort: turn set `done: true`, `error: "cancelled"`, `deepRun.status: "cancelled"`; the question is restored to the composer box via `setQuestion((cur) => cur || q)` — frontend-v2/src/screens/Chat.tsx:143-147. [DERIVED]
- `sendDeep` catch, three ways: signal aborted → silent return; `olderPlanBackend(e)` → retry as `startDeep(idx, q, request, null)` with no plan; otherwise turn gets `done: true`, `error: e instanceof ApiError ? e.message : String(e)`, status `"cancelled"` — frontend-v2/src/screens/Chat.tsx:154-158. [DERIVED]
- Turn-level errors render as `.answer answer-error` — frontend-v2/src/screens/Chat.tsx:311. [DERIVED]
- Completed turn with `!t.error` and neither `answerText` nor `productResearch` renders the fixed "model returned no answer text … pick a lighter model" empty-answer block — frontend-v2/src/screens/Chat.tsx:318-322. [DERIVED]
- No error codes raised in this unit; errors are strings stored on turns. [DERIVED]

## dumb-code flags
- Magic fallback `320` for missing CSS `max-height` — frontend-v2/src/screens/Chat.tsx:86. [DERIVED]
- Loose check `focusTurn == null` against a prop typed `number | null` with default `null` — frontend-v2/src/screens/Chat.tsx:99 vs frontend-v2/src/screens/Chat.tsx:47,61. [DERIVED]
- `busy` derived from the last turn only; an unfinished non-last turn would read as idle — frontend-v2/src/screens/Chat.tsx:73-74 [INFERRED: no guard visible for out-of-order completion, though sends are serialized by the busy check :106].
- Patch lambda `onUpdateTurns((ts) => ts.map(...))` duplicated 5× with index addressing — frontend-v2/src/screens/Chat.tsx:119,128,145,172,201. [DERIVED]
- Preset vocabulary `"quick"|"standard"|"thorough"` duplicated between the Depth `<select>` and the default `"standard"`, and consumed by `presetSeconds` — frontend-v2/src/screens/Chat.tsx:264-266,69,164. [DERIVED]
- `focusTurn` scroll indexes `.msg-user` nodes positionally, assuming each `TurnView` renders exactly one — frontend-v2/src/screens/Chat.tsx:100 vs frontend-v2/src/screens/Chat.tsx:302,305 [INFERRED: research turns render via `ResearchTurnView`, whose DOM is not in this file].

## refactor notes
- Sole importer is frontend-v2/src/App.tsx (FACTS.importers); changing any of the 8 props breaks it — frontend-v2/src/screens/Chat.tsx:42-64. [DERIVED]
- CSS classes are behavior-coupled, not cosmetic: `.msg-user` is queried by index for report jumps — frontend-v2/src/screens/Chat.tsx:100; the autosizer reads `getComputedStyle(el).maxHeight` off `.composer__input` — frontend-v2/src/screens/Chat.tsx:83-88. [DERIVED]
- Deep wire contract: `deepRequest` shape and the `{ goal, query, move }` plan projection must match the server and lib/deep (`presetSeconds`) — frontend-v2/src/screens/Chat.tsx:165-167,164. [DERIVED]
- Stop is session-scoped, not turn-scoped: every cancel/stop path calls `stopStream(session.id)` — frontend-v2/src/screens/Chat.tsx:192-193,282. Per-turn cancellation requires lib/chat changes first. [DERIVED]
- Turn patches are index-addressed (`i === idx`); any turn insertion/removal/reorder in App's store silently retargets patches — frontend-v2/src/screens/Chat.tsx:119,128,145,172,201. [DERIVED]
- Header-controls split is contractual: mode/model/corpusExplore belong to the top bar via `useComposerSettings`; only deep/preset/reasoning live in the composer — frontend-v2/src/screens/Chat.tsx:66-69. [DERIVED]

## VERIFY
```verify
grep -Fq 'require_retrieval: true' frontend-v2/src/screens/Chat.tsx
! grep -Fq 'require_retrieval: false' frontend-v2/src/screens/Chat.tsx
grep -Fq 'useState("standard")' frontend-v2/src/screens/Chat.tsx
grep -Fq 'setPreset("quick")' frontend-v2/src/screens/Chat.tsx
grep -Eq 'option value="(quick|standard|thorough)"' frontend-v2/src/screens/Chat.tsx
grep -Fq 'e.nativeEvent.isComposing' frontend-v2/src/screens/Chat.tsx
grep -Fq 'parseFloat(getComputedStyle(el).maxHeight) || 320' frontend-v2/src/screens/Chat.tsx
test "$(grep -c -F 'ts.map(' frontend-v2/src/screens/Chat.tsx)" -ge 5
```
