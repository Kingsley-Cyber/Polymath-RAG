---
triggered_by: RAG E2E gate Q1
status: done
last_reviewed: 2026-08-14
last_touched: 2026-08-14
---

# Refactor 0006: Q1 heterogeneous extraction qualification

Q1 qualified the production extraction path and fixed one discovered
operational defect:

- Frozen heterogeneous qualification corpus `eval/gold/
  qualification_q1.yaml` (53 items, 11 classes, sha
  `2ce1d237…`) + frozen harness artifacts + `eval/q1/REPORT_Q1.md`
  with verdict **PASS**.
- Regression lock `tests/contracts/test_q1_qualification_regression.py`
  (corpus hash, scorer hash, baseline metrics).
- **Defect fix**: census stage reorder — `canonicalize` →
  `project_canonical` → `verify_projections` (was
  verify → canonicalize → project_canonical). The verifier now
  reconciles the canonical graph only when it is due; incremental
  ingestion no longer degrades falsely. Verified with a clean
  9-document heterogeneous pipeline run: 0 degradations, 0 failed
  attempts.

Affected dependents verified: extraction code (compiler/rule pack/
ontology/thresholds) untouched; full unit + integration suites green;
the C2 census re-arm behavior preserved (integration-tested).

Proof: see work log `2026-08-14-q1-qualification.md`.
