# unit: frontend-v2/src/screens/Chat.tsx
anchor: frontend-v2/src/screens/Chat.tsx:1-323

## purpose
Chat screen for one corpus: renders the session's turns, streams each answer through `ProcessRail` into a Markdown `AnswerBody`, and sends either normal turns (always `require_retrieval: true`) or Deep research turns (planned first, shown as a confirmable plan card). The turns belong to the session held by App; this screen only reads and patches them through `onUpdateTurns`. frontend-v2/src/screens/Chat.tsx:15-32 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Chat` | exported React function component | ({ corpusId: string, session: ChatSession, onUpdateTurns: (fn: (turns: Turn[]) => Turn[]) => void, models: Synthesizer[], corpusExploreAvailable: boolean, focusTurn?: number or null, onFocusDone?: () => void }) -> JSX | frontend-v2/src/screens/Chat.tsx:40-61 | frontend-v2/src/App.tsx |

Everything else is module-private: `STARTERS` (34-38), `send` (100), `patchRun` (123), `sendDeep` (131), `startDeep` (159), `researchNext` (176), `research` (184), `TurnView` (288), `AnswerActions` (316). [DERIVED]

## contracts

**`Chat` (frontend-v2/src/screens/Chat.tsx:40)**
- in: `corpusId: string` (49); `session: ChatSession` — App creates it before this screen mounts (50-51); `models: Synthesizer[]` — the `/synthesizers` catalog read once by App (54-55); `corpusExploreAvailable: boolean` — server-advertised capability (56-57); `focusTurn` defaults to `null` (46, 59).
- pre: `mode`, `model`, `corpusExplore` come from `useComposerSettings()` (62); a reopened chat mid-answer is still streaming — `busy` is derived from the last turn, not local state (67-70).
- post (normal send): body always contains `message`, `corpus_id`, `mode`, `require_retrieval: true` (107); `synthesizer` only when `model` truthy (108); `reasoning` only when non-empty (109); `corpus_explorer: true` only when `corpusExplore && corpusExploreAvailable` (110).
- post (deep send): new turn labelled `` `DEEP · ${preset}` `` with `deepRun.status` = `"running"` if `loadSkipPlan()` else `"planning"` (133-136).

**`sendDeep` (frontend-v2/src/screens/Chat.tsx:131)**
- in: `q` trimmed non-empty (guarded at 101-104).
- out: plan with non-empty `goals` → `status: "ready"`, waits for user confirm (145-147); empty plan or `olderPlanBackend(e)` → `startDeep` immediately (148-149, 153); other error → `status: "cancelled"`, `done: true`, `error: e instanceof ApiError ? e.message : String(e)` (154).
- post: abort during planning → `done: true`, `error: "cancelled"`, `status: "cancelled"`, and the question restored to the composer via `setQuestion((cur) => cur || q)` (139-143).

**`startDeep` (frontend-v2/src/screens/Chat.tsx:159)**
- in: `idx`, `q`, `request: DeepRunRequest`, `goals: DeepGoal[] | null`, optional `estimateS`.
- post: `estimateS: estimateS ?? presetSeconds(request.preset)` and `startedAt: Date.now()` (160); request carries `question`, `corpus_id`, `preset`, `mode`, optional `synthesizer` (161-162), and `plan` only when goals truthy, each item mapped to exactly `{ goal, query, move }` (163).

**`researchNext` (frontend-v2/src/screens/Chat.tsx:176)** — sets composer state only (`question=q`, `deep=true`, `preset="quick"`, focus input); nothing is sent (176-181).

## effect surface
- Network: `api.reasoningModes(s)` on mount (72); `api.deepResearchPlan({ question, corpus_id, preset, mode }, signal)` (145); `runTurn(body, patch, signal)` normal stream (114-116); `runTurn(deepRequest, patch, signal, deepResearchStream)` deep stream (167-169).
- Stream registry: `beginStream(id)` / `endStream(id, ac)` / `stopStream(session.id)` keyed by `session.id` (112/118, 138/148, 165/171, 188-189, 270).
- DOM: textarea autosize, max-height fallback `320` px (78-85); auto-scroll to bottom on `turns` change (88-91); `scrollIntoView` on `.msg-user[focusTurn]` (96).
- Persisted setting read via `loadSkipPlan()` from `../lib/deep` (135); the storage medium is not visible in this file [INFERRED: it is the "start without showing the plan" setting named at 128].
- Postgres tables / Qdrant / files / subprocesses / env flags: none — FACTS `tables_read` and `tables_written` are empty (frontend-v2/src/screens/Chat.tsx:1-31 facts).

## invariants
INVARIANT: `require_retrieval` === `true` on every normal send — frontend-v2/src/screens/Chat.tsx:107 [DERIVED]
  fails-if: answers arrive without cited passages, breaking the welcome promise at 203.
INVARIANT: `busy` === (!!last && !last.done) with last = `turns[turns.length - 1]` — frontend-v2/src/screens/Chat.tsx:69-70 [DERIVED]
  fails-if: double-send past the guard at 102, or Stop button never appears (269).
INVARIANT: `corpus_explorer` sent only when `corpusExplore && corpusExploreAvailable` — frontend-v2/src/screens/Chat.tsx:110 [DERIVED]
  fails-if: capability flag sent to a server that does not advertise it (56-57).
INVARIANT: plan accepted only when `Array.isArray(plan?.goals) && plan.goals.length` — frontend-v2/src/screens/Chat.tsx:147 [DERIVED]
  fails-if: a goal-less plan parks the turn at `"ready"` forever instead of falling through to `startDeep` (148-149).
INVARIANT: `deepRequest.plan` items contain exactly `goal`, `query`, `move` — frontend-v2/src/screens/Chat.tsx:163 [DERIVED]
  fails-if: extra fields leak into the wire request or required ones are dropped.
INVARIANT: send button disabled iff `!question.trim()`, and `send()` returns on `!q || busy` — frontend-v2/src/screens/Chat.tsx:275, 101-102 [DERIVED]
  fails-if: empty or duplicate concurrent sends.
INVARIANT: focus effect runs only when `focusTurn != null` and always calls `onFocusDone?.()` — frontend-v2/src/screens/Chat.tsx:95-97 [DERIVED]
  fails-if: DR7e jump never completes and App keeps a stale `focusTurn`.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: `api.reasoningModes` 72, `api.deepResearchPlan` 145, streamed `runTurn` 114/167; clock: `Date.now()` 160; browser layout: `getComputedStyle`/`scrollHeight` 80-84) — frontend-v2/src/screens/Chat.tsx:72,145,160,80-84 [DERIVED]
idempotency: UNSAFE — the `busy` guard (102) blocks overlap, but every successful send appends a new turn (106, 136); replaying the same question duplicates turns. [DERIVED]

## failure behaviour
- Normal turn: `runTurn` inside try/finally, so `endStream(id, ac)` always runs (113-119); failures land as `t.error` rendered at 298.
- Deep planning catch (150-155): aborted → silent return (151); `olderPlanBackend(e)` → direct `startDeep` (153); otherwise the turn is closed with the error string (154). Nothing is rethrown.
- Abort mid-planning: turn marked `done: true`, `error: "cancelled"`, `status: "cancelled"`; question returned to the box (139-143).
- Model returns no text (`done && !error && !answerText`): static empty-answer message, no retry (304-309).
- No error codes raised locally; `ApiError` is imported from `../lib/api` and its `.message` is the only propagated text (4, 154).

## dumb-code flags
- Magic number `320` px fallback for composer max-height — frontend-v2/src/screens/Chat.tsx:82 [DERIVED]
- `stopStream(session.id)` literal repeated 3× — frontend-v2/src/screens/Chat.tsx:188,189,270 [DERIVED]
- Depth literals `quick`/`standard`/`thorough` duplicated across the select options and `useState("standard")` default; `researchNext` re-defaults preset to `"quick"` — frontend-v2/src/screens/Chat.tsx:65,253-257,179 [DERIVED]
- Fallback label string `"default"` when the reasoning catalog lacks `.default` — frontend-v2/src/screens/Chat.tsx:262 [DERIVED]
- `key={i}` index-keyed turn list — frontend-v2/src/screens/Chat.tsx:214 [DERIVED]
- `focusTurn = null` default checked with loose `focusTurn == null` — frontend-v2/src/screens/Chat.tsx:46,95 [DERIVED]

## refactor notes
- All turn patches are index-based (`i === idx` at 115, 124, 141, 168): truncating or reordering `turns` mid-stream misroutes patches. Blast radius: App.tsx store and `../lib/chatStore`. [DERIVED]
- HEADER-CONTROLS contract: this screen must keep reading `mode`/`model`/`corpusExplore` from `useComposerSettings()` (62) per the owner note (24-27); re-owning them here breaks `../lib/composerSettings` consumers. [DERIVED]
- Streams are keyed by `session.id` and deliberately survive unmount so the answer lands in this chat (29-31, 112-118); moving the AbortController into component state regresses that fix. [DERIVED]
- `deepRun` shape (`status` ∈ planning/ready/running/cancelled, `plan`, `request`) and `ResearchHandlers` (184-192) are consumed by `isResearchTurn`/`ResearchTurnView` (289); `../lib/deep` and `../components/deep/ResearchTurn` must change with it. [DERIVED]

## VERIFY
```verify
grep -Fq 'require_retrieval: true' frontend-v2/src/screens/Chat.tsx
grep -Fq 'const [preset, setPreset] = useState("standard");' frontend-v2/src/screens/Chat.tsx
grep -Fq 'if (deep) { void sendDeep(q); return; }' frontend-v2/src/screens/Chat.tsx
grep -Fq 'estimateS: estimateS ?? presetSeconds(request.preset)' frontend-v2/src/screens/Chat.tsx
grep -Fq 'stopStream(session.id)' frontend-v2/src/screens/Chat.tsx
! grep -Fq 'localStorage' frontend-v2/src/screens/Chat.tsx
```
