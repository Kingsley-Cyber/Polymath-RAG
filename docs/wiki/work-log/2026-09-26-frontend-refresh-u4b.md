---
change_id: FRONTEND-REFRESH-U4B
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Citation markers in answers are focusable chips with a card naming the source; FRONTEND-REFRESH-V1 complete."
architecture_impact: "frontend-v2 only: src/components/Citations.tsx (new), src/components/AnswerBody.tsx, src/styles/app.css, src/__tests__/citations.test.tsx (new)."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U4b: citation hover cards

## Contract
- FRONTEND-REFRESH-V1 §6 Chat (the citation cards left open by U4, 11.509).

## Changes
- **The chips.** A remark step in `Citations.tsx` splits `[S1]` (chat) and `[c1]` (deep research) markers out of answer
  text, with no package added. Code spans and links are left alone.
  - Each marker becomes a chip that keeps the model's marker verbatim, so page text and copy-paste stay faithful.
  - Its accessible name is "Source S1: <title>".
  - A card shows on hover or keyboard focus, and click pins it: the source title, where in it (breadcrumb / heading /
    locator), and the passage (capped at 420 characters).
- **Where a card comes from.**
  - Chat: the receipt's legend (tag → chunk) joined to its chunks (title, preview).
  - Deep research: the report's resolved citations.
  - An unknown marker stays a chip, without a card.

## Proof
- `citations.test.tsx`, 3 tests:
  - a chat marker: its name, the card's place and passage, code untouched, click pins the card;
  - a deep research marker resolves its own source;
  - an unknown marker has no card.
- The chat-session tests pass unchanged (the marker text is kept). vitest 89 passed; `tsc` clean.

## Rejected claims
- "Show the marker without brackets": the answer's text would then differ from what the model wrote. The chip keeps `[S1]`.

## Open contract gaps
- None for the frontend refresh.
