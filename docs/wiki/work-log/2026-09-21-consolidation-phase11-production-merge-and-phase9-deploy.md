---
change_id: CONSOLIDATION-MIGRATION-PHASE11-PRODUCTION-MERGE-AND-PHASE9-DEPLOY
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "DEPLOY — `item2/corpus-scoped-atoms` (the migration branch through `81a4472` + Item 2D `221b95c`) merged into `production` (`8ae4cf3`) and bounced: `DOMAIN_OPERATION`, `adapters/ecommerce/`, `governance/trail/`, manifest `ecommerce.product_research`, corpus-scoped atom search and the remote host-path refusal are LIVE. The Hermes skill copy was redeployed from this repository."
last_reviewed: 2026-09-21
---

# Consolidation migration — Phase 11 (production merge + acceptance) and Phase 9 (the real Hermes deploy)

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 11 (merge gate) and Phase 9 (deterministic host deployment). The owner authorized the merge in chat on 2026-09-21 ("Production merge is authorized … target `item2/corpus-scoped-atoms` …
verify ancestry and current HEADs … follow the established drain, merge, guards, boot, health verification and rollback procedure"). Procedure: `docs/migration/CONTINUATION.md` "Next Exact Action".

## Changes
- Verified before the merge: `production` `7155250`, `item2/corpus-scoped-atoms` `a176880`; the migration branch `81a4472`, Item 2D `221b95c` and the host-path fix are ancestors of `item2`; `production`'s two newer commits are docs only;
  `git merge-tree` = no conflicts; both checkouts clean; 0 open adapter runs; 13 worker types healthy on one bundle. Local rollback tag `pre-consolidation-merge` → `7155250` (UNPUSHED).
- Drain (`kill -TERM` the supervisor → 0 supervisors, nothing on `:7200`, 0 fleet processes) → `git merge --no-ff item2/corpus-scoped-atoms` = `8ae4cf3` → four guards → ONE `scripts/boot_polymath.sh`.
- Phase 9: `scripts/deploy_ecommerce_skill.py --target ~/.hermes/standalone/opportunity-research`: dry run (8 to write: `binding.py` new + the 7 adapted files; 182 / 190 unchanged; the 7 deployed files were byte-identical to AutoResearch
  `a7baa66`, i.e. no hand edits to lose; backed up outside the repo first) → `--execute` → `--check`.
- No Postgres migration. `POLYMATH_TRAIL_MODE` left unset (daemon default). Nothing pushed.

## Proof
- DEPLOYED: `/ready` true with embedder + reranker; 13 worker types healthy, ONE bundle `53482cc21156`; `/adapter/list` shows `ecommerce.product_research` 0.1.0 (54 steps, 9 agent-reason steps, 12 working external operations) beside the three pre-existing adapters.
- LIVE_PATH_PROVEN through the PUBLIC hostname, vantage = the host (`scripts/hosted_mcp_acceptance.py --url https://mcp.kingsleylab.xyz --vantage host --expect-adapter ecommerce.product_research --cycle …`): exit 0 — 15 PASS · 1 WARN (the edge
  403s `Python-urllib`) · 1 SKIP (`--explore`). `isolation.host_path_upload` PASS = the fix is live. `adapter.cycle` PASS: `ecommerce.product_research` started on `cinema`, reached its first awaiting step, cancelled (`adr_c9f7c005ae64572820710b48db4c6618`;
  mechanical smoke, no spend, not a product result).
- Main checkout (execution path = live code), database-free: the migration suite + Server A pins + adapter contract = all green; Item 2D `test_search_atoms_callers_scoped.py` + `test_profile_atom_corpus_scope.py` green. Guards 0/0/0/READY.
- Hermes: `hermes mcp test polymath` lists the adapter and evidence tools. Deploy `--check` exit 0, receipt `parity: true`, 190 files compared, `hermes_skill … is: deployed`; the engine's own suite run INSIDE the deployed copy under the Hermes
  venv with a throwaway `OPPORTUNITY_RESEARCH_DB`: ALL 606 CHECKS PASSED (609 in the repository: the difference is the checks that need the containing repository).

## Rejected claims
- "The hosted product is accepted." No — host vantage only; no external machine, no per-friend principals yet (owner decision 2026-09-21: required before onboarding), no real ecommerce workflow.
- "Hermes was reloaded." No gateway restart was done: the only tool-surface delta is `upload_document`'s description; `adapter_list` is dynamic. The reload stays owed and harmless.
- "Item 2D is live-proven." Its unit / static proofs are green in the live checkout; its live isolation proof needs a second corpus (Phase 10).

## Open contract gaps
- `ADAPTER_RUNTIME`, `ADAPTER_CONTRACT_V1`, `MCP_SURFACE`, `EVIDENCE_BOUNDARY_API`: dispositions were given per slice in the branch work-logs (11.363 – 11.377); the merge adds no new change. **TESTED_UNCHANGED** in the live checkout.
- `unexpected_in_deployed: registry/friction_library.upstream.patch` in the Hermes copy is the excluded upstream patch (M-006); the deploy never deletes. **NOT_AFFECTED**.
