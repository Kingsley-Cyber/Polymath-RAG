---
title: "WORK LOG — cinema chat does not retrieve pMAP or latent points"
change_id: PMAP-ABSTRACT-QUERY-WIRING-GAP
date: 2026-09-17
owner: governance
last_reviewed: 2026-09-17
status: measured
architecture_impact: none (read-only audit; no runtime change)
---

## Contract
Record a measured gap: parent maps and the abstract/latent layer are indexed for cinema, and live HYBRID `/chat/stream` does not search them. The owner-designed ParentSkeleton → map → dual-read spine is the intended retrieval path. Acceptance: a dated report citing live Qdrant/Postgres counts and a cinema chat receipt with `dualread: 0` and `latent_rescue: 0`.

## Changes
- `docs/wiki/reports/2026-09-17/PMAP-ABSTRACT-QUERY-WIRING-GAP.md` — the report.
- This work-log and TREE declarations. No runtime, flag, or test change.

## Proof
Live 2026-09-17 against fleet on `production` `cf1ee4f`, cinema 67 docs, embedding `embed_e794ec4cab197a3f`:
- PG: 11,993 active parent maps (67/67 docs), 11,691 READY enrichments, 67 document summaries.
- Qdrant: 11,703 cinema parent-map points; 11,691 `latent_abstraction` + 11,683 `latent_transfer` in the routing collection; 67 cinema profiles.
- Murch chat receipt `q_ff8c0289c9994460b3734ee3`: `dualread: 0`, `latent_rescue: 0`, `document_summary: 0`, hierarchical 25 / dense 50 / sparse 40.
- Gold Rule-of-Six list child never entered any lane; its parent map row carries `routing_signature='Explanation of Rule of Six emphasizing emotion and story'` and hooks `["Rule of Six","emotion","story"]`.
- `.env` has no `POLYMATH_CHAT_INTENT_POLICY` / `DUALREAD` / `LATENT` / `HIERARCHY_ROUTE_DOCUMENTS`. Defaults keep lane E and lane D off (`candidate_engine.py` `dualread_enabled=False`, `latent_enabled=False`; `hierarchy_route_documents=False`; `intent_policy_enabled` requires env on).

## Rejected claims
- "pMAP and the abstract layer are mapped into the retrieval layer" — rejected for production cinema chat. They are in Qdrant. The chat engine did not query those collections/kinds. Ledger rows marked DONE (default-off) are not a live retrieval proof.
- "The gold Murch list is missing because the parent was never mapped" — rejected. The parent map exists and names Rule of Six. Dual-read did not run.
- "Document summaries are the hierarchical door on these turns" — rejected. `document_summary: 0`; section summaries (24) were the only hierarchy that fired.

## Open contract gaps
- 290 cinema pMAP PG rows have no Qdrant point (11,993 vs 11,703). 1 document summary missing from Qdrant (67 vs 66). Not diagnosed here.
- Retrieval claim becomes true only after flags on + bounce + a receipt with `dualread > 0` (and `latent_rescue > 0` if the abstract layer is in the claim).
- Dual-read on the current Qdrant profile would use `doc-profile-vnext-v1` (Murch: 1 TOPIC / 1 Q, Rule of Six absent). The v3.2 compiler output that named Rule of Six is superseded in the index. Flipping retrieval flags does not restore that profile.
- `POLYMATH_DOC_PARENT_MAP_ENABLED` is unset: new uploads are not mapped. Cinema pMAP is a 2026-09-08 backfill.

## Addendum 2026-09-17 — extraction prompts (same change_id)
Owner asked whether the document-wide ONE/SUMMARY/TOPIC/TERM/Q compiler is still sent, and for the same analysis on pMAP. Report §§8–9.

### Changes
- `docs/wiki/reports/2026-09-17/PMAP-ABSTRACT-QUERY-WIRING-GAP.md` §§8–9 + §6 item 5 + residual on vNext collapse. No runtime change.

### Proof (live cinema, fleet `.env`, 2026-09-17)
- Document profile is stage `doc_profile`, prompt `doc-profile-v3.2` **or** `doc-profile-vnext-v1`. `DETAIL:` is not in either system prompt; compiler still accepts it. Murch has no DETAIL.
- `.env` `POLYMATH_DOC_PROFILE_VNEXT=1`. Latest-per-doc cinema = 67/67 vNext. Qdrant Murch point `prompt_version=doc-profile-vnext-v1`, `topics=['Film Editing']`, questions multivector n=1.
- Murch v3.2 artifact (2026-09-07): TOPIC 10 including Rule of Six; Q 15 starting "What are the six criteria of Murch’s Rule of Six?"; TERM 10 including Rule of Six. vNext (2026-09-08, `groq/compound`, quality 0.823): one line per label. Rebuilt fingerprint omits Rule of Six from STRUCTURE/COVERAGE/VOCABULARY.
- pMAP stage `doc_parent_map`, prompt `map-prompt-v2`, compiler `map-compiler-v1`. Rule of Six parent `chunk_a9a6bf42…` alias P0007. Stored `routing_signature='Explanation of Rule of Six emphasizing emotion and story'`, hooks `["Rule of Six","emotion","story"]`. Rebuilt EXCERPT is the tongue-in-cheek ranking sentence (≤30 words), not the numbered six-criteria list (present in the 8,242-char parent). Grounding `DOCUMENT:` is `## OEBPS/Text/main.xhtml`.
- Murch 42 active maps, one historical `batch_id`. Today's `MAP_RELIABILITY_CAP=15` would plan 15/15/12. `POLYMATH_DOC_PARENT_MAP_ENABLED` absent from `.env`.
- Chat consumer of both: lane E (`profile_nominate` → `search_parent_maps`). Still `dualread: 0`.

### Rejected claims
- "The ONE/SUMMARY/TOPIC compiler is gone" — rejected. v3.2 and vNext both ran on cinema; vNext is what Qdrant serves.
- "pMAP is sent the parent (or the six-criteria list)" — rejected. Skeleton only; salient excerpt is one ≤30-word sentence.
- "Turning dual-read on would retrieve the v3.2 Rule-of-Six profile" — rejected for today's index. Qdrant holds vNext.

## Addendum 2026-09-17 — close-out (original Proof above is frozen)

Same change_id. Does **not** rewrite `dualread: 0` / vNext Qdrant in the original Proof. Live cinema after elite A–G:

### Changes
- Report §13. Work-log `2026-09-17-wiring-gap-closeout.md`. Register 11.279.
- Qdrant: 290 missing cinema parent-map points upserted (local embedder).
- `.env`: `POLYMATH_DOC_PARENT_MAP_ENABLED=1`, `POLYMATH_DOC_PARENT_MAP_SINCE=2026-09-17T13:24:27Z`, `POLYMATH_DOC_PROFILE_VNEXT=0`.

### Proof
- HYBRID “Rule of Six”: `dualread=23`, `latent_rescue=18`, `document_summary=16`. Gold child tagged `SHADOW_DUALREAD`; parent `chunk_a9a6bf42…`.
- Cinema parent maps PG 11,993 = Qdrant 11,993.
- Manga doc summary: compiler wrote 0 (all children non-summarizable). Not a projection miss.

### Rejected claims
- "The 67 vs 66 document summary is an unprojected Qdrant point" — rejected. PG and Qdrant both 66; the 67th document has no body region_role.

### Open contract gaps
- Fleet bounce **done** 2026-09-17T13:27Z: live workers carry `ENABLED=1` / `SINCE=2026-09-17T13:24:27Z` / `VNEXT=0`. Cinema pMAP tickets unchanged (48 `done`).
- A later fresh upload (run `created_at` after `SINCE`) is the live mint proof for slice G.
