---
change_id: DEEP-RESEARCH-DR7-ADMISSION
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The research experience (plan card, live research view, evidence-based report with a sentence audit, actions, reports list) admitted into DEEP-RESEARCH-MODE-V1 as §11 and slices DR7a–DR7f."
architecture_impact: "docs only: docs/wiki/plans/DEEP-RESEARCH-MODE-V1.md (§5 rows, §11)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR7: admitting the research experience

## Contract
- The owner, 2026-09-26: "can you using your creative training data, make this deepresearch comparable and better designed".

## Changes
- DEEP-RESEARCH-MODE-V1 §11 (DECIDED):
  - what the best research tools do (plan first, visible rounds, outline-first reports, history and export) and where they
    are weak (confidence from tone, unaudited citations, buried disagreement, a hidden method);
  - Polymath's five parts: plan card, live research view, evidence-based report with a sentence audit, actions, reports list;
  - the backend contracts: `/research/deep/plan`, a confirmed `plan`, `/research/deep/finish`, coverage frames,
    `report_model`, `audit`;
  - the deterministic evidence model and the `coverage_complete` stop;
  - the build order and the live acceptance.
- §5 gains DR7a–DR7f.

## Proof
- Grounded in the code:
  - the chat history is browser-only by design (`frontend-v2/src/lib/chatStore.ts`, CHAT-HISTORY-V1), so the reports list reads
    it and needs no migration;
  - chat has no document scoping, so "research this next" starts a new deep research run instead of a scoped chat turn;
  - migrations 0067–0071 are reserved for code RAG.

## Rejected claims
- "Comparable means a server-side history now": that would change CHAT-HISTORY-V1's deliberate browser-only rule, which is the
  owner's decision. It is recorded as an option.

## Open contract gaps
- Server-side report history (owner decision; a migration after 0071).
- Multi-library research: HYBRID answers one library per call (§10 admission gap).
