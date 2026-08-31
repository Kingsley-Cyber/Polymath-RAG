---
last_reviewed: 2026-08-30
change_id: UI-V3-PRESENTATION-PRD
owner: governance
date: 2026-08-30
status: draft-for-implementation
architecture_impact: orchestrator retrieve/ask response enrichment + frontend views
---

# PRD — v4 UI v3.3-Presentation Overhaul

> Goal: make the v4 UI present like polymath v3.3 — documents and sections
> as first-class readable objects, human citation locators, chunk internals
> demoted to provenance-on-demand — WITHOUT changing any retrieval contract,
> storage schema, or admission semantics. Presentation-layer only plus two
> additive response fields.

## 0. Problem (owner-verbal, confirmed by inspection)

The v4 UI renders internal machinery: evidence items lead with
`chunk:chunk_6a8f85be…` locators, documents are hash-ids in a flat table,
chunk details are the default view. v3.3 presented documents → sections
with heading paths, readable titles, summaries and coverage stats. The
backend ships ids but not presentation metadata — the UI cannot show what
was never sent.

## 1. Verified contract surface (Graphify + schema inspection)

Graphify (12,947 nodes / 21,129 edges): `retrieve` 32 nodes,
`evidence_assembly` 38 nodes + 98 touching edges, `answer_synthesis` 58,
`pass1` 45 — the four contract points below are the whole surface the UI
reads. No other files need to change.

| # | Contract point | Current | Gap |
|---|---|---|---|
| A | `shared/polymath_shared/evidence_assembly.py` — evidence items: `{lane, text_kind, source_document_id, source_span{locator "chunk:{id}@s:e", chunk_id, offsets}, …}`; source_name joined but **section title / heading path absent**; `locator` = raw internal id | items lack presentation fields | add `title`, `heading_path`, `human_locator` |
| B | `orchestrator/api/retrieve.py` response: `{evidence[{chunk_id, doc_id, parent_id, source_name:""(empty bug), locator, g3_score, arrival}], selected_sections, selected_documents, meta}` | source_name empty; no titles/quotes in evidence | pass through A's fields; include `text`/`plain_summary` excerpt |
| C | `answer_synthesis.py` citations (`locators` list) | same raw id locators | human locator |
| D | Frontend: `MessageBubble.ChunksPanel` renders `[n] chunk:chunk_…`; `FilesView` flat table with hash ids; no section tree; no sources panel styled like v3.3 | full rewrite of 2 components + 1 new | see §3 |

## 2. Data availability (verified live)

- `chunks.heading_path` column exists; **populated only for new ingests**
  (intake_worker writes it; legacy rows have NULL). Presentation must
  handle NULL heading_path: fall back to first heading line from
  `document_layout` regions or the child `summary` head.
- `retrieval_summaries` carries `plain_summary`, `keywords`, `coverage`,
  `provenance` per section — the parent-card content for the tree view.
- `documents.source_name` exists (the delete-by-name fix already reads it).
- Section summaries already embed + project as
  `routing_section_summary` — the tree view reuses existing vectors.

## 3. Backend changes (additive, no contract breaks)

1. `evidence_assembly.assemble_evidence_bundle`: for each evidence item,
   join `chunks.heading_path` (or first heading from `document_layout`) +
   `documents.source_name` + parent section title (from
   `retrieval_summaries.plain_summary` head). Add three OPTIONAL response
   fields per item: `title`, `heading_path`, `human_locator`
   (`"{source_name} › {section}"`). Keep every existing field —
   analyzers/receipts unchanged.
2. `retrieve.py`: evidence items pass through the new fields; evidence
   `text` excerpt (first 240 chars) included for one-call rendering.
3. `answer_synthesis`: citations emit `human_locator` alongside locators.
4. 422→400 class fix for wrong-confirm already shipped (4191b74); carry
   into this PR's tests.

Failure mode: all new fields are best-effort — a missing join renders
empty string, never raises. Response shape grows; nothing removed.

## 4. Frontend changes

1. **Sources panel (new component, v3.3 style)**: answers render `[n]`
   citations → Sources list: `source_name › section title` + verbatim
   quote + copy. Chunk ids/offsets only behind "provenance" expander.
2. **Documents view**: document card (name, size, stage chips, ✓ summary
   status) → expandable **section tree**: section title + parent card
   summary + coverage, children as evidence rows beneath. Hash ids behind
   a copy affordance.
3. **Readiness panel**: verdict line + human labels (shipped 2026-08-30,
   a18c767) — keep; wire the new pending-label map for
   `unprojected_procedures/concepts`.
4. Keep adaptive polling (4s active / 12s idle) + focus refetch.

## 5. Tests

- Backend: assembly unit test (heading_path present → title+human_locator
  populated; NULL → empty strings, no raise); retrieve response shape test
  (all legacy fields present + new fields additive).
- Frontend: build passes; manual golden screenshots (answer view, docs
  tree) attached to the PR.

## 6. Acceptance

- Answers show Sources with human names/sections; zero raw chunk ids in
  the default view.
- Documents render as document → section tree with summaries.
- No retrieval contract change: pass1/FAST/HYBRID/GRAPH outputs identical
  modulo additive fields; receipts unchanged.

## 7. Sequencing / dependencies

Independent of the ingestion-lane work (extract2, ceiling 72K, lean
prompt). Backend ~half day, frontend ~half day. Can start immediately in
a fresh session pointed at this file.

## 8. Drift check vs HEAD 62bcc9d (2026-08-30, post-RETRIEVAL-FULL-FIX-V1)

The §1 table was verified BEFORE commits 24d65f9 + 37777c4 landed on the
same contract points. Re-verified live at HEAD; the plan survives intact,
with these corrections and additions:

- **source_name:"" is NOT yet fixed** — probed live at HEAD: FAST
  evidence items still ship `source_name: ''` (selected_sections carry
  the real name). The fix is §3.1/§3.2 work for the implementing
  session, not something to assume done.
- **§1B response grew (additive)**: `evidence[]` items now carry
  `document_rank`; the response adds `entity_card_lane[]`; `meta` adds
  `entity_card_votes`, `liveness`, and — MULTI-CORPUS-FAST-V1 —
  `meta.corpus_ids` (list) while `meta.corpus_id` is **null when the
  scope is >1 corpus**. Frontend must key off `meta.corpus_ids`, never
  assume a single corpus id.
- **§1C partially superseded on the chat path**: CITATION-TAGS-V1
  (24d65f9) — /chat/stream answers now cite `[S1]..[Sn]` tags with a
  SOURCE TAGS legend in the prompt; the §4.1 Sources panel should map
  `[S#]` → evidence bundle entries. `answer_synthesis.py` locators are
  still raw ids (verified at HEAD) — §3.3 stands.
- **Volume**: depth-profile answers now ship up to 32 evidence rows and
  the synthesis bundle caps at 48×2000 chars (EVIDENCE-BUDGET-V2) — the
  Sources panel needs scroll/collapse at that scale.
- Plan version is `pass1-retrieval-v2`; response-shape tests in §5 must
  pin the ADDITIVE stance against v2, not the v1 field list.
