---
change_id: UI-V3-PRESENTATION-V1
owner: orchestrator
date: 2026-08-30
status: complete
architecture_impact: additive response fields (evidence_assembly presentation, retrieve/chat passthrough, citations human_locators) + 2 new UI endpoints (sections tree, F13 toggle) + frontend Sources panel / document tree; no retrieval contract change
last_reviewed: 2026-08-30
---

# WORK LOG — UI-V3-PRESENTATION-V1 (the v3.3-presentation overhaul, PRD executed)

## Contract
UI-V3-PRESENTATION-PRD.md §§3-6 with its §8 drift check: documents and
sections as first-class readable objects, human citation locators,
chunk internals demoted to provenance-on-demand, zero raw chunk ids in
the default view — presentation only, everything additive.

## Changes
- §3.1 `evidence_assembly._presentation`: every bundle item gains
  `presentation {title, heading_path, human_locator}` — best-effort,
  NULL heading_path (all legacy rows) degrades to source-name-only,
  never raises. Chunk resolver now selects heading_path.
- §3.2 FAST response: `_presentation_joins` (two batched queries,
  fail-open) fixes the measured `source_name:""` bug (child routing
  points carry no name; the documents row does) and adds
  title/heading_path/human_locator + a 240-char text excerpt per
  evidence item.
- §3.3 citations: `human_locators` beside raw `locators` (additive).
- Chat chunk inventory (ui.py): source_name/title/heading_path/
  human_locator per chunk ref for the Sources panel.
- NEW `GET /documents/{doc_id}/sections`: the document -> section tree
  from the compiled parent cards (ONE-SUMMARY-AUTHORITY); title = 
  heading leaf, or summary head when heading_path is NULL (PRD §2).
- F13 `PATCH /corpora/{id}/query_enabled`: the retrieval-visibility
  toggle, surfaced in Files view with an ENABLED/HIDDEN pill.
- Frontend: SourceRow (human name › section + verbatim quote, raw
  locator/ids behind a per-row provenance expander, quote copy);
  DocRows (expandable section tree: title, card summary, keywords,
  child count, id copy affordance); Retrieval-visibility panel.

## Proof
- LIVE: FAST evidence now ships real names ("AWS for Solutions
  Architects 2nd Edition" + human locators + excerpts) — the
  source_name bug is dead; /documents/<doc>/sections returns 40
  sections with fallback titles on the legacy corpus; the F13 PATCH
  flips and reports.
- BROWSER (dev server :5173): Files view renders the expandable
  document -> section tree with summaries+keywords; chat answer cites
  [S#]; the Sources panel shows "[1] AWS for Solutions Architects 2nd
  Edition (Shrivastava).md · child_chunk" with verbatim quote and a
  provenance expander — zero raw chunk ids in the default view
  (acceptance §6.1).
- tsc --noEmit clean; vite production build clean.
- test_evidence_assembly presentation tests (NULL-safe, heading leaf,
  doc-summary identity) green; citations pin updated for the additive
  human_locators field; determinism suite at the 8-failure pre-existing
  baseline.

## Rejected claims
- "Join section titles from retrieval_summaries at assembly time" —
  rejected for the bundle path: the assembler is pure over resolvers;
  the heading lives on the chunk row the resolver already returns. The
  tree endpoint reads the cards directly instead.

## Open contract gaps
- heading_path is NULL corpus-wide (both docs predate the column):
  human locators are source-name-only until the next ingest populates
  it — the PRD's §2 expectation, verified live.
- Golden screenshots captured in-session (browser), not attached as
  files; attach on the next PR if the owner wants artifacts.
