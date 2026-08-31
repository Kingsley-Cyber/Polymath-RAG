---
change_id: AUTO-ENRICH-UI-V1
owner: control-plane
date: 2026-08-31
status: complete
architecture_impact: control scheduler (auto-mint on promotion) + shared latent/trigger.py (ONE mint path) + documents endpoint enrichment counts + FilesView badges/conditional buttons/new-corpus/add-files
last_reviewed: 2026-08-31
---

# WORK LOG — AUTO-ENRICH-UI-V1 (auto-kick at ingest + enrichment UI)

## Contract
Owner 2026-08-31: latent lanes auto-kick during ingest (AI picks the
control timing); the document ✨ button renders ONLY while sections
remain to enrich (e.g. ingest-era errors); files show an
already-enriched indicator; the UI gains explicit add-file and
new-corpus affordances.

## Changes
- AUTO-ENRICH-ON-INGEST (amends §0a): the census tick is the control
  timer and RUN PROMOTION to query_ready is the trigger —
  `apply_promotions` mints the enrichment ticket/event per promoted
  run (fail-open; `enrichment_auto` settings gate, default ON).
  Timing rationale: retrieval is up FIRST (enrichment additive, §0b
  absence-invisible), parents are settled, and (stage, input_hash)
  idempotency makes re-promotions free. Buttons remain the gap-filler.
- ONE mint path: `latent/trigger.mint_parent_enrichment` shared by the
  scheduler and both §0a endpoints (ends the copy-drift class).
- `/documents` gains per-doc `parents / enriched / enrich_failed`
  (DISTINCT-counted — the LEFT-JOIN cross-multiply trap avoided).
- FilesView: EnrichBadge (green "✨ enriched" when complete, amber
  "✨ x/y" partial with failed count in the tooltip); EnrichCell — the
  per-doc ✨ button renders ONLY while remaining>0; corpus panel shows
  "✨ Enrich (n remaining)" or a "fully enriched" pill; explicit
  "＋ Add files" button; TopBar "＋ new" corpus flow (id prompt →
  synthetic option → corpus is created server-side on first upload,
  which is the existing intake contract).

## Proof
- /documents live: AWS parents=40 enriched=40 failed=0; Learning SQL
  25/24/1 — matches ground truth exactly.
- Browser: AWS row shows the green pill and NO button; SQL shows
  "✨ 24/25" + "✨ 1" retry; corpus panel "Enrich (1 remaining)";
  Add-files and new-corpus controls render. tsc + vite build clean.
- Auto-enrich hook loaded (control restarted); next promotion mints
  enrichment automatically.

## Rejected claims
- "Trigger enrichment at extract completion" — rejected: mid-ingest
  enrichment races settling parents and competes for lanes while the
  corpus is not yet queryable; post-promotion is strictly better on
  both axes.

## Open contract gaps
- The 1 remaining SQL section is the genuine ENRICH_UNPARSEABLE; its
  retry button re-attempts on click (may keep failing on that model —
  acceptable, visible).
