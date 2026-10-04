---
change_id: COPY-ON-HOVER-V1
owner: "@king"
date: 2026-10-04
status: complete
status_note: "Chat: a small copy button appears when the pointer is over a question (input) or an answer (output) and copies exactly that text; it shows 'Copied' for two seconds. Before, only the answer had one, always showing; the question had none. UI only: built and proven in a real browser against a read-only preview; goes live with the next UI build (no restart needed, so it does not touch a running ingest)."
architecture_impact: "frontend-v2 ui/CopyButton.tsx (new, shared), screens/Chat.tsx (the question bubble and AnswerActions use it), components/deep/ResearchTurn.tsx (the research question bubble), styles/app.css (.msg-user row order, .copy-btn--hover reveal rules); tests."
last_reviewed: 2026-10-04
---

# COPY-ON-HOVER-V1: copy a question or an answer from a hover button

## Contract
- The owner, 2026-10-04: "there should be an input and output simple button that shows up when I hover with mouse to simply
  copy."

## Measured (the code and the live app)
- `Chat.tsx` had `AnswerActions`: one copy button under a finished answer, always showing. The question bubble (`.msg-user`) and
  the deep-research question bubble (`ResearchTurn.tsx`) had none.

## Changes
- **`ui/CopyButton.tsx`** (new): one button for both; `copyText` (the existing clipboard helper with its textarea fallback);
  the label flips to "Copied" with a check for two seconds (the timer is cleared on unmount).
- **Question** (chat and deep-research turns): the button follows the bubble in the markup, so the bubble's `:hover` reveals it
  (`.msg-user__bubble:hover + .copy-btn--hover`); the row now reads right-to-left in CSS (`row-reverse`) so the bubble stays at the
  right edge and the button sits on its left. **Answer**: the same button inside `.answer-actions`, shown on `.msg-assistant:hover`.
- **Always shown** where hover cannot work or must not hide it: keyboard focus (`:focus-visible`), the two seconds of "Copied",
  and touch screens (`@media (hover: none)`). Not offered on an answer still streaming (the text is incomplete).

## Proof
- `chat-copy.test.tsx` (6, jsdom): both buttons exist with the hover class and the question's follows its bubble; copying the
  question puts exactly the question on the clipboard, reads "Copied" (class `copy-btn--done`) and goes back after 2 s (fake
  timers); copying the answer puts the Markdown as written; a streaming answer has no answer copy but its question does; a
  deep-research turn's question has the button; the stylesheet contract (hidden by default, the four reveal selectors, the touch
  rule). Whole UI suite 186 passed, 7 skipped; `tsc` clean.
- Fail first on the live UI (`620c13dd`): 5 of the 6 fail (the existing answer copy passes).
- Sealed CI reproduction on this tree (throwaway Postgres, nothing else reachable): contracts **878 passed**, 5 skipped, 0 failed.
  The determinism suite was NOT re-run: no backend file differs from the last full run (`ef8b55cd`: 3,301 passed); this slice
  changes frontend files, docs, the scaffold list and the code wiki (2,239 / 2,239; guards 0).
- A real browser (the side-copy build served read-only on a spare port with the sign-in carried by the cookie): buttons hidden at
  rest; hovering the question shows its icon on the left of the bubble; hovering the answer shows its icon under the text;
  clicking each (clipboard stubbed so the owner's clipboard stayed untouched) copied exactly the question and the answer Markdown,
  the label read "Copied" with opacity 1, and both returned to "Copy question" / "Copy answer" after 2 s.

## Contract impact (pre-commit)
- `contract_impact.py --check --staged`: none (no changed file maps to an architecture contract).

## Rejected claims
- "Make the button always visible": the owner asked for hover; touch screens keep it visible because they cannot hover.

## Open contract gaps
- Copy buttons for a source passage and a deep-research report section are not part of this request.
