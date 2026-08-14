---
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# Wiki

This is a working wiki. The read-only worm (`scripts/wiki_worm.py`) audits it
weekly, reports open refactors and work records, and fails on broken metadata.

## Layout

- `decisions/`: Architecture Decision Records. One per decision. Numbered.
- `refactors/`: work triggered by ADRs or dependency changes.
- `experiments/`: measured model and system experiments from
  the architecture doc.
- `work-log/`: append-only records for repository mutations.

## Front-matter

Every wiki file has YAML front-matter:

```yaml
---
owner: <process role or @king>
last_reviewed: YYYY-MM-DD
last_touched: YYYY-MM-DD
status: draft | accepted | superseded
supersedes: NNNN-<slug>.md
superseded_by: NNNN-<slug>.md
---
```

The worm uses these fields. The status field is required.
