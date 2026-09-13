---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1: PRODUCTION SWITCH + OFFICIAL-MCP-CLIENT ACCEPTANCE (Trail-free half): the fleet runs main's tree; polymath.knowledge_brief and substack.article_development completed through one Polymath MCP connection with a supervised-worker restart mid-run"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-PRODUCTION-ACCEPTANCE
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.264
architecture_impact: "Operational: the fleet worktree moved from architecture/evidence-first-v5 (tagged archive/evidence-first-v5-2026-09-13) to a local `production` branch tracking origin/main (`main` itself is checked out in the owner's polymath-v4-main worktree); one clean bounce; 24 supervised slots incl. adapter_step. New script scripts/adapter_mcp_acceptance.py (registered) drives a real adapter run through the official mcp client. No runtime code change."
---

> Plan "FINAL PRODUCTION ACCEPTANCE": an official MCP client connected ONLY to Polymath runs one real adapter run start →
> finish; observable receipts for items 1–10; then the second adapter through the SAME surface with no adapter-name branch.

## Contract
Production must run main's tree (E1 contracts, E2 substrate + supervised `adapter_step` slot, E4 connector, E7 manifests) on ONE
execution-bundle hash; the acceptance client is the official `mcp` Python client (streamable-http, bearer), never a fixture, never
a direct import; the run must survive a controlled restart of the SUPERVISED worker; invented citations must be refused; the
result must be fetched under the same run_id with lineage.

## Changes
- **Production switch** (`production_switch` procedure, recorded here): tagged the old head `archive/evidence-first-v5-2026-09-13`
  (6b1edd5); `git checkout main` was REFUSED (`main` is checked out in `polymath-v4-main`) → the fleet worktree now runs branch
  **`production` = origin/main @ 64a4732**; the owner's parked `scripts/verify_final_state.py` modification was stashed and restored
  untouched; migration 0061 already applied; `bundle_integrity` READY; every supervisor/child stopped by exact match; ONE boot →
  **24 healthy / ONE hash `d9d4abe107fa` / `/ready` true / 0 quarantines**; `adapter_step` slot spawned (pid 18933) and registered
  `healthy`; `GET /adapter/list` served by the orchestrator; the MCP server lists all seven `adapter_*` tools.
  (The first bounce ran on the old branch because the script lacked `set -e` after the refused checkout — wasted, harmless, idle fleet.)
- **`scripts/adapter_mcp_acceptance.py`** (new, registered in `scripts/README.md`, declared in TREE): `--adapter` polymath.knowledge_brief |
  substack.article_development; official `mcp` client → adapter_list/start/next/submit/status/result; scripted agent answers that cite
  only the step's `context.evidence_refs`; one deliberately invented submission per run (must be refused); SIGKILL of the supervised
  `adapter_step` worker before the first submission (the supervisor must respawn it); exit 0 only when the result validates, is
  `completed`, and its output cites ids present in the lineage. **The client makes zero TrailSignal calls.**

## Proof — acceptance receipts (production, 2026-09-13)
| item | polymath.knowledge_brief | substack.article_development |
| --- | --- | --- |
| run_id | `adr_c7a2c85b42f5bdc26980934280faf35b` | `adr_5b6804278cba4afd8bd610e7aadb434a` |
| terminal | `completed` at 19:13:00Z, 3 steps accepted | `completed` at 19:15:57Z, 11 steps issued/accepted, branch_loops 1 |
| real Polymath knowledge | 45 evidence refs from `/retrieve` (cinema) | 116 evidence refs (plan + retrieve + graph + gap_retrieve) |
| typed AGENT_REASON | `brief` (seq 2) issued and accepted | `thesis`, `narrative`, `draft` issued and accepted |
| controlled restart (supervised) | worker pid 18933 SIGKILLed → supervisor respawned 19679; run resumed | 19679 → 19960; run resumed |
| invented citation refused | 422 `cited ids not in context.evidence_refs: chunk_invented` | 422 + schema errors (`theses` required; additional properties) |
| result under the same run_id | `adapter_result` → lineage 45 evidence ids, 2 receipt hashes, output cites 2 lineage ids, unknowns preserved, `external_operations: []`; result_hash `9ad5ec57945eca1a…` | lineage 116, 10 receipts, output cites 3 lineage ids, unknowns preserved, `external_operations: []`; result_hash `e192ab11f9b5bc49…` |
Durable: `adapter_runs` / `adapter_steps` (receipt hashes) / `adapter_results` rows for both run_ids on the production store.

**Plan acceptance items** — 1 ✓ one Polymath run owns the lifecycle; 2 ✓ real corpus retrieval/graph/provenance contributed;
3 ✓ typed AGENT_REASON steps issued and accepted; 7 ✓ a controlled restart (supervised worker) resumed without losing accepted work;
8 ✓ unknowns survive, invention is refused; 9 ✓ Polymath evidence lineage + step receipts (Trail refs absent by construction);
10 ✓ result fetched through adapter_result under the same run_id; **second adapter through the same surface ✓** with the
runtime-neutrality test pinning "no adapter-name conditional". **4 / 5 / 6 (Trail invoked through its public interface; real
Trail discovery/acquisition/extraction/evidence/scoring; deterministic non-LLM score) — NOT MET: TrailSignal's stack is down on
this host, no `polymath` principal exists, and Trail has no v2 evidence promotion or deterministic score yet (C1/C2 behind P9).**

## Rejected claims
- **"Switch by checking out `main`"** — REJECTED by git: `main` is held by the owner's `polymath-v4-main` worktree; the fleet worktree tracks
  origin/main on `production` instead (never touched the other worktree).
- **"The in-process harness runs count as the client acceptance"** — REJECTED: this log's receipts come from the official `mcp` client
  against the supervised production fleet; the harness runs (11.260/11.262) were the substrate proofs.
- **"Declare the E2E done"** — REJECTED: items 4–6 are unmet until the Trail path is live (owner O1/O4) and Trail reaches C2 (E3).

## Open contract gaps
- **Owner O1**: Trail `config/v2/principals.yaml` + `secrets.yaml` entries for `polymath` (YAML in the E0 matrix); worker env
  `TRAIL_SIGNAL_MCP_JWT_SECRET` (≥32 chars) or a minted `TRAIL_SIGNAL_MCP_TOKEN_POLYMATH`.
- **Owner O4**: Trail's stack (Temporal :7233, Postgres :15433, VersityGW :7070, MinIO/HAProxy :19000 from ADR-060 pins, daemon :8767)
  + SearXNG :8080 — then `trail.product_discovery` runs live through the same client to its first `planned` gap (G_gates, Trail C1).
- **Trail E3** (P6R/P7R/P4W/P8R/P9 → C1 → C2/Q1 → C3) for acceptance items 5–6; **E6** `research_*` equivalence baseline + migration.
