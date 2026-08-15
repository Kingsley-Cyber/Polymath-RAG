---
change_id: r1f-graph-mode
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (GRAPH mode addition; FAST/HYBRID unchanged; synthesis unchanged)
---

# R1F: production GRAPH mode — PASS

## Contract

Expose GRAPH = promoted HYBRID (hybrid-retrieval-v1) + the
already-qualified evidence-authorized, corpus-authorized canonical
bidirectional hop1 graph augmentation (D2 machinery: seeds from
entities attached to in-scope evidence, authorized-fact filtering,
HIGH_MEDIUM allowlist, 8-seed / 20-fact bounds, SPO preserved).
Preserve FAST and HYBRID exactly. Route document summaries and
section summaries as bounded synthesis CONTEXT, child chunks as
exact textual evidence, and graph facts as the GRAPH evidence lane —
never conflated. Do not modify synthesis; qualify the retrieval
structure.

## Changes

- `shared/polymath_shared/retrieval_modes.py`: MODE_GRAPH exposed;
  GRAPH_PLAN_VERSION = graph-retrieval-v1; bounds 8 seeds / 20 facts.
- `orchestrator/orchestrator/api/graph.py`: production GRAPH service —
  one promoted HYBRID Pass-1 (shared engine) + `_neo4j_expand` (the
  existing qualified hop1, no second graph implementation); seeds
  from query + selected-evidence surfaces with preferred retrieved
  chunks; hierarchical synthesis-context response (document →
  document summary → sections → section summaries → exact child
  evidence + unassigned rescue bucket; GRAPH_RELATIONSHIPS lane);
  FAST readiness/failure semantics inherited.
- `/retrieve`, `/evidence`, `/chat` accept mode=GRAPH through one
  path; /evidence and /chat feed the existing EvidenceBundle v2
  (graph lane = qualified facts, text lane = HYBRID evidence) — no
  synthesis change.
- Qualification: frozen R1D set through graph_retrieve (HYBRID
  parity, graph authorization/SPO/bounds, determinism, isolation,
  latency) + endpoint integration test (hierarchical shape, parity,
  isolation, failure semantics).

## Proof

- HYBRID parity over 48 queries: 0 mismatches (docs / sections /
  evidence identities) — GRAPH's Pass-1 reproduces HYBRID exactly.
- Graph lane: 6 facts surfaced across the frozen set; all corpus-
  authorized (0 foreign), SPO orientation byte-identical to the
  authoritative fact rows, bounds respected (≤8 seeds, ≤20 facts).
- Determinism: repeated GRAPH requests identical (structure + facts).
- Isolation: 0 leaks. Latency: Pass-1 p50 637.6ms / p95 748.0ms
  (HYBRID baseline), graph increment p50 7.3ms / p95 12.8ms, total
  p50 644.8ms / p95 763.8ms — graph augmentation is ~10ms.
- Suites: unit 0 failures; integration 0 failures (3 endpoint tests
  incl. GRAPH); guards green.

## Rejected claims

- No synthesis redesign (EvidenceBundle v2 semantics untouched;
  summaries stay routing/context; children stay exact evidence).
- No second graph implementation (D2 machinery reused).
- FAST/HYBRID byte-identical (parity measured).

## Open contract gaps

- Synthesis-quality qualification with the hierarchical context
  structure (the intended Polymath synthesis architecture) is the
  next authorized step — not started. R1E remains a frozen negative
  result (no corpus reach).
