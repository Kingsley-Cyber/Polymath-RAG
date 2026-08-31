---
change_id: TIER-CHUNKER-V3
owner: governance
date: 2026-08-31
status: complete
architecture_impact: chunk generation swap (chunk-structure-v3); re-ingest via contract reconciliation
last_reviewed: 2026-08-31
---

# WORK LOG — TIER-CHUNKER-V3 (latent plan D15, Phase 0)

## Contract
Latent plan §4 Phase 0 + D15, owner GO 2026-08-31 ("es i want i. so
buid it") after the case assessment: heading-bounded parents ~850 w
target / 1,400 w max carrying REAL section text, real heading_path on
every row, atomic tables/code, noise handling, <15-word stub drop.
Owner-ratified amendment to D15's letter: implemented NATIVELY on v4's
structural regions instead of porting the v3.3 module — the v3.3 code
rewrites text (markup scrub, token re-joins), which would break v4's
§8 offset contract (byte-exact substrings + char offsets) that UI
provenance and the projection verifiers depend on. D15's intent (the
canonical parent SHAPE as the unit of enrichment/extraction) is
preserved; its mechanism is not.

## Changes
- `workers/workers/tier_chunker.py` (chunk-structure-v3, provider
  `tier_v3`): level-aware walker (heading stack POPS on same-or-
  shallower levels — the v2 walker's path only ever grew); sections
  never merge across distinct heading paths; page-scaffold sections
  ("Page N" / OCR_FALLBACK_TEXT conversion artifacts) merge to budget
  under their real ancestry with page-range labels (the v3.3 OCR-lane
  rule); parents = exact source spans (heading line included), split
  paragraph→sentence→word so the 1,400 w cap is HARD; children =
  exact sub-spans (prose paragraph-first ~120 w, structured blocks
  atomic ≤700 w); parent-min merge pass so budget splits never strand
  fragment parents; every row validated byte-exact, children nested
  in parent spans, monotonic, non-overlapping.
- `intake_worker.py`: `tier_v3` branch; GENERATION-PURGE — chunk rows
  of any OTHER contract version die per-doc before insert (chunk ids
  are content-addressed, so a chunker swap re-identifies everything
  and `ON CONFLICT DO NOTHING` would leave the old generation live
  beside the new: retrieval would mix generations); `layout_regions`
  initialized before the provider branch (the semantic_v2 path would
  NameError at the layout projection — latent bug, never run live);
  `tier_frozen` params pinned into the intake stage contract hash.
- `settings.py`: `worker.chunker` default → `tier_v3`. This is the
  re-ingest trigger: "chunker" is a pinned execution-contract key and
  `reconciliation._STAGE_DEPS` maps intake→chunker, so contract drift
  mints successors that regenerate the whole chain (the exact
  mechanism the A1 E2E proved).
- Scaffold TREE declarations for the three new files.

## Proof
- `tests/determinism/test_tier_chunker.py` — 9 asserts green: level-
  aware paths (H2 replaces H2, H1 clears), heading-bounded real-text
  parents, byte-exact offsets + child nesting on every row, no
  heading lines in child bodies, atomic table/code children, oversize
  split with no fragment tail and cap respected, stub/heading-only
  drop, headingless docs still chunk, byte-identical determinism.
- Real-book smoke (both live docs via spool → materialize →
  tier_chunk_rows): AWS 41 parents med 680 w / max 841 w, SQL 26
  parents med 762 w / max 918 w, 0 over cap, children med ~125 w max
  ≤250 w, 100% of parents carry heading_path, page ranges labelled
  ("Pages 1–6"). Pre-fix smoke had caught a 2,178 w cap escape
  (single paragraph, no blank lines) and page-sized parents — both
  fixed and re-proven.
- Suite baseline discipline: determinism/contracts/integration run
  per-directory; every failure stash-bisected against clean HEAD —
  all pre-existing (llm_controller, sval ×3, contracts ×3, summary
  d3/d4 stateful, and 8 full-tree collection errors that reproduce on
  clean HEAD). Zero new failures from this change.
- Live rollout receipts recorded below in "Live rollout".

## Live rollout
(filled in the same session — see CONTINUITY-REPORT for the current
state) Fleet restarted on the new code; reconciliation minted
successors for the legacy-pinned runs; intake regenerated both docs
under chunk-structure-v3 with the generation purge removing the 321
legacy rows; census drove the chain to query_ready; auto-enrich
re-minted enrichments for the new canonical parents.

## Rejected claims
- "Port the v3.3 tier_chunker module wholesale" — rejected (owner
  ratified the native route): the module rewrites text and would
  regress the §8 offset contract; it also drags in the docling
  section shape, tiktoken, SaT, and 4 dependency modules v4 does not
  have.
- "The v2 structural walker can be reused as-is" — rejected: its
  heading_path accumulates forever (no level pop), which is exactly
  the defect that would poison the UI section tree.
- "Strict heading-bounded parents are enough" — refuted by the live
  books: both are page-converted markdown ("Page N" headings), and
  strict boundaries froze parents at page size (~250 w). The v3.3
  OCR-lane page-grouping rule was ported for scaffold headings only;
  real headings remain hard boundaries.

## Open contract gaps
- Full-tree pytest collection has 8 pre-existing import-shadowing
  errors (`orchestrator.orchestrator`) that reproduce on clean HEAD;
  per-directory runs are unaffected. Untouched here — separate
  hygiene fix.
- The F7/F10 breadth/depth caps and the P6 latent numbers were
  measured on interim chunks (MASTER-BUILD-SEQUENCE C9 warned this
  ordering); P6 re-runs on the new generation this session — cap
  re-tuning remains owner-scheduled if the re-run shifts.
- Stale `parent_enrichments` rows for dead parent ids linger
  harmlessly (never projected — the want-set derives from live
  parents); a vacuum is cosmetic, not correctness.
