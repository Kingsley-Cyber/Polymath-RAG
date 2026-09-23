---
change_id: CHAT-COMPOSER-V1
owner: "@king"
date: 2026-09-22
status: complete
architecture_impact: "frontend-v2 only: the chat input is one rounded, Claude-style box whose textarea grows with its text up to a cap, with the send / stop button inside it; you can type while an answer streams. No backend or wire change."
last_reviewed: 2026-09-22
---

# Chat composer — a box that grows with the text, Claude-style

## Contract
Owner, 2026-09-22: "the ui textbox is weird with that scroll feature, why can't it be more like Claude or a React chat box."
Measured on the live page before the change: `textarea.chat__input`, `rows=1`, height fixed at 44 px, `overflow-y: auto`,
`max-height: 180px` never reached. Nothing resized the box, so a multi-line question scrolled inside a one-line box.

## Changes
- `frontend-v2/src/screens/Chat.tsx`: the composer is one `.composer` box: an auto-growing `textarea.composer__input`
  (a layout effect sets its height to its content, up to the CSS `max-height`, then scrolls inside) and a bottom bar holding
  the current mode and corpus, plus one round icon button: Send (↑, disabled when empty) or Stop (■) while an answer streams.
  Clicking anywhere in the box focuses the text. Enter sends; Shift+Enter is a newline; Enter never sends mid IME
  composition. The box stays editable while an answer streams (the next question sends once the answer is done).
- `frontend-v2/src/styles/app.css`: `.composer*` rules replace `.chat__composer-inner` / `.chat__input`: 18 px radius,
  focus ring on the box (`:focus-within`), `max-height: min(40vh, 320px)`, the send button in the theme accent, no hard
  border line above the composer (a fade into the thread instead).
- `frontend-v2/src/__tests__/chat-session.test.tsx`: `button()` also matches an accessible name (the icon buttons are
  "Send" / "Stop"). New case: Enter sends, Shift+Enter does not, the box stays editable mid-answer, Enter does not start
  a second stream, and the queued question sends after the answer.

## Proof
- Offline suite 17 / 17 (chat-session 7, chat-surface 7, retrieval-modes 2, proxy-covers-backend 1); `tsc --noEmit` clean.
- In the browser (Vite dev server from the worktree on :5274 against the live backend): empty box 30 px, send disabled;
  four lines → 98 px, no inner scrollbar; thirty lines → capped at 307 px (40 vh) with an inner scrollbar; cleared → back to
  30 px. No console errors. No message was sent.

## Rejected claims
- "The mode / model / reasoning controls moved into the composer like Claude's": not done. They stay in the card above
  the thread; the composer bar only shows the current mode and corpus.

## Open contract gaps
- `/chat/stream` request body: TESTED_UNCHANGED (the same `send()` builds it; pinned by chat-session and the live
  contract check).
