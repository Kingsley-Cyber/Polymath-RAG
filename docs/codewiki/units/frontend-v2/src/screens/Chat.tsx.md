# unit: frontend-v2/src/screens/Chat.tsx
anchor: frontend-v2/src/screens/Chat.tsx:1-326

## purpose
Chat screen for one corpus: renders the session's thread and sends each question either as a normal streaming turn (process rail + Markdown answer) or as a deep-research run with a confirmable plan card. frontend-v2/src/screens/Chat.tsx:16-31 [DERIVED]
Turns belong to the session held by App; this screen reads them and writes through `onUpdateTurns`, so a stream opened here still lands in the chat after the screen unmounts. frontend-v2/src/screens/Chat.tsx:29-31 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Chat` | function component | `({ corpusId: string; session: ChatSession; onUpdateTurns: (fn: (turns: Turn[]) => Turn[]) => void; models: Synthesizer[]; corpusExploreAvailable: boolean; focusTurn?: number \| null; onFocusDone?: () => void }) -> JSX` | frontend-v2/src/screens/Chat.tsx:40-286 | frontend-v2/src/App.tsx (FACTS.importers) |

Internal only (not exported): `STARTERS` (34-38), `send` (100), `patchRun` (123), `sendDeep` (131), `startDeep` (159), `researchNext` (176), `research` (184), `TurnView` (288), `AnswerActions` (315). frontend-v2/src/screens/Chat.tsx:34-315 [DERIVED]

## contracts

**Chat** (frontend-v2/src/screens/Chat.tsx:40-286)
- in: `corpusId` sent as `corpus_id` on every request (107); `session` created by App before mount (50); `models` = the `/synthesizers` catalog read once by App (54); `corpusExploreAvailable` gates the `corpus_explorer` field (56, 110); `focusTurn` defaults `null`, scrolls `.msg-user[focusTurn]` into view then calls `onFocusDone` (58-60, 94-98). [DERIVED]
- out: turn mutations exit only via `onUpdateTurns` (53), used at 106, 115, 124, 136, 139-141, 147, 154, 168. [DERIVED]
- pre: `send()` requires trimmed question and `!busy` (101-102); `busy = !!last && !last.done` (69-70). [DERIVED]
- post: normal turn appended as `newTurn(q, mode)` (106); deep turn labeled `` `DEEP · ${preset}` `` with `deepRun: { status, request }` (136); every `beginStream(id)` is paired with `endStream(id, ac)` in `try/finally` for run streams (112-118, 165-171). [DERIVED]

**sendDeep(q)** (131-156)
- in: `q` trimmed by caller (101-104). [DERIVED]
- post: `loadSkipPlan()` true → straight to `startDeep` (135-137); plan with `Array.isArray(plan?.goals) && plan.goals.length` → `status: "ready"` and wait for person (145-147); empty plan → direct run (148-149). [DERIVED]

**startDeep(idx, q, request, goals, estimateS?)** (159-173)
- post: `estimateS: estimateS ?? presetSeconds(request.preset)` (160); `plan` sent only when `goals` non-null, stripped to `{ goal, query, move }` (163); streams via `deepResearchStream` (167-169). [DERIVED]

## effect surface
- Network: `api.reasoningModes(s)` (72); `runTurn(body, ...)` with `{ message, corpus_id, mode, require_retrieval, synthesizer?, reasoning?, corpus_explorer? }` (107-110, 114-116); `api.deepResearchPlan({ question, corpus_id, preset, mode }, ac.signal)` (145); `runTurn(deepRequest, ..., deepResearchStream)` (167-169); `stopStream(session.id)` (188, 189, 271). [DERIVED]
- Browser-persisted settings: `useComposerSettings()` — mode/model/Corpus Explore "kept per browser" (24-27, 62); `loadSkipPlan()` — "start without showing the plan" setting (128-129, 135). [DERIVED]
- DOM writes: textarea `height`/`overflowY` (79-84); `scrollTop = scrollHeight` on turn change (89-90); `scrollIntoView` for `focusTurn` (96); `inputRef.current?.focus()` (180, 204). [DERIVED]
- Timers/clock: `setTimeout(..., 2000)` copy reset (320); `Date.now()` on run start (160). [DERIVED]
- Postgres/Qdrant: none in this file (FACTS `tables_read: []`, `tables_written: []`); env flags: none read. [DERIVED]

## invariants
INVARIANT: `require_retrieval` === `true` on every normal send body — frontend-v2/src/screens/Chat.tsx:107 [DERIVED]
  fails-if: a turn can be answered without retrieval grounding.
INVARIANT: `corpus_explorer` in body iff `corpusExplore && corpusExploreAvailable` — frontend-v2/src/screens/Chat.tsx:110 [DERIVED]
  fails-if: request sent against user choice or to a server without the capability.
INVARIANT: `busy === !!turns[turns.length-1] && !turns[turns.length-1].done` — frontend-v2/src/screens/Chat.tsx:69-70 [DERIVED]
  fails-if: double-send or Stop/Send button flips mid-stream.
INVARIANT: textarea height = `min(scrollHeight, maxHeight || 320)` px — frontend-v2/src/screens/Chat.tsx:81-84 [DERIVED]
  fails-if: composer grows unbounded or clips text.
INVARIANT: `preset` ∈ {`"quick"`, `"standard"`, `"thorough"`}, initial `useState("standard")` — frontend-v2/src/screens/Chat.tsx:65, 252-254 [DERIVED]
  fails-if: deep request carries an unknown preset string.
INVARIANT: turn patching addressed by `idx = turns.length` captured at send — frontend-v2/src/screens/Chat.tsx:105, 115, 124, 136 [DERIVED]
  fails-if: if `turns` is reordered/spliced mid-stream, patches land on the wrong turn (index addressing, not id).
INVARIANT: copied flag resets after `2000` ms — frontend-v2/src/screens/Chat.tsx:320 [DERIVED]
  fails-if: "Copied" confirmation never clears.
INVARIANT: reasoning `""` renders as the option labeled `reasons.data?.default ?? "default"` — frontend-v2/src/screens/Chat.tsx:261 [DERIVED]
  fails-if: select shows a value the server does not treat as default.

## determinism & idempotency
determinism: NONDETERMINISTIC (network 72/114/145/167; clock `Date.now()` 160; timers 320; user input/events throughout). [DERIVED]
idempotency: UNSAFE — `send`/`sendDeep` append a new turn (106, 136) and `startDeep` opens a stream (165); re-invoking with the same question duplicates turns; only guard is the `busy` check at 102. [DERIVED]

## failure behaviour
- `sendDeep` catch: `olderPlanBackend(e)` → silent fallback to direct `startDeep` (153); otherwise turn set `done: true`, `error: e instanceof ApiError ? e.message : String(e)`, `deepRun.status: "cancelled"` (154). [DERIVED]
- Abort during planning: turn set `done: true, error: "cancelled"`, `status: "cancelled"`, and the question is restored to the composer (`setQuestion((cur) => cur || q)`) (139-142). [DERIVED]
- Run streams release registration via `finally { endStream(id, ac) }` even on throw (117-118, 170-171). [DERIVED]
- Render: `t.error` shown in `.answer-error` (297); done with no `answerText` and no error → fixed "empty-answer" message (302-307). [DERIVED]
- `reasons` fetch failure is not surfaced: select falls back to one option labeled `default` (261). [DERIVED]

## dumb-code flags
- Magic numbers: `320` px max-height fallback (82); `2000` ms copy reset (320). [DERIVED]
- `key={i}` — array index as React key on turns (213). [DERIVED]
- `stopStream(session.id)` literal repeated 3× (188, 189, 271). [DERIVED]
- Preset strings `"quick"`/`"standard"`/`"thorough"` duplicated between state default (65), `<option>` list (252-254), and `researchNext`'s `setPreset("quick")` (179). [DERIVED]
- `sendDeep` early returns on abort (146, 151) skip `endStream(id, ac)` begun at 138 — cleanup must come from `stopStream` itself [INFERRED: not visible in this file]. [DERIVED]
- Reasoning default `""` and display fallback `"default"` (63, 261) are two literals for one concept. [DERIVED]

## refactor notes
- Sole importer is `frontend-v2/src/App.tsx` (FACTS.importers) — any prop change to `Chat` has blast radius of exactly that file. [DERIVED]
- Deep-research state lives on the turn (`t.deepRun`) so a chat switch keeps the plan card and live view (122-124); moving it into component state breaks that DR7 behavior. [DERIVED]
- `mode`/`model`/`corpusExplore` come from `useComposerSettings` owned by the top bar (24-27, 62); re-adding them to the composer duplicates state and violates HEADER-CONTROLS. [DERIVED]
- Wire field names `message`, `corpus_id`, `mode`, `require_retrieval`, `synthesizer`, `reasoning`, `corpus_explorer`, `question`, `preset`, `plan` (107-110, 161-163) are the server contract; renaming breaks the API. [DERIVED]
- `TurnView` dispatches to `ResearchTurnView` when `isResearchTurn(t)`, coupled via the `ResearchHandlers` shape (184-191, 289); changing either side requires updating `components/deep/ResearchTurn.tsx`. [DERIVED]
- Index-based turn patching (105/115) assumes the turns array is append-only for the stream's lifetime; any insert/reorder feature must switch patches to a stable id. [INFERRED: index addressing is visible, the reorder hazard follows]

## VERIFY
```verify
grep -Fq 'require_retrieval: true' frontend-v2/src/screens/Chat.tsx
grep -Fq 'const [preset, setPreset] = useState("standard");' frontend-v2/src/screens/Chat.tsx
grep -Fq 'if (corpusExplore && corpusExploreAvailable) body.corpus_explorer = true;' frontend-v2/src/screens/Chat.tsx
grep -Fq 'setTimeout(() => setCopied(false), 2000)' frontend-v2/src/screens/Chat.tsx
grep -Fq 'key={i}' frontend-v2/src/screens/Chat.tsx
grep -Fq 'stopStream(session.id)' frontend-v2/src/screens/Chat.tsx
! grep -Fq 'corpus_explorer: true' frontend-v2/src/screens/Chat.tsx
```
