---
change_id: DOCUMENT-RAG-S1C-RECEIPT-WHITELIST-LATENT-LABELS
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "shared + orchestrator code on branch fix/s1c-receipt-whitelist-latent-labels. The stored chat receipt keeps S1a's four keys (they were dropped by the meta whitelist on every live turn). E3's seat label and the prompt's latent-label count apply only to the latent seats (COMPLEMENTARY / DIVERGENT), never to DIRECT / RELATED q0 seats. Receipt + prompt-label change only."
last_reviewed: 2026-09-23
---

# S1c: S1a's receipts survive storage; only latent seats are labelled and counted

## Contract
- RETRIEVAL-PATHWAYS-5Q (register 11.436, five live cinema turns) found two defects in S1a / E3.
  - `query_receipts.summarize_response` keeps only a whitelist of meta keys. It dropped `retrieval_trace`,
    `latent_selection`, `wildcard` and `trace_ms` on every live turn. The S1a harness test had captured the payload BEFORE
    summarization, the same defect class as backlog B7 (the generation receipt).
  - `prompt.latent_labels` was 15 on every turn, i.e. every selected row. WLK2C seats every row
    (DIRECT / COMPLEMENTARY / DIVERGENT / RELATED), and E3 labelled any seat, so the prompt showed `(DIRECT · DIRECT)`.
    E3 meant the latent seats only (`evidence_packet._SEAT_ROLES` = COMPLEMENTARY, DIVERGENT).
- Owner authority: "merge and bounce slices that pass their tests" (2026-09-23).

## Changes
- `shared/polymath_shared/query_receipts.py` (`summarize_response`): the whitelist adds `retrieval_trace`,
  `latent_selection`, `wildcard`, `trace_ms`.
- `orchestrator/orchestrator/api/ui.py`:
  - NEW `_LATENT_SEATS = ("COMPLEMENTARY", "DIVERGENT")`;
  - `_grounded_messages` adds ` · SEAT via: …` only for those seats; DIRECT / RELATED rows keep the plain role label;
  - `_LATENT_LABEL_RE` counts only those seats.
- Tests (new; none edited):
  - `test_query_receipts.py::test_summarize_keeps_the_s1a_turn_receipts`, through the REAL `summarize_response`;
  - `test_chat_synthesis.py::test_only_latent_seats_are_labelled_and_counted`: four seats, two labelled, count 2.

## Proof
- **Red first:** both new tests failed on `5bc598b` (KeyError `retrieval_trace`; `(DIRECT · DIRECT)` present in the prompt).
- test_query_receipts + test_chat_synthesis + test_turn_receipt_extras: 27 passed, 1 failed (the known pre-existing
  handlers-wired failure).
- **Wider run (EXECUTED):** test_chat_runtime, test_chat_synthesis, test_query_receipts, test_turn_receipt_extras,
  test_compile_steps_and_emitted_reasoning, test_chat_modes, test_chat_funnel, test_evidence_packet: 105 passed, 2 failed.
  Both failures are the known pre-existing compiler-on-both-routes and handlers-wired (they fail on production too).
- **Contract impact:** EVIDENCE_BOUNDARY_API / RETRIEVAL_RECEIPT UPDATED (the stored receipt keeps four additive keys).
  The rest are TESTED_UNCHANGED.

## Rejected claims
- "The harness receipt test proves the stored receipt": it proves the payload handed to the writer. The writer summarizes.
  The new test goes through `summarize_response` itself.

## Open contract gaps
- LIVE proof after the bounce: the next turn's stored receipt carries the four keys, and `latent_labels` ≤ the latent seats.
