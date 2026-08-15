---
triggered_by: ADR-0010 (RAG E2E gate I0)
status: done
last_reviewed: 2026-08-14
last_touched: 2026-08-14
---

# Refactor 0007: I0 native document materialization

ADR-0010 introduced the native document materialization layer. This
refactor materialized it:

- `shared/polymath_shared/materializer.py`: deterministic per-format
  materialization (TXT/MD/HTML/PDF/EPUB/DOCX) → normalized text +
  structural source map (page/chapter/section/paragraph) + parser
  identity + hashes; typed loud failures (unsupported/encrypted/
  corrupted/empty/low-yield).
- Intake worker materializes inside the stage transaction and persists
  `documents.source_hash` / `materialization` / `source_map`
  (migration 0006); failures commit a FAILURE receipt.
- Extract worker now consumes the authoritative Postgres chunks
  committed by intake (no re-derivation from event bytes) — one chunk
  lineage for native and text formats.
- New contract `contracts/ingestion/v1/materialization.schema.json`;
  one new dependency (`pypdf`); public-domain book fixtures in six
  formats; 14 unit + 4 contract + 1 live E2E tests (both book samples
  through the full pipeline with source lineage).

Affected dependents verified: semantic extraction untouched (compiler/
rule pack/ontology/GLiNER/thresholds unchanged); TXT behavior
byte-stable (Q1 regression locks still green); full suites green.

Proof: see work log `2026-08-14-i0-native-documents.md`.
