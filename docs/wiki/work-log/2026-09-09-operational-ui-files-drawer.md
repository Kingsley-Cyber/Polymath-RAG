---
title: "WORK LOG — Operational UI: Files health columns + document diagnostic drawer (frontend Slice 2)"
change_id: OPERATIONAL-UI-V1
date: 2026-09-09
owner: frontend (FilesView) — renders the CANONICAL-DOCUMENT-STATUS-V1 / summary contract, recomputes nothing
last_reviewed: 2026-09-09
status: complete (Slice 2 of the operational-UI frontend; Control Plane screen + Chat selectors follow)
register: 11.187
package: frontend/src/components/FilesView.tsx, frontend/src/api.ts, frontend/src/types.ts, frontend/src/app.css, frontend/dist/*, scripts/scaffold_polymath_v4.py
architecture_impact: "Frontend-only. Wires the operational-UI backend contract (register 11.187 backend slice) into the existing Files screen — the §1 health columns and the §2 diagnostic drawer. No new screen, no navigation change, no status math in React: every number is the backend authority (GET /documents/summary + GET /documents/{id}/status detail). Committed dist rebuilt; scaffold dist-hash declaration updated."
---

> **Ledger:** operational-UI brief §1 (Files health columns) + §2 (document diagnostic drawer) + register **11.187**. Minimal visual extension of the existing UI; no pipeline/architecture change.

## Contract

The Files screen answers "is THIS document healthy?" without a corpus scan on every render. Each row carries
compact operational columns; expanding a row opens the full per-document diagnostic. Both read ONE backend
authority — the frontend renders, never recomputes readiness (§11), and an under-mapped document must LOOK
unhealthy (§1).

## Changes

- **`types.ts`**: `DocSummary` (the `/documents/summary` row: children / parents / map_eligible / map_active /
  map_excluded / map_unresolved / profile_present / profile_vnext / graph_entities / graph_relations /
  vnext_ready); `DocumentStatus` extended with the drawer's detail sections (identity.bytes/run_id,
  profile.model/projected, full pMAP efficiency, `graph`, `projections`, `elapsed_s`, state.corpus_vnext_verdict).
- **`api.ts`**: `fetchDocumentsSummary(corpus)` → `Record<doc_id, DocSummary>` from `GET /documents/summary`.
- **`FilesView.tsx`**: Documents table columns now **File / Type / Size / Added / Parents / pMAP / Graph /
  Profile / Ready**. New cells render the batch summary: `PmapCell` (active/eligible; GREEN when fully mapped,
  **RED `st-failed` when unresolved>0**, amber while reconciling), `GraphCell` (entities/relations),
  `ProfileCell` (✓ vNext / ! legacy / … none), `ReadyCell` (backend `vnext_ready`, never inferred). The refresh
  fetches the summary as a best-effort batch so the base list never blocks on it. The row drawer's `StatusPanel`
  is rewritten into the §2 diagnostic: **DOCUMENT / GRAPH EXTRACTION / DOCUMENT PROFILE / PMAP / PROJECTIONS /
  READINESS**, each a wrapped row of labelled Stats with exact counts + the exact ordered `blockers` from the
  contract, and an elapsed-time badge. Removed the now-orphaned legacy `MapBadge`/`EnrichBadge` (the pMAP column
  + drawer supersede them); the per-doc `EnrichCell` action is unchanged (parent_enrichment stays legacy/bridge).
- **`app.css`**: `.ddrawer*` classes for the drawer (sections, labelled stats, ok/no glyphs, red blocker chip),
  reusing the existing `--good/--warn/--bad` status palette.
- **`frontend/dist/*` + `scaffold_polymath_v4.py`**: rebuilt production bundle (`npm run build` green); scaffold
  dist-hash declaration updated `index-BDrlm60s.js`/`index-ECN76Tar.css` → `index-fFvRpVKr.js`/`index-DP6HCqU5.css`.

## Proof

- `npm run build` (tsc --noEmit && vite build) → **green**, 293 modules.
- LIVE (orchestrator :7200): `GET /documents/summary?corpus_id=rag-canary` → 10 docs in **12 ms**, every row
  carries the exact `DocSummary` key set (asserted); `?corpus_id=cinema` → 67 docs in **620 ms**, **53 render RED**
  (unresolved>0) incl. 1319 eligible / 0 mapped / 1316 unresolved — the "must look unhealthy" case is real data.
  `GET /documents/{id}/status` (detail) returns every drawer section populated (identity.bytes/run_id, chunks,
  profile model+projected, pMAP coverage/efficiency, graph entities/relations/facts/predicates/neighborhoods,
  projections, corpus_vnext_verdict, elapsed_s, blockers).
- `repo_guard` ok; `wiki_worm --check` ok.

## Rejected claims

- **No readiness recomputed in React** — `ReadyCell` and the drawer render the backend `vnext_ready` /
  `blockers`; the frontend applies no status math (§11, §14).
- **No secret rendered** — the Files screen never touches lane/api-key data (that is the Control-Plane slice, and
  it exposes the env NAME only).
- **Not a corpus scan per render** — the columns come from ONE bounded batch endpoint (12 ms canary / 620 ms
  67-doc cinema), fetched best-effort alongside the existing document list (§12).

## Open contract gaps

- Slice 3: Control Plane screen (corpus summary + four functional-pool cards + model/account lanes, §3–8).
- Slice 4: Chat selectors (Query Type / Intent / Model / Reasoning; reasoning DEFAULT LOW, no auto-escalate, §9).
- Slice 5: §13 acceptance test against the live backend + durability (CONTINUITY / register close-out).
