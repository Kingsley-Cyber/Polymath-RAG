---
change_id: GOVERNED-CONVERGENCE-V1-TG0-TG2
owner: "@king"
date: 2026-09-20
status: in-progress
architecture_impact: "Polymath side only. TG1 adds seven adapter_* proxies to MCP Server B (stdio). TG2a makes adapter_next carry READABLE evidence (a sibling key, no wire-schema change). TG2b adds an OPT-IN evidence-boundary knowledge surface for adapter steps (pure shared module + worker dispatch + manifest 2.2.0 + additive step-ref properties + EvidencePacket JSON Schema + four contract-map rows). Default surface in code stays legacy; kill switch POLYMATH_ADAPTER_KNOWLEDGE_SURFACE=retrieve. Trail untouched."
last_reviewed: 2026-09-20
---

## Contract
Owner goal 2026-09-20 (session 1 of GOVERNED-CONVERGENCE-V1): TG0 + TG1 + TG2, Polymath side only. Done = fleet +
Trail stack up, R0 and R1 fixture runs green, TG1 + TG2 merged, live-proven, ledgered, tagged locally; then STOP
(TG3+ is a separate goal). Plan of record: `docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md`.

- Single owner per change: `governance` (MCP Server B text surface, contracts, manifest, docs) · `worker`
  (`adapter_step` executor dispatch) · `shared` deterministic policy (`adapter/evidence_boundary.py`,
  `adapter/service.py`). The orchestrator's `/adapter/*` routes and `/chat/evidence` are UNCHANGED.
- Inputs/outputs: `adapter_next` gains a sibling `evidence{rows,receipts}`; adapter step refs gain four OPTIONAL
  properties; `AdapterResultV1.output` gains `evidence_admissions` for `trail.product_discovery` 2.2.0.
- Failure modes are typed: `EVIDENCE_CONTRACT_MISMATCH` (terminal, never a fallback), `EVIDENCE_SURFACE_UNAVAILABLE`
  (terminal when `on_unavailable: gap`), degraded legacy fallback recorded on the step output, empty evidence = success.
- Verifier: worktree unit suites (shared/contracts/config), then live R1 + `scripts/adapter_evidence_boundary_proof.py`.
- Rollback boundary: env kill switch (no deploy), or `git revert` of the merge + one bounce.

## Changes
(filled at close)

## Proof
(filled at close)

## Rejected claims
(filled at close)

## Open contract gaps
(filled at close — one disposition per impacted contract)
