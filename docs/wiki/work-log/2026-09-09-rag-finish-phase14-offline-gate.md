---
title: "WORK LOG — RAG-finish Phase 14: offline acceptance gate GREEN + canary harness"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (gate assessment) + evaluation (canary harness)
last_reviewed: 2026-09-09
status: complete (offline gate green; the live canary loop is Phase 15)
register: 11.195 (pending)
package: scripts/rag_pipeline_canary.py
architecture_impact: "Adds the Phase 15 canary harness (generate 3-5 KB .txt -> /upload -> poll document_status to VNEXT_COMPLETE under a 4-min cap -> diagnostic packet OUTSIDE the repo -> /retrieve probe with citation check). No runtime behavior change; the harness only RUNS live under the Phase 15 preconditions. Records the Phase 14 offline acceptance gate as GREEN."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 14** (offline gate) + **PHASE 12/15** (diagnostics/canary) + register **11.195** (pending).

## Contract

All offline acceptance items green before the first timed provider canary; provide the iterative canary
harness that drives the real `/upload` pipeline and requires 3 consecutive passes.

## Phase 14 offline acceptance gate — GREEN

`pytest` over the full RAG-finish surface + adjacency + control-plane: **178 passed, 1 skipped** (`-o addopts=""`).
Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok · `bundle_integrity` READY. Checklist:

- [x] Graphify runtime graph captured (Phase 1, `03_PHASE1_RUNTIME_TOPOLOGY.md`).
- [x] four functional pools represented explicitly (LANE-REGISTRY-V1).
- [x] one-key-one-account isolation implemented/tested (`test_lane_registry`, `test_groq_account_isolation`).
- [x] provider-wide family coupling removed except the proven Groq exception (11.185 + registry audit).
- [x] configured lanes have active/reachable diagnostics (`lane_inventory.py`, `unreachable_pins`).
- [x] retryable work is functional-pool-owned — extraction/profile FULL; pMAP stage worker in-run failover.
- [x] rate-limit seed/override/evidence precedence + no runtime catalog dependency (EFFECTIVE-CAPACITY-V1).
- [x] per account/model provider capacity + per function/account/model workload qualification visible.
- [x] pMAP batch capability lane-specific (Phase 7, `pmap_pool_batch_cap`, `map_batch_cap`).
- [x] `DocumentGroundingContextV1` deterministic fixtures green + budget enforced (Phase 5).
- [x] pMAP prompt includes deterministic grounding; contract/version invalidates old skeleton-only generation
      (MAP_PROMPT_VERSION=map-prompt-v2 + grounding_hash in batch identity).
- [x] MAP compiler tolerant-format/strict-identity + partial persistence/repair (unchanged, tested).
- [x] offline 15/40/60 lane-capability batch-planner tests green.
- [x] profile compiler adversarial + profile/extraction pool failover tests green (existing suites).
- [x] canonical document status builder exists; exact blocker list from durable state (Phase 12).
- [x] run-scoped canary diagnostics writer works (`rag_pipeline_canary.py`).
- [x] repo guards/preflight green.
- [n/a] frontend build — the frontend is not touched (Phase 18 optional).

## Changes

- `scripts/rag_pipeline_canary.py`: the iterative timed canary. Generates a unique ~4 KB synthetic .txt
  (title, author, contents, 4 headings, an exact identifier `ZQX-NNNN`, a numerical fact, an explicit
  negation, a cross-section relationship) → `/upload` → polls `document_status` to `VNEXT_COMPLETE` with a
  hard 240 s cap, recording the timeline → writes a diagnostic packet under `/tmp` (AGENTS §7) → `/retrieve`
  probe verifying the canary's chunk + fact are cited. Requires `--passes` consecutive successes.

## Proof

- Offline gate: **178 passed, 1 skipped**; guards green; `bundle_integrity` READY.
- Harness compiles; `httpx` present; `/retrieve` request shape matches `RetrieveRequest`.

## Rejected claims

- **NOT run live yet** — the harness spends provider quota and needs the Phase 15 preconditions (fleet
  restart to load the pMAP slot + `POLYMATH_DOC_PARENT_MAP_ENABLED=1` scoped to the canary corpus). Nothing
  live changed by committing it.
- **Diagnostics live OUTSIDE the repo** (`/tmp`, AGENTS §7) so a canary run never adds undeclared repo files.

## Open contract gaps

- Phase 15: restart the fleet, enable the flag scoped to `rag-canary`, run the harness to 3 consecutive
  passes, then commit a final evidence report. Phase 17 corpus reconciliation stays behind the forensic hold.
