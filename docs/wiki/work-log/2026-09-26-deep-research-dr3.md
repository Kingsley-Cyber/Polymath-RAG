---
change_id: DEEP-RESEARCH-DR3
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The Deep research switch in the chat composer: its own route and request, progress in the process rail, a report with resolved sources."
architecture_impact: "frontend-v2 only: src/lib/api.ts (sseStream, deepResearchStream), src/lib/chat.ts (DeepAnswer, runTurn's stream parameter), src/screens/Chat.tsx (switch, depth, sendDeep), src/components/AnswerBody.tsx (DeepSources), src/styles/app.css, src/__tests__/chat-deep.test.tsx (new), src/__tests__/live-contract.test.ts (deep request fields)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR3: the composer switch

## Contract
- DEEP-RESEARCH-MODE-V1 §4 UI / slice DR3 (plan of record 11.504). Owner decisions: a switch in the composer, presets, the
  composer's model writes the report.

## Changes
- **The composer.**
  - A "Deep research" chip, and while it is on, a "Depth" chip (Quick / Standard / Thorough).
  - The placeholder says "Research <library> in depth…".
  - Corpus Explore hides while deep research is on (the two are different surfaces).
- **The request.** `sendDeep` posts `{question, corpus_id, preset, mode, synthesizer?}` to `/research/deep`, never to
  `/chat/stream`, and the turn is labelled "DEEP · <depth>".
- **The client.**
  - Both streams now go through one SSE reader (`sseStream`); keep-alive comments carry no data and are skipped.
  - `runTurn` takes the stream to read.
  - An `answer` frame of kind `deep` fills `turn.deep` (citations, unknown citations, the run's counts).
- **The answer.**
  - The report renders as Markdown, with a Sources list: each id (c1 …) resolved to its title and source, and the passage behind a disclosure.
  - Below it: the run's findings, searches and stop reason, and any cited id the research did not hold.
  - A 409 (one run at a time) shows as the turn's error.
- **The live contract test** now checks `deepResearchStream` too. Its request fields are read from Chat.tsx's `deepRequest`
  and checked against the backend's request schema, the same way the chat's `body` is.

## Proof
- `chat-deep.test.tsx`, 3 tests:
  - the switch and depth send exactly `{question, corpus_id, preset: "thorough", mode}` to `/research/deep`, with no chat stream;
  - the progress, the report, the resolved sources, the counts and the unknown id render;
  - a 409 is reported, not swallowed.
- vitest 86 passed (the live contract checks include the new stream against :7200). `tsc` clean.

## Rejected claims
- None.

## Open contract gaps
- DR4: five live questions, on the owner's word.
- DR0: a dedicated lane stage, and the reserved deep retrieval surfaces.
