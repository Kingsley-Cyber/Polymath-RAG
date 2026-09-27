---
change_id: DEEP-RESEARCH-DR6D
owner: "@king"
date: 2026-09-26
status: partial
status_note: "Live A/B on 17acf6c4: moves + the DR7 report won on citation honesty and counter-evidence, lost breadth on standard / thorough because the coverage stop cut level 2; fixed (a lookup may stop early, any other question keeps its depth); q2 and q5 re-run after the next deploy."
architecture_impact: "shared/polymath_shared/deep_research/engine.py (COVERAGE_STOP_INTENTS, _may_stop_early; the coverage event still follows every level); tests/contracts/test_deep_research_experience.py (+1 test; two stop tests use a lookup question)."
last_reviewed: 2026-09-26
---

# DEEP-RESEARCH DR6d: the live A/B, and the coverage stop fixed

## Contract
- DEEP-RESEARCH-MODE-V1 §10.9 (moves must cite ≥ the baseline's distinct documents on ≥ 4 of 5 questions, cover ≥ the baseline's
  goals, show counter-evidence or "none found" on evaluative / mechanism questions, stay inside the deadline with LLM calls ≤
  baseline + 10%) and §11.6 (DR7f: plan card ≤ 3 s, uncited ≤ 10%, counter-evidence, `coverage_complete`, deadlines).
- Probe outside the repo: `scratchpad/dr4/ab.py`, the 5 DR4 questions, `moves: false` then `moves: true`, one at a time, as the
  owner over loopback. Report text stays in the scratchpad.

## Changes
- **Run (production `17acf6c4`, 10 runs, 0 errors, every citation resolved):**

  | Q | Preset | Books off → on | Uncited sentences off → on | Counter-evidence (on) | Stop (on) | Time off → on | LLM calls off → on |
  |---|---|---|---|---|---|---|---|
  | 1 light & mood | quick | 4 → 4 | 20/29 → 3/15 | 3 | frontier_empty | 31 → 44 s | 4 → 4 |
  | 2 Laban effort | standard | **9 → 6** | 31/53 → 1/12 | 2 | coverage_complete (level 1) | 77 → 35 s | 13 → 4 |
  | 3 habits | quick | 2 → 2 | 16/26 → 0/15 | 3 | frontier_empty | 33 → 23 s | 4 → 4 |
  | 4 JTBD ↔ blue ocean | standard | 3 → 3 | 14/35 → 3/16 | none (RELATIONSHIP: no inverse slot by design) | coverage_complete | 66 → 39 s | 13 → 4 |
  | 5 shots & editing | thorough | **12 → 5** | 19/45 → 2/14 | 3 | coverage_complete (level 1; the gate dropped 1 query) | 95 → 30 s | 17 → 4 |

  - Question 4 (DR4's empty report) now answers: 32 citations resolved with moves off, 13 with moves on. **DR4 is closed.**
  - The plan card's call took 1.1–2.4 s. The moves-off reports use the old report prompt; the moves-on reports use DR7's (TL;DR,
    sections, disagreement), so the uncited rates compare the two whole pipelines.
- **Verdict against §10.9:** books ≥ baseline on 3 of 5 (q2, q5 lost), so **FAIL**. Cause: `coverage_complete` ended the
  standard and thorough runs after level 1 (every goal had 2 findings from 2 books), so they never read further.
- **Fix:** `coverage_complete` may end a LOOKUP (EXACT / DEFINITION) after any level; every other question keeps the depth
  the person chose until its second level (`COVERAGE_STOP_INTENTS`, `_may_stop_early`). The coverage event still follows
  every level: `_covered` runs first.

## Proof
- New test: a MECHANISM question covered at level 1 still runs level 2 (it failed on the old rule). The two early-stop tests
  now use a lookup question with the same quota ("What is habit stacking, and is it worth it?": DEFINITION + evaluative →
  1 / 1 / 0 / 1).
- `tests/contracts` 609 passed; the adapter/Trail determinism set 306 passed; ruff clean on the changed files.

## Rejected claims
- "Moves read fewer books": not in themselves. Every loss came from the early stop cutting level 2 (the losing runs stopped at
  level 1; the quick runs, which never have a level 2, tied).

## Open contract gaps
- After the next deploy, re-run q2 and q5 with moves on (2 live runs). They must reach ≥ 9 and ≥ 12 books, or be explained.
- DR7f's "uncited ≤ 10%" is met on 2 of 5 (0% / 8%; the others 14–20%). A stricter report prompt or a repair pass is the next
  lever. `coverage_complete` on a lookup question is still unproven live.
- The gate dropped one of q5's four planned queries; its floor (0.2) is unmeasured on real plans.
