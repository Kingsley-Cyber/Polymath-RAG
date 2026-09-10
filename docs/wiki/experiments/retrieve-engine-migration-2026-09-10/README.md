---
change_id: RETRIEVE-ENGINE-MIGRATION-V1
date: 2026-09-10
last_reviewed: 2026-09-10
status: evidence (frozen)
architecture_impact: none (read-only parity measurement backing the /retrieve HYBRID reader migration)
---

# `/retrieve` HYBRID reader-migration parity (v1 → final core)

Backs `RETRIEVE-ENGINE-MIGRATION-V1` (register 11.191): migrating `/retrieve`'s single-corpus HYBRID mode from
the v1 `hybrid_fast_retrieve` onto the final `chat_retrieve_mode("HYBRID")` core, behind
`POLYMATH_RETRIEVE_ENGINE` (default `v2`, `v1` = rollback). This is MIGRATE LEGACY READER, NOT delete legacy
state — no summary/enrichment table is touched. Machine-readable results: `parity-result.json`.

## Method (read-only, local sidecars, no external spend)

For a covered corpus and two legacy corpora, call both engines directly and compare the public contract (the
top-level response keys) — content differs by design (final ranking); the CONTRACT must match.

## Result

| Corpus | Kind | v1 keys | v2 keys | v2 non-empty | v2 no error |
|---|---|---|---|---|---|
| `rag-canary` | vNext/covered | evidence·meta·query·selected_documents·selected_sections·trace | identical | 15 | ✓ |
| `ecom-meta-v1` | legacy, query_ready+enabled | identical | identical | 15 | ✓ |
| `cinema` | legacy, partial pMAP (hold) | identical | identical | 15 | ✓ |

**`migration_safe = True`** — identical public-contract keys on both engines across covered AND legacy corpora;
the final core runs **coverage-free** (base lanes = standard projections, additive lanes flag-off) and does not
error on legacy corpora. v2 returns 15 evidence rows vs v1's 10 (richer default, not a regression; callers that
need a fixed count pass a limit).

## Scope / what did NOT migrate

- `/retrieve` FAST = multi-corpus; the final core is single-corpus (`corpus_required`) → KEEP v1.
- `/retrieve` GRAPH / WILDCARD → the v1 engines return a DIFFERENT shape (graph_retrieve is nested
  documents/sections) than `chat_retrieve_mode` (flat) → NOT parity-proven → KEEP v1 pending their own parity.
- `/retrieve` default/LEGACY path reads `retrieval_summaries` → DELETE STATE, U-2/cutover-gated.
- `/ask` = a distinct grounded composite → migrate later.

## Rollback

`POLYMATH_RETRIEVE_ENGINE=v1` restores the legacy engine for HYBRID with zero code change. The running
orchestrator serves the change only after its next restart (the code default is `v2`).
