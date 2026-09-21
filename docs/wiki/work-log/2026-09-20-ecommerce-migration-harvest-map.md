---
change_id: GOVERNED-CONVERGENCE-V1-MIGRATION-REFRAME
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — docs only. The owner reframed the work as a migration / recovery project and asked for a harvest map before any further code. This slice records the authoritative product direction in the plan of record and adds the read-only harvest map. No code, manifest, contract, Trail, skill-repo or Item 2D change. Implementation stays HALTED."
last_reviewed: 2026-09-20
---

## Contract
Owner words 2026-09-20: "Do the plan update and requirements/gap matrix first. Keep implementation halted until I review that
result." — then, after observing "i think we have rebuilt this project twice": "establish whether we are rebuilding
functionality that already exists in TRAIL_AGENT_AUTORESEARCH … This is a read-only comparison. Do not implement, run tests or
services, or design another framework." — then the reframe: "stop treating this as 'finish TG5' and treat it as a
migration/recovery project … a harvest map, not another implementation prompt … Harvest behavior, not architecture."
- Evidence standard, applied to BOTH systems: implementation · fixture execution · real-input execution · evidence of useful
  ecommerce output. An unexercised capability is not automatically missing; existing code is not automatically proven useful.
- Verifier: every claim that decides retain / replace / reconnect checked by the primary agent against current code or a run
  artifact; the rest reader-reported with file:line. Nothing executed.

## Changes
- `docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md`: status → REFRAMED / HALTED; NEW section "Product direction and migration
  reframe" (authoritative goal, roles, scope, the re-read of "ignore ecom", the UNCONFIRMED dossier specification kept
  unconfirmed, one owner per authority, the halt); execution-ledger line.
- NEW `docs/wiki/reports/2026-09-20/ECOMMERCE-MIGRATION-HARVEST-MAP.md`.
- Register 11.362, scaffold `TREE`, CONTINUITY pointer.

## Proof
Read-only. Verified by the primary agent: the controller's one complete real run (`calib_books_01`: 5 concepts × 2 variations,
135 supplier candidates 96 / 39, 8 leads with price + MOQ, 146 observations all Reddit, supplier name `unresolved`); the
`evidence_score` arithmetic (`executors.py:553-556`); the hard-coded supplier identity (`sourcing_exa.py:49`); the controller's
own admission rules (`verifiers.py:18/62/102`); Trail discarding `metric_if_present` (one definition line, no reader); 4 of 7
hard gates outside `STAGE_GATES` (`qualification.py:42-44`); the registry mirror DRIFT (+6 seeds, +10 friction families, +6
niche candidates; 3 other files byte-identical; `source_capabilities.csv` not mirrored); the local clone = the owner's GitHub
repo, engine files unchanged from GitHub. Reader-reported: function signatures, state keys, couplings, test-section reuse.
Guards: `agent_preflight` 0 · `repo_guard` 0 · `wiki_worm --check` 0 · `bundle_integrity` READY (static; no database).

## Rejected claims
- "The original controller is proven." One complete real run, on a deleted corpus and a retired answer lane, Reddit only, no
  competing-product research, no resolved supplier, a failed canary, no rendered report.
- "The governed path is missing these capabilities." Several are unexercised rather than missing (`P_reality`, qualification,
  score); several are genuinely absent (population discovery, bridge laws, typed concepts + variations).
- "Move the controller under the adapter." That nests a second state machine. The harvest is functions, prompts, validators,
  schemas, parsers and the renderer.
- "The dossier specification is a requirement." It was never confirmed by the owner and is recorded as unconfirmed.

## Open contract gaps
Dispositions: no contract changed — everything NOT_AFFECTED.
- Owner review of the harvest map is the gate for ALL implementation (M1-04 containment, D1, Item 2D included).
- Decisions only the owner can make: the commerce corpus; whether Trail-side fixes (TG7) precede the first ecommerce run;
  whether the mirror's drifted registry rows are upstreamed to Trail or dropped.
- Open design points the evidence does not settle are listed in §9 of the harvest map.
