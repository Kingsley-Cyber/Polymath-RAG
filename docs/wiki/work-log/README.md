---
owner: governance
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# Repository work log

This folder is the append-only record of repository mutations. Runtime events
belong in structured logs; design decisions belong in ADRs; measured model
results belong in experiments.

Name each entry `<date>-<change-id>.md`. Declare the path in the scaffold
`TREE` before creating it. Corrections are new entries that link to the old
record.

Required front matter:

```yaml
change_id: <stable id>
owner: <process role or governance>
date: YYYY-MM-DD
status: in_progress | complete | blocked
architecture_impact: none | <ADR path>
```

Required sections, in order:

1. `Contract`
2. `Changes`
3. `Proof`
4. `Rejected claims`
5. `Open contract gaps`

`scripts/repo_guard.py` validates the fields, section order, declared path,
and companion files required by an architecture or script change.
