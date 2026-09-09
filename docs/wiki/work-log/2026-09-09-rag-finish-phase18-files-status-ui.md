---
title: "WORK LOG — RAG-finish Phase 18: Files/status UI on CANONICAL-DOCUMENT-STATUS-V1"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: orchestrator (read-only status endpoint) + governance (frontend)
last_reviewed: 2026-09-09
status: complete
register: 11.197 (pending)
package: orchestrator/orchestrator/api/ui.py, frontend/src/types.ts, frontend/src/api.ts, frontend/src/components/FilesView.tsx, tests/determinism/test_document_status_endpoint.py
architecture_impact: "Surfaces CANONICAL-DOCUMENT-STATUS-V1 in the product: a read-only GET /documents/{doc_id}/status endpoint (reuses document_status) + a lightweight map_active count on the /documents list, rendered as a per-row pMAP badge + an expandable status panel (profile / pMAP arithmetic / vNext readiness / contract versions / ordered blockers). No provider call; no write path; the orchestrator is reload-only (no worker fence)."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 18** + register **11.197** (pending).

## Contract

Files/status UI shows operational truth per document: profile state, pMAP mapped/eligible/excluded/
unresolved, semantic-index state, primary blocker (+ expanded: profile field/contract versions, pMAP batch
counts). Backend contract tests + `npm run build` (no new frontend test framework).

## Changes

- **Backend** (`orchestrator/api/ui.py`): `GET /documents/{doc_id}/status` → `document_status(conn, doc_id)`
  (404 `DOCUMENT_UNKNOWN` when absent). Added a cheap indexed `map_active` (active parent maps) subquery to
  the `GET /documents` list rows for the vNext row badge (full detail via the status endpoint).
- **Frontend**: `types.ts` (+`map_active`, `DocumentStatus`), `api.ts` (`fetchDocumentStatus`),
  `FilesView.tsx` — a `MapBadge` (🗺 maps/parents, green when fully mapped) per row + a `StatusPanel` in the
  expanded row (vNext ready pill, profile present/valid/vnext + quality, pMAP mapped/eligible/excluded/
  unresolved + batches, ordered blockers, profile contract versions). Fetched on row expand; best-effort.

## Proof

- `GET /documents/{doc_id}/status` and the `map_active` list field LIVE-verified against `rag-canary`:
  list rows carry `map_active` (5,5,5); the status endpoint returns `found=true vnext_ready=true blockers=[]
  pmap 5/5`. (orchestrator reloaded via `pkill -f "uvicorn orchestrator.main"`, ~10 s, workers untouched.)
- Backend contract test `test_document_status_endpoint.py` → 2/2 (canonical return + 404 on unknown);
  `test_documents_list_query.py` still green (2/2) with the added `map_active`.
- Frontend `npm run build` → **green** (`tsc --noEmit` + `vite build`, 293 modules).
- `bundle_integrity` READY; `repo_guard` / `wiki_worm` ok.

## Rejected claims

- **No frontend test framework added** (plan Phase 18): backend contract tests + `npm run build` per the plan.
- **Read-only** — the status endpoint and list field never write; the orchestrator reload carries no worker
  fence (orchestrator/ is reload-only).

## Open contract gaps

- The status panel is per-row on expand (one status fetch per open row); a corpus-wide status roll-up is not
  built (not required — the readiness panel already summarizes the corpus).
