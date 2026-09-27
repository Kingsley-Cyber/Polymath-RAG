---
change_id: FRONTEND-REFRESH-U4
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Chat: settings as chips inside the composer, a real empty state with starter questions, icon send/stop, Copy on each answer. Citation hover cards remain (U4b)."
architecture_impact: "frontend-v2 only: src/screens/Chat.tsx, src/components/AnswerBody.tsx (verdict wording), src/styles/app.css."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U4: Chat

## Contract
- FRONTEND-REFRESH-V1 §6 Chat / slice U4 (plan of record 11.504); problem P6.

## Changes
- **The boxed settings card above the chat is gone** (with the screen title; the top bar already names the library).
  Retrieval, Model, Reasoning and Corpus Explore are now compact chips in the composer's bottom bar, next to send. The model
  menu opens upward there.
- **The empty chat** says "Ask <library>", explains that answers cite their passages and that uncovered questions say so,
  and offers three starter questions. Clicking one fills the box; nothing is sent until Enter.
- **Send and Stop** are icons. **Copy** appears under each finished answer, with a "Copied" confirmation.
- **Verdict badges** read "Supported" / "Abstained" instead of upper case.

## Proof
- vitest 67 passed. The chat tests needed no change: the `.label` texts ("Retrieval" …) and the mode select keep their contract.
- `tsc --noEmit` clean.
- Seen on the dev server against :7200: the empty state, the starters and the chips. No live question was sent (live chat
  turns need the owner's word).

## Rejected claims
- None.

## Open contract gaps
- **U4b: citation hover cards.** A marker in the answer would open its source title, section and snippet. It needs the
  answer's citation markers mapped to the receipt's evidence rows; not built in this slice.
