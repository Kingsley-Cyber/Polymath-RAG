---
change_id: r1b-summary-led-pass1
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (Pass-1 engine only; no FAST/HYBRID/GRAPH exposure, no synthesis change)
---

# R1B: summary-led Pass-1 retrieval — PASS

## Contract

Build and qualify Pass 1 of the intended architecture:
query → three independent neural searches (document summary / section
summary / global child) → RRF → explicit document aggregation →
bounded document resolution → section resolution → FILTERED child
deepening → global-child rescue union → dedupe → G3 (order-only) →
bounded hierarchical Pass-1 evidence. SUMMARIES ROUTE / CHILDREN
PROVE / GLOBAL CHILD SEARCH PROTECTS RECALL. Close the R1A routing
receipt/reconciliation gap. No HYBRID/MMR/Pass-2/GRAPH/support
classifier/synthesis changes.

## Changes

- `shared/polymath_shared/pass1.py`: versioned `Pass1RetrievalPlan`
  (pass1-retrieval-v1) + deterministic engine: three corpus-filtered
  neural searches with per-lane provenance; RRF (k=60) with preserved
  per-lane contributions; `DocumentCandidate` aggregation (multi-
  representation support visible); bounded document/section
  resolution; filtered child deepening (corpus+doc+parent filters);
  global-child rescue (recall safety; summary miss never implies
  document unreachability); dedupe by chunk identity; G3 candidate-set
  invariant; bounded hierarchical final evidence. Routing summaries
  never enter the exact-evidence set.
- verify_worker: `reconcile_routing_qdrant` — neural routing points
  cannot silently disappear (receipt cleared on store loss → census
  re-drive; orphan points detected; missing receipts reported).
- census: `_missing_projection_receipts('project_qdrant')` covers
  routing kinds (document_summary / section_summary / child).
- Qualification: frozen 34-query set (eval/r1b/queries.json, sha256
  `0eadb8c5…95b6`) over the frozen I2 corpus; gold doc + gold child
  (content-substring resolved). Ablations A-F + rescue accounting +
  filter verification + cross-corpus isolation + determinism +
  latency. Pure determinism tests (5) + self-contained integration
  reconciliation test.

## Proof

F (full pipeline): DOC R@1 0.882 / R@3 0.912 / MRR 0.910;
SEC R@1 0.882 / R@3 0.912 / MRR 0.897; CHILD R@1 0.853 / R@5 0.971 /
MRR 0.900; final-evidence supporting-child recall 0.941.

Ablations: document-only DOC R@1 0.824 (no children — expected);
section-only final recall 0.941; global-child-only final recall 0.971;
hierarchy without rescue 0.912 → with rescue 0.941 (rescue recovered
gold children; 8 rescue arrivals); G3 changes order only (recall
identical, candidate-set invariant held).

Arrivals (F): 170 MULTI_REPRESENTATION + 8 GLOBAL_CHILD_RESCUE
(documented: in this single-parent corpus every deepened child is also
a global-lane hit, so the multi-representation label dominates).
Filter verification: deepened children ⊆ selected doc+section ✓.
Cross-corpus isolation: 0 leaks ✓. Determinism: two full runs
semantically identical ✓. Latency: lanes ~8-15ms p50; total Pass-1
p50 675ms (G3 dominates). Reconciliation: census detects a lost
routing receipt; re-projection restores it; verify routing report
converges empty ✓. Suites: unit 0 failures, integration 0 failures,
guards green.

## Rejected claims

- No answer-support claim: R1B establishes broad retrieval →
  structured routing → bounded exact candidates only; D4/D4.1 remain
  valid negative experiments. No arbitrary abstention threshold.
- No FAST exposure, no HYBRID, no MMR, no Pass-2, no GRAPH changes.

## Open contract gaps

- R1C (FAST production route) will expose this engine behind the
  retrieval API — not started. The clean-download snapshot digest
  ledger item remains open (recorded; immutable revision pin governs).
