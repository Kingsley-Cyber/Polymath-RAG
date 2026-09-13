---
title: "WORK LOG — FRONTEND-V2-FILES-OPS-01: the Files screen lost filenames and both lifecycle operations"
change_id: FRONTEND-V2-FILES-OPS-01
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.246
architecture_impact: "frontend-v2 only. Adds three client methods (documents/upload/deleteDocument) over backend contracts that ALREADY EXIST, and rewrites the Files screen to use GET /documents as the identity authority with /documents/summary merged in. No backend change, no schema change, no retrieval/ingestion behaviour touched."
---

> The owner reported the V2 Files screen was missing add-file, delete-file, and showed
> a truncated content hash where the filename belongs. Verified: a V2 migration
> regression, not a backend gap — the backend already has all three capabilities.

## Contract

§23 frontend gate: "Files uses canonical readiness/status" and the V2 app must expose
working, backend-integrated views. A file manager that cannot add or delete files and
labels every row with a hash is not that.

## Changes

**Verified first — the backend already exposes everything, the frontend never wired it.**
Read against `orchestrator/orchestrator/api/ui.py`, not the owner's summary:

| route | shape (confirmed live) |
|---|---|
| `GET /documents?corpus_id=` | `{documents:[{doc_id, source_name, media_type, bytes, created_at, chunks, parents, enriched, enrich_failed, map_active}], runs}` |
| `POST /upload` | multipart `corpus_id`+`file`(+`allow_near_duplicate`); ext ∈ `.md .txt .html .pdf .epub .docx`; 409 duplicate / 413 too big / 422 bad-ext-or-empty |
| `DELETE /documents/{doc_id}?confirm=` | confirm = doc_id **or** source_name; 400 confirmation_required / 404 unknown / 409 runs_in_flight |

The frontend `api.ts` exposed only `documentSummaries()` — no `/documents`, no `/upload`,
no delete. And `Files.tsx` rendered the identity column as `{id.slice(0, 18)}…` — a
truncated content hash where the human filename belongs.

**Fix (frontend-v2 only):**

- `lib/api.ts` — added a multipart helper (`postForm`, no explicit content-type so the
  browser keeps the boundary) and a `del` helper, plus `documents()`, `upload()`,
  `deleteDocument()`. `upload` builds the exact `FormData` the route expects; `deleteDocument`
  passes the confirm token in the query string.
- `lib/contracts.ts` — `DocumentRow` / `DocumentsResponse` / `UploadResult` typed from
  the live route.
- `screens/Files.tsx` — `GET /documents` is now the IDENTITY/list authority:
  - **File** column is `source_name` (falls back to a short doc_id ONLY when a document
    genuinely has no name), with a small secondary doc_id, plus **Type** (extension),
    **Added** (date), **Size** (readable bytes);
  - `/documents/summary` is merged by `doc_id` for the operational columns (Status /
    pMAP / Profile / Graph), so a just-uploaded document with no summary yet still
    appears immediately, as PROCESSING;
  - **＋ Add Files** (multiple, accept-filtered) → `POST /upload` per file, per-file
    error surfaced, list refreshed on completion;
  - per-row **Delete** → confirm dialog naming the file → `DELETE …?confirm=<source_name>`
    → list refreshed. Backend rejections (409/413/422) are parsed and shown, not swallowed.
- `styles/app.css` — `banner--ok` (success), and the Files toolbar/name/delete classes.
  All colors are existing themeable tokens.

## Proof

**Build + guards.** `tsc --noEmit && vite build` clean; `vitest` proxy-coverage guard
green (`/documents` and `/upload` were already in the dev-proxy allowlist, and DELETE is
under the `/documents` prefix — no proxy change needed).

**Live, at the origin the proxy fronts (`127.0.0.1:7200/v2/`), new bundle
`index-Bj2oTFC3.js`:**
- the File column renders real names — `canary_59622_ZQX-59622.txt`, not a hash — with
  Type `TXT`, Added `Sep 9, 2026`, Size `3.5 KB`, Status `VNEXT READY`;
- **＋ Add Files** present; **10 Delete** buttons (one per row); no console errors.

**Full lifecycle round-trip, zero residue** (rag-canary, the designated probe corpus):
1. `POST /upload` with the UI's exact multipart → `accepted:true`, doc created; corpus
   10 → 11; the new row appeared in the UI by its filename `filesops_probe.md`.
2. Clicked the row's **Delete** in the browser → the page issued
   `DELETE /documents/doc_956…?confirm=filesops_probe.md → 200 OK` (the filename as the
   confirm token, exactly as designed).
3. `GET /documents` → probe gone; corpus back to **10**. The corpus is exactly as it was.

## Rejected claims

- **"The backend is missing upload/delete — build the pipeline."** Rejected on reading
  the routes: `POST /upload` and `DELETE /documents/{doc_id}` both exist and work. This
  was purely a frontend wiring regression.
- **"Trust the owner's endpoint signatures."** Not rejected, but not assumed either —
  every signature (multipart field names, the `confirm` semantics, the accepted
  extensions) was read from the source before wiring, and the confirm-by-filename
  behaviour came straight from the route's own code.
- **"Show the doc_id when a summary is missing."** Rejected: a freshly uploaded document
  has identity (`source_name`) from `/documents` before it has a summary, so it renders
  by name with a PROCESSING status rather than as a hash.

## Open contract gaps

- Upload is sequential and uses `window.confirm` for delete — deliberate for a tight,
  dependency-free slice; a drag-and-drop zone and an inline confirm are follow-ups, not
  blockers.
- The real public URL (`rag.kingsleylab.xyz/v2/`) is behind owner-held basic auth, so
  this is verified at the origin the proxy fronts, not through the credentialed URL —
  the same BLOCKED_OWNER boundary already recorded for the frontend gate (11.245).
