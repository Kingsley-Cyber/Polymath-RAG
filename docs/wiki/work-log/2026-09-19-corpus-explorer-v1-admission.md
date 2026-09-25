---
change_id: CORPUS-EXPLORER-V1-CE0
owner: "@king"
date: 2026-09-19
status: complete
status_note: "CE1-CE7 built and live (11.336-11.339, merge e84d7cc); firing closed and frozen (11.349); leftover caveats sit in OWNER-BACKLOG B19/B20. (was: admitted)"
architecture_impact: "CE0 admission only (docs + register + worktree). No code. Admits CORPUS-EXPLORER-V1: an optional, two-layer-gated (capability POLYMATH_CORPUS_EXPLORER x per-request corpus_explorer), non-generative concept-keyed corpus-activation path (CONCEPT/THEORY atoms via search_atoms, independent of Scout) that feeds the EXISTING WLK2C bridge compiler under a distinct CORPUS_EXPLORE origin into the existing V2 fusion + C4/C5/CA4 spine. Focused scope (atoms + Scout doc-nominations; parent-map/entity/graph deferred). Reuses bridge_compiler/bridge_integration unchanged (adds only an origin param). Flag-off = pre-feature-equivalent V2."
last_reviewed: 2026-09-19
---

## Contract
Owner /goal (2026-09-19) admitted CORPUS-EXPLORER-V1 as the next mission after LATENT-QUERY-FUSION-V2
(checkpoint tag `v4-latent-query-fusion-v2` -> `4500c20`). Plan-of-record: `docs/wiki/plans/CORPUS-EXPLORER-V1.md`
(ported from the grounded plan `/Users/king/.claude/plans/wild-stargazing-raven.md`, three recon passes +
direct file reads). LOCKED DESIGN (owner): NOT a second bridge compiler — reuse WLK2C
(`bridge_compiler.compile_bridges/parse_and_validate/compiler_eligible/LATENT_INTENTS`,
`bridge_integration.bridges_to_subqueries` + an origin param). NEW = non-generative concept path
`shared/polymath_shared/corpus_activation.py` from CONCEPT/THEORY atoms via `search_atoms`, INDEPENDENT of
Scout (Scout = optional corroboration). Focused scope only. Distinct origin `CORPUS_EXPLORE` (add to
`chat_plan.ORIGIN_TYPES`), mapped to the EXISTING BRIDGE fusion class/weight (no new weight/tunable).
Two-layer gate: server capability `POLYMATH_CORPUS_EXPLORER` (default 0) AND per-request `corpus_explorer`
AND `not plan.fallback`. UI "Corpus Explore" toggle off the critical path.

## Changes
CE0 (this slice) is admission + scaffolding only — no production code:
- Added `docs/wiki/plans/CORPUS-EXPLORER-V1.md` (plan-of-record, front matter + file:line seams for CE1-CE7 + CE-UI).
- Added this work-log.
- Appended `PLAN-AUTHORITY-REGISTER.md` row 11.335 (admission).
- Declared both new docs in `scripts/scaffold_polymath_v4.py` TREE.
- Verified pre-mission checkpoint: `production` HEAD == tag `v4-latent-query-fusion-v2` == `4500c20`, tree
  clean; guards preflight/repo_guard/wiki_worm=0, bundle_integrity READY; fleet 10 worker types healthy,
  one bundle, `/ready` true (embedder+reranker). Isolated in worktree `pmv4-explorer`
  (branch `explorer/corpus-activation`) off the checkpoint tag.

## Proof
`ADMITTED` (docs). Baseline guards green at 4500c20 (preflight=0, repo_guard=0, wiki_worm=0, bundle READY);
checkpoint tag == HEAD verified; live fleet healthy. No code executed this slice; CE1+ carry the
UNIT_PROVEN / LIVE_PATH_PROVEN evidence.

## Rejected claims
- REJECTED "make Scout deterministic" — Scout is already deterministic (recon-confirmed); the gap is
  document-centric grounding granularity, addressed by a non-generative concept-activation source.
- REJECTED building a second/parallel bridge compiler — WLK2C already enforces "activation not invention";
  CORPUS-EXPLORER reuses it.
- NOT claimed: any code proven this slice (CE0 is admission only).

## Open contract gaps
CE1-CE7 + CE-UI pending. Contracts to touch (dispositions to be recorded per slice): `chat_plan.ORIGIN_TYPES`
(add CORPUS_EXPLORE), `bridge_integration.bridges_to_subqueries` (origin param, backward-compatible),
`ranked_fusion.lineage_class` (map CORPUS_EXPLORE -> BRIDGE class), `candidate_engine.SubQuery` (origin
already free string), `StreamChatRequest`/`_compile_chat_plan` (per-request flag), `ui.py` latent filters
(LATENT_ORIGINS), `capabilities.py` (advertise the flag). All additive + fail-open + flag-gated; flag-off =
pre-feature-equivalent V2.
