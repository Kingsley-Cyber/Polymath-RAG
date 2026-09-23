---
change_id: GROUNDED-LEARNING-OBJECTIVE
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents only. Records the owner's retrieval objective (grounded learning value), the policy input the owner shared (not yet decided), where the retrieval path is lost in today's code, and which laws conflict with the objective."
last_reviewed: 2026-09-23
---

# The owner's objective is grounded learning value, and the path context is lost at five points

## Contract
Owner, 2026-09-23: "Before I make any decision, this is a convo I had; it reveals more about my project intent." In that
conversation the owner wrote: "I want a RAG pipeline that taps into latent or subdued chunks, since a lot of my corpus
knowledge is documents I'm not well versed on, so I may not know how to query properly. I'm using it to improve my
knowledge."

The shared conversation also contained ranking-policy recommendations from another assistant. They are recorded as input,
not as decisions. A second excerpt, shared in the same turn, gave an execution design:
- precompute relationships at index time;
- let the existing compiler plan every independent probe in one call;
- start the q0 search during compilation;
- search concurrently;
- batch the conditional judging;
- expand only for an identified gap;
- take a timing trace first.

## Changes
- `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md` §12:
  - the objective;
  - the shared policy input (marked undecided);
  - the five points where the path context is lost, with anchors;
  - which earlier recommendations are withdrawn;
  - which laws conflict with the objective;
  - the open decision on the admission judge.
- `docs/wiki/plans/CONTINUITY-REPORT.md`: the mission carries the objective, and the plan-of-record step names the decisions
  it must settle.
- Report §13: that execution design mapped to today's code, gap by gap. Two $0 first measurements: a timing trace of one
  slow turn, and a trace of one dropped chunk through every judge.
- Report §5 CORRECTED: `meta.phase_ms` marks are cumulative. For owner-style turns since `5df4536` (n = 6, before the
  thinking fix): compile ≈ 12 s, retrieval ≈ 19 s (GNN 3 s), synthesis 34–51 s. The 7-day "before" medians are mostly
  harness turns, so they are not a clean baseline.
- Report method CORRECTED: the 1,508 turns are live pipeline runs over 139 distinct questions, mostly the 2026-09-18
  qualification runs (1,397 with deterministic synthesis), not owner-typed questions.
- `receipt_audit.py`: phase durations are now computed from the marks, and a `population_7d` block is added. The lane
  numbers are unchanged on rerun.
- Register 11.418; a scaffold `TREE` entry for this work-log.

## Proof
READ at `3aa531e` (the code is unchanged since `7eb767d`):
- `candidate_engine.py:814–919` (lanes D–I use `query_ids=[ctx.query_id]`) and `:1447` (`rerank_children(result.context.query,
  rows)`);
- `bridge_integration.py:46`;
- `latent_selection.py:65–96`: q0↔bridge in one call, bridge↔chunk in one call per bridge, and q0↔chunk reused.
  `evaluate_candidate` then combines them by floors (`latent_eligibility.py:142`), and `seat_portfolio` seats by caps with
  adequate-direct first (`latent_portfolio.py:47`, docstring lines 15–16);
- `ui.py:3519`.

## Rejected claims
- "Live retrieve is about 30 s" (11.415, audit §5): wrong. The `retrieve` mark is cumulative and includes the ≈ 12 s
  compile. Retrieval itself is ≈ 19 s.
- "1,508 real UI chat turns / the owner's turns" (11.415, audit method): wrong population. They are live pipeline runs through
  the UI streaming endpoint over 139 distinct questions, mostly qualification runs. The lane measurements stand as pipeline
  measurements.
- "Compile and retrieval regressed after the cap-10 deploy": not established. The before / after populations differ, and the
  GNN turns (same population) show no change.
- "The bridge pass already judges the path": it judges three separate pairs and combines the scores with thresholds. No
  judgment sees question, bridge and chunk together.
- "A relevance floor against q0 protects quality": if it judges the isolated chunk, it reproduces the failure (§12). What
  survives is the rule that an unsupported connection never enters.
- My §11 two-hop product and the chat seat budgets as admission rules: withdrawn. They conflict with the objective.

## Open contract gaps
- None changed (documents only): NOT_AFFECTED.
- The owner has not decided. The consolidated plan of record must settle:
  - the objective as a law, amending FINAL l.39, FINAL §47, WLK2C non-displacement and ELITE §6 rule 1;
  - the admission-judge design (A / B / C / D; recommendation C);
  - the contribution taxonomy;
  - the judge's cost and latency budget;
  - the acceptance fixtures.
