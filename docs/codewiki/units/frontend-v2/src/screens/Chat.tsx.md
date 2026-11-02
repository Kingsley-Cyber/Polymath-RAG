# unit: frontend-v2/src/screens/Chat.tsx
anchor: frontend-v2/src/screens/Chat.tsx:1-338

## purpose
Chat screen (F2 + F3): question/answer over one corpus, streaming each turn through a process rail into a Markdown answer; supports deep-research turns with a confirmable plan, and product-answer follow-ups. Mounted by App, which owns the sessions and turns. — frontend-v2/src/screens/Chat.tsx:16-33 [DERIVED], frontend-v2/src/screens/Chat.tsx:41 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
| Chat | function (React component, exported) | ({ corpusId: string, session: ChatSession, onUpdateTurns, models: Synthesizer[], corpusExploreAvailable: boolean, focusTurn = null, onFocusDone?, onOpenResearch? }) -> JSX | frontend-v2/src/screens/Chat.tsx:41-299 | frontend-v2/src/App.tsx (FACTS.importers) |
| TurnView | function (module-private) | ({ t, models, research?, product? }) -> JSX | frontend-v2/src/screens/Chat.tsx:301-329 | — (internal) |
| AnswerActions | function (module-private) | ({ text: string }) -> JSX | frontend-v2/src/screens/Chat.tsx:332-338 | — (internal) |

## contracts

**Chat** — frontend-v2/src/screens/Chat.tsx:41-64 [DERIVED]
- in: `corpusId: string`; `session: ChatSession` (App creates it before this screen mounts, :52); `onUpdateTurns: (fn: (turns: Turn[]) => Turn[]) => void` (:55); `models: Synthesizer[]` (:57); `corpusExploreAvailable: boolean` (:59); `focusTurn?: number | null = null` (:61); `onFocusDone?: () => void` (:62); `onOpenResearch?: (runId: string) => void` (:64).
- pre: `session` exists before mount (:52); `corpus_explorer` sent only when the server advertises the capability (:58-59).
- post (normal send): request body = `{ message: q, corpus_id: corpusId, mode, require_retrieval: true }` plus optional `synthesizer`, `reasoning`, `corpus_explorer` — frontend-v2/src/screens/Chat.tsx:111-114 [DERIVED].
- post (deep send): request = `{ question: q, corpus_id, preset, mode }` plus optional `synthesizer` and `plan` (goal/query/move only) — frontend-v2/src/screens/Chat.tsx:165-167 [DERIVED].
- every `beginStream(id)` is matched by `endStream(id, ac)` — directly in `finally` (:116-122, :169-175) or before handing over to `startDeep` (:152, :156) — frontend-v2/src/screens/Chat.tsx:116-122 [DERIVED].

**send()** — frontend-v2/src/screens/Chat.tsx:104-124 [DERIVED]
- pre: no-ops when `!q || busy` (:106); deep toggle routes to `sendDeep` instead (:108).
- out: appends `newTurn(q, mode)` at index `turns.length` (:109-110); patches that index from the stream (:118-119).

**sendDeep(q)** — frontend-v2/src/screens/Chat.tsx:135-160 [DERIVED]
- pre: called only from `send()` when `deep` (:108).
- post: appends a turn labelled `DEEP · ${preset}` with `deepRun.status` = `"running"` (skip-plan setting) or `"planning"` (:140); with goals, patches to `"ready"` and waits for user start (:151, :188-190).

**startDeep(idx, q, request, goals, estimateS?)** — frontend-v2/src/screens/Chat.tsx:163-177 [DERIVED]
- post: sets `status: "running"`, `startedAt: Date.now()`, `estimateS: estimateS ?? presetSeconds(request.preset)` (:164); streams via `runTurn(..., deepResearchStream)` (:171-173).

## effect surface
- Network: `api.reasoningModes(s)` on mount (:76); `api.deepResearchPlan({ question, corpus_id, preset, mode }, ac.signal)` when a planned deep turn is sent (:149); `runTurn(body, ...)` for normal turns (:118) and `runTurn(deepRequest, ..., deepResearchStream)` for deep turns (:171). [DERIVED]
- Browser persistence: `useComposerSettings()` — mode/model/corpusExplore kept per browser (:66, doc :25-27). [DERIVED]
- Stream registry: `beginStream` / `endStream` / `stopStream` keyed by `session.id` (:116, :142, :169, :192-193, :284). [DERIVED]
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). Qdrant collections, files, subprocesses, env flags: none visible.

## invariants
INVARIANT: `busy` ⇔ last turn exists and `!last.done` — frontend-v2/src/screens/Chat.tsx:73-74 [DERIVED]
  fails-if: Stop button and send-guard desync; a done turn shows Send while streaming or Stop while idle.
INVARIANT: `body.require_retrieval` is `true` on every normal send — frontend-v2/src/screens/Chat.tsx:111 [DERIVED]
  fails-if: answers arrive without citation passages, breaking the "every answer cites" promise (:214).
INVARIANT: `body.corpus_explorer` present ⇔ `corpusExplore && corpusExploreAvailable` — frontend-v2/src/screens/Chat.tsx:114 [DERIVED]
  fails-if: explorer requested on a server without the capability.
INVARIANT: plan forwarded to server only with keys `goal`, `query`, `move` — frontend-v2/src/screens/Chat.tsx:167 [DERIVED]
  fails-if: server rejects or misreads extra plan fields.
INVARIANT: deep plan shown for confirmation only when `Array.isArray(plan?.goals) && plan.goals.length` — frontend-v2/src/screens/Chat.tsx:151 [DERIVED]
  fails-if: empty plan renders a dead plan card instead of auto-starting.
INVARIANT: `estimateS` falls back to `presetSeconds(request.preset)` — frontend-v2/src/screens/Chat.tsx:164 [DERIVED]
  fails-if: progress estimate missing when the plan carried no estimate.
INVARIANT: textarea height ≤ computed `maxHeight`, fallback `320` — frontend-v2/src/screens/Chat.tsx:86-88 [DERIVED]
  fails-if: composer grows unbounded on long input.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `api.reasoningModes` :76, `api.deepResearchPlan` :149, `runTurn` streams :118/:171; clock `Date.now()` :164; user input incl. IME composition state :246)
idempotency: UNSAFE (each `send()`/`sendDeep()` call appends a new turn :110/:140; duplicates prevented only by the `!q || busy` guard :106)

## failure behaviour
- Abort during deep planning: listener marks the turn `done: true, error: "cancelled"`, `deepRun.status: "cancelled"`, and restores the question to the box (`cur || q`) — frontend-v2/src/screens/Chat.tsx:143-147 [DERIVED].
- `sendDeep` catch (:154-158): aborted → silent return; `olderPlanBackend(e)` → falls back to `startDeep(..., null)` with no plan; otherwise turn marked `done: true` with `error: e instanceof ApiError ? e.message : String(e)` and `status: "cancelled"`. [DERIVED]
- Stream slots released in `finally` even when `runTurn` throws (:121-122, :174-175) — the caller sees the turn left not-done. [DERIVED]
- Turn display: `t.error` rendered in `.answer-error` (:313); `t.done && !t.error` with no `answerText`/`productResearch` renders the `.empty-answer` hint "Send again, or pick a lighter model" (:315-324). [DERIVED]

## dumb-code flags
- Magic number `320` px as maxHeight fallback — frontend-v2/src/screens/Chat.tsx:86 [DERIVED].
- Preset literals duplicated: `"quick"` at :183 and :266; `"standard"` default at :69 and option :267 — must stay in sync with each other and with `presetSeconds` — frontend-v2/src/screens/Chat.tsx:69 [DERIVED], sync requirement [INFERRED: preset string feeds `presetSeconds(request.preset)` :164].
- `stopStream(session.id)` repeated at :192, :193, :284. [DERIVED]
- Turn list keyed by array index (`key={i}` :226) and patched by index (:119, :128, :140, :172, :202-203); no stable turn id in this file. [DERIVED]
- Comment promises deep-plan auto-start "after 10 s" (:132) but no `10` or timer exists in this file. [DERIVED for absence; INFERRED: the timer lives in `ResearchTurn`, which receives `onStart` :188-190]
- Hardcoded user-facing copy in code: STARTERS (:35-39), empty-answer advice (:322-323), hint "Enter to send · Shift+Enter for a new line" (:295). [DERIVED]

## refactor notes
- Only importer is `frontend-v2/src/App.tsx` (FACTS.importers); any props change to `Chat` (:41-64) touches App.tsx and only App.tsx.
- Turn addressing is positional: `onUpdateTurns` patches by index everywhere (:110, :119, :128, :140, :172, :202-203). Inserting/deleting a turn while one streams misroutes its patches. [INFERRED: index math is visible, reorder risk follows from it]
- Stream lifecycle is keyed by `session.id` through lib/chat (`beginStream`/`endStream`/`stopStream`, :116/:142/:169/:192-193/:284); the screen may unmount mid-stream and the answer must still land in this chat (:30-32), so that keying contract must not change here.
- `deepRun`, `productRun`, `productReport` live on the `Turn` object (:140, :202-203); reshaping `Turn` in lib/chat ripples into `ResearchTurnView`, `AnswerBody`, and `isResearchTurn` usage (:304-317).
- Imports come through `../` from `screens/` (FACTS.imports; :2-14) — moving this file breaks eleven relative paths.

## VERIFY
```verify
grep -Fq 'require_retrieval: true' frontend-v2/src/screens/Chat.tsx
grep -Fq 'corpusExplore && corpusExploreAvailable' frontend-v2/src/screens/Chat.tsx
grep -Fq 'e.nativeEvent.isComposing' frontend-v2/src/screens/Chat.tsx
grep -Fq 'parseFloat(getComputedStyle(el).maxHeight) || 320' frontend-v2/src/screens/Chat.tsx
grep -Fq 'presetSeconds(request.preset)' frontend-v2/src/screens/Chat.tsx
! grep -Fq 'isComposing === true' frontend-v2/src/screens/Chat.tsx
```
