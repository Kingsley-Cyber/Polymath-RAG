---
change_id: ENRICHMENT-SURFACES-AUDIT
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "none — documents and read-only evidence scripts only. An audit of whether the enrichment surfaces reach answers, the feasibility report's §11 (open-source parsers), and a CONTINUITY refresh. No code, flag, schema or data change."
last_reviewed: 2026-09-23
---

# ENRICHMENT-SURFACES-AUDIT — do the skeleton, pMAP, profile and atoms reach the answers?

## Contract
Owner, 2026-09-23: "audit the document extraction skeleton and profile to see if they are used and reach the answers, like
seealso, questions … when complete give me the prompt to kickstart a fresh compaction to continue. Analyze the bootstrap
polymath skill: is it still good to use, or does it need to be updated." Also, the same day: "we are not building the parsers
from scratch; repos already have it that are open source that we can add into our repo."

## Changes
- NEW `docs/wiki/reports/2026-09-23/ENRICHMENT-SURFACES-AUDIT.md` contains:
  - a verdict per surface;
  - the per-lane funnel;
  - answers on SEEALSO and questions;
  - nine defects ranked by effect;
  - a latency signal;
  - six recommended fixes (owner decisions).
- NEW `docs/wiki/experiments/enrichment-surfaces-2026-09-23/`: three read-only, zero-cost scripts and their outputs:
  - `receipt_audit.py` / `.json`: per-lane funnel over the owner's UI turns, enrichment-only share, resolution-lift
    cross-encoder ranks, and retrieve latency before / after `5df4536`;
  - `surface_counts.py` / `.json`: profile, atom and parent-map points per corpus, and the lift vocabulary;
  - `replay_probe.py` / `.json`: lifted terms (one real turn per intent) and the bridge-compiler concept labels (three real
    questions), both in-process with no LLM call.
- `docs/wiki/reports/2026-09-23/CODE-KNOWLEDGE-V1-FEASIBILITY.md` §11: every parser comes from an existing open-source package
  (libcst, tree-sitter + tree-sitter-luau, the luau-analyze release, PyYAML, Microsoft.PowerFx.Core, the Canvas Authoring MCP)
  behind a thin adapter. Versions and licenses were checked on 2026-09-23.
- `docs/wiki/plans/CONTINUITY-REPORT.md`:
  - the preamble's read order now points at the CURRENT block (it still named the 2026-09-09 handoff and the librarian
    checklist);
  - the CURRENT block is rewritten in the structured bootstrap format.
- Register 11.415; scaffold `TREE` entries for the 8 new files.
- Outside the repository:
  - the polymath-bootstrap skill (`~/.claude/skills/polymath-bootstrap/SKILL.md`) was refreshed for drifted facts: forensic
    hold lifted, `origin/production` exists, the fleet shape, `local_extractor` retired, the realignment docs are no longer
    controlling, and the worktree PYTHONPATH recipe (measured);
  - new traps were added to the skill: `test_live_*` spend, a worktree has no `.env`, git-ignored `dist`, receipts first, and
    the pgrep self-match.

## Proof
- EXECUTED (read-only, $0):
  - the funnel of 1,508 `chat_stream` receipts (status ok, 7 days to 2026-09-23);
  - Qdrant and Postgres counts;
  - in-process replays of real turns through `chat_retrieval.chat_retrieve_mode` and `ui._profile_scout` +
    `bridge_integration.concepts_from_nominations`.
  - Every number in the report is in the committed JSON outputs.
- READ: the producer→prompt trace at `7eb767d` (a read-only sub-agent). I re-read the anchors behind each defect before
  recording it:
  - `resolution_lift.py:105-118`;
  - `chat_retrieval.py:360-377`;
  - `candidate_engine.py:853-869`;
  - `profile_scout.py:138-147`;
  - `bridge_integration.py:35-52`;
  - `ui.py:1538-1544` and `:2370-2389`;
  - `projection.py:28`.
- Worktree import resolution was measured for the skill refresh on `pmv4-librarian`. Without PYTHONPATH, `polymath_shared` and
  the `orchestrator.*` / `workers.*` / `control.*` submodules resolve to MAIN. With the four worktree dirs on PYTHONPATH,
  all four resolve to the worktree.
- Guards: see the commit (preflight / repo_guard / wiki_worm / bundle_integrity).

## Rejected claims
- "The profile's SEEALSO reaches answers": only the atom store's SEEALSO does (≈ 1 per doc for cinema), through lane G, in
  RELATIONSHIP / EXPLORATORY turns. The profile's 638 SEEALSO items are never searched.
- "Aliases improve retrieval": for cinema they reach retrieval only through the resolution lift, which put 0 of 7,806
  candidates into the evidence in 7 days.
- "The subquery cap 10 made HYBRID faster": the warm replay said 5.3–5.7 s. The live retrieve phase since the deploy is
  ≈ 30 s (n = 4). This is a signal to measure, not yet a cause.
- "Worktree tests of orchestrator / workers / control are never valid proof" (the old skill text): they are valid when the
  four worktree dirs are on PYTHONPATH and `find_spec` confirms the origins.

## Open contract gaps
- None changed by this slice (documents and read-only scripts): NOT_AFFECTED.
- The nine defects in report §4 are recorded, not fixed. Each fix is a separate admitted slice after the owner's word
  (report §6). Fixes 1, 3, 5 and 6 touch orchestrator / shared code (stale-bundle fence, bounce).
- CODE-KNOWLEDGE-V1 stays BLOCKED on the 13 owner decisions (feasibility report §8 + §10). The lift redesign (fix 1) should be
  settled before its slice C10, because for code, identifiers are the vocabulary.
