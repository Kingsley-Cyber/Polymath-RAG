---
title: "WORK LOG — FRONTEND-V2-CORPUS-RESOLUTION: derive the default corpus from backend authority; gate corpus-scoped requests until it resolves"
change_id: FRONTEND-V2-CORPUS-RESOLUTION
date: 2026-09-12
owner: king
last_reviewed: 2026-09-12
status: complete
register: 11.250
architecture_impact: "frontend-v2 only (src/App.tsx). The active corpus is derived from /corpora (the backend authority) instead of a hardcoded name, and every corpus-scoped request is gated until a valid corpus resolves. No backend change; dist is a local build artifact (gitignored)."
---

> Owner: "Fix the default. Do not recreate `rag-canary` just to satisfy a frontend
> assumption. The live system currently has only `cinema`, while `App.tsx` still
> initializes to the now-missing `rag-canary`, causing a fresh V2 load to issue a 404
> until the user manually changes corpus. Derive the default from backend authority
> (valid persisted → first query-enabled → first → empty). Do not use another hardcoded
> fallback such as `cinema`. Prevent dependent API calls from firing while corpus
> resolution is still pending."

## Contract
`frontend-v2/src/App.tsx` initialised `corpusId` to the literal `"rag-canary"`. The live
backend holds only `cinema` (verified: `/corpora` = `[cinema(67)]`, `documents` table = 67
cinema rows, no `rag-canary`), so a cold `/v2/` load fired
`GET /semantic_readiness?corpus_id=rag-canary → 404` (plus two `control_plane?corpus_id=rag-canary`)
and painted a 404 banner on Overview until the user hand-picked a corpus.

Required behaviour (owner spec): resolve the active corpus from backend authority —
(1) a persisted/current corpus that still exists, else (2) the first **query-enabled**
corpus (`Corpus.query_ready`), else (3) the first returned corpus, else (4) none → explicit
empty state. **No hardcoded fallback** (not `cinema`). And no corpus-scoped request may fire
while resolution is pending — changing the seed from `"rag-canary"` to `""` alone would
merely swap a 404 for `corpus_id=` (empty), so requests must be *gated*, not re-seeded.
`rag-canary` must NOT be recreated to satisfy the frontend.

## Changes
`frontend-v2/src/App.tsx` only (all state-resolution; no new files, no backend touch):

- **Seed from persistence, not a literal.** `corpusId` initialises from
  `localStorage["polymath-v2.corpus"]` (new `CORPUS_KEY`), else `""` (= unresolved).
- **Backend authority derivations.** `corpusList = corpora.data ?? []`,
  `corporaLoaded = corpora.data != null || corpora.error != null`,
  `corpusValid = corpusId !== "" && corpusList.some(c => c.corpus_id === corpusId)`.
- **Resolution effect** (runs when `/corpora` lands and whenever the id stops being valid):
  keep a still-valid current/persisted id; else pick `find(query_ready)?.corpus_id ??
  corpusList[0]?.corpus_id ?? ""`. The `""` fallthrough is only reached when the backend
  has zero corpora.
- **Persistence effect:** a non-empty resolved corpus is written back to `CORPUS_KEY`, so a
  refresh/deep-link re-resolves to it (priority 1).
- **Gated control-plane probe.** The app-level `useAsync` for `/control_plane` now returns
  `Promise.resolve(null)` unless `corpusValid`, so it never fires for `""` or a stale id.
- **Gated screen render.** New `CORPUS_SCREENS` set (overview/chat/compare/files/control/
  graph); `<main>` renders those only when `corpusValid`, otherwise a "Resolving corpus…" /
  "No corpora yet" panel. Models/Settings (corpus-free) always render. Because every
  corpus-scoped screen owns its own `useAsync` hooks, gating the render gates the requests.
- **Selector + delete honour validity.** `<select value={corpusValid ? corpusId : ""}>`
  with a disabled placeholder (`Loading…` / `Select corpus…` / `No corpora`) and options
  from `corpusList` (no more `<option value={corpusId}>` echo of a dead name); "Delete
  corpus" disabled on `!corpusValid`; Settings shows `{corpusId || "—"}`.

## Proof
- **Build:** `tsc --noEmit && vite build` clean (52 modules); bundle hash changed
  `index-BJ3rXy1X.js → index-BbxsggDg.js`; orchestrator serves it live at
  `http://127.0.0.1:7200/v2/` (static-from-disk, no restart).
- **Fresh/no-previous-state load** (browser, `localStorage.clear()`, `corpusKey=null`):
  `performance.getEntriesByType("resource")` for the page load =
  `/corpora → /control_plane?corpus_id=cinema → /semantic_readiness?corpus_id=cinema`
  (+ a second `/corpora`+`control_plane?cinema`). **Zero `rag-canary`, zero `corpus_id=`
  (empty), zero transient 404.** Whole-session filter for `rag-canary` = `[]`.
- **Resolved corpus = `cinema`** — the first `query_ready` corpus, exists in `/corpora`
  (67 docs). Overview reads "Readiness for cinema" with the 404 banner GONE.
- **Every spec-named screen inherits it** (screenshots): Overview (cinema readiness +
  counts), Files (`cinema — 67 documents, 44 vNext-ready, 23 not ready`, real rows),
  Control Plane (`corpus cinema`, 67/44/23, 23 live workers), Chat ("Ask cinema anything"),
  Graph ("Source-attested relationships in cinema", attested entities).
- **Persistence / refresh:** after load `localStorage["polymath-v2.corpus"] == "cinema"`;
  a reload seeds `cinema`, validates it against `/corpora`, keeps it, fires only cinema.
- **Ground truth cross-check:** `/documents?corpus_id=cinema` = 67, `/control_plane?corpus_id=cinema`
  = 200, `/documents/summary?corpus_id=cinema` = 67 (the first Files paint showing "0 / not
  reachable" was a 2-second mid-load transient; it filled to 67 on settle).

## Rejected claims
- **"Default to `cinema`."** REJECTED per owner — no hardcoded fallback; the default is
  derived from `/corpora`. `cinema` is where resolution *lands today* only because it is the
  sole query-enabled corpus, not because it is named anywhere in the code.
- **"Recreate `rag-canary` as the fixture."** REJECTED per owner explicitly ("Do not
  recreate rag-canary just to satisfy a frontend assumption").
- **"Just seed `corpusId=""`."** Insufficient — it would fire `semantic_readiness?corpus_id=`
  (empty) → a different invalid request. The `corpusValid` gate on both the app-level probe
  and the screen render is what actually prevents the premature call.

## Open contract gaps
- **Corpus-less backend.** When `/corpora` is empty the app shows an explicit "No corpora
  yet" state but no create-corpus affordance (upload requires an existing `corpus_id`). Not
  exercised here (cinema present); a follow-up if a truly empty backend is a real path.
- **Deep-link is via persisted `localStorage`, not a URL parameter** — the app has no
  router, so "deep-link" means a refresh re-resolving the persisted corpus. A shareable
  `?corpus=` URL would be a separate router change, out of this slice.
- **Graph** was confirmed by the same uniform `corpusId`-prop + `CORPUS_SCREENS`-gate
  mechanism as the four screens driven live; not separately network-traced.
