---
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# Experiments

Measured experiments with the EXPERIMENT tag. Each entry:

- States the hypothesis.
- States the measurement method.
- Publishes the result, including null results.
- States the decision: ship, kill, or continue.

Front-matter:

```yaml
---
hypothesis: <one sentence>
status: proposed | running | concluded
conclusion: ship | kill | continue | null
last_touched: YYYY-MM-DD
---
```

A null result is a valid conclusion. "We tried, it didn't work, here
is why" is the most valuable kind of experiment entry.
