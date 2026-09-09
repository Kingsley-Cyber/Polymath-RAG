---
title: "WORK LOG — RAG-finish Phase 12: canonical document status"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (read-only status aggregate; no runtime behavior change)
last_reviewed: 2026-09-09
status: complete (per-document status builder; the canary diagnostic packet writer + the Files/status endpoint follow in the canary harness / Phase 18)
register: 11.194 (pending)
package: shared/polymath_shared/document_status.py, tests/determinism/test_document_status.py
architecture_impact: "Adds CANONICAL-DOCUMENT-STATUS-V1: one read-only per-document aggregate from durable Postgres (stage tickets + profile/pMAP artifacts + 0054 pMAP arithmetic + readiness verdicts + pool lane health) with an ordered blocker list a failed canary reads. No provider call; bundle unchanged; no fleet fence."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 12** + register **11.194** (pending).

## Contract

A failed canary must explain itself: one authoritative per-document status exposing exact counts + exact
blockers, derived from durable state (receipts prove state; logs do not), following the plan's triage order
so the FIRST blocker names the stage/lane to look at.

## Changes

- `shared/polymath_shared/document_status.py`: `document_status(conn, doc_id)` → identity, chunks
  (children/parents), profile (present/valid/vnext/quality/versions), pmap (eligible/mapped/excluded/
  unresolved/batches), readiness (legacy + `vnext_readiness`), stages (ticket/status/attempt/error),
  functional_pools (lane health), and an ordered `blockers` list. Non-blocking pMAP shortfalls surface as
  `pmap_unresolved:N_of_M`, not a generic stage blocker.
- `tests/determinism/test_document_status.py`: scripted-conn tests for a COMPLETE doc (no blockers,
  VNEXT_COMPLETE) and a pMAP-STALLED doc (names `pmap_unresolved:2_of_3` first) + missing-document.

## Proof

- `pytest tests/determinism/test_document_status.py` → **3/3 green**.
- `bundle_integrity` READY; `repo_guard` / `wiki_worm` ok.

## Rejected claims

- **NOT a new source of truth** — `document_status` only READS durable Postgres (the same rows the readiness
  verdict and the DAG already own); it computes no state and writes nothing. A comment or log line is never
  consulted (receipts prove state).
- **NOT the live endpoint** — the Files/status UI wiring is Phase 18; this slice is the reusable builder only.

## Open contract gaps

- The canary diagnostic packet writer (run-scoped folder) is built into the Phase 15 canary harness, which
  consumes `document_status`. The Files/status UI consuming the same aggregate is Phase 18.
