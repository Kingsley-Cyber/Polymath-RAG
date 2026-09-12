---
title: "WORK LOG — FRONTEND-V2-CONTINUATION: per-corpus and per-document continue buttons for incomplete docs"
change_id: FRONTEND-V2-CONTINUATION
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.249
architecture_impact: "frontend-v2 only, over the §0a enrich endpoints that already exist (POST /corpora/{id}/enrich, POST /documents/{id}/enrich). Two continuation controls wired into the Files screen. No backend change."
---

> Owner: "I need the UI to have a continuation button per corpus and document — 2 sep
> controls for incomplete docs." The backend §0a enrich buttons exist; V2 never wired them.

## Contract

An incomplete (not-vNext-ready) document/corpus must be re-drivable from the UI. The
backend exposes the two continuation primitives; the Files screen must surface both.

## Changes

`_mint_enrichment` (the §0a shared path) re-drives the corpus's latest run's parent
enrichment — for the whole corpus (`POST /corpora/{id}/enrich`) or one document
(`POST /documents/{id}/enrich`), returning `{status: queued, run_id, ticket_id, scope}`.
Wired **two separate controls** in Files:

1. **Continue corpus** — header button next to "＋ Add Files". Enabled only when the
   corpus has incomplete documents (shows the count); calls `enrichCorpus`. Disabled and
   labelled "all documents are vNext ready" when nothing is incomplete.
2. **▸ Continue** (per document) — in each row's action cell, shown **only for
   incomplete docs** (`!vnext_ready`); calls `enrichDocument(doc_id)`. Ready docs get no
   continue button (nothing to continue).

Both refresh the list on completion and surface backend errors (`describeError`).
`api.ts` gains `enrichCorpus` / `enrichDocument`.

## Proof

`tsc && vite build` clean, vitest proxy guard green. Live:
- served bundle `index-BJ3rXy1X.js` carries both "▸ Continue" and "Continue corpus";
- **per-document continuation fired for real** on an incomplete cinema doc:
  `POST /documents/doc_63ba98…/enrich` → `{status: "queued", run_id: run_d27feb…,
  ticket_id: tkt_8833ca…, scope: doc_63ba98…}` — it queued a real enrichment ticket;
- the corpus endpoint returns a clean `no_run_for_corpus` 404 on an all-ready corpus
  (rag-canary), which is exactly the state where the UI **disables** the corpus button —
  so the error is unreachable through the UI.

## Rejected claims

- **"Trigger the whole cinema corpus enrich to prove the corpus button."** Rejected:
  cinema is §19 spend-gated; the corpus path is the identical `_mint_enrichment` with
  `doc_id=None`, already proven by the per-doc call, so a single-doc queue proves the
  wiring without a large cinema operation.
- **"Show Continue on every row."** Rejected: the owner asked for it on INCOMPLETE docs;
  a ready doc has nothing to continue, so the button only renders when `!vnext_ready`.

## Open contract gaps

- "Continue" mints parent-enrichment (the §0a button's scope); a doc blocked on pMAP or a
  missing vNext profile specifically may need those stages re-driven too — this wires the
  button the backend offers, not a new orchestration. Whether one click clears a given
  doc depends on what it's blocked on.
- Actually draining the queued work is the fleet/§19 spend question, unchanged here.
