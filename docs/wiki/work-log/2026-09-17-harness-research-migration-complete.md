---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 COMPLETE: final merged-main multi-hypothesis product-discovery proof passes"
change_id: HARNESS-RESEARCH-MIGRATION-V1-COMPLETE
date: 2026-09-17
owner: king
last_reviewed: 2026-09-17
status: complete
register: 11.276
architecture_impact: "Records migration completion. No code change in this slice: docs/continuity/register + scaffold declaration + scripts/README companion only. The migration itself: Polymath is the composition root and drives TrailSignal's seven bounded synchronous research operations through TrailSignal's public MCP; TrailSignal alone owns evidence admission, qualification, and the LAW-1 deterministic score; the host harness executes live-world actions. HR4 made opportunity.qualify/opportunity.score a per-hypothesis portfolio; HR5 fixed the durable admitted read model JSONB decode found by the live proof. Polymath's adapter consumes the per-hypothesis wire (register 11.275). No retired research path remains (O6, register 11.274)."
---

## Contract
Owner hard completion order 2026-09-16: finish A43 -> HR5 -> merge both -> final merged-main live proof -> mark COMPLETE -> stop. The final proof is the completion gate; governance polish alone is not a reason to continue.

## Changes
Docs/continuity only (no runtime): this work-log; CONTINUITY-REPORT COMPLETE checkpoint (in place); PLAN-AUTHORITY-REGISTER row 11.276; scaffold_polymath_v4.py TREE declares this work-log; scripts/README companion note.

## Proof
Final merged-main live acceptance, 2026-09-17: `set -a; . ./.env; set +a; .venv/bin/python scripts/adapter_mcp_acceptance.py --adapter trail.product_discovery --corpus cinema --harness receipts --harness-receipts tests/fixtures/harness_receipts` against the Trail daemon serving authoritative merged Trail main (`de64d84`, HR5 fix present) driven by the fleet (`production` 7f232e0). EXIT 0; status `completed`, 42/42 steps, 2 branch loops. All seven bounded Trail ops executed (registry.project, gaps.compile, evidence.admit, hypotheses.judge, territory.project, opportunity.qualify, opportunity.score). TWO live hypotheses: the non-first one carrying the field evidence was scored (`score:bf42e37bc7b7020212c604ee88d22004`, LAW-1 deterministic), the evidence-free one received a typed OpportunityScoreRefusalV1 (`HARD_GATE_UNMET`), no cross-hypothesis contamination. A supervised adapter_step worker restart mid-run (killed 1828 -> respawned 86504) reloaded admitted evidence from the durable store and the run resumed and completed — the HR5 `load_admitted` `result_json::text` + tolerant `_ensure_admitted` fix; zero `invalid tool input` in the daemon log. No retired Polymath research path invoked; no planned-capability placeholder hit. Trail authority: PRs #15-22 (ADR-063..068), all VERIFIED and merged; Polymath consumer PR #29 (register 11.275).

## Rejected claims
- "The migration is incomplete because the terminal envelope shows `qualifications: []`" — rejected. The per-hypothesis score/refusal is populated and correct; the output schema declares `qualifications` an optional array and an empty array is valid; no evidence, lineage, or score-authority loss. Owner-classified LOW backlog, does not block completion.
- "More governance slices are needed" — rejected. HR5 is VERIFIED at rank 148 (highest evidenced node); no governance node outranks it, so no further rank-fix slice can be required.

## Open contract gaps
- LOW backlog (do NOT reopen the migration): terminal AdapterResultV1 envelope surfaces `qualifications: []` while per-hypothesis scoring/refusal is correct. Any further work requires evidence from real product use, not migration cleanup.
