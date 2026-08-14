---
triggered_by: ADR-0006
status: done
last_reviewed: 2026-08-13
last_touched: 2026-08-13
---

# Refactor 0001: production Phase B implementation

ADR-0006 introduced the packaging and deployment boundary. This refactor
materialized the production code that boundary supervises:

- workflow schema and transactional receipts (shared + stores);
- the deterministic rule pack and compiler (shared);
- the no-LLM ingestion layer (workers);
- transactional intake (orchestrator);
- independent census/lease control (control);
- pinned GLiNER runtime (sidecars);
- launchd units and Makefile (deployment).

Affected dependents verified: `contracts/` unchanged (no wire-schema
change); `architecture/dependencies.json` unchanged (no new owner or
edge — workers still depend only on contracts + shared; the sidecar
still depends only on contracts + shared).

Proof: 26 tests passing, all three guards green. See work log
`2026-08-13-phase-b.md`.
