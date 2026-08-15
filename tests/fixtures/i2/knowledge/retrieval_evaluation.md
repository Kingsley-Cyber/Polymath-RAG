# Retrieval Evaluation

Retrieval evaluation measures whether the right evidence surfaces for a query. Precision and recall are computed against annotated relevance judgments.

A benchmark stops being held out after its results influence implementation. Frozen fixtures, answer keys, and scorers are hashed, and their exposure history is recorded.

Evaluation must distinguish development-set regressions from independent qualification. Reusing the same set for tuning and final judgment inflates the result.

Per-lane ablations reveal where quality comes from. Document routing, dense search, lexical search, and graph expansion are measured separately before fusion is judged.
