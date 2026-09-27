---
change_id: DEEP-RESEARCH-DR2
owner: "@king"
date: 2026-09-26
status: complete
status_note: "POST /research/deep streams the research loop over the caller's libraries on the chat's frame types; scope enforced on every search, one run per person, cancel on disconnect, a receipt."
architecture_impact: "orchestrator/orchestrator/api/deep_research.py (new), orchestrator/orchestrator/main.py (router), orchestrator/orchestrator/web_boundary.py (one rule), shared/polymath_shared/principal_context.py (acting_as), shared/polymath_shared/query_receipts.py (meta whitelist), frontend-v2/vite.config.ts (/research proxy), tests/contracts/test_deep_research_route.py (new)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR2: POST /research/deep

## Contract
- DEEP-RESEARCH-MODE-V1 §4 / slice DR2 (plan of record 11.504). Owner decisions: a composer switch with its own route,
  libraries only, presets, one run at a time for friends, the composer's model writes the report.

## Changes
- **`POST /research/deep`**, taking `{question, corpus_id | corpus_ids, preset, mode, synthesizer}`.
  - The libraries are checked once (`web_scope.require_corpora`: a friend reaches only libraries they may read). Every
    search then calls `/retrieve`'s implementation in-process with exactly those libraries AND under the caller's principal.
  - **The principal is re-applied on each worker thread.** A context variable does not cross threads, and a worker thread
    without it would read as the trusted-local owner. The new `principal_context.acting_as(principal)` carries the
    request's own principal onto the coroutine each worker thread schedules.
  - **Citation aliases.** Per-run aliases (c1, c2, …) keep the model's citations short and exact; the answer resolves them
    back to evidence rows (id, kind, document, library, title, source, text).
  - **Model lanes.** Planning and extraction run on the chat compiler's governed lanes: the per-lane limiter, two attempts
    across lanes, a 60 s timeout per call. The report is written by the composer's model, `litellm:` or `ollama:` ids as chat
    accepts them.
  - **Frames.** The chat's own types: `phase` (progress with readable labels), `token` (the report), `answer` (kind
    `deep`: text, citations, unknown citations, and the run's counts in `meta.deep_research`), `error`, `done`. SSE comment
    keep-alives are sent after 15 s of silence.
  - **Limits and records.**
    - One run at a time per person (409 `DEEP_RESEARCH_BUSY`).
    - Any exit or a client disconnect sets the cancel flag; the engine stops within a quarter second.
    - A `deep_research` receipt is written (`meta.deep_research` whitelisted in `query_receipts`).
    - Refusals come before any work: 422 no library / unknown preset / unknown synthesizer, 403 a library the caller
      cannot read.
- The web boundary lists it as USER class, and vite proxies `/research` for the dev server.

## Proof
- `test_deep_research_route.py`, 9 tests, over a real route with fake search results and fake model replies:
  - the frame order, with tokens before the answer and `done` last;
  - citations resolved from an alias to its row;
  - every search under the caller's principal and exactly the requested libraries (a mutant without `acting_as` fails this test);
  - 403 before any search;
  - 422 for no library and for a bad preset;
  - 409 for a second run by the same person, while another person may run;
  - the run slot is released and the receipt written;
  - `NOTHING_FOUND` ends with an error frame and then `done`;
  - keep-alive comments on a slow stream;
  - the boundary classification.
- Totals: `tests/contracts` 308 passed; ruff: no new findings.

## Contract dispositions
- CHAT / SSE frame contract: TESTED_UNCHANGED. A new producer uses the existing frame types (`answer.kind` gains the value
  `deep`); the chat routes are untouched.
- QUERY_RECEIPTS: UPDATED. The meta whitelist gains `deep_research`; the schema is unchanged.

## Rejected claims
- "Building the retrieval request from the resolved libraries is enough to keep a friend's scope": the worker thread lost
  the principal, so the route re-applies it too (defence in depth; proven by the mutant).

## Open contract gaps
- **DR0 (deferred).** A dedicated `deep_research` stage in `config/llm_accounts.yaml` (today the chat compiler's lanes are
  shared), and turning on the reserved deep-research retrieval surfaces (ANCHOR, broad SEEALSO, broad BRIDGE, RECALLQ).
- **DR3.** The composer switch and progress UI.
- **DR4.** Five live questions, on the owner's word.
- The orchestrator needs a bounce after merge.
