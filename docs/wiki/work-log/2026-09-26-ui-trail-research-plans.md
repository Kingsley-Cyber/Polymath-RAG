---
change_id: UI-TRAIL-RESEARCH-PLANS
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Docs only: the friends-access runbook, and three PROPOSED plans the owner asked for (frontend refresh, a Trail interface, a deep research mode). Nothing is built; each plan waits for the owner's decisions."
architecture_impact: "docs/runbooks/friends-access.md (new), docs/wiki/plans/FRONTEND-REFRESH-V1.md (new), docs/wiki/plans/TRAIL-INTERFACE-V1.md (new), docs/wiki/plans/DEEP-RESEARCH-MODE-V1.md (new), scripts/scaffold_polymath_v4.py (TREE), PLAN-AUTHORITY-REGISTER, CONTINUITY."
last_reviewed: 2026-09-26
---

# Friends-access runbook and three proposed plans

## Contract
- The owner, 2026-09-26: "after this created documentations for this part … plan improving the frontend, i think the themes are
  bad and ugly, i dont want to make it heavy but its needs improvement and planned out, and i think the trail signal os needs a
  interface or design, and plan a deepresearch mode design that is based on github and easy to implement."
- Docs only. No code, no config, no live change.

## Changes
- `docs/runbooks/friends-access.md`: the friends' and the owner's guide to FRIENDS-ACCESS-V1. It covers:
  - signing in, what friends can and cannot do, and connecting an agent;
  - adding and managing friends, and the command-line fallback;
  - how the web boundary works, a troubleshooting table by error code, the live check, and going back to the shared password.
- `docs/wiki/plans/FRONTEND-REFRESH-V1.md`: PROPOSED.
  - 14 measured problems, the "quiet library" direction, tokens with computed contrast, Light / Dark / System + accent (with a
    migration map for the ten old theme ids), the layout at three widths, and in-house UI pieces.
  - Slices U0–U6, the tests that pin markup, and four owner decisions.
- `docs/wiki/plans/TRAIL-INTERFACE-V1.md`: PROPOSED.
  - A Research section in `frontend-v2`, nothing inside TrailSignal (its governance needs ADRs and a build-graph node for
    any change; ADR-063 makes Polymath the owner of hypothesis state).
  - `GET /adapter/runs`, `GET /adapter/{id}/view` and `/report` (read-only, owner-scoped); screens for runs, progress,
    outcome, gates, evidence, lived world, concepts, report; slices T0–T6; six owner decisions.
- `docs/wiki/plans/DEEP-RESEARCH-MODE-V1.md`: PROPOSED.
  - dzhng/deep-research's breadth × depth loop (MIT) rebuilt in Python on Polymath's evidence retrieval, chosen after a
    GitHub survey of 12 projects (langchain open_deep_research archived 2026-08-21; HKUDS has no license).
  - A composer switch plus `POST /research/deep` on the chat stream's frame types; presets 3×1 / 3×2 / 4×2 with a cost
    table; citation checks; slices DR0–DR5; seven owner decisions.
- `GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md`: new row **A-15**.
  - A finished run's `result.output.qualifications` comes back empty when a later step emits an empty list: the worker
    keeps empty lists and `_gather` takes the newest.
  - Evidence: the R7 result has `[]`, while the embedded Trail store holds 2 `opportunity.qualify` results for that run.

## Proof
- Screens seen in the in-app browser on :7200 (owner view) at 1280×800 and 375×812, in four of the ten themes.
- Frontend facts come from a read-only audit of `frontend-v2` at `7e1918c2` (graft-first). The token contrast figures in the plan
  were computed with the WCAG formula.
- A-15 checked directly: `result.json` `output.qualifications` is an empty list (6 score refusals, 0 scores). A read-only
  query of the embedded store lists 2 `opportunity.qualify` operations with 1 result each for the R7 run. The code path was
  read at `adapter_step_worker.py:509-514` and `service.py:658-669`.
- The GitHub facts (licenses, stars, activity, archive status) were verified on the repositories and the GitHub API on
  2026-09-26. The Polymath and TrailSignal facts come from read-only, graft-first surveys.
- Guards: preflight, repo_guard, wiki_worm = 0 (recorded at commit).

## Rejected claims
- "The Files screen lost its documents after the friends-access merge": it was still loading. The loading state renders
  "0 documents" and "not reachable", which is itself problem P4 in the frontend plan.

## Open contract gaps
- All three plans wait for the owner's decisions; none is a plan of record until the owner says so.
