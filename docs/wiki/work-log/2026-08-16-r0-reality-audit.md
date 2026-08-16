---
change_id: r0-reality-audit
owner: governance
date: 2026-08-16
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: complete
architecture_impact: none (inspection only; no code/config/test/artifact changes)
---

# Work Log: 2026-08-16 — R0 repository reality audit

## Contract

Inspection-only audit authorized before any repair plan: establish an
exact, code-grounded model of what Polymath actually does today,
reconcile it against documentation, and reclassify the frozen I3
findings. No code, config, test, or evaluation artifacts modified.
Deliverable: `eval/r0/REPORT.md`.

## Changes

- `eval/r0/REPORT.md` (new): the full audit (pipeline trace, GLiNER,
  admission durability, compiler, coordination, durability, stores,
  query_ready, provenance, retrieval, control plane, doc-vs-code
  table, I3 reclassification, repair surfaces).

## Proof

All claims traced to executable code at HEAD `9000973`:
- stage chain control/control/census.py:18; intake submission
  shared/polymath_shared/intake_submission.py; chunker
  workers/workers/chunker.py; extract workers/workers/extract_worker.py;
  candidate pairing workers/workers/candidates.py:108-127; compiler
  shared/polymath_shared/rulepack/compiler.py; trigger localization
  workers/workers/evidence_proposer.py:localize_trigger; binding
  shared/polymath_shared/endpoint_binding.py (_COORDINATION_SPLIT_RE
  line 34); projection workers/workers/project_qdrant_worker.py +
  project_neo4j_worker.py; verifier workers/workers/verify_worker.py;
  census control/control/census.py (terminal-run exclusion line 62);
  GLiNER sidecars/gliner_runtime/manifest.toml; retrieval
  shared/polymath_shared/pass1.py, hybrid.py,
  orchestrator/orchestrator/api/{fast,hybrid,graph}.py.
- I3 findings reclassified: D1 MIXED (admission-doc vs durability
  design), D2 REAL DEFECT (verify/projector race), reconstruction
  no-redrive REAL DEFECT, D3 design boundary, D4 documentation defect,
  noun-trigger/start-founded/coordination-explosion REAL DEFECTS with
  exact mechanisms and owning modules.
- Key disconnects: entity durability (fact-endpoint-only persistence),
  query_ready point-in-time semantics with no re-verification path,
  comma-only coordination splitting.

## Rejected claims

- No GLiNER discovery failure observed in I3 — raw proposals exist;
  the loss is downstream durability (proposal-loss point documented).
- No fixes proposed; repair surfaces labeled POSSIBLE only.

## Open contract gaps

- Whether the fact-endpoint-only entity durability is the intended
  design or a documentation drift requires a user decision before any
  repair gate (I3R) is authorized.
