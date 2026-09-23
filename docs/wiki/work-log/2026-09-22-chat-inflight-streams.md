---
change_id: CHAT-INFLIGHT-STREAMS-V1
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "frontend-v2 only: App owns every chat's turns, keyed by chat id, and Chat.tsx reads them and writes through a functional updater. A chat's stream now lands in that chat after the user opens another one, Stop reaches it from any screen, and a turn cut off by a page reload reads as interrupted instead of busy forever. No backend or wire change."
last_reviewed: 2026-09-22
---

# Chat — an answer lands in its own chat after you switch chats mid-stream

## Contract
Owner report, 2026-09-22: "I created 3/4 new chats and tested the same question on different retrieval layers and only graph worked."
Expected: every chat shows its own answer, whichever chat is on screen when that answer arrives.

Evidence before the fix (all $0, read-only):
- Receipt ledger `query_receipts`: the owner's three turns (same question, corpus `cinema`, client `ui-stream`) all finished on the
  backend as `ok` / `generated` with evidence: GNN `q_bdd1abd51e` (150 s, 8 used evidence), HYBRID `q_be4b06b788` (88 s, 6),
  GRAPH `q_7eab052201` (81 s, 7). Retrieval worked in every mode, and so did synthesis.
- Orchestrator access log: `POST /chat/stream` for GNN, then a Chat remount (`/capabilities` + `/reasoning_modes` + `/synthesizers`),
  then `POST` for HYBRID, then a remount, then `POST` for GRAPH, then many remounts. Every chat switch remounts the Chat screen
  (`<Chat key={activeChat.id}>`).
- Code: `Chat.tsx` held the turns in its own `useState`, and `runTurn`'s `onUpdate` wrote to that instance. Opening another chat
  unmounted it and left the stream running with nowhere to land. App kept the turn as it was at the switch (`done: false`, no
  answer). GRAPH "worked" because it was the chat on screen when its answer arrived.

## Changes
- `frontend-v2/src/App.tsx`: `updateTurns(id, fn)` replaces `updateChat(id, turns)`. It is a functional update on App's session
  state, keyed by chat id, so a stream whose Chat screen is gone still updates its own chat. `deleteChat` stops that chat's stream.
- `frontend-v2/src/screens/Chat.tsx`: no local turn state. It renders `session.turns`, writes through `onUpdateTurns`, and
  derives `busy` from the chat's last turn, so a chat reopened mid-answer still shows as streaming. Stop calls
  `stopStream(session.id)`.
- `frontend-v2/src/lib/chat.ts`: `beginStream` / `endStream` / `stopStream`, a module-scope registry of live streams by chat id.
  A stream outlives the screen that started it, so Stop must reach it from any screen.
- `frontend-v2/src/lib/chatStore.ts`: `loadSessions` marks a turn left unfinished by a previous page as done, with the error
  `INTERRUPTED`. No stream survives a page load, and without this the chat would read as busy forever.
- `frontend-v2/src/__tests__/chat-session.test.tsx`: three cases, driving the real `App` through the real `runTurn` /
  `chatStream` against a fetch stub with several live streams:
  1. An answer lands in its own chat after you open another chat mid-stream (the owner's case: GNN, then GRAPH).
  2. A chat reopened mid-stream keeps streaming live, and Stop still cancels it (the request's signal is aborted, and the turn
     reads `cancelled`).
  3. A turn cut off by a reload reads as interrupted, and its chat is usable again.

## Proof
- On the unfixed code (`a0182c7`), all three new cases FAIL at the owner's symptom: "expected … to contain 'The GNN answer
  [S1].'"; "Streaming…: expected undefined to be defined"; the cut-off turn loaded with `done: false`.
- After the fix: `tsc --noEmit` clean; offline suite 16 / 16 (chat-session 6, chat-surface 7, retrieval-modes 2,
  proxy-covers-backend 1); `npm run build` clean.
- Proof level: UNIT_PROVEN (the executed path is this code: the real App, Chat, runTurn and chatStream under jsdom). After the
  merge, DEPLOYED: the served bundle is the one built from the merge. No live chat turn was spent to prove it. The backend half
  (every mode answering through the real client) is the live contract check, 12 / 12 earlier today (register 11.405).

## Rejected claims
- "FAST / HYBRID / WILDCARD / GNN retrieval is broken": refused. The receipts show every one of the owner's turns retrieved
  evidence and generated an answer.
- "The lost answers can be recovered": refused. The receipt ledger records the question, plan and evidence, not the answer
  text, so those turns have to be sent again.
- "Concurrency caused the failure": refused as the cause. Three turns at once were slower (81–150 s against 19–40 s alone;
  the GRAPH receipt records `embed_deadline` degraded, embedding 9.2 s against a 2.5 s deadline) but they all completed. Only
  the UI lost them.

## Open contract gaps
- Chat SSE frames (phase / reasoning / token / answer / error / done): TESTED_UNCHANGED. Handled 1 : 1 by the same `runTurn`.
- `/chat/stream` request body: TESTED_UNCHANGED (`{message, corpus_id, mode, require_retrieval}` + optional fields, pinned by the
  first chat-session case and the live contract check).
- `polymath-v2.chats` localStorage shape: NOT_AFFECTED (same fields; a stale unfinished turn is normalized on load, not migrated).
- Persistence cost: DEFERRED. Every stream frame still re-serializes the chat history to localStorage, as before this change.
  Throttle it if long threads make the UI sluggish.
