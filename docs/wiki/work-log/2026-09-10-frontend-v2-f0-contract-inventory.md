---
title: "WORK LOG — Frontend V2 F0: backend contract inventory measured against the live orchestrator"
change_id: FRONTEND-V2-CONTRACT-INVENTORY-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (F0; inventory only — no endpoint added or changed)
register: 11.195
package: "docs/wiki/plans/FRONTEND-V2-CONTRACT-INVENTORY-V1.md"
architecture_impact: "none. Establishes which backend authority serves each V2 capability and names five gaps (GAP-1..5) that F4/F6/F7/F10 must close before those screens can be honest."
---

> **Ledger:** owner directive 2026-09-10 — "the application itself is now the priority", phases F0–F12.
> Register **11.195**. Read-only against the live backend; no provider spend (the one `/chat/stream`
> exercise used `synthesizer=deterministic-template-v3`, no LLM).

## Contract

Requested outcome: F0 — inventory the backend contracts Frontend V2 will consume.

- **Smallest acceptance:** every capability the owner listed maps to a named endpoint + field, verified on a
  real 200 response; anything unserved is recorded as a GAP rather than assumed buildable.
- **Owner / public contract:** none changed. Inventory only.
- **Inputs/outputs/persistence:** reads `/openapi.json` + 14 live endpoints; writes one plan document.
- **Dependency edges:** F1–F12 consume this document. No code edge.
- **Verifier / rollback:** the measurements below are re-runnable against a live orchestrator; rollback = delete
  the document (nothing depends on it yet).

## Changes

- `docs/wiki/plans/FRONTEND-V2-CONTRACT-INVENTORY-V1.md` — the inventory: readiness triad authority map,
  capability→contract table, GAP-1…GAP-5, F1+ non-negotiables.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register **11.195**; `scripts/scaffold_polymath_v4.py` TREE.

## Proof

- `/openapi.json` = **39 routes** on the live app (bundle `f0db5412e473820e`).
- **Readiness triad served, and the legacy boolean disproven in the same breath:** `cinema` returns
  `query_ready: true` from `/corpora` while `/semantic_readiness?corpus_id=cinema` returns
  `SEMANTIC_INCOMPLETE` / `VNEXT_INCOMPLETE` with `parents{eligible 11993, mapped 1449, unresolved 10176}` and
  `/documents/summary` shows **14 of 67** documents `vnext_ready` (53 blocked). `rag-canary` returns
  `SEMANTIC_COMPLETE` / `VNEXT_COMPLETE`, 10/10 ready, 50/50 parents mapped, 0 unresolved.
- **Retrieval introspection is real, not aspirational:** a live `/chat/stream` answer frame carries
  `retrieval{engine "chat-retrieval-v2", mode, arrivals (per-chunk lane provenance), lane_sizes
  (document_summary/section_summary/entity_card/hierarchical_children/global_dense_child/global_sparse_child/
  latent_rescue/dualread/resolution_lift/seealso_fanout/graph_dest/union), funnel, composition, aspects,
  weak_aspects, legend, chunks, used_evidence, final_detail, graph_fact_count, graph_seeds, graph_bounds,
  graph_degraded, wildcard_diagnostics, latent, degraded, latency_ms}` — capabilities 3,4,5,6 are SERVED.
- **Pickers exist:** `/synthesizers` 14 offered, `/reasoning_modes` 10 (default `none`), `/capabilities`
  contracts block.
- **GAP-4 measured, not theorised:** `/control_plane?corpus_id=cinema` reports `processing: 64` while those 64
  runs last updated **2026-09-07** — `_POOL_STAGES`/run counting uses `status IN ('intake','reconciling',
  'degraded')` with no age qualifier (`control_plane_status.py:123`). V2 would paint 64 dormant runs as live.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

## Rejected claims

- **"`query_ready` is good enough for a readiness badge."** REJECTED with data — `cinema.query_ready=true`
  alongside 53/67 blocked documents and 10,176 unresolved parents.
- **"F6 retrieval comparison can be built client-side from N `/chat/stream` calls."** REJECTED as *honest* —
  it is buildable, but N calls do not share a compiled plan or a retrieval seed, so the diff confounds mode with
  run-to-run variance, and each arm costs a synthesis. Recorded as GAP-2, not silently shipped.
- **"F7 answer review just means re-answering with another model."** REJECTED — `synthesizer` re-answers;
  reviewing answer A against the evidence A cited has no contract. GAP-3.
- **"The UI can compose CONTROL READY itself."** REJECTED as a durable answer — composition in the client is
  recomputation, which 11.187's design law forbids precisely so two screens cannot disagree. GAP-1.

## Open contract gaps

- **F1 is BLOCKED on the approved greenfield design.** No such document exists in `docs/wiki/plans/`,
  `docs/wiki/reports/`, or `~/Downloads` (searched 2026-09-10). The owner's F0–F12 list and capability list are
  sufficient for F0 (fact-finding) but do not settle F1's information architecture, navigation or design system.
- GAP-1…GAP-5 are backend work, unstarted. F6/F7 cannot be honestly built until GAP-2/GAP-3 are closed.
- Nothing here is tested by an automated assertion; it is a measurement snapshot. A drift guard (re-probe the
  triad + capability fields, fail on shape change) is not built.
