---
change_id: WLK2C-RETRIEVAL-LINEAGE-V1
owner: wildcard-investigation
date: 2026-09-18
status: admitted
architecture_impact: "DOCS-ONLY admission (no production/fleet/shared change, no bounce). Admits the WLK2C mission (owner /goal): query-anchored evidence lineage + a tiered bridge-source policy (reuse subquery → GRAPH path → bounded concept-bridge compiler → none) + DIRECT/COMPLEMENTARY/DIVERGENT role admission (q0 primary, NOT max). Grounded in WLK2A (bridge-primary validated). Implementation executes C0–C7 on worktree `wlk2c/retrieval-lineage`, one merge+port-gated-bounce+CA5 qual at the end. Extends CA3/CA4 additively; does not reopen CA0–CA5; global rerank floor unchanged; WLK2B not reopened; no hard-coded concepts."
last_reviewed: 2026-09-18
---

## Contract
Owner admitted WLK2C via `/goal` (2026-09-18). Mission: make Polymath remember WHY a candidate was
retrieved (lineage) so it answers q0 AND surfaces bounded complementary/latent knowledge with an
explainable grounded bridge back to q0. This slice ADMITS the mission (plan-of-record on disk); no code.
Authority = the `/goal` spec; plan-of-record = `docs/wiki/plans/WLK2C-RETRIEVAL-LINEAGE-V1.md`.

## Changes
Docs only (fence-safe, no bounce):
- `docs/wiki/plans/WLK2C-RETRIEVAL-LINEAGE-V1.md` — plan-of-record: governing invariants, tiered
  bridge-source policy, bounded bridge-compiler contract, role admission (DIRECT/COMPLEMENTARY/
  DIVERGENT), phase slices C0–C7 with integration points + proof, live qualification/acceptance,
  rejection conditions, scope exclusions, execution/runtime-resolution hazards.
- Register row 11.315; this work-log; scaffold TREE declaration; CONTINUITY refreshed (WLK2C admitted,
  in-flight on worktree `wlk2c/retrieval-lineage`).
- Worktree `pmv4-wlk2c` (branch `wlk2c/retrieval-lineage`) created from production HEAD for the code slices.

## Proof
`IMPLEMENTED` (admission only — no executable change). The plan-of-record encodes the owner's spec + the
integration map already established by the WLK2A investigation (CompiledQuery lineage fields exist;
`retrieval_text_for` = q0-only is the discard point; `select_evidence`/`compose_evidence` are the
selection owners). Guards green (repo_guard/wiki_worm/preflight = 0). No fleet change, no bounce.

## Rejected claims
- No implementation claims yet. The WLK2A "chunk-quality-limited" read was already withdrawn (corrected
  by the bridge-primary test); WLK2C proceeds on the validated bridge mechanism.

## Open contract gaps
None from this slice (docs only; `contract_impact` = no impacted production contract). The mission's
contract changes land in C0–C7 (each with its own work-log/register/scaffold + one disposition per
impacted contract). Deferred to C7: one merge + port-gated bounce + CA5 64×4 qualification. Out of scope
(not this mission): wc02 routing, wc03/wc10 nomination, Scout coverage, ingestion, pMAP, CA0–CA5
contracts, the global rerank floor, WLK1, WLK3.
