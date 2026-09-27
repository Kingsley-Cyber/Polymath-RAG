---
change_id: DEEP-RESEARCH-DR4
owner: "@king"
date: 2026-09-26
status: partial
status_note: "Live proof: run 1 found every search empty (fixed, live a2b38e6a); run 2 = 4 of 5 cited reports, 100% of citations resolved; the 5th returned an empty report (fixed here, live after the next deploy, then that one question is re-run)."
architecture_impact: "orchestrator/orchestrator/api/deep_research.py (evidence_rows_of + _build_rows; the report step takes chat's reasoning policy; REPORT_EMPTY); tests/contracts/test_deep_research_route.py (+4 tests)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR4: live proof

## Contract
- DEEP-RESEARCH-MODE-V1 §5 slice DR4: 5 smoke questions across cinema and commerce-v1; every cited cid resolves, stop
  reasons are sensible, cost matches §3. The owner's "finish the incomplete ones" (2026-09-26) authorized it.
- Questions (probe outside the repo; report text stays out of the repo):
  1. cinema, quick: how the direction and quality of light change a shot's mood;
  2. cinema, standard: how Laban effort qualities help animators and actors convey emotion;
  3. commerce-v1, quick: what makes a new habit stick;
  4. commerce-v1, standard: how jobs-to-be-done thinking relates to blue ocean strategy;
  5. cinema, thorough: how shot choice and editing rhythm tell a story together.

## Changes
- **Run 1 (production `5fd5075b`): 5 of 5 NOTHING_FOUND, 20 of 20 searches empty.**
  - Cause: `/retrieve` builds `evidence_rows` only on the default lane. HYBRID (and every engine mode) answers with a flat
    `evidence` list and ignores `evidence: true`, and the route read only `evidence_rows`. The DR2 tests faked a retrieve that
    returned `evidence_rows`.
  - Fix (`a2b38e6a`, live after the owner's merge + bounce, READY 26/13/1): `evidence_rows_of` builds the same rows from the
    engine's list with `build_evidence_rows`, as `chat.attach_evidence_rows` does. Every other `evidence: true` caller (MCP
    tools, the ecommerce adapter) uses the default lane or EXPLORE.
- **Run 2 (production `a2b38e6a`):**

  | Question | Wall | Levels | Searches | LLM calls (+1 report) | Learnings | Cited / resolved | Stop |
  |---|---|---|---|---|---|---|---|
  | 1 cinema quick | 46.8 s | 1 | 3 | 4 | 9 | 11 / 11 | frontier_empty |
  | 2 cinema standard | 115.2 s | 2 | 9 | 13 | 27 | 11 / 11 | frontier_empty |
  | 3 commerce quick | 37.9 s | 1 | 3 | 4 | 9 | 15 / 15 | frontier_empty |
  | 4 commerce standard | 98.0 s | 2 | 9 | 13 | 23 | **0 (empty report)** | frontier_empty |
  | 5 cinema thorough | 132.2 s | 2 | 12 | 17 | 36 | 24 / 24 | frontier_empty |

  - Counts match §3 exactly (5 / 14 / 18 LLM calls with the report); times are inside the estimates. 0 unknown citations,
    0 dropped learnings, 0 empty searches, 0 errors.
  - Question 4: the report model (`deepseek-v4-flash` on the anthropic route) returned nothing and the route streamed a blank
    "unsupported" answer with no error. The report step called litellm without chat's reasoning policy
    (`POLYMATH_REASONING_POLICY=1` live), so thinking stayed on (the known v4 gotcha: it can spend the budget thinking).
- **Fix (this slice):** `_report_tokens` applies `reasoning_policy.apply_litellm(kwargs, CHAT_SYNTHESIS, model)` exactly as chat
  does (`thinking: disabled` for this model); an empty report ends with an error frame `REPORT_EMPTY` (the receipt records it).

## Proof
- `test_deep_research_route.py`, 15 passed (4 new, each failing first on the unfixed code):
  - an engine-shaped search feeds the research (it failed with NOTHING_FOUND);
  - rows come from `evidence_rows` first; nothing builds nothing;
  - an empty report is an error, not a blank answer (it failed: no error frame);
  - the report call equals chat's reasoning-policy kwargs (it failed: `thinking` / `allowed_openai_params` missing).
- `tests/contracts` whole: exit 0. Ruff: no new findings.
- Wire check of the rows fix (read-only, $0): the same live HYBRID searches gave 10 rows (cinema) and 6 (commerce-v1) with
  text where the route had 0.

## Rejected claims
- "DR2's route tests prove the searches work": they faked `evidence_rows`; only the live run showed the engine's shape.

## Open contract gaps
- The report fix is live only after the next merge + bounce; then re-run question 4 (one live run) to close DR4.
- `parse_repairs` equals the learning count in every run: the model's LEARNING lines never match the strict grammar (the
  lenient reader accepts them, and the receipt counts it). Tighten the extract prompt's example or widen the strict form.
- `/retrieve` silently ignores `evidence: true` on the engine modes. Either honour it or answer a typed 422, like
  `document_ids`.
