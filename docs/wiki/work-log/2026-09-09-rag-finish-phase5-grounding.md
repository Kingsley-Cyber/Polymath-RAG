---
title: "WORK LOG — RAG-finish Phase 5: DOCUMENT-GROUNDING-CONTEXT-V1"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (deterministic policy; pure shared/, no I/O, no model)
last_reviewed: 2026-09-09
status: complete
register: 11.190 (pending)
package: shared/polymath_shared/document_profile/grounding.py, tests/determinism/test_document_grounding.py
architecture_impact: "New deterministic, CPU-only document-grounding compiler for the pMAP prompt (plan frozen §1.6 / Phase 5). Pure policy, reuses context.py helpers, no LLM/profile dependency. NOT yet wired into the pMAP prompt (that is Phase 6) — bundle hash unchanged (7e97368daa92ec19), no fleet fence. No provider quota spent."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 5** + register **11.190** (pending).

## Contract

Give every pMAP request compact, reliable, whole-document orientation WITHOUT an LLM dependency (plan Phase
5 / frozen §1.6): one deterministic CPU-only compiler over the common normalized structural inputs
(frontmatter + parent heading paths), a hard ~50-100-token budget, deterministic hash, no invented summary,
graceful degradation, independent of the LLM Document Profile.

## Changes

- `shared/polymath_shared/document_profile/grounding.py` (DOCUMENT-GROUNDING-CONTEXT-V1):
  `build_grounding_context(document, parents, budget_tokens=90) -> DocumentGroundingContextV1` with fields
  title / byline / doc_type / anchors + `render()` (the compact block for the pMAP prompt) + `context_hash`
  (enters pMAP generation identity in Phase 6). Reuses `context.py` (`clean_title`, `structure_lines`,
  `est_tokens`, `_trim_tokens`) so grounding and the profile context share one title/structure derivation.
  Precedence: frontmatter title → title-like first line → cleaned filename → "untitled". Outline = first
  MEANINGFUL segment of each furniture-filtered heading path (OCR/page-noise + title-echoing running headers
  rejected, deduped). Hard budget: trim outline → byline → type; the title is protected.
- `tests/determinism/test_document_grounding.py` — 11 document-class fixtures (md, plain-text-title-line,
  html, epub/TOC, docx, pdf, OCR-noisy, transcript, almost-empty, boilerplate-heavy, unicode) + invariant
  tests.

## Proof

- `pytest tests/determinism/test_document_grounding.py` → **9/9 green** (11 fixtures × invariants):
  within-budget + deterministic-hash for every fixture; title/author/outline surfaced for structured md;
  first-line title for plain text; TOC/boilerplate excluded from outline; OCR noise + repeated running
  header rejected/deduped; graceful degradation (missing author/structure omitted, title always present);
  unicode preserved; render is source-derived only (no invented token); budget stress trims outline before
  title.
- Sample renders (14-34 tok, all ≤ budget): structured md → `DOCUMENT/BY/TYPE/OUTLINE`; OCR scan →
  `Anatomy for Sculptors` + `The Skeleton · Musculature` (running header dropped); unicode preserved.
- `bundle_integrity` READY, hash unchanged `7e97368daa92ec19` (unwired) → no fleet fence.
- `repo_guard` / `wiki_worm` / `agent_preflight` ok.

## Rejected claims

- **NOT wired into runtime** — the pMAP prompt still renders skeletons only until Phase 6 injects the
  grounding and bumps `MAP_PROMPT_VERSION`; nothing about live ingestion changed here.
- **No format-specific ad-hoc logic** — one compiler over normalized inputs (frontmatter + heading paths);
  media_type only labels the TYPE line, it does not branch the derivation (plan Phase 5 action 2).

## Open contract gaps

- Phase 6: inject `grounding.render()` ahead of the ParentSkeleton blocks in `map_prompt.build_map_prompt`,
  bump `MAP_PROMPT_VERSION` → v2, and fold `context_hash` into the batch/generation identity so old
  skeleton-only maps do not satisfy the grounded generation. That is the first FENCED edit (map_prompt is
  imported by the pMAP path) → will need a fleet restart when it lands.
