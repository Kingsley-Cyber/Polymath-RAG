---
title: "HANDOFF ARCHIVE — drafts whose authoritative implementation has landed"
owner: governance
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: archive
---

# Applied handoff drafts (archive)

These patch scripts were DESIGN INPUT for phases that have since been implemented, measured and committed on the branch. They no longer apply (their anchors target older code) and are kept only as the record of what the executor started from.

| draft | authoritative implementation |
|---|---|
| p1c_patch.py, p1c_patch2.py, p1c_runs.sh, p1c_worklog_skeleton.md | P1.c — work-log `docs/wiki/work-log/2026-09-06-p1c-composition.md`, register 11.95 (composer re-designed: bounded diversity, acceptance floor, dominance guard; prefix 24 by measurement, not 28) |
| p1d_engine_draft.py, p1d_engine_rewrite.py, p1d_route_patch.py, p1d_tests_patch.py, p1d_worklog_skeleton.md | P1.d — work-log `docs/wiki/work-log/2026-09-06-p1d-latency-architecture.md`, register 11.96 (implemented as CONCURRENCY-DEADLINES-V1 + METAL-LEASE-V1 by two worktree agents from the drafts as design input; re-derived against the P1.c code) |
| p1e_patch.py, p1e_ui_patch.py, p1e_worklog_skeleton.md | P1.e — work-log `docs/wiki/work-log/2026-09-06-p1e-mode-recomposition.md`, register 11.97 (implemented by a worktree agent from the drafts as design input, re-derived against the current code, measured by the integrator) |
