---
title: "WORK LOG — elite mode slice C in the live production worktree"
change_id: ELITE-MODE-RETRIEVAL-SYNTHESIS-V1
date: 2026-09-17
owner: orchestrator
last_reviewed: 2026-09-17
status: executing
architecture_impact: "Synthesis now consumes compiled document-profile ONE/SUMMARY + parent-map signatures (ORIENTATION) and WILDCARD bridges (DERIVED [A#]). Chat flags INTENT_POLICY / HIERARCHY_ROUTE_DOCUMENTS / SYNTH_ROLES enabled in fleet .env. Cinema Qdrant document profiles re-projected from stored v3.2 artifacts (no Groq). Frontend files Claude already added are TREE-declared. No new mode, no new collection."
---

## Contract
Make HYBRID/GRAPH/WILDCARD earn their keep in the same worktree Claude is editing (`polymath-v4` `production`): put the LLM-extracted abstract layer into the synthesizer, restore usable document-profile vectors, turn the existing profile→map spine on via intent policy. Acceptance: empty-bundle prompts stay byte-identical; orientation/derived blocks appear when supplied; Murch v3.2 Qdrant payload has Rule of Six topics after reproject; orchestrator restarted so `.env` and `ui.py` are live.

## Changes
- `orchestrator/orchestrator/api/ui.py` — `_load_orientation` / `_render_orientation` / `_render_derived`; bundle keys `orientation` + `derived_insights`; receipts `orientation_docs` / `maps_in_prompt` / `derived_in_prompt`.
- `tests/determinism/test_chat_synthesis.py` — additive prompt test.
- `.env` — `POLYMATH_CHAT_INTENT_POLICY=on`, `POLYMATH_CHAT_HIERARCHY_ROUTE_DOCUMENTS=1`, `POLYMATH_CHAT_SYNTH_ROLES=1`.
- Cinema profile reproject from `doc-profile-v3.2` artifacts (local embedder).
- TREE: `AnswerBody.tsx`, `ProcessRail.tsx` (Claude's files, already in this worktree).
- Plan `ELITE-MODE-RETRIEVAL-SYNTHESIS-V1.md` marked executing for slices A–C.

## Proof
Determinism: `test_chat_synthesis.py` + `test_chat_hygiene.py`. Live: Qdrant Murch `prompt_version=doc-profile-v3.2` after reproject; `/ready` orchestrator after bounce.

Cinema HYBRID stream 2026-09-17 ~08:40Z (`/chat/stream`, `corpus_id=cinema`, synthesizer `deterministic-template-v3`, query “What are Murch's six criteria for the Rule of Six?”):
- `lane_sizes.dualread` = **23** (was 0 before intent policy)
- `orientation_docs` = **3**, `maps_in_prompt` = **5**, `derived_in_prompt` = 0 (HYBRID, not WILDCARD)
- answer cites the gold six-criteria passage (“An ideal cut … six criteria at once: 1) it is true to the emotion of the moment; 2) it advances the story”)
- phases: scope → compile → retrieve → assemble → synthesize, no error

## Rejected claims
- New worktree / new Qdrant collection / fourth mode.
- Re-calling Groq for profiles (v3.2 artifacts already exist).
- Changing Claude's frontend components (declared only).

## Open contract gaps
- Slice D GRAPH `[G#]` bind left for a follow-up (existing test pins `[fact:]` tagless lines).
- Slice E P12 atom-frontier still unimplemented.
- `POLYMATH_DOC_PROFILE_VNEXT=1` still on — new ingest would write thin profiles again; cinema Qdrant is restored to v3.2 until the next profile worker run.
