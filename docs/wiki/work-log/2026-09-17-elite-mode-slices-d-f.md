---
title: "WORK LOG — elite mode slices D–F (GRAPH [G#], atom frontier, derived after DIRECT)"
change_id: ELITE-MODE-RETRIEVAL-SYNTHESIS-V1
date: 2026-09-17
owner: orchestrator
last_reviewed: 2026-09-17
status: complete
status_note: "Slices D-F shipped (register 11.278); slice G followed (11.279-11.280). Later GRAPH/WILDCARD work moved to SKELETON-ROUTING-V1 (11.440). (was: executing)"
architecture_impact: "GRAPH synthesis now emits labelled RELATIONS [G#] bound to a proving [S#] instead of tagless [fact:] lines mixed into EVIDENCE. Lane H localizes graph-destination docs through the parent map before hydrating children. WILDCARD sweep merges profile-atom nominations via the same map door (P12) without editing divergent.py. Derived [A#] blocks follow DIRECT evidence. No new store, no worker-tree edit, Claude frontend untouched."
---

## Contract
Make GRAPH and WILDCARD earn their keep in the same worktree Claude is editing (`polymath-v4` `production`). Acceptance: empty-bundle prompts stay byte-identical; GRAPH facts appear as `[G#]` with `proves: [S#]` when a judged child exists; unbound facts are labelled not source-backed; parent-map dest localization is a pure function + fail-open; atoms nominate extra WILDCARD parents; `[A#]` comes after EVIDENCE.

## Changes
- `orchestrator/orchestrator/api/ui.py` — `_render_relations` / `_proving_tag`; `[fact:]` removed from EVIDENCE; prompt order ORIENTATION → EVIDENCE → RELATIONS → DERIVED; receipts `relations_in_prompt` + counted `derived_in_prompt`.
- `orchestrator/orchestrator/api/chat_retrieval.py` — `graph_dest_parents_from_maps`, `merge_atom_frontier`, `bind_graph_fact_chunks`; lane H dest→map→child; WILDCARD sweep P12 atom merge.
- `tests/determinism/test_chat_synthesis.py` — B8 now pins `[G1]`+`proves: [S1]`; derived-after-evidence; unbound `[G#]`.
- `tests/determinism/test_wildcard_finish.py` — atom-frontier + dest-map unit tests.
- Register 11.278. TREE: this work-log.

## Proof
Offline: 16/16 `test_chat_synthesis.py` + `test_wildcard_finish.py` `-k "not live"` green (the two live `ecom-meta-v1` failures are pre-existing corpus 404, not this slice). `repo_guard` + `wiki_worm --check` ok.

Live cinema after orchestrator bounce (pid 47017, 2026-09-17 ~08:57Z), synthesizer `deterministic-template-v3`:

GRAPH “How does Walter Murch's Rule of Six relate emotion to story in an ideal cut?”
- intent RELATIONSHIP; `lane_sizes.graph_dest` = **8**; `graph_fact_count` = **3**; `graph_degraded` = null
- `relations_in_prompt` = **3** (tagless `[fact:]` gone); `orientation_docs` = 3, `maps_in_prompt` = 6; dualread = 21

WILDCARD “What transferable pattern in Murch's Rule of Six might apply to staging a fight scene?”
- 3 bridges; `derived_in_prompt` = **3**; `orientation_docs` = 3, `maps_in_prompt` = 6; dualread = 22

## Rejected claims
- Editing `shared/polymath_shared/divergent.py` (HASH-FENCE) — atom merge lives in the orchestrator sweep wrapper.
- A new Qdrant collection or a fourth mode.
- Flipping `POLYMATH_DOC_PARENT_MAP_ENABLED` (Slice G) or `POLYMATH_DOC_PROFILE_VNEXT`.
- Touching Claude's frontend-v2 components.

## Open contract gaps
- Slice G still owner-gated (new-ingest maps).
- `POLYMATH_DOC_PROFILE_VNEXT=1` still on — a new profile worker run would thin restored v3.2 cinema points.
- Live GRAPH/WILDCARD receipts require an orchestrator bounce after this `ui.py` edit.
- Dual-read children still tagged LATENT via `LANE_E` in `_LATENT_LANES` (pre-existing, not this slice).
