---
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# Refactors

A refactor is any change triggered by an ADR or by a dependency
upgrade. Each refactor lives in its own file:

```
NNNN-<slug>.md
```

Front-matter:

```yaml
---
triggered_by: ADR-NNNN | dependency:<name>:<old>-><new>
status: planned | in_progress | done | blocked
last_touched: YYYY-MM-DD
---
```

The wiki worm lists every entry that is not `done`. A review due date belongs
in the entry when the owning change has an external deadline.
